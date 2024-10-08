#!/usr/bin/env python

import os
import re
import shutil
import sys
import tempfile
from ConfigParser import SafeConfigParser

# Assume we are run from the galaxy root directory, add lib to the python path
cwd = os.getcwd()
new_path = [ os.path.join( cwd, "lib" ), os.path.join( cwd, "test" ) ]
new_path.extend( sys.path[1:] )
sys.path = new_path

from base.test_logging import logging_config_file
from base.agent_shed_util import parse_agent_panel_config

from galaxy.util.properties import load_app_properties

import logging
import os.path
import time
import threading
import random
import httplib
import socket
import urllib
from paste import httpserver
from galaxy.app import UniverseApplication
from galaxy.web import buildapp
from galaxy import agents
from galaxy.util.json import dumps

from functional import database_contexts
from base.api_util import get_master_api_key
from base.api_util import get_user_api_key
from base.nose_util import run
from base.instrument import StructuredTestDataPlugin

import nose.core
import nose.config
import nose.loader
import nose.plugins.manager

log = logging.getLogger( "functional_tests.py" )

default_galaxy_test_host = "localhost"
default_galaxy_test_port_min = 8000
default_galaxy_test_port_max = 9999
default_galaxy_locales = 'en'
default_galaxy_test_file_dir = "test-data,https://github.com/galaxyproject/galaxy-test-data.git"
migrated_agent_panel_config = 'config/migrated_agents_conf.xml'
installed_agent_panel_configs = [
    os.environ.get('GALAXY_TEST_SHED_TOOL_CONF', 'config/shed_agent_conf.xml')
]


# should this serve static resources (scripts, images, styles, etc.)
STATIC_ENABLED = True

# Set up a job_conf.xml that explicitly limits jobs to 10 minutes.
job_conf_xml = '''<?xml version="1.0"?>
<!-- A test job config that explicitly configures job running the way it is configured by default (if there is no explicit config). -->
<job_conf>
    <plugins>
        <plugin id="local" type="runner" load="galaxy.jobs.runners.local:LocalJobRunner" workers="4"/>
    </plugins>
    <handlers>
        <handler id="main"/>
    </handlers>
    <destinations>
        <destination id="local" runner="local"/>
    </destinations>
    <limits>
        <limit type="walltime">00:10:00</limit>
    </limits>
</job_conf>
'''


def get_static_settings():
    """Returns dictionary of the settings necessary for a galaxy App
    to be wrapped in the static middleware.

    This mainly consists of the filesystem locations of url-mapped
    static resources.
    """
    cwd = os.getcwd()
    static_dir = os.path.join( cwd, 'static' )
    # TODO: these should be copied from config/galaxy.ini
    return dict(
        # TODO: static_enabled needed here?
        static_enabled=True,
        static_cache_time=360,
        static_dir=static_dir,
        static_images_dir=os.path.join( static_dir, 'images', '' ),
        static_favicon_dir=os.path.join( static_dir, 'favicon.ico' ),
        static_scripts_dir=os.path.join( static_dir, 'scripts', '' ),
        static_style_dir=os.path.join( static_dir, 'june_2007_style', 'blue' ),
        static_robots_txt=os.path.join( static_dir, 'robots.txt' ),
    )


def get_webapp_global_conf():
    """Get the global_conf dictionary sent as the first argument to app_factory.
    """
    # (was originally sent 'dict()') - nothing here for now except static settings
    global_conf = dict()
    if STATIC_ENABLED:
        global_conf.update( get_static_settings() )
    return global_conf


