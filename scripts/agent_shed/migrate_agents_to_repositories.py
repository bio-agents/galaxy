#!/usr/bin/env python

'''
Migrate old Galaxy agent shed to next gen Galaxy agent shed.  Specifically, the agent archives stored as
files in the old agent shed will be migrated to mercurial repositories in the next gen agent shed.  This
script can be run any number of times as it initially eliminates any current repositories and db records
associated with them, and migrates old agent shed stuff to new agent shed stuff.

====== CRITICAL =======

0. This script must be run on a repo updated to changeset:   5621:4618be57481b

1. Before running this script, make sure the following config setting is set in agent_shed_wsgi.ini

# Enable next-gen agent shed features
enable_next_gen_agent_shed = True

2. This script requires the Galaxy instance to use Postgres for database storage.  

To run this script, use "sh migrate_agents_to_repositories.sh" from this directory
'''

import sys, os, subprocess, ConfigParser, shutil, tarfile, tempfile

assert sys.version_info[:2] >= ( 2, 4 )
new_path = [ os.path.join( os.getcwd(), "lib" ) ]
new_path.extend( sys.path[1:] ) # remove scripts/ from the path
sys.path = new_path

import psycopg2

import galaxy.webapps.agent_shed.app
from mercurial import hg, ui, httprepo, commands
from time import strftime

