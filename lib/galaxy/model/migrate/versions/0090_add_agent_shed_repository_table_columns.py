"""
Migration script to add the uninstalled and dist_to_shed columns to the agent_shed_repository table.
"""
import datetime
import logging
import sys

from sqlalchemy import Boolean, Column, MetaData, Table

now = datetime.datetime.utcnow
log = logging.getLogger( __name__ )
log.setLevel(logging.DEBUG)
handler = logging.StreamHandler( sys.stdout )
format = "%(name)s %(levelname)s %(asctime)s %(message)s"
formatter = logging.Formatter( format )
handler.setFormatter( formatter )
log.addHandler( handler )

metadata = MetaData()


def default_false(migrate_engine):
    if migrate_engine.name in ['mysql', 'sqlite']:
        return "0"
    elif migrate_engine.name in ['postgres', 'postgresql']:
        return "false"


def upgrade(migrate_engine):
    metadata.bind = migrate_engine
    print __doc__
    metadata.reflect()
    AgentShedRepository_table = Table( "agent_shed_repository", metadata, autoload=True )
    c = Column( "uninstalled", Boolean, default=False )
    try:
        c.create( AgentShedRepository_table )
        assert c is AgentShedRepository_table.c.uninstalled
        migrate_engine.execute( "UPDATE agent_shed_repository SET uninstalled=%s" % default_false(migrate_engine) )
    except Exception, e:
        print "Adding uninstalled column to the agent_shed_repository table failed: %s" % str( e )
    c = Column( "dist_to_shed", Boolean, default=False )
    try:
        c.create( AgentShedRepository_table )
        assert c is AgentShedRepository_table.c.dist_to_shed
        migrate_engine.execute( "UPDATE agent_shed_repository SET dist_to_shed=%s" % default_false(migrate_engine) )
    except Exception, e:
        print "Adding dist_to_shed column to the agent_shed_repository table failed: %s" % str( e )


def downgrade(migrate_engine):
    metadata.bind = migrate_engine
    metadata.reflect()
    AgentShedRepository_table = Table( "agent_shed_repository", metadata, autoload=True )
    try:
        AgentShedRepository_table.c.uninstalled.drop()
    except Exception, e:
        print "Dropping column uninstalled from the agent_shed_repository table failed: %s" % str( e )
    try:
        AgentShedRepository_table.c.dist_to_shed.drop()
    except Exception, e:
        print "Dropping column dist_to_shed from the agent_shed_repository table failed: %s" % str( e )
