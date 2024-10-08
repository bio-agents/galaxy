import json
import logging
import os
import re
import shutil
import socket
import string
from urllib2 import HTTPError
from operator import itemgetter

import sqlalchemy.orm.exc
from sqlalchemy import and_, false, or_, true

from galaxy import util
from galaxy.web import url_for
from galaxy.util import checkers
from agent_shed.util import basic_util
from agent_shed.util import common_util
from agent_shed.util import encoding_util
from agent_shed.util import hg_util

log = logging.getLogger( __name__ )

MAX_CONTENT_SIZE = 1048576
DATATYPES_CONFIG_FILENAME = 'datatypes_conf.xml'
REPOSITORY_DATA_MANAGER_CONFIG_FILENAME = 'data_manager_conf.xml'

new_repo_email_alert_template = """
Sharable link:         ${sharable_link}
Repository name:       ${repository_name}
Revision:              ${revision}
Change description:
${description}

Uploaded by:           ${username}
Date content uploaded: ${display_date}

${content_alert_str}

-----------------------------------------------------------------------------
This change alert was sent from the Galaxy agent shed hosted on the server
"${host}"
-----------------------------------------------------------------------------
You received this alert because you registered to receive email when
new repositories were created in the Galaxy agent shed named "${host}".
-----------------------------------------------------------------------------
"""

email_alert_template = """
Sharable link:         ${sharable_link}
Repository name:       ${repository_name}
Revision:              ${revision}
Change description:
${description}

Changed by:     ${username}
Date of change: ${display_date}

${content_alert_str}

-----------------------------------------------------------------------------
This change alert was sent from the Galaxy agent shed hosted on the server
"${host}"
-----------------------------------------------------------------------------
You received this alert because you registered to receive email whenever
changes were made to the repository named "${repository_name}".
-----------------------------------------------------------------------------
"""

contact_owner_template = """
GALAXY TOOL SHED REPOSITORY MESSAGE
------------------------

The user '${username}' sent you the following message regarding your agent shed
repository named '${repository_name}'.  You can respond by sending a reply to
the user's email address: ${email}.
-----------------------------------------------------------------------------
${message}
-----------------------------------------------------------------------------
This message was sent from the Galaxy Agent Shed instance hosted on the server
'${host}'
"""


def can_eliminate_repository_dependency(metadata_dict, agent_shed_url, name, owner):
    """
    Determine if the relationship between a repository_dependency record
    associated with a agent_shed_repository record on the Galaxy side
    can be eliminated.
    """
    rd_dict = metadata_dict.get('repository_dependencies', {})
    rd_tups = rd_dict.get( 'repository_dependencies', [] )
    for rd_tup in rd_tups:
        tsu, n, o, none1, none2, none3 = common_util.parse_repository_dependency_tuple(rd_tup)
        if tsu == agent_shed_url and n == name and o == owner:
            # The repository dependency is current, so keep it.
            return False
    return True


def can_eliminate_agent_dependency(metadata_dict, name, type, version):
    """
    Determine if the relationship between a agent_dependency record
    associated with a agent_shed_repository record on the Galaxy side
    can be eliminated.
    """
    td_dict = metadata_dict.get('agent_dependencies', {})
    for td_key, td_val in td_dict.items():
        n = td_val.get('name', None)
        t = td_val.get('type', None)
        v = td_val.get('version', None)
        if n == name and t == type and v == version:
            # The agent dependency is current, so keep it.
            return False
    return True


def clean_dependency_relationships(trans, metadata_dict, agent_shed_repository, agent_shed_url):
    """
    Repositories of type agent_dependency_definition allow for defining a
    package dependency at some point in the change log and then removing the
    dependency later in the change log.  This function keeps the dependency
    relationships on the Galaxy side current by deleting database records
    that defined the now-broken relationships.
    """
    for rrda in agent_shed_repository.required_repositories:
        rd = rrda.repository_dependency
        r = rd.repository
        if can_eliminate_repository_dependency(metadata_dict, agent_shed_url, r.name, r.owner):
            trans.install_model.context.delete(rrda)
            trans.install_model.context.flush()
    for td in agent_shed_repository.agent_dependencies:
        if can_eliminate_agent_dependency(metadata_dict, td.name, td.type, td.version):
            trans.install_model.context.delete(td)
            trans.install_model.context.flush()


def create_or_update_agent_shed_repository( app, name, description, installed_changeset_revision, ctx_rev, repository_clone_url,
                                           metadata_dict, status, current_changeset_revision=None, owner='', dist_to_shed=False ):
    """
    Update a agent shed repository record in the Galaxy database with the new information received.
    If a record defined by the received agent shed, repository name and owner does not exist, create
    a new record with the received information.
    """
    # The received value for dist_to_shed will be True if the AgentMigrationManager is installing a repository
    # that contains agents or datatypes that used to be in the Galaxy distribution, but have been moved
    # to the main Galaxy agent shed.
    if current_changeset_revision is None:
        # The current_changeset_revision is not passed if a repository is being installed for the first
        # time.  If a previously installed repository was later uninstalled, this value should be received
        # as the value of that change set to which the repository had been updated just prior to it being
        # uninstalled.
        current_changeset_revision = installed_changeset_revision
    context = app.install_model.context
    agent_shed = get_agent_shed_from_clone_url( repository_clone_url )
    if not owner:
        owner = get_repository_owner_from_clone_url( repository_clone_url )
    includes_datatypes = 'datatypes' in metadata_dict
    if status in [ app.install_model.AgentShedRepository.installation_status.DEACTIVATED ]:
        deleted = True
        uninstalled = False
    elif status in [ app.install_model.AgentShedRepository.installation_status.UNINSTALLED ]:
        deleted = True
        uninstalled = True
    else:
        deleted = False
        uninstalled = False
    agent_shed_repository = \
        get_installed_repository( app, agent_shed=agent_shed, name=name, owner=owner, installed_changeset_revision=installed_changeset_revision )
    if agent_shed_repository:
        log.debug( "Updating an existing row for repository '%s' in the agent_shed_repository table, status set to '%s'." %
                   ( str( name ), str( status ) ) )
        agent_shed_repository.description = description
        agent_shed_repository.changeset_revision = current_changeset_revision
        agent_shed_repository.ctx_rev = ctx_rev
        agent_shed_repository.metadata = metadata_dict
        agent_shed_repository.includes_datatypes = includes_datatypes
        agent_shed_repository.deleted = deleted
        agent_shed_repository.uninstalled = uninstalled
        agent_shed_repository.status = status
    else:
        log.debug( "Adding new row for repository '%s' in the agent_shed_repository table, status set to '%s'." %
                   ( str( name ), str( status ) ) )
        agent_shed_repository = \
            app.install_model.AgentShedRepository( agent_shed=agent_shed,
                                                  name=name,
                                                  description=description,
                                                  owner=owner,
                                                  installed_changeset_revision=installed_changeset_revision,
                                                  changeset_revision=current_changeset_revision,
                                                  ctx_rev=ctx_rev,
                                                  metadata=metadata_dict,
                                                  includes_datatypes=includes_datatypes,
                                                  dist_to_shed=dist_to_shed,
                                                  deleted=deleted,
                                                  uninstalled=uninstalled,
                                                  status=status )
    context.add( agent_shed_repository )
    context.flush()
    return agent_shed_repository


