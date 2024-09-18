"""
Class encapsulating the management of repositories installed into Galaxy from the Agent Shed.
"""
import copy
import logging
import os

from sqlalchemy import and_, false, true

from galaxy import util
from agent_shed.util import common_util
from agent_shed.util import container_util
from agent_shed.util import shed_util_common as suc
from agent_shed.util import agent_dependency_util
from agent_shed.util import xml_util

from agent_shed.galaxy_install.datatypes import custom_datatype_manager
from agent_shed.galaxy_install.metadata.installed_repository_metadata_manager import InstalledRepositoryMetadataManager
from agent_shed.galaxy_install.repository_dependencies import repository_dependency_manager
from agent_shed.galaxy_install.agents import data_manager
from agent_shed.galaxy_install.agents import agent_panel_manager

log = logging.getLogger( __name__ )


class InstalledRepositoryManager( object ):

    def __init__( self, app ):
        """
        Among other things, keep in in-memory sets of tuples defining installed repositories and agent dependencies along with
        the relationships between each of them.  This will allow for quick discovery of those repositories or components that
        can be uninstalled.  The feature allowing a Galaxy administrator to uninstall a repository should not be available to
        repositories or agent dependency packages that are required by other repositories or their contents (packages). The
        uninstall feature should be available only at the repository hierarchy level where every dependency will be uninstalled.
        The exception for this is if an item (repository or agent dependency package) is not in an INSTALLED state - in these
        cases, the specific item can be uninstalled in order to attempt re-installation.
        """
        self.app = app
        self.install_model = self.app.install_model
        self.context = self.install_model.context
        self.agent_configs = self.app.config.agent_configs
        if self.app.config.migrated_agents_config not in self.agent_configs:
            self.agent_configs.append( self.app.config.migrated_agents_config )
        self.installed_repository_dicts = []
        # Keep an in-memory dictionary whose keys are tuples defining agent_shed_repository objects (whose status is 'Installed')
        # and whose values are a list of tuples defining agent_shed_repository objects (whose status can be anything) required by
        # the key.  The value defines the entire repository dependency tree.
        self.repository_dependencies_of_installed_repositories = {}
        # Keep an in-memory dictionary whose keys are tuples defining agent_shed_repository objects (whose status is 'Installed')
        # and whose values are a list of tuples defining agent_shed_repository objects (whose status is 'Installed') required by
        # the key.  The value defines the entire repository dependency tree.
        self.installed_repository_dependencies_of_installed_repositories = {}
        # Keep an in-memory dictionary whose keys are tuples defining agent_shed_repository objects (whose status is 'Installed')
        # and whose values are a list of tuples defining agent_shed_repository objects (whose status is 'Installed') that require
        # the key.
        self.installed_dependent_repositories_of_installed_repositories = {}
        # Keep an in-memory dictionary whose keys are tuples defining agent_shed_repository objects (whose status is 'Installed')
        # and whose values are a list of tuples defining its immediate agent_dependency objects (whose status can be anything).
        # The value defines only the immediate agent dependencies of the repository and does not include any dependencies of the
        # agent dependencies.
        self.agent_dependencies_of_installed_repositories = {}
        # Keep an in-memory dictionary whose keys are tuples defining agent_shed_repository objects (whose status is 'Installed')
        # and whose values are a list of tuples defining its immediate agent_dependency objects (whose status is 'Installed').
        # The value defines only the immediate agent dependencies of the repository and does not include any dependencies of the
        # agent dependencies.
        self.installed_agent_dependencies_of_installed_repositories = {}
        # Keep an in-memory dictionary whose keys are tuples defining agent_dependency objects (whose status is 'Installed') and
        # whose values are a list of tuples defining agent_dependency objects (whose status can be anything) required by the
        # installed agent dependency at runtime.  The value defines the entire agent dependency tree.
        self.runtime_agent_dependencies_of_installed_agent_dependencies = {}
        # Keep an in-memory dictionary whose keys are tuples defining agent_dependency objects (whose status is 'Installed') and
        # whose values are a list of tuples defining agent_dependency objects (whose status is 'Installed') that require the key
        # at runtime.  The value defines the entire agent dependency tree.
        self.installed_runtime_dependent_agent_dependencies_of_installed_agent_dependencies = {}
        if app.config.manage_dependency_relationships:
            # Load defined dependency relationships for installed agent shed repositories and their contents.
            self.load_dependency_relationships()

    def activate_repository( self, repository ):
        """Activate an installed agent shed repository that has been marked as deactivated."""
        repository_clone_url = common_util.generate_clone_url_for_installed_repository( self.app, repository )
        shed_agent_conf, agent_path, relative_install_dir = suc.get_agent_panel_config_agent_path_install_dir( self.app, repository )
        repository.deleted = False
        repository.status = self.install_model.AgentShedRepository.installation_status.INSTALLED
        if repository.includes_agents_for_display_in_agent_panel:
            tpm = agent_panel_manager.AgentPanelManager( self.app )
            irmm = InstalledRepositoryMetadataManager( app=self.app,
                                                       tpm=tpm,
                                                       repository=repository,
                                                       changeset_revision=repository.changeset_revision,
                                                       metadata_dict=repository.metadata )
            repository_agents_tups = irmm.get_repository_agents_tups()
            # Reload agents into the appropriate agent panel section.
            agent_panel_dict = repository.metadata[ 'agent_panel_section' ]
            tpm.add_to_agent_panel( repository.name,
                                   repository_clone_url,
                                   repository.installed_changeset_revision,
                                   repository_agents_tups,
                                   repository.owner,
                                   shed_agent_conf,
                                   agent_panel_dict,
                                   new_install=False )
            if repository.includes_data_managers:
                tp, data_manager_relative_install_dir = repository.get_agent_relative_path( self.app )
                # Hack to add repository.name here, which is actually the root of the installed repository
                data_manager_relative_install_dir = os.path.join( data_manager_relative_install_dir, repository.name )
                dmh = data_manager.DataManagerHandler( self.app )
                dmh.install_data_managers( self.app.config.shed_data_manager_config_file,
                                           repository.metadata,
                                           repository.get_shed_config_dict( self.app ),
                                           data_manager_relative_install_dir,
                                           repository,
                                           repository_agents_tups )
        self.install_model.context.add( repository )
        self.install_model.context.flush()
        if repository.includes_datatypes:
            if agent_path:
                repository_install_dir = os.path.abspath( os.path.join( agent_path, relative_install_dir ) )
            else:
                repository_install_dir = os.path.abspath( relative_install_dir )
            # Activate proprietary datatypes.
            cdl = custom_datatype_manager.CustomDatatypeLoader( self.app )
            installed_repository_dict = cdl.load_installed_datatypes( repository,
                                                                      repository_install_dir,
                                                                      deactivate=False )
            if installed_repository_dict:
                converter_path = installed_repository_dict.get( 'converter_path' )
                if converter_path is not None:
                    cdl.load_installed_datatype_converters( installed_repository_dict, deactivate=False )
                display_path = installed_repository_dict.get( 'display_path' )
                if display_path is not None:
                    cdl.load_installed_display_applications( installed_repository_dict, deactivate=False )

    def add_entry_to_installed_repository_dependencies_of_installed_repositories( self, repository ):
        """
        Add an entry to self.installed_repository_dependencies_of_installed_repositories.  A side-effect of this method
        is the population of self.installed_dependent_repositories_of_installed_repositories.  Since this method discovers
        all repositories required by the received repository, it can use the list to add entries to the reverse dictionary.
        """
        repository_tup = self.get_repository_tuple_for_installed_repository_manager( repository )
        agent_shed, name, owner, installed_changeset_revision = repository_tup
        # Get the list of repository dependencies for this repository.
        status = self.install_model.AgentShedRepository.installation_status.INSTALLED
        repository_dependency_tups = self.get_repository_dependency_tups_for_installed_repository( repository, status=status )
        # Add an entry to self.installed_repository_dependencies_of_installed_repositories.
        if repository_tup not in self.installed_repository_dependencies_of_installed_repositories:
            debug_msg = "Adding an entry for revision %s of repository %s owned by %s " % ( installed_changeset_revision, name, owner )
            debug_msg += "to installed_repository_dependencies_of_installed_repositories."
            log.debug( debug_msg )
            self.installed_repository_dependencies_of_installed_repositories[ repository_tup ] = repository_dependency_tups
        # Use the repository_dependency_tups to add entries to the reverse dictionary
        # self.installed_dependent_repositories_of_installed_repositories.
        for required_repository_tup in repository_dependency_tups:
            debug_msg = "Appending revision %s of repository %s owned by %s " % ( installed_changeset_revision, name, owner )
            debug_msg += "to all dependent repositories in installed_dependent_repositories_of_installed_repositories."
            log.debug( debug_msg )
            if required_repository_tup in self.installed_dependent_repositories_of_installed_repositories:
                self.installed_dependent_repositories_of_installed_repositories[ required_repository_tup ].append( repository_tup )
            else:
                self.installed_dependent_repositories_of_installed_repositories[ required_repository_tup ] = [ repository_tup ]

    def add_entry_to_installed_runtime_dependent_agent_dependencies_of_installed_agent_dependencies( self, agent_dependency ):
        """Add an entry to self.installed_runtime_dependent_agent_dependencies_of_installed_agent_dependencies."""
        agent_dependency_tup = self.get_agent_dependency_tuple_for_installed_repository_manager( agent_dependency )
        if agent_dependency_tup not in self.installed_runtime_dependent_agent_dependencies_of_installed_agent_dependencies:
            agent_shed_repository_id, name, version, type = agent_dependency_tup
            debug_msg = "Adding an entry for version %s of %s %s " % ( version, type, name )
            debug_msg += "to installed_runtime_dependent_agent_dependencies_of_installed_agent_dependencies."
            log.debug( debug_msg )
            status = self.install_model.AgentDependency.installation_status.INSTALLED
            installed_runtime_dependent_agent_dependency_tups = self.get_runtime_dependent_agent_dependency_tuples( agent_dependency,
                                                                                                                  status=status )
            self.installed_runtime_dependent_agent_dependencies_of_installed_agent_dependencies[ agent_dependency_tup ] = \
                installed_runtime_dependent_agent_dependency_tups

    def add_entry_to_installed_agent_dependencies_of_installed_repositories( self, repository ):
        """Add an entry to self.installed_agent_dependencies_of_installed_repositories."""
        repository_tup = self.get_repository_tuple_for_installed_repository_manager( repository )
        if repository_tup not in self.installed_agent_dependencies_of_installed_repositories:
            agent_shed, name, owner, installed_changeset_revision = repository_tup
            debug_msg = "Adding an entry for revision %s of repository %s owned by %s " % ( installed_changeset_revision, name, owner )
            debug_msg += "to installed_agent_dependencies_of_installed_repositories."
            log.debug( debug_msg )
            installed_agent_dependency_tups = []
            for agent_dependency in repository.agent_dependencies:
                if agent_dependency.status == self.app.install_model.AgentDependency.installation_status.INSTALLED:
                    agent_dependency_tup = self.get_agent_dependency_tuple_for_installed_repository_manager( agent_dependency )
                    installed_agent_dependency_tups.append( agent_dependency_tup )
            self.installed_agent_dependencies_of_installed_repositories[ repository_tup ] = installed_agent_dependency_tups

    def add_entry_to_repository_dependencies_of_installed_repositories( self, repository ):
        """Add an entry to self.repository_dependencies_of_installed_repositories."""
        repository_tup = self.get_repository_tuple_for_installed_repository_manager( repository )
        if repository_tup not in self.repository_dependencies_of_installed_repositories:
            agent_shed, name, owner, installed_changeset_revision = repository_tup
            debug_msg = "Adding an entry for revision %s of repository %s owned by %s " % ( installed_changeset_revision, name, owner )
            debug_msg += "to repository_dependencies_of_installed_repositories."
            log.debug( debug_msg )
            repository_dependency_tups = self.get_repository_dependency_tups_for_installed_repository( repository, status=None )
            self.repository_dependencies_of_installed_repositories[ repository_tup ] = repository_dependency_tups

    def add_entry_to_runtime_agent_dependencies_of_installed_agent_dependencies( self, agent_dependency ):
        """Add an entry to self.runtime_agent_dependencies_of_installed_agent_dependencies."""
        agent_dependency_tup = self.get_agent_dependency_tuple_for_installed_repository_manager( agent_dependency )
        if agent_dependency_tup not in self.runtime_agent_dependencies_of_installed_agent_dependencies:
            agent_shed_repository_id, name, version, type = agent_dependency_tup
            debug_msg = "Adding an entry for version %s of %s %s " % ( version, type, name )
            debug_msg += "to runtime_agent_dependencies_of_installed_agent_dependencies."
            log.debug( debug_msg )
            runtime_dependent_agent_dependency_tups = self.get_runtime_dependent_agent_dependency_tuples( agent_dependency,
                                                                                                        status=None )
            self.runtime_agent_dependencies_of_installed_agent_dependencies[ agent_dependency_tup ] = \
                runtime_dependent_agent_dependency_tups

    def add_entry_to_agent_dependencies_of_installed_repositories( self, repository ):
        """Add an entry to self.agent_dependencies_of_installed_repositories."""
        repository_tup = self.get_repository_tuple_for_installed_repository_manager( repository )
        if repository_tup not in self.agent_dependencies_of_installed_repositories:
            agent_shed, name, owner, installed_changeset_revision = repository_tup
            debug_msg = "Adding an entry for revision %s of repository %s owned by %s " % ( installed_changeset_revision, name, owner )
            debug_msg += "to agent_dependencies_of_installed_repositories."
            log.debug( debug_msg )
            agent_dependency_tups = []
            for agent_dependency in repository.agent_dependencies:
                agent_dependency_tup = self.get_agent_dependency_tuple_for_installed_repository_manager( agent_dependency )
                agent_dependency_tups.append( agent_dependency_tup )
            self.agent_dependencies_of_installed_repositories[ repository_tup ] = agent_dependency_tups

    def get_containing_repository_for_agent_dependency( self, agent_dependency_tup ):
        agent_shed_repository_id, name, version, type = agent_dependency_tup
        return self.app.install_model.context.query( self.app.install_model.AgentShedRepository ).get( agent_shed_repository_id )

    def get_dependencies_for_repository( self, agent_shed_url, repo_info_dict, includes_agent_dependencies, updating=False ):
        """
        Return dictionaries containing the sets of installed and missing agent dependencies and repository
        dependencies associated with the repository defined by the received repo_info_dict.
        """
        rdim = repository_dependency_manager.RepositoryDependencyInstallManager( self.app )
        repository = None
        installed_rd = {}
        installed_td = {}
        missing_rd = {}
        missing_td = {}
        name = repo_info_dict.keys()[ 0 ]
        repo_info_tuple = repo_info_dict[ name ]
        description, repository_clone_url, changeset_revision, ctx_rev, repository_owner, repository_dependencies, agent_dependencies = \
            suc.get_repo_info_tuple_contents( repo_info_tuple )
        if agent_dependencies:
            if not includes_agent_dependencies:
                includes_agent_dependencies = True
            # Inspect the agent_dependencies dictionary to separate the installed and missing agent dependencies.
            # We don't add to installed_td and missing_td here because at this point they are empty.
            installed_td, missing_td = self.get_installed_and_missing_agent_dependencies_for_repository( agent_dependencies )
        # In cases where a repository dependency is required only for compiling a dependent repository's
        # agent dependency, the value of repository_dependencies will be an empty dictionary here.
        if repository_dependencies:
            # We have a repository with one or more defined repository dependencies.
            if not repository:
                repository = suc.get_repository_for_dependency_relationship( self.app,
                                                                             agent_shed_url,
                                                                             name,
                                                                             repository_owner,
                                                                             changeset_revision )
            if not updating and repository and repository.metadata:
                installed_rd, missing_rd = self.get_installed_and_missing_repository_dependencies( repository )
            else:
                installed_rd, missing_rd = \
                    self.get_installed_and_missing_repository_dependencies_for_new_or_updated_install( repo_info_tuple )
            # Discover all repository dependencies and retrieve information for installing them.
            all_repo_info_dict = rdim.get_required_repo_info_dicts( agent_shed_url, util.listify( repo_info_dict ) )
            has_repository_dependencies = all_repo_info_dict.get( 'has_repository_dependencies', False )
            has_repository_dependencies_only_if_compiling_contained_td = \
                all_repo_info_dict.get( 'has_repository_dependencies_only_if_compiling_contained_td', False )
            includes_agents_for_display_in_agent_panel = all_repo_info_dict.get( 'includes_agents_for_display_in_agent_panel', False )
            includes_agent_dependencies = all_repo_info_dict.get( 'includes_agent_dependencies', False )
            includes_agents = all_repo_info_dict.get( 'includes_agents', False )
            required_repo_info_dicts = all_repo_info_dict.get( 'all_repo_info_dicts', [] )
            # Display agent dependencies defined for each of the repository dependencies.
            if required_repo_info_dicts:
                required_agent_dependencies = {}
                for rid in required_repo_info_dicts:
                    for name, repo_info_tuple in rid.items():
                        description, repository_clone_url, changeset_revision, ctx_rev, \
                            repository_owner, rid_repository_dependencies, rid_agent_dependencies = \
                            suc.get_repo_info_tuple_contents( repo_info_tuple )
                        if rid_agent_dependencies:
                            for td_key, td_dict in rid_agent_dependencies.items():
                                if td_key not in required_agent_dependencies:
                                    required_agent_dependencies[ td_key ] = td_dict
                if required_agent_dependencies:
                    # Discover and categorize all agent dependencies defined for this repository's repository dependencies.
                    required_installed_td, required_missing_td = \
                        self.get_installed_and_missing_agent_dependencies_for_repository( required_agent_dependencies )
                    if required_installed_td:
                        if not includes_agent_dependencies:
                            includes_agent_dependencies = True
                        for td_key, td_dict in required_installed_td.items():
                            if td_key not in installed_td:
                                installed_td[ td_key ] = td_dict
                    if required_missing_td:
                        if not includes_agent_dependencies:
                            includes_agent_dependencies = True
                        for td_key, td_dict in required_missing_td.items():
                            if td_key not in missing_td:
                                missing_td[ td_key ] = td_dict
        else:
            # We have a single repository with (possibly) no defined repository dependencies.
            all_repo_info_dict = rdim.get_required_repo_info_dicts( agent_shed_url, util.listify( repo_info_dict ) )
            has_repository_dependencies = all_repo_info_dict.get( 'has_repository_dependencies', False )
            has_repository_dependencies_only_if_compiling_contained_td = \
                all_repo_info_dict.get( 'has_repository_dependencies_only_if_compiling_contained_td', False )
            includes_agents_for_display_in_agent_panel = all_repo_info_dict.get( 'includes_agents_for_display_in_agent_panel', False )
            includes_agent_dependencies = all_repo_info_dict.get( 'includes_agent_dependencies', False )
            includes_agents = all_repo_info_dict.get( 'includes_agents', False )
            required_repo_info_dicts = all_repo_info_dict.get( 'all_repo_info_dicts', [] )
        dependencies_for_repository_dict = \
            dict( changeset_revision=changeset_revision,
                  has_repository_dependencies=has_repository_dependencies,
                  has_repository_dependencies_only_if_compiling_contained_td=has_repository_dependencies_only_if_compiling_contained_td,
                  includes_agent_dependencies=includes_agent_dependencies,
                  includes_agents=includes_agents,
                  includes_agents_for_display_in_agent_panel=includes_agents_for_display_in_agent_panel,
                  installed_repository_dependencies=installed_rd,
                  installed_agent_dependencies=installed_td,
                  missing_repository_dependencies=missing_rd,
                  missing_agent_dependencies=missing_td,
                  name=name,
                  repository_owner=repository_owner )
        return dependencies_for_repository_dict

    def get_installed_and_missing_repository_dependencies( self, repository ):
        """
        Return the installed and missing repository dependencies for a agent shed repository that has a record
        in the Galaxy database, but may or may not be installed.  In this case, the repository dependencies are
        associated with the repository in the database.  Do not include a repository dependency if it is required
        only to compile a agent dependency defined for the dependent repository since these special kinds of repository
        dependencies are really a dependency of the dependent repository's contained agent dependency, and only
        if that agent dependency requires compilation.
        """
        missing_repository_dependencies = {}
        installed_repository_dependencies = {}
        has_repository_dependencies = repository.has_repository_dependencies
        if has_repository_dependencies:
            # The repository dependencies container will include only the immediate repository
            # dependencies of this repository, so the container will be only a single level in depth.
            metadata = repository.metadata
            installed_rd_tups = []
            missing_rd_tups = []
            for tsr in repository.repository_dependencies:
                prior_installation_required = self.set_prior_installation_required( repository, tsr )
                only_if_compiling_contained_td = self.set_only_if_compiling_contained_td( repository, tsr )
                rd_tup = [ tsr.agent_shed,
                           tsr.name,
                           tsr.owner,
                           tsr.changeset_revision,
                           prior_installation_required,
                           only_if_compiling_contained_td,
                           tsr.id,
                           tsr.status ]
                if tsr.status == self.app.install_model.AgentShedRepository.installation_status.INSTALLED:
                    installed_rd_tups.append( rd_tup )
                else:
                    # We'll only add the rd_tup to the missing_rd_tups list if the received repository
                    # has agent dependencies that are not correctly installed.  This may prove to be a
                    # weak check since the repository in question may not have anything to do with
                    # compiling the missing agent dependencies.  If we discover that this is a problem,
                    # more granular checking will be necessary here.
                    if repository.missing_agent_dependencies:
                        if not self.repository_dependency_needed_only_for_compiling_agent_dependency( repository, tsr ):
                            missing_rd_tups.append( rd_tup )
                    else:
                        missing_rd_tups.append( rd_tup )
            if installed_rd_tups or missing_rd_tups:
                # Get the description from the metadata in case it has a value.
                repository_dependencies = metadata.get( 'repository_dependencies', {} )
                description = repository_dependencies.get( 'description', None )
                # We need to add a root_key entry to one or both of installed_repository_dependencies dictionary and the
                # missing_repository_dependencies dictionaries for proper display parsing.
                root_key = container_util.generate_repository_dependencies_key_for_repository( repository.agent_shed,
                                                                                               repository.name,
                                                                                               repository.owner,
                                                                                               repository.installed_changeset_revision,
                                                                                               prior_installation_required,
                                                                                               only_if_compiling_contained_td )
                if installed_rd_tups:
                    installed_repository_dependencies[ 'root_key' ] = root_key
                    installed_repository_dependencies[ root_key ] = installed_rd_tups
                    installed_repository_dependencies[ 'description' ] = description
                if missing_rd_tups:
                    missing_repository_dependencies[ 'root_key' ] = root_key
                    missing_repository_dependencies[ root_key ] = missing_rd_tups
                    missing_repository_dependencies[ 'description' ] = description
        return installed_repository_dependencies, missing_repository_dependencies

    def get_installed_and_missing_repository_dependencies_for_new_or_updated_install( self, repo_info_tuple ):
        """
        Parse the received repository_dependencies dictionary that is associated with a repository being
        installed into Galaxy for the first time and attempt to determine repository dependencies that are
        already installed and those that are not.
        """
        missing_repository_dependencies = {}
        installed_repository_dependencies = {}
        missing_rd_tups = []
        installed_rd_tups = []
        ( description, repository_clone_url, changeset_revision, ctx_rev,
          repository_owner, repository_dependencies, agent_dependencies ) = suc.get_repo_info_tuple_contents( repo_info_tuple )
        if repository_dependencies:
            description = repository_dependencies[ 'description' ]
            root_key = repository_dependencies[ 'root_key' ]
            # The repository dependencies container will include only the immediate repository dependencies of
            # this repository, so the container will be only a single level in depth.
            for key, rd_tups in repository_dependencies.items():
                if key in [ 'description', 'root_key' ]:
                    continue
                for rd_tup in rd_tups:
                    agent_shed, name, owner, changeset_revision, prior_installation_required, only_if_compiling_contained_td = \
                        common_util.parse_repository_dependency_tuple( rd_tup )
                    # Updates to installed repository revisions may have occurred, so make sure to locate the
                    # appropriate repository revision if one exists.  We need to create a temporary repo_info_tuple
                    # that includes the correct repository owner which we get from the current rd_tup.  The current
                    # tuple looks like: ( description, repository_clone_url, changeset_revision, ctx_rev, repository_owner,
                    #                     repository_dependencies, installed_td )
                    tmp_clone_url = common_util.generate_clone_url_from_repo_info_tup( self.app, rd_tup )
                    tmp_repo_info_tuple = ( None, tmp_clone_url, changeset_revision, None, owner, None, None )
                    repository, installed_changeset_revision = suc.repository_was_previously_installed( self.app,
                                                                                                        agent_shed,
                                                                                                        name,
                                                                                                        tmp_repo_info_tuple,
                                                                                                        from_tip=False )
                    if repository:
                        new_rd_tup = [ agent_shed,
                                       name,
                                       owner,
                                       changeset_revision,
                                       prior_installation_required,
                                       only_if_compiling_contained_td,
                                       repository.id,
                                       repository.status ]
                        if repository.status == self.install_model.AgentShedRepository.installation_status.INSTALLED:
                            if new_rd_tup not in installed_rd_tups:
                                installed_rd_tups.append( new_rd_tup )
                        else:
                            # A repository dependency that is not installed will not be considered missing if its value
                            # for only_if_compiling_contained_td is True  This is because this type of repository dependency
                            # will only be considered at the time that the specified agent dependency is being installed, and
                            # even then only if the compiled binary of the agent dependency could not be installed due to the
                            # unsupported installation environment.
                            if not util.asbool( only_if_compiling_contained_td ):
                                if new_rd_tup not in missing_rd_tups:
                                    missing_rd_tups.append( new_rd_tup )
                    else:
                        new_rd_tup = [ agent_shed,
                                       name,
                                       owner,
                                       changeset_revision,
                                       prior_installation_required,
                                       only_if_compiling_contained_td,
                                       None,
                                       'Never installed' ]
                        if not util.asbool( only_if_compiling_contained_td ):
                            # A repository dependency that is not installed will not be considered missing if its value for
                            # only_if_compiling_contained_td is True - see above...
                            if new_rd_tup not in missing_rd_tups:
                                missing_rd_tups.append( new_rd_tup )
        if installed_rd_tups:
            installed_repository_dependencies[ 'root_key' ] = root_key
            installed_repository_dependencies[ root_key ] = installed_rd_tups
            installed_repository_dependencies[ 'description' ] = description
        if missing_rd_tups:
            missing_repository_dependencies[ 'root_key' ] = root_key
            missing_repository_dependencies[ root_key ] = missing_rd_tups
            missing_repository_dependencies[ 'description' ] = description
        return installed_repository_dependencies, missing_repository_dependencies

    def get_installed_and_missing_agent_dependencies_for_repository( self, agent_dependencies_dict ):
        """
        Return the lists of installed agent dependencies and missing agent dependencies for a set of repositories
        being installed into Galaxy.
        """
        # FIXME: This implementation breaks when updates to a repository contain dependencies that result in
        # multiple entries for a specific agent dependency.  A scenario where this can happen is where 2 repositories
        # define  the same dependency internally (not using the complex repository dependency definition to a separate
        # package repository approach).  If 2 repositories contain the same agent_dependencies.xml file, one dependency
        # will be lost since the values in these returned dictionaries are not lists.  All agent dependency dictionaries
        # should have lists as values.  These scenarios are probably extreme corner cases, but still should be handled.
        installed_agent_dependencies = {}
        missing_agent_dependencies = {}
        if agent_dependencies_dict:
            # Make sure not to change anything in the received agent_dependencies_dict as that would be a bad side-effect!
            tmp_agent_dependencies_dict = copy.deepcopy( agent_dependencies_dict )
            for td_key, val in tmp_agent_dependencies_dict.items():
                # Default the status to NEVER_INSTALLED.
                agent_dependency_status = self.install_model.AgentDependency.installation_status.NEVER_INSTALLED
                # Set environment agent dependencies are a list.
                if td_key == 'set_environment':
                    new_val = []
                    for requirement_dict in val:
                        # {'repository_name': 'xx',
                        #  'name': 'bwa',
                        #  'version': '0.5.9',
                        #  'repository_owner': 'yy',
                        #  'changeset_revision': 'zz',
                        #  'type': 'package'}
                        agent_dependency = \
                            agent_dependency_util.get_agent_dependency_by_name_version_type( self.app,
                                                                                           requirement_dict.get( 'name', None ),
                                                                                           requirement_dict.get( 'version', None ),
                                                                                           requirement_dict.get( 'type', 'package' ) )
                        if agent_dependency:
                            agent_dependency_status = agent_dependency.status
                        requirement_dict[ 'status' ] = agent_dependency_status
                        new_val.append( requirement_dict )
                        if agent_dependency_status in [ self.install_model.AgentDependency.installation_status.INSTALLED ]:
                            if td_key in installed_agent_dependencies:
                                installed_agent_dependencies[ td_key ].extend( new_val )
                            else:
                                installed_agent_dependencies[ td_key ] = new_val
                        else:
                            if td_key in missing_agent_dependencies:
                                missing_agent_dependencies[ td_key ].extend( new_val )
                            else:
                                missing_agent_dependencies[ td_key ] = new_val
                else:
                    # The val dictionary looks something like this:
                    # {'repository_name': 'xx',
                    #  'name': 'bwa',
                    #  'version': '0.5.9',
                    #  'repository_owner': 'yy',
                    #  'changeset_revision': 'zz',
                    #  'type': 'package'}
                    agent_dependency = agent_dependency_util.get_agent_dependency_by_name_version_type( self.app,
                                                                                                     val.get( 'name', None ),
                                                                                                     val.get( 'version', None ),
                                                                                                     val.get( 'type', 'package' ) )
                    if agent_dependency:
                        agent_dependency_status = agent_dependency.status
                    val[ 'status' ] = agent_dependency_status
                if agent_dependency_status in [ self.install_model.AgentDependency.installation_status.INSTALLED ]:
                    installed_agent_dependencies[ td_key ] = val
                else:
                    missing_agent_dependencies[ td_key ] = val
        return installed_agent_dependencies, missing_agent_dependencies

    def get_repository_dependency_tups_for_installed_repository( self, repository, dependency_tups=None, status=None ):
        """
        Return a list of of tuples defining agent_shed_repository objects (whose status can be anything) required by the
        received repository.  The returned list defines the entire repository dependency tree.  This method is called
        only from Galaxy.
        """
        if dependency_tups is None:
            dependency_tups = []
        repository_tup = self.get_repository_tuple_for_installed_repository_manager( repository )
        for rrda in repository.required_repositories:
            repository_dependency = rrda.repository_dependency
            required_repository = repository_dependency.repository
            if status is None or required_repository.status == status:
                required_repository_tup = self.get_repository_tuple_for_installed_repository_manager( required_repository )
                if required_repository_tup == repository_tup:
                    # We have a circular repository dependency relationship, skip this entry.
                    continue
                if required_repository_tup not in dependency_tups:
                    dependency_tups.append( required_repository_tup )
                    return self.get_repository_dependency_tups_for_installed_repository( required_repository,
                                                                                         dependency_tups=dependency_tups )
        return dependency_tups

    def get_repository_tuple_for_installed_repository_manager( self, repository ):
        return ( str( repository.agent_shed ),
                 str( repository.name ),
                 str( repository.owner ),
                 str( repository.installed_changeset_revision ) )

    def get_repository_install_dir( self, agent_shed_repository ):
        for agent_config in self.agent_configs:
            tree, error_message = xml_util.parse_xml( agent_config )
            if tree is None:
                return None
            root = tree.getroot()
            agent_path = root.get( 'agent_path', None )
            if agent_path:
                ts = common_util.remove_port_from_agent_shed_url( str( agent_shed_repository.agent_shed ) )
                relative_path = os.path.join( agent_path,
                                              ts,
                                              'repos',
                                              str( agent_shed_repository.owner ),
                                              str( agent_shed_repository.name ),
                                              str( agent_shed_repository.installed_changeset_revision ) )
                if os.path.exists( relative_path ):
                    return relative_path
        return None

    def get_runtime_dependent_agent_dependency_tuples( self, agent_dependency, status=None ):
        """
        Return the list of agent dependency objects that require the received agent dependency at run time.  The returned
        list will be filtered by the received status if it is not None.  This method is called only from Galaxy.
        """
        runtime_dependent_agent_dependency_tups = []
        required_env_shell_file_path = agent_dependency.get_env_shell_file_path( self.app )
        if required_env_shell_file_path:
            required_env_shell_file_path = os.path.abspath( required_env_shell_file_path )
        if required_env_shell_file_path is not None:
            for td in self.app.install_model.context.query( self.app.install_model.AgentDependency ):
                if status is None or td.status == status:
                    env_shell_file_path = td.get_env_shell_file_path( self.app )
                    if env_shell_file_path is not None:
                        try:
                            contents = open( env_shell_file_path, 'r' ).read()
                        except Exception, e:
                            contents = None
                            log.debug( 'Error reading file %s, so cannot determine if package %s requires package %s at run time: %s' %
                                       ( str( env_shell_file_path ), str( td.name ), str( agent_dependency.name ), str( e ) ) )
                        if contents is not None and contents.find( required_env_shell_file_path ) >= 0:
                            td_tuple = self.get_agent_dependency_tuple_for_installed_repository_manager( td )
                            runtime_dependent_agent_dependency_tups.append( td_tuple )
        return runtime_dependent_agent_dependency_tups

    def get_agent_dependency_tuple_for_installed_repository_manager( self, agent_dependency ):
        if agent_dependency.type is None:
            type = None
        else:
            type = str( agent_dependency.type )
        return ( agent_dependency.agent_shed_repository_id, str( agent_dependency.name ), str( agent_dependency.version ), type )

    def handle_existing_agent_dependencies_that_changed_in_update( self, repository, original_dependency_dict,
                                                                  new_dependency_dict ):
        """
        This method is called when a Galaxy admin is getting updates for an installed agent shed
        repository in order to cover the case where an existing agent dependency was changed (e.g.,
        the version of the dependency was changed) but the agent version for which it is a dependency
        was not changed.  In this case, we only want to determine if any of the dependency information
        defined in original_dependency_dict was changed in new_dependency_dict.  We don't care if new
        dependencies were added in new_dependency_dict since they will just be treated as missing
        dependencies for the agent.
        """
        updated_agent_dependency_names = []
        deleted_agent_dependency_names = []
        for original_dependency_key, original_dependency_val_dict in original_dependency_dict.items():
            if original_dependency_key not in new_dependency_dict:
                updated_agent_dependency = self.update_existing_agent_dependency( repository,
                                                                                original_dependency_val_dict,
                                                                                new_dependency_dict )
                if updated_agent_dependency:
                    updated_agent_dependency_names.append( updated_agent_dependency.name )
                else:
                    deleted_agent_dependency_names.append( original_dependency_val_dict[ 'name' ] )
        return updated_agent_dependency_names, deleted_agent_dependency_names

    def handle_repository_install( self, repository ):
        """Load the dependency relationships for a repository that was just installed or reinstalled."""
        # Populate self.repository_dependencies_of_installed_repositories.
        self.add_entry_to_repository_dependencies_of_installed_repositories( repository )
        # Populate self.installed_repository_dependencies_of_installed_repositories.
        self.add_entry_to_installed_repository_dependencies_of_installed_repositories( repository )
        # Populate self.agent_dependencies_of_installed_repositories.
        self.add_entry_to_agent_dependencies_of_installed_repositories( repository )
        # Populate self.installed_agent_dependencies_of_installed_repositories.
        self.add_entry_to_installed_agent_dependencies_of_installed_repositories( repository )
        for agent_dependency in repository.agent_dependencies:
            # Populate self.runtime_agent_dependencies_of_installed_agent_dependencies.
            self.add_entry_to_runtime_agent_dependencies_of_installed_agent_dependencies( agent_dependency )
            # Populate self.installed_runtime_dependent_agent_dependencies_of_installed_agent_dependencies.
            self.add_entry_to_installed_runtime_dependent_agent_dependencies_of_installed_agent_dependencies( agent_dependency )

    def handle_repository_uninstall( self, repository ):
        """Remove the dependency relationships for a repository that was just uninstalled."""
        for agent_dependency in repository.agent_dependencies:
            agent_dependency_tup = self.get_agent_dependency_tuple_for_installed_repository_manager( agent_dependency )
            # Remove this agent_dependency from all values in
            # self.installed_runtime_dependent_agent_dependencies_of_installed_agent_dependencies
            altered_installed_runtime_dependent_agent_dependencies_of_installed_agent_dependencies = {}
            for ( td_tup, installed_runtime_dependent_agent_dependency_tups ) in self.installed_runtime_dependent_agent_dependencies_of_installed_agent_dependencies.items():
                if agent_dependency_tup in installed_runtime_dependent_agent_dependency_tups:
                    # Remove the agent_dependency from the list.
                    installed_runtime_dependent_agent_dependency_tups.remove( agent_dependency_tup )
                # Add the possibly altered list to the altered dictionary.
                altered_installed_runtime_dependent_agent_dependencies_of_installed_agent_dependencies[ td_tup ] = \
                    installed_runtime_dependent_agent_dependency_tups
            self.installed_runtime_dependent_agent_dependencies_of_installed_agent_dependencies = \
                altered_installed_runtime_dependent_agent_dependencies_of_installed_agent_dependencies
            # Remove the entry for this agent_dependency from self.runtime_agent_dependencies_of_installed_agent_dependencies.
            self.remove_entry_from_runtime_agent_dependencies_of_installed_agent_dependencies( agent_dependency )
            # Remove the entry for this agent_dependency from
            # self.installed_runtime_dependent_agent_dependencies_of_installed_agent_dependencies.
            self.remove_entry_from_installed_runtime_dependent_agent_dependencies_of_installed_agent_dependencies( agent_dependency )
        # Remove this repository's entry from self.installed_agent_dependencies_of_installed_repositories.
        self.remove_entry_from_installed_agent_dependencies_of_installed_repositories( repository )
        # Remove this repository's entry from self.agent_dependencies_of_installed_repositories
        self.remove_entry_from_agent_dependencies_of_installed_repositories( repository )
        # Remove this repository's entry from self.installed_repository_dependencies_of_installed_repositories.
        self.remove_entry_from_installed_repository_dependencies_of_installed_repositories( repository )
        # Remove this repository's entry from self.repository_dependencies_of_installed_repositories.
        self.remove_entry_from_repository_dependencies_of_installed_repositories( repository )

    def handle_agent_dependency_install( self, repository, agent_dependency ):
        """Load the dependency relationships for a agent dependency that was just installed independently of its containing repository."""
        # The received repository must have a status of 'Installed'.  The value of agent_dependency.status will either be
        # 'Installed' or 'Error', but we only need to change the in-memory dictionaries if it is 'Installed'.
        if agent_dependency.is_installed:
            # Populate self.installed_runtime_dependent_agent_dependencies_of_installed_agent_dependencies.
            self.add_entry_to_installed_runtime_dependent_agent_dependencies_of_installed_agent_dependencies( agent_dependency )
            # Populate self.installed_agent_dependencies_of_installed_repositories.
            repository_tup = self.get_repository_tuple_for_installed_repository_manager( repository )
            agent_dependency_tup = self.get_agent_dependency_tuple_for_installed_repository_manager( agent_dependency )
            if repository_tup in self.installed_agent_dependencies_of_installed_repositories:
                self.installed_agent_dependencies_of_installed_repositories[ repository_tup ].append( agent_dependency_tup )
            else:
                self.installed_agent_dependencies_of_installed_repositories[ repository_tup ] = [ agent_dependency_tup ]

    def load_dependency_relationships( self ):
        """Load relationships for all installed repositories and agent dependencies into in-memnory dictionaries."""
        # Get the list of installed agent shed repositories.
        for repository in self.context.query( self.app.install_model.AgentShedRepository ) \
                                      .filter( self.app.install_model.AgentShedRepository.table.c.status ==
                                               self.app.install_model.AgentShedRepository.installation_status.INSTALLED ):
            # Populate self.repository_dependencies_of_installed_repositories.
            self.add_entry_to_repository_dependencies_of_installed_repositories( repository )
            # Populate self.installed_repository_dependencies_of_installed_repositories.
            self.add_entry_to_installed_repository_dependencies_of_installed_repositories( repository )
            # Populate self.agent_dependencies_of_installed_repositories.
            self.add_entry_to_agent_dependencies_of_installed_repositories( repository )
            # Populate self.installed_agent_dependencies_of_installed_repositories.
            self.add_entry_to_installed_agent_dependencies_of_installed_repositories( repository )
        # Get the list of installed agent dependencies.
        for agent_dependency in self.context.query( self.app.install_model.AgentDependency ) \
                                           .filter( self.app.install_model.AgentDependency.table.c.status ==
                                                    self.app.install_model.AgentDependency.installation_status.INSTALLED ):
            # Populate self.runtime_agent_dependencies_of_installed_agent_dependencies.
            self.add_entry_to_runtime_agent_dependencies_of_installed_agent_dependencies( agent_dependency )
            # Populate self.installed_runtime_dependent_agent_dependencies_of_installed_agent_dependencies.
            self.add_entry_to_installed_runtime_dependent_agent_dependencies_of_installed_agent_dependencies( agent_dependency )

    def load_proprietary_datatypes( self ):
        cdl = custom_datatype_manager.CustomDatatypeLoader( self.app )
        for agent_shed_repository in self.context.query( self.install_model.AgentShedRepository ) \
                                                .filter( and_( self.install_model.AgentShedRepository.table.c.includes_datatypes == true(),
                                                               self.install_model.AgentShedRepository.table.c.deleted == false() ) ) \
                                                .order_by( self.install_model.AgentShedRepository.table.c.id ):
            relative_install_dir = self.get_repository_install_dir( agent_shed_repository )
            if relative_install_dir:
                installed_repository_dict = cdl.load_installed_datatypes( agent_shed_repository, relative_install_dir )
                if installed_repository_dict:
                    self.installed_repository_dicts.append( installed_repository_dict )

    def load_proprietary_converters_and_display_applications( self, deactivate=False ):
        cdl = custom_datatype_manager.CustomDatatypeLoader( self.app )
        for installed_repository_dict in self.installed_repository_dicts:
            if installed_repository_dict[ 'converter_path' ]:
                cdl.load_installed_datatype_converters( installed_repository_dict, deactivate=deactivate )
            if installed_repository_dict[ 'display_path' ]:
                cdl.load_installed_display_applications( installed_repository_dict, deactivate=deactivate )

    def purge_repository( self, repository ):
        """Purge a repository with status New (a white ghost) from the database."""
        sa_session = self.app.model.context.current
        status = 'ok'
        message = ''
        purged_agent_versions = 0
        purged_agent_dependencies = 0
        purged_required_repositories = 0
        purged_orphan_repository_repository_dependency_association_records = 0
        purged_orphan_repository_dependency_records = 0
        if repository.is_new:
            # Purge this repository's associated agent versions.
            if repository.agent_versions:
                for agent_version in repository.agent_versions:
                    if agent_version.parent_agent_association:
                        for agent_version_association in agent_version.parent_agent_association:
                            try:
                                sa_session.delete( agent_version_association )
                                sa_session.flush()
                            except Exception, e:
                                status = 'error'
                                message = 'Error attempting to purge agent_versions for the repository named %s with status %s: %s.' % \
                                    ( str( repository.name ), str( repository.status ), str( e ) )
                                return status, message
                    if agent_version.child_agent_association:
                        for agent_version_association in agent_version.child_agent_association:
                            try:
                                sa_session.delete( agent_version_association )
                                sa_session.flush()
                            except Exception, e:
                                status = 'error'
                                message = 'Error attempting to purge agent_versions for the repository named %s with status %s: %s.' % \
                                    ( str( repository.name ), str( repository.status ), str( e ) )
                                return status, message
                    try:
                        sa_session.delete( agent_version )
                        sa_session.flush()
                        purged_agent_versions += 1
                    except Exception, e:
                        status = 'error'
                        message = 'Error attempting to purge agent_versions for the repository named %s with status %s: %s.' % \
                            ( str( repository.name ), str( repository.status ), str( e ) )
                        return status, message
            # Purge this repository's associated agent dependencies.
            if repository.agent_dependencies:
                for agent_dependency in repository.agent_dependencies:
                    try:
                        sa_session.delete( agent_dependency )
                        sa_session.flush()
                        purged_agent_dependencies += 1
                    except Exception, e:
                        status = 'error'
                        message = 'Error attempting to purge agent_dependencies for the repository named %s with status %s: %s.' % \
                            ( str( repository.name ), str( repository.status ), str( e ) )
                        return status, message
            # Purge this repository's associated required repositories.
            if repository.required_repositories:
                for rrda in repository.required_repositories:
                    try:
                        sa_session.delete( rrda )
                        sa_session.flush()
                        purged_required_repositories += 1
                    except Exception, e:
                        status = 'error'
                        message = 'Error attempting to purge required_repositories for the repository named %s with status %s: %s.' % \
                            ( str( repository.name ), str( repository.status ), str( e ) )
                        return status, message
            # Purge any "orphan" repository_dependency records associated with the repository, but not with any
            # repository_repository_dependency_association records.
            for orphan_repository_dependency in \
                sa_session.query( self.app.install_model.RepositoryDependency ) \
                          .filter( self.app.install_model.RepositoryDependency.table.c.agent_shed_repository_id == repository.id ):
                # Purge any repository_repository_dependency_association records whose repository_dependency_id is
                # the id of the orphan repository_dependency record.
                for orphan_rrda in \
                    sa_session.query( self.app.install_model.RepositoryRepositoryDependencyAssociation ) \
                              .filter( self.app.install_model.RepositoryRepositoryDependencyAssociation.table.c.repository_dependency_id == orphan_repository_dependency.id ):
                    try:
                        sa_session.delete( orphan_rrda )
                        sa_session.flush()
                        purged_orphan_repository_repository_dependency_association_records += 1
                    except Exception, e:
                        status = 'error'
                        message = 'Error attempting to purge repository_repository_dependency_association records associated with '
                        message += 'an orphan repository_dependency record for the repository named %s with status %s: %s.' % \
                            ( str( repository.name ), str( repository.status ), str( e ) )
                        return status, message
                try:
                    sa_session.delete( orphan_repository_dependency )
                    sa_session.flush()
                    purged_orphan_repository_dependency_records += 1
                except Exception, e:
                    status = 'error'
                    message = 'Error attempting to purge orphan repository_dependency records for the repository named %s with status %s: %s.' % \
                        ( str( repository.name ), str( repository.status ), str( e ) )
                    return status, message
            # Purge the repository.
            sa_session.delete( repository )
            sa_session.flush()
            message = 'The repository named <b>%s</b> with status <b>%s</b> has been purged.<br/>' % \
                ( str( repository.name ), str( repository.status ) )
            message += 'Total associated agent_version records purged: %d<br/>' % purged_agent_versions
            message += 'Total associated agent_dependency records purged: %d<br/>' % purged_agent_dependencies
            message += 'Total associated repository_repository_dependency_association records purged: %d<br/>' % purged_required_repositories
            message += 'Total associated orphan repository_repository_dependency_association records purged: %d<br/>' % \
                purged_orphan_repository_repository_dependency_association_records
            message += 'Total associated orphan repository_dependency records purged: %d<br/>' % purged_orphan_repository_dependency_records
        else:
            status = 'error'
            message = 'A repository must have the status <b>New</b> in order to be purged.  This repository has '
            message += ' the status %s.' % str( repository.status )
        return status, message

    def remove_entry_from_installed_repository_dependencies_of_installed_repositories( self, repository ):
        """
        Remove an entry from self.installed_repository_dependencies_of_installed_repositories.  A side-effect of this method
        is removal of appropriate value items from self.installed_dependent_repositories_of_installed_repositories.
        """
        # Remove tuples defining this repository from value lists in self.installed_dependent_repositories_of_installed_repositories.
        repository_tup = self.get_repository_tuple_for_installed_repository_manager( repository )
        agent_shed, name, owner, installed_changeset_revision = repository_tup
        altered_installed_dependent_repositories_of_installed_repositories = {}
        for r_tup, v_tups in self.installed_dependent_repositories_of_installed_repositories.items():
            if repository_tup in v_tups:
                debug_msg = "Removing entry for revision %s of repository %s owned by %s " % \
                    ( installed_changeset_revision, name, owner )
                r_agent_shed, r_name, r_owner, r_installed_changeset_revision = r_tup
                debug_msg += "from the dependent list for revision %s of repository %s owned by %s " % \
                    ( r_installed_changeset_revision, r_name, r_owner )
                debug_msg += "in installed_repository_dependencies_of_installed_repositories."
                log.debug( debug_msg )
                v_tups.remove( repository_tup )
            altered_installed_dependent_repositories_of_installed_repositories[ r_tup ] = v_tups
        self.installed_dependent_repositories_of_installed_repositories = \
            altered_installed_dependent_repositories_of_installed_repositories
        # Remove this repository's entry from self.installed_repository_dependencies_of_installed_repositories.
        if repository_tup in self.installed_repository_dependencies_of_installed_repositories:
            debug_msg = "Removing entry for revision %s of repository %s owned by %s " % ( installed_changeset_revision, name, owner )
            debug_msg += "from installed_repository_dependencies_of_installed_repositories."
            log.debug( debug_msg )
            del self.installed_repository_dependencies_of_installed_repositories[ repository_tup ]

    def remove_entry_from_installed_runtime_dependent_agent_dependencies_of_installed_agent_dependencies( self, agent_dependency ):
        """Remove an entry from self.installed_runtime_dependent_agent_dependencies_of_installed_agent_dependencies."""
        agent_dependency_tup = self.get_agent_dependency_tuple_for_installed_repository_manager( agent_dependency )
        if agent_dependency_tup in self.installed_runtime_dependent_agent_dependencies_of_installed_agent_dependencies:
            agent_shed_repository_id, name, version, type = agent_dependency_tup
            debug_msg = "Removing entry for version %s of %s %s " % ( version, type, name )
            debug_msg += "from installed_runtime_dependent_agent_dependencies_of_installed_agent_dependencies."
            log.debug( debug_msg )
            del self.installed_runtime_dependent_agent_dependencies_of_installed_agent_dependencies[ agent_dependency_tup ]

    def remove_entry_from_installed_agent_dependencies_of_installed_repositories( self, repository ):
        """Remove an entry from self.installed_agent_dependencies_of_installed_repositories."""
        repository_tup = self.get_repository_tuple_for_installed_repository_manager( repository )
        if repository_tup in self.installed_agent_dependencies_of_installed_repositories:
            agent_shed, name, owner, installed_changeset_revision = repository_tup
            debug_msg = "Removing entry for revision %s of repository %s owned by %s " % ( installed_changeset_revision, name, owner )
            debug_msg += "from installed_agent_dependencies_of_installed_repositories."
            log.debug( debug_msg )
            del self.installed_agent_dependencies_of_installed_repositories[ repository_tup ]

    def remove_entry_from_repository_dependencies_of_installed_repositories( self, repository ):
        """Remove an entry from self.repository_dependencies_of_installed_repositories."""
        repository_tup = self.get_repository_tuple_for_installed_repository_manager( repository )
        if repository_tup in self.repository_dependencies_of_installed_repositories:
            agent_shed, name, owner, installed_changeset_revision = repository_tup
            debug_msg = "Removing entry for revision %s of repository %s owned by %s " % ( installed_changeset_revision, name, owner )
            debug_msg += "from repository_dependencies_of_installed_repositories."
            log.debug( debug_msg )
            del self.repository_dependencies_of_installed_repositories[ repository_tup ]

    def remove_entry_from_runtime_agent_dependencies_of_installed_agent_dependencies( self, agent_dependency ):
        """Remove an entry from self.runtime_agent_dependencies_of_installed_agent_dependencies."""
        agent_dependency_tup = self.get_agent_dependency_tuple_for_installed_repository_manager( agent_dependency )
        if agent_dependency_tup in self.runtime_agent_dependencies_of_installed_agent_dependencies:
            agent_shed_repository_id, name, version, type = agent_dependency_tup
            debug_msg = "Removing entry for version %s of %s %s from runtime_agent_dependencies_of_installed_agent_dependencies." % \
                ( version, type, name )
            log.debug( debug_msg )
            del self.runtime_agent_dependencies_of_installed_agent_dependencies[ agent_dependency_tup ]

    def remove_entry_from_agent_dependencies_of_installed_repositories( self, repository ):
        """Remove an entry from self.agent_dependencies_of_installed_repositories."""
        repository_tup = self.get_repository_tuple_for_installed_repository_manager( repository )
        if repository_tup in self.agent_dependencies_of_installed_repositories:
            agent_shed, name, owner, installed_changeset_revision = repository_tup
            debug_msg = "Removing entry for revision %s of repository %s owned by %s from agent_dependencies_of_installed_repositories." % \
                ( installed_changeset_revision, name, owner )
            log.debug( debug_msg )
            del self.agent_dependencies_of_installed_repositories[ repository_tup ]

    def repository_dependency_needed_only_for_compiling_agent_dependency( self, repository, repository_dependency ):
        for rd_tup in repository.tuples_of_repository_dependencies_needed_for_compiling_td:
            agent_shed, name, owner, changeset_revision, prior_installation_required, only_if_compiling_contained_td = rd_tup
            # TODO: we may discover that we need to check more than just installed_changeset_revision and changeset_revision here, in which
            # case we'll need to contact the agent shed to get the list of all possible changeset_revisions.
            cleaned_agent_shed = common_util.remove_protocol_and_port_from_agent_shed_url( agent_shed )
            cleaned_repository_dependency_agent_shed = \
                common_util.remove_protocol_and_port_from_agent_shed_url( str( repository_dependency.agent_shed ) )
            if cleaned_repository_dependency_agent_shed == cleaned_agent_shed and \
                repository_dependency.name == name and \
                repository_dependency.owner == owner and \
                ( repository_dependency.installed_changeset_revision == changeset_revision or
                  repository_dependency.changeset_revision == changeset_revision ):
                return True
        return False

    def set_only_if_compiling_contained_td( self, repository, required_repository ):
        """
        Return True if the received required_repository is only needed to compile a agent
        dependency defined for the received repository.
        """
        # This method is called only from Galaxy when rendering repository dependencies
        # for an installed agent shed repository.
        # TODO: Do we need to check more than changeset_revision here?
        required_repository_tup = [ required_repository.agent_shed,
                                    required_repository.name,
                                    required_repository.owner,
                                    required_repository.changeset_revision ]
        for tup in repository.tuples_of_repository_dependencies_needed_for_compiling_td:
            partial_tup = tup[ 0:4 ]
            if partial_tup == required_repository_tup:
                return 'True'
        return 'False'

    def set_prior_installation_required( self, repository, required_repository ):
        """
        Return True if the received required_repository must be installed before the
        received repository.
        """
        agent_shed_url = common_util.get_agent_shed_url_from_agent_shed_registry( self.app,
                                                                               str( required_repository.agent_shed ) )
        required_repository_tup = [ agent_shed_url,
                                    str( required_repository.name ),
                                    str( required_repository.owner ),
                                    str( required_repository.changeset_revision ) ]
        # Get the list of repository dependency tuples associated with the received repository
        # where prior_installation_required is True.
        required_rd_tups_that_must_be_installed = repository.requires_prior_installation_of
        for required_rd_tup in required_rd_tups_that_must_be_installed:
            # Repository dependency tuples in metadata include a prior_installation_required value,
            # so strip it for comparision.
            partial_required_rd_tup = required_rd_tup[ 0:4 ]
            if partial_required_rd_tup == required_repository_tup:
                # Return the string value of prior_installation_required, which defaults to 'False'.
                return str( required_rd_tup[ 4 ] )
        return 'False'

    def update_existing_agent_dependency( self, repository, original_dependency_dict, new_dependencies_dict ):
        """
        Update an exsiting agent dependency whose definition was updated in a change set
        pulled by a Galaxy administrator when getting updates to an installed agent shed
        repository.  The original_dependency_dict is a single agent dependency definition,
        an example of which is::

            {"name": "bwa",
             "readme": "\\nCompiling BWA requires zlib and libpthread to be present on your system.\\n        ",
             "type": "package",
             "version": "0.6.2"}

        The new_dependencies_dict is the dictionary generated by the metadata_util.generate_agent_dependency_metadata method.
        """
        new_agent_dependency = None
        original_name = original_dependency_dict[ 'name' ]
        original_type = original_dependency_dict[ 'type' ]
        original_version = original_dependency_dict[ 'version' ]
        # Locate the appropriate agent_dependency associated with the repository.
        agent_dependency = None
        for agent_dependency in repository.agent_dependencies:
            if agent_dependency.name == original_name and \
                agent_dependency.type == original_type and \
                    agent_dependency.version == original_version:
                break
        if agent_dependency and agent_dependency.can_update:
            dependency_install_dir = agent_dependency.installation_directory( self.app )
            removed_from_disk, error_message = \
                agent_dependency_util.remove_agent_dependency_installation_directory( dependency_install_dir )
            if removed_from_disk:
                context = self.app.install_model.context
                new_dependency_name = None
                new_dependency_type = None
                new_dependency_version = None
                for new_dependency_key, new_dependency_val_dict in new_dependencies_dict.items():
                    # Match on name only, hopefully this will be enough!
                    if original_name == new_dependency_val_dict[ 'name' ]:
                        new_dependency_name = new_dependency_val_dict[ 'name' ]
                        new_dependency_type = new_dependency_val_dict[ 'type' ]
                        new_dependency_version = new_dependency_val_dict[ 'version' ]
                        break
                if new_dependency_name and new_dependency_type and new_dependency_version:
                    # Update all attributes of the agent_dependency record in the database.
                    log.debug( "Updating version %s of agent dependency %s %s to have new version %s and type %s."
                               % ( str( agent_dependency.version ),
                                   str( agent_dependency.type ),
                                   str( agent_dependency.name ),
                                   str( new_dependency_version ),
                                   str( new_dependency_type ) ) )
                    agent_dependency.type = new_dependency_type
                    agent_dependency.version = new_dependency_version
                    agent_dependency.status = self.app.install_model.AgentDependency.installation_status.UNINSTALLED
                    agent_dependency.error_message = None
                    context.add( agent_dependency )
                    context.flush()
                    new_agent_dependency = agent_dependency
                else:
                    # We have no new agent dependency definition based on a matching dependency name, so remove
                    # the existing agent dependency record from the database.
                    log.debug( "Deleting version %s of agent dependency %s %s from the database since it is no longer defined."
                               % ( str( agent_dependency.version ), str( agent_dependency.type ), str( agent_dependency.name ) ) )
                    context.delete( agent_dependency )
                    context.flush()
        return new_agent_dependency
