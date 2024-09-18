from time import gmtime
from time import strftime


class ShedCounter( object ):
    def __init__( self, model ):
        # TODO: Enhance the ShedCounter to retrieve information from the db instead of displaying what's currently in memory.
        self.model = model
        self.custom_datatypes = 0
        self.generation_time = strftime( "%b %d, %Y", gmtime() )
        self.deleted_repositories = 0
        self.deprecated_repositories = 0
        self.invalid_versions_of_agents = 0
        self.repositories = 0
        self.total_clones = 0
        self.valid_versions_of_agents = 0
        self.unique_owners = 0
        self.unique_valid_agents = 0
        self.workflows = 0
        self.generate_statistics()

    @property
    def sa_session( self ):
        """Returns a SQLAlchemy session"""
        return self.model.context

    def generate_statistics( self ):
        self.custom_datatypes = 0
        self.deleted_repositories = 0
        self.deprecated_repositories = 0
        self.invalid_versions_of_agents = 0
        self.repositories = 0
        self.total_clones = 0
        self.unique_owners = 0
        self.valid_versions_of_agents = 0
        self.unique_valid_agents = 0
        self.workflows = 0
        unique_user_ids = []
        for repository in self.sa_session.query( self.model.Repository ):
            self.repositories += 1
            self.total_clones += repository.times_downloaded
            is_deleted = repository.deleted
            if is_deleted:
                self.deleted_repositories += 1
            else:
                if repository.deprecated:
                    self.deprecated_repositories += 1
                if repository.user_id not in unique_user_ids:
                    self.unique_owners += 1
                    unique_user_ids.append( repository.user_id )
                processed_datatypes = []
                processed_guids = []
                processed_invalid_agent_configs = []
                processed_relative_workflow_paths = []
                processed_agent_ids = []
                # A repository's metadata_revisions are those that ignore the value of the
                # repository_metadata.downloadable column.
                for metadata_revision in repository.metadata_revisions:
                    metadata = metadata_revision.metadata
                    if 'agents' in metadata:
                        agent_dicts = metadata[ 'agents' ]
                        for agent_dict in agent_dicts:
                            if 'guid' in agent_dict:
                                guid = agent_dict[ 'guid' ]
                                if guid not in processed_guids:
                                    self.valid_versions_of_agents += 1
                                    processed_guids.append( guid )
                            if 'id' in agent_dict:
                                agent_id = agent_dict[ 'id' ]
                                if agent_id not in processed_agent_ids:
                                    self.unique_valid_agents += 1
                                    processed_agent_ids.append( agent_id )
                    if 'invalid_agents' in metadata:
                        invalid_agent_configs = metadata[ 'invalid_agents' ]
                        for invalid_agent_config in invalid_agent_configs:
                            if invalid_agent_config not in processed_invalid_agent_configs:
                                self.invalid_versions_of_agents += 1
                                processed_invalid_agent_configs.append( invalid_agent_config )
                    if 'datatypes' in metadata:
                        datatypes = metadata[ 'datatypes' ]
                        for datatypes_dict in datatypes:
                            if 'extension' in datatypes_dict:
                                extension = datatypes_dict[ 'extension' ]
                                if extension not in processed_datatypes:
                                    self.custom_datatypes += 1
                                    processed_datatypes.append( extension )
                    if 'workflows' in metadata:
                        workflows = metadata[ 'workflows' ]
                        for workflow_tup in workflows:
                            relative_path, exported_workflow_dict = workflow_tup
                            if relative_path not in processed_relative_workflow_paths:
                                self.workflows += 1
                                processed_relative_workflow_paths.append( relative_path )
        self.generation_time = strftime( "%b %d, %Y", gmtime() )
