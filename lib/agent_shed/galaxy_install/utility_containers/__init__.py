import logging
import threading

from agent_shed.utility_containers import utility_container_manager

log = logging.getLogger( __name__ )


class GalaxyUtilityContainerManager( utility_container_manager.UtilityContainerManager ):

    def __init__( self, app ):
        self.app = app

    def build_repository_containers( self, repository, datatypes, invalid_agents, missing_repository_dependencies,
                                     missing_agent_dependencies, readme_files_dict, repository_dependencies,
                                     agent_dependencies, valid_agents, workflows, valid_data_managers,
                                     invalid_data_managers, data_managers_errors, new_install=False,
                                     reinstalling=False ):
        """
        Return a dictionary of containers for the received repository's dependencies and readme files for
        display during installation to Galaxy.
        """
        containers_dict = dict( datatypes=None,
                                invalid_agents=None,
                                missing_agent_dependencies=None,
                                readme_files=None,
                                repository_dependencies=None,
                                missing_repository_dependencies=None,
                                agent_dependencies=None,
                                valid_agents=None,
                                workflows=None,
                                valid_data_managers=None,
                                invalid_data_managers=None )
        # Some of the agent dependency folders will include links to display agent dependency information, and
        # some of these links require the repository id.  However we need to be careful because sometimes the
        # repository object is None.
        if repository:
            repository_id = repository.id
            changeset_revision = repository.changeset_revision
        else:
            repository_id = None
            changeset_revision = None
        lock = threading.Lock()
        lock.acquire( True )
        try:
            folder_id = 0
            # Datatypes container.
            if datatypes:
                folder_id, datatypes_root_folder = self.build_datatypes_folder( folder_id, datatypes )
                containers_dict[ 'datatypes' ] = datatypes_root_folder
            # Invalid agents container.
            if invalid_agents:
                folder_id, invalid_agents_root_folder = \
                    self.build_invalid_agents_folder( folder_id,
                                                     invalid_agents,
                                                     changeset_revision,
                                                     repository=repository,
                                                     label='Invalid agents' )
                containers_dict[ 'invalid_agents' ] = invalid_agents_root_folder
            # Readme files container.
            if readme_files_dict:
                folder_id, readme_files_root_folder = self.build_readme_files_folder( folder_id, readme_files_dict )
                containers_dict[ 'readme_files' ] = readme_files_root_folder
            # Installed repository dependencies container.
            if repository_dependencies:
                if new_install:
                    label = 'Repository dependencies'
                else:
                    label = 'Installed repository dependencies'
                folder_id, repository_dependencies_root_folder = \
                    self.build_repository_dependencies_folder( folder_id=folder_id,
                                                               repository_dependencies=repository_dependencies,
                                                               label=label,
                                                               installed=True )
                containers_dict[ 'repository_dependencies' ] = repository_dependencies_root_folder
            # Missing repository dependencies container.
            if missing_repository_dependencies:
                folder_id, missing_repository_dependencies_root_folder = \
                    self.build_repository_dependencies_folder( folder_id=folder_id,
                                                               repository_dependencies=missing_repository_dependencies,
                                                               label='Missing repository dependencies',
                                                               installed=False )
                containers_dict[ 'missing_repository_dependencies' ] = missing_repository_dependencies_root_folder
            # Installed agent dependencies container.
            if agent_dependencies:
                if new_install:
                    label = 'Agent dependencies'
                else:
                    label = 'Installed agent dependencies'
                # We only want to display the Status column if the agent_dependency is missing.
                folder_id, agent_dependencies_root_folder = \
                    self.build_agent_dependencies_folder( folder_id,
                                                         agent_dependencies,
                                                         label=label,
                                                         missing=False,
                                                         new_install=new_install,
                                                         reinstalling=reinstalling )
                containers_dict[ 'agent_dependencies' ] = agent_dependencies_root_folder
            # Missing agent dependencies container.
            if missing_agent_dependencies:
                # We only want to display the Status column if the agent_dependency is missing.
                folder_id, missing_agent_dependencies_root_folder = \
                    self.build_agent_dependencies_folder( folder_id,
                                                         missing_agent_dependencies,
                                                         label='Missing agent dependencies',
                                                         missing=True,
                                                         new_install=new_install,
                                                         reinstalling=reinstalling )
                containers_dict[ 'missing_agent_dependencies' ] = missing_agent_dependencies_root_folder
            # Valid agents container.
            if valid_agents:
                folder_id, valid_agents_root_folder = self.build_agents_folder( folder_id,
                                                                              valid_agents,
                                                                              repository,
                                                                              changeset_revision,
                                                                              label='Valid agents' )
                containers_dict[ 'valid_agents' ] = valid_agents_root_folder
            # Workflows container.
            if workflows:
                folder_id, workflows_root_folder = \
                    self.build_workflows_folder( folder_id=folder_id,
                                                 workflows=workflows,
                                                 repository_metadata_id=None,
                                                 repository_id=repository_id,
                                                 label='Workflows' )
                containers_dict[ 'workflows' ] = workflows_root_folder
            if valid_data_managers:
                folder_id, valid_data_managers_root_folder = \
                    self.build_data_managers_folder( folder_id=folder_id,
                                                     data_managers=valid_data_managers,
                                                     label='Valid Data Managers' )
                containers_dict[ 'valid_data_managers' ] = valid_data_managers_root_folder
            if invalid_data_managers or data_managers_errors:
                folder_id, invalid_data_managers_root_folder = \
                    self.build_invalid_data_managers_folder( folder_id=folder_id,
                                                             data_managers=invalid_data_managers,
                                                             error_messages=data_managers_errors,
                                                             label='Invalid Data Managers' )
                containers_dict[ 'invalid_data_managers' ] = invalid_data_managers_root_folder
        except Exception, e:
            log.debug( "Exception in build_repository_containers: %s" % str( e ) )
        finally:
            lock.release()
        return containers_dict