def generate_config_file( input_filename, output_filename, config_items ):
    '''
    Generate a config file with the configuration that has been defined for the embedded web application.
    This is mostly relevant when setting metadata externally, since the script for doing that does not
    have access to app.config.
    '''
    cp = SafeConfigParser()
    cp.read( input_filename )
    config_items_by_section = []
    for label, value in config_items:
        found = False
        # Attempt to determine the correct section for this configuration option.
        for section in cp.sections():
            if cp.has_option( section, label ):
                config_tuple = section, label, value
                config_items_by_section.append( config_tuple )
                found = True
                continue
        # Default to app:main if no section was found.
        if not found:
            config_tuple = 'app:main', label, value
            config_items_by_section.append( config_tuple )
    print( config_items_by_section )

    # Replace the default values with the provided configuration.
    for section, label, value in config_items_by_section:
        if cp.has_option( section, label ):
            cp.remove_option( section, label )
        cp.set( section, label, str( value ) )
    fh = open( output_filename, 'w' )
    cp.write( fh )
    fh.close()


def run_tests( test_config ):
    return run( test_config )


def __copy_database_template( source, db_path ):
    """
    Copy a 'clean' sqlite template database (from file or URL) to specified
    database path.
    """
    os.makedirs( os.path.dirname( db_path ) )
    if os.path.exists( source ):
        shutil.copy( source, db_path )
        assert os.path.exists( db_path )
    elif source.lower().startswith( ( "http://", "https://", "ftp://" ) ):
        urllib.urlretrieve( source, db_path )
    else:
        raise Exception( "Failed to copy database template from source %s" % source )


