"""
Migration script to create table for storing agent tag associations.
"""
import datetime
import logging

from sqlalchemy import Column, ForeignKey, Integer, MetaData, Table

from galaxy.model.custom_types import TrimmedString

now = datetime.datetime.utcnow
log = logging.getLogger( __name__ )
metadata = MetaData()

# Table to add

AgentTagAssociation_table = Table( "agent_tag_association", metadata,
                                  Column( "id", Integer, primary_key=True ),
                                  Column( "agent_id", TrimmedString(255), index=True ),
                                  Column( "tag_id", Integer, ForeignKey( "tag.id" ), index=True ),
                                  Column( "user_id", Integer, ForeignKey( "galaxy_user.id" ), index=True ),
                                  Column( "user_tname", TrimmedString(255), index=True),
                                  Column( "value", TrimmedString(255), index=True),
                                  Column( "user_value", TrimmedString(255), index=True) )


def upgrade(migrate_engine):
    metadata.bind = migrate_engine
    print __doc__
    metadata.reflect()

    # Create agent_tag_association table
    try:
        AgentTagAssociation_table.create()
    except Exception, e:
        log.error( "Creating agent_tag_association table failed: %s" % str( e ) )


def downgrade(migrate_engine):
    metadata.bind = migrate_engine
    metadata.reflect()

    # Drop agent_tag_association table
    try:
        AgentTagAssociation_table.drop()
    except Exception, e:
        log.error( "Dropping agent_tag_association table failed: %s" % str( e ) )
