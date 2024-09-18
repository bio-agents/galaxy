"""
Migration script to add the suite column to the agent table.
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


def upgrade( migrate_engine ):
    metadata.bind = migrate_engine
    print __doc__
    metadata.reflect()
    # Create and initialize imported column in job table.
    Agent_table = Table( "agent", metadata, autoload=True )
    c = Column( "suite", Boolean, default=False, index=True )
    try:
        # Create
        c.create( Agent_table, index_name='ix_agent_suite')
        assert c is Agent_table.c.suite
        # Initialize.
        if migrate_engine.name == 'mysql' or migrate_engine.name == 'sqlite':
            default_false = "0"
        elif migrate_engine.name in ['postgresql', 'postgres']:
            default_false = "false"
        migrate_engine.execute( "UPDATE agent SET suite=%s" % default_false )
    except Exception, e:
        print "Adding suite column to the agent table failed: %s" % str( e )
        log.debug( "Adding suite column to the agent table failed: %s" % str( e ) )


def downgrade( migrate_engine ):
    metadata.bind = migrate_engine
    metadata.reflect()
    # Drop suite column from agent table.
    Agent_table = Table( "agent", metadata, autoload=True )
    try:
        Agent_table.c.suite.drop()
    except Exception, e:
        print "Dropping column suite from the agent table failed: %s" % str( e )
        log.debug( "Dropping column suite from the agent table failed: %s" % str( e ) )
