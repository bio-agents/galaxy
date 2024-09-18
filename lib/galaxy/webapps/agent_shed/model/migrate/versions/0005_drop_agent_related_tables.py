"""
Drops the agent, agent_category_association, event, agent_event_association, agent_rating_association,
agent_tag_association and agent_annotation_association tables since they are no longer used in the
next-gen agent shed.
"""
import datetime
import logging
import sys

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, MetaData, Table, TEXT
from sqlalchemy.exc import NoSuchTableError

# Need our custom types, but don't import anything else from model
from galaxy.model.custom_types import TrimmedString

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
    print __doc__
    # Load existing tables
    metadata.bind = migrate_engine
    metadata.reflect()
    # Load and then drop the agent_category_association table
    try:
        AgentCategoryAssociation_table = Table( "agent_category_association", metadata, autoload=True )
    except NoSuchTableError:
        log.debug( "Failed loading table agent_category_association" )
    try:
        AgentCategoryAssociation_table.drop()
    except Exception, e:
        log.debug( "Dropping agent_category_association table failed: %s" % str( e ) )
    # Load and then drop the agent_event_association table
    try:
        AgentEventAssociation_table = Table( "agent_event_association", metadata, autoload=True )
    except NoSuchTableError:
        log.debug( "Failed loading table agent_event_association" )
    try:
        AgentEventAssociation_table.drop()
    except Exception, e:
        log.debug( "Dropping agent_event_association table failed: %s" % str( e ) )
    # Load and then drop the agent_rating_association table
    try:
        AgentRatingAssociation_table = Table( "agent_rating_association", metadata, autoload=True )
    except NoSuchTableError:
        log.debug( "Failed loading table agent_rating_association" )
    try:
        AgentRatingAssociation_table.drop()
    except Exception, e:
        log.debug( "Dropping agent_rating_association table failed: %s" % str( e ) )
    # Load and then drop the agent_tag_association table
    try:
        AgentTagAssociation_table = Table( "agent_tag_association", metadata, autoload=True )
    except NoSuchTableError:
        log.debug( "Failed loading table agent_tag_association" )
    try:
        AgentTagAssociation_table.drop()
    except Exception, e:
        log.debug( "Dropping agent_tag_association table failed: %s" % str( e ) )
    # Load and then drop the agent_annotation_association table
    try:
        AgentAnnotationAssociation_table = Table( "agent_annotation_association", metadata, autoload=True )
    except NoSuchTableError:
        log.debug( "Failed loading table agent_annotation_association" )
    try:
        AgentAnnotationAssociation_table.drop()
    except Exception, e:
        log.debug( "Dropping agent_annotation_association table failed: %s" % str( e ) )
    # Load and then drop the event table
    try:
        Event_table = Table( "event", metadata, autoload=True )
    except NoSuchTableError:
        log.debug( "Failed loading table event" )
    try:
        Event_table.drop()
    except Exception, e:
        log.debug( "Dropping event table failed: %s" % str( e ) )
    # Load and then drop the agent table
    try:
        Agent_table = Table( "agent", metadata, autoload=True )
    except NoSuchTableError:
        log.debug( "Failed loading table agent" )
    try:
        Agent_table.drop()
    except Exception, e:
        log.debug( "Dropping agent table failed: %s" % str( e ) )


