"""Migration script to add status and error_message columns to the agent_shed_repository table."""
import datetime

from sqlalchemy import Column, MetaData, Table, TEXT

# Need our custom types, but don't import anything else from model
from galaxy.model.custom_types import TrimmedString

now = datetime.datetime.utcnow
metadata = MetaData()


def upgrade(migrate_engine):
    metadata.bind = migrate_engine
    print __doc__
    metadata.reflect()
    AgentShedRepository_table = Table( "agent_shed_repository", metadata, autoload=True )
    # Add the status column to the agent_shed_repository table.
    col = Column( "status", TrimmedString( 255 ) )
    try:
        col.create( AgentShedRepository_table )
        assert col is AgentShedRepository_table.c.status
    except Exception, e:
        print "Adding status column to the agent_shed_repository table failed: %s" % str( e )
    # Add the error_message column to the agent_shed_repository table.
    col = Column( "error_message", TEXT )
    try:
        col.create( AgentShedRepository_table )
        assert col is AgentShedRepository_table.c.error_message
    except Exception, e:
        print "Adding error_message column to the agent_shed_repository table failed: %s" % str( e )
    # Update the status column value for agent_shed_repositories to the default value 'Installed'.
    cmd = "UPDATE agent_shed_repository SET status = 'Installed';"
    try:
        migrate_engine.execute( cmd )
    except Exception, e:
        print "Exception executing sql command: "
        print cmd
        print str( e )
    # Update the status column for agent_shed_repositories that have been uninstalled.
    cmd = "UPDATE agent_shed_repository SET status = 'Uninstalled' WHERE uninstalled;"
    try:
        migrate_engine.execute( cmd )
    except Exception, e:
        print "Exception executing sql command: "
        print cmd
        print str( e )
    # Update the status column for agent_shed_repositories that have been deactivated.
    cmd = "UPDATE agent_shed_repository SET status = 'Deactivated' where deleted and not uninstalled;"
    try:
        migrate_engine.execute( cmd )
    except Exception, e:
        print "Exception executing sql command: "
        print cmd
        print str( e )


def downgrade(migrate_engine):
    metadata.bind = migrate_engine
    metadata.reflect()
    AgentShedRepository_table = Table( "agent_shed_repository", metadata, autoload=True )
    try:
        AgentShedRepository_table.c.status.drop()
    except Exception, e:
        print "Dropping column status from the agent_shed_repository table failed: %s" % str( e )
    try:
        AgentShedRepository_table.c.error_message.drop()
    except Exception, e:
        print "Dropping column error_message from the agent_shed_repository table failed: %s" % str( e )
