import json
import logging
import os
import threading

from galaxy import util
from agent_shed.galaxy_install.utility_containers import GalaxyUtilityContainerManager
from agent_shed.util import common_util, container_util, readme_util
from agent_shed.util import shed_util_common as suc, agent_dependency_util
from agent_shed.utility_containers import utility_container_manager

log = logging.getLogger( __name__ )


class DependencyDisplayer( object ):

    def __init__( self, app ):
        self.app = app

    def add_installation_directories_to_agent_dependencies( self, agent_dependencies ):
        """
        Determine the path to the installation directory for each of the received
        agent dependencies.  This path will be displayed within the agent dependencies
        container on the select_agent_panel_section or reselect_agent_panel_section
        pages when installing or reinstalling repositories that contain agents with
        the defined agent dependencies.  The list of agent dependencies may be associated
        with more than a single repository.
        """
        for dependency_key, requirements_dict in agent_dependencies.items():
            if dependency_key in [ 'set_environment' ]:
                continue
            repository_name = requirements_dict.get( 'repository_name', 'unknown' )
            repository_owner = requirements_dict.get( 'repository_owner', 'unknown' )
            changeset_revision = requirements_dict.get( 'changeset_revision', 'unknown' )
            dependency_name = requirements_dict[ 'name' ]
            version = requirements_dict[ 'version' ]
            if self.app.config.agent_dependency_dir:
                root_dir = self.app.config.agent_dependency_dir
            else:
                root_dir = '<set your agent_dependency_dir in your Galaxy configuration file>'
            install_dir = os.path.join( root_dir,
                                        dependency_name,
                                        version,
                                        repository_owner,
                                        repository_name,
                                        changeset_revision )
            requirements_dict[ 'install_dir' ] = install_dir
            agent_dependencies[ dependency_key ] = requirements_dict
        return agent_dependencies

    def generate_message_for_invalid_repository_dependencies( self, metadata_dict, error_from_tuple=False ):
        """
        Get or generate and return an error message associated with an invalid repository dependency.
        """
        message = ''
        if metadata_dict:
            if error_from_tuple:
                # Return the error messages associated with a set of one or more invalid repository
                # dependency tuples.
                invalid_repository_dependencies_dict = metadata_dict.get( 'invalid_repository_dependencies', None )
                if invalid_repository_dependencies_dict is not None:
                    invalid_repository_dependencies = \
                        invalid_repository_dependencies_dict.get( 'invalid_repository_dependencies', [] )
                    for repository_dependency_tup in invalid_repository_dependencies:
                        agentshed, name, owner, changeset_revision, \
                            prior_installation_required, \
                            only_if_compiling_contained_td, error = \
                            common_util.parse_repository_dependency_tuple( repository_dependency_tup, contains_error=True )
                        if error:
                            message += '%s  ' % str( error )
            else:
                # The complete dependency hierarchy could not be determined for a repository being installed into
                # Galaxy.  This is likely due to invalid repository dependency definitions, so we'll get them from
                # the metadata and parse them for display in an error message.  This will hopefully communicate the
                # problem to the user in such a way that a resolution can be determined.
                message += 'The complete dependency hierarchy could not be determined for this repository, so no required '
                message += 'repositories will not be installed.  This is likely due to invalid repository dependency definitions.  '
                repository_dependencies_dict = metadata_dict.get( 'repository_dependencies', None )
                if repository_dependencies_dict is not None:
                    rd_tups = repository_dependencies_dict.get( 'repository_dependencies', None )
                    if rd_tups is not None:
                        message += 'Here are the attributes of the dependencies defined for this repository to help determine the '
                        message += 'cause of this problem.<br/>'
                        message += '<table cellpadding="2" cellspacing="2">'
                        message += '<tr><th>Agent shed</th><th>Repository name</th><th>Owner</th><th>Changeset revision</th>'
                        message += '<th>Prior install required</th></tr>'
                        for rd_tup in rd_tups:
                            agent_shed, name, owner, changeset_revision, pir, oicct = \
                                common_util.parse_repository_dependency_tuple( rd_tup )
                            if util.asbool( pir ):
                                pir_str = 'True'
                            else:
                                pir_str = ''
                            message += '<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % \
                                ( agent_shed, name, owner, changeset_revision, pir_str )
                        message += '</table>'
        return message

    def generate_message_for_invalid_agent_dependencies( self, metadata_dict ):
        """
        Agent dependency definitions can only be invalid if they include a definition for a complex
        repository dependency and the repository dependency definition is invalid.  This method
        retrieves the error message associated with the invalid agent dependency for display in the
        caller.
        """
        message = ''
        if metadata_dict:
            invalid_agent_dependencies = metadata_dict.get( 'invalid_agent_dependencies', None )
            if invalid_agent_dependencies:
                for td_key, requirement_dict in invalid_agent_dependencies.items():
                    error = requirement_dict.get( 'error', None )
                    if error:
                        message = '%s  ' % str( error )
        return message

    def generate_message_for_orphan_agent_dependencies( self, repository, metadata_dict ):
        """
        The designation of a AgentDependency into the "orphan" category has evolved over time,
        and is significantly restricted since the introduction of the TOOL_DEPENDENCY_DEFINITION
        repository type.  This designation is still critical, however, in that it handles the
        case where a repository contains both agents and a agent_dependencies.xml file, but the
        definition in the agent_dependencies.xml file is in no way related to anything defined
        by any of the contained agent's requirements tag sets.  This is important in that it is
        often a result of a typo (e.g., dependency name or version) that differs between the agent
        dependency definition within the agent_dependencies.xml file and what is defined in the
        agent config's <requirements> tag sets.  In these cases, the user should be presented with
        a warning message, and this warning message is is in fact displayed if the following
        is_orphan attribute is True.  This is tricky because in some cases it may be intentional,
        and agent dependencies that are categorized as "orphan" are in fact valid.
        """
        has_orphan_package_dependencies = False
        has_orphan_set_environment_dependencies = False
        message = ''
        package_orphans_str = ''
        set_environment_orphans_str = ''
        # Agent dependencies are categorized as orphan only if the repository contains agents.
        if metadata_dict:
            agents = metadata_dict.get( 'agents', [] )
            agent_dependencies = metadata_dict.get( 'agent_dependencies', {} )
            # The use of the orphan_agent_dependencies category in metadata has been deprecated,
            # but we still need to check in case the metadata is out of date.
            orphan_agent_dependencies = metadata_dict.get( 'orphan_agent_dependencies', {} )
            # Updating should cause no problems here since a agent dependency cannot be included
            # in both dictionaries.
            agent_dependencies.update( orphan_agent_dependencies )
            if agent_dependencies and agents:
                for td_key, requirements_dict in agent_dependencies.items():
                    if td_key == 'set_environment':
                        # "set_environment": [{"name": "R_SCRIPT_PATH", "type": "set_environment"}]
                        for env_requirements_dict in requirements_dict:
                            name = env_requirements_dict[ 'name' ]
                            type = env_requirements_dict[ 'type' ]
                            if self.agent_dependency_is_orphan( type, name, None, agents ):
                                if not has_orphan_set_environment_dependencies:
                                    has_orphan_set_environment_dependencies = True
                                set_environment_orphans_str += "<b>* name:</b> %s, <b>type:</b> %s<br/>" % \
                                    ( str( name ), str( type ) )
                    else:
                        # "R/2.15.1": {"name": "R", "readme": "some string", "type": "package", "version": "2.15.1"}
                        name = requirements_dict[ 'name' ]
                        type = requirements_dict[ 'type' ]
                        version = requirements_dict[ 'version' ]
                        if self.agent_dependency_is_orphan( type, name, version, agents ):
                            if not has_orphan_package_dependencies:
                                has_orphan_package_dependencies = True
                            package_orphans_str += "<b>* name:</b> %s, <b>type:</b> %s, <b>version:</b> %s<br/>" % \
                                ( str( name ), str( type ), str( version ) )
        if has_orphan_package_dependencies:
            message += "The settings for <b>name</b>, <b>version</b> and <b>type</b> from a "
            message += "contained agent configuration file's <b>requirement</b> tag does not match "
            message += "the information for the following agent dependency definitions in the "
            message += "<b>agent_dependencies.xml</b> file, so these agent dependencies have no "
            message += "relationship with any agents within this repository.<br/>"
            message += package_orphans_str
        if has_orphan_set_environment_dependencies:
            message += "The settings for <b>name</b> and <b>type</b> from a contained agent "
            message += "configuration file's <b>requirement</b> tag does not match the information "
            message += "for the following agent dependency definitions in the <b>agent_dependencies.xml</b> "
            message += "file, so these agent dependencies have no relationship with any agents within "
            message += "this repository.<br/>"
            message += set_environment_orphans_str
        return message

    def get_installed_and_missing_agent_dependencies_for_installed_repository( self, repository, all_agent_dependencies ):
        """
        Return the lists of installed agent dependencies and missing agent dependencies for a Agent Shed
        repository that has been installed into Galaxy.
        """
        if all_agent_dependencies:
            agent_dependencies = {}
            missing_agent_dependencies = {}
            for td_key, val in all_agent_dependencies.items():
                if td_key in [ 'set_environment' ]:
                    for index, td_info_dict in enumerate( val ):
                        name = td_info_dict[ 'name' ]
                        version = None
                        type = td_info_dict[ 'type' ]
                        agent_dependency = agent_dependency_util.get_agent_dependency_by_name_type_repository( self.app,
                                                                                                            repository,
                                                                                                            name,
                                                                                                            type )
                        if agent_dependency:
                            td_info_dict[ 'repository_id' ] = repository.id
                            td_info_dict[ 'agent_dependency_id' ] = agent_dependency.id
                            if agent_dependency.status:
                                agent_dependency_status = str( agent_dependency.status )
                            else:
                                agent_dependency_status = 'Never installed'
                            td_info_dict[ 'status' ] = agent_dependency_status
                            val[ index ] = td_info_dict
                            if agent_dependency.status == self.app.install_model.AgentDependency.installation_status.INSTALLED:
                                agent_dependencies[ td_key ] = val
                            else:
                                missing_agent_dependencies[ td_key ] = val
                else:
                    name = val[ 'name' ]
                    version = val[ 'version' ]
                    type = val[ 'type' ]
                    agent_dependency = agent_dependency_util.get_agent_dependency_by_name_version_type_repository( self.app,
                                                                                                                repository,
                                                                                                                name,
                                                                                                                version,
                                                                                                                type )
                    if agent_dependency:
                        val[ 'repository_id' ] = repository.id
                        val[ 'agent_dependency_id' ] = agent_dependency.id
                        if agent_dependency.status:
                            agent_dependency_status = str( agent_dependency.status )
                        else:
                            agent_dependency_status = 'Never installed'
                        val[ 'status' ] = agent_dependency_status
                        if agent_dependency.status == self.app.install_model.AgentDependency.installation_status.INSTALLED:
                            agent_dependencies[ td_key ] = val
                        else:
                            missing_agent_dependencies[ td_key ] = val
        else:
            agent_dependencies = None
            missing_agent_dependencies = None
        return agent_dependencies, missing_agent_dependencies

    def merge_containers_dicts_for_new_install( self, containers_dicts ):
        """
        When installing one or more agent shed repositories for the first time, the received list of
        containers_dicts contains a containers_dict for each repository being installed.  Since the
        repositories are being installed for the first time, all entries are None except the repository
        dependencies and agent dependencies.  The entries for missing dependencies are all None since
        they have previously been merged into the installed dependencies.  This method will merge the
        dependencies entries into a single container and return it for display.
        """
        new_containers_dict = dict( readme_files=None,
                                    datatypes=None,
                                    missing_repository_dependencies=None,
                                    repository_dependencies=None,
                                    missing_agent_dependencies=None,
                                    agent_dependencies=None,
                                    invalid_agents=None,
                                    valid_agents=None,
                                    workflows=None )
        if containers_dicts:
            lock = threading.Lock()
            lock.acquire( True )
            try:
                repository_dependencies_root_folder = None
                agent_dependencies_root_folder = None
                # Use a unique folder id (hopefully the following is).
                folder_id = 867
                for old_container_dict in containers_dicts:
                    # Merge repository_dependencies.
                    old_container_repository_dependencies_root = old_container_dict[ 'repository_dependencies' ]
                    if old_container_repository_dependencies_root:
                        if repository_dependencies_root_folder is None:
                            repository_dependencies_root_folder = utility_container_manager.Folder( id=folder_id,
                                                                                                    key='root',
                                                                                                    label='root',
                                                                                                    parent=None )
                            folder_id += 1
                            repository_dependencies_folder = utility_container_manager.Folder( id=folder_id,
                                                                                               key='merged',
                                                                                               label='Repository dependencies',
                                                                                               parent=repository_dependencies_root_folder )
                            folder_id += 1
                        # The old_container_repository_dependencies_root will be a root folder containing a single sub_folder.
                        old_container_repository_dependencies_folder = old_container_repository_dependencies_root.folders[ 0 ]
                        # Change the folder id so it won't confict with others being merged.
                        old_container_repository_dependencies_folder.id = folder_id
                        folder_id += 1
                        repository_components_tuple = \
                            container_util.get_components_from_key( old_container_repository_dependencies_folder.key )
                        components_list = suc.extract_components_from_tuple( repository_components_tuple )
                        name = components_list[ 1 ]
                        # Generate the label by retrieving the repository name.
                        old_container_repository_dependencies_folder.label = str( name )
                        repository_dependencies_folder.folders.append( old_container_repository_dependencies_folder )
                    # Merge agent_dependencies.
                    old_container_agent_dependencies_root = old_container_dict[ 'agent_dependencies' ]
                    if old_container_agent_dependencies_root:
                        if agent_dependencies_root_folder is None:
                            agent_dependencies_root_folder = utility_container_manager.Folder( id=folder_id,
                                                                                              key='root',
                                                                                              label='root',
                                                                                              parent=None )
                            folder_id += 1
                            agent_dependencies_folder = utility_container_manager.Folder( id=folder_id,
                                                                                         key='merged',
                                                                                         label='Agent dependencies',
                                                                                         parent=agent_dependencies_root_folder )
                            folder_id += 1
                        else:
                            td_list = [ td.listify for td in agent_dependencies_folder.agent_dependencies ]
                            # The old_container_agent_dependencies_root will be a root folder containing a single sub_folder.
                            old_container_agent_dependencies_folder = old_container_agent_dependencies_root.folders[ 0 ]
                            for td in old_container_agent_dependencies_folder.agent_dependencies:
                                if td.listify not in td_list:
                                    agent_dependencies_folder.agent_dependencies.append( td )
                if repository_dependencies_root_folder:
                    repository_dependencies_root_folder.folders.append( repository_dependencies_folder )
                    new_containers_dict[ 'repository_dependencies' ] = repository_dependencies_root_folder
                if agent_dependencies_root_folder:
                    agent_dependencies_root_folder.folders.append( agent_dependencies_folder )
                    new_containers_dict[ 'agent_dependencies' ] = agent_dependencies_root_folder
            except Exception, e:
                log.debug( "Exception in merge_containers_dicts_for_new_install: %s" % str( e ) )
            finally:
                lock.release()
        return new_containers_dict

    def merge_missing_repository_dependencies_to_installed_container( self, containers_dict ):
        """
        Merge the list of missing repository dependencies into the list of installed
        repository dependencies.
        """
        missing_rd_container_root = containers_dict.get( 'missing_repository_dependencies', None )
        if missing_rd_container_root:
            # The missing_rd_container_root will be a root folder containing a single sub_folder.
            missing_rd_container = missing_rd_container_root.folders[ 0 ]
            installed_rd_container_root = containers_dict.get( 'repository_dependencies', None )
            # The installed_rd_container_root will be a root folder containing a single sub_folder.
            if installed_rd_container_root:
                installed_rd_container = installed_rd_container_root.folders[ 0 ]
                installed_rd_container.label = 'Repository dependencies'
                for index, rd in enumerate( missing_rd_container.repository_dependencies ):
                    # Skip the header row.
                    if index == 0:
                        continue
                    installed_rd_container.repository_dependencies.append( rd )
                installed_rd_container_root.folders = [ installed_rd_container ]
                containers_dict[ 'repository_dependencies' ] = installed_rd_container_root
            else:
                # Change the folder label from 'Missing repository dependencies' to be
                # 'Repository dependencies' for display.
                root_container = containers_dict[ 'missing_repository_dependencies' ]
                for sub_container in root_container.folders:
                    # There should only be 1 sub-folder.
                    sub_container.label = 'Repository dependencies'
                containers_dict[ 'repository_dependencies' ] = root_container
        containers_dict[ 'missing_repository_dependencies' ] = None
        return containers_dict

    def merge_missing_agent_dependencies_to_installed_container( self, containers_dict ):
        """
        Merge the list of missing agent dependencies into the list of installed agent
        dependencies.
        """
        missing_td_container_root = containers_dict.get( 'missing_agent_dependencies', None )
        if missing_td_container_root:
            # The missing_td_container_root will be a root folder containing a single sub_folder.
            missing_td_container = missing_td_container_root.folders[ 0 ]
            installed_td_container_root = containers_dict.get( 'agent_dependencies', None )
            # The installed_td_container_root will be a root folder containing a single sub_folder.
            if installed_td_container_root:
                installed_td_container = installed_td_container_root.folders[ 0 ]
                installed_td_container.label = 'Agent dependencies'
                for index, td in enumerate( missing_td_container.agent_dependencies ):
                    # Skip the header row.
                    if index == 0:
                        continue
                    installed_td_container.agent_dependencies.append( td )
                installed_td_container_root.folders = [ installed_td_container ]
                containers_dict[ 'agent_dependencies' ] = installed_td_container_root
            else:
                # Change the folder label from 'Missing agent dependencies' to be
                # 'Agent dependencies' for display.
                root_container = containers_dict[ 'missing_agent_dependencies' ]
                for sub_container in root_container.folders:
                    # There should only be 1 subfolder.
                    sub_container.label = 'Agent dependencies'
                containers_dict[ 'agent_dependencies' ] = root_container
        containers_dict[ 'missing_agent_dependencies' ] = None
        return containers_dict

    def populate_containers_dict_for_new_install( self, agent_shed_url, agent_path, readme_files_dict,
                                                  installed_repository_dependencies, missing_repository_dependencies,
                                                  installed_agent_dependencies, missing_agent_dependencies,
                                                  updating=False ):
        """
        Return the populated containers for a repository being installed for the first time
        or for an installed repository that is being updated and the updates include newly
        defined repository (and possibly agent) dependencies.
        """
        installed_agent_dependencies, missing_agent_dependencies = \
            self.populate_agent_dependencies_dicts( agent_shed_url=agent_shed_url,
                                                   agent_path=agent_path,
                                                   repository_installed_agent_dependencies=installed_agent_dependencies,
                                                   repository_missing_agent_dependencies=missing_agent_dependencies,
                                                   required_repo_info_dicts=None )
        # Most of the repository contents are set to None since we don't yet know what they are.
        gucm = GalaxyUtilityContainerManager( self.app )
        containers_dict = gucm.build_repository_containers( repository=None,
                                                            datatypes=None,
                                                            invalid_agents=None,
                                                            missing_repository_dependencies=missing_repository_dependencies,
                                                            missing_agent_dependencies=missing_agent_dependencies,
                                                            readme_files_dict=readme_files_dict,
                                                            repository_dependencies=installed_repository_dependencies,
                                                            agent_dependencies=installed_agent_dependencies,
                                                            valid_agents=None,
                                                            workflows=None,
                                                            valid_data_managers=None,
                                                            invalid_data_managers=None,
                                                            data_managers_errors=None,
                                                            new_install=True,
                                                            reinstalling=False )
        if not updating:
            # If we installing a new repository and not updaing an installed repository, we can merge
            # the missing_repository_dependencies container contents to the installed_repository_dependencies
            # container.  When updating an installed repository, merging will result in losing newly defined
            # dependencies included in the updates.
            containers_dict = self.merge_missing_repository_dependencies_to_installed_container( containers_dict )
            # Merge the missing_agent_dependencies container contents to the installed_agent_dependencies container.
            containers_dict = self.merge_missing_agent_dependencies_to_installed_container( containers_dict )
        return containers_dict

    def populate_containers_dict_from_repository_metadata( self, agent_shed_url, agent_path, repository, reinstalling=False,
                                                           required_repo_info_dicts=None ):
        """
        Retrieve necessary information from the received repository's metadata to populate the
        containers_dict for display.  This method is called only from Galaxy (not the agent shed)
        when displaying repository dependencies for installed repositories and when displaying
        them for uninstalled repositories that are being reinstalled.
        """
        metadata = repository.metadata
        if metadata:
            # Handle proprietary datatypes.
            datatypes = metadata.get( 'datatypes', None )
            # Handle invalid agents.
            invalid_agents = metadata.get( 'invalid_agents', None )
            # Handle README files.
            if repository.has_readme_files:
                if reinstalling or repository.status not in \
                    [ self.app.install_model.AgentShedRepository.installation_status.DEACTIVATED,
                      self.app.install_model.AgentShedRepository.installation_status.INSTALLED ]:
                    # Since we're reinstalling, we need to send a request to the agent shed to get the README files.
                    agent_shed_url = common_util.get_agent_shed_url_from_agent_shed_registry( self.app, agent_shed_url )
                    params = dict( name=str( repository.name ),
                                   owner=str( repository.owner ),
                                   changeset_revision=str( repository.installed_changeset_revision ) )
                    pathspec = [ 'repository', 'get_readme_files' ]
                    raw_text = common_util.agent_shed_get( self.app, agent_shed_url, pathspec=pathspec, params=params )
                    readme_files_dict = json.loads( raw_text )
                else:
                    readme_files_dict = readme_util.build_readme_files_dict( self.app,
                                                                             repository,
                                                                             repository.changeset_revision,
                                                                             repository.metadata, agent_path )
            else:
                readme_files_dict = None
            # Handle repository dependencies.
            installed_repository_dependencies, missing_repository_dependencies = \
                self.app.installed_repository_manager.get_installed_and_missing_repository_dependencies( repository )
            # Handle the current repository's agent dependencies.
            repository_agent_dependencies = metadata.get( 'agent_dependencies', None )
            # Make sure to display missing agent dependencies as well.
            repository_invalid_agent_dependencies = metadata.get( 'invalid_agent_dependencies', None )
            if repository_invalid_agent_dependencies is not None:
                if repository_agent_dependencies is None:
                    repository_agent_dependencies = {}
                repository_agent_dependencies.update( repository_invalid_agent_dependencies )
            repository_installed_agent_dependencies, repository_missing_agent_dependencies = \
                self.get_installed_and_missing_agent_dependencies_for_installed_repository( repository,
                                                                                           repository_agent_dependencies )
            if reinstalling:
                installed_agent_dependencies, missing_agent_dependencies = \
                    self.populate_agent_dependencies_dicts( agent_shed_url,
                                                           agent_path,
                                                           repository_installed_agent_dependencies,
                                                           repository_missing_agent_dependencies,
                                                           required_repo_info_dicts )
            else:
                installed_agent_dependencies = repository_installed_agent_dependencies
                missing_agent_dependencies = repository_missing_agent_dependencies
            # Handle valid agents.
            valid_agents = metadata.get( 'agents', None )
            # Handle workflows.
            workflows = metadata.get( 'workflows', None )
            # Handle Data Managers
            valid_data_managers = None
            invalid_data_managers = None
            data_managers_errors = None
            if 'data_manager' in metadata:
                valid_data_managers = metadata['data_manager'].get( 'data_managers', None )
                invalid_data_managers = metadata['data_manager'].get( 'invalid_data_managers', None )
                data_managers_errors = metadata['data_manager'].get( 'messages', None )
            gucm = GalaxyUtilityContainerManager( self.app )
            containers_dict = gucm.build_repository_containers( repository=repository,
                                                                datatypes=datatypes,
                                                                invalid_agents=invalid_agents,
                                                                missing_repository_dependencies=missing_repository_dependencies,
                                                                missing_agent_dependencies=missing_agent_dependencies,
                                                                readme_files_dict=readme_files_dict,
                                                                repository_dependencies=installed_repository_dependencies,
                                                                agent_dependencies=installed_agent_dependencies,
                                                                valid_agents=valid_agents,
                                                                workflows=workflows,
                                                                valid_data_managers=valid_data_managers,
                                                                invalid_data_managers=invalid_data_managers,
                                                                data_managers_errors=data_managers_errors,
                                                                new_install=False,
                                                                reinstalling=reinstalling )
        else:
            containers_dict = dict( datatypes=None,
                                    invalid_agents=None,
                                    readme_files_dict=None,
                                    repository_dependencies=None,
                                    agent_dependencies=None,
                                    valid_agents=None,
                                    workflows=None )
        return containers_dict

    def populate_agent_dependencies_dicts( self, agent_shed_url, agent_path, repository_installed_agent_dependencies,
                                          repository_missing_agent_dependencies, required_repo_info_dicts ):
        """
        Return the populated installed_agent_dependencies and missing_agent_dependencies dictionaries
        for all repositories defined by entries in the received required_repo_info_dicts.
        """
        installed_agent_dependencies = None
        missing_agent_dependencies = None
        if repository_installed_agent_dependencies is None:
            repository_installed_agent_dependencies = {}
        else:
            # Add the install_dir attribute to the agent_dependencies.
            repository_installed_agent_dependencies = \
                self.add_installation_directories_to_agent_dependencies( repository_installed_agent_dependencies )
        if repository_missing_agent_dependencies is None:
            repository_missing_agent_dependencies = {}
        else:
            # Add the install_dir attribute to the agent_dependencies.
            repository_missing_agent_dependencies = \
                self.add_installation_directories_to_agent_dependencies( repository_missing_agent_dependencies )
        if required_repo_info_dicts:
            # Handle the agent dependencies defined for each of the repository's repository dependencies.
            for rid in required_repo_info_dicts:
                for name, repo_info_tuple in rid.items():
                    description, repository_clone_url, changeset_revision, \
                        ctx_rev, repository_owner, repository_dependencies, \
                        agent_dependencies = \
                        suc.get_repo_info_tuple_contents( repo_info_tuple )
                    if agent_dependencies:
                        # Add the install_dir attribute to the agent_dependencies.
                        agent_dependencies = self.add_installation_directories_to_agent_dependencies( agent_dependencies )
                        # The required_repository may have been installed with a different changeset revision.
                        required_repository, installed_changeset_revision = \
                            suc.repository_was_previously_installed( self.app,
                                                                     agent_shed_url,
                                                                     name,
                                                                     repo_info_tuple,
                                                                     from_tip=False )
                        if required_repository:
                            required_repository_installed_agent_dependencies, required_repository_missing_agent_dependencies = \
                                self.get_installed_and_missing_agent_dependencies_for_installed_repository( required_repository,
                                                                                                           agent_dependencies )
                            if required_repository_installed_agent_dependencies:
                                # Add the install_dir attribute to the agent_dependencies.
                                required_repository_installed_agent_dependencies = \
                                    self.add_installation_directories_to_agent_dependencies( required_repository_installed_agent_dependencies )
                                for td_key, td_dict in required_repository_installed_agent_dependencies.items():
                                    if td_key not in repository_installed_agent_dependencies:
                                        repository_installed_agent_dependencies[ td_key ] = td_dict
                            if required_repository_missing_agent_dependencies:
                                # Add the install_dir attribute to the agent_dependencies.
                                required_repository_missing_agent_dependencies = \
                                    self.add_installation_directories_to_agent_dependencies( required_repository_missing_agent_dependencies )
                                for td_key, td_dict in required_repository_missing_agent_dependencies.items():
                                    if td_key not in repository_missing_agent_dependencies:
                                        repository_missing_agent_dependencies[ td_key ] = td_dict
        if repository_installed_agent_dependencies:
            installed_agent_dependencies = repository_installed_agent_dependencies
        if repository_missing_agent_dependencies:
            missing_agent_dependencies = repository_missing_agent_dependencies
        return installed_agent_dependencies, missing_agent_dependencies

    def agent_dependency_is_orphan( self, type, name, version, agents ):
        """
        Determine if the combination of the received type, name and version is defined in the <requirement>
        tag for at least one agent in the received list of agents.  If not, the agent dependency defined by the
        combination is considered an orphan in its repository in the agent shed.
        """
        if type == 'package':
            if name and version:
                for agent_dict in agents:
                    requirements = agent_dict.get( 'requirements', [] )
                    for requirement_dict in requirements:
                        req_name = requirement_dict.get( 'name', None )
                        req_version = requirement_dict.get( 'version', None )
                        req_type = requirement_dict.get( 'type', None )
                        if req_name == name and req_version == version and req_type == type:
                            return False
        elif type == 'set_environment':
            if name:
                for agent_dict in agents:
                    requirements = agent_dict.get( 'requirements', [] )
                    for requirement_dict in requirements:
                        req_name = requirement_dict.get( 'name', None )
                        req_type = requirement_dict.get( 'type', None )
                        if req_name == name and req_type == type:
                            return False
        return True
