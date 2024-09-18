import json
import logging
import os
import sys
import tempfile
import traceback

from fabric.api import lcd
from sqlalchemy import or_

from galaxy import exceptions, util
from agent_shed.util import basic_util, common_util, encoding_util, hg_util
from agent_shed.util import shed_util_common as suc, agent_dependency_util
from agent_shed.util import agent_util, xml_util

from agent_shed.galaxy_install.datatypes import custom_datatype_manager
from agent_shed.galaxy_install.metadata.installed_repository_metadata_manager import InstalledRepositoryMetadataManager
from agent_shed.galaxy_install.repository_dependencies import repository_dependency_manager
from agent_shed.galaxy_install.agent_dependencies.recipe.env_file_builder import EnvFileBuilder
from agent_shed.galaxy_install.agent_dependencies.recipe.install_environment import InstallEnvironment
from agent_shed.galaxy_install.agent_dependencies.recipe.recipe_manager import StepManager
from agent_shed.galaxy_install.agent_dependencies.recipe.recipe_manager import TagManager
from agent_shed.galaxy_install.agents import data_manager, agent_panel_manager

from agent_shed.agents import data_table_manager, agent_version_manager

log = logging.getLogger( __name__ )

FAILED_TO_FETCH_VERSIONS = object()


class InstallAgentDependencyManager( object ):

    def __init__( self, app ):
        self.app = app
        self.install_model = self.app.install_model
        self.INSTALL_ACTIONS = [ 'download_binary', 'download_by_url', 'download_file',
                                 'setup_perl_environment', 'setup_python_environment',
                                 'setup_r_environment', 'setup_ruby_environment', 'shell_command' ]

    def format_traceback( self ):
        ex_type, ex, tb = sys.exc_info()
        return ''.join( traceback.format_tb( tb ) )

    def get_agent_shed_repository_install_dir( self, agent_shed_repository ):
        return os.path.abspath( agent_shed_repository.repo_files_directory( self.app ) )

    def install_and_build_package( self, install_environment, agent_dependency, actions_dict ):
        """Install a Galaxy agent dependency package either via a url or a mercurial or git clone command."""
        install_dir = actions_dict[ 'install_dir' ]
        package_name = actions_dict[ 'package_name' ]
        actions = actions_dict.get( 'actions', None )
        filtered_actions = []
        env_file_builder = EnvFileBuilder( install_dir )
        step_manager = StepManager( self.app )
        if actions:
            with install_environment.use_tmp_dir() as work_dir:
                with lcd( work_dir ):
                    # The first action in the list of actions will be the one that defines the initial download process.
                    # There are currently three supported actions; download_binary, download_by_url and clone via a
                    # shell_command action type.  The recipe steps will be filtered at this stage in the process, with
                    # the filtered actions being used in the next stage below.  The installation directory (i.e., dir)
                    # is also defined in this stage and is used in the next stage below when defining current_dir.
                    action_type, action_dict = actions[ 0 ]
                    if action_type in self.INSTALL_ACTIONS:
                        # Some of the parameters passed here are needed only by a subset of the step handler classes,
                        # but to allow for a standard method signature we'll pass them along.  We don't check the
                        # agent_dependency status in this stage because it should not have been changed based on a
                        # download.
                        agent_dependency, filtered_actions, dir = \
                            step_manager.execute_step( agent_dependency=agent_dependency,
                                                       package_name=package_name,
                                                       actions=actions,
                                                       action_type=action_type,
                                                       action_dict=action_dict,
                                                       filtered_actions=filtered_actions,
                                                       env_file_builder=env_file_builder,
                                                       install_environment=install_environment,
                                                       work_dir=work_dir,
                                                       current_dir=None,
                                                       initial_download=True )
                    else:
                        # We're handling a complex repository dependency where we only have a set_environment tag set.
                        # <action type="set_environment">
                        #    <environment_variable name="PATH" action="prepend_to">$INSTALL_DIR/bin</environment_variable>
                        # </action>
                        filtered_actions = [ a for a in actions ]
                        dir = install_dir
                    # We're in stage 2 of the installation process.  The package has been down-loaded, so we can
                    # now perform all of the actions defined for building it.
                    for action_tup in filtered_actions:
                        if dir is None:
                            dir = ''
                        current_dir = os.path.abspath( os.path.join( work_dir, dir ) )
                        with lcd( current_dir ):
                            action_type, action_dict = action_tup
                            agent_dependency, tmp_filtered_actions, tmp_dir = \
                                step_manager.execute_step( agent_dependency=agent_dependency,
                                                           package_name=package_name,
                                                           actions=actions,
                                                           action_type=action_type,
                                                           action_dict=action_dict,
                                                           filtered_actions=filtered_actions,
                                                           env_file_builder=env_file_builder,
                                                           install_environment=install_environment,
                                                           work_dir=work_dir,
                                                           current_dir=current_dir,
                                                           initial_download=False )
                            if agent_dependency.status in [ self.install_model.AgentDependency.installation_status.ERROR ]:
                                # If the agent_dependency status is in an error state, return it with no additional
                                # processing.
                                return agent_dependency
                            # Make sure to handle the special case where the value of dir is reset (this happens when
                            # the action_type is change_directiory).  In all other action types, dir will be returned as
                            # None.
                            if tmp_dir is not None:
                                dir = tmp_dir
        return agent_dependency

    def install_and_build_package_via_fabric( self, install_environment, agent_shed_repository, agent_dependency, actions_dict ):
        try:
            # There is currently only one fabric method.
            agent_dependency = self.install_and_build_package( install_environment, agent_dependency, actions_dict )
        except Exception, e:
            log.exception( 'Error installing agent dependency %s version %s.', str( agent_dependency.name ), str( agent_dependency.version ) )
            # Since there was an installation error, update the agent dependency status to Error. The remove_installation_path option must
            # be left False here.
            error_message = '%s\n%s' % ( self.format_traceback(), str( e ) )
            agent_dependency = agent_dependency_util.set_agent_dependency_attributes(self.app,
                                                                                  agent_dependency=agent_dependency,
                                                                                  status=self.app.install_model.AgentDependency.installation_status.ERROR,
                                                                                  error_message=error_message)
        agent_dependency = self.mark_agent_dependency_installed( agent_dependency )
        return agent_dependency

    def install_specified_agent_dependencies( self, agent_shed_repository, agent_dependencies_config, agent_dependencies,
                                             from_agent_migration_manager=False ):
        """
        Follow the recipe in the received agent_dependencies_config to install specified packages for
        repository agents.  The received list of agent_dependencies are the database records for those
        dependencies defined in the agent_dependencies_config that are to be installed.  This list may
        be a subset of the set of dependencies defined in the agent_dependencies_config.  This allows
        for filtering out dependencies that have not been checked for installation on the 'Manage agent
        dependencies' page for an installed Agent Shed repository.
        """
        attr_tups_of_dependencies_for_install = [ ( td.name, td.version, td.type ) for td in agent_dependencies ]
        installed_packages = []
        tag_manager = TagManager( self.app )
        # Parse the agent_dependencies.xml config.
        tree, error_message = xml_util.parse_xml( agent_dependencies_config )
        if tree is None:
            log.debug( "The received agent_dependencies.xml file is likely invalid: %s" % str( error_message ) )
            return installed_packages
        root = tree.getroot()
        elems = []
        for elem in root:
            if elem.tag == 'set_environment':
                version = elem.get( 'version', '1.0' )
                if version != '1.0':
                    raise Exception( 'The <set_environment> tag must have a version attribute with value 1.0' )
                for sub_elem in elem:
                    elems.append( sub_elem )
            else:
                elems.append( elem )
        for elem in elems:
            name = elem.get( 'name', None )
            version = elem.get( 'version', None )
            type = elem.get( 'type', None )
            if type is None:
                if elem.tag in [ 'environment_variable', 'set_environment' ]:
                    type = 'set_environment'
                else:
                    type = 'package'
            if ( name and type == 'set_environment' ) or ( name and version ):
                # elem is a package set_environment tag set.
                attr_tup = ( name, version, type )
                try:
                    index = attr_tups_of_dependencies_for_install.index( attr_tup )
                except Exception, e:
                    index = None
                if index is not None:
                    agent_dependency = agent_dependencies[ index ]
                    # If the agent_dependency.type is 'set_environment', then the call to process_tag_set() will
                    # handle everything - no additional installation is necessary.
                    agent_dependency, proceed_with_install, action_elem_tuples = \
                        tag_manager.process_tag_set( agent_shed_repository,
                                                     agent_dependency,
                                                     elem,
                                                     name,
                                                     version,
                                                     from_agent_migration_manager=from_agent_migration_manager,
                                                     agent_dependency_db_records=agent_dependencies )
                    if ( agent_dependency.type == 'package' and proceed_with_install ):
                        try:
                            agent_dependency = self.install_package( elem,
                                                                    agent_shed_repository,
                                                                    agent_dependencies=agent_dependencies,
                                                                    from_agent_migration_manager=from_agent_migration_manager )
                        except Exception, e:
                            error_message = "Error installing agent dependency %s version %s: %s" % \
                                ( str( name ), str( version ), str( e ) )
                            log.exception( error_message )
                            if agent_dependency:
                                # Since there was an installation error, update the agent dependency status to Error. The
                                # remove_installation_path option must be left False here.
                                agent_dependency = \
                                    agent_dependency_util.set_agent_dependency_attributes(self.app,
                                                                                        agent_dependency=agent_dependency,
                                                                                        status=self.app.install_model.AgentDependency.installation_status.ERROR,
                                                                                        error_message=error_message)
                        if agent_dependency and agent_dependency.status in [ self.install_model.AgentDependency.installation_status.INSTALLED,
                                                                           self.install_model.AgentDependency.installation_status.ERROR ]:
                            installed_packages.append( agent_dependency )
                            if self.app.config.manage_dependency_relationships:
                                # Add the agent_dependency to the in-memory dictionaries in the installed_repository_manager.
                                self.app.installed_repository_manager.handle_agent_dependency_install( agent_shed_repository,
                                                                                                      agent_dependency )
        return installed_packages

    def install_via_fabric( self, agent_shed_repository, agent_dependency, install_dir, package_name=None, custom_fabfile_path=None,
                            actions_elem=None, action_elem=None, **kwd ):
        """
        Parse a agent_dependency.xml file's <actions> tag set to gather information for installation using
        self.install_and_build_package().  The use of fabric is being eliminated, so some of these functions
        may need to be renamed at some point.
        """
        if not os.path.exists( install_dir ):
            os.makedirs( install_dir )
        actions_dict = dict( install_dir=install_dir )
        if package_name:
            actions_dict[ 'package_name' ] = package_name
        actions = []
        is_binary_download = False
        if actions_elem is not None:
            elems = actions_elem
            if elems.get( 'os' ) is not None and elems.get( 'architecture' ) is not None:
                is_binary_download = True
        elif action_elem is not None:
            # We were provided with a single <action> element to perform certain actions after a platform-specific tarball was downloaded.
            elems = [ action_elem ]
        else:
            elems = []
        step_manager = StepManager( self.app )
        agent_shed_repository_install_dir = self.get_agent_shed_repository_install_dir( agent_shed_repository )
        install_environment = InstallEnvironment( self.app, agent_shed_repository_install_dir, install_dir )
        for action_elem in elems:
            # Make sure to skip all comments, since they are now included in the XML tree.
            if action_elem.tag != 'action':
                continue
            action_dict = {}
            action_type = action_elem.get( 'type', None )
            if action_type is not None:
                action_dict = step_manager.prepare_step( agent_dependency=agent_dependency,
                                                         action_type=action_type,
                                                         action_elem=action_elem,
                                                         action_dict=action_dict,
                                                         install_environment=install_environment,
                                                         is_binary_download=is_binary_download )
                action_tuple = ( action_type, action_dict )
                if action_type == 'set_environment':
                    if action_tuple not in actions:
                        actions.append( action_tuple )
                else:
                    actions.append( action_tuple )
        if actions:
            actions_dict[ 'actions' ] = actions
        if custom_fabfile_path is not None:
            # TODO: this is not yet supported or functional, but when it is handle it using the fabric api.
            raise Exception( 'Agent dependency installation using proprietary fabric scripts is not yet supported.' )
        else:
            agent_dependency = self.install_and_build_package_via_fabric( install_environment,
                                                                         agent_shed_repository,
                                                                         agent_dependency,
                                                                         actions_dict )
        return agent_dependency

    def install_package( self, elem, agent_shed_repository, agent_dependencies=None, from_agent_migration_manager=False ):
        """
        Install a agent dependency package defined by the XML element elem.  The value of agent_dependencies is
        a partial or full list of AgentDependency records associated with the agent_shed_repository.
        """
        tag_manager = TagManager( self.app )
        # The value of package_name should match the value of the "package" type in the agent config's
        # <requirements> tag set, but it's not required.
        package_name = elem.get( 'name', None )
        package_version = elem.get( 'version', None )
        if agent_dependencies and package_name and package_version:
            agent_dependency = None
            for agent_dependency in agent_dependencies:
                if package_name == str( agent_dependency.name ) and package_version == str( agent_dependency.version ):
                    break
            if agent_dependency is not None:
                for package_elem in elem:
                    agent_dependency, proceed_with_install, actions_elem_tuples = \
                        tag_manager.process_tag_set( agent_shed_repository,
                                                     agent_dependency,
                                                     package_elem,
                                                     package_name,
                                                     package_version,
                                                     from_agent_migration_manager=from_agent_migration_manager,
                                                     agent_dependency_db_records=None )
                    if proceed_with_install and actions_elem_tuples:
                        # Get the installation directory for agent dependencies that will be installed for the received
                        # agent_shed_repository.
                        install_dir = \
                            agent_dependency_util.get_agent_dependency_install_dir( app=self.app,
                                                                                  repository_name=agent_shed_repository.name,
                                                                                  repository_owner=agent_shed_repository.owner,
                                                                                  repository_changeset_revision=agent_shed_repository.installed_changeset_revision,
                                                                                  agent_dependency_type='package',
                                                                                  agent_dependency_name=package_name,
                                                                                  agent_dependency_version=package_version )
                        # At this point we have a list of <actions> elems that are either defined within an <actions_group>
                        # tag set with <actions> sub-elements that contains os and architecture attributes filtered by the
                        # platform into which the appropriate compiled binary will be installed, or not defined within an
                        # <actions_group> tag set and not filtered.  Here is an example actions_elem_tuple.
                        # [(True, [<Element 'actions' at 0x109293d10>)]
                        binary_installed = False
                        for actions_elem_tuple in actions_elem_tuples:
                            in_actions_group, actions_elems = actions_elem_tuple
                            if in_actions_group:
                                # Platform matching is only performed inside <actions_group> tag sets, os and architecture
                                # attributes are otherwise ignored.
                                can_install_from_source = False
                                for actions_elem in actions_elems:
                                    system = actions_elem.get( 'os' )
                                    architecture = actions_elem.get( 'architecture' )
                                    # If this <actions> element has the os and architecture attributes defined, then we only
                                    # want to process until a successful installation is achieved.
                                    if system and architecture:
                                        # If an <actions> tag has been defined that matches our current platform, and the
                                        # recipe specified within that <actions> tag has been successfully processed, skip
                                        # any remaining platform-specific <actions> tags.  We cannot break out of the loop
                                        # here because there may be <action> tags at the end of the <actions_group> tag set
                                        # that must be processed.
                                        if binary_installed:
                                            continue
                                        # No platform-specific <actions> recipe has yet resulted in a successful installation.
                                        agent_dependency = self.install_via_fabric( agent_shed_repository,
                                                                                   agent_dependency,
                                                                                   install_dir,
                                                                                   package_name=package_name,
                                                                                   actions_elem=actions_elem,
                                                                                   action_elem=None )
                                        if agent_dependency.status == self.install_model.AgentDependency.installation_status.INSTALLED:
                                            # If an <actions> tag was found that matches the current platform, and
                                            # self.install_via_fabric() did not result in an error state, set binary_installed
                                            # to True in order to skip any remaining platform-specific <actions> tags.
                                            binary_installed = True
                                        else:
                                            # Process the next matching <actions> tag, or any defined <actions> tags that do not
                                            # contain platform dependent recipes.
                                            log.debug( 'Error downloading binary for agent dependency %s version %s: %s' %
                                                       ( str( package_name ), str( package_version ), str( agent_dependency.error_message ) ) )
                                    else:
                                        if actions_elem.tag == 'actions':
                                            # We've reached an <actions> tag that defines the recipe for installing and compiling from
                                            # source.  If binary installation failed, we proceed with the recipe.
                                            if not binary_installed:
                                                installation_directory = agent_dependency.installation_directory( self.app )
                                                if os.path.exists( installation_directory ):
                                                    # Delete contents of installation directory if attempt at binary installation failed.
                                                    installation_directory_contents = os.listdir( installation_directory )
                                                    if installation_directory_contents:
                                                        removed, error_message = \
                                                            agent_dependency_util.remove_agent_dependency( self.app, agent_dependency )
                                                        if removed:
                                                            can_install_from_source = True
                                                        else:
                                                            log.debug( 'Error removing old files from installation directory %s: %s' %
                                                                       ( str( installation_directory, str( error_message ) ) ) )
                                                    else:
                                                        can_install_from_source = True
                                                else:
                                                    can_install_from_source = True
                                            if can_install_from_source:
                                                # We now know that binary installation was not successful, so proceed with the <actions>
                                                # tag set that defines the recipe to install and compile from source.
                                                log.debug( 'Proceeding with install and compile recipe for agent dependency %s.' %
                                                           str( agent_dependency.name ) )
                                                # Reset above error to installing
                                                agent_dependency.status = self.install_model.AgentDependency.installation_status.INSTALLING
                                                agent_dependency = self.install_via_fabric( agent_shed_repository,
                                                                                           agent_dependency,
                                                                                           install_dir,
                                                                                           package_name=package_name,
                                                                                           actions_elem=actions_elem,
                                                                                           action_elem=None )
                                    if actions_elem.tag == 'action' and \
                                            agent_dependency.status != self.install_model.AgentDependency.installation_status.ERROR:
                                        # If the agent dependency is not in an error state, perform any final actions that have been
                                        # defined within the actions_group tag set, but outside of an <actions> tag, which defines
                                        # the recipe for installing and compiling from source.
                                        agent_dependency = self.install_via_fabric( agent_shed_repository,
                                                                                   agent_dependency,
                                                                                   install_dir,
                                                                                   package_name=package_name,
                                                                                   actions_elem=None,
                                                                                   action_elem=actions_elem )
                            else:
                                # Checks for "os" and "architecture" attributes  are not made for any <actions> tag sets outside of
                                # an <actions_group> tag set.  If the attributes are defined, they will be ignored. All <actions> tags
                                # outside of an <actions_group> tag set will always be processed.
                                agent_dependency = self.install_via_fabric( agent_shed_repository,
                                                                           agent_dependency,
                                                                           install_dir,
                                                                           package_name=package_name,
                                                                           actions_elem=actions_elems,
                                                                           action_elem=None )
                                if agent_dependency.status != self.install_model.AgentDependency.installation_status.ERROR:
                                    log.debug( 'Agent dependency %s version %s has been installed in %s.' %
                                               ( str( package_name ), str( package_version ), str( install_dir ) ) )
        return agent_dependency

    def mark_agent_dependency_installed( self, agent_dependency ):
        if agent_dependency.status not in [ self.install_model.AgentDependency.installation_status.ERROR,
                                           self.install_model.AgentDependency.installation_status.INSTALLED ]:
            log.debug( 'Changing status for agent dependency %s from %s to %s.' %
                       ( str( agent_dependency.name ),
                         str( agent_dependency.status ),
                           str( self.install_model.AgentDependency.installation_status.INSTALLED ) ) )
            status = self.install_model.AgentDependency.installation_status.INSTALLED
            agent_dependency = agent_dependency_util.set_agent_dependency_attributes( self.app,
                                                                                   agent_dependency=agent_dependency,
                                                                                   status=status )
        return agent_dependency


