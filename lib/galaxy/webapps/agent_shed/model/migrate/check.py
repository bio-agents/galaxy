import logging
import os.path
import sys

from migrate.versioning import repository, schema
from sqlalchemy import create_engine, MetaData, Table
from sqlalchemy.exc import NoSuchTableError

log = logging.getLogger( __name__ )

# path relative to galaxy
migrate_repository_directory = os.path.dirname( __file__ ).replace( os.getcwd() + os.path.sep, '', 1 )
migrate_repository = repository.Repository( migrate_repository_directory )


def create_or_verify_database( url, engine_options={} ):
    """
    Check that the database is use-able, possibly creating it if empty (this is
    the only time we automatically create tables, otherwise we force the
    user to do it using the management script so they can create backups).

    1) Empty database --> initialize with latest version and return
    2) Database older than migration support --> fail and require manual update
    3) Database at state where migrate support introduced --> add version control information but make no changes (might still require manual update)
    4) Database versioned but out of date --> fail with informative message, user must run "sh manage_db.sh upgrade"

    """
    # Create engine and metadata
    engine = create_engine( url, **engine_options )
    meta = MetaData( bind=engine )
    # Try to load dataset table
    try:
        Table( "galaxy_user", meta, autoload=True )
    except NoSuchTableError:
        # No 'galaxy_user' table means a completely uninitialized database, which
        # is fine, init the database in a versioned state
        log.info( "No database, initializing" )
        # Database might or might not be versioned
        try:
            # Declare the database to be under a repository's version control
            db_schema = schema.ControlledSchema.create( engine, migrate_repository )
        except:
            # The database is already under version control
            db_schema = schema.ControlledSchema( engine, migrate_repository )
        # Apply all scripts to get to current version
        migrate_to_current_version( engine, db_schema )
        return
    try:
        Table( "migrate_version", meta, autoload=True )
    except NoSuchTableError:
        # The database exists but is not yet under migrate version control, so init with version 1
        log.info( "Adding version control to existing database" )
        try:
            Table( "metadata_file", meta, autoload=True )
            schema.ControlledSchema.create( engine, migrate_repository, version=2 )
        except NoSuchTableError:
            schema.ControlledSchema.create( engine, migrate_repository, version=1 )
    # Verify that the code and the DB are in sync
    db_schema = schema.ControlledSchema( engine, migrate_repository )
    if migrate_repository.versions.latest != db_schema.version:
        exception_msg = "Your database has version '%d' but this code expects version '%d'.  " % ( db_schema.version, migrate_repository.versions.latest )
        exception_msg += "Back up your database and then migrate the schema by running the following from your Galaxy installation directory:"
        exception_msg += "\n\nsh manage_db.sh upgrade agent_shed\n"
        raise Exception( exception_msg )
    else:
        log.info( "At database version %d" % db_schema.version )


def migrate_to_current_version( engine, schema ):
    # Changes to get to current version
    changeset = schema.changeset( None )
    for ver, change in changeset:
        nextver = ver + changeset.step
        log.info( 'Migrating %s -> %s... ' % ( ver, nextver ) )
        old_stdout = sys.stdout

        class FakeStdout( object ):
            def __init__( self ):
                self.buffer = []

            def write( self, s ):
                self.buffer.append( s )

            def flush( self ):
                pass
        sys.stdout = FakeStdout()
        try:
            schema.runchange( ver, change, changeset.step )
        finally:
            for message in "".join( sys.stdout.buffer ).split( "\n" ):
                log.info( message )
            sys.stdout = old_stdout
