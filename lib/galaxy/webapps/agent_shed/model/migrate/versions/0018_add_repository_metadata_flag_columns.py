"""
Migration script to alter the repository_metadata table by dropping the agent_test_errors column and adding columns
agent_test_results, missing_test_components.
"""
import logging
import sys

from sqlalchemy import Boolean, Column, MetaData, Table
from sqlalchemy.exc import NoSuchTableError

# Need our custom types, but don't import anything else from model
from galaxy.model.custom_types import JSONType

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
    elif migrate_engine.name in ['postgresql', 'postgres']:
        default_false = "false"

    try:
        RepositoryMetadata_table = Table( "repository_metadata", metadata, autoload=True )
    except NoSuchTableError:
        RepositoryMetadata_table = None
        log.debug( "Failed loading table repository_metadata." )

    if RepositoryMetadata_table is not None:
        # Drop the agent_test_errors column from the repository_metadata table as it is poorly named.  It will be replaced with the new
        # agent_test_results column.
        try:
            col = RepositoryMetadata_table.c.agent_test_errors
            col.drop()
        except Exception, e:
            log.debug( "Dropping column 'agent_test_errors' from repository_metadata table failed: %s" % ( str( e ) ) )

        # Create the agent_test_results column to replace the ill-named agent_test_errors column just dropped above.
        c = Column( "agent_test_results", JSONType, nullable=True )
        try:
            c.create( RepositoryMetadata_table )
            assert c is RepositoryMetadata_table.c.agent_test_results
        except Exception, e:
            print "Adding agent_test_results column to the repository_metadata table failed: %s" % str( e )

        # Create the missing_test_components column.
        c = Column( "missing_test_components", Boolean, default=False, index=True )
        try:
            c.create( RepositoryMetadata_table, index_name="ix_repository_metadata_mtc")
            assert c is RepositoryMetadata_table.c.missing_test_components
            migrate_engine.execute( "UPDATE repository_metadata SET missing_test_components=%s" % default_false )
        except Exception, e:
            print "Adding missing_test_components column to the repository_metadata table failed: %s" % str( e )


def downgrade(migrate_engine):
    metadata.bind = migrate_engine
    metadata.reflect()
    # Drop missing_test_components and agent_test_results from the repository_metadata table and add agent_test_errors to the repository_metadata table.
    RepositoryMetadata_table = Table( "repository_metadata", metadata, autoload=True )

    # Drop the missing_test_components column.
    try:
        RepositoryMetadata_table.c.missing_test_components.drop()
    except Exception, e:
        print "Dropping column missing_test_components from the repository_metadata table failed: %s" % str( e )

    # Drop the agent_test_results column.
    try:
        RepositoryMetadata_table.c.agent_test_results.drop()
    except Exception, e:
        print "Dropping column agent_test_results from the repository_metadata table failed: %s" % str( e )

    # Create the agent_test_errors column.
    c = Column( "agent_test_errors", JSONType, nullable=True )
    try:
        c.create( RepositoryMetadata_table )
        assert c is RepositoryMetadata_table.c.agent_test_errors
    except Exception, e:
        print "Adding agent_test_errors column to the repository_metadata table failed: %s" % str( e )
