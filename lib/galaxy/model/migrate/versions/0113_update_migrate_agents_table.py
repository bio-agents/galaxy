"""
Migration script to update the migrate_agents.repository_path column to point to the new location lib/agent_shed/galaxy_install/migrate.
"""
import datetime
import logging
import sys

now = datetime.datetime.utcnow
log = logging.getLogger( __name__ )
log.setLevel(logging.DEBUG)
handler = logging.StreamHandler( sys.stdout )
format = "%(name)s %(levelname)s %(asctime)s %(message)s"
formatter = logging.Formatter( format )
handler.setFormatter( formatter )
log.addHandler( handler )


def upgrade(migrate_engine):
    print __doc__
    # Create the table.
    try:
        cmd = "UPDATE migrate_agents set repository_path='lib/galaxy/agent_shed/migrate';"
        migrate_engine.execute( cmd )
    except Exception, e:
        log.debug( "Updating migrate_agents.repository_path column to point to the new location lib/agent_shed/galaxy_install/migrate failed: %s" % str( e ) )


def downgrade(migrate_engine):
    try:
        cmd = "UPDATE migrate_agents set repository_path='lib/galaxy/agent_shed/migrate';"
        migrate_engine.execute( cmd )
    except Exception, e:
        log.debug( "Updating migrate_agents.repository_path column to point to the old location lib/galaxy/agent_shed/migrate failed: %s" % str( e ) )
