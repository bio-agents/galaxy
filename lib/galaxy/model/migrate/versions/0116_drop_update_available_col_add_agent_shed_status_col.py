"""
Migration script to drop the update_available Boolean column and replace it with the agent_shed_status JSONType column in the agent_shed_repository table.
"""
import datetime
import logging
import sys

from sqlalchemy import Boolean, Column, MetaData, Table
from sqlalchemy.exc import NoSuchTableError

from galaxy.model.custom_types import JSONType

now = datetime.datetime.utcnow
log = logging.getLogger( __name__ )
log.setLevel( logging.DEBUG )
handler = logging.StreamHandler( sys.stdout )
format = "%(name)s %(levelname)s %(asctime)s %(message)s"
formatter = logging.Formatter( format )
handler.setFormatter( formatter )
log.addHandler( handler )

metadata = MetaData()


def default_false( migrate_engine ):
    if migrate_engine.name in ['mysql', 'sqlite']:
        return "0"
    elif migrate_engine.name in [ 'postgres', 'postgresql' ]:
        return "false"


def upgrade( migrate_engine ):
    metadata.bind = migrate_engine
    print __doc__
    metadata.reflect()
    try:
        AgentShedRepository_table = Table( "agent_shed_repository", metadata, autoload=True )
    except NoSuchTableError:
        AgentShedRepository_table = None
        log.debug( "Failed loading table agent_shed_repository" )
    if AgentShedRepository_table is not None:
        # For some unknown reason it is no longer possible to drop a column in a migration script if using the sqlite database.
        if migrate_engine.name != 'sqlite':
            try:
                col = AgentShedRepository_table.c.update_available
                col.drop()
            except Exception, e:
                print "Dropping column update_available from the agent_shed_repository table failed: %s" % str( e )
        c = Column( "agent_shed_status", JSONType, nullable=True )
        try:
            c.create( AgentShedRepository_table )
            assert c is AgentShedRepository_table.c.agent_shed_status
        except Exception, e:
            print "Adding agent_shed_status column to the agent_shed_repository table failed: %s" % str( e )


def downgrade( migrate_engine ):
    metadata.bind = migrate_engine
    metadata.reflect()
    try:
        AgentShedRepository_table = Table( "agent_shed_repository", metadata, autoload=True )
    except NoSuchTableError:
        AgentShedRepository_table = None
        log.debug( "Failed loading table agent_shed_repository" )
    if AgentShedRepository_table is not None:
        # For some unknown reason it is no longer possible to drop a column in a migration script if using the sqlite database.
        if migrate_engine.name != 'sqlite':
            try:
                col = AgentShedRepository_table.c.agent_shed_status
                col.drop()
            except Exception, e:
                print "Dropping column agent_shed_status from the agent_shed_repository table failed: %s" % str( e )
            c = Column( "update_available", Boolean, default=False )
            try:
                c.create( AgentShedRepository_table )
                assert c is AgentShedRepository_table.c.update_available
                migrate_engine.execute( "UPDATE agent_shed_repository SET update_available=%s" % default_false( migrate_engine ) )
            except Exception, e:
                print "Adding column update_available to the agent_shed_repository table failed: %s" % str( e )
