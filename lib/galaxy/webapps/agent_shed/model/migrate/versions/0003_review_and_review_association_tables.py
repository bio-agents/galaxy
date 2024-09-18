"""
Adds the agent_rating_association table, enabling agents to be rated along with review comments.
"""
import datetime
import logging
import sys

from sqlalchemy import Column, DateTime, ForeignKey, Integer, MetaData, Table, TEXT

now = datetime.datetime.utcnow
log = logging.getLogger( __name__ )
log.setLevel(logging.DEBUG)
handler = logging.StreamHandler( sys.stdout )
format = "%(name)s %(levelname)s %(asctime)s %(message)s"
formatter = logging.Formatter( format )
handler.setFormatter( formatter )
log.addHandler( handler )

metadata = MetaData()

AgentRatingAssociation_table = Table( "agent_rating_association", metadata,
                                     Column( "id", Integer, primary_key=True ),
                                     Column( "create_time", DateTime, default=now ),
                                     Column( "update_time", DateTime, default=now, onupdate=now ),
                                     Column( "agent_id", Integer, ForeignKey( "agent.id" ), index=True ),
                                     Column( "user_id", Integer, ForeignKey( "galaxy_user.id" ), index=True ),
                                     Column( "rating", Integer, index=True ),
                                     Column( "comment", TEXT ) )


def upgrade(migrate_engine):
    print __doc__
    metadata.bind = migrate_engine
    # Load existing tables
    metadata.reflect()
    try:
        AgentRatingAssociation_table.create()
    except Exception, e:
        log.debug( "Creating agent_rating_association table failed: %s" % str( e ) )


def downgrade(migrate_engine):
    # Load existing tables
    metadata.bind = migrate_engine
    metadata.reflect()
    try:
        AgentRatingAssociation_table.drop()
    except Exception, e:
        log.debug( "Dropping agent_rating_association table failed: %s" % str( e ) )