class InstallRepositoryManager( object ):

    def __init__( self, app, tpm=None ):
        self.app = app
        self.install_model = self.app.install_model
        if tpm is None:
            self.tpm = agent_panel_manager.AgentPanelManager( self.app )
        else:
            self.tpm = tpm

    def get_repository_components_for_installation( self, encoded_tsr_id, encoded_tsr_ids, repo_info_dicts,
                                                    agent_panel_section_keys ):
        """
        The received encoded_tsr_ids, repo_info_dicts, and
        agent_panel_section_keys are 3 lists that contain associated elements
        at each location in the list.  This method will return the elements
        from repo_info_dicts and agent_panel_section_keys associated with the
        received encoded_tsr_id by determining its location in the received
        encoded_tsr_ids list.
        """
        for tsr_id, repo_info_dict, agent_panel_section_key in zip( encoded_tsr_ids,
                                                                   repo_info_dicts,
                                                                   agent_panel_section_keys ):
            if tsr_id == encoded_tsr_id:
                return repo_info_dict, agent_panel_section_key
        return None, None

    def __get_install_info_from_agent_shed( self, agent_shed_url, name, owner, changeset_revision ):
        params = dict( name=str( name ),
                       owner=str( owner ),
                       changeset_revision=str( changeset_revision ) )
        pathspec = [ 'api', 'repositories', 'get_repository_revision_install_info' ]
        try:
            raw_text = common_util.agent_shed_get( self.app, agent_shed_url, pathspec=pathspec, params=params )
        except Exception, e:
            message = "Error attempting to retrieve installation information from agent shed "
            message += "%s for revision %s of repository %s owned by %s: %s" % \
                ( str( agent_shed_url ), str( changeset_revision ), str( name ), str( owner ), str( e ) )
            log.warn( message )
            raise exceptions.InternalServerError( message )
        if raw_text:
            # If successful, the response from get_repository_revision_install_info will be 3
            # dictionaries, a dictionary defining the Repository, a dictionary defining the
            # Repository revision (RepositoryMetadata), and a dictionary including the additional
            # information required to install the repository.
            items = json.loads( raw_text )
            repository_revision_dict = items[ 1 ]
            repo_info_dict = items[ 2 ]
        else:
            message = "Unable to retrieve installation information from agent shed %s for revision %s of repository %s owned by %s: %s" % \
                ( str( agent_shed_url ), str( changeset_revision ), str( name ), str( owner ), str( e ) )
            log.warn( message )
            raise exceptions.InternalServerError( message )
        # Make sure the agent shed returned everything we need for installing the repository.
        if not repository_revision_dict or not repo_info_dict:
            invalid_parameter_message = "No information is available for the requested repository revision.\n"
            invalid_parameter_message += "One or more of the following parameter values is likely invalid:\n"
            invalid_parameter_message += "agent_shed_url: %s\n" % str( agent_shed_url )
            invalid_parameter_message += "name: %s\n" % str( name )
            invalid_parameter_message += "owner: %s\n" % str( owner )
            invalid_parameter_message += "changeset_revision: %s\n" % str( changeset_revision )
            raise exceptions.RequestParameterInvalidException( invalid_parameter_message )
        repo_info_dicts = [ repo_info_dict ]
        return repository_revision_dict, repo_info_dicts

    def __handle_repository_contents( self, agent_shed_repository, agent_path, repository_clone_url, relative_install_dir,
                                      agent_shed=None, agent_section=None, shed_agent_conf=None, reinstalling=False,
                                      agent_versions_response=None ):
        """
        Generate the metadata for the installed agent shed repository, among other things.
        This method is called when an administrator is installing a new repository or
        reinstalling an uninstalled repository.
        """
        shed_config_dict = self.app.agentbox.get_shed_config_dict_by_filename( shed_agent_conf )
        tdtm = data_table_manager.AgentDataTableManager( self.app )
        irmm = InstalledRepositoryMetadataManager( app=self.app,
                                                   tpm=self.tpm,
                                                   repository=agent_shed_repository,
                                                   changeset_revision=agent_shed_repository.changeset_revision,
                                                   repository_clone_url=repository_clone_url,
                                                   shed_config_dict=shed_config_dict,
                                                   relative_install_dir=relative_install_dir,
                                                   repository_files_dir=None,
                                                   resetting_all_metadata_on_repository=False,
                                                   updating_installed_repository=False,
                                                   persist=True )
        irmm.generate_metadata_for_changeset_revision()
        irmm_metadata_dict = irmm.get_metadata_dict()
        agent_shed_repository.metadata = irmm_metadata_dict
        # Update the agent_shed_repository.agent_shed_status column in the database.
        agent_shed_status_dict = suc.get_agent_shed_status_for_installed_repository( self.app, agent_shed_repository )
        if agent_shed_status_dict:
            agent_shed_repository.agent_shed_status = agent_shed_status_dict
        self.install_model.context.add( agent_shed_repository )
        self.install_model.context.flush()
        if agent_versions_response and agent_versions_response is not FAILED_TO_FETCH_VERSIONS:
            agent_version_dicts = agent_versions_response
            tvm = agent_version_manager.AgentVersionManager( self.app )
            tvm.handle_agent_versions( agent_version_dicts, agent_shed_repository )
        if 'agent_dependencies' in irmm_metadata_dict and not reinstalling:
            agent_dependency_util.create_agent_dependency_objects( self.app,
                                                                 agent_shed_repository,
                                                                 relative_install_dir,
                                                                 set_status=True )
        if 'sample_files' in irmm_metadata_dict:
            sample_files = irmm_metadata_dict.get( 'sample_files', [] )
            agent_index_sample_files = tdtm.get_agent_index_sample_files( sample_files )
            agent_data_table_conf_filename, agent_data_table_elems = \
                tdtm.install_agent_data_tables( agent_shed_repository, agent_index_sample_files )
            if agent_data_table_elems:
                self.app.agent_data_tables.add_new_entries_from_config_file( agent_data_table_conf_filename,
                                                                            None,
                                                                            self.app.config.shed_agent_data_table_config,
                                                                            persist=True )
        if 'agents' in irmm_metadata_dict:
            agent_panel_dict = self.tpm.generate_agent_panel_dict_for_new_install( irmm_metadata_dict[ 'agents' ], agent_section )
            sample_files = irmm_metadata_dict.get( 'sample_files', [] )
            agent_index_sample_files = tdtm.get_agent_index_sample_files( sample_files )
            agent_util.copy_sample_files( self.app, agent_index_sample_files, agent_path=agent_path )
            sample_files_copied = [ str( s ) for s in agent_index_sample_files ]
            repository_agents_tups = irmm.get_repository_agents_tups()
            if repository_agents_tups:
                # Handle missing data table entries for agent parameters that are dynamically generated select lists.
                repository_agents_tups = tdtm.handle_missing_data_table_entry( relative_install_dir,
                                                                              agent_path,
                                                                              repository_agents_tups )
                # Handle missing index files for agent parameters that are dynamically generated select lists.
                repository_agents_tups, sample_files_copied = agent_util.handle_missing_index_file( self.app,
                                                                                                  agent_path,
                                                                                                  sample_files,
                                                                                                  repository_agents_tups,
                                                                                                  sample_files_copied )
                # Copy remaining sample files included in the repository to the ~/agent-data directory of the
                # local Galaxy instance.
                agent_util.copy_sample_files( self.app,
                                             sample_files,
                                             agent_path=agent_path,
                                             sample_files_copied=sample_files_copied )
                self.tpm.add_to_agent_panel( repository_name=agent_shed_repository.name,
                                            repository_clone_url=repository_clone_url,
                                            changeset_revision=agent_shed_repository.installed_changeset_revision,
                                            repository_agents_tups=repository_agents_tups,
                                            owner=agent_shed_repository.owner,
                                            shed_agent_conf=shed_agent_conf,
                                            agent_panel_dict=agent_panel_dict,
                                            new_install=True )
        if 'data_manager' in irmm_metadata_dict:
            dmh = data_manager.DataManagerHandler( self.app )
            dmh.install_data_managers( self.app.config.shed_data_manager_config_file,
                                       irmm_metadata_dict,
                                       shed_config_dict,
                                       relative_install_dir,
                                       agent_shed_repository,
                                       repository_agents_tups )
        if 'datatypes' in irmm_metadata_dict:
            agent_shed_repository.status = self.install_model.AgentShedRepository.installation_status.LOADING_PROPRIETARY_DATATYPES
            if not agent_shed_repository.includes_datatypes:
                agent_shed_repository.includes_datatypes = True
            self.install_model.context.add( agent_shed_repository )
            self.install_model.context.flush()
            files_dir = relative_install_dir
            if shed_config_dict.get( 'agent_path' ):
                files_dir = os.path.join( shed_config_dict[ 'agent_path' ], files_dir )
            datatypes_config = hg_util.get_config_from_disk( suc.DATATYPES_CONFIG_FILENAME, files_dir )
            # Load data types required by agents.
            cdl = custom_datatype_manager.CustomDatatypeLoader( self.app )
            converter_path, display_path = \
                cdl.alter_config_and_load_prorietary_datatypes( datatypes_config, files_dir, override=False )
            if converter_path or display_path:
                # Create a dictionary of agent shed repository related information.
                repository_dict = \
                    cdl.create_repository_dict_for_proprietary_datatypes( agent_shed=agent_shed,
                                                                          name=agent_shed_repository.name,
                                                                          owner=agent_shed_repository.owner,
                                                                          installed_changeset_revision=agent_shed_repository.installed_changeset_revision,
                                                                          agent_dicts=irmm_metadata_dict.get( 'agents', [] ),
                                                                          converter_path=converter_path,
                                                                          display_path=display_path )
            if converter_path:
                # Load proprietary datatype converters
                self.app.datatypes_registry.load_datatype_converters( self.app.agentbox, installed_repository_dict=repository_dict )
            if display_path:
                # Load proprietary datatype display applications
                self.app.datatypes_registry.load_display_applications( self.app, installed_repository_dict=repository_dict )

    def handle_agent_shed_repositories( self, installation_dict ):
        # The following installation_dict entries are all required.
        install_repository_dependencies = installation_dict[ 'install_repository_dependencies' ]
        new_agent_panel_section_label = installation_dict[ 'new_agent_panel_section_label' ]
        no_changes_checked = installation_dict[ 'no_changes_checked' ]
        repo_info_dicts = installation_dict[ 'repo_info_dicts' ]
        agent_panel_section_id = installation_dict[ 'agent_panel_section_id' ]
        agent_path = installation_dict[ 'agent_path' ]
        agent_shed_url = installation_dict[ 'agent_shed_url' ]
        rdim = repository_dependency_manager.RepositoryDependencyInstallManager( self.app )
        created_or_updated_agent_shed_repositories, agent_panel_section_keys, repo_info_dicts, filtered_repo_info_dicts = \
            rdim.create_repository_dependency_objects( agent_path=agent_path,
                                                       agent_shed_url=agent_shed_url,
                                                       repo_info_dicts=repo_info_dicts,
                                                       install_repository_dependencies=install_repository_dependencies,
                                                       no_changes_checked=no_changes_checked,
                                                       agent_panel_section_id=agent_panel_section_id,
                                                       new_agent_panel_section_label=new_agent_panel_section_label )
        return created_or_updated_agent_shed_repositories, agent_panel_section_keys, repo_info_dicts, filtered_repo_info_dicts

    def initiate_repository_installation( self, installation_dict ):
        # The following installation_dict entries are all required.
        created_or_updated_agent_shed_repositories = installation_dict[ 'created_or_updated_agent_shed_repositories' ]
        filtered_repo_info_dicts = installation_dict[ 'filtered_repo_info_dicts' ]
        has_repository_dependencies = installation_dict[ 'has_repository_dependencies' ]
        includes_agent_dependencies = installation_dict[ 'includes_agent_dependencies' ]
        includes_agents = installation_dict[ 'includes_agents' ]
        includes_agents_for_display_in_agent_panel = installation_dict[ 'includes_agents_for_display_in_agent_panel' ]
        install_repository_dependencies = installation_dict[ 'install_repository_dependencies' ]
        install_agent_dependencies = installation_dict[ 'install_agent_dependencies' ]
        message = installation_dict[ 'message' ]
        new_agent_panel_section_label = installation_dict[ 'new_agent_panel_section_label' ]
        shed_agent_conf = installation_dict[ 'shed_agent_conf' ]
        status = installation_dict[ 'status' ]
        agent_panel_section_id = installation_dict[ 'agent_panel_section_id' ]
        agent_panel_section_keys = installation_dict[ 'agent_panel_section_keys' ]
        agent_path = installation_dict[ 'agent_path' ]
        agent_shed_url = installation_dict[ 'agent_shed_url' ]
        # Handle contained agents.
        if includes_agents_for_display_in_agent_panel and ( new_agent_panel_section_label or agent_panel_section_id ):
            self.tpm.handle_agent_panel_section( self.app.agentbox,
                                                agent_panel_section_id=agent_panel_section_id,
                                                new_agent_panel_section_label=new_agent_panel_section_label )
        encoded_repository_ids = [ self.app.security.encode_id( tsr.id ) for tsr in created_or_updated_agent_shed_repositories ]
        new_kwd = dict( includes_agents=includes_agents,
                        includes_agents_for_display_in_agent_panel=includes_agents_for_display_in_agent_panel,
                        has_repository_dependencies=has_repository_dependencies,
                        install_repository_dependencies=install_repository_dependencies,
                        includes_agent_dependencies=includes_agent_dependencies,
                        install_agent_dependencies=install_agent_dependencies,
                        message=message,
                        repo_info_dicts=filtered_repo_info_dicts,
                        shed_agent_conf=shed_agent_conf,
                        status=status,
                        agent_path=agent_path,
                        agent_panel_section_keys=agent_panel_section_keys,
                        agent_shed_repository_ids=encoded_repository_ids,
                        agent_shed_url=agent_shed_url )
        encoded_kwd = encoding_util.agent_shed_encode( new_kwd )
        tsr_ids = [ r.id for r in created_or_updated_agent_shed_repositories  ]
        agent_shed_repositories = []
        for tsr_id in tsr_ids:
            tsr = self.install_model.context.query( self.install_model.AgentShedRepository ).get( tsr_id )
            agent_shed_repositories.append( tsr )
        clause_list = []
        for tsr_id in tsr_ids:
            clause_list.append( self.install_model.AgentShedRepository.table.c.id == tsr_id )
        query = self.install_model.context.query( self.install_model.AgentShedRepository ).filter( or_( *clause_list ) )
        return encoded_kwd, query, agent_shed_repositories, encoded_repository_ids

    def install( self, agent_shed_url, name, owner, changeset_revision, install_options ):
        # Get all of the information necessary for installing the repository from the specified agent shed.
        repository_revision_dict, repo_info_dicts = self.__get_install_info_from_agent_shed( agent_shed_url,
                                                                                            name,
                                                                                            owner,
                                                                                            changeset_revision )
        installed_agent_shed_repositories = self.__initiate_and_install_repositories(
            agent_shed_url,
            repository_revision_dict,
            repo_info_dicts,
            install_options
        )
        return installed_agent_shed_repositories

    def __initiate_and_install_repositories( self, agent_shed_url, repository_revision_dict, repo_info_dicts, install_options ):
        try:
            has_repository_dependencies = repository_revision_dict[ 'has_repository_dependencies' ]
        except KeyError:
            raise exceptions.InternalServerError( "Agent shed response missing required parameter 'has_repository_dependencies'." )
        try:
            includes_agents = repository_revision_dict[ 'includes_agents' ]
        except KeyError:
            raise exceptions.InternalServerError( "Agent shed response missing required parameter 'includes_agents'." )
        try:
            includes_agent_dependencies = repository_revision_dict[ 'includes_agent_dependencies' ]
        except KeyError:
            raise exceptions.InternalServerError( "Agent shed response missing required parameter 'includes_agent_dependencies'." )
        try:
            includes_agents_for_display_in_agent_panel = repository_revision_dict[ 'includes_agents_for_display_in_agent_panel' ]
        except KeyError:
            raise exceptions.InternalServerError( "Agent shed response missing required parameter 'includes_agents_for_display_in_agent_panel'." )
        # Get the information about the Galaxy components (e.g., agent pane section, agent config file, etc) that will contain the repository information.
        install_repository_dependencies = install_options.get( 'install_repository_dependencies', False )
        install_agent_dependencies = install_options.get( 'install_agent_dependencies', False )
        if install_agent_dependencies:
            self.__assert_can_install_dependencies()
        new_agent_panel_section_label = install_options.get( 'new_agent_panel_section_label', '' )
        shed_agent_conf = install_options.get( 'shed_agent_conf', None )
        if shed_agent_conf:
            # Get the agent_path setting.
            shed_conf_dict = self.tpm.get_shed_agent_conf_dict( shed_agent_conf )
            agent_path = shed_conf_dict[ 'agent_path' ]
        else:
            # Don't use migrated_agents_conf.xml.
            try:
                shed_config_dict = self.app.agentbox.dynamic_confs( include_migrated_agent_conf=False )[ 0 ]
            except IndexError:
                raise exceptions.RequestParameterMissingException( "Missing required parameter 'shed_agent_conf'." )
            shed_agent_conf = shed_config_dict[ 'config_filename' ]
            agent_path = shed_config_dict[ 'agent_path' ]
        agent_panel_section_id = self.app.agentbox.find_section_id( install_options.get( 'agent_panel_section_id', '' ) )
        # Build the dictionary of information necessary for creating agent_shed_repository database records
        # for each repository being installed.
        installation_dict = dict( install_repository_dependencies=install_repository_dependencies,
                                  new_agent_panel_section_label=new_agent_panel_section_label,
                                  no_changes_checked=False,
                                  repo_info_dicts=repo_info_dicts,
                                  agent_panel_section_id=agent_panel_section_id,
                                  agent_path=agent_path,
                                  agent_shed_url=agent_shed_url )
        # Create the agent_shed_repository database records and gather additional information for repository installation.
        created_or_updated_agent_shed_repositories, agent_panel_section_keys, repo_info_dicts, filtered_repo_info_dicts = \
            self.handle_agent_shed_repositories( installation_dict )
        if created_or_updated_agent_shed_repositories:
            # Build the dictionary of information necessary for installing the repositories.
            installation_dict = dict( created_or_updated_agent_shed_repositories=created_or_updated_agent_shed_repositories,
                                      filtered_repo_info_dicts=filtered_repo_info_dicts,
                                      has_repository_dependencies=has_repository_dependencies,
                                      includes_agent_dependencies=includes_agent_dependencies,
                                      includes_agents=includes_agents,
                                      includes_agents_for_display_in_agent_panel=includes_agents_for_display_in_agent_panel,
                                      install_repository_dependencies=install_repository_dependencies,
                                      install_agent_dependencies=install_agent_dependencies,
                                      message='',
                                      new_agent_panel_section_label=new_agent_panel_section_label,
                                      shed_agent_conf=shed_agent_conf,
                                      status='done',
                                      agent_panel_section_id=agent_panel_section_id,
                                      agent_panel_section_keys=agent_panel_section_keys,
                                      agent_path=agent_path,
                                      agent_shed_url=agent_shed_url )
            # Prepare the repositories for installation.  Even though this
            # method receives a single combination of agent_shed_url, name,
            # owner and changeset_revision, there may be multiple repositories
            # for installation at this point because repository dependencies
            # may have added additional repositories for installation along
            # with the single specified repository.
            encoded_kwd, query, agent_shed_repositories, encoded_repository_ids = \
                self.initiate_repository_installation( installation_dict )
            # Some repositories may have repository dependencies that are
            # required to be installed before the dependent repository, so
            # we'll order the list of tsr_ids to ensure all repositories
            # install in the required order.
            tsr_ids = [ self.app.security.encode_id( agent_shed_repository.id ) for agent_shed_repository in agent_shed_repositories ]

            decoded_kwd = dict(
                shed_agent_conf=shed_agent_conf,
                agent_path=agent_path,
                agent_panel_section_keys=agent_panel_section_keys,
                repo_info_dicts=filtered_repo_info_dicts,
                install_agent_dependencies=install_agent_dependencies,
            )
            return self.install_repositories(tsr_ids, decoded_kwd, reinstalling=False)

    def install_repositories( self, tsr_ids, decoded_kwd, reinstalling ):
        shed_agent_conf = decoded_kwd.get( 'shed_agent_conf', '' )
        agent_path = decoded_kwd[ 'agent_path' ]
        agent_panel_section_keys = util.listify( decoded_kwd[ 'agent_panel_section_keys' ] )
        repo_info_dicts = util.listify( decoded_kwd[ 'repo_info_dicts' ] )
        install_agent_dependencies = decoded_kwd['install_agent_dependencies']
        filtered_repo_info_dicts = []
        filtered_agent_panel_section_keys = []
        repositories_for_installation = []
        # Some repositories may have repository dependencies that are required to be installed before the
        # dependent repository, so we'll order the list of tsr_ids to ensure all repositories install in the
        # required order.
        ordered_tsr_ids, ordered_repo_info_dicts, ordered_agent_panel_section_keys = \
            self.order_components_for_installation( tsr_ids,
                                                    repo_info_dicts,
                                                    agent_panel_section_keys=agent_panel_section_keys )
        for tsr_id in ordered_tsr_ids:
            repository = self.install_model.context.query( self.install_model.AgentShedRepository ) \
                .get( self.app.security.decode_id( tsr_id ) )
            if repository.status in [ self.install_model.AgentShedRepository.installation_status.NEW,
                                      self.install_model.AgentShedRepository.installation_status.UNINSTALLED ]:
                repositories_for_installation.append( repository )
                repo_info_dict, agent_panel_section_key = \
                    self.get_repository_components_for_installation( tsr_id,
                                                                     ordered_tsr_ids,
                                                                     ordered_repo_info_dicts,
                                                                     ordered_agent_panel_section_keys )
                filtered_repo_info_dicts.append( repo_info_dict )
                filtered_agent_panel_section_keys.append( agent_panel_section_key )

        installed_agent_shed_repositories = []
        if repositories_for_installation:
            for agent_shed_repository, repo_info_dict, agent_panel_section_key in zip( repositories_for_installation,
                                                                                     filtered_repo_info_dicts,
                                                                                     filtered_agent_panel_section_keys ):
                self.install_agent_shed_repository( agent_shed_repository,
                                                   repo_info_dict=repo_info_dict,
                                                   agent_panel_section_key=agent_panel_section_key,
                                                   shed_agent_conf=shed_agent_conf,
                                                   agent_path=agent_path,
                                                   install_agent_dependencies=install_agent_dependencies,
                                                   reinstalling=reinstalling )
                installed_agent_shed_repositories.append( agent_shed_repository )
        else:
            raise RepositoriesInstalledException()
        return installed_agent_shed_repositories

    def install_agent_shed_repository( self, agent_shed_repository, repo_info_dict, agent_panel_section_key, shed_agent_conf, agent_path,
                                      install_agent_dependencies, reinstalling=False ):
        if agent_panel_section_key:
            _, agent_section = self.app.agentbox.get_section( agent_panel_section_key )
            if agent_section is None:
                log.debug( 'Invalid agent_panel_section_key "%s" specified.  Agents will be loaded outside of sections in the agent panel.',
                           str( agent_panel_section_key ) )
        else:
            agent_section = None
        if isinstance( repo_info_dict, basestring ):
            repo_info_dict = encoding_util.agent_shed_decode( repo_info_dict )
        # Clone each repository to the configured location.
        self.update_agent_shed_repository_status( agent_shed_repository,
                                                 self.install_model.AgentShedRepository.installation_status.CLONING )
        repo_info_tuple = repo_info_dict[ agent_shed_repository.name ]
        description, repository_clone_url, changeset_revision, ctx_rev, repository_owner, repository_dependencies, agent_dependencies = repo_info_tuple
        relative_clone_dir = suc.generate_agent_shed_repository_install_dir( repository_clone_url,
                                                                            agent_shed_repository.installed_changeset_revision )
        relative_install_dir = os.path.join( relative_clone_dir, agent_shed_repository.name )
        install_dir = os.path.join( agent_path, relative_install_dir )
        cloned_ok, error_message = hg_util.clone_repository( repository_clone_url, os.path.abspath( install_dir ), ctx_rev )
        if cloned_ok:
            if reinstalling:
                # Since we're reinstalling the repository we need to find the latest changeset revision to
                # which it can be updated.
                changeset_revision_dict = self.app.update_repository_manager.get_update_to_changeset_revision_and_ctx_rev( agent_shed_repository )
                current_changeset_revision = changeset_revision_dict.get( 'changeset_revision', None )
                current_ctx_rev = changeset_revision_dict.get( 'ctx_rev', None )
                if current_ctx_rev != ctx_rev:
                    repo = hg_util.get_repo_for_repository( self.app,
                                                            repository=None,
                                                            repo_path=os.path.abspath( install_dir ),
                                                            create=False )
                    hg_util.pull_repository( repo, repository_clone_url, current_changeset_revision )
                    hg_util.update_repository( repo, ctx_rev=current_ctx_rev )
            agent_versions_response = fetch_agent_versions( self.app, agent_shed_repository )
            self.__handle_repository_contents( agent_shed_repository=agent_shed_repository,
                                               agent_path=agent_path,
                                               repository_clone_url=repository_clone_url,
                                               relative_install_dir=relative_install_dir,
                                               agent_shed=agent_shed_repository.agent_shed,
                                               agent_section=agent_section,
                                               shed_agent_conf=shed_agent_conf,
                                               agent_versions_response=agent_versions_response,
                                               reinstalling=reinstalling )
            self.install_model.context.refresh( agent_shed_repository )
            metadata = agent_shed_repository.metadata
            if 'agents' in metadata:
                # Get the agent_versions from the agent shed for each agent in the installed change set.
                self.update_agent_shed_repository_status( agent_shed_repository,
                                                         self.install_model.AgentShedRepository.installation_status.SETTING_TOOL_VERSIONS )
                if agent_versions_response is FAILED_TO_FETCH_VERSIONS:
                    if not error_message:
                        error_message = ""
                    error_message += "Version information for the agents included in the <b>%s</b> repository is missing.  " % agent_shed_repository.name
                    error_message += "Reset all of this repository's metadata in the agent shed, then set the installed agent versions "
                    error_message += "from the installed repository's <b>Repository Actions</b> menu.  "
            if install_agent_dependencies and agent_shed_repository.agent_dependencies and 'agent_dependencies' in metadata:
                work_dir = tempfile.mkdtemp( prefix="tmp-agentshed-itsr" )
                # Install agent dependencies.
                self.update_agent_shed_repository_status( agent_shed_repository,
                                                         self.install_model.AgentShedRepository.installation_status.INSTALLING_TOOL_DEPENDENCIES )
                # Get the agent_dependencies.xml file from the repository.
                agent_dependencies_config = hg_util.get_config_from_disk( 'agent_dependencies.xml', install_dir )
                itdm = InstallAgentDependencyManager( self.app )
                itdm.install_specified_agent_dependencies( agent_shed_repository=agent_shed_repository,
                                                          agent_dependencies_config=agent_dependencies_config,
                                                          agent_dependencies=agent_shed_repository.agent_dependencies,
                                                          from_agent_migration_manager=False )
                basic_util.remove_dir( work_dir )
            self.update_agent_shed_repository_status( agent_shed_repository,
                                                     self.install_model.AgentShedRepository.installation_status.INSTALLED )
            if self.app.config.manage_dependency_relationships:
                # Add the installed repository and any agent dependencies to the in-memory dictionaries
                # in the installed_repository_manager.
                self.app.installed_repository_manager.handle_repository_install( agent_shed_repository )
        else:
            # An error occurred while cloning the repository, so reset everything necessary to enable another attempt.
            suc.set_repository_attributes( self.app,
                                           agent_shed_repository,
                                           status=self.install_model.AgentShedRepository.installation_status.ERROR,
                                           error_message=error_message,
                                           deleted=False,
                                           uninstalled=False,
                                           remove_from_disk=True )

    def order_components_for_installation( self, tsr_ids, repo_info_dicts, agent_panel_section_keys ):
        """
        Some repositories may have repository dependencies that are required to be installed
        before the dependent repository.  This method will inspect the list of repositories
        about to be installed and make sure to order them appropriately.  For each repository
        about to be installed, if required repositories are not contained in the list of repositories
        about to be installed, then they are not considered.  Repository dependency definitions
        that contain circular dependencies should not result in an infinite loop, but obviously
        prior installation will not be handled for one or more of the repositories that require
        prior installation.
        """
        ordered_tsr_ids = []
        ordered_repo_info_dicts = []
        ordered_agent_panel_section_keys = []
        # Create a dictionary whose keys are the received tsr_ids and whose values are a list of
        # tsr_ids, each of which is contained in the received list of tsr_ids and whose associated
        # repository must be installed prior to the repository associated with the tsr_id key.
        prior_install_required_dict = suc.get_prior_import_or_install_required_dict( self.app,
                                                                                     tsr_ids,
                                                                                     repo_info_dicts )
        processed_tsr_ids = []
        while len( processed_tsr_ids ) != len( prior_install_required_dict.keys() ):
            tsr_id = suc.get_next_prior_import_or_install_required_dict_entry( prior_install_required_dict,
                                                                               processed_tsr_ids )
            processed_tsr_ids.append( tsr_id )
            # Create the ordered_tsr_ids, the ordered_repo_info_dicts and the ordered_agent_panel_section_keys lists.
            if tsr_id not in ordered_tsr_ids:
                prior_install_required_ids = prior_install_required_dict[ tsr_id ]
                for prior_install_required_id in prior_install_required_ids:
                    if prior_install_required_id not in ordered_tsr_ids:
                        # Install the associated repository dependency first.
                        prior_repo_info_dict, prior_agent_panel_section_key = \
                            self.get_repository_components_for_installation( prior_install_required_id,
                                                                             tsr_ids,
                                                                             repo_info_dicts,
                                                                             agent_panel_section_keys=agent_panel_section_keys )
                        ordered_tsr_ids.append( prior_install_required_id )
                        ordered_repo_info_dicts.append( prior_repo_info_dict )
                        ordered_agent_panel_section_keys.append( prior_agent_panel_section_key )
                repo_info_dict, agent_panel_section_key = \
                    self.get_repository_components_for_installation( tsr_id,
                                                                     tsr_ids,
                                                                     repo_info_dicts,
                                                                     agent_panel_section_keys=agent_panel_section_keys )
                if tsr_id not in ordered_tsr_ids:
                    ordered_tsr_ids.append( tsr_id )
                    ordered_repo_info_dicts.append( repo_info_dict )
                    ordered_agent_panel_section_keys.append( agent_panel_section_key )
        return ordered_tsr_ids, ordered_repo_info_dicts, ordered_agent_panel_section_keys

    def update_agent_shed_repository_status( self, agent_shed_repository, status, error_message=None ):
        """
        Update the status of a agent shed repository in the process of being installed into Galaxy.
        """
        agent_shed_repository.status = status
        if error_message:
            agent_shed_repository.error_message = str( error_message )
        self.install_model.context.add( agent_shed_repository )
        self.install_model.context.flush()

    def __assert_can_install_dependencies(self):
        if self.app.config.agent_dependency_dir is None:
            no_agent_dependency_dir_message = "Agent dependencies can be automatically installed only if you set "
            no_agent_dependency_dir_message += "the value of your 'agent_dependency_dir' setting in your Galaxy "
            no_agent_dependency_dir_message += "configuration file (galaxy.ini) and restart your Galaxy server.  "
            raise exceptions.ConfigDoesNotAllowException( no_agent_dependency_dir_message )


