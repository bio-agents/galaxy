import json
import logging
import os
import urllib
import urllib2

from galaxy import util
from galaxy.util.odict import odict
from galaxy.web import url_for
from agent_shed.util import encoding_util, xml_util

log = logging.getLogger( __name__ )

REPOSITORY_OWNER = 'devteam'


def accumulate_agent_dependencies( agent_shed_accessible, agent_dependencies, all_agent_dependencies ):
    if agent_shed_accessible:
        if agent_dependencies:
            for agent_dependency in agent_dependencies:
                if agent_dependency not in all_agent_dependencies:
                    all_agent_dependencies.append( agent_dependency )
    return all_agent_dependencies


def check_for_missing_agents( app, agent_panel_configs, latest_agent_migration_script_number ):
    # Get the 000x_agents.xml file associated with the current migrate_agents version number.
    agents_xml_file_path = os.path.abspath( os.path.join( 'scripts', 'migrate_agents', '%04d_agents.xml' % latest_agent_migration_script_number ) )
    # Parse the XML and load the file attributes for later checking against the proprietary agent_panel_config.
    migrated_agent_configs_dict = odict()
    tree, error_message = xml_util.parse_xml( agents_xml_file_path )
    if tree is None:
        return False, odict()
    root = tree.getroot()
    agent_shed = root.get( 'name' )
    agent_shed_url = get_agent_shed_url_from_agent_shed_registry( app, agent_shed )
    # The default behavior is that the agent shed is down.
    agent_shed_accessible = False
    missing_agent_configs_dict = odict()
    if agent_shed_url:
        for elem in root:
            if elem.tag == 'repository':
                repository_dependencies = []
                all_agent_dependencies = []
                repository_name = elem.get( 'name' )
                changeset_revision = elem.get( 'changeset_revision' )
                agent_shed_accessible, repository_dependencies_dict = get_repository_dependencies( app,
                                                                                                  agent_shed_url,
                                                                                                  repository_name,
                                                                                                  REPOSITORY_OWNER,
                                                                                                  changeset_revision )
                if agent_shed_accessible:
                    # Accumulate all agent dependencies defined for repository dependencies for display to the user.
                    for rd_key, rd_tups in repository_dependencies_dict.items():
                        if rd_key in [ 'root_key', 'description' ]:
                            continue
                        for rd_tup in rd_tups:
                            agent_shed, name, owner, changeset_revision, prior_installation_required, only_if_compiling_contained_td = \
                                parse_repository_dependency_tuple( rd_tup )
                        agent_shed_accessible, agent_dependencies = get_agent_dependencies( app,
                                                                                         agent_shed_url,
                                                                                         name,
                                                                                         owner,
                                                                                         changeset_revision )
                        all_agent_dependencies = accumulate_agent_dependencies( agent_shed_accessible, agent_dependencies, all_agent_dependencies )
                    agent_shed_accessible, agent_dependencies = get_agent_dependencies( app,
                                                                                     agent_shed_url,
                                                                                     repository_name,
                                                                                     REPOSITORY_OWNER,
                                                                                     changeset_revision )
                    all_agent_dependencies = accumulate_agent_dependencies( agent_shed_accessible, agent_dependencies, all_agent_dependencies )
                    for agent_elem in elem.findall( 'agent' ):
                        agent_config_file_name = agent_elem.get( 'file' )
                        if agent_config_file_name:
                            # We currently do nothing with repository dependencies except install them (we do not display repositories that will be
                            # installed to the user).  However, we'll store them in the following dictionary in case we choose to display them in the
                            # future.
                            dependencies_dict = dict( agent_dependencies=all_agent_dependencies,
                                                      repository_dependencies=repository_dependencies )
                            migrated_agent_configs_dict[ agent_config_file_name ] = dependencies_dict
                else:
                    break
        if agent_shed_accessible:
            # Parse the proprietary agent_panel_configs (the default is agent_conf.xml) and generate the list of missing agent config file names.
            for agent_panel_config in agent_panel_configs:
                tree, error_message = xml_util.parse_xml( agent_panel_config )
                if tree:
                    root = tree.getroot()
                    for elem in root:
                        if elem.tag == 'agent':
                            missing_agent_configs_dict = check_agent_tag_set( elem, migrated_agent_configs_dict, missing_agent_configs_dict )
                        elif elem.tag == 'section':
                            for section_elem in elem:
                                if section_elem.tag == 'agent':
                                    missing_agent_configs_dict = check_agent_tag_set( section_elem, migrated_agent_configs_dict, missing_agent_configs_dict )
    else:
        exception_msg = '\n\nThe entry for the main Galaxy agent shed at %s is missing from the %s file.  ' % ( agent_shed, app.config.agent_sheds_config )
        exception_msg += 'The entry for this agent shed must always be available in this file, so re-add it before attempting to start your Galaxy server.\n'
        raise Exception( exception_msg )
    return agent_shed_accessible, missing_agent_configs_dict


