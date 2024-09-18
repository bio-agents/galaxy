"""
Migration script to create the agent_version and agent_version_association tables and drop the agent_id_guid_map table.
"""
import datetime
import logging
import sys
from json import loads

from sqlalchemy import Column, DateTime, ForeignKey, Integer, MetaData, String, Table, TEXT

# Need our custom types, but don't import anything else from model
from galaxy.model.custom_types import _sniffnfix_pg9_hex, TrimmedString

now = datetime.datetime.utcnow
log = logging.getLogger( __name__ )
log.setLevel(logging.DEBUG)
handler = logging.StreamHandler( sys.stdout )
format = "%(name)s %(levelname)s %(asctime)s %(message)s"
formatter = logging.Formatter( format )
handler.setFormatter( formatter )
log.addHandler( handler )

metadata = MetaData()


def nextval( migrate_engine, table, col='id' ):
    if migrate_engine.name in ['postgres', 'postgresql']:
        return "nextval('%s_%s_seq')" % ( table, col )
    elif migrate_engine.name in ['mysql', 'sqlite']:
        return "null"
    else:
        raise Exception( 'Unable to convert data for unknown database type: %s' % migrate_engine.name )


def localtimestamp(migrate_engine):
    if migrate_engine.name in ['mysql', 'postgres', 'postgresql']:
        return "LOCALTIMESTAMP"
    elif migrate_engine.name == 'sqlite':
        return "current_date || ' ' || current_time"
    else:
        raise Exception( 'Unable to convert data for unknown database type: %s' % migrate_engine.name )

AgentVersion_table = Table( "agent_version", metadata,
    Column( "id", Integer, primary_key=True ),
    Column( "create_time", DateTime, default=now ),
    Column( "update_time", DateTime, default=now, onupdate=now ),
    Column( "agent_id", String( 255 ) ),
    Column( "agent_shed_repository_id", Integer, ForeignKey( "agent_shed_repository.id" ), index=True, nullable=True ) )

AgentVersionAssociation_table = Table( "agent_version_association", metadata,
    Column( "id", Integer, primary_key=True ),
    Column( "agent_id", Integer, ForeignKey( "agent_version.id" ), index=True, nullable=False ),
    Column( "parent_id", Integer, ForeignKey( "agent_version.id" ), index=True, nullable=False ) )


def upgrade(migrate_engine):
    metadata.bind = migrate_engine
    print __doc__

    AgentIdGuidMap_table = Table( "agent_id_guid_map", metadata, autoload=True )

    metadata.reflect()
    # Create the tables.
    try:
        AgentVersion_table.create()
    except Exception, e:
        log.debug( "Creating agent_version table failed: %s" % str( e ) )
    try:
        AgentVersionAssociation_table.create()
    except Exception, e:
        log.debug( "Creating agent_version_association table failed: %s" % str( e ) )
    # Populate the agent table with agents included in installed agent shed repositories.
    cmd = "SELECT id, metadata FROM agent_shed_repository"
    result = migrate_engine.execute( cmd )
    count = 0
    for row in result:
        if row[1]:
            agent_shed_repository_id = row[0]
            repository_metadata = loads( _sniffnfix_pg9_hex( str( row[1] ) ) )
            # Create a new row in the agent table for each agent included in repository.  We will NOT
            # handle agent_version_associaions because we do not have the information we need to do so.
            agents = repository_metadata.get( 'agents', [] )
            for agent_dict in agents:
                cmd = "INSERT INTO agent_version VALUES (%s, %s, %s, '%s', %s)" % \
                    ( nextval( migrate_engine, 'agent_version' ), localtimestamp( migrate_engine ), localtimestamp( migrate_engine ), agent_dict[ 'guid' ], agent_shed_repository_id )
                migrate_engine.execute( cmd )
                count += 1
    print "Added %d rows to the new agent_version table." % count
    # Drop the agent_id_guid_map table since the 2 new tables render it unnecessary.
    try:
        AgentIdGuidMap_table.drop()
    except Exception, e:
        log.debug( "Dropping agent_id_guid_map table failed: %s" % str( e ) )


def downgrade(migrate_engine):
    metadata.bind = migrate_engine

    AgentIdGuidMap_table = Table( "agent_id_guid_map", metadata,
        Column( "id", Integer, primary_key=True ),
        Column( "create_time", DateTime, default=now ),
        Column( "update_time", DateTime, default=now, onupdate=now ),
        Column( "agent_id", String( 255 ) ),
        Column( "agent_version", TEXT ),
        Column( "agent_shed", TrimmedString( 255 ) ),
        Column( "repository_owner", TrimmedString( 255 ) ),
        Column( "repository_name", TrimmedString( 255 ) ),
        Column( "guid", TEXT, index=True, unique=True ) )

    metadata.reflect()
    try:
        AgentVersionAssociation_table.drop()
    except Exception, e:
        log.debug( "Dropping agent_version_association table failed: %s" % str( e ) )
    try:
        AgentVersion_table.drop()
    except Exception, e:
        log.debug( "Dropping agent_version table failed: %s" % str( e ) )
    try:
        AgentIdGuidMap_table.create()
    except Exception, e:
        log.debug( "Creating agent_id_guid_map table failed: %s" % str( e ) )