class RepositoriesInstalledException(exceptions.RequestParameterInvalidException):

    def __init__(self):
        super(RepositoriesInstalledException, self).__init__('All repositories that you are attempting to install have been previously installed.')


def fetch_agent_versions( app, agent_shed_repository ):
    """ Fetch a data structure describing agent shed versions from the agent shed
    corresponding to a agent_shed_repository object.
    """
    failed_to_fetch = False
    try:
        agent_shed_url = common_util.get_agent_shed_url_from_agent_shed_registry( app, str( agent_shed_repository.agent_shed ) )
        params = dict( name=str( agent_shed_repository.name ),
                       owner=str( agent_shed_repository.owner ),
                       changeset_revision=str( agent_shed_repository.changeset_revision ) )
        pathspec = [ 'repository', 'get_agent_versions' ]
        url = common_util.url_join( agent_shed_url, pathspec=pathspec, params=params )
        text = common_util.agent_shed_get( app, agent_shed_url, pathspec=pathspec, params=params )
        if text:
            return json.loads( text )
        else:
            log.error("No content returned from agent shed repository version request to %s", url)
            failed_to_fetch = True
    except Exception:
        failed_to_fetch = True
        log.exception("Failed to fetch agent shed repository version information.")
    if failed_to_fetch:
        return FAILED_TO_FETCH_VERSIONS