def extract_components_from_tuple( repository_components_tuple ):
    '''Extract the repository components from the provided tuple in a backward-compatible manner.'''
    agentshed = repository_components_tuple[ 0 ]
    name = repository_components_tuple[ 1 ]
    owner = repository_components_tuple[ 2 ]
    changeset_revision = repository_components_tuple[ 3 ]
    components_list = [ agentshed, name, owner, changeset_revision ]
    if len( repository_components_tuple ) == 5:
        agentshed, name, owner, changeset_revision, prior_installation_required = repository_components_tuple
        components_list = [ agentshed, name, owner, changeset_revision, prior_installation_required ]
    elif len( repository_components_tuple ) == 6:
        agentshed, name, owner, changeset_revision, prior_installation_required, only_if_compiling_contained_td = repository_components_tuple
        components_list = [ agentshed, name, owner, changeset_revision, prior_installation_required, only_if_compiling_contained_td ]
    return components_list


def generate_sharable_link_for_repository_in_agent_shed( repository, changeset_revision=None ):
    """Generate the URL for sharing a repository that is in the agent shed."""
    base_url = url_for( '/', qualified=True ).rstrip( '/' )
    protocol, base = base_url.split( '://' )
    sharable_url = '%s://%s/view/%s/%s' % ( protocol, base, repository.user.username, repository.name )
    if changeset_revision:
        sharable_url += '/%s' % changeset_revision
    return sharable_url


def generate_agent_guid( repository_clone_url, agent ):
    """
    Generate a guid for the installed agent.  It is critical that this guid matches the guid for
    the agent in the Galaxy agent shed from which it is being installed.  The form of the guid is
    <agent shed host>/repos/<repository owner>/<repository name>/<agent id>/<agent version>
    """
    tmp_url = common_util.remove_protocol_and_user_from_clone_url( repository_clone_url )
    return '%s/%s/%s' % ( tmp_url, agent.id, agent.version )


def generate_agent_shed_repository_install_dir( repository_clone_url, changeset_revision ):
    """
    Generate a repository installation directory that guarantees repositories with the same
    name will always be installed in different directories.  The agent path will be of the form:
    <agent shed url>/repos/<repository owner>/<repository name>/<installed changeset revision>
    """
    tmp_url = common_util.remove_protocol_and_user_from_clone_url( repository_clone_url )
    # Now tmp_url is something like: bx.psu.edu:9009/repos/some_username/column
    items = tmp_url.split( '/repos/' )
    agent_shed_url = items[ 0 ]
    repo_path = items[ 1 ]
    agent_shed_url = common_util.remove_port_from_agent_shed_url( agent_shed_url )
    return common_util.url_join( agent_shed_url, pathspec=[ 'repos', repo_path, changeset_revision ] )


def get_absolute_path_to_file_in_repository( repo_files_dir, file_name ):
    """Return the absolute path to a specified disk file contained in a repository."""
    stripped_file_name = basic_util.strip_path( file_name )
    file_path = None
    for root, dirs, files in os.walk( repo_files_dir ):
        if root.find( '.hg' ) < 0:
            for name in files:
                if name == stripped_file_name:
                    return os.path.abspath( os.path.join( root, name ) )
    return file_path


def get_categories( app ):
    """Get all categories from the database."""
    sa_session = app.model.context.current
    return sa_session.query( app.model.Category ) \
                     .filter( app.model.Category.table.c.deleted == false() ) \
                     .order_by( app.model.Category.table.c.name ) \
                     .all()


def get_category( app, id ):
    """Get a category from the database."""
    sa_session = app.model.context.current
    return sa_session.query( app.model.Category ).get( app.security.decode_id( id ) )


def get_category_by_name( app, name ):
    """Get a category from the database via name."""
    sa_session = app.model.context.current
    try:
        return sa_session.query( app.model.Category ).filter_by( name=name ).one()
    except sqlalchemy.orm.exc.NoResultFound:
        return None


def get_ctx_rev( app, agent_shed_url, name, owner, changeset_revision ):
    """
    Send a request to the agent shed to retrieve the ctx_rev for a repository defined by the
    combination of a name, owner and changeset revision.
    """
    agent_shed_url = common_util.get_agent_shed_url_from_agent_shed_registry( app, agent_shed_url )
    params = dict( name=name, owner=owner, changeset_revision=changeset_revision )
    pathspec = [ 'repository', 'get_ctx_rev' ]
    ctx_rev = common_util.agent_shed_get( app, agent_shed_url, pathspec=pathspec, params=params )
    return ctx_rev


def get_current_repository_metadata_for_changeset_revision( app, repository, changeset_revision ):
    encoded_repository_id = app.security.encode_id( repository.id )
    repository_metadata = get_repository_metadata_by_changeset_revision( app,
                                                                         encoded_repository_id,
                                                                         changeset_revision )
    if repository_metadata:
        return repository_metadata
    # The installable changeset_revision may have been changed because it was "moved ahead"
    # in the repository changelog.
    repo = hg_util.get_repo_for_repository( app, repository=repository, repo_path=None, create=False )
    updated_changeset_revision = get_next_downloadable_changeset_revision( repository,
                                                                           repo,
                                                                           after_changeset_revision=changeset_revision )
    if updated_changeset_revision:
        repository_metadata = get_repository_metadata_by_changeset_revision( app,
                                                                             encoded_repository_id,
                                                                             updated_changeset_revision )
        if repository_metadata:
            return repository_metadata
    return None


def get_ids_of_agent_shed_repositories_being_installed( app, as_string=False ):
    installing_repository_ids = []
    new_status = app.install_model.AgentShedRepository.installation_status.NEW
    cloning_status = app.install_model.AgentShedRepository.installation_status.CLONING
    setting_agent_versions_status = app.install_model.AgentShedRepository.installation_status.SETTING_TOOL_VERSIONS
    installing_dependencies_status = app.install_model.AgentShedRepository.installation_status.INSTALLING_TOOL_DEPENDENCIES
    loading_datatypes_status = app.install_model.AgentShedRepository.installation_status.LOADING_PROPRIETARY_DATATYPES
    for agent_shed_repository in \
        app.install_model.context.query( app.install_model.AgentShedRepository ) \
                                 .filter( or_( app.install_model.AgentShedRepository.status == new_status,
                                               app.install_model.AgentShedRepository.status == cloning_status,
                                               app.install_model.AgentShedRepository.status == setting_agent_versions_status,
                                               app.install_model.AgentShedRepository.status == installing_dependencies_status,
                                               app.install_model.AgentShedRepository.status == loading_datatypes_status ) ):
        installing_repository_ids.append( app.security.encode_id( agent_shed_repository.id ) )
    if as_string:
        return ','.join( installing_repository_ids )
    return installing_repository_ids


