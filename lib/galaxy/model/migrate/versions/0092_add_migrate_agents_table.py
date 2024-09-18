"""
Migration script to create the migrate_agents table.
"""
import datetime
import logging
import sys

from sqlalchemy import Column, Integer, MetaData, Table, TEXT

# Need our custom types, but don't import anything else from model
from galaxy.model.custom_types import TrimmedString

now = datetime.datetime.utcnow
log = logging.getLogger( __name__ )
log.setLevel(logging.DEBUG)
handler = logging.StreamHandler( sys.stdout )
format = "%(name)s %(levelname)s %(asctime)s %(message)s"
formatter = logging.Formatter( format )
handler.setFormatter( formatter )
log.addHandler( handler )

metadata = MetaData()

MigrateAgents_table = Table( "migrate_agents", metadata,
                            Column( "repository_id", TrimmedString( 255 ) ),
                            Column( "repository_path", TEXT ),
                            Column( "version", Integer ) )


def upgrade(migrate_engine):
    metadata.bind = migrate_engine
    print __doc__

    metadata.reflect()
    # Create the table.
    try:
        MigrateAgents_table.create()
        cmd = "INSERT INTO migrate_agents VALUES ('GalaxyAgents', 'lib/galaxy/agent_shed/migrate', %d)" % 1
        migrate_engine.execute( cmd )
    except Exception, e:
        log.debug( "Creating migrate_agents table failed: %s" % str( e ) )


def downgrade(migrate_engine):
    metadata.bind = migrate_engine
    metadata.reflect()
    try:
        MigrateAgents_table.drop()
    except Exception, e:
        log.debug( "Dropping migrate_agents table failed: %s" % str( e ) )