def directory_hash_id( id ):
    s = str( id )
    l = len( s )
    # Shortcut -- ids 0-999 go under ../000/
    if l < 4:
        return [ "000" ]
    # Pad with zeros until a multiple of three
    padded = ( ( ( 3 - len( s ) ) % 3 ) * "0" ) + s
    # Drop the last three digits -- 1000 files per directory
    padded = padded[:-3]
    # Break into chunks of three
    return [ padded[i*3:(i+1)*3] for i in range( len( padded ) // 3 ) ]

def get_versions( app, item ):
    """Get all versions of item whose state is a valid state"""
    valid_states = [ app.model.Agent.states.NEW, 
                     app.model.Agent.states.WAITING, 
                     app.model.Agent.states.APPROVED, 
                     app.model.Agent.states.ARCHIVED ]
    versions = [ item ]
    this_item = item
    while item.newer_version:
        if item.newer_version.state in valid_states:
            versions.append( item.newer_version )
        item = item.newer_version
    item = this_item
    while item.older_version:
        if item.older_version[ 0 ].state in valid_states:
            versions.insert( 0, item.older_version[ 0 ] )
        item = item.older_version[ 0 ]
    return versions

def get_approved_agents( app, sa_session ):
    """Get only the latest version of each agent from the database whose state is approved"""
    agents = []
    for agent in sa_session.query( app.model.Agent ) \
                          .order_by( app.model.Agent.table.c.name ):
        if agent.state == app.model.Agent.states.APPROVED:
            agents.append( agent )
    return agents

def create_repository_from_agent( app, sa_session, agent ):
    # Make the repository name a form of the agent's agent_id by
    # lower-casing everything and replacing any blank spaces with underscores.
    repo_name = agent.agent_id.lower().replace( ' ', '_' )
    print "Creating repository '%s' in database" % ( repo_name )
    repository = app.model.Repository( name=repo_name,
                                       description=agent.description,
                                       user_id = agent.user_id )
    # Flush to get the id
    sa_session.add( repository )
    sa_session.flush()
    # Determine the local repository's path on disk
    dir = os.path.join( app.config.file_path, *directory_hash_id( repository.id ) )
    # Create directory if it does not exist
    if not os.path.exists( dir ):
        os.makedirs( dir )
    # Define repository name inside hashed directory
    repository_path = os.path.join( dir, "repo_%d" % repository.id )
    # Create repository directory
    if not os.path.exists( repository_path ):
        os.makedirs( repository_path )
    # Create the local hg repository
    print "Creating repository '%s' on disk" % ( os.path.abspath( repository_path ) )
    repo = hg.repository( ui.ui(), os.path.abspath( repository_path ), create=True )
    # Add an entry in the hgweb.config file for the new repository - this enables calls to repository.repo_path
    add_hgweb_config_entry( repository, repository_path )
    # Migrate agent categories
    for tca in agent.categories:
        category = tca.category
        print "Associating category '%s' with repository '%s' in database" % ( category.name, repository.name )
        rca = app.model.RepositoryCategoryAssociation( repository, category )
        sa_session.add( rca )
    sa_session.flush()
    # Migrate agent ratings
    print "Associating ratings for agent '%s' with repository '%s'" % ( agent.name, repository.name )
    for tra in agent.ratings:
        rra = app.model.RepositoryRatingAssociation( user=tra.user,
                                                     rating=tra.rating,
                                                     comment=tra.comment )
        rra.repository=repository
        sa_session.add( rra )
    sa_session.flush()

def add_hgweb_config_entry( repository, repository_path ):
    # Add an entry in the hgweb.config file for a new repository.  This enables calls to repository.repo_path.
    # An entry looks something like: repos/test/mira_assembler = database/community_files/000/repo_123
    hgweb_config = "%s/hgweb.config" %  os.getcwd()
    entry = "repos/%s/%s = %s" % ( repository.user.username, repository.name, repository_path.lstrip( './' ) )
    if os.path.exists( hgweb_config ):
        output = open( hgweb_config, 'a' )
    else:
        output = open( hgweb_config, 'w' )
        output.write( '[paths]\n' )
    output.write( "%s\n" % entry )
    output.close()

def create_hgrc_file( repository ):
    # At this point, an entry for the repository is required to be in the hgweb.config
    # file so we can call repository.repo_path.
    # Create a .hg/hgrc file that looks something like this:
    # [web]
    # allow_push = test
    # name = convert_characters1
    # push_ssl = False
    # Upon repository creation, only the owner can push to it ( allow_push setting ),
    # and since we support both http and https, we set push_ssl to False to override
    # the default (which is True) in the mercurial api.
    hgrc_file = os.path.abspath( os.path.join( repository.repo_path, ".hg", "hgrc" ) )
    output = open( hgrc_file, 'w' )
    output.write( '[web]\n' )
    output.write( 'allow_push = %s\n' % repository.user.username )
    output.write( 'name = %s\n' % repository.name )
    output.write( 'push_ssl = false\n' )
    output.flush()
    output.close()

def add_agent_files_to_repository( app, sa_session, agent ):
    current_working_dir = os.getcwd()
    # Get the repository to which the agent will be migrated
    repo_name = agent.agent_id.lower().replace( ' ', '_' )
    repository = get_repository_by_name( app, sa_session, repo_name )
    repo_path = os.path.abspath( repository.repo_path )
    # Get all valid versions of the agent
    agent_versions = get_versions( app, agent )
    for agent_version in agent_versions:
        print "------------------------------"
        print "Migrating agent '%s' version '%s' from archive to repository '%s'" % ( agent_version.agent_id, agent_version.version, repo_path )
        # Make a temporary working directory
        tmp_dir = tempfile.mkdtemp()
        tmp_archive_dir = os.path.join( tmp_dir, 'tmp_archive_dir' )
        if not os.path.exists( tmp_archive_dir ):
            os.makedirs( tmp_archive_dir )
        cmd = "hg clone %s" % repo_path
        os.chdir( tmp_archive_dir )
        os.system( cmd )
        os.chdir( current_working_dir )        
        cloned_repo_dir = os.path.join( tmp_archive_dir, 'repo_%d' % repository.id )
        # We want these change sets to be associated with the owner of the repository, so we'll
        # set the HGUSER environment variable accordingly.  We do this because in the mercurial
        # api, the default username to be used in commits is determined in this order: $HGUSER,
        # [ui] section of hgrcs, $EMAIL and stop searching if one of these is set.
        os.environ[ 'HGUSER' ] = repository.user.username
        # Copy the agent archive to the tmp_archive_dir.  The src file cannot be derived from
        # agent.file_name here because we have not loaded the Agent class in the model, so the
        # agent.file_name defaults to /tmp/...
        dir = os.path.join( app.config.file_path, 'agents', *directory_hash_id( agent_version.id ) )
        src = os.path.abspath( os.path.join( dir, 'agent_%d.dat' % agent_version.id ) )
        dst = os.path.join( tmp_archive_dir, agent_archive_file_name( agent_version, src ) )
        shutil.copy( src, dst )
        # Extract the archive to cloned_repo_dir
        tarfile.open( dst ).extractall( path=cloned_repo_dir )
        # Remove the archive
        os.remove( dst )
        # Change current working directory to the cloned repository
        os.chdir( cloned_repo_dir )
        for root, dirs, files in os.walk( cloned_repo_dir ):
            if '.hg' in dirs:
                # Don't visit .hg directories
                dirs.remove( '.hg' )
            if 'hgrc' in files:
                 # Don't include hgrc files in commit - should be impossible
                 # since we don't visit .hg dirs, but just in case...
                files.remove( 'hgrc' )
            for dir in dirs:
                os.system( "hg add %s" % dir )
            for name in files:
                print "Adding file '%s' to cloned repository at %s" % ( name, str( os.getcwd() ) )
                os.system( "hg add %s" % name )
        print "Committing change set to cloned repository at %s" % str( os.getcwd() )
        os.system( "hg commit -m 'Migrated agent version %s from old agent shed archive to new agent shed repository'" % agent_version.version )
        print "Pushing changeset from cloned repository '%s' to repository '%s'" % ( cloned_repo_dir, repo_path )
        cmd = "hg push %s" % repo_path
        print "cmd is: ", cmd
        os.system( cmd )
        # The agent shed includes a repository source file browser, which currently depends upon
        # copies of the hg repository file store in the repo_path for browsing.  We'll do the
        # following to make these copies.
        os.chdir( repo_path )
        os.system( 'hg update' )
        # Change the current working directory to the original
        os.chdir( current_working_dir )
        # Now that we have out new repository made current with all change sets,
        # we'll create a hgrc file for it.
        create_hgrc_file( repository )
        # Remove tmp directory
        shutil.rmtree( tmp_dir )

def get_repository_by_name( app, sa_session, repo_name ):
    """Get a repository from the database"""
    return sa_session.query( app.model.Repository ).filter_by( name=repo_name ).one()

def contains( containing_str, contained_str ):
    return containing_str.lower().find( contained_str.lower() ) >= 0

def agent_archive_extension( file_name ):
    extension = None
    if extension is None:
        head = open( file_name, 'rb' ).read( 4 )
        try:
            assert head[:3] == 'BZh'
            assert int( head[-1] ) in range( 0, 10 )
            extension = 'tar.bz2'
        except AssertionError:
            pass
    if extension is None:
        try:
            assert head[:2] == '\037\213'
            extension = 'tar.gz'
        except:
            pass
    if extension is None:
        extension = 'tar'
    return extension

def agent_archive_file_name( agent, file_name ):
    return '%s_%s.%s' % ( agent.agent_id, agent.version, agent_archive_extension( file_name ) )
    
def main():
    if len( sys.argv ) < 2:
        print "Usage: python %s <Agent shed config file>" % sys.argv[0]
        sys.exit( 0 )
    now = strftime( "%Y-%m-%d %H:%M:%S" )
    print " "
    print "##########################################"
    print "%s - Migrating current agent archives to new agent repositories" % now
    # agent_shed_wsgi.ini file
    ini_file = sys.argv[1]
    conf_parser = ConfigParser.ConfigParser( {'here':os.getcwd()} )
    conf_parser.read( ini_file )
    try:
        db_conn_str = conf_parser.get( "app:main", "database_connection" )
    except ConfigParser.NoOptionError, e:
        db_conn_str = conf_parser.get( "app:main", "database_file" )
    print 'DB Connection: ', db_conn_str
    # Determine db connection - only postgres is supported
    if contains( db_conn_str, '///' ) and contains( db_conn_str, '?' ) and contains( db_conn_str, '&' ):
        # postgres:///galaxy_test?user=postgres&password=postgres 
        db_str = db_conn_str.split( '///' )[1]
        db_name = db_str.split( '?' )[0]
        db_user = db_str.split( '?' )[1].split( '&' )[0].split( '=' )[1]
        db_password = db_str.split( '?' )[1].split( '&' )[1].split( '=' )[1]
    elif contains( db_conn_str, '//' ) and contains( db_conn_str, ':' ):
        # dialect://user:password@host/db_name
        db_name = db_conn_str.split('/')[-1]
        db_user = db_conn_str.split('//')[1].split(':')[0]
    # Instantiate app
    configuration = {}
    for key, value in conf_parser.items( "app:main" ):
        configuration[key] = value
    app = galaxy.webapps.agent_shed.app.UniverseApplication( global_conf=dict( __file__=ini_file ), **configuration )
    sa_session = app.model.context
    # Remove the hgweb.config file if it exists
    hgweb_config = "%s/hgweb.config" %  os.getcwd()
    if os.path.exists( hgweb_config ):
        print "Removing old file: ", hgweb_config
        os.remove( hgweb_config )
    repo_records = 0
    rca_records = 0
    rra_records = 0
    for repo in sa_session.query( app.model.Repository ):
        # Remove the hg repository from disk.  We have to be careful here, because old
        # agent files exist in app.config.file_path/agents and we don't want to delete them
        dir = os.path.join( app.config.file_path, *directory_hash_id( repo.id ) )
        if os.path.exists( dir ):
            print "Removing old repository file directory: ", dir
            shutil.rmtree( dir )
        # Delete all records from db tables: 
        # repository_category_association, repository_rating_association, repository
        print "Deleting db records for repository: ", repo.name
        for rca in repo.categories:
            sa_session.delete( rca )
            rca_records += 1
        for rra in repo.ratings:
            sa_session.delete( rra )
            rra_records += 1
        sa_session.delete( repo )
        repo_records += 1
    sa_session.flush()
    print "Deleted %d rows from the repository table" % repo_records
    print "Deleted %d rows from the repository_category_association table" % rca_records
    print "Deleted %d rows from the repository_rating_association table" % rra_records
    # Migrate database agent, agent category and agent rating records to new 
    # database repository, repository category and repository rating records
    # and create the hg repository on disk for each.
    for agent in get_approved_agents( app, sa_session ):
        create_repository_from_agent( app, sa_session, agent )
    # Add, commit and push all valid versions of each approved agent to the
    # associated hg repository.
    for agent in get_approved_agents( app, sa_session ):
        add_agent_files_to_repository( app, sa_session, agent )
    app.shutdown()
    print ' '
    print 'Migration to next gen agent shed complete...'
    print "##########################################"
    sys.exit(0)

if __name__ == "__main__":
    main()