def downgrade(migrate_engine):
    # Load existing tables
    metadata.bind = migrate_engine
    metadata.reflect()
    # We've lost all of our data, so downgrading is useless. However, we'll
    # at least re-create the dropped tables.
    Event_table = Table( 'event', metadata,
                         Column( "id", Integer, primary_key=True ),
                         Column( "create_time", DateTime, default=now ),
                         Column( "update_time", DateTime, default=now, onupdate=now ),
                         Column( "state", TrimmedString( 255 ), index=True ),
                         Column( "comment", TEXT ) )

    Agent_table = Table( "agent", metadata,
                        Column( "id", Integer, primary_key=True ),
                        Column( "guid", TrimmedString( 255 ), index=True, unique=True ),
                        Column( "agent_id", TrimmedString( 255 ), index=True ),
                        Column( "create_time", DateTime, default=now ),
                        Column( "update_time", DateTime, default=now, onupdate=now ),
                        Column( "newer_version_id", Integer, ForeignKey( "agent.id" ), nullable=True ),
                        Column( "name", TrimmedString( 255 ), index=True ),
                        Column( "description" , TEXT ),
                        Column( "user_description" , TEXT ),
                        Column( "version", TrimmedString( 255 ) ),
                        Column( "user_id", Integer, ForeignKey( "galaxy_user.id" ), index=True ),
                        Column( "external_filename" , TEXT ),
                        Column( "deleted", Boolean, index=True, default=False ),
                        Column( "suite", Boolean, default=False, index=True ) )

    AgentCategoryAssociation_table = Table( "agent_category_association", metadata,
                                           Column( "id", Integer, primary_key=True ),
                                           Column( "agent_id", Integer, ForeignKey( "agent.id" ), index=True ),
                                           Column( "category_id", Integer, ForeignKey( "category.id" ), index=True ) )

    AgentEventAssociation_table = Table( "agent_event_association", metadata,
                                        Column( "id", Integer, primary_key=True ),
                                        Column( "agent_id", Integer, ForeignKey( "agent.id" ), index=True ),
                                        Column( "event_id", Integer, ForeignKey( "event.id" ), index=True ) )

    AgentRatingAssociation_table = Table( "agent_rating_association", metadata,
                                         Column( "id", Integer, primary_key=True ),
                                         Column( "create_time", DateTime, default=now ),
                                         Column( "update_time", DateTime, default=now, onupdate=now ),
                                         Column( "agent_id", Integer, ForeignKey( "agent.id" ), index=True ),
                                         Column( "user_id", Integer, ForeignKey( "galaxy_user.id" ), index=True ),
                                         Column( "rating", Integer, index=True ),
                                         Column( "comment", TEXT ) )

    AgentTagAssociation_table = Table( "agent_tag_association", metadata,
                                      Column( "id", Integer, primary_key=True ),
                                      Column( "agent_id", Integer, ForeignKey( "agent.id" ), index=True ),
                                      Column( "tag_id", Integer, ForeignKey( "tag.id" ), index=True ),
                                      Column( "user_id", Integer, ForeignKey( "galaxy_user.id" ), index=True ),
                                      Column( "user_tname", TrimmedString(255), index=True),
                                      Column( "value", TrimmedString(255), index=True),
                                      Column( "user_value", TrimmedString(255), index=True) )

    AgentAnnotationAssociation_table = Table( "agent_annotation_association", metadata,
                                             Column( "id", Integer, primary_key=True ),
                                             Column( "agent_id", Integer, ForeignKey( "agent.id" ), index=True ),
                                             Column( "user_id", Integer, ForeignKey( "galaxy_user.id" ), index=True ),
                                             Column( "annotation", TEXT, index=True) )

    # Create the event table
    try:
        Event_table.create()
    except Exception, e:
        log.debug( "Creating event table failed: %s" % str( e ) )
    # Create the agent table
    try:
        Agent_table.create()
    except Exception, e:
        log.debug( "Creating agent table failed: %s" % str( e ) )
    # Create the agent_category_association table
    try:
        AgentCategoryAssociation_table.create()
    except Exception, e:
        log.debug( "Creating agent_category_association table failed: %s" % str( e ) )
    # Create the agent_event_association table
    try:
        AgentEventAssociation_table.create()
    except Exception, e:
        log.debug( "Creating agent_event_association table failed: %s" % str( e ) )
    # Create the agent_rating_association table
    try:
        AgentRatingAssociation_table.create()
    except Exception, e:
        log.debug( "Creating agent_rating_association table failed: %s" % str( e ) )
    # Create the agent_tag_association table
    try:
        AgentTagAssociation_table.create()
    except Exception, e:
        log.debug( "Creating agent_tag_association table failed: %s" % str( e ) )
    # Create the agent_annotation_association table
    try:
        AgentAnnotationAssociation_table.create()
    except Exception, e:
        log.debug( "Creating agent_annotation_association table failed: %s" % str( e ) )
