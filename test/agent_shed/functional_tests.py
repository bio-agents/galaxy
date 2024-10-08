#!/usr/bin/env python
from __future__ import absolute_import

import httplib
import logging
import os
import random
import shutil
import socket
import string
import sys
import tempfile
import threading
import time
import urllib

galaxy_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir))
agent_shed_home_directory = os.path.join( galaxy_root, 'test', 'agent_shed' )
default_agent_shed_test_file_dir = os.path.join( agent_shed_home_directory, 'test_data' )
# Here's the directory where everything happens.  Temporary directories are created within this directory to contain
# the hgweb.config file, the database, new repositories, etc.  Since the agent shed browses repository contents via HTTP,
# the full path to the temporary directroy wher eht repositories are located cannot contain invalid url characters.
agent_shed_test_tmp_dir = os.path.join( agent_shed_home_directory, 'tmp' )
os.environ[ 'TOOL_SHED_TEST_TMP_DIR' ] = agent_shed_test_tmp_dir
# Need to remove this directory from sys.path
sys.path[0:1] = [ os.path.join( galaxy_root, "lib" ), os.path.join( galaxy_root, "test" ) ]

from paste import httpserver
import nose.config
import nose.core
import nose.loader
import nose.plugins.manager

# This is for the agent shed application.
from galaxy.webapps.agent_shed import buildapp as agentshedbuildapp
from galaxy.webapps.agent_shed.app import UniverseApplication as AgentshedUniverseApplication
# This is for the galaxy application.
from galaxy.app import UniverseApplication as GalaxyUniverseApplication
from galaxy.util import asbool
from galaxy.web import buildapp as galaxybuildapp

from base import nose_util
from functional import database_contexts

log = logging.getLogger( "agent_shed_functional_tests.py" )

default_agent_shed_test_host = "localhost"
default_agent_shed_test_port_min = 8000
default_agent_shed_test_port_max = 8999
default_agent_shed_locales = 'en'
default_galaxy_test_port_min = 9000
default_galaxy_test_port_max = 9999
default_galaxy_test_host = 'localhost'

# Use separate databases for Galaxy and agent shed install info by default,
# set GALAXY_TEST_INSTALL_DB_MERGED to True to revert to merged databases
# behavior.
default_install_db_merged = False

# should this serve static resources (scripts, images, styles, etc.)
STATIC_ENABLED = True


def get_static_settings():
    """Returns dictionary of the settings necessary for a galaxy App
    to be wrapped in the static middleware.

    This mainly consists of the filesystem locations of url-mapped
    static resources.
    """
    static_dir = os.path.join( galaxy_root, 'static' )
    # TODO: these should be copied from galaxy.ini
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

agent_sheds_conf_xml_template = '''<?xml version="1.0"?>
<agent_sheds>
    <agent_shed name="Galaxy main agent shed" url="http://agentshed.g2.bx.psu.edu/"/>
    <agent_shed name="Galaxy test agent shed" url="http://testagentshed.g2.bx.psu.edu/"/>
    <agent_shed name="Embedded agent shed for functional tests" url="http://${shed_url}:${shed_port}/"/>
</agent_sheds>
'''

shed_agent_conf_xml_template = '''<?xml version="1.0"?>
<agentbox agent_path="${shed_agent_path}">
</agentbox>
'''

agent_conf_xml = '''<?xml version="1.0"?>
<agentbox>
    <section name="Get Data" id="getext">
        <agent file="data_source/upload.xml"/>
    </section>
</agentbox>
'''

agent_data_table_conf_xml_template = '''<?xml version="1.0"?>
<tables>
</tables>
'''

shed_data_manager_conf_xml_template = '''<?xml version="1.0"?>
<data_managers>
</data_managers>
'''


def run_tests( test_config ):
    return nose_util.run( test_config )