def check_agent_tag_set( elem, migrated_agent_configs_dict, missing_agent_configs_dict ):
    file_path = elem.get( 'file', None )
    if file_path:
        name = os.path.basename( file_path )
        for migrated_agent_config in migrated_agent_configs_dict.keys():
            if migrated_agent_config in [ file_path, name ]:
                missing_agent_configs_dict[ name ] = migrated_agent_configs_dict[ migrated_agent_config ]
    return missing_agent_configs_dict


def generate_clone_url_for_installed_repository( app, repository ):
    """Generate the URL for cloning a repository that has been installed into a Galaxy instance."""
    agent_shed_url = get_agent_shed_url_from_agent_shed_registry( app, str( repository.agent_shed ) )
    return url_join( agent_shed_url, pathspec=[ 'repos', str( repository.owner ), str( repository.name ) ] )


def generate_clone_url_for_repository_in_agent_shed( user, repository ):
    """Generate the URL for cloning a repository that is in the agent shed."""
    base_url = url_for( '/', qualified=True ).rstrip( '/' )
    if user:
        protocol, base = base_url.split( '://' )
        username = '%s@' % user.username
        return '%s://%s%s/repos/%s/%s' % ( protocol, username, base, repository.user.username, repository.name )
    else:
        return '%s/repos/%s/%s' % ( base_url, repository.user.username, repository.name )


def generate_clone_url_from_repo_info_tup( app, repo_info_tup ):
    """Generate the URL for cloning a repository given a tuple of agentshed, name, owner, changeset_revision."""
    # Example tuple: ['http://localhost:9009', 'blast_datatypes', 'test', '461a4216e8ab', False]
    agentshed, name, owner, changeset_revision, prior_installation_required, only_if_compiling_contained_td = \
        parse_repository_dependency_tuple( repo_info_tup )
    agent_shed_url = get_agent_shed_url_from_agent_shed_registry( app, agentshed )
    # Don't include the changeset_revision in clone urls.
    return url_join( agent_shed_url, pathspec=[ 'repos', owner, name ] )


def get_non_shed_agent_panel_configs( app ):
    """Get the non-shed related agent panel configs - there can be more than one, and the default is agent_conf.xml."""
    config_filenames = []
    for config_filename in app.config.agent_configs:
        # Any config file that includes a agent_path attribute in the root tag set like the following is shed-related.
        # <agentbox agent_path="../shed_agents">
        tree, error_message = xml_util.parse_xml( config_filename )
        if tree is None:
            continue
        root = tree.getroot()
        agent_path = root.get( 'agent_path', None )
        if agent_path is None:
            config_filenames.append( config_filename )
    return config_filenames


def get_repository_dependencies( app, agent_shed_url, repository_name, repository_owner, changeset_revision ):
    repository_dependencies_dict = {}
    agent_shed_accessible = True
    params = dict( name=repository_name, owner=repository_owner, changeset_revision=changeset_revision )
    pathspec = [ 'repository', 'get_repository_dependencies' ]
    try:
        raw_text = agent_shed_get( app, agent_shed_url, pathspec=pathspec, params=params )
        agent_shed_accessible = True
    except Exception, e:
        agent_shed_accessible = False
        log.warn( "The URL\n%s\nraised the exception:\n%s\n", url_join( agent_shed_url, pathspec=pathspec, params=params ), e )
    if agent_shed_accessible:
        if len( raw_text ) > 2:
            encoded_text = json.loads( raw_text )
            repository_dependencies_dict = encoding_util.agent_shed_decode( encoded_text )
    return agent_shed_accessible, repository_dependencies_dict


def get_protocol_from_agent_shed_url( agent_shed_url ):
    """Return the protocol from the received agent_shed_url if it exists."""
    try:
        if agent_shed_url.find( '://' ) > 0:
            return agent_shed_url.split( '://' )[0].lower()
    except Exception, e:
        # We receive a lot of calls here where the agent_shed_url is None.  The container_util uses
        # that value when creating a header row.  If the agent_shed_url is not None, we have a problem.
        if agent_shed_url is not None:
            log.exception( "Handled exception getting the protocol from Agent Shed URL %s:\n%s", str( agent_shed_url ), e )
        # Default to HTTP protocol.
        return 'http'