def main():
    # ---- Configuration ------------------------------------------------------
    galaxy_test_host = os.environ.get( 'GALAXY_TEST_HOST', default_galaxy_test_host )
    galaxy_test_port = os.environ.get( 'GALAXY_TEST_PORT', None )
    galaxy_test_save = os.environ.get( 'GALAXY_TEST_SAVE', None)
    agent_path = os.environ.get( 'GALAXY_TEST_TOOL_PATH', 'agents' )
    if 'HTTP_ACCEPT_LANGUAGE' not in os.environ:
        os.environ[ 'HTTP_ACCEPT_LANGUAGE' ] = default_galaxy_locales
    testing_migrated_agents = __check_arg( '-migrated' )
    testing_installed_agents = __check_arg( '-installed' )
    datatypes_conf_override = None

    if testing_migrated_agents or testing_installed_agents:
        # Store a jsonified dictionary of agent_id : GALAXY_TEST_FILE_DIR pairs.
        galaxy_agent_shed_test_file = 'shed_agents_dict'
        # We need the upload agent for functional tests, so we'll create a temporary agent panel config that defines it.
        fd, tmp_agent_panel_conf = tempfile.mkstemp()
        os.write( fd, '<?xml version="1.0"?>\n' )
        os.write( fd, '<agentbox>\n' )
        os.write( fd, '<agent file="data_source/upload.xml"/>\n' )
        os.write( fd, '</agentbox>\n' )
        os.close( fd )
        agent_config_file = tmp_agent_panel_conf
        galaxy_test_file_dir = None
        library_import_dir = None
        user_library_import_dir = None
        # Exclude all files except test_agentbox.py.
        ignore_files = ( re.compile( r'^test_[adghlmsu]*' ), re.compile( r'^test_ta*' ) )
    else:
        framework_agent_dir = os.path.join('test', 'functional', 'agents')
        framework_test = __check_arg( '-framework' )  # Run through suite of tests testing framework.
        if framework_test:
            agent_conf = os.path.join( framework_agent_dir, 'samples_agent_conf.xml' )
            datatypes_conf_override = os.path.join( framework_agent_dir, 'sample_datatypes_conf.xml' )
        else:
            # Use agent_conf.xml agentbox.
            agent_conf = None
            if __check_arg( '-with_framework_test_agents' ):
                agent_conf = "%s,%s" % ( 'config/agent_conf.xml.sample', os.path.join( framework_agent_dir, 'samples_agent_conf.xml' ) )
        test_dir = default_galaxy_test_file_dir
        agent_config_file = os.environ.get( 'GALAXY_TEST_TOOL_CONF', agent_conf )
        galaxy_test_file_dir = os.environ.get( 'GALAXY_TEST_FILE_DIR', test_dir )
        first_test_file_dir = galaxy_test_file_dir.split(",")[0]
        if not os.path.isabs( first_test_file_dir ):
            first_test_file_dir = os.path.join( os.getcwd(), first_test_file_dir )
        library_import_dir = first_test_file_dir
        import_dir = os.path.join( first_test_file_dir, 'users' )
        if os.path.exists(import_dir):
            user_library_import_dir = import_dir
        else:
            user_library_import_dir = None
        ignore_files = ()

    start_server = 'GALAXY_TEST_EXTERNAL' not in os.environ
    agent_data_table_config_path = None
    if os.path.exists( 'agent_data_table_conf.test.xml' ):
        # If explicitly defined tables for test, use those.
        agent_data_table_config_path = 'agent_data_table_conf.test.xml'
    else:
        # ... otherise find whatever Galaxy would use as the default and
        # the sample data for fucntional tests to that.
        default_agent_data_config = 'config/agent_data_table_conf.xml.sample'
        for agent_data_config in ['config/agent_data_table_conf.xml', 'agent_data_table_conf.xml' ]:
            if os.path.exists( agent_data_config ):
                default_agent_data_config = agent_data_config
        agent_data_table_config_path = '%s,test/functional/agent-data/sample_agent_data_tables.xml' % default_agent_data_config

    default_data_manager_config = 'config/data_manager_conf.xml.sample'
    for data_manager_config in ['config/data_manager_conf.xml', 'data_manager_conf.xml' ]:
        if os.path.exists( data_manager_config ):
            default_data_manager_config = data_manager_config
    data_manager_config_file = "%s,test/functional/agents/sample_data_manager_conf.xml" % default_data_manager_config
    shed_agent_data_table_config = 'config/shed_agent_data_table_conf.xml'
    agent_dependency_dir = os.environ.get( 'GALAXY_TOOL_DEPENDENCY_DIR', None )
    use_distributed_object_store = os.environ.get( 'GALAXY_USE_DISTRIBUTED_OBJECT_STORE', False )
    galaxy_test_tmp_dir = os.environ.get( 'GALAXY_TEST_TMP_DIR', None )
    if galaxy_test_tmp_dir is None:
        galaxy_test_tmp_dir = tempfile.mkdtemp()

    galaxy_job_conf_file = os.environ.get( 'GALAXY_TEST_JOB_CONF',
                                           os.path.join( galaxy_test_tmp_dir, 'test_job_conf.xml' ) )
    # Generate the job_conf.xml file.
    file( galaxy_job_conf_file, 'w' ).write( job_conf_xml )

    database_auto_migrate = False

    galaxy_test_proxy_port = None
    if start_server:
        tempdir = tempfile.mkdtemp( dir=galaxy_test_tmp_dir )
        # Configure the database path.
        if 'GALAXY_TEST_DBPATH' in os.environ:
            galaxy_db_path = os.environ[ 'GALAXY_TEST_DBPATH' ]
        else:
            galaxy_db_path = os.path.join( tempdir, 'database' )
        # Configure the paths Galaxy needs to  test agents.
        file_path = os.path.join( galaxy_db_path, 'files' )
        template_cache_path = os.path.join( galaxy_db_path, 'compiled_templates' )
        new_file_path = tempfile.mkdtemp( prefix='new_files_path_', dir=tempdir )
        job_working_directory = tempfile.mkdtemp( prefix='job_working_directory_', dir=tempdir )
        install_database_connection = os.environ.get( 'GALAXY_TEST_INSTALL_DBURI', None )
        if 'GALAXY_TEST_DBURI' in os.environ:
            database_connection = os.environ['GALAXY_TEST_DBURI']
        else:
            db_path = os.path.join( galaxy_db_path, 'universe.sqlite' )
            if 'GALAXY_TEST_DB_TEMPLATE' in os.environ:
                # Middle ground between recreating a completely new
                # database and pointing at existing database with
                # GALAXY_TEST_DBURI. The former requires a lot of setup
                # time, the latter results in test failures in certain
                # cases (namely agent shed tests expecting clean database).
                log.debug( "Copying database template from %s.", os.environ['GALAXY_TEST_DB_TEMPLATE'] )
                __copy_database_template(os.environ['GALAXY_TEST_DB_TEMPLATE'], db_path)
                database_auto_migrate = True
            database_connection = 'sqlite:///%s' % db_path
        kwargs = {}
        for dir in file_path, new_file_path, template_cache_path:
            try:
                if not os.path.exists( dir ):
                    os.makedirs( dir )
            except OSError:
                pass

    # Data Manager testing temp path
    # For storing Data Manager outputs and .loc files so that real ones don't get clobbered
    data_manager_test_tmp_path = tempfile.mkdtemp( prefix='data_manager_test_tmp', dir=galaxy_test_tmp_dir )
    galaxy_data_manager_data_path = tempfile.mkdtemp( prefix='data_manager_agent-data', dir=data_manager_test_tmp_path )

    # ---- Build Application --------------------------------------------------
    master_api_key = get_master_api_key()
    app = None
    if start_server:
        kwargs = dict( admin_users='test@bx.psu.edu',
                       api_allow_run_as='test@bx.psu.edu',
                       allow_library_path_paste=True,
                       allow_user_creation=True,
                       allow_user_deletion=True,
                       database_connection=database_connection,
                       database_auto_migrate=database_auto_migrate,
                       datatype_converters_config_file="datatype_converters_conf.xml.sample",
                       file_path=file_path,
                       id_secret='changethisinproductiontoo',
                       job_queue_workers=5,
                       job_working_directory=job_working_directory,
                       library_import_dir=library_import_dir,
                       log_destination="stdout",
                       new_file_path=new_file_path,
                       template_cache_path=template_cache_path,
                       running_functional_tests=True,
                       shed_agent_data_table_config=shed_agent_data_table_config,
                       template_path="templates",
                       test_conf="test.conf",
                       agent_config_file=agent_config_file,
                       agent_data_table_config_path=agent_data_table_config_path,
                       agent_path=agent_path,
                       galaxy_data_manager_data_path=galaxy_data_manager_data_path,
                       agent_parse_help=False,
                       update_integrated_agent_panel=False,
                       use_heartbeat=False,
                       user_library_import_dir=user_library_import_dir,
                       master_api_key=master_api_key,
                       use_tasked_jobs=True,
                       check_migrate_agents=False,
                       cleanup_job='onsuccess',
                       enable_beta_agent_formats=True,
                       auto_configure_logging=logging_config_file is None,
                       data_manager_config_file=data_manager_config_file )
        if install_database_connection is not None:
            kwargs[ 'install_database_connection' ] = install_database_connection
        if not database_connection.startswith( 'sqlite://' ):
            kwargs[ 'database_engine_option_max_overflow' ] = '20'
            kwargs[ 'database_engine_option_pool_size' ] = '10'
        if agent_dependency_dir is not None:
            kwargs[ 'agent_dependency_dir' ] = agent_dependency_dir
        if use_distributed_object_store:
            kwargs[ 'object_store' ] = 'distributed'
            kwargs[ 'distributed_object_store_config_file' ] = 'distributed_object_store_conf.xml.sample'
        if datatypes_conf_override:
            kwargs[ 'datatypes_config_file' ] = datatypes_conf_override
        # If the user has passed in a path for the .ini file, do not overwrite it.
        galaxy_config_file = os.environ.get( 'GALAXY_TEST_INI_FILE', None )
        if not galaxy_config_file:
            galaxy_config_file = os.path.join( galaxy_test_tmp_dir, 'functional_tests_wsgi.ini' )
            config_items = []
            for label in kwargs:
                config_tuple = label, kwargs[ label ]
                config_items.append( config_tuple )
            # Write a temporary file, based on config/galaxy.ini.sample, using the configuration options defined above.
            generate_config_file( 'config/galaxy.ini.sample', galaxy_config_file, config_items )
        # Set the global_conf[ '__file__' ] option to the location of the temporary .ini file, which gets passed to set_metadata.sh.
        kwargs[ 'global_conf' ] = get_webapp_global_conf()
        kwargs[ 'global_conf' ][ '__file__' ] = galaxy_config_file
        kwargs[ 'config_file' ] = galaxy_config_file
        kwargs = load_app_properties(
            kwds=kwargs
        )
        # Build the Universe Application
        app = UniverseApplication( **kwargs )
        database_contexts.galaxy_context = app.model.context
        log.info( "Embedded Universe application started" )

    # ---- Run webserver ------------------------------------------------------
    server = None

    if start_server:
        webapp = buildapp.app_factory( kwargs[ 'global_conf' ], app=app,
            use_translogger=False, static_enabled=STATIC_ENABLED )
        if galaxy_test_port is not None:
            server = httpserver.serve( webapp, host=galaxy_test_host, port=galaxy_test_port, start_loop=False )
        else:
            random.seed()
            for i in range( 0, 9 ):
                try:
                    galaxy_test_port = str( random.randint( default_galaxy_test_port_min, default_galaxy_test_port_max ) )
                    log.debug( "Attempting to serve app on randomly chosen port: %s" % galaxy_test_port )
                    server = httpserver.serve( webapp, host=galaxy_test_host, port=galaxy_test_port, start_loop=False )
                    break
                except socket.error, e:
                    if e[0] == 98:
                        continue
                    raise
            else:
                raise Exception( "Unable to open a port between %s and %s to start Galaxy server" % ( default_galaxy_test_port_min, default_galaxy_test_port_max ) )
        if galaxy_test_proxy_port:
            os.environ['GALAXY_TEST_PORT'] = galaxy_test_proxy_port
        else:
            os.environ['GALAXY_TEST_PORT'] = galaxy_test_port

        t = threading.Thread( target=server.serve_forever )
        t.start()
        # Test if the server is up
        for i in range( 10 ):
            conn = httplib.HTTPConnection( galaxy_test_host, galaxy_test_port )  # directly test the app, not the proxy
            conn.request( "GET", "/" )
            if conn.getresponse().status == 200:
                break
            time.sleep( 0.1 )
        else:
            raise Exception( "Test HTTP server did not return '200 OK' after 10 tries" )
        log.info( "Embedded web server started" )

    # ---- Find tests ---------------------------------------------------------
    if galaxy_test_proxy_port:
        log.info( "Functional tests will be run against %s:%s" % ( galaxy_test_host, galaxy_test_proxy_port ) )
    else:
        log.info( "Functional tests will be run against %s:%s" % ( galaxy_test_host, galaxy_test_port ) )
    success = False
    try:
        agent_configs = app.config.agent_configs
        # What requires these? Handy for (eg) functional tests to save outputs?
        if galaxy_test_save:
            os.environ[ 'GALAXY_TEST_SAVE' ] = galaxy_test_save
        # Pass in through script setenv, will leave a copy of ALL test validate files
        os.environ[ 'GALAXY_TEST_HOST' ] = galaxy_test_host

        def _run_functional_test( testing_shed_agents=None ):
            workflow_test = __check_arg( '-workflow', param=True )
            if workflow_test:
                import functional.workflow
                functional.workflow.WorkflowTestCase.workflow_test_file = workflow_test
                functional.workflow.WorkflowTestCase.master_api_key = master_api_key
                functional.workflow.WorkflowTestCase.user_api_key = get_user_api_key()
            data_manager_test = __check_arg( '-data_managers', param=False )
            if data_manager_test:
                import functional.test_data_managers
                functional.test_data_managers.data_managers = app.data_managers  # seems like a hack...
                functional.test_data_managers.build_tests(
                    tmp_dir=data_manager_test_tmp_path,
                    testing_shed_agents=testing_shed_agents,
                    master_api_key=master_api_key,
                    user_api_key=get_user_api_key(),
                )
            else:
                # We must make sure that functional.test_agentbox is always imported after
                # database_contexts.galaxy_content is set (which occurs in this method above).
                # If functional.test_agentbox is imported before database_contexts.galaxy_content
                # is set, sa_session will be None in all methods that use it.
                import functional.test_agentbox
                functional.test_agentbox.agentbox = app.agentbox
                # When testing data managers, do not test agentbox.
                functional.test_agentbox.build_tests(
                    app=app,
                    testing_shed_agents=testing_shed_agents,
                    master_api_key=master_api_key,
                    user_api_key=get_user_api_key(),
                )
            test_config = nose.config.Config( env=os.environ, ignoreFiles=ignore_files, plugins=nose.plugins.manager.DefaultPluginManager() )
            test_config.plugins.addPlugin( StructuredTestDataPlugin() )
            test_config.configure( sys.argv )
            result = run_tests( test_config )
            success = result.wasSuccessful()
            return success

        if testing_migrated_agents or testing_installed_agents:
            shed_agents_dict = {}
            if testing_migrated_agents:
                has_test_data, shed_agents_dict = parse_agent_panel_config( migrated_agent_panel_config, shed_agents_dict )
            elif testing_installed_agents:
                for shed_agent_config in installed_agent_panel_configs:
                    has_test_data, shed_agents_dict = parse_agent_panel_config( shed_agent_config, shed_agents_dict )
            # Persist the shed_agents_dict to the galaxy_agent_shed_test_file.
            shed_agents_file = open( galaxy_agent_shed_test_file, 'w' )
            shed_agents_file.write( dumps( shed_agents_dict ) )
            shed_agents_file.close()
            if not os.path.isabs( galaxy_agent_shed_test_file ):
                galaxy_agent_shed_test_file = os.path.join( os.getcwd(), galaxy_agent_shed_test_file )
            os.environ[ 'GALAXY_TOOL_SHED_TEST_FILE' ] = galaxy_agent_shed_test_file
            if testing_installed_agents:
                # Eliminate the migrated_agent_panel_config from the app's agent_configs, append the list of installed_agent_panel_configs,
                # and reload the app's agentbox.
                relative_migrated_agent_panel_config = os.path.join( app.config.root, migrated_agent_panel_config )
                if relative_migrated_agent_panel_config in agent_configs:
                    agent_configs.remove( relative_migrated_agent_panel_config )
                for installed_agent_panel_config in installed_agent_panel_configs:
                    agent_configs.append( installed_agent_panel_config )
                app.agentbox = agents.AgentBox( agent_configs, app.config.agent_path, app )
            success = _run_functional_test( testing_shed_agents=True )
            try:
                os.unlink( tmp_agent_panel_conf )
            except:
                log.info( "Unable to remove temporary file: %s" % tmp_agent_panel_conf )
            try:
                os.unlink( galaxy_agent_shed_test_file )
            except:
                log.info( "Unable to remove file: %s" % galaxy_agent_shed_test_file )
        else:
            if galaxy_test_file_dir:
                os.environ[ 'GALAXY_TEST_FILE_DIR' ] = galaxy_test_file_dir
            success = _run_functional_test( )
    except:
        log.exception( "Failure running tests" )

    log.info( "Shutting down" )
    # ---- Tear down -----------------------------------------------------------
    if server:
        log.info( "Shutting down embedded web server" )
        server.server_close()
        server = None
        log.info( "Embedded web server stopped" )
    if app:
        log.info( "Shutting down app" )
        app.shutdown()
        app = None
        log.info( "Embedded Universe application stopped" )
    try:
        if os.path.exists( tempdir ) and 'GALAXY_TEST_NO_CLEANUP' not in os.environ:
            log.info( "Cleaning up temporary files in %s" % tempdir )
            shutil.rmtree( tempdir )
        else:
            log.info( "GALAXY_TEST_NO_CLEANUP is on. Temporary files in %s" % tempdir )
    except:
        pass
    if success:
        return 0
    else:
        return 1


def __check_arg( name, param=False ):
    try:
        index = sys.argv.index( name )
        del sys.argv[ index ]
        if param:
            ret_val = sys.argv[ index ]
            del sys.argv[ index ]
        else:
            ret_val = True
    except ValueError:
        ret_val = False
    return ret_val

if __name__ == "__main__":
    sys.exit( main() )