def main():
    # ---- Configuration ------------------------------------------------------
    agent_shed_test_host = os.environ.get( 'TOOL_SHED_TEST_HOST', default_agent_shed_test_host )
    agent_shed_test_port = os.environ.get( 'TOOL_SHED_TEST_PORT', None )
    galaxy_test_host = os.environ.get( 'GALAXY_TEST_HOST', default_galaxy_test_host )
    galaxy_test_port = os.environ.get( 'GALAXY_TEST_PORT', None )
    agent_path = os.environ.get( 'TOOL_SHED_TEST_TOOL_PATH', 'agents' )
    if 'HTTP_ACCEPT_LANGUAGE' not in os.environ:
        os.environ[ 'HTTP_ACCEPT_LANGUAGE' ] = default_agent_shed_locales
    agent_shed_test_file_dir = os.environ.get( 'TOOL_SHED_TEST_FILE_DIR', default_agent_shed_test_file_dir )
    if not os.path.isabs( agent_shed_test_file_dir ):
        agent_shed_test_file_dir = agent_shed_test_file_dir
    ignore_files = ()
    agent_dependency_dir = os.environ.get( 'TOOL_SHED_TOOL_DEPENDENCY_DIR', None )
    use_distributed_object_store = os.environ.get( 'TOOL_SHED_USE_DISTRIBUTED_OBJECT_STORE', False )
    if not os.path.isdir( agent_shed_test_tmp_dir ):
        os.mkdir( agent_shed_test_tmp_dir )
    agent_shed_test_proxy_port = None
    galaxy_test_proxy_port = None
    if 'TOOL_SHED_TEST_DBPATH' in os.environ:
        shed_db_path = os.environ[ 'TOOL_SHED_TEST_DBPATH' ]
    else:
        tempdir = tempfile.mkdtemp( dir=agent_shed_test_tmp_dir )
        shed_db_path = os.path.join( tempdir, 'database' )
    shed_agent_data_table_conf_file = os.environ.get( 'TOOL_SHED_TEST_TOOL_DATA_TABLE_CONF', os.path.join( agent_shed_test_tmp_dir, 'shed_agent_data_table_conf.xml' ) )
    galaxy_shed_data_manager_conf_file = os.environ.get( 'GALAXY_SHED_DATA_MANAGER_CONF', os.path.join( agent_shed_test_tmp_dir, 'test_shed_data_manager_conf.xml' ) )
    galaxy_agent_data_table_conf_file = os.environ.get( 'GALAXY_TEST_TOOL_DATA_TABLE_CONF', os.path.join( agent_shed_test_tmp_dir, 'agent_data_table_conf.xml' ) )
    galaxy_agent_conf_file = os.environ.get( 'GALAXY_TEST_TOOL_CONF', os.path.join( agent_shed_test_tmp_dir, 'test_agent_conf.xml' ) )
    galaxy_shed_agent_conf_file = os.environ.get( 'GALAXY_TEST_SHED_TOOL_CONF', os.path.join( agent_shed_test_tmp_dir, 'test_shed_agent_conf.xml' ) )
    galaxy_migrated_agent_conf_file = os.environ.get( 'GALAXY_TEST_MIGRATED_TOOL_CONF', os.path.join( agent_shed_test_tmp_dir, 'test_migrated_agent_conf.xml' ) )
    galaxy_agent_sheds_conf_file = os.environ.get( 'GALAXY_TEST_TOOL_SHEDS_CONF', os.path.join( agent_shed_test_tmp_dir, 'test_sheds_conf.xml' ) )
    if 'GALAXY_TEST_TOOL_DATA_PATH' in os.environ:
        agent_data_path = os.environ.get( 'GALAXY_TEST_TOOL_DATA_PATH' )
    else:
        agent_data_path = tempfile.mkdtemp( dir=agent_shed_test_tmp_dir )
        os.environ[ 'GALAXY_TEST_TOOL_DATA_PATH' ] = agent_data_path
    if 'GALAXY_TEST_DBPATH' in os.environ:
        galaxy_db_path = os.environ[ 'GALAXY_TEST_DBPATH' ]
    else:
        tempdir = tempfile.mkdtemp( dir=agent_shed_test_tmp_dir )
        galaxy_db_path = os.path.join( tempdir, 'database' )
    shed_file_path = os.path.join( shed_db_path, 'files' )
    galaxy_file_path = os.path.join( galaxy_db_path, 'files' )
    hgweb_config_file_path = tempfile.mkdtemp( dir=agent_shed_test_tmp_dir )
    new_repos_path = tempfile.mkdtemp( dir=agent_shed_test_tmp_dir )
    galaxy_tempfiles = tempfile.mkdtemp( dir=agent_shed_test_tmp_dir )
    galaxy_shed_agent_path = tempfile.mkdtemp( dir=agent_shed_test_tmp_dir )
    galaxy_migrated_agent_path = tempfile.mkdtemp( dir=agent_shed_test_tmp_dir )
    galaxy_agent_dependency_dir = tempfile.mkdtemp( dir=agent_shed_test_tmp_dir )
    os.environ[ 'GALAXY_TEST_TOOL_DEPENDENCY_DIR' ] = galaxy_agent_dependency_dir
    hgweb_config_dir = hgweb_config_file_path
    os.environ[ 'TEST_HG_WEB_CONFIG_DIR' ] = hgweb_config_dir
    print "Directory location for hgweb.config:", hgweb_config_dir
    if 'TOOL_SHED_TEST_DBURI' in os.environ:
        agentshed_database_connection = os.environ[ 'TOOL_SHED_TEST_DBURI' ]
    else:
        agentshed_database_connection = 'sqlite:///' + os.path.join( shed_db_path, 'community_test.sqlite' )
    galaxy_database_auto_migrate = False
    if 'GALAXY_TEST_DBURI' in os.environ:
        galaxy_database_connection = os.environ[ 'GALAXY_TEST_DBURI' ]
    else:
        db_path = os.path.join( galaxy_db_path, 'universe.sqlite' )
        if 'GALAXY_TEST_DB_TEMPLATE' in os.environ:
            # Middle ground between recreating a completely new
            # database and pointing at existing database with
            # GALAXY_TEST_DBURI. The former requires a lot of setup
            # time, the latter results in test failures in certain
            # cases (namely agent shed tests expecting clean database).
            __copy_database_template(os.environ['GALAXY_TEST_DB_TEMPLATE'], db_path)
            galaxy_database_auto_migrate = True
        if not os.path.exists(galaxy_db_path):
            os.makedirs(galaxy_db_path)
        galaxy_database_connection = 'sqlite:///%s' % db_path
    if 'GALAXY_TEST_INSTALL_DBURI' in os.environ:
        install_galaxy_database_connection = os.environ[ 'GALAXY_TEST_INSTALL_DBURI' ]
    elif asbool( os.environ.get( 'GALAXY_TEST_INSTALL_DB_MERGED', default_install_db_merged ) ):
        install_galaxy_database_connection = galaxy_database_connection
    else:
        install_galaxy_db_path = os.path.join( galaxy_db_path, 'install.sqlite' )
        install_galaxy_database_connection = 'sqlite:///%s' % install_galaxy_db_path
    agent_shed_global_conf = get_webapp_global_conf()
    agent_shed_global_conf[ '__file__' ] = 'agent_shed_wsgi.ini.sample'
    kwargs = dict( admin_users='test@bx.psu.edu',
                   allow_user_creation=True,
                   allow_user_deletion=True,
                   database_connection=agentshed_database_connection,
                   datatype_converters_config_file='datatype_converters_conf.xml.sample',
                   file_path=shed_file_path,
                   global_conf=agent_shed_global_conf,
                   hgweb_config_dir=hgweb_config_dir,
                   job_queue_workers=5,
                   id_secret='changethisinproductiontoo',
                   log_destination="stdout",
                   new_file_path=new_repos_path,
                   running_functional_tests=True,
                   shed_agent_data_table_config=shed_agent_data_table_conf_file,
                   smtp_server='smtp.dummy.string.tld',
                   email_from='functional@localhost',
                   template_path='templates',
                   agent_path=agent_path,
                   agent_parse_help=False,
                   agent_data_table_config_path=galaxy_agent_data_table_conf_file,
                   use_heartbeat=False )
    for dir in [ agent_shed_test_tmp_dir ]:
        try:
            os.makedirs( dir )
        except OSError:
            pass

    print "Agent shed database connection:", agentshed_database_connection
    print "Galaxy database connection:", galaxy_database_connection

    # Generate the agent_data_table_conf.xml file.
    file( galaxy_agent_data_table_conf_file, 'w' ).write( agent_data_table_conf_xml_template )
    # Generate the shed_agent_data_table_conf.xml file.
    file( shed_agent_data_table_conf_file, 'w' ).write( agent_data_table_conf_xml_template )
    os.environ[ 'TOOL_SHED_TEST_TOOL_DATA_TABLE_CONF' ] = shed_agent_data_table_conf_file
    # ---- Build Agent Shed Application --------------------------------------------------
    agentshedapp = None