def get_agent_dependencies( app, agent_shed_url, repository_name, repository_owner, changeset_revision ):
    agent_dependencies = []
    agent_shed_accessible = True
    params = dict( name=repository_name, owner=repository_owner, changeset_revision=changeset_revision )
    pathspec = [ 'repository', 'get_agent_dependencies' ]
    try:
        text = agent_shed_get( app, agent_shed_url, pathspec=pathspec, params=params )
        agent_shed_accessible = True
    except Exception, e:
        agent_shed_accessible = False
        log.warn( "The URL\n%s\nraised the exception:\n%s\n", url_join( agent_shed_url, pathspec=pathspec, params=params ), e )
    if agent_shed_accessible:
        if text:
            agent_dependencies_dict = encoding_util.agent_shed_decode( text )
            for requirements_dict in agent_dependencies_dict.values():
                agent_dependency_name = requirements_dict[ 'name' ]
                agent_dependency_version = requirements_dict[ 'version' ]
                agent_dependency_type = requirements_dict[ 'type' ]
                agent_dependencies.append( ( agent_dependency_name, agent_dependency_version, agent_dependency_type ) )
    return agent_shed_accessible, agent_dependencies


def get_agent_shed_repository_ids( as_string=False, **kwd ):
    tsrid = kwd.get( 'agent_shed_repository_id', None )
    tsridslist = util.listify( kwd.get( 'agent_shed_repository_ids', None ) )
    if not tsridslist:
        tsridslist = util.listify( kwd.get( 'id', None ) )
    if tsridslist is not None:
        if tsrid is not None and tsrid not in tsridslist:
            tsridslist.append( tsrid )
        if as_string:
            return ','.join( tsridslist )
        return tsridslist
    else:
        tsridslist = util.listify( kwd.get( 'ordered_tsr_ids', None ) )
        if tsridslist is not None:
            if as_string:
                return ','.join( tsridslist )
            return tsridslist
    if as_string:
        return ''
    return []


def get_agent_shed_url_from_agent_shed_registry( app, agent_shed ):
    """
    The value of agent_shed is something like: agentshed.g2.bx.psu.edu.  We need the URL to this agent shed, which is
    something like: http://agentshed.g2.bx.psu.edu/
    """
    cleaned_agent_shed = remove_protocol_from_agent_shed_url( agent_shed )
    for shed_url in app.agent_shed_registry.agent_sheds.values():
        if shed_url.find( cleaned_agent_shed ) >= 0:
            if shed_url.endswith( '/' ):
                shed_url = shed_url.rstrip( '/' )
            return shed_url
    # The agent shed from which the repository was originally installed must no longer be configured in agent_sheds_conf.xml.
    return None


def handle_galaxy_url( trans, **kwd ):
    galaxy_url = kwd.get( 'galaxy_url', None )
    if galaxy_url:
        trans.set_cookie( galaxy_url, name='agentshedgalaxyurl' )
    else:
        galaxy_url = trans.get_cookie( name='agentshedgalaxyurl' )
    return galaxy_url


def handle_agent_shed_url_protocol( app, shed_url ):
    """Handle secure and insecure HTTP protocol since they may change over time."""
    try:
        if app.name == 'galaxy':
            url = remove_protocol_from_agent_shed_url( shed_url )
            agent_shed_url = get_agent_shed_url_from_agent_shed_registry( app, url )
        else:
            agent_shed_url = str( url_for( '/', qualified=True ) ).rstrip( '/' )
        return agent_shed_url
    except Exception, e:
        # We receive a lot of calls here where the agent_shed_url is None.  The container_util uses
        # that value when creating a header row.  If the agent_shed_url is not None, we have a problem.
        if shed_url is not None:
            log.exception( "Handled exception removing protocol from URL %s:\n%s", str( shed_url ), e )
        return shed_url


