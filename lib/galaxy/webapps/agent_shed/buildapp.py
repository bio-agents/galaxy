"""
Provides factory methods to assemble the Galaxy web application
"""
import atexit
import logging
import os

from inspect import isclass
from paste import httpexceptions
from galaxy.util import asbool

import galaxy.webapps.agent_shed.model
import galaxy.webapps.agent_shed.model.mapping
import galaxy.web.framework.webapp
from galaxy.webapps.util import build_template_error_formatters
from galaxy.webapps.agent_shed.framework.middleware import hg
from galaxy import util
from galaxy.config import process_is_uwsgi
from galaxy.util.properties import load_app_properties

log = logging.getLogger( __name__ )


class CommunityWebApplication( galaxy.web.framework.webapp.WebApplication ):
    pass


def add_ui_controllers( webapp, app ):
    """
    Search for controllers in the 'galaxy.webapps.controllers' module and add
    them to the webapp.
    """
    from galaxy.web.base.controller import BaseUIController
    import galaxy.webapps.agent_shed.controllers
    controller_dir = galaxy.webapps.agent_shed.controllers.__path__[0]
    for fname in os.listdir( controller_dir ):
        if not fname.startswith( "_" ) and fname.endswith( ".py" ):
            name = fname[:-3]
            module_name = "galaxy.webapps.agent_shed.controllers." + name
            module = __import__( module_name )
            for comp in module_name.split( "." )[1:]:
                module = getattr( module, comp )
            # Look for a controller inside the modules
            for key in dir( module ):
                T = getattr( module, key )
                if isclass( T ) and T is not BaseUIController and issubclass( T, BaseUIController ):
                    webapp.add_ui_controller( name, T( app ) )