def get_latest_downloadable_changeset_revision( app, repository, repo ):
    repository_tip = repository.tip( app )
    repository_metadata = get_repository_metadata_by_changeset_revision( app, app.security.encode_id( repository.id ), repository_tip )
    if repository_metadata and repository_metadata.downloadable:
        return repository_tip
    changeset_revisions = [ revision[ 1 ] for revision in get_metadata_revisions( repository, repo ) ]
    if changeset_revisions:
        return changeset_revisions[ -1 ]
    return hg_util.INITIAL_CHANGELOG_HASH


def get_agent_dependency_definition_metadata_from_agent_shed( app, agent_shed_url, name, owner ):
    """
    Send a request to the agent shed to retrieve the current metadata for a
    repository of type agent_dependency_definition defined by the combination
    of a name and owner.
    """
    agent_shed_url = common_util.get_agent_shed_url_from_agent_shed_registry( app, agent_shed_url )
    params = dict( name=name, owner=owner )
    pathspec = [ 'repository', 'get_agent_dependency_definition_metadata' ]
    metadata = common_util.agent_shed_get( app, agent_shed_url, pathspec=pathspec, params=params )
    return metadata


def get_next_downloadable_changeset_revision( repository, repo, after_changeset_revision ):
    """
    Return the installable changeset_revision in the repository changelog after the changeset to which
    after_changeset_revision refers.  If there isn't one, return None.
    """
    changeset_revisions = [ revision[ 1 ] for revision in get_metadata_revisions( repository, repo ) ]
    if len( changeset_revisions ) == 1:
        changeset_revision = changeset_revisions[ 0 ]
        if changeset_revision == after_changeset_revision:
            return None
    found_after_changeset_revision = False
    for changeset in repo.changelog:
        changeset_revision = str( repo.changectx( changeset ) )
        if found_after_changeset_revision:
            if changeset_revision in changeset_revisions:
                return changeset_revision
        elif not found_after_changeset_revision and changeset_revision == after_changeset_revision:
            # We've found the changeset in the changelog for which we need to get the next downloadable changeset.
            found_after_changeset_revision = True
    return None


def get_next_prior_import_or_install_required_dict_entry( prior_required_dict, processed_tsr_ids ):
    """
    This method is used in the Agent Shed when exporting a repository and its dependencies, and in Galaxy
    when a repository and its dependencies are being installed.  The order in which the prior_required_dict
    is processed is critical in order to ensure that the ultimate repository import or installation order is
    correctly defined.  This method determines the next key / value pair from the received prior_required_dict
    that should be processed.
    """
    # Return the first key / value pair that is not yet processed and whose value is an empty list.
    for key, value in prior_required_dict.items():
        if key in processed_tsr_ids:
            continue
        if not value:
            return key
    # Return the first key / value pair that is not yet processed and whose ids in value are all included
    # in processed_tsr_ids.
    for key, value in prior_required_dict.items():
        if key in processed_tsr_ids:
            continue
        all_contained = True
        for required_repository_id in value:
            if required_repository_id not in processed_tsr_ids:
                all_contained = False
                break
        if all_contained:
            return key
    # Return the first key / value pair that is not yet processed.  Hopefully this is all that is necessary
    # at this point.
    for key, value in prior_required_dict.items():
        if key in processed_tsr_ids:
            continue
        return key


def get_metadata_revisions( repository, repo, sort_revisions=True, reverse=False, downloadable=True ):
    """
    Return a list of changesets for the provided repository.
    """
    if downloadable:
        metadata_revisions = repository.downloadable_revisions
    else:
        metadata_revisions = repository.metadata_revisions
    changeset_tups = []
    for repository_metadata in metadata_revisions:
        ctx = hg_util.get_changectx_for_changeset( repo, repository_metadata.changeset_revision )
        if ctx:
            rev = '%04d' % ctx.rev()
        else:
            rev = -1
        changeset_tups.append( ( rev, repository_metadata.changeset_revision ) )
    if sort_revisions:
        changeset_tups.sort( key=itemgetter( 0 ), reverse=reverse )
    return changeset_tups


def get_prior_import_or_install_required_dict( app, tsr_ids, repo_info_dicts ):
    """
    This method is used in the Agent Shed when exporting a repository and its dependencies,
    and in Galaxy when a repository and its dependencies are being installed.  Return a
    dictionary whose keys are the received tsr_ids and whose values are a list of tsr_ids,
    each of which is contained in the received list of tsr_ids and whose associated repository
    must be imported or installed prior to the repository associated with the tsr_id key.
    """
    # Initialize the dictionary.
    prior_import_or_install_required_dict = {}
    for tsr_id in tsr_ids:
        prior_import_or_install_required_dict[ tsr_id ] = []
    # Inspect the repository dependencies for each repository about to be installed and populate the dictionary.
    for repo_info_dict in repo_info_dicts:
        repository, repository_dependencies = get_repository_and_repository_dependencies_from_repo_info_dict( app, repo_info_dict )
        if repository:
            encoded_repository_id = app.security.encode_id( repository.id )
            if encoded_repository_id in tsr_ids:
                # We've located the database table record for one of the repositories we're about to install, so find out if it has any repository
                # dependencies that require prior installation.
                prior_import_or_install_ids = get_repository_ids_requiring_prior_import_or_install( app, tsr_ids, repository_dependencies )
                prior_import_or_install_required_dict[ encoded_repository_id ] = prior_import_or_install_ids
    return prior_import_or_install_required_dict


def get_repo_info_tuple_contents( repo_info_tuple ):
    """Take care in handling the repo_info_tuple as it evolves over time as new agent shed features are introduced."""
    if len( repo_info_tuple ) == 6:
        description, repository_clone_url, changeset_revision, ctx_rev, repository_owner, agent_dependencies = repo_info_tuple
        repository_dependencies = None
    elif len( repo_info_tuple ) == 7:
        description, repository_clone_url, changeset_revision, ctx_rev, repository_owner, repository_dependencies, agent_dependencies = repo_info_tuple
    return description, repository_clone_url, changeset_revision, ctx_rev, repository_owner, repository_dependencies, agent_dependencies


def get_repository_and_repository_dependencies_from_repo_info_dict( app, repo_info_dict ):
    """Return a agent_shed_repository or repository record defined by the information in the received repo_info_dict."""
    repository_name = repo_info_dict.keys()[ 0 ]
    repo_info_tuple = repo_info_dict[ repository_name ]
    description, repository_clone_url, changeset_revision, ctx_rev, repository_owner, repository_dependencies, agent_dependencies = \
        get_repo_info_tuple_contents( repo_info_tuple )
    if hasattr( app, "install_model" ):
        # In a agent shed client (Galaxy, or something install repositories like Galaxy)
        agent_shed = get_agent_shed_from_clone_url( repository_clone_url )
        repository = get_repository_for_dependency_relationship( app, agent_shed, repository_name, repository_owner, changeset_revision )
    else:
        # We're in the agent shed.
        repository = get_repository_by_name_and_owner( app, repository_name, repository_owner )
    return repository, repository_dependencies


