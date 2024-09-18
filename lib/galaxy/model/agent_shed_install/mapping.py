from galaxy.model import agent_shed_install as install_model
from sqlalchemy import MetaData
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table, TEXT
from sqlalchemy.orm import relation, mapper
from galaxy.model.custom_types import JSONType, TrimmedString
from galaxy.model.orm.now import now
from galaxy.model.base import ModelMapping
from galaxy.model.orm.engine_factory import build_engine

metadata = MetaData()

install_model.AgentShedRepository.table = Table( "agent_shed_repository", metadata,
                                                Column( "id", Integer, primary_key=True ),
                                                Column( "create_time", DateTime, default=now ),
                                                Column( "update_time", DateTime, default=now, onupdate=now ),
                                                Column( "agent_shed", TrimmedString( 255 ), index=True ),
                                                Column( "name", TrimmedString( 255 ), index=True ),
                                                Column( "description" , TEXT ),
                                                Column( "owner", TrimmedString( 255 ), index=True ),
                                                Column( "installed_changeset_revision", TrimmedString( 255 ) ),
                                                Column( "changeset_revision", TrimmedString( 255 ), index=True ),
                                                Column( "ctx_rev", TrimmedString( 10 ) ),
                                                Column( "metadata", JSONType, nullable=True ),
                                                Column( "includes_datatypes", Boolean, index=True, default=False ),
                                                Column( "agent_shed_status", JSONType, nullable=True ),
                                                Column( "deleted", Boolean, index=True, default=False ),
                                                Column( "uninstalled", Boolean, default=False ),
                                                Column( "dist_to_shed", Boolean, default=False ),
                                                Column( "status", TrimmedString( 255 ) ),
                                                Column( "error_message", TEXT ) )

install_model.RepositoryRepositoryDependencyAssociation.table = Table( 'repository_repository_dependency_association', metadata,
                                                                       Column( "id", Integer, primary_key=True ),
                                                                       Column( "create_time", DateTime, default=now ),
                                                                       Column( "update_time", DateTime, default=now, onupdate=now ),
                                                                       Column( "agent_shed_repository_id", Integer, ForeignKey( "agent_shed_repository.id" ), index=True ),
                                                                       Column( "repository_dependency_id", Integer, ForeignKey( "repository_dependency.id" ), index=True ) )

install_model.RepositoryDependency.table = Table( "repository_dependency", metadata,
                                                  Column( "id", Integer, primary_key=True ),
                                                  Column( "create_time", DateTime, default=now ),
                                                  Column( "update_time", DateTime, default=now, onupdate=now ),
                                                  Column( "agent_shed_repository_id", Integer, ForeignKey( "agent_shed_repository.id" ), index=True, nullable=False ) )

install_model.AgentDependency.table = Table( "agent_dependency", metadata,
                                            Column( "id", Integer, primary_key=True ),
                                            Column( "create_time", DateTime, default=now ),
                                            Column( "update_time", DateTime, default=now, onupdate=now ),
                                            Column( "agent_shed_repository_id", Integer, ForeignKey( "agent_shed_repository.id" ), index=True, nullable=False ),
                                            Column( "name", TrimmedString( 255 ) ),
                                            Column( "version", TEXT ),
                                            Column( "type", TrimmedString( 40 ) ),
                                            Column( "status", TrimmedString( 255 ), nullable=False ),
                                            Column( "error_message", TEXT ) )

install_model.AgentVersion.table = Table( "agent_version", metadata,
                                         Column( "id", Integer, primary_key=True ),
                                         Column( "create_time", DateTime, default=now ),
                                         Column( "update_time", DateTime, default=now, onupdate=now ),
                                         Column( "agent_id", String( 255 ) ),
                                         Column( "agent_shed_repository_id", Integer, ForeignKey( "agent_shed_repository.id" ), index=True, nullable=True ) )

install_model.AgentVersionAssociation.table = Table( "agent_version_association", metadata,
                                                    Column( "id", Integer, primary_key=True ),
                                                    Column( "agent_id", Integer, ForeignKey( "agent_version.id" ), index=True, nullable=False ),
                                                    Column( "parent_id", Integer, ForeignKey( "agent_version.id" ), index=True, nullable=False ) )

install_model.MigrateAgents.table = Table( "migrate_agents", metadata,
                                          Column( "repository_id", TrimmedString( 255 ) ),
                                          Column( "repository_path", TEXT ),
                                          Column( "version", Integer ) )

mapper( install_model.AgentShedRepository, install_model.AgentShedRepository.table,
        properties=dict( agent_versions=relation( install_model.AgentVersion,
                                                 primaryjoin=( install_model.AgentShedRepository.table.c.id == install_model.AgentVersion.table.c.agent_shed_repository_id ),
                                                 backref='agent_shed_repository' ),
                         agent_dependencies=relation( install_model.AgentDependency,
                                                     primaryjoin=( install_model.AgentShedRepository.table.c.id == install_model.AgentDependency.table.c.agent_shed_repository_id ),
                                                     order_by=install_model.AgentDependency.table.c.name,
                                                     backref='agent_shed_repository' ),
                         required_repositories=relation( install_model.RepositoryRepositoryDependencyAssociation,
                                                         primaryjoin=( install_model.AgentShedRepository.table.c.id == install_model.RepositoryRepositoryDependencyAssociation.table.c.agent_shed_repository_id ) ) ) )

mapper( install_model.RepositoryRepositoryDependencyAssociation, install_model.RepositoryRepositoryDependencyAssociation.table,
        properties=dict( repository=relation( install_model.AgentShedRepository,
                                              primaryjoin=( install_model.RepositoryRepositoryDependencyAssociation.table.c.agent_shed_repository_id == install_model.AgentShedRepository.table.c.id ) ),
                         repository_dependency=relation( install_model.RepositoryDependency,
                                                         primaryjoin=( install_model.RepositoryRepositoryDependencyAssociation.table.c.repository_dependency_id == install_model.RepositoryDependency.table.c.id ) ) ) )

mapper( install_model.RepositoryDependency, install_model.RepositoryDependency.table,
        properties=dict( repository=relation( install_model.AgentShedRepository,
                                              primaryjoin=( install_model.RepositoryDependency.table.c.agent_shed_repository_id == install_model.AgentShedRepository.table.c.id ) ) ) )

mapper( install_model.AgentDependency, install_model.AgentDependency.table )

mapper( install_model.AgentVersion, install_model.AgentVersion.table,
        properties=dict(
            parent_agent_association=relation( install_model.AgentVersionAssociation,
                                              primaryjoin=( install_model.AgentVersion.table.c.id == install_model.AgentVersionAssociation.table.c.agent_id ) ),
            child_agent_association=relation( install_model.AgentVersionAssociation,
                                             primaryjoin=( install_model.AgentVersion.table.c.id == install_model.AgentVersionAssociation.table.c.parent_id ) ) ) )

mapper( install_model.AgentVersionAssociation, install_model.AgentVersionAssociation.table )


def init( url, engine_options={}, create_tables=False ):
    """Connect mappings to the database"""
    # Load the appropriate db module
    engine = build_engine( url, engine_options )
    # Connect the metadata to the database.
    metadata.bind = engine
    result = ModelMapping( [ install_model ], engine=engine )
    # Create tables if needed
    if create_tables:
        metadata.create_all()
        # metadata.engine.commit()
    result.create_tables = create_tables
    # load local galaxy security policy
    return result