#    if not agentshed_database_connection.startswith( 'sqlite://' ):
#        kwargs[ 'database_engine_option_max_overflow' ] = '20'
    if agent_dependency_dir is not None:
        kwargs[ 'agent_dependency_dir' ] = agent_dependency_dir
    if use_distributed_object_store:
        kwargs[ 'object_store' ] = 'distributed'
        kwargs[ 'distributed_object_store_config_file' ] = 'distributed_object_store_conf.xml.sample'

    kwargs[ 'global_conf' ] = agent_shed_global_conf

    if not agentshed_database_connection.startswith( 'sqlite://' ):
            kwargs[ 'database_engine_option_pool_size' ] = '10'

    agentshedapp = AgentshedUniverseApplication( **kwargs )
    database_contexts.agent_shed_context = agentshedapp.model.context
    log.info( "Embedded Agentshed application started" )

    # ---- Run agent shed webserver ------------------------------------------------------
    agent_shed_server = None
    agent_shed_global_conf[ 'database_connection' ] = agentshed_database_connection
    agentshedwebapp = agentshedbuildapp.app_factory( agent_shed_global_conf,
                                                   use_translogger=False,
                                                   static_enabled=True,
                                                   app=agentshedapp )
    if agent_shed_test_port is not None:
        agent_shed_server = httpserver.serve( agentshedwebapp, host=agent_shed_test_host, port=agent_shed_test_port, start_loop=False )
    else:
        random.seed()
        for i in range( 0, 9 ):
            try:
                agent_shed_test_port = str( random.randint( default_agent_shed_test_port_min, default_agent_shed_test_port_max ) )
                log.debug( "Attempting to serve app on randomly chosen port: %s" % agent_shed_test_port )
                agent_shed_server = httpserver.serve( agentshedwebapp, host=agent_shed_test_host, port=agent_shed_test_port, start_loop=False )
                break
            except socket.error, e:
                if e[0] == 98:
                    continue
                raise
        else:
            raise Exception( "Unable to open a port between %s and %s to start Galaxy server" % ( default_agent_shed_test_port_min, default_agent_shed_test_port_max ) )
    if agent_shed_test_proxy_port:
        os.environ[ 'TOOL_SHED_TEST_PORT' ] = agent_shed_test_proxy_port
    else:
        os.environ[ 'TOOL_SHED_TEST_PORT' ] = agent_shed_test_port
    t = threading.Thread( target=agent_shed_server.serve_forever )
    t.start()
    # Test if the server is up
    for i in range( 10 ):
        # Directly test the app, not the proxy.
        conn = httplib.HTTPConnection( agent_shed_test_host, agent_shed_test_port )
        conn.request( "GET", "/" )
        if conn.getresponse().status == 200:
            break
        time.sleep( 0.1 )
    else:
        raise Exception( "Test HTTP server did not return '200 OK' after 10 tries" )
    log.info( "Embedded web server started" )

    # ---- Optionally start up a Galaxy instance ------------------------------------------------------
    if 'TOOL_SHED_TEST_OMIT_GALAXY' not in os.environ:
        # Generate the agent_conf.xml file.
        file( galaxy_agent_conf_file, 'w' ).write( agent_conf_xml )
        # Generate the shed_agent_conf.xml file.
        agent_sheds_conf_template_parser = string.Template( agent_sheds_conf_xml_template )
        agent_sheds_conf_xml = agent_sheds_conf_template_parser.safe_substitute( shed_url=agent_shed_test_host, shed_port=agent_shed_test_port )
        file( galaxy_agent_sheds_conf_file, 'w' ).write( agent_sheds_conf_xml )
        # Generate the agent_sheds_conf.xml file.
        shed_agent_conf_template_parser = string.Template( shed_agent_conf_xml_template )
        shed_agent_conf_xml = shed_agent_conf_template_parser.safe_substitute( shed_agent_path=galaxy_shed_agent_path )
        file( galaxy_shed_agent_conf_file, 'w' ).write( shed_agent_conf_xml )
        # Generate the migrated_agent_conf.xml file.
        migrated_agent_conf_xml = shed_agent_conf_template_parser.safe_substitute( shed_agent_path=galaxy_migrated_agent_path )
        file( galaxy_migrated_agent_conf_file, 'w' ).write( migrated_agent_conf_xml )
        os.environ[ 'GALAXY_TEST_SHED_TOOL_CONF' ] = galaxy_shed_agent_conf_file
        # Generate shed_data_manager_conf.xml
        if not os.environ.get( 'GALAXY_SHED_DATA_MANAGER_CONF' ):
            open( galaxy_shed_data_manager_conf_file, 'wb' ).write( shed_data_manager_conf_xml_template )
        galaxy_global_conf = get_webapp_global_conf()
        galaxy_global_conf[ '__file__' ] = 'config/galaxy.ini.sample'

        kwargs = dict( allow_user_creation=True,
                       allow_user_deletion=True,
                       admin_users='test@bx.psu.edu',
                       allow_library_path_paste=True,
                       install_database_connection=install_galaxy_database_connection,
                       database_connection=galaxy_database_connection,
                       database_auto_migrate=galaxy_database_auto_migrate,
                       datatype_converters_config_file="datatype_converters_conf.xml.sample",
                       check_migrate_agents=False,
                       enable_agent_shed_check=True,
                       file_path=galaxy_file_path,
                       global_conf=galaxy_global_conf,
                       hours_between_check=0.001,
                       id_secret='changethisinproductiontoo',
                       job_queue_workers=5,
                       log_destination="stdout",
                       migrated_agents_config=galaxy_migrated_agent_conf_file,
                       new_file_path=galaxy_tempfiles,
                       running_functional_tests=True,
                       shed_data_manager_config_file=galaxy_shed_data_manager_conf_file,
                       shed_agent_data_table_config=shed_agent_data_table_conf_file,
                       shed_agent_path=galaxy_shed_agent_path,
                       template_path="templates",
                       agent_data_path=agent_data_path,
                       agent_dependency_dir=galaxy_agent_dependency_dir,
                       agent_path=agent_path,
                       agent_config_file=[ galaxy_agent_conf_file, galaxy_shed_agent_conf_file ],
                       agent_sheds_config_file=galaxy_agent_sheds_conf_file,
                       agent_parse_help=False,
                       agent_data_table_config_path=galaxy_agent_data_table_conf_file,
                       update_integrated_agent_panel=False,
                       use_heartbeat=False )

        # ---- Build Galaxy Application --------------------------------------------------
        if not galaxy_database_connection.startswith( 'sqlite://' ) and not install_galaxy_database_connection.startswith( 'sqlite://' ):
            kwargs[ 'database_engine_option_pool_size' ] = '10'
            kwargs[ 'database_engine_option_max_overflow' ] = '20'
        galaxyapp = GalaxyUniverseApplication( **kwargs )

        log.info( "Embedded Galaxy application started" )

        # ---- Run galaxy webserver ------------------------------------------------------
        galaxy_server = None
        galaxy_global_conf[ 'database_file' ] = galaxy_database_connection
        galaxywebapp = galaxybuildapp.app_factory( galaxy_global_conf,
                                                   use_translogger=False,
                                                   static_enabled=True,
                                                   app=galaxyapp )
        database_contexts.galaxy_context = galaxyapp.model.context
        database_contexts.install_context = galaxyapp.install_model.context
        if galaxy_test_port is not None:
            galaxy_server = httpserver.serve( galaxywebapp, host=galaxy_test_host, port=galaxy_test_port, start_loop=False )
        else:
            random.seed()
            for i in range( 0, 9 ):
                try:
                    galaxy_test_port = str( random.randint( default_galaxy_test_port_min, default_galaxy_test_port_max ) )
                    log.debug( "Attempting to serve app on randomly chosen port: %s" % galaxy_test_port )
                    galaxy_server = httpserver.serve( galaxywebapp, host=galaxy_test_host, port=galaxy_test_port, start_loop=False )
                    break
                except socket.error, e:
                    if e[0] == 98:
                        continue
                    raise
            else:
                raise Exception( "Unable to open a port between %s and %s to start Galaxy server" %
                                 ( default_galaxy_test_port_min, default_galaxy_test_port_max ) )
        if galaxy_test_proxy_port:
            os.environ[ 'GALAXY_TEST_PORT' ] = galaxy_test_proxy_port
        else:
            os.environ[ 'GALAXY_TEST_PORT' ] = galaxy_test_port
        t = threading.Thread( target=galaxy_server.serve_forever )
        t.start()
        # Test if the server is up
        for i in range( 10 ):
            # Directly test the app, not the proxy.
            conn = httplib.HTTPConnection( galaxy_test_host, galaxy_test_port )
            conn.request( "GET", "/" )
            if conn.getresponse().status == 200:
                break
            time.sleep( 0.1 )
        else:
            raise Exception( "Test HTTP server did not return '200 OK' after 10 tries" )
        log.info( "Embedded galaxy web server started" )
    # ---- Find tests ---------------------------------------------------------
    if agent_shed_test_proxy_port:
        log.info( "Functional tests will be run against %s:%s" % ( agent_shed_test_host, agent_shed_test_proxy_port ) )
    else:
        log.info( "Functional tests will be run against %s:%s" % ( agent_shed_test_host, agent_shed_test_port ) )
    if galaxy_test_proxy_port:
        log.info( "Galaxy tests will be run against %s:%s" % ( galaxy_test_host, galaxy_test_proxy_port ) )
    else:
        log.info( "Galaxy tests will be run against %s:%s" % ( galaxy_test_host, galaxy_test_port ) )
    success = False
    try:
        # Pass in through script set env, will leave a copy of ALL test validate files.
        os.environ[ 'TOOL_SHED_TEST_HOST' ] = agent_shed_test_host
        os.environ[ 'GALAXY_TEST_HOST' ] = galaxy_test_host
        if agent_shed_test_file_dir:
            os.environ[ 'TOOL_SHED_TEST_FILE_DIR' ] = agent_shed_test_file_dir
        test_config = nose.config.Config( env=os.environ, ignoreFiles=ignore_files, plugins=nose.plugins.manager.DefaultPluginManager() )
        test_config.configure( sys.argv )
        # Run the tests.
        result = run_tests( test_config )
        success = result.wasSuccessful()
    except:
        log.exception( "Failure running tests" )

    log.info( "Shutting down" )
    # ---- Tear down -----------------------------------------------------------
    if agent_shed_server:
        log.info( "Shutting down embedded web server" )
        agent_shed_server.server_close()
        agent_shed_server = None
        log.info( "Embedded web server stopped" )
    if agentshedapp:
        log.info( "Shutting down agent shed app" )
        agentshedapp.shutdown()
        agentshedapp = None
        log.info( "Embedded agent shed application stopped" )
    if 'TOOL_SHED_TEST_OMIT_GALAXY' not in os.environ:
        if galaxy_server:
            log.info( "Shutting down galaxy web server" )
            galaxy_server.server_close()
            galaxy_server = None
            log.info( "Embedded galaxy server stopped" )
        if galaxyapp:
            log.info( "Shutting down galaxy app" )
            galaxyapp.shutdown()
            galaxyapp = None
            log.info( "Embedded galaxy application stopped" )
    if 'TOOL_SHED_TEST_NO_CLEANUP' not in os.environ:
        try:
            for dir in [ agent_shed_test_tmp_dir ]:
                if os.path.exists( dir ):
                    log.info( "Cleaning up temporary files in %s" % dir )
                    shutil.rmtree( dir )
        except:
            pass
    if success:
        return 0
    else:
        return 1


def __copy_database_template( source, db_path ):
    """
    Copy a 'clean' sqlite template database (from file or URL) to specified
    database path.
    """
    os.makedirs( os.path.dirname( db_path ) )
    if os.path.exists( source ):
        shutil.copy( source, db_path )
        assert os.path.exists( db_path )
    elif source.startswith("http"):
        urllib.urlretrieve( source, db_path )
    else:
        raise Exception( "Failed to copy database template from source %s" % source )


if __name__ == "__main__":
    try:
        sys.exit( main() )
    except Exception, e:
        log.exception( str( e ) )
        exit(1)