def app_factory( global_conf, **kwargs ):
    """Return a wsgi application serving the root object"""
    # Create the Galaxy agent shed application unless passed in
    kwargs = load_app_properties(
        kwds=kwargs,
        config_prefix='TOOL_SHED_CONFIG_'
    )
    if 'app' in kwargs:
        app = kwargs.pop( 'app' )
    else:
        try:
            from galaxy.webapps.agent_shed.app import UniverseApplication
            app = UniverseApplication( global_conf=global_conf, **kwargs )
        except:
            import traceback
            import sys
            traceback.print_exc()
            sys.exit( 1 )
    atexit.register( app.shutdown )
    # Create the universe WSGI application
    webapp = CommunityWebApplication( app, session_cookie='galaxycommunitysession', name="agent_shed" )
    add_ui_controllers( webapp, app )
    webapp.add_route( '/view/{owner}', controller='repository', action='sharable_owner' )
    webapp.add_route( '/view/{owner}/{name}', controller='repository', action='sharable_repository' )
    webapp.add_route( '/view/{owner}/{name}/{changeset_revision}', controller='repository', action='sharable_repository_revision' )
    # Handle displaying agent help images and README file images for agents contained in repositories.
    webapp.add_route( '/repository/static/images/{repository_id}/{image_file:.+?}',
                      controller='repository',
                      action='display_image_in_repository',
                      repository_id=None,
                      image_file=None )
    webapp.add_route( '/{controller}/{action}', action='index' )
    webapp.add_route( '/{action}', controller='repository', action='index' )
    webapp.add_route( '/repos/*path_info', controller='hg', action='handle_request', path_info='/' )
    # Add the web API.  # A good resource for RESTful services - http://routes.readthedocs.org/en/latest/restful.html
    webapp.add_api_controllers( 'galaxy.webapps.agent_shed.api', app )
    webapp.mapper.connect( 'api_key_retrieval',
                           '/api/authenticate/baseauth/',
                           controller='authenticate',
                           action='get_agent_shed_api_key',
                           conditions=dict( method=[ "GET" ] ) )
    webapp.mapper.connect( 'group',
                           '/api/groups/',
                           controller='groups',
                           action='index',
                           conditions=dict( method=[ "GET" ] ) )
    webapp.mapper.connect( 'group',
                           '/api/groups/',
                           controller='groups',
                           action='create',
                           conditions=dict( method=[ "POST" ] ) )
    webapp.mapper.connect( 'group',
                           '/api/groups/{encoded_id}',
                           controller='groups',
                           action='show',
                           conditions=dict( method=[ "GET" ] ) )
    webapp.mapper.resource( 'category',
                            'categories',
                            controller='categories',
                            name_prefix='category_',
                            path_prefix='/api',
                            parent_resources=dict( member_name='category', collection_name='categories' ) )
    webapp.mapper.resource( 'repository',
                            'repositories',
                            controller='repositories',
                            collection={ 'add_repository_registry_entry' : 'POST',
                                         'get_repository_revision_install_info' : 'GET',
                                         'get_ordered_installable_revisions' : 'GET',
                                         'remove_repository_registry_entry' : 'POST',
                                         'repository_ids_for_setting_metadata' : 'GET',
                                         'reset_metadata_on_repositories' : 'POST',
                                         'reset_metadata_on_repository' : 'POST' },
                            name_prefix='repository_',
                            path_prefix='/api',
                            new={ 'import_capsule' : 'POST' },
                            parent_resources=dict( member_name='repository', collection_name='repositories' ) )
    webapp.mapper.resource( 'repository_revision',
                            'repository_revisions',
                            member={ 'repository_dependencies' : 'GET',
                                     'export' : 'POST' },
                            controller='repository_revisions',
                            name_prefix='repository_revision_',
                            path_prefix='/api',
                            parent_resources=dict( member_name='repository_revision', collection_name='repository_revisions' ) )
    webapp.mapper.resource( 'user',
                            'users',
                            controller='users',
                            name_prefix='user_',
                            path_prefix='/api',
                            parent_resources=dict( member_name='user', collection_name='users' ) )
    webapp.mapper.connect( 'update_repository',
                           '/api/repositories/{id}',
                           controller='repositories',
                           action='update',
                           conditions=dict( method=[ "PATCH", "PUT" ] ) )
    webapp.mapper.connect( 'repository_create_changeset_revision',
                           '/api/repositories/{id}/changeset_revision',
                           controller='repositories',
                           action='create_changeset_revision',
                           conditions=dict( method=[ "POST" ] ) )
    webapp.mapper.connect( 'create_repository',
                           '/api/repositories',
                           controller='repositories',
                           action='create',
                           conditions=dict( method=[ "POST" ] ) )
    webapp.mapper.connect( 'agents',
                           '/api/agents',
                           controller='agents',
                           action='index',
                           conditions=dict( method=[ "GET" ] ) )
    webapp.mapper.connect( "version", "/api/version", controller="configuration", action="version", conditions=dict( method=[ "GET" ] ) )

    webapp.finalize_config()
    # Wrap the webapp in some useful middleware
    if kwargs.get( 'middleware', True ):
        webapp = wrap_in_middleware( webapp, global_conf, **kwargs )
    if asbool( kwargs.get( 'static_enabled', True) ):
        if process_is_uwsgi:
            log.error("Static middleware is enabled in your configuration but this is a uwsgi process.  Refusing to wrap in static middleware.")
        else:
            webapp = wrap_in_static( webapp, global_conf, **kwargs )
    # Close any pooled database connections before forking
    try:
        galaxy.webapps.agent_shed.model.mapping.metadata.bind.dispose()
    except:
        log.exception("Unable to dispose of pooled agent_shed model database connections.")
    # Return
    return webapp