def get_repository_by_id( app, id ):
    """Get a repository from the database via id."""
    if is_agent_shed_client( app ):
        return app.install_model.context.query( app.install_model.AgentShedRepository ).get( app.security.decode_id( id ) )
    else:
        sa_session = app.model.context.current
        return sa_session.query( app.model.Repository ).get( app.security.decode_id( id ) )


def get_repository_by_name( app, name ):
    """Get a repository from the database via name."""
    repository_query = get_repository_query( app )
    return repository_query.filter_by( name=name ).first()


def get_repository_by_name_and_owner( app, name, owner ):
    """Get a repository from the database via name and owner"""
    repository_query = get_repository_query( app )
    if is_agent_shed_client( app ):
        return repository_query \
            .filter( and_( app.install_model.AgentShedRepository.table.c.name == name,
                           app.install_model.AgentShedRepository.table.c.owner == owner ) ) \
            .first()
    # We're in the agent shed.
    user = get_user_by_username( app, owner )
    if user:
        return repository_query \
            .filter( and_( app.model.Repository.table.c.name == name,
                           app.model.Repository.table.c.user_id == user.id ) ) \
            .first()
    return None


def get_repository_dependency_types( repository_dependencies ):
    """
    Inspect the received list of repository_dependencies tuples and return boolean values
    for has_repository_dependencies and has_repository_dependencies_only_if_compiling_contained_td.
    """
    # Set has_repository_dependencies, which will be True only if at least one repository_dependency
    # is defined with the value of
    # only_if_compiling_contained_td as False.
    has_repository_dependencies = False
    for rd_tup in repository_dependencies:
        agent_shed, name, owner, changeset_revision, prior_installation_required, only_if_compiling_contained_td = \
            common_util.parse_repository_dependency_tuple( rd_tup )
        if not util.asbool( only_if_compiling_contained_td ):
            has_repository_dependencies = True
            break
    # Set has_repository_dependencies_only_if_compiling_contained_td, which will be True only if at
    # least one repository_dependency is defined with the value of only_if_compiling_contained_td as True.
    has_repository_dependencies_only_if_compiling_contained_td = False
    for rd_tup in repository_dependencies:
        agent_shed, name, owner, changeset_revision, prior_installation_required, only_if_compiling_contained_td = \
            common_util.parse_repository_dependency_tuple( rd_tup )
        if util.asbool( only_if_compiling_contained_td ):
            has_repository_dependencies_only_if_compiling_contained_td = True
            break
    return has_repository_dependencies, has_repository_dependencies_only_if_compiling_contained_td


def get_repository_for_dependency_relationship( app, agent_shed, name, owner, changeset_revision ):
    """
    Return an installed agent_shed_repository database record that is defined by either the current changeset
    revision or the installed_changeset_revision.
    """
    # This method is used only in Galaxy, not the Agent Shed.  We store the port (if one exists) in the database.
    agent_shed = common_util.remove_protocol_from_agent_shed_url( agent_shed )
    if agent_shed is None or name is None or owner is None or changeset_revision is None:
        message = "Unable to retrieve the repository record from the database because one or more of the following "
        message += "required parameters is None: agent_shed: %s, name: %s, owner: %s, changeset_revision: %s " % \
            ( str( agent_shed ), str( name ), str( owner ), str( changeset_revision ) )
        raise Exception( message )
    repository = get_installed_repository( app=app,
                                           agent_shed=agent_shed,
                                           name=name,
                                           owner=owner,
                                           installed_changeset_revision=changeset_revision )
    if not repository:
        repository = get_installed_repository( app=app,
                                               agent_shed=agent_shed,
                                               name=name,
                                               owner=owner,
                                               changeset_revision=changeset_revision )
    if not repository:
        agent_shed_url = common_util.get_agent_shed_url_from_agent_shed_registry( app, agent_shed )
        repository_clone_url = os.path.join( agent_shed_url, 'repos', owner, name )
        repo_info_tuple = (None, repository_clone_url, changeset_revision, None, owner, None, None)
        repository, pcr = repository_was_previously_installed( app, agent_shed_url, name, repo_info_tuple )
    if not repository:
        # The received changeset_revision is no longer installable, so get the next changeset_revision
        # in the repository's changelog in the agent shed that is associated with repository_metadata.
        agent_shed_url = common_util.get_agent_shed_url_from_agent_shed_registry( app, agent_shed )
        params = dict( name=name, owner=owner, changeset_revision=changeset_revision )
        pathspec = [ 'repository', 'next_installable_changeset_revision' ]
        text = common_util.agent_shed_get( app, agent_shed_url, pathspec=pathspec, params=params )
        if text:
            repository = get_installed_repository( app=app,
                                                   agent_shed=agent_shed,
                                                   name=name,
                                                   owner=owner,
                                                   changeset_revision=text )
    return repository


def get_repository_file_contents( file_path ):
    """Return the display-safe contents of a repository file for display in a browser."""
    if checkers.is_gzip( file_path ):
        return '<br/>gzip compressed file<br/>'
    elif checkers.is_bz2( file_path ):
        return '<br/>bz2 compressed file<br/>'
    elif checkers.check_zip( file_path ):
        return '<br/>zip compressed file<br/>'
    elif checkers.check_binary( file_path ):
        return '<br/>Binary file<br/>'
    else:
        safe_str = ''
        for i, line in enumerate( open( file_path ) ):
            safe_str = '%s%s' % ( safe_str, basic_util.to_html_string( line ) )
            # Stop reading after string is larger than MAX_CONTENT_SIZE.
            if len( safe_str ) > MAX_CONTENT_SIZE:
                large_str = \
                    '<br/>File contents truncated because file size is larger than maximum viewing size of %s<br/>' % \
                    util.nice_size( MAX_CONTENT_SIZE )
                safe_str = '%s%s' % ( safe_str, large_str )
                break
        if len( safe_str ) > basic_util.MAX_DISPLAY_SIZE:
            # Eliminate the middle of the file to display a file no larger than basic_util.MAX_DISPLAY_SIZE.
            # This may not be ideal if the file is larger than MAX_CONTENT_SIZE.
            join_by_str = \
                "<br/><br/>...some text eliminated here because file size is larger than maximum viewing size of %s...<br/><br/>" % \
                util.nice_size( basic_util.MAX_DISPLAY_SIZE )
            safe_str = util.shrink_string_by_size( safe_str,
                                                   basic_util.MAX_DISPLAY_SIZE,
                                                   join_by=join_by_str,
                                                   left_larger=True,
                                                   beginning_on_size_error=True )
        return safe_str


def get_repository_files( folder_path ):
    """Return the file hierarchy of a agent shed repository."""
    contents = []
    for item in os.listdir( folder_path ):
        # Skip .hg directories
        if item.startswith( '.hg' ):
            continue
        if os.path.isdir( os.path.join( folder_path, item ) ):
            # Append a '/' character so that our jquery dynatree will function properly.
            item = '%s/' % item
        contents.append( item )
    if contents:
        contents.sort()
    return contents


