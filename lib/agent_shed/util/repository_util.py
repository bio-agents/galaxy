import ConfigParser
import logging
import os
import re

from sqlalchemy import false

from galaxy import util
from galaxy import web
from galaxy.web.form_builder import build_select_field
from galaxy.webapps.agent_shed.model import directory_hash_id
from agent_shed.dependencies.repository import relation_builder
from agent_shed.util import common_util
from agent_shed.util import hg_util
from agent_shed.util import shed_util_common as suc
from agent_shed.util.web_util import escape

log = logging.getLogger( __name__ )

VALID_REPOSITORYNAME_RE = re.compile( "^[a-z0-9\_]+$" )


def build_allow_push_select_field( trans, current_push_list, selected_value='none' ):
    options = []
    for user in trans.sa_session.query( trans.model.User ):
        if user.username not in current_push_list:
            options.append( user )
    return build_select_field( trans,
                               objs=options,
                               label_attr='username',
                               select_field_name='allow_push',
                               selected_value=selected_value,
                               refresh_on_change=False,
                               multiple=True )


def change_repository_name_in_hgrc_file( hgrc_file, new_name ):
    config = ConfigParser.ConfigParser()
    config.read( hgrc_file )
    config.read( hgrc_file )
    config.set( 'web', 'name', new_name )
    new_file = open( hgrc_file, 'wb' )
    config.write( new_file )
    new_file.close()


def check_or_update_agent_shed_status_for_installed_repository( app, repository ):
    updated = False
    agent_shed_status_dict = suc.get_agent_shed_status_for_installed_repository( app, repository )
    if agent_shed_status_dict:
        ok = True
        if agent_shed_status_dict != repository.agent_shed_status:
            repository.agent_shed_status = agent_shed_status_dict
            app.install_model.context.add( repository )
            app.install_model.context.flush()
            updated = True
    else:
        ok = False
    return ok, updated


def create_repo_info_dict( app, repository_clone_url, changeset_revision, ctx_rev, repository_owner, repository_name=None,
                           repository=None, repository_metadata=None, agent_dependencies=None, repository_dependencies=None ):
    """
    Return a dictionary that includes all of the information needed to install a repository into a local
    Galaxy instance.  The dictionary will also contain the recursive list of repository dependencies defined
    for the repository, as well as the defined agent dependencies.

    This method is called from Galaxy under four scenarios:
    1. During the agent shed repository installation process via the agent shed's get_repository_information()
    method.  In this case both the received repository and repository_metadata will be objects, but
    agent_dependencies and repository_dependencies will be None.
    2. When getting updates for an installed repository where the updates include newly defined repository
    dependency definitions.  This scenario is similar to 1. above. The agent shed's get_repository_information()
    method is the caller, and both the received repository and repository_metadata will be objects, but
    agent_dependencies and repository_dependencies will be None.
    3. When a agent shed repository that was uninstalled from a Galaxy instance is being reinstalled with no
    updates available.  In this case, both repository and repository_metadata will be None, but agent_dependencies
    and repository_dependencies will be objects previously retrieved from the agent shed if the repository includes
    definitions for them.
    4. When a agent shed repository that was uninstalled from a Galaxy instance is being reinstalled with updates
    available.  In this case, this method is reached via the agent shed's get_updated_repository_information()
    method, and both repository and repository_metadata will be objects but agent_dependencies and
    repository_dependencies will be None.
    """
    repo_info_dict = {}
    repository = suc.get_repository_by_name_and_owner( app, repository_name, repository_owner )
    if app.name == 'agent_shed':
        # We're in the agent shed.
        repository_metadata = suc.get_repository_metadata_by_changeset_revision( app,
                                                                                 app.security.encode_id( repository.id ),
                                                                                 changeset_revision )
        if repository_metadata:
            metadata = repository_metadata.metadata
            if metadata:
                agent_shed_url = str( web.url_for( '/', qualified=True ) ).rstrip( '/' )
                rb = relation_builder.RelationBuilder( app, repository, repository_metadata, agent_shed_url )
                # Get a dictionary of all repositories upon which the contents of the received repository depends.
                repository_dependencies = rb.get_repository_dependencies_for_changeset_revision()
                agent_dependencies = metadata.get( 'agent_dependencies', {} )
    if agent_dependencies:
        new_agent_dependencies = {}
        for dependency_key, requirements_dict in agent_dependencies.items():
            if dependency_key in [ 'set_environment' ]:
                new_set_environment_dict_list = []
                for set_environment_dict in requirements_dict:
                    set_environment_dict[ 'repository_name' ] = repository_name
                    set_environment_dict[ 'repository_owner' ] = repository_owner
                    set_environment_dict[ 'changeset_revision' ] = changeset_revision
                    new_set_environment_dict_list.append( set_environment_dict )
                new_agent_dependencies[ dependency_key ] = new_set_environment_dict_list
            else:
                requirements_dict[ 'repository_name' ] = repository_name
                requirements_dict[ 'repository_owner' ] = repository_owner
                requirements_dict[ 'changeset_revision' ] = changeset_revision
                new_agent_dependencies[ dependency_key ] = requirements_dict
        agent_dependencies = new_agent_dependencies
    # Cast unicode to string, with the exception of description, since it is free text and can contain special characters.
    repo_info_dict[ str( repository.name ) ] = ( repository.description,
                                                 str( repository_clone_url ),
                                                 str( changeset_revision ),
                                                 str( ctx_rev ),
                                                 str( repository_owner ),
                                                 repository_dependencies,
                                                 agent_dependencies )
    return repo_info_dict


