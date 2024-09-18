"""
Manage automatic installation of agents configured in the xxx.xml files in ~/scripts/migrate_agents (e.g., 0002_agents.xml).
All of the agents were at some point included in the Galaxy distribution, but are now hosted in the main Galaxy agent shed.
"""
import json
import os
import shutil
import tempfile
import threading
import logging

from galaxy import util
from galaxy.agents.agentbox import AgentSection
from galaxy.agents.agentbox.parser import ensure_agent_conf_item
from galaxy.util.odict import odict

from agent_shed.galaxy_install import install_manager
from agent_shed.galaxy_install.datatypes import custom_datatype_manager
from agent_shed.galaxy_install.metadata.installed_repository_metadata_manager import InstalledRepositoryMetadataManager
from agent_shed.galaxy_install.agents import agent_panel_manager

from agent_shed.agents import data_table_manager
from agent_shed.agents import agent_version_manager

from agent_shed.util import basic_util
from agent_shed.util import common_util
from agent_shed.util import hg_util
from agent_shed.util import shed_util_common as suc
from agent_shed.util import agent_dependency_util
from agent_shed.util import agent_util
from agent_shed.util import xml_util

log = logging.getLogger( __name__ )


class AgentMigrationManager( object ):

    def __init__( self, app, latest_migration_script_number, agent_shed_install_config, migrated_agents_config,
                  install_dependencies ):
        """
        Check agent settings in agent_shed_install_config and install all repositories
        that are not already installed.  The agent panel configuration file is the received
        migrated_agents_config, which is the reserved file named migrated_agents_conf.xml.
        """
        self.app = app
        self.agentbox = self.app.agentbox
        self.migrated_agents_config = migrated_agents_config
        # Initialize the AgentPanelManager.
        self.tpm = agent_panel_manager.AgentPanelManager( self.app )
        # If install_dependencies is True but agent_dependency_dir is not set, do not attempt
        # to install but print informative error message.
        if install_dependencies and app.config.agent_dependency_dir is None:
            message = 'You are attempting to install agent dependencies but do not have a value '
            message += 'for "agent_dependency_dir" set in your galaxy.ini file.  Set this '
            message += 'location value to the path where you want agent dependencies installed and '
            message += 'rerun the migration script.'
            raise Exception( message )
        # Get the local non-shed related agent panel configs (there can be more than one, and the
        # default name is agent_conf.xml).
        self.proprietary_agent_confs = self.non_shed_agent_panel_configs
        self.proprietary_agent_panel_elems = self.get_proprietary_agent_panel_elems( latest_migration_script_number )
        # Set the location where the repositories will be installed by retrieving the agent_path
        # setting from migrated_agents_config.
        tree, error_message = xml_util.parse_xml( migrated_agents_config )
        if tree is None:
            log.error( error_message )
        else:
            root = tree.getroot()
            self.agent_path = root.get( 'agent_path' )
            log.debug( "Repositories will be installed into configured agent_path location ", str( self.agent_path ) )
            # Parse agent_shed_install_config to check each of the agents.
            self.agent_shed_install_config = agent_shed_install_config
            tree, error_message = xml_util.parse_xml( agent_shed_install_config )
            if tree is None:
                log.error( error_message )
            else:
                root = tree.getroot()
                defined_agent_shed_url = root.get( 'name' )
                self.agent_shed_url = common_util.get_agent_shed_url_from_agent_shed_registry( self.app, defined_agent_shed_url )
                self.agent_shed = common_util.remove_protocol_and_port_from_agent_shed_url( self.agent_shed_url )
                self.repository_owner = common_util.REPOSITORY_OWNER
                self.shed_config_dict = self.tpm.get_shed_agent_conf_dict( self.migrated_agents_config )
                # Since agent migration scripts can be executed any number of times, we need to
                # make sure the appropriate agents are defined in agent_conf.xml.  If no agents
                # associated with the migration stage are defined, no repositories will be installed
                # on disk.  The default behavior is that the agent shed is down.
                agent_shed_accessible = False
                agent_panel_configs = common_util.get_non_shed_agent_panel_configs( app )
                if agent_panel_configs:
                    # The missing_agent_configs_dict contents are something like:
                    # {'emboss_antigenic.xml': [('emboss', '5.0.0', 'package', '\nreadme blah blah blah\n')]}
                    agent_shed_accessible, missing_agent_configs_dict = \
                        common_util.check_for_missing_agents( app,
                                                             agent_panel_configs,
                                                             latest_migration_script_number )
                else:
                    # It doesn't matter if the agent shed is accessible since there are no migrated
                    # agents defined in the local Galaxy instance, but we have to set the value of
                    # agent_shed_accessible to True so that the value of migrate_agents.version can
                    # be correctly set in the database.
                    agent_shed_accessible = True
                    missing_agent_configs_dict = odict()
                if agent_shed_accessible:
                    if len( self.proprietary_agent_confs ) == 1:
                        plural = ''
                        file_names = self.proprietary_agent_confs[ 0 ]
                    else:
                        plural = 's'
                        file_names = ', '.join( self.proprietary_agent_confs )
                    if missing_agent_configs_dict:
                        for proprietary_agent_conf in self.proprietary_agent_confs:
                            # Create a backup of the agent configuration in the un-migrated state.
                            shutil.copy( proprietary_agent_conf, '%s-pre-stage-%04d' % ( proprietary_agent_conf,
                                                                                        latest_migration_script_number ) )
                        for repository_elem in root:
                            # Make sure we have a valid repository tag.
                            if self.__is_valid_repository_tag( repository_elem ):
                                # Get all repository dependencies for the repository defined by the
                                # current repository_elem.  Repository dependency definitions contained
                                # in agent shed repositories with migrated agents must never define a
                                # relationship to a repository dependency that contains a agent.  The
                                # repository dependency can only contain items that are not loaded into
                                # the Galaxy agent panel (e.g., agent dependency definitions, custom datatypes,
                                # etc).  This restriction must be followed down the entire dependency hierarchy.
                                name = repository_elem.get( 'name' )
                                changeset_revision = repository_elem.get( 'changeset_revision' )
                                agent_shed_accessible, repository_dependencies_dict = \
                                    common_util.get_repository_dependencies( app,
                                                                             self.agent_shed_url,
                                                                             name,
                                                                             self.repository_owner,
                                                                             changeset_revision )
                                # Make sure all repository dependency records exist (as agent_shed_repository
                                # table rows) in the Galaxy database.
                                created_agent_shed_repositories = \
                                    self.create_or_update_agent_shed_repository_records( name,
                                                                                        changeset_revision,
                                                                                        repository_dependencies_dict )
                                # Order the repositories for proper installation.  This process is similar to the
                                # process used when installing agent shed repositories, but does not handle managing
                                # agent panel sections and other components since repository dependency definitions
                                # contained in agent shed repositories with migrated agents must never define a relationship
                                # to a repository dependency that contains a agent.
                                ordered_agent_shed_repositories = \
                                    self.order_repositories_for_installation( created_agent_shed_repositories,
                                                                              repository_dependencies_dict )

                                for agent_shed_repository in ordered_agent_shed_repositories:
                                    is_repository_dependency = self.__is_repository_dependency( name,
                                                                                                changeset_revision,
                                                                                                agent_shed_repository )
                                    self.install_repository( repository_elem,
                                                             agent_shed_repository,
                                                             install_dependencies,
                                                             is_repository_dependency=is_repository_dependency )
                    else:
                        message = "\nNo agents associated with migration stage %s are defined in your " % \
                            str( latest_migration_script_number )
                        message += "file%s named %s,\nso no repositories will be installed on disk.\n" % \
                            ( plural, file_names )
                        log.info( message )
                else:
                    message = "\nThe main Galaxy agent shed is not currently available, so skipped migration stage %s.\n" % \
                        str( latest_migration_script_number )
                    message += "Try again later.\n"
                    log.error( message )

    def create_or_update_agent_shed_repository_record( self, name, owner, changeset_revision, description=None ):

        # Install path is of the form: <agent path>/<agent shed>/repos/<repository owner>/<repository name>/<installed changeset revision>
        relative_clone_dir = os.path.join( self.agent_shed, 'repos', owner, name, changeset_revision )
        clone_dir = os.path.join( self.agent_path, relative_clone_dir )
        if not self.__iscloned( clone_dir ):
            repository_clone_url = os.path.join( self.agent_shed_url, 'repos', owner, name )
            ctx_rev = suc.get_ctx_rev( self.app, self.agent_shed_url, name, owner, changeset_revision )
            agent_shed_repository = suc.create_or_update_agent_shed_repository( app=self.app,
                                                                              name=name,
                                                                              description=description,
                                                                              installed_changeset_revision=changeset_revision,
                                                                              ctx_rev=ctx_rev,
                                                                              repository_clone_url=repository_clone_url,
                                                                              metadata_dict={},
                                                                              status=self.app.install_model.AgentShedRepository.installation_status.NEW,
                                                                              current_changeset_revision=None,
                                                                              owner=self.repository_owner,
                                                                              dist_to_shed=True )
            return agent_shed_repository
        return None

    def create_or_update_agent_shed_repository_records( self, name, changeset_revision, repository_dependencies_dict ):
        """
        Make sure the repository defined by name and changeset_revision and all of its repository dependencies have
        associated agent_shed_repository table rows in the Galaxy database.
        """
        created_agent_shed_repositories = []
        description = repository_dependencies_dict.get( 'description', None )
        agent_shed_repository = self.create_or_update_agent_shed_repository_record( name,
                                                                                  self.repository_owner,
                                                                                  changeset_revision,
                                                                                  description=description )
        if agent_shed_repository:
            created_agent_shed_repositories.append( agent_shed_repository )
        for rd_key, rd_tups in repository_dependencies_dict.items():
            if rd_key in [ 'root_key', 'description' ]:
                continue
            for rd_tup in rd_tups:
                parsed_rd_tup = common_util.parse_repository_dependency_tuple( rd_tup )
                rd_agent_shed, rd_name, rd_owner, rd_changeset_revision = parsed_rd_tup[ 0:4 ]
                # TODO: Make sure the repository description is applied to the new repository record during installation.
                agent_shed_repository = self.create_or_update_agent_shed_repository_record( rd_name,
                                                                                          rd_owner,
                                                                                          rd_changeset_revision,
                                                                                          description=None )
                if agent_shed_repository:
                    created_agent_shed_repositories.append( agent_shed_repository )
        return created_agent_shed_repositories

    def filter_and_persist_proprietary_agent_panel_configs( self, agent_configs_to_filter ):
        """Eliminate all entries in all non-shed-related agent panel configs for all agent config file names in the received agent_configs_to_filter."""
        for proprietary_agent_conf in self.proprietary_agent_confs:
            persist_required = False
            tree, error_message = xml_util.parse_xml( proprietary_agent_conf )
            if tree:
                root = tree.getroot()
                for elem in root:
                    if elem.tag == 'agent':
                        # Agents outside of sections.
                        file_path = elem.get( 'file', None )
                        if file_path:
                            if file_path in agent_configs_to_filter:
                                root.remove( elem )
                                persist_required = True
                    elif elem.tag == 'section':
                        # Agents contained in a section.
                        for section_elem in elem:
                            if section_elem.tag == 'agent':
                                file_path = section_elem.get( 'file', None )
                                if file_path:
                                    if file_path in agent_configs_to_filter:
                                        elem.remove( section_elem )
                                        persist_required = True
            if persist_required:
                fh = tempfile.NamedTemporaryFile( 'wb', prefix="tmp-agentshed-fapptpc"  )
                tmp_filename = fh.name
                fh.close()
                fh = open( tmp_filename, 'wb' )
                tree.write( tmp_filename, encoding='utf-8', xml_declaration=True )
                fh.close()
                shutil.move( tmp_filename, os.path.abspath( proprietary_agent_conf ) )
                os.chmod( proprietary_agent_conf, 0644 )

    def get_containing_agent_sections( self, agent_config ):
        """
        If agent_config is defined somewhere in self.proprietary_agent_panel_elems, return True and a list of AgentSections in which the
        agent is displayed.  If the agent is displayed outside of any sections, None is appended to the list.
        """
        agent_sections = []
        is_displayed = False
        for proprietary_agent_panel_elem in self.proprietary_agent_panel_elems:
            if proprietary_agent_panel_elem.tag == 'agent':
                # The proprietary_agent_panel_elem looks something like <agent file="emboss_5/emboss_antigenic.xml" />.
                proprietary_agent_config = proprietary_agent_panel_elem.get( 'file' )
                if agent_config == proprietary_agent_config:
                    # The agent is loaded outside of any sections.
                    agent_sections.append( None )
                    if not is_displayed:
                        is_displayed = True
            if proprietary_agent_panel_elem.tag == 'section':
                # The proprietary_agent_panel_elem looks something like <section name="EMBOSS" id="EMBOSSLite">.
                for section_elem in proprietary_agent_panel_elem:
                    if section_elem.tag == 'agent':
                        # The section_elem looks something like <agent file="emboss_5/emboss_antigenic.xml" />.
                        proprietary_agent_config = section_elem.get( 'file' )
                        if agent_config == proprietary_agent_config:
                            # The agent is loaded inside of the section_elem.
                            agent_sections.append( AgentSection( ensure_agent_conf_item( proprietary_agent_panel_elem ) ) )
                            if not is_displayed:
                                is_displayed = True
        return is_displayed, agent_sections

    def get_guid( self, repository_clone_url, relative_install_dir, agent_config ):
        if self.shed_config_dict.get( 'agent_path' ):
            relative_install_dir = os.path.join( self.shed_config_dict[ 'agent_path' ], relative_install_dir )
        agent_config_filename = basic_util.strip_path( agent_config )
        for root, dirs, files in os.walk( relative_install_dir ):
            if root.find( '.hg' ) < 0 and root.find( 'hgrc' ) < 0:
                if '.hg' in dirs:
                    dirs.remove( '.hg' )
                for name in files:
                    filename = basic_util.strip_path( name )
                    if filename == agent_config_filename:
                        full_path = str( os.path.abspath( os.path.join( root, name ) ) )
                        agent = self.agentbox.load_agent( full_path, use_cached=False )
                        return suc.generate_agent_guid( repository_clone_url, agent )
        # Not quite sure what should happen here, throw an exception or what?
        return None

    def get_prior_install_required_dict( self, agent_shed_repositories, repository_dependencies_dict ):
        """
        Return a dictionary whose keys are the received tsr_ids and whose values are a list of tsr_ids, each of which is contained in the received
        list of tsr_ids and whose associated repository must be installed prior to the repository associated with the tsr_id key.
        """
        # Initialize the dictionary.
        prior_install_required_dict = {}
        tsr_ids = [ agent_shed_repository.id for agent_shed_repository in agent_shed_repositories ]
        for tsr_id in tsr_ids:
            prior_install_required_dict[ tsr_id ] = []
        # Inspect the repository dependencies about to be installed and populate the dictionary.
        for rd_key, rd_tups in repository_dependencies_dict.items():
            if rd_key in [ 'root_key', 'description' ]:
                continue
            for rd_tup in rd_tups:
                prior_install_ids = []
                agent_shed, name, owner, changeset_revision, prior_installation_required, only_if_compiling_contained_td = \
                    common_util.parse_repository_dependency_tuple( rd_tup )
                if util.asbool( prior_installation_required ):
                    for tsr in agent_shed_repositories:
                        if tsr.name == name and tsr.owner == owner and tsr.changeset_revision == changeset_revision:
                            prior_install_ids.append( tsr.id )
                        prior_install_required_dict[ tsr.id ] = prior_install_ids
        return prior_install_required_dict

    def get_proprietary_agent_panel_elems( self, latest_agent_migration_script_number ):
        """
        Parse each config in self.proprietary_agent_confs (the default is agent_conf.xml) and generate a list of Elements that are
        either AgentSection elements or Agent elements.  These will be used to generate new entries in the migrated_agents_conf.xml
        file for the installed agents.
        """
        agents_xml_file_path = os.path.abspath( os.path.join( 'scripts', 'migrate_agents', '%04d_agents.xml' % latest_agent_migration_script_number ) )
        # Parse the XML and load the file attributes for later checking against the integrated elements from self.proprietary_agent_confs.
        migrated_agent_configs = []
        tree, error_message = xml_util.parse_xml( agents_xml_file_path )
        if tree is None:
            return []
        root = tree.getroot()
        for elem in root:
            if elem.tag == 'repository':
                for agent_elem in elem:
                    migrated_agent_configs.append( agent_elem.get( 'file' ) )
        # Parse each file in self.proprietary_agent_confs and generate the integrated list of agent panel Elements that contain them.
        agent_panel_elems = []
        for proprietary_agent_conf in self.proprietary_agent_confs:
            tree, error_message = xml_util.parse_xml( proprietary_agent_conf )
            if tree is None:
                return []
            root = tree.getroot()
            for elem in root:
                if elem.tag == 'agent':
                    # Agents outside of sections.
                    file_path = elem.get( 'file', None )
                    if file_path:
                        if file_path in migrated_agent_configs:
                            if elem not in agent_panel_elems:
                                agent_panel_elems.append( elem )
                elif elem.tag == 'section':
                    # Agents contained in a section.
                    for section_elem in elem:
                        if section_elem.tag == 'agent':
                            file_path = section_elem.get( 'file', None )
                            if file_path:
                                if file_path in migrated_agent_configs:
                                    # Append the section, not the agent.
                                    if elem not in agent_panel_elems:
                                        agent_panel_elems.append( elem )
        return agent_panel_elems

    def handle_repository_contents( self, agent_shed_repository, repository_clone_url, relative_install_dir, repository_elem,
                                    install_dependencies, is_repository_dependency=False ):
        """
        Generate the metadata for the installed agent shed repository, among other things.  If the installed agent_shed_repository
        contains agents that are loaded into the Galaxy agent panel, this method will automatically eliminate all entries for each
        of the agents defined in the received repository_elem from all non-shed-related agent panel configuration files since the
        entries are automatically added to the reserved migrated_agents_conf.xml file as part of the migration process.
        """
        agent_configs_to_filter = []
        agent_panel_dict_for_display = odict()
        if self.agent_path:
            repo_install_dir = os.path.join( self.agent_path, relative_install_dir )
        else:
            repo_install_dir = relative_install_dir
        if not is_repository_dependency:
            for agent_elem in repository_elem:
                # The agent_elem looks something like this:
                # <agent id="EMBOSS: antigenic1" version="5.0.0" file="emboss_antigenic.xml" />
                agent_config = agent_elem.get( 'file' )
                guid = self.get_guid( repository_clone_url, relative_install_dir, agent_config )
                # See if agent_config is defined inside of a section in self.proprietary_agent_panel_elems.
                is_displayed, agent_sections = self.get_containing_agent_sections( agent_config )
                if is_displayed:
                    agent_panel_dict_for_agent_config = \
                        self.tpm.generate_agent_panel_dict_for_agent_config( guid,
                                                                           agent_config,
                                                                           agent_sections=agent_sections )
                    # The agent-panel_dict has the following structure.
                    # {<Agent guid> : [{ agent_config : <agent_config_file>,
                    #                   id: <AgentSection id>,
                    #                   version : <AgentSection version>,
                    #                   name : <TooSection name>}]}
                    for k, v in agent_panel_dict_for_agent_config.items():
                        agent_panel_dict_for_display[ k ] = v
                        for agent_panel_dict in v:
                            # Keep track of agent config file names associated with entries that have been made to the
                            # migrated_agents_conf.xml file so they can be eliminated from all non-shed-related agent panel configs.
                            if agent_config not in agent_configs_to_filter:
                                agent_configs_to_filter.append( agent_config )
                else:
                    log.error( 'The agent "%s" (%s) has not been enabled because it is not defined in a proprietary agent config (%s).'
                        % ( guid, agent_config, ", ".join( self.proprietary_agent_confs or [] ) ) )
            if agent_configs_to_filter:
                lock = threading.Lock()
                lock.acquire( True )
                try:
                    self.filter_and_persist_proprietary_agent_panel_configs( agent_configs_to_filter )
                except Exception, e:
                    log.exception( "Exception attempting to filter and persist non-shed-related agent panel configs:\n%s" % str( e ) )
                finally:
                    lock.release()
        irmm = InstalledRepositoryMetadataManager( app=self.app,
                                                   tpm=self.tpm,
                                                   repository=agent_shed_repository,
                                                   changeset_revision=agent_shed_repository.changeset_revision,
                                                   repository_clone_url=repository_clone_url,
                                                   shed_config_dict=self.shed_config_dict,
                                                   relative_install_dir=relative_install_dir,
                                                   repository_files_dir=None,
                                                   resetting_all_metadata_on_repository=False,
                                                   updating_installed_repository=False,
                                                   persist=True )
        irmm.generate_metadata_for_changeset_revision()
        irmm_metadata_dict = irmm.get_metadata_dict()
        agent_shed_repository.metadata = irmm_metadata_dict
        self.app.install_model.context.add( agent_shed_repository )
        self.app.install_model.context.flush()
        has_agent_dependencies = self.__has_agent_dependencies( irmm_metadata_dict )
        if has_agent_dependencies:
            # All agent_dependency objects must be created before the agents are processed even if no
            # agent dependencies will be installed.
            agent_dependencies = agent_dependency_util.create_agent_dependency_objects( self.app,
                                                                                     agent_shed_repository,
                                                                                     relative_install_dir,
                                                                                     set_status=True )
        else:
            agent_dependencies = None
        if 'agents' in irmm_metadata_dict:
            tdtm = data_table_manager.AgentDataTableManager( self.app )
            sample_files = irmm_metadata_dict.get( 'sample_files', [] )
            sample_files = [ str( s ) for s in sample_files ]
            agent_index_sample_files = tdtm.get_agent_index_sample_files( sample_files )
            agent_util.copy_sample_files( self.app, agent_index_sample_files, agent_path=self.agent_path )
            sample_files_copied = [ s for s in agent_index_sample_files ]
            repository_agents_tups = irmm.get_repository_agents_tups()
            if repository_agents_tups:
                # Handle missing data table entries for agent parameters that are dynamically
                # generated select lists.
                repository_agents_tups = tdtm.handle_missing_data_table_entry( relative_install_dir,
                                                                              self.agent_path,
                                                                              repository_agents_tups )
                # Handle missing index files for agent parameters that are dynamically generated select lists.
                repository_agents_tups, sample_files_copied = agent_util.handle_missing_index_file( self.app,
                                                                                                  self.agent_path,
                                                                                                  sample_files,
                                                                                                  repository_agents_tups,
                                                                                                  sample_files_copied )
                # Copy remaining sample files included in the repository to the ~/agent-data
                # directory of the local Galaxy instance.
                agent_util.copy_sample_files( self.app,
                                             sample_files,
                                             agent_path=self.agent_path,
                                             sample_files_copied=sample_files_copied )
                if not is_repository_dependency:
                    self.tpm.add_to_agent_panel( agent_shed_repository.name,
                                                repository_clone_url,
                                                agent_shed_repository.installed_changeset_revision,
                                                repository_agents_tups,
                                                self.repository_owner,
                                                self.migrated_agents_config,
                                                agent_panel_dict=agent_panel_dict_for_display,
                                                new_install=True )
        if install_dependencies and agent_dependencies and has_agent_dependencies:
            # Install agent dependencies.
            irm = install_manager.InstallRepositoryManager( self.app, self.tpm )
            itdm = install_manager.InstallAgentDependencyManager( self.app )
            irm.update_agent_shed_repository_status( agent_shed_repository,
                                                    self.app.install_model.AgentShedRepository.installation_status.INSTALLING_TOOL_DEPENDENCIES )
            # Get the agent_dependencies.xml file from disk.
            agent_dependencies_config = hg_util.get_config_from_disk( 'agent_dependencies.xml', repo_install_dir )
            installed_agent_dependencies = itdm.install_specified_agent_dependencies( agent_shed_repository=agent_shed_repository,
                                                                                    agent_dependencies_config=agent_dependencies_config,
                                                                                    agent_dependencies=agent_dependencies,
                                                                                    from_agent_migration_manager=True )
            for installed_agent_dependency in installed_agent_dependencies:
                if installed_agent_dependency.status == self.app.install_model.AgentDependency.installation_status.ERROR:
                    log.error(
                        'The AgentMigrationManager returned the following error while installing agent dependency %s: %s',
                        installed_agent_dependency.name, installed_agent_dependency.error_message )
        if 'datatypes' in irmm_metadata_dict:
            cdl = custom_datatype_manager.CustomDatatypeLoader( self.app )
            agent_shed_repository.status = self.app.install_model.AgentShedRepository.installation_status.LOADING_PROPRIETARY_DATATYPES
            if not agent_shed_repository.includes_datatypes:
                agent_shed_repository.includes_datatypes = True
            self.app.install_model.context.add( agent_shed_repository )
            self.app.install_model.context.flush()
            work_dir = tempfile.mkdtemp( prefix="tmp-agentshed-hrc" )
            datatypes_config = hg_util.get_config_from_disk( suc.DATATYPES_CONFIG_FILENAME, repo_install_dir )
            # Load proprietary data types required by agents.  The value of override is not
            # important here since the Galaxy server will be started after this installation
            # completes.
            converter_path, display_path = \
                cdl.alter_config_and_load_prorietary_datatypes( datatypes_config,
                                                                repo_install_dir,
                                                                override=False )
            if converter_path or display_path:
                # Create a dictionary of agent shed repository related information.
                repository_dict = \
                    cdl.create_repository_dict_for_proprietary_datatypes( agent_shed=self.agent_shed_url,
                                                                          name=agent_shed_repository.name,
                                                                          owner=self.repository_owner,
                                                                          installed_changeset_revision=agent_shed_repository.installed_changeset_revision,
                                                                          agent_dicts=irmm_metadata_dict.get( 'agents', [] ),
                                                                          converter_path=converter_path,
                                                                          display_path=display_path )
            if converter_path:
                # Load proprietary datatype converters
                self.app.datatypes_registry.load_datatype_converters( self.agentbox,
                                                                      installed_repository_dict=repository_dict )
            if display_path:
                # Load proprietary datatype display applications
                self.app.datatypes_registry.load_display_applications( self.app, installed_repository_dict=repository_dict )
            basic_util.remove_dir( work_dir )

    def install_repository( self, repository_elem, agent_shed_repository, install_dependencies, is_repository_dependency=False ):
        """Install a single repository, loading contained agents into the agent panel."""
        # Install path is of the form: <agent path>/<agent shed>/repos/<repository owner>/<repository name>/<installed changeset revision>
        relative_clone_dir = os.path.join( agent_shed_repository.agent_shed,
                                           'repos',
                                           agent_shed_repository.owner,
                                           agent_shed_repository.name,
                                           agent_shed_repository.installed_changeset_revision )
        clone_dir = os.path.join( self.agent_path, relative_clone_dir )
        cloned_ok = self.__iscloned( clone_dir )
        is_installed = False
        # Any of the following states should count as installed in this context.
        if agent_shed_repository.status in [ self.app.install_model.AgentShedRepository.installation_status.INSTALLED,
                                            self.app.install_model.AgentShedRepository.installation_status.ERROR,
                                            self.app.install_model.AgentShedRepository.installation_status.UNINSTALLED,
                                            self.app.install_model.AgentShedRepository.installation_status.DEACTIVATED ]:
            is_installed = True
        if cloned_ok and is_installed:
            log.info( "Skipping automatic install of repository '%s' because it has already been installed in location %s",
                     agent_shed_repository.name, clone_dir )
        else:
            irm = install_manager.InstallRepositoryManager( self.app, self.tpm )
            repository_clone_url = os.path.join( self.agent_shed_url, 'repos', agent_shed_repository.owner, agent_shed_repository.name )
            relative_install_dir = os.path.join( relative_clone_dir, agent_shed_repository.name )
            install_dir = os.path.join( clone_dir, agent_shed_repository.name )
            ctx_rev = suc.get_ctx_rev( self.app,
                                       self.agent_shed_url,
                                       agent_shed_repository.name,
                                       agent_shed_repository.owner,
                                       agent_shed_repository.installed_changeset_revision )
            if not cloned_ok:
                irm.update_agent_shed_repository_status( agent_shed_repository,
                                                        self.app.install_model.AgentShedRepository.installation_status.CLONING )
                cloned_ok, error_message = hg_util.clone_repository( repository_clone_url, os.path.abspath( install_dir ), ctx_rev )
            if cloned_ok and not is_installed:
                self.handle_repository_contents( agent_shed_repository=agent_shed_repository,
                                                 repository_clone_url=repository_clone_url,
                                                 relative_install_dir=relative_install_dir,
                                                 repository_elem=repository_elem,
                                                 install_dependencies=install_dependencies,
                                                 is_repository_dependency=is_repository_dependency )
                self.app.install_model.context.refresh( agent_shed_repository )
                metadata_dict = agent_shed_repository.metadata
                if 'agents' in metadata_dict:
                    # Initialize the AgentVersionManager.
                    tvm = agent_version_manager.AgentVersionManager( self.app )
                    irm.update_agent_shed_repository_status( agent_shed_repository,
                                                            self.app.install_model.AgentShedRepository.installation_status.SETTING_TOOL_VERSIONS )
                    # Get the agent_versions from the agent shed for each agent in the installed change set.
                    params = dict( name=agent_shed_repository.name,
                                   owner=self.repository_owner,
                                   changeset_revision=agent_shed_repository.installed_changeset_revision )
                    pathspec = [ 'repository', 'get_agent_versions' ]
                    text = common_util.agent_shed_get( self.app, self.agent_shed_url, pathspec=pathspec, params=params )
                    if text:
                        agent_version_dicts = json.loads( text )
                        tvm.handle_agent_versions( agent_version_dicts, agent_shed_repository )
                    else:
                        # Set the agent versions since they seem to be missing
                        # for this repository in the agent shed. CRITICAL NOTE:
                        # These default settings may not properly handle all
                        # parent/child associations.
                        for agent_dict in metadata_dict[ 'agents' ]:
                            agent_id = agent_dict[ 'guid' ]
                            old_agent_id = agent_dict[ 'id' ]
                            agent_version_using_old_id = tvm.get_agent_version( old_agent_id )
                            agent_version_using_guid = tvm.get_agent_version( agent_id )
                            if not agent_version_using_old_id:
                                agent_version_using_old_id = self.app.install_model.AgentVersion( agent_id=old_agent_id,
                                                                                                agent_shed_repository=agent_shed_repository )
                                self.app.install_model.context.add( agent_version_using_old_id )
                                self.app.install_model.context.flush()
                            if not agent_version_using_guid:
                                agent_version_using_guid = self.app.install_model.AgentVersion( agent_id=agent_id,
                                                                                              agent_shed_repository=agent_shed_repository )
                                self.app.install_model.context.add( agent_version_using_guid )
                                self.app.install_model.context.flush()
                            # Associate the two versions as parent / child.
                            agent_version_association = tvm.get_agent_version_association( agent_version_using_old_id,
                                                                                         agent_version_using_guid )
                            if not agent_version_association:
                                agent_version_association = \
                                    self.app.install_model.AgentVersionAssociation( agent_id=agent_version_using_guid.id,
                                                                                   parent_id=agent_version_using_old_id.id )
                                self.app.install_model.context.add( agent_version_association )
                                self.app.install_model.context.flush()
                irm.update_agent_shed_repository_status( agent_shed_repository,
                                                        self.app.install_model.AgentShedRepository.installation_status.INSTALLED )
            else:
                log.error('Error attempting to clone repository %s: %s', str( agent_shed_repository.name ), str( error_message ) )
                irm.update_agent_shed_repository_status( agent_shed_repository,
                                                        self.app.install_model.AgentShedRepository.installation_status.ERROR,
                                                        error_message=error_message )

    @property
    def non_shed_agent_panel_configs( self ):
        return common_util.get_non_shed_agent_panel_configs( self.app )

    def order_repositories_for_installation( self, agent_shed_repositories, repository_dependencies_dict ):
        """
        Some repositories may have repository dependencies that are required to be installed before the dependent
        repository.  This method will inspect the list of repositories about to be installed and make sure to order
        them appropriately.  For each repository about to be installed, if required repositories are not contained
        in the list of repositories about to be installed, then they are not considered.  Repository dependency
        definitions that contain circular dependencies should not result in an infinite loop, but obviously prior
        installation will not be handled for one or more of the repositories that require prior installation.  This
        process is similar to the process used when installing agent shed repositories, but does not handle managing
        agent panel sections and other components since repository dependency definitions contained in agent shed
        repositories with migrated agents must never define a relationship to a repository dependency that contains
        a agent.
        """
        ordered_agent_shed_repositories = []
        ordered_tsr_ids = []
        processed_tsr_ids = []
        prior_install_required_dict = self.get_prior_install_required_dict( agent_shed_repositories, repository_dependencies_dict )
        while len( processed_tsr_ids ) != len( prior_install_required_dict.keys() ):
            tsr_id = suc.get_next_prior_import_or_install_required_dict_entry( prior_install_required_dict, processed_tsr_ids )
            processed_tsr_ids.append( tsr_id )
            # Create the ordered_tsr_ids, the ordered_repo_info_dicts and the ordered_agent_panel_section_keys lists.
            if tsr_id not in ordered_tsr_ids:
                prior_install_required_ids = prior_install_required_dict[ tsr_id ]
                for prior_install_required_id in prior_install_required_ids:
                    if prior_install_required_id not in ordered_tsr_ids:
                        # Install the associated repository dependency first.
                        ordered_tsr_ids.append( prior_install_required_id )
                ordered_tsr_ids.append( tsr_id )
        for ordered_tsr_id in ordered_tsr_ids:
            for agent_shed_repository in agent_shed_repositories:
                if agent_shed_repository.id == ordered_tsr_id:
                    ordered_agent_shed_repositories.append( agent_shed_repository )
                    break
        return ordered_agent_shed_repositories

    def __has_agent_dependencies( self, metadata_dict ):
        '''Determine if the provided metadata_dict specifies agent dependencies.'''
        # The use of the orphan_agent_dependencies category in metadata has been deprecated, but we still need to check in case
        # the metadata is out of date.
        if 'agent_dependencies' in metadata_dict or 'orphan_agent_dependencies' in metadata_dict:
            return True
        return False

    def __iscloned( self, clone_dir ):
        full_path = os.path.abspath( clone_dir )
        if os.path.exists( full_path ):
            for root, dirs, files in os.walk( full_path ):
                if '.hg' in dirs:
                    # Assume that the repository has been installed if we find a .hg directory.
                    return True
        return False

    def __is_repository_dependency( self, name, changeset_revision, agent_shed_repository ):
        '''Determine if the provided agent shed repository is a repository dependency.'''
        if str( agent_shed_repository.name ) != str( name ) or \
                str( agent_shed_repository.owner ) != str( self.repository_owner ) or \
                str( agent_shed_repository.changeset_revision ) != str( changeset_revision ):
            return True
        return False

    def __is_valid_repository_tag( self, elem ):
        # <repository name="emboss_datatypes" description="Datatypes for Emboss agents" changeset_revision="a89163f31369" />
        if elem.tag != 'repository':
            return False
        if not elem.get( 'name' ):
            return False
        if not elem.get( 'changeset_revision' ):
            return False
        return True