def get_repository_from_refresh_on_change( app, **kwd ):
    # The changeset_revision_select_field in several grids performs a refresh_on_change which sends in request parameters like
    # changeset_revison_1, changeset_revision_2, etc.  One of the many select fields on the grid performed the refresh_on_change,
    # so we loop through all of the received values to see which value is not the repository tip.  If we find it, we know the
    # refresh_on_change occurred and we have the necessary repository id and change set revision to pass on.
    repository_id = None
    v = None
    for k, v in kwd.items():
        changeset_revision_str = 'changeset_revision_'
        if k.startswith( changeset_revision_str ):
            repository_id = app.security.encode_id( int( k.lstrip( changeset_revision_str ) ) )
            repository = get_repository_in_agent_shed( app, repository_id )
            if repository.tip( app ) != v:
                return v, repository
    # This should never be reached - raise an exception?
    return v, None


def get_repository_ids_requiring_prior_import_or_install( app, tsr_ids, repository_dependencies ):
    """
    This method is used in the Agent Shed when exporting a repository and its dependencies,
    and in Galaxy when a repository and its dependencies are being installed.  Inspect the
    received repository_dependencies and determine if the encoded id of each required
    repository is in the received tsr_ids.  If so, then determine whether that required
    repository should be imported / installed prior to its dependent repository.  Return a
    list of encoded repository ids, each of which is contained in the received list of tsr_ids,
    and whose associated repositories must be imported / installed prior to the dependent
    repository associated with the received repository_dependencies.
    """
    prior_tsr_ids = []
    if repository_dependencies:
        for key, rd_tups in repository_dependencies.items():
            if key in [ 'description', 'root_key' ]:
                continue
            for rd_tup in rd_tups:
                agent_shed, \
                    name, \
                    owner, \
                    changeset_revision, \
                    prior_installation_required, \
                    only_if_compiling_contained_td = \
                    common_util.parse_repository_dependency_tuple( rd_tup )
                # If only_if_compiling_contained_td is False, then the repository dependency
                # is not required to be installed prior to the dependent repository even if
                # prior_installation_required is True.  This is because the only meaningful
                # content of the repository dependency is its contained agent dependency, which
                # is required in order to compile the dependent repository's agent dependency.
                # In the scenario where the repository dependency is not installed prior to the
                # dependent repository's agent dependency compilation process, the agent dependency
                # compilation framework will install the repository dependency prior to compilation
                # of the dependent repository's agent dependency.
                if not util.asbool( only_if_compiling_contained_td ):
                    if util.asbool( prior_installation_required ):
                        if is_agent_shed_client( app ):
                            # We store the port, if one exists, in the database.
                            agent_shed = common_util.remove_protocol_from_agent_shed_url( agent_shed )
                            repository = get_repository_for_dependency_relationship( app,
                                                                                     agent_shed,
                                                                                     name,
                                                                                     owner,
                                                                                     changeset_revision )
                        else:
                            repository = get_repository_by_name_and_owner( app, name, owner )
                        if repository:
                            encoded_repository_id = app.security.encode_id( repository.id )
                            if encoded_repository_id in tsr_ids:
                                prior_tsr_ids.append( encoded_repository_id )
    return prior_tsr_ids


def get_repository_in_agent_shed( app, id ):
    """Get a repository on the agent shed side from the database via id."""
    sa_session = app.model.context.current
    return sa_session.query( app.model.Repository ).get( app.security.decode_id( id ) )


def get_repository_categories( app, id ):
    """Get categories of a repository on the agent shed side from the database via id"""
    sa_session = app.model.context.current
    return sa_session.query( app.model.RepositoryCategoryAssociation ) \
        .filter(app.model.RepositoryCategoryAssociation.table.c.repository_id == app.security.decode_id( id ))


def get_repository_metadata_by_changeset_revision( app, id, changeset_revision ):
    """Get metadata for a specified repository change set from the database."""
    # Make sure there are no duplicate records, and return the single unique record for the changeset_revision.
    # Duplicate records were somehow created in the past.  The cause of this issue has been resolved, but we'll
    # leave this method as is for a while longer to ensure all duplicate records are removed.
    sa_session = app.model.context.current
    all_metadata_records = sa_session.query( app.model.RepositoryMetadata ) \
                                     .filter( and_( app.model.RepositoryMetadata.table.c.repository_id == app.security.decode_id( id ),
                                                    app.model.RepositoryMetadata.table.c.changeset_revision == changeset_revision ) ) \
                                     .order_by( app.model.RepositoryMetadata.table.c.update_time.desc() ) \
                                     .all()
    if len( all_metadata_records ) > 1:
        # Delete all records older than the last one updated.
        for repository_metadata in all_metadata_records[ 1: ]:
            sa_session.delete( repository_metadata )
            sa_session.flush()
        return all_metadata_records[ 0 ]
    elif all_metadata_records:
        return all_metadata_records[ 0 ]
    return None


def get_repository_owner( cleaned_repository_url ):
    """Gvien a "cleaned" repository clone URL, return the owner of the repository."""
    items = cleaned_repository_url.split( '/repos/' )
    repo_path = items[ 1 ]
    if repo_path.startswith( '/' ):
        repo_path = repo_path.replace( '/', '', 1 )
    return repo_path.lstrip( '/' ).split( '/' )[ 0 ]


def get_repository_owner_from_clone_url( repository_clone_url ):
    """Given a repository clone URL, return the owner of the repository."""
    tmp_url = common_util.remove_protocol_and_user_from_clone_url( repository_clone_url )
    return get_repository_owner( tmp_url )


def get_repository_query( app ):
    if is_agent_shed_client( app ):
        query = app.install_model.context.query( app.install_model.AgentShedRepository )
    else:
        query = app.model.context.query( app.model.Repository )
    return query


def get_repository_type_from_agent_shed( app, agent_shed_url, name, owner ):
    """
    Send a request to the agent shed to retrieve the type for a repository defined by the
    combination of a name and owner.
    """
    agent_shed_url = common_util.get_agent_shed_url_from_agent_shed_registry( app, agent_shed_url )
    params = dict( name=name, owner=owner )
    pathspec = [ 'repository', 'get_repository_type' ]
    repository_type = common_util.agent_shed_get( app, agent_shed_url, pathspec=pathspec, params=params )
    return repository_type


