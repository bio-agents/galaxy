"""
Migration script to drop the installed_changeset_revision column from the agent_dependency table.
"""
import datetime
import logging
import sys

from sqlalchemy import MetaData, Table
from sqlalchemy.exc import NoSuchTableError

now = datetime.datetime.utcnow
log = logging.getLogger( __name__ )
log.setLevel( logging.DEBUG )
handler = logging.StreamHandler( sys.stdout )
format = "%(name)s %(levelname)s %(asctime)s %(message)s"
formatter = logging.Formatter( format )
handler.setFormatter( formatter )
log.addHandler( handler )

metadata = MetaData()


def upgrade(migrate_engine):
    metadata.bind = migrate_engine
    print __doc__
    metadata.reflect()
    try:
        AgentDependency_table = Table( "agent_dependency", metadata, autoload=True )
    except NoSuchTableError:
        AgentDependency_table = None
        log.debug( "Failed loading table agent_dependency" )
    if AgentDependency_table is not None:
        try:
            col = AgentDependency_table.c.installed_changeset_revision
            col.drop()
        except Exception, e:
            log.debug( "Dropping column 'installed_changeset_revision' from agent_dependency table failed: %s" % ( str( e ) ) )


def downgrade(migrate_engine):
    metadata.bind = migrate_engine
    pass