def create_repository( app, name, type, description, long_description, user_id, category_ids=[], remote_repository_url=None, homepage_url=None ):
    """Create a new AgentShed repository"""
    sa_session = app.model.context.current
    # Add the repository record to the database.
    repository = app.model.Repository( name=name,
                                       type=type,
                                       remote_repository_url=remote_repository_url,
                                       homepage_url=homepage_url,
                                       description=description,
                                       long_description=long_description,
                                       user_id=user_id )
    # Flush to get the id.
    sa_session.add( repository )
    sa_session.flush()
    # Create an admin role for the repository.
    create_repository_admin_role( app, repository )
    # Determine the repository's repo_path on disk.
    dir = os.path.join( app.config.file_path, *directory_hash_id( repository.id ) )
    # Create directory if it does not exist.
    if not os.path.exists( dir ):
        os.makedirs( dir )
    # Define repo name inside hashed directory.
    repository_path = os.path.join( dir, "repo_%d" % repository.id )
    # Create local repository directory.
    if not os.path.exists( repository_path ):
        os.makedirs( repository_path )
    # Create the local repository.
    hg_util.get_repo_for_repository( app, repository=None, repo_path=repository_path, create=True )
    # Add an entry in the hgweb.config file for the local repository.
    lhs = "repos/%s/%s" % ( repository.user.username, repository.name )
    app.hgweb_config_manager.add_entry( lhs, repository_path )
    # Create a .hg/hgrc file for the local repository.
    hg_util.create_hgrc_file( app, repository )
    flush_needed = False
    if category_ids:
        # Create category associations
        for category_id in category_ids:
            category = sa_session.query( app.model.Category ) \
                                 .get( app.security.decode_id( category_id ) )
            rca = app.model.RepositoryCategoryAssociation( repository, category )
            sa_session.add( rca )
            flush_needed = True
    if flush_needed:
        sa_session.flush()
    # Update the repository registry.
    app.repository_registry.add_entry( repository )
    message = "Repository <b>%s</b> has been created." % escape( str( repository.name ) )
    return repository, message


def update_repository( app, trans, id, **kwds ):
    """Update an existing AgentShed repository"""
    message = None
    flush_needed = False
    sa_session = app.model.context.current
    repository = sa_session.query( app.model.Repository ).get( app.security.decode_id( id ) )
    if repository is None:
        return None, "Unknown repository ID"

    if not ( trans.user_is_admin() or
            trans.app.security_agent.user_can_administer_repository( trans.user, repository ) ):
        message = "You are not the owner of this repository, so you cannot administer it."
        return None, message

    # Whitelist properties that can be changed via this method
    for key in ( 'type', 'description', 'long_description', 'remote_repository_url', 'homepage_url' ):
        # If that key is available, not None and different than what's in the model
        if key in kwds and kwds[ key ] is not None and kwds[ key ] != getattr( repository, key ):
            setattr( repository, key, kwds[ key ] )
            flush_needed = True

    if 'category_ids' in kwds and isinstance( kwds[ 'category_ids' ], list ):
        # Get existing category associations
        category_associations = sa_session.query( app.model.RepositoryCategoryAssociation ) \
                                          .filter( app.model.RepositoryCategoryAssociation.table.c.repository_id == app.security.decode_id( id ) )
        # Remove all of them
        for rca in category_associations:
            sa_session.delete( rca )

        # Then (re)create category associations
        for category_id in kwds[ 'category_ids' ]:
            category = sa_session.query( app.model.Category ) \
                                 .get( app.security.decode_id( category_id ) )
            if category:
                rca = app.model.RepositoryCategoryAssociation( repository, category )
                sa_session.add( rca )
            else:
                pass
        flush_needed = True

    # However some properties are special, like 'name'
    if 'name' in kwds and kwds[ 'name' ] is not None and repository.name != kwds[ 'name' ]:
        if repository.times_downloaded != 0:
            message = "Repository names cannot be changed if the repository has been cloned."
        else:
            message = validate_repository_name( trans.app, kwds[ 'name' ], trans.user )
        if message:
            return None, message

        repo_dir = repository.repo_path( app )
        # Change the entry in the hgweb.config file for the repository.
        old_lhs = "repos/%s/%s" % ( repository.user.username, repository.name )
        new_lhs = "repos/%s/%s" % ( repository.user.username, kwds[ 'name' ] )
        trans.app.hgweb_config_manager.change_entry( old_lhs, new_lhs, repo_dir )

        # Change the entry in the repository's hgrc file.
        hgrc_file = os.path.join( repo_dir, '.hg', 'hgrc' )
        change_repository_name_in_hgrc_file( hgrc_file, kwds[ 'name' ] )

        # Rename the repository's admin role to match the new repository name.
        repository_admin_role = repository.admin_role
        repository_admin_role.name = get_repository_admin_role_name( str( kwds[ 'name' ] ), str( repository.user.username ) )
        trans.sa_session.add( repository_admin_role )
        repository.name = kwds[ 'name' ]
        flush_needed = True

    if flush_needed:
        trans.sa_session.add( repository )
        trans.sa_session.flush()
        message = "The repository information has been updated."
    else:
        message = None
    return repository, message