def get_agent_panel_config_agent_path_install_dir( app, repository ):
    """
    Return shed-related agent panel config, the agent_path configured in it, and the relative path to
    the directory where the repository is installed.  This method assumes all repository agents are
    defined in a single shed-related agent panel config.
    """
    agent_shed = common_util.remove_port_from_agent_shed_url( str( repository.agent_shed ) )
    relative_install_dir = '%s/repos/%s/%s/%s' % ( agent_shed,
                                                   str( repository.owner ),
                                                   str( repository.name ),
                                                   str( repository.installed_changeset_revision ) )
    # Get the relative agent installation paths from each of the shed agent configs.
    shed_config_dict = repository.get_shed_config_dict( app )
    if not shed_config_dict:
        # Just pick a semi-random shed config.
        for shed_config_dict in app.agentbox.dynamic_confs( include_migrated_agent_conf=True ):
            if ( repository.dist_to_shed and shed_config_dict[ 'config_filename' ] == app.config.migrated_agents_config ) \
                    or ( not repository.dist_to_shed and shed_config_dict[ 'config_filename' ] != app.config.migrated_agents_config ):
                break
    shed_agent_conf = shed_config_dict[ 'config_filename' ]
    agent_path = shed_config_dict[ 'agent_path' ]
    return shed_agent_conf, agent_path, relative_install_dir


def get_agent_path_by_shed_agent_conf_filename( app, shed_agent_conf ):
    """
    Return the agent_path config setting for the received shed_agent_conf file by searching the agent box's in-memory list of shed_agent_confs for the
    dictionary whose config_filename key has a value matching the received shed_agent_conf.
    """
    for shed_agent_conf_dict in app.agentbox.dynamic_confs( include_migrated_agent_conf=True ):
        config_filename = shed_agent_conf_dict[ 'config_filename' ]
        if config_filename == shed_agent_conf:
            return shed_agent_conf_dict[ 'agent_path' ]
        else:
            file_name = basic_util.strip_path( config_filename )
            if file_name == shed_agent_conf:
                return shed_agent_conf_dict[ 'agent_path' ]
    return None


def get_agent_shed_from_clone_url( repository_clone_url ):
    tmp_url = common_util.remove_protocol_and_user_from_clone_url( repository_clone_url )
    return tmp_url.split( '/repos/' )[ 0 ].rstrip( '/' )


def get_installed_repository( app, agent_shed, name, owner, changeset_revision=None, installed_changeset_revision=None ):
    """
    Return a agent shed repository database record defined by the combination of a agentshed, repository name,
    repository owner and either current or originally installed changeset_revision.
    """
    query = app.install_model.context.query( app.install_model.AgentShedRepository )
    # We store the port, if one exists, in the database.
    agent_shed = common_util.remove_protocol_from_agent_shed_url( agent_shed )
    clause_list = [ app.install_model.AgentShedRepository.table.c.agent_shed == agent_shed,
                    app.install_model.AgentShedRepository.table.c.name == name,
                    app.install_model.AgentShedRepository.table.c.owner == owner ]
    if changeset_revision is not None:
        clause_list.append( app.install_model.AgentShedRepository.table.c.changeset_revision == changeset_revision )
    if installed_changeset_revision is not None:
        clause_list.append( app.install_model.AgentShedRepository.table.c.installed_changeset_revision == installed_changeset_revision )
    return query.filter( and_( *clause_list ) ).first()


def get_agent_shed_repository_by_id( app, repository_id ):
    """Return a agent shed repository database record defined by the id."""
    # This method is used only in Galaxy, not the agent shed.
    return app.install_model.context.query( app.install_model.AgentShedRepository ) \
                                    .filter( app.install_model.AgentShedRepository.table.c.id == app.security.decode_id( repository_id ) ) \
                                    .first()


def get_agent_shed_status_for_installed_repository( app, repository ):
    """
    Send a request to the agent shed to retrieve information about newer installable repository revisions,
    current revision updates, whether the repository revision is the latest downloadable revision, and
    whether the repository has been deprecated in the agent shed.  The received repository is a AgentShedRepository
    object from Galaxy.
    """
    agent_shed_url = common_util.get_agent_shed_url_from_agent_shed_registry( app, str( repository.agent_shed ) )
    params = dict( name=repository.name, owner=repository.owner, changeset_revision=repository.changeset_revision )
    pathspec = [ 'repository', 'status_for_installed_repository' ]
    try:
        encoded_agent_shed_status_dict = common_util.agent_shed_get( app, agent_shed_url, pathspec=pathspec, params=params )
        agent_shed_status_dict = encoding_util.agent_shed_decode( encoded_agent_shed_status_dict )
        return agent_shed_status_dict
    except HTTPError, e:
        # This should handle backward compatility to the Galaxy 12/20/12 release.  We used to only handle updates for an installed revision
        # using a boolean value.
        log.debug( "Error attempting to get agent shed status for installed repository %s: %s\nAttempting older 'check_for_updates' method.\n" %
                   ( str( repository.name ), str( e ) ) )
        pathspec = [ 'repository', 'check_for_updates' ]
        params[ 'from_update_manager' ] = True
        try:
            # The value of text will be 'true' or 'false', depending upon whether there is an update available for the installed revision.
            text = common_util.agent_shed_get( app, agent_shed_url, pathspec=pathspec, params=params )
            return dict( revision_update=text )
        except Exception, e:
            # The required agent shed may be unavailable, so default the revision_update value to 'false'.
            return dict( revision_update='false' )
    except Exception, e:
        log.exception( "Error attempting to get agent shed status for installed repository %s: %s" % ( str( repository.name ), str( e ) ) )
        return {}


def get_agent_shed_repository_status_label( app, agent_shed_repository=None, name=None, owner=None, changeset_revision=None, repository_clone_url=None ):
    """Return a color-coded label for the status of the received agent-shed_repository installed into Galaxy."""
    if agent_shed_repository is None:
        if name is not None and owner is not None and repository_clone_url is not None:
            agent_shed = get_agent_shed_from_clone_url( repository_clone_url )
            agent_shed_repository = get_installed_repository( app,
                                                             agent_shed=agent_shed,
                                                             name=name,
                                                             owner=owner,
                                                             installed_changeset_revision=changeset_revision )
    if agent_shed_repository:
        status_label = agent_shed_repository.status
        if agent_shed_repository.status in [ app.install_model.AgentShedRepository.installation_status.CLONING,
                                            app.install_model.AgentShedRepository.installation_status.SETTING_TOOL_VERSIONS,
                                            app.install_model.AgentShedRepository.installation_status.INSTALLING_REPOSITORY_DEPENDENCIES,
                                            app.install_model.AgentShedRepository.installation_status.INSTALLING_TOOL_DEPENDENCIES,
                                            app.install_model.AgentShedRepository.installation_status.LOADING_PROPRIETARY_DATATYPES ]:
            bgcolor = app.install_model.AgentShedRepository.states.INSTALLING
        elif agent_shed_repository.status in [ app.install_model.AgentShedRepository.installation_status.NEW,
                                              app.install_model.AgentShedRepository.installation_status.UNINSTALLED ]:
            bgcolor = app.install_model.AgentShedRepository.states.UNINSTALLED
        elif agent_shed_repository.status in [ app.install_model.AgentShedRepository.installation_status.ERROR ]:
            bgcolor = app.install_model.AgentShedRepository.states.ERROR
        elif agent_shed_repository.status in [ app.install_model.AgentShedRepository.installation_status.DEACTIVATED ]:
            bgcolor = app.install_model.AgentShedRepository.states.WARNING
        elif agent_shed_repository.status in [ app.install_model.AgentShedRepository.installation_status.INSTALLED ]:
            if agent_shed_repository.repository_dependencies_being_installed:
                bgcolor = app.install_model.AgentShedRepository.states.WARNING
                status_label = '%s, %s' % ( status_label,
                                            app.install_model.AgentShedRepository.installation_status.INSTALLING_REPOSITORY_DEPENDENCIES )
            elif agent_shed_repository.missing_repository_dependencies:
                bgcolor = app.install_model.AgentShedRepository.states.WARNING
                status_label = '%s, missing repository dependencies' % status_label
            elif agent_shed_repository.agent_dependencies_being_installed:
                bgcolor = app.install_model.AgentShedRepository.states.WARNING
                status_label = '%s, %s' % ( status_label,
                                            app.install_model.AgentShedRepository.installation_status.INSTALLING_TOOL_DEPENDENCIES )
            elif agent_shed_repository.missing_agent_dependencies:
                bgcolor = app.install_model.AgentShedRepository.states.WARNING
                status_label = '%s, missing agent dependencies' % status_label
            else:
                bgcolor = app.install_model.AgentShedRepository.states.OK
        else:
            bgcolor = app.install_model.AgentShedRepository.states.ERROR
    else:
        bgcolor = app.install_model.AgentShedRepository.states.WARNING
        status_label = 'unknown status'
    return '<div class="count-box state-color-%s">%s</div>' % ( bgcolor, status_label )