def parse_repository_dependency_tuple( repository_dependency_tuple, contains_error=False ):
    # Default both prior_installation_required and only_if_compiling_contained_td to False in cases where metadata should be reset on the
    # repository containing the repository_dependency definition.
    prior_installation_required = 'False'
    only_if_compiling_contained_td = 'False'
    if contains_error:
        if len( repository_dependency_tuple ) == 5:
            agent_shed, name, owner, changeset_revision, error = repository_dependency_tuple
        elif len( repository_dependency_tuple ) == 6:
            agent_shed, name, owner, changeset_revision, prior_installation_required, error = repository_dependency_tuple
        elif len( repository_dependency_tuple ) == 7:
            agent_shed, name, owner, changeset_revision, prior_installation_required, only_if_compiling_contained_td, error = \
                repository_dependency_tuple
        return agent_shed, name, owner, changeset_revision, prior_installation_required, only_if_compiling_contained_td, error
    else:
        if len( repository_dependency_tuple ) == 4:
            agent_shed, name, owner, changeset_revision = repository_dependency_tuple
        elif len( repository_dependency_tuple ) == 5:
            agent_shed, name, owner, changeset_revision, prior_installation_required = repository_dependency_tuple
        elif len( repository_dependency_tuple ) == 6:
            agent_shed, name, owner, changeset_revision, prior_installation_required, only_if_compiling_contained_td = repository_dependency_tuple
        return agent_shed, name, owner, changeset_revision, prior_installation_required, only_if_compiling_contained_td


def remove_port_from_agent_shed_url( agent_shed_url ):
    """Return a partial Agent Shed URL, eliminating the port if it exists."""
    try:
        if agent_shed_url.find( ':' ) > 0:
            # Eliminate the port, if any, since it will result in an invalid directory name.
            new_agent_shed_url = agent_shed_url.split( ':' )[ 0 ]
        else:
            new_agent_shed_url = agent_shed_url
        return new_agent_shed_url.rstrip( '/' )
    except Exception, e:
        # We receive a lot of calls here where the agent_shed_url is None.  The container_util uses
        # that value when creating a header row.  If the agent_shed_url is not None, we have a problem.
        if agent_shed_url is not None:
            log.exception( "Handled exception removing the port from Agent Shed URL %s:\n%s", str( agent_shed_url ), e )
        return agent_shed_url


def remove_protocol_and_port_from_agent_shed_url( agent_shed_url ):
    """Return a partial Agent Shed URL, eliminating the protocol and/or port if either exists."""
    agent_shed = remove_protocol_from_agent_shed_url( agent_shed_url )
    agent_shed = remove_port_from_agent_shed_url( agent_shed )
    return agent_shed


def remove_protocol_and_user_from_clone_url( repository_clone_url ):
    """Return a URL that can be used to clone a repository, eliminating the protocol and user if either exists."""
    if repository_clone_url.find( '@' ) > 0:
        # We have an url that includes an authenticated user, something like:
        # http://test@bx.psu.edu:9009/repos/some_username/column
        items = repository_clone_url.split( '@' )
        tmp_url = items[ 1 ]
    elif repository_clone_url.find( '//' ) > 0:
        # We have an url that includes only a protocol, something like:
        # http://bx.psu.edu:9009/repos/some_username/column
        items = repository_clone_url.split( '//' )
        tmp_url = items[ 1 ]
    else:
        tmp_url = repository_clone_url
    return tmp_url.rstrip( '/' )


def remove_protocol_from_agent_shed_url( agent_shed_url ):
    """Return a partial Agent Shed URL, eliminating the protocol if it exists."""
    return util.remove_protocol_from_url( agent_shed_url )


def agent_shed_get( app, base_url, pathspec=[], params={} ):
    """Make contact with the agent shed via the uri provided."""
    registry = app.agent_shed_registry
    # urllib2 auto-detects system proxies, when passed a Proxyhandler.
    # Refer: https://docs.python.org/2/howto/urllib2.html#proxies
    proxy = urllib2.ProxyHandler()
    urlopener = urllib2.build_opener( proxy )
    urllib2.install_opener( urlopener )
    password_mgr = registry.password_manager_for_url( base_url )
    if password_mgr is not None:
        auth_handler = urllib2.HTTPBasicAuthHandler( password_mgr )
        urlopener.add_handler( auth_handler )
    full_url = url_join( base_url, pathspec=pathspec, params=params )
    response = urlopener.open( full_url )
    content = response.read()
    response.close()
    return content


def url_join( base_url, pathspec=None, params=None ):
    """Return a valid URL produced by appending a base URL and a set of request parameters."""
    url = base_url.rstrip( '/' )
    if pathspec is not None:
        if not isinstance( pathspec, basestring ):
            pathspec = '/'.join( pathspec )
        url = '%s/%s' % ( url, pathspec )
    if params is not None:
        url = '%s?%s' % ( url, urllib.urlencode( params ) )
    return url