def wrap_in_middleware( app, global_conf, **local_conf ):
    """Based on the configuration wrap `app` in a set of common and useful middleware."""
    # Merge the global and local configurations
    conf = global_conf.copy()
    conf.update( local_conf )
    debug = asbool( conf.get( 'debug', False ) )
    # First put into place httpexceptions, which must be most closely
    # wrapped around the application (it can interact poorly with
    # other middleware):
    app = httpexceptions.make_middleware( app, conf )
    log.debug( "Enabling 'httpexceptions' middleware" )
    # If we're using remote_user authentication, add middleware that
    # protects Galaxy from improperly configured authentication in the
    # upstream server
    if asbool(conf.get( 'use_remote_user', False )):
        from galaxy.webapps.agent_shed.framework.middleware.remoteuser import RemoteUser
        app = RemoteUser( app, maildomain=conf.get( 'remote_user_maildomain', None ),
                          display_servers=util.listify( conf.get( 'display_servers', '' ) ),
                          admin_users=conf.get( 'admin_users', '' ).split( ',' ),
                          remote_user_secret_header=conf.get('remote_user_secret', None) )
        log.debug( "Enabling 'remote user' middleware" )
    # The recursive middleware allows for including requests in other
    # requests or forwarding of requests, all on the server side.
    if asbool(conf.get('use_recursive', True)):
        from paste import recursive
        app = recursive.RecursiveMiddleware( app, conf )
        log.debug( "Enabling 'recursive' middleware" )
    # Various debug middleware that can only be turned on if the debug
    # flag is set, either because they are insecure or greatly hurt
    # performance
    if debug:
        # Middleware to check for WSGI compliance
        if asbool( conf.get( 'use_lint', True ) ):
            from paste import lint
            app = lint.make_middleware( app, conf )
            log.debug( "Enabling 'lint' middleware" )
        # Middleware to run the python profiler on each request
        if asbool( conf.get( 'use_profile', False ) ):
            import profile
            app = profile.ProfileMiddleware( app, conf )
            log.debug( "Enabling 'profile' middleware" )
        # Middleware that intercepts print statements and shows them on the
        # returned page
        if asbool( conf.get( 'use_printdebug', True ) ):
            from paste.debug import prints
            app = prints.PrintDebugMiddleware( app, conf )
            log.debug( "Enabling 'print debug' middleware" )
    if debug and asbool( conf.get( 'use_interactive', False ) ) and not process_is_uwsgi:
        # Interactive exception debugging, scary dangerous if publicly
        # accessible, if not enabled we'll use the regular error printing
        # middleware.
        from weberror import evalexception
        app = evalexception.EvalException( app, conf,
                                           templating_formatters=build_template_error_formatters() )
        log.debug( "Enabling 'eval exceptions' middleware" )
    else:
        if debug and asbool( conf.get( 'use_interactive', False ) ) and process_is_uwsgi:
            log.error("Interactive debugging middleware is enabled in your configuration "
                      "but this is a uwsgi process.  Refusing to wrap in interactive error middleware.")
        # Not in interactive debug mode, just use the regular error middleware
        import galaxy.web.framework.middleware.error
        app = galaxy.web.framework.middleware.error.ErrorMiddleware( app, conf )
        log.debug( "Enabling 'error' middleware" )
    # Transaction logging (apache access.log style)
    if asbool( conf.get( 'use_translogger', True ) ):
        from paste.translogger import TransLogger
        app = TransLogger( app )
        log.debug( "Enabling 'trans logger' middleware" )
    # If sentry logging is enabled, log here before propogating up to
    # the error middleware
    # TODO sentry config is duplicated between agent_shed/galaxy, refactor this.
    sentry_dsn = conf.get( 'sentry_dsn', None )
    if sentry_dsn:
        from galaxy.web.framework.middleware.sentry import Sentry
        log.debug( "Enabling 'sentry' middleware" )
        app = Sentry( app, sentry_dsn )
    # X-Forwarded-Host handling
    from galaxy.web.framework.middleware.xforwardedhost import XForwardedHostMiddleware
    app = XForwardedHostMiddleware( app )
    log.debug( "Enabling 'x-forwarded-host' middleware" )
    app = hg.Hg( app, conf )
    log.debug( "Enabling hg middleware" )
    return app


def wrap_in_static( app, global_conf, **local_conf ):
    urlmap, _ = galaxy.web.framework.webapp.build_url_map( app, global_conf, local_conf )
    return urlmap