def get_updated_changeset_revisions( app, name, owner, changeset_revision ):
    """
    Return a string of comma-separated changeset revision hashes for all available updates to the received changeset
    revision for the repository defined by the received name and owner.
    """
    repository = get_repository_by_name_and_owner( app, name, owner )
    repo = hg_util.get_repo_for_repository( app, repository=repository, repo_path=None, create=False )
    # Get the upper bound changeset revision.
    upper_bound_changeset_revision = get_next_downloadable_changeset_revision( repository, repo, changeset_revision )
    # Build the list of changeset revision hashes defining each available update up to, but excluding
    # upper_bound_changeset_revision.
    changeset_hashes = []
    for changeset in hg_util.reversed_lower_upper_bounded_changelog( repo, changeset_revision, upper_bound_changeset_revision ):
        # Make sure to exclude upper_bound_changeset_revision.
        if changeset != upper_bound_changeset_revision:
            changeset_hashes.append( str( repo.changectx( changeset ) ) )
    if changeset_hashes:
        changeset_hashes_str = ','.join( changeset_hashes )
        return changeset_hashes_str
    return ''


def get_updated_changeset_revisions_from_agent_shed( app, agent_shed_url, name, owner, changeset_revision ):
    """
    Get all appropriate newer changeset revisions for the repository defined by
    the received agent_shed_url / name / owner combination.
    """
    agent_shed_url = common_util.get_agent_shed_url_from_agent_shed_registry( app, agent_shed_url )
    if agent_shed_url is None or name is None or owner is None or changeset_revision is None:
        message = "Unable to get updated changeset revisions from the Agent Shed because one or more of the following "
        message += "required parameters is None: agent_shed_url: %s, name: %s, owner: %s, changeset_revision: %s " % \
            ( str( agent_shed_url ), str( name ), str( owner ), str( changeset_revision ) )
        raise Exception( message )
    params = dict( name=name, owner=owner, changeset_revision=changeset_revision )
    pathspec = [ 'repository', 'updated_changeset_revisions' ]
    text = common_util.agent_shed_get( app, agent_shed_url, pathspec=pathspec, params=params )
    return text


def get_user( app, id ):
    """Get a user from the database by id."""
    sa_session = app.model.context.current
    return sa_session.query( app.model.User ).get( app.security.decode_id( id ) )


def get_user_by_username( app, username ):
    """Get a user from the database by username."""
    sa_session = app.model.context.current
    try:
        user = sa_session.query( app.model.User ) \
                         .filter( app.model.User.table.c.username == username ) \
                         .one()
        return user
    except Exception:
        return None


def handle_email_alerts( app, host, repository, content_alert_str='', new_repo_alert=False, admin_only=False ):
    """
    There are 2 complementary features that enable a agent shed user to receive email notification:
    1. Within User Preferences, they can elect to receive email when the first (or first valid)
       change set is produced for a new repository.
    2. When viewing or managing a repository, they can check the box labeled "Receive email alerts"
       which caused them to receive email alerts when updates to the repository occur.  This same feature
       is available on a per-repository basis on the repository grid within the agent shed.

    There are currently 4 scenarios for sending email notification when a change is made to a repository:
    1. An admin user elects to receive email when the first change set is produced for a new repository
       from User Preferences.  The change set does not have to include any valid content.  This allows for
       the capture of inappropriate content being uploaded to new repositories.
    2. A regular user elects to receive email when the first valid change set is produced for a new repository
       from User Preferences.  This differs from 1 above in that the user will not receive email until a
       change set tha tincludes valid content is produced.
    3. An admin user checks the "Receive email alerts" check box on the manage repository page.  Since the
       user is an admin user, the email will include information about both HTML and image content that was
       included in the change set.
    4. A regular user checks the "Receive email alerts" check box on the manage repository page.  Since the
       user is not an admin user, the email will not include any information about both HTML and image content
       that was included in the change set.
    """
    sa_session = app.model.context.current
    repo = hg_util.get_repo_for_repository( app, repository=repository, repo_path=None, create=False )
    sharable_link = generate_sharable_link_for_repository_in_agent_shed( repository, changeset_revision=None )
    smtp_server = app.config.smtp_server
    if smtp_server and ( new_repo_alert or repository.email_alerts ):
        # Send email alert to users that want them.
        if app.config.email_from is not None:
            email_from = app.config.email_from
        elif host.split( ':' )[0] in [ 'localhost', '127.0.0.1', '0.0.0.0' ]:
            email_from = 'galaxy-no-reply@' + socket.getfqdn()
        else:
            email_from = 'galaxy-no-reply@' + host.split( ':' )[0]
        tip_changeset = repo.changelog.tip()
        ctx = repo.changectx( tip_changeset )
        try:
            username = ctx.user().split()[0]
        except:
            username = ctx.user()
        # We'll use 2 template bodies because we only want to send content
        # alerts to agent shed admin users.
        if new_repo_alert:
            template = new_repo_email_alert_template
        else:
            template = email_alert_template
        display_date = hg_util.get_readable_ctx_date( ctx )
        admin_body = string.Template( template ).safe_substitute( host=host,
                                                                  sharable_link=sharable_link,
                                                                  repository_name=repository.name,
                                                                  revision='%s:%s' % ( str( ctx.rev() ), ctx ),
                                                                  display_date=display_date,
                                                                  description=ctx.description(),
                                                                  username=username,
                                                                  content_alert_str=content_alert_str )
        body = string.Template( template ).safe_substitute( host=host,
                                                            sharable_link=sharable_link,
                                                            repository_name=repository.name,
                                                            revision='%s:%s' % ( str( ctx.rev() ), ctx ),
                                                            display_date=display_date,
                                                            description=ctx.description(),
                                                            username=username,
                                                            content_alert_str='' )
        admin_users = app.config.get( "admin_users", "" ).split( "," )
        frm = email_from
        if new_repo_alert:
            subject = "Galaxy agent shed alert for new repository named %s" % str( repository.name )
            subject = subject[ :80 ]
            email_alerts = []
            for user in sa_session.query( app.model.User ) \
                                  .filter( and_( app.model.User.table.c.deleted == false(),
                                                 app.model.User.table.c.new_repo_alert == true() ) ):
                if admin_only:
                    if user.email in admin_users:
                        email_alerts.append( user.email )
                else:
                    email_alerts.append( user.email )
        else:
            subject = "Galaxy agent shed update alert for repository named %s" % str( repository.name )
            email_alerts = json.loads( repository.email_alerts )
        for email in email_alerts:
            to = email.strip()
            # Send it
            try:
                if to in admin_users:
                    util.send_mail( frm, to, subject, admin_body, app.config )
                else:
                    util.send_mail( frm, to, subject, body, app.config )
            except Exception:
                log.exception( "An error occurred sending a agent shed repository update alert by email." )