def create_repository_admin_role( app, repository ):
    """
    Create a new role with name-spaced name based on the repository name and its owner's public user
    name.  This will ensure that the tole name is unique.
    """
    sa_session = app.model.context.current
    name = get_repository_admin_role_name( str( repository.name ), str( repository.user.username ) )
    description = 'A user or group member with this role can administer this repository.'
    role = app.model.Role( name=name, description=description, type=app.model.Role.types.SYSTEM )
    sa_session.add( role )
    sa_session.flush()
    # Associate the role with the repository owner.
    app.model.UserRoleAssociation( repository.user, role )
    # Associate the role with the repository.
    rra = app.model.RepositoryRoleAssociation( repository, role )
    sa_session.add( rra )
    sa_session.flush()
    return role


def get_installed_agent_shed_repository( app, id ):
    """Get a agent shed repository record from the Galaxy database defined by the id."""
    rval = []
    if isinstance( id, list ):
        return_list = True
    else:
        id = [ id ]
        return_list = False
    for i in id:
        rval.append( app.install_model.context.query( app.install_model.AgentShedRepository ).get( app.security.decode_id( i ) ) )
    if return_list:
        return rval
    return rval[0]


def get_repo_info_dict( app, user, repository_id, changeset_revision ):
    repository = suc.get_repository_in_agent_shed( app, repository_id )
    repo = hg_util.get_repo_for_repository( app, repository=repository, repo_path=None, create=False )
    repository_clone_url = common_util.generate_clone_url_for_repository_in_agent_shed( user, repository )
    repository_metadata = suc.get_repository_metadata_by_changeset_revision( app,
                                                                             repository_id,
                                                                             changeset_revision )
    if not repository_metadata:
        # The received changeset_revision is no longer installable, so get the next changeset_revision
        # in the repository's changelog.  This generally occurs only with repositories of type
        # repository_suite_definition or agent_dependency_definition.
        next_downloadable_changeset_revision = \
            suc.get_next_downloadable_changeset_revision( repository, repo, changeset_revision )
        if next_downloadable_changeset_revision:
            repository_metadata = suc.get_repository_metadata_by_changeset_revision( app,
                                                                                     repository_id,
                                                                                     next_downloadable_changeset_revision )
    if repository_metadata:
        # For now, we'll always assume that we'll get repository_metadata, but if we discover our assumption
        # is not valid we'll have to enhance the callers to handle repository_metadata values of None in the
        # returned repo_info_dict.
        metadata = repository_metadata.metadata
        if 'agents' in metadata:
            includes_agents = True
        else:
            includes_agents = False
        includes_agents_for_display_in_agent_panel = repository_metadata.includes_agents_for_display_in_agent_panel
        repository_dependencies_dict = metadata.get( 'repository_dependencies', {} )
        repository_dependencies = repository_dependencies_dict.get( 'repository_dependencies', [] )
        has_repository_dependencies, has_repository_dependencies_only_if_compiling_contained_td = \
            suc.get_repository_dependency_types( repository_dependencies )
        if 'agent_dependencies' in metadata:
            includes_agent_dependencies = True
        else:
            includes_agent_dependencies = False
    else:
        # Here's where we may have to handle enhancements to the callers. See above comment.
        includes_agents = False
        has_repository_dependencies = False
        has_repository_dependencies_only_if_compiling_contained_td = False
        includes_agent_dependencies = False
        includes_agents_for_display_in_agent_panel = False
    ctx = hg_util.get_changectx_for_changeset( repo, changeset_revision )
    repo_info_dict = create_repo_info_dict( app=app,
                                            repository_clone_url=repository_clone_url,
                                            changeset_revision=changeset_revision,
                                            ctx_rev=str( ctx.rev() ),
                                            repository_owner=repository.user.username,
                                            repository_name=repository.name,
                                            repository=repository,
                                            repository_metadata=repository_metadata,
                                            agent_dependencies=None,
                                            repository_dependencies=None )
    return repo_info_dict, includes_agents, includes_agent_dependencies, includes_agents_for_display_in_agent_panel, \
        has_repository_dependencies, has_repository_dependencies_only_if_compiling_contained_td


