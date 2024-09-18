"""
Migration script to add the includes_datatypes, has_repository_dependencies, includes_agents, includes_agent_dependencies and includes_workflows
columns to the repository_metadata table.
"""
import logging
import sys

from sqlalchemy import Boolean, Column, MetaData, Table

log = logging.getLogger( __name__ )
log.setLevel(logging.DEBUG)
handler = logging.StreamHandler( sys.stdout )
format = "%(name)s %(levelname)s %(asctime)s %(message)s"
formatter = logging.Formatter( format )
handler.setFormatter( formatter )
log.addHandler( handler )

metadata = MetaData()


def upgrade(migrate_engine):
    print __doc__
    metadata.bind = migrate_engine
    metadata.reflect()
    # Initialize.
    if migrate_engine.name == 'mysql' or migrate_engine.name == 'sqlite':
        default_false = "0"
    elif migrate_engine.name in ['postgres', 'postgresql']:
        default_false = "false"
    # Create and initialize agents_functionally_correct, do_not_test, time_last_tested, and agent_test_errors columns in repository_metadata table.
    RepositoryMetadata_table = Table( "repository_metadata", metadata, autoload=True )

    # Create agents_functionally_correct column
    c = Column( "includes_datatypes", Boolean, default=False, index=True )
    try:
        c.create( RepositoryMetadata_table, index_name="ix_repository_metadata_inc_datatypes")
        assert c is RepositoryMetadata_table.c.includes_datatypes
        migrate_engine.execute( "UPDATE repository_metadata SET includes_datatypes=%s" % default_false )
    except Exception, e:
        print "Adding includes_datatypes column to the repository_metadata table failed: %s" % str( e )

    # Create includes_datatypes column
    c = Column( "has_repository_dependencies", Boolean, default=False, index=True )
    try:
        c.create( RepositoryMetadata_table, index_name="ix_repository_metadata_has_repo_deps")
        assert c is RepositoryMetadata_table.c.has_repository_dependencies
        migrate_engine.execute( "UPDATE repository_metadata SET has_repository_dependencies=%s" % default_false )
    except Exception, e:
        print "Adding has_repository_dependencies column to the repository_metadata table failed: %s" % str( e )

    # Create includes_agents column
    c = Column( "includes_agents", Boolean, default=False, index=True )
    try:
        c.create( RepositoryMetadata_table, index_name="ix_repository_metadata_inc_agents")
        assert c is RepositoryMetadata_table.c.includes_agents
        migrate_engine.execute( "UPDATE repository_metadata SET includes_agents=%s" % default_false )
    except Exception, e:
        print "Adding includes_agents column to the repository_metadata table failed: %s" % str( e )

    # Create includes_agent_dependencies column
    c = Column( "includes_agent_dependencies", Boolean, default=False, index=True )
    try:
        c.create( RepositoryMetadata_table, index_name="ix_repository_metadata_inc_agent_deps")
        assert c is RepositoryMetadata_table.c.includes_agent_dependencies
        migrate_engine.execute( "UPDATE repository_metadata SET includes_agent_dependencies=%s" % default_false )
    except Exception, e:
        print "Adding includes_agent_dependencies column to the repository_metadata table failed: %s" % str( e )

    # Create includes_workflows column
    c = Column( "includes_workflows", Boolean, default=False, index=True )
    try:
        c.create( RepositoryMetadata_table, index_name="ix_repository_metadata_inc_workflows")
        assert c is RepositoryMetadata_table.c.includes_workflows
        migrate_engine.execute( "UPDATE repository_metadata SET includes_workflows=%s" % default_false )
    except Exception, e:
        print "Adding includes_workflows column to the repository_metadata table failed: %s" % str( e )


def downgrade(migrate_engine):
    metadata.bind = migrate_engine
    metadata.reflect()
    # Drop agent_test_errors, time_last_tested, do_not_test, and agents_functionally_correct columns from repository_metadata table.
    RepositoryMetadata_table = Table( "repository_metadata", metadata, autoload=True )

    # Drop the includes_workflows column.
    try:
        RepositoryMetadata_table.c.includes_workflows.drop()
    except Exception, e:
        print "Dropping column includes_workflows from the repository_metadata table failed: %s" % str( e )

    # Drop the includes_agent_dependencies column.
    try:
        RepositoryMetadata_table.c.includes_agent_dependencies.drop()
    except Exception, e:
        print "Dropping column includes_agent_dependencies from the repository_metadata table failed: %s" % str( e )

    # Drop the includes_agents column.
    try:
        RepositoryMetadata_table.c.includes_agents.drop()
    except Exception, e:
        print "Dropping column includes_agents from the repository_metadata table failed: %s" % str( e )

    # Drop the has_repository_dependencies column.
    try:
        RepositoryMetadata_table.c.has_repository_dependencies.drop()
    except Exception, e:
        print "Dropping column has_repository_dependencies from the repository_metadata table failed: %s" % str( e )

    # Drop the includes_datatypes column.
    try:
        RepositoryMetadata_table.c.includes_datatypes.drop()
    except Exception, e:
        print "Dropping column includes_datatypes from the repository_metadata table failed: %s" % str( e )