def have_shed_agent_conf_for_install( app ):
    return bool( app.agentbox.dynamic_confs( include_migrated_agent_conf=False ) )


def is_agent_shed_client( app ):
    """
    The agent shed and clients to the agent (i.e. Galaxy) require a lot
    of similar functionality in this file but with small differences. This
    method should determine if the app performing the action is the agent shed
    or a client of the agent shed.
    """
    return hasattr( app, "install_model" )


def open_repository_files_folder( folder_path ):
    """
    Return a list of dictionaries, each of which contains information for a file or directory contained
    within a directory in a repository file hierarchy.
    """
    try:
        files_list = get_repository_files( folder_path )
    except OSError, e:
        if str( e ).find( 'No such file or directory' ) >= 0:
            # We have a repository with no contents.
            return []
    folder_contents = []
    for filename in files_list:
        is_folder = False
        if filename and filename[ -1 ] == os.sep:
            is_folder = True
        if filename:
            full_path = os.path.join( folder_path, filename )
            node = { "title": filename,
                     "isFolder": is_folder,
                     "isLazy": is_folder,
                     "agenttip": full_path,
                     "key": full_path }
            folder_contents.append( node )
    return folder_contents


def repository_was_previously_installed( app, agent_shed_url, repository_name, repo_info_tuple, from_tip=False ):
    """
    Find out if a repository is already installed into Galaxy - there are several scenarios where this
    is necessary.  For example, this method will handle the case where the repository was previously
    installed using an older changeset_revsion, but later the repository was updated in the agent shed
    and now we're trying to install the latest changeset revision of the same repository instead of
    updating the one that was previously installed.  We'll look in the database instead of on disk since
    the repository may be currently uninstalled.
    """
    agent_shed_url = common_util.get_agent_shed_url_from_agent_shed_registry( app, agent_shed_url )
    description, repository_clone_url, changeset_revision, ctx_rev, repository_owner, repository_dependencies, agent_dependencies = \
        get_repo_info_tuple_contents( repo_info_tuple )
    agent_shed = get_agent_shed_from_clone_url( repository_clone_url )
    # See if we can locate the repository using the value of changeset_revision.
    agent_shed_repository = get_installed_repository( app,
                                                     agent_shed=agent_shed,
                                                     name=repository_name,
                                                     owner=repository_owner,
                                                     installed_changeset_revision=changeset_revision )
    if agent_shed_repository:
        return agent_shed_repository, changeset_revision
    # Get all previous changeset revisions from the agent shed for the repository back to, but excluding,
    # the previous valid changeset revision to see if it was previously installed using one of them.
    params = dict( galaxy_url=url_for( '/', qualified=True ),
                   name=repository_name,
                   owner=repository_owner,
                   changeset_revision=changeset_revision,
                   from_tip=str( from_tip ) )
    pathspec = [ 'repository', 'previous_changeset_revisions' ]
    text = common_util.agent_shed_get( app, agent_shed_url, pathspec=pathspec, params=params )
    if text:
        changeset_revisions = util.listify( text )
        for previous_changeset_revision in changeset_revisions:
            agent_shed_repository = get_installed_repository( app,
                                                             agent_shed=agent_shed,
                                                             name=repository_name,
                                                             owner=repository_owner,
                                                             installed_changeset_revision=previous_changeset_revision )
            if agent_shed_repository:
                return agent_shed_repository, previous_changeset_revision
    return None, None


def set_image_paths( app, encoded_repository_id, text ):
    """
    Handle agent help image display for agents that are contained in repositories in
    the agent shed or installed into Galaxy as well as image display in repository
    README files.  This method will determine the location of the image file and
    return the path to it that will enable the caller to open the file.
    """
    if text:
        if is_agent_shed_client( app ):
            route_to_images = 'admin_agentshed/static/images/%s' % encoded_repository_id
        else:
            # We're in the agent shed.
            route_to_images = '/repository/static/images/%s' % encoded_repository_id
        # We used to require $PATH_TO_IMAGES and ${static_path}, but
        # we now eliminate it if it's used.
        text = text.replace( '$PATH_TO_IMAGES', '' )
        text = text.replace( '${static_path}', '' )
        # Use regex to instantiate routes into the defined image paths, but replace
        # paths that start with neither http:// nor https://, which will allow for
        # settings like .. images:: http_files/images/help.png
        for match in re.findall( '.. image:: (?!http)/?(.+)', text ):
            text = text.replace( match, match.replace( '/', '%2F' ) )
        text = re.sub( r'\.\. image:: (?!https?://)/?(.+)', r'.. image:: %s/\1' % route_to_images, text )
    return text


def set_repository_attributes( app, repository, status, error_message, deleted, uninstalled, remove_from_disk=False ):
    if remove_from_disk:
        relative_install_dir = repository.repo_path( app )
        if relative_install_dir:
            clone_dir = os.path.abspath( relative_install_dir )
            try:
                shutil.rmtree( clone_dir )
                log.debug( "Removed repository installation directory: %s" % str( clone_dir ) )
            except Exception, e:
                log.debug( "Error removing repository installation directory %s: %s" % ( str( clone_dir ), str( e ) ) )
    repository.error_message = error_message
    repository.status = status
    repository.deleted = deleted
    repository.uninstalled = uninstalled
    app.install_model.context.add( repository )
    app.install_model.context.flush()


def agent_shed_is_this_agent_shed( agentshed_base_url ):
    """Determine if a agent shed is the current agent shed."""
    cleaned_agentshed_base_url = common_util.remove_protocol_from_agent_shed_url( agentshed_base_url )
    cleaned_agent_shed = common_util.remove_protocol_from_agent_shed_url( str( url_for( '/', qualified=True ) ) )
    return cleaned_agentshed_base_url == cleaned_agent_shed