def get_repository_admin_role_name( repository_name, repository_owner ):
    return '%s_%s_admin' % ( str( repository_name ), str( repository_owner ) )


def get_role_by_id( app, role_id ):
    """Get a Role from the database by id."""
    sa_session = app.model.context.current
    return sa_session.query( app.model.Role ).get( app.security.decode_id( role_id ) )


def handle_role_associations( app, role, repository, **kwd ):
    sa_session = app.model.context.current
    message = escape( kwd.get( 'message', '' ) )
    status = kwd.get( 'status', 'done' )
    repository_owner = repository.user
    if kwd.get( 'manage_role_associations_button', False ):
        in_users_list = util.listify( kwd.get( 'in_users', [] ) )
        in_users = [ sa_session.query( app.model.User ).get( x ) for x in in_users_list ]
        # Make sure the repository owner is always associated with the repostory's admin role.
        owner_associated = False
        for user in in_users:
            if user.id == repository_owner.id:
                owner_associated = True
                break
        if not owner_associated:
            in_users.append( repository_owner )
            message += "The repository owner must always be associated with the repository's administrator role.  "
            status = 'error'
        in_groups_list = util.listify( kwd.get( 'in_groups', [] ) )
        in_groups = [ sa_session.query( app.model.Group ).get( x ) for x in in_groups_list ]
        in_repositories = [ repository ]
        app.security_agent.set_entity_role_associations( roles=[ role ],
                                                         users=in_users,
                                                         groups=in_groups,
                                                         repositories=in_repositories )
        sa_session.refresh( role )
        message += "Role <b>%s</b> has been associated with %d users, %d groups and %d repositories.  " % \
            ( escape( str( role.name ) ), len( in_users ), len( in_groups ), len( in_repositories ) )
    in_users = []
    out_users = []
    in_groups = []
    out_groups = []
    for user in sa_session.query( app.model.User ) \
                          .filter( app.model.User.table.c.deleted == false() ) \
                          .order_by( app.model.User.table.c.email ):
        if user in [ x.user for x in role.users ]:
            in_users.append( ( user.id, user.email ) )
        else:
            out_users.append( ( user.id, user.email ) )
    for group in sa_session.query( app.model.Group ) \
                           .filter( app.model.Group.table.c.deleted == false() ) \
                           .order_by( app.model.Group.table.c.name ):
        if group in [ x.group for x in role.groups ]:
            in_groups.append( ( group.id, group.name ) )
        else:
            out_groups.append( ( group.id, group.name ) )
    associations_dict = dict( in_users=in_users,
                              out_users=out_users,
                              in_groups=in_groups,
                              out_groups=out_groups,
                              message=message,
                              status=status )
    return associations_dict


def validate_repository_name( app, name, user ):
    """
    Validate whether the given name qualifies as a new TS repo name.
    Repository names must be unique for each user, must be at least two characters
    in length and must contain only lower-case letters, numbers, and the '_' character.
    """
    if name in [ 'None', None, '' ]:
        return 'Enter the required repository name.'
    if name in [ 'repos' ]:
        return "The term <b>%s</b> is a reserved word in the agent shed, so it cannot be used as a repository name." % name
    check_existing = suc.get_repository_by_name_and_owner( app, name, user.username )
    if check_existing is not None:
        if check_existing.deleted:
            return 'You own a deleted repository named <b>%s</b>, please choose a different name.' % escape( name )
        else:
            return "You already own a repository named <b>%s</b>, please choose a different name." % escape( name )
    if len( name ) < 2:
        return "Repository names must be at least 2 characters in length."
    if len( name ) > 80:
        return "Repository names cannot be more than 80 characters in length."
    if not( VALID_REPOSITORYNAME_RE.match( name ) ):
        return "Repository names must contain only lower-case letters, numbers and underscore."
    return ''
