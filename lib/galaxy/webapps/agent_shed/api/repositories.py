import json
import logging
import os
import tarfile
import StringIO
from cgi import FieldStorage
from collections import namedtuple
from time import strftime

from sqlalchemy import and_, false

from galaxy import util
from galaxy import web
from galaxy.util import checkers
from galaxy.exceptions import ActionInputError
from galaxy.exceptions import ConfigDoesNotAllowException
from galaxy.exceptions import InsufficientPermissionsException
from galaxy.exceptions import MalformedId
from galaxy.exceptions import ObjectNotFound
from galaxy.exceptions import RequestParameterInvalidException
from galaxy.exceptions import RequestParameterMissingException
from galaxy.web import _future_expose_api as expose_api
from galaxy.web import _future_expose_api_anonymous_and_sessionless as expose_api_anonymous_and_sessionless
from galaxy.web import _future_expose_api_raw_anonymous_and_sessionless as expose_api_raw_anonymous_and_sessionless
from galaxy.web.base.controller import BaseAPIController
from galaxy.web.base.controller import HTTPBadRequest
from galaxy.webapps.agent_shed.search.repo_search import RepoSearch
from agent_shed.capsule import capsule_manager
from agent_shed.dependencies import attribute_handlers
from agent_shed.metadata import repository_metadata_manager
from agent_shed.repository_types import util as rt_util
from agent_shed.util import basic_util
from agent_shed.util import commit_util
from agent_shed.util import encoding_util
from agent_shed.util import hg_util
from agent_shed.util import repository_content_util
from agent_shed.util import repository_util
from agent_shed.util import shed_util_common as suc
from agent_shed.util import agent_util

log = logging.getLogger( __name__ )


class RepositoriesController( BaseAPIController ):
    """RESTful controller for interactions with repositories in the Agent Shed."""

    @web.expose_api
    def add_repository_registry_entry( self, trans, payload, **kwd ):
        """
        POST /api/repositories/add_repository_registry_entry
        Adds appropriate entries to the repository registry for the repository defined by the received name and owner.

        :param key: the user's API key

        The following parameters are included in the payload.
        :param agent_shed_url (required): the base URL of the Agent Shed containing the Repository
        :param name (required): the name of the Repository
        :param owner (required): the owner of the Repository
        """
        response_dict = {}
        if not trans.user_is_admin():
            response_dict[ 'status' ] = 'error'
            response_dict[ 'message' ] = "You are not authorized to add entries to this Agent Shed's repository registry."
            return response_dict
        agent_shed_url = payload.get( 'agent_shed_url', '' )
        if not agent_shed_url:
            raise HTTPBadRequest( detail="Missing required parameter 'agent_shed_url'." )
        agent_shed_url = agent_shed_url.rstrip( '/' )
        name = payload.get( 'name', '' )
        if not name:
            raise HTTPBadRequest( detail="Missing required parameter 'name'." )
        owner = payload.get( 'owner', '' )
        if not owner:
            raise HTTPBadRequest( detail="Missing required parameter 'owner'." )
        repository = suc.get_repository_by_name_and_owner( trans.app, name, owner )
        if repository is None:
            error_message = 'Cannot locate repository with name %s and owner %s,' % ( str( name ), str( owner ) )
            log.debug( error_message )
            response_dict[ 'status' ] = 'error'
            response_dict[ 'message' ] = error_message
            return response_dict
        # Update the repository registry.
        trans.app.repository_registry.add_entry( repository )
        response_dict[ 'status' ] = 'ok'
        response_dict[ 'message' ] = 'Entries for repository %s owned by %s have been added to the Agent Shed repository registry.' \
            % ( name, owner )
        return response_dict

    @web.expose_api_anonymous
    def get_ordered_installable_revisions( self, trans, name, owner, **kwd ):
        """
        GET /api/repositories/get_ordered_installable_revisions

        :param name: the name of the Repository
        :param owner: the owner of the Repository

        Returns the ordered list of changeset revision hash strings that are associated with installable revisions.
        As in the changelog, the list is ordered oldest to newest.
        """
        # Example URL: http://localhost:9009/api/repositories/get_installable_revisions?name=add_column&owner=test
        if name and owner:
            # Get the repository information.
            repository = suc.get_repository_by_name_and_owner( trans.app, name, owner )
            if repository is None:
                error_message = "Error in the Agent Shed repositories API in get_ordered_installable_revisions: "
                error_message += "cannot locate repository %s owned by %s." % ( str( name ), str( owner ) )
                log.debug( error_message )
                return []
            repo = hg_util.get_repo_for_repository( trans.app, repository=repository, repo_path=None, create=False )
            ordered_installable_revisions = suc.get_ordered_metadata_changeset_revisions( repository, repo, downloadable=True )
            return ordered_installable_revisions
        else:
            error_message = "Error in the Agent Shed repositories API in get_ordered_installable_revisions: "
            error_message += "invalid name %s or owner %s received." % ( str( name ), str( owner ) )
            log.debug( error_message )
            return []

    @web.expose_api_anonymous
    def get_repository_revision_install_info( self, trans, name, owner, changeset_revision, **kwd ):
        """
        GET /api/repositories/get_repository_revision_install_info

        :param name: the name of the Repository
        :param owner: the owner of the Repository
        :param changeset_revision: the changeset_revision of the RepositoryMetadata object associated with the Repository

        Returns a list of the following dictionaries::
        - a dictionary defining the Repository.  For example:
        {
            "deleted": false,
            "deprecated": false,
            "description": "add_column hello",
            "id": "f9cad7b01a472135",
            "long_description": "add_column hello",
            "name": "add_column",
            "owner": "test",
            "private": false,
            "times_downloaded": 6,
            "url": "/api/repositories/f9cad7b01a472135",
            "user_id": "f9cad7b01a472135"
        }
        - a dictionary defining the Repository revision (RepositoryMetadata).  For example:
        {
            "changeset_revision": "3a08cc21466f",
            "downloadable": true,
            "has_repository_dependencies": false,
            "has_repository_dependencies_only_if_compiling_contained_td": false,
            "id": "f9cad7b01a472135",
            "includes_datatypes": false,
            "includes_agent_dependencies": false,
            "includes_agents": true,
            "includes_agents_for_display_in_agent_panel": true,
            "includes_workflows": false,
            "malicious": false,
            "repository_id": "f9cad7b01a472135",
            "url": "/api/repository_revisions/f9cad7b01a472135",
            "valid_agents": [{u'add_to_agent_panel': True,
                u'description': u'data on any column using simple expressions',
                u'guid': u'localhost:9009/repos/enis/sample_repo_1/Filter1/2.2.0',
                u'id': u'Filter1',
                u'name': u'Filter',
                u'requirements': [],
                u'tests': [{u'inputs': [[u'input', u'1.bed'], [u'cond', u"c1=='chr22'"]],
                  u'name': u'Test-1',
                  u'outputs': [[u'out_file1', u'filter1_test1.bed']],
                  u'required_files': [u'1.bed', u'filter1_test1.bed']}],
                u'agent_config': u'database/community_files/000/repo_1/filtering.xml',
                u'agent_type': u'default',
                u'version': u'2.2.0',
                u'version_string_cmd': None}]
        }
        - a dictionary including the additional information required to install the repository.  For example:
        {
            "add_column": [
                "add_column hello",
                "http://test@localhost:9009/repos/test/add_column",
                "3a08cc21466f",
                "1",
                "test",
                {},
                {}
            ]
        }
        """
        # Example URL:
        # http://<xyz>/api/repositories/get_repository_revision_install_info?name=<n>&owner=<o>&changeset_revision=<cr>
        if name and owner and changeset_revision:
            # Get the repository information.
            repository = suc.get_repository_by_name_and_owner( trans.app, name, owner )
            if repository is None:
                log.debug( 'Cannot locate repository %s owned by %s' % ( str( name ), str( owner ) ) )
                return {}, {}, {}
            encoded_repository_id = trans.security.encode_id( repository.id )
            repository_dict = repository.to_dict( view='element',
                                                  value_mapper=self.__get_value_mapper( trans ) )
            repository_dict[ 'url' ] = web.url_for( controller='repositories',
                                                    action='show',
                                                    id=encoded_repository_id )
            # Get the repository_metadata information.
            repository_metadata = suc.get_repository_metadata_by_changeset_revision( trans.app,
                                                                                     encoded_repository_id,
                                                                                     changeset_revision )
            if repository_metadata is None:
                # The changeset_revision column in the repository_metadata table has been updated with a new
                # value value, so find the changeset_revision to which we need to update.
                repo = hg_util.get_repo_for_repository( trans.app, repository=repository, repo_path=None, create=False )
                new_changeset_revision = suc.get_next_downloadable_changeset_revision( repository, repo, changeset_revision )
                repository_metadata = suc.get_repository_metadata_by_changeset_revision( trans.app,
                                                                                         encoded_repository_id,
                                                                                         new_changeset_revision )
                changeset_revision = new_changeset_revision
            if repository_metadata is not None:
                encoded_repository_metadata_id = trans.security.encode_id( repository_metadata.id )
                repository_metadata_dict = repository_metadata.to_dict( view='collection',
                                                                        value_mapper=self.__get_value_mapper( trans ) )
                repository_metadata_dict[ 'url' ] = web.url_for( controller='repository_revisions',
                                                                 action='show',
                                                                 id=encoded_repository_metadata_id )
                if 'agents' in repository_metadata.metadata:
                    repository_metadata_dict[ 'valid_agents' ] = repository_metadata.metadata[ 'agents' ]
                # Get the repo_info_dict for installing the repository.
                repo_info_dict, \
                    includes_agents, \
                    includes_agent_dependencies, \
                    includes_agents_for_display_in_agent_panel, \
                    has_repository_dependencies, \
                    has_repository_dependencies_only_if_compiling_contained_td = \
                    repository_util.get_repo_info_dict( trans.app,
                                                        trans.user,
                                                        encoded_repository_id,
                                                        changeset_revision )
                return repository_dict, repository_metadata_dict, repo_info_dict
            else:
                log.debug( "Unable to locate repository_metadata record for repository id %s and changeset_revision %s" %
                           ( str( repository.id ), str( changeset_revision ) ) )
                return repository_dict, {}, {}
        else:
            debug_msg = "Error in the Agent Shed repositories API in get_repository_revision_install_info: "
            debug_msg += "Invalid name %s or owner %s or changeset_revision %s received." % \
                ( str( name ), str( owner ), str( changeset_revision ) )
            log.debug( debug_msg )
            return {}, {}, {}

    def __get_value_mapper( self, trans ):
        value_mapper = { 'id' : trans.security.encode_id,
                         'repository_id' : trans.security.encode_id,
                         'user_id' : trans.security.encode_id }
        return value_mapper

    @web.expose_api
    def import_capsule( self, trans, payload, **kwd ):
        """
        POST /api/repositories/new/import_capsule
        Import a repository capsule into the Agent Shed.

        :param key: the user's API key

        The following parameters are included in the payload.
        :param agent_shed_url (required): the base URL of the Agent Shed into which the capsule should be imported.
        :param capsule_file_name (required): the name of the capsule file.
        """
        # Get the information about the capsule to be imported from the payload.
        agent_shed_url = payload.get( 'agent_shed_url', '' )
        if not agent_shed_url:
            raise HTTPBadRequest( detail="Missing required parameter 'agent_shed_url'." )
        capsule_file_name = payload.get( 'capsule_file_name', '' )
        if not capsule_file_name:
            raise HTTPBadRequest( detail="Missing required parameter 'capsule_file_name'." )
        capsule_file_path = os.path.abspath( capsule_file_name )
        capsule_dict = dict( error_message='',
                             encoded_file_path=None,
                             status='ok',
                             tar_archive=None,
                             uploaded_file=None,
                             capsule_file_name=None )
        if os.path.getsize( os.path.abspath( capsule_file_name ) ) == 0:
            log.debug( 'Your capsule file %s is empty.' % str( capsule_file_name ) )
            return {}
        try:
            # Open for reading with transparent compression.
            tar_archive = tarfile.open( capsule_file_path, 'r:*' )
        except tarfile.ReadError, e:
            log.debug( 'Error opening capsule file %s: %s' % ( str( capsule_file_name ), str( e ) ) )
            return {}
        irm = capsule_manager.ImportRepositoryManager( trans.app,
                                                       trans.request.host,
                                                       trans.user,
                                                       trans.user_is_admin() )
        capsule_dict[ 'tar_archive' ] = tar_archive
        capsule_dict[ 'capsule_file_name' ] = capsule_file_name
        capsule_dict = irm.extract_capsule_files( **capsule_dict )
        capsule_dict = irm.validate_capsule( **capsule_dict )
        status = capsule_dict.get( 'status', 'error' )
        if status == 'error':
            log.debug( 'The capsule contents are invalid and cannot be imported:<br/>%s' %
                       str( capsule_dict.get( 'error_message', '' ) ) )
            return {}
        encoded_file_path = capsule_dict.get( 'encoded_file_path', None )
        if encoded_file_path is None:
            log.debug( 'The capsule_dict %s is missing the required encoded_file_path entry.' % str( capsule_dict ) )
            return {}
        file_path = encoding_util.agent_shed_decode( encoded_file_path )
        manifest_file_path = os.path.join( file_path, 'manifest.xml' )
        # The manifest.xml file has already been validated, so no error_message should be returned here.
        repository_info_dicts, error_message = irm.get_repository_info_from_manifest( manifest_file_path )
        # Determine the status for each exported repository archive contained within the capsule.
        repository_status_info_dicts = irm.get_repository_status_from_agent_shed( repository_info_dicts )
        # Generate a list of repository name / import results message tuples for display after the capsule is imported.
        import_results_tups = []
        # Only create repositories that do not yet exist and that the current user is authorized to create.  The
        # status will be None for repositories that fall into the intersection of these 2 categories.
        for repository_status_info_dict in repository_status_info_dicts:
            # Add the capsule_file_name and encoded_file_path to the repository_status_info_dict.
            repository_status_info_dict[ 'capsule_file_name' ] = capsule_file_name
            repository_status_info_dict[ 'encoded_file_path' ] = encoded_file_path
            import_results_tups = irm.create_repository_and_import_archive( repository_status_info_dict,
                                                                            import_results_tups )
        irm.check_status_and_reset_downloadable( import_results_tups )
        basic_util.remove_dir( file_path )
        # NOTE: the order of installation is defined in import_results_tups, but order will be lost
        # when transferred to return_dict.
        return_dict = {}
        for import_results_tup in import_results_tups:
            ok, name_owner, message = import_results_tup
            name, owner = name_owner
            key = 'Archive of repository "%s" owned by "%s"' % ( str( name ), str( owner ) )
            val = message.replace( '<b>', '"' ).replace( '</b>', '"' )
            return_dict[ key ] = val
        return return_dict

    @expose_api_raw_anonymous_and_sessionless
    def index( self, trans, deleted=False, owner=None, name=None, **kwd ):
        """
        GET /api/repositories
        Displays a collection of repositories with optional criteria.

        :param q:        (optional)if present search on the given query will be performed
        :type  q:        str

        :param page:     (optional)requested page of the search
        :type  page:     int

        :param page_size:     (optional)requested page_size of the search
        :type  page_size:     int

        :param jsonp:    (optional)flag whether to use jsonp format response, defaults to False
        :type  jsonp:    bool

        :param callback: (optional)name of the function to wrap callback in
                         used only when jsonp is true, defaults to 'callback'
        :type  callback: str

        :param deleted:  (optional)displays repositories that are or are not set to deleted.
        :type  deleted:  bool

        :param owner:    (optional)the owner's public username.
        :type  owner:    str

        :param name:     (optional)the repository name.
        :type  name:     str

        :returns dict:   object containing list of results

        Examples:
            GET http://localhost:9009/api/repositories
            GET http://localhost:9009/api/repositories?q=fastq
        """
        repository_dicts = []
        deleted = util.asbool( deleted )
        q = kwd.get( 'q', '' )
        if q:
            page = kwd.get( 'page', 1 )
            page_size = kwd.get( 'page_size', 10 )
            try:
                page = int( page )
                page_size = int( page_size )
            except ValueError:
                raise RequestParameterInvalidException( 'The "page" and "page_size" parameters have to be integers.' )
            return_jsonp = util.asbool( kwd.get( 'jsonp', False ) )
            callback = kwd.get( 'callback', 'callback' )
            search_results = self._search( trans, q, page, page_size )
            if return_jsonp:
                response = str( '%s(%s);' % ( callback, json.dumps( search_results ) ) )
            else:
                response = json.dumps( search_results )
            return response

        clause_list = [ and_( trans.app.model.Repository.table.c.deprecated == false(),
                              trans.app.model.Repository.table.c.deleted == deleted ) ]
        if owner is not None:
            clause_list.append( and_( trans.app.model.User.table.c.username == owner,
                                      trans.app.model.Repository.table.c.user_id == trans.app.model.User.table.c.id ) )
        if name is not None:
            clause_list.append( trans.app.model.Repository.table.c.name == name )
        for repository in trans.sa_session.query( trans.app.model.Repository ) \
                                          .filter( *clause_list ) \
                                          .order_by( trans.app.model.Repository.table.c.name ):
            repository_dict = repository.to_dict( view='collection',
                                                  value_mapper=self.__get_value_mapper( trans ) )
            repository_dict[ 'category_ids' ] = \
                [ trans.security.encode_id( x.category.id ) for x in repository.categories ]
            repository_dicts.append( repository_dict )
        return json.dumps( repository_dicts )

    def _search( self, trans, q, page=1, page_size=10 ):
        """
        Perform the search over TS repositories.
        Note that search works over the Whoosh index which you have
        to pre-create with scripts/agent_shed/build_ts_whoosh_index.sh manually.
        Also TS config option agentshed_search_on has to be True and
        whoosh_index_dir has to be specified.
        """
        conf = self.app.config
        if not conf.agentshed_search_on:
            raise ConfigDoesNotAllowException( 'Searching the TS through the API is turned off for this instance.' )
        if not conf.whoosh_index_dir:
            raise ConfigDoesNotAllowException( 'There is no directory for the search index specified. Please contact the administrator.' )
        search_term = q.strip()
        if len( search_term ) < 3:
            raise RequestParameterInvalidException( 'The search term has to be at least 3 characters long.' )

        repo_search = RepoSearch()

        Boosts = namedtuple( 'Boosts', [ 'repo_name_boost',
                                         'repo_description_boost',
                                         'repo_long_description_boost',
                                         'repo_homepage_url_boost',
                                         'repo_remote_repository_url_boost',
                                         'repo_owner_username_boost' ] )
        boosts = Boosts( float( conf.get( 'repo_name_boost', 0.9 ) ),
                         float( conf.get( 'repo_description_boost', 0.6 ) ),
                         float( conf.get( 'repo_long_description_boost', 0.5 ) ),
                         float( conf.get( 'repo_homepage_url_boost', 0.3 ) ),
                         float( conf.get( 'repo_remote_repository_url_boost', 0.2 ) ),
                         float( conf.get( 'repo_owner_username_boost', 0.3 ) ) )

        results = repo_search.search( trans,
                                      search_term,
                                      page,
                                      page_size,
                                      boosts )
        results[ 'hostname' ] = web.url_for( '/', qualified=True )
        return results

    @web.expose_api
    def remove_repository_registry_entry( self, trans, payload, **kwd ):
        """
        POST /api/repositories/remove_repository_registry_entry
        Removes appropriate entries from the repository registry for the repository defined by the received name and owner.

        :param key: the user's API key

        The following parameters are included in the payload.
        :param agent_shed_url (required): the base URL of the Agent Shed containing the Repository
        :param name (required): the name of the Repository
        :param owner (required): the owner of the Repository
        """
        response_dict = {}
        if not trans.user_is_admin():
            response_dict[ 'status' ] = 'error'
            response_dict[ 'message' ] = "You are not authorized to remove entries from this Agent Shed's repository registry."
            return response_dict
        agent_shed_url = payload.get( 'agent_shed_url', '' )
        if not agent_shed_url:
            raise HTTPBadRequest( detail="Missing required parameter 'agent_shed_url'." )
        agent_shed_url = agent_shed_url.rstrip( '/' )
        name = payload.get( 'name', '' )
        if not name:
            raise HTTPBadRequest( detail="Missing required parameter 'name'." )
        owner = payload.get( 'owner', '' )
        if not owner:
            raise HTTPBadRequest( detail="Missing required parameter 'owner'." )
        repository = suc.get_repository_by_name_and_owner( trans.app, name, owner )
        if repository is None:
            error_message = 'Cannot locate repository with name %s and owner %s,' % ( str( name ), str( owner ) )
            log.debug( error_message )
            response_dict[ 'status' ] = 'error'
            response_dict[ 'message' ] = error_message
            return response_dict
        # Update the repository registry.
        trans.app.repository_registry.remove_entry( repository )
        response_dict[ 'status' ] = 'ok'
        response_dict[ 'message' ] = 'Entries for repository %s owned by %s have been removed from the Agent Shed repository registry.' \
            % ( name, owner )
        return response_dict

    @web.expose_api
    def repository_ids_for_setting_metadata( self, trans, my_writable=False, **kwd ):
        """
        GET /api/repository_ids_for_setting_metadata

        Displays a collection (list) of repository ids ordered for setting metadata.

        :param key: the API key of the Agent Shed user.
        :param my_writable (optional): if the API key is associated with an admin user in the Agent Shed, setting this param value
                                       to True will restrict resetting metadata to only repositories that are writable by the user
                                       in addition to those repositories of type agent_dependency_definition.  This param is ignored
                                       if the current user is not an admin user, in which case this same restriction is automatic.
        """
        if trans.user_is_admin():
            my_writable = util.asbool( my_writable )
        else:
            my_writable = True
        handled_repository_ids = []
        repository_ids = []
        rmm = repository_metadata_manager.RepositoryMetadataManager( trans.app, trans.user )
        query = rmm.get_query_for_setting_metadata_on_repositories( my_writable=my_writable, order=False )
        # Make sure repositories of type agent_dependency_definition are first in the list.
        for repository in query:
            if repository.type == rt_util.TOOL_DEPENDENCY_DEFINITION and repository.id not in handled_repository_ids:
                repository_ids.append( trans.security.encode_id( repository.id ) )
        # Now add all remaining repositories to the list.
        for repository in query:
            if repository.type != rt_util.TOOL_DEPENDENCY_DEFINITION and repository.id not in handled_repository_ids:
                repository_ids.append( trans.security.encode_id( repository.id ) )
        return repository_ids

    @web.expose_api
    def reset_metadata_on_repositories( self, trans, payload, **kwd ):
        """
        PUT /api/repositories/reset_metadata_on_repositories

        Resets all metadata on all repositories in the Agent Shed in an "orderly fashion".  Since there are currently only two
        repository types (agent_dependecy_definition and unrestricted), the order in which metadata is reset is repositories of
        type agent_dependecy_definition first followed by repositories of type unrestricted, and only one pass is necessary.  If
        a new repository type is introduced, the process will undoubtedly need to be revisited.  To facilitate this order, an
        in-memory list of repository ids that have been processed is maintained.

        :param key: the API key of the Agent Shed user.

        The following parameters can optionally be included in the payload.
        :param my_writable (optional): if the API key is associated with an admin user in the Agent Shed, setting this param value
                                       to True will restrict resetting metadata to only repositories that are writable by the user
                                       in addition to those repositories of type agent_dependency_definition.  This param is ignored
                                       if the current user is not an admin user, in which case this same restriction is automatic.
        :param encoded_ids_to_skip (optional): a list of encoded repository ids for repositories that should not be processed.
        :param skip_file (optional): A local file name that contains the encoded repository ids associated with repositories to skip.
                                     This param can be used as an alternative to the above encoded_ids_to_skip.
        """

        def handle_repository( trans, rmm, repository, results ):
            log.debug( "Resetting metadata on repository %s" % str( repository.name ) )
            try:
                rmm.set_repository( repository )
                rmm.reset_all_metadata_on_repository_in_agent_shed()
                rmm_invalid_file_tups = rmm.get_invalid_file_tups()
                if rmm_invalid_file_tups:
                    message = agent_util.generate_message_for_invalid_agents( trans.app,
                                                                            rmm_invalid_file_tups,
                                                                            repository,
                                                                            None,
                                                                            as_html=False )
                    results[ 'unsuccessful_count' ] += 1
                else:
                    message = "Successfully reset metadata on repository %s owned by %s" % \
                        ( str( repository.name ), str( repository.user.username ) )
                    results[ 'successful_count' ] += 1
            except Exception, e:
                message = "Error resetting metadata on repository %s owned by %s: %s" % \
                    ( str( repository.name ), str( repository.user.username ), str( e ) )
                results[ 'unsuccessful_count' ] += 1
            status = '%s : %s' % ( str( repository.name ), message )
            results[ 'repository_status' ].append( status )
            return results
        rmm = repository_metadata_manager.RepositoryMetadataManager( app=trans.app,
                                                                     user=trans.user,
                                                                     resetting_all_metadata_on_repository=True,
                                                                     updating_installed_repository=False,
                                                                     persist=False )
        start_time = strftime( "%Y-%m-%d %H:%M:%S" )
        results = dict( start_time=start_time,
                        repository_status=[],
                        successful_count=0,
                        unsuccessful_count=0 )
        handled_repository_ids = []
        encoded_ids_to_skip = payload.get( 'encoded_ids_to_skip', [] )
        skip_file = payload.get( 'skip_file', None )
        if skip_file and os.path.exists( skip_file ) and not encoded_ids_to_skip:
            # Load the list of encoded_ids_to_skip from the skip_file.
            # Contents of file must be 1 encoded repository id per line.
            lines = open( skip_file, 'rb' ).readlines()
            for line in lines:
                if line.startswith( '#' ):
                    # Skip comments.
                    continue
                encoded_ids_to_skip.append( line.rstrip( '\n' ) )
        if trans.user_is_admin():
            my_writable = util.asbool( payload.get( 'my_writable', False ) )
        else:
            my_writable = True
        query = rmm.get_query_for_setting_metadata_on_repositories( my_writable=my_writable, order=False )
        # First reset metadata on all repositories of type repository_dependency_definition.
        for repository in query:
            encoded_id = trans.security.encode_id( repository.id )
            if encoded_id in encoded_ids_to_skip:
                log.debug( "Skipping repository with id %s because it is in encoded_ids_to_skip %s" %
                           ( str( repository.id ), str( encoded_ids_to_skip ) ) )
            elif repository.type == rt_util.TOOL_DEPENDENCY_DEFINITION and repository.id not in handled_repository_ids:
                results = handle_repository( trans, rmm, repository, results )
        # Now reset metadata on all remaining repositories.
        for repository in query:
            encoded_id = trans.security.encode_id( repository.id )
            if encoded_id in encoded_ids_to_skip:
                log.debug( "Skipping repository with id %s because it is in encoded_ids_to_skip %s" %
                           ( str( repository.id ), str( encoded_ids_to_skip ) ) )
            elif repository.type != rt_util.TOOL_DEPENDENCY_DEFINITION and repository.id not in handled_repository_ids:
                results = handle_repository( trans, rmm, repository, results )
        stop_time = strftime( "%Y-%m-%d %H:%M:%S" )
        results[ 'stop_time' ] = stop_time
        return json.dumps( results, sort_keys=True, indent=4 )

    @web.expose_api
    def reset_metadata_on_repository( self, trans, payload, **kwd ):
        """
        PUT /api/repositories/reset_metadata_on_repository

        Resets all metadata on a specified repository in the Agent Shed.

        :param key: the API key of the Agent Shed user.

        The following parameters must be included in the payload.
        :param repository_id: the encoded id of the repository on which metadata is to be reset.
        """

        def handle_repository( trans, start_time, repository ):
            results = dict( start_time=start_time,
                            repository_status=[] )
            try:
                rmm = repository_metadata_manager.RepositoryMetadataManager( app=trans.app,
                                                                             user=trans.user,
                                                                             repository=repository,
                                                                             resetting_all_metadata_on_repository=True,
                                                                             updating_installed_repository=False,
                                                                             persist=False )
                rmm.reset_all_metadata_on_repository_in_agent_shed()
                rmm_invalid_file_tups = rmm.get_invalid_file_tups()
                if rmm_invalid_file_tups:
                    message = agent_util.generate_message_for_invalid_agents( trans.app,
                                                                            rmm_invalid_file_tups,
                                                                            repository,
                                                                            None,
                                                                            as_html=False )
                    results[ 'status' ] = 'warning'
                else:
                    message = "Successfully reset metadata on repository %s owned by %s" % \
                        ( str( repository.name ), str( repository.user.username ) )
                    results[ 'status' ] = 'ok'
            except Exception, e:
                message = "Error resetting metadata on repository %s owned by %s: %s" % \
                    ( str( repository.name ), str( repository.user.username ), str( e ) )
                results[ 'status' ] = 'error'
            status = '%s : %s' % ( str( repository.name ), message )
            results[ 'repository_status' ].append( status )
            return results

        repository_id = payload.get( 'repository_id', None )
        if repository_id is not None:
            repository = suc.get_repository_in_agent_shed( trans.app, repository_id )
            start_time = strftime( "%Y-%m-%d %H:%M:%S" )
            log.debug( "%s...resetting metadata on repository %s" % ( start_time, str( repository.name ) ) )
            results = handle_repository( trans, start_time, repository )
            stop_time = strftime( "%Y-%m-%d %H:%M:%S" )
            results[ 'stop_time' ] = stop_time
        return results

    @expose_api_anonymous_and_sessionless
    def show( self, trans, id, **kwd ):
        """
        GET /api/repositories/{encoded_repository_id}
        Returns information about a repository in the Agent Shed.

        Example URL: http://localhost:9009/api/repositories/f9cad7b01a472135

        :param id: the encoded id of the Repository object
        :type  id: encoded str

        :returns:   detailed repository information
        :rtype:     dict

        :raises:  ObjectNotFound, MalformedId
        """
        try:
            trans.security.decode_id( id )
        except Exception:
            raise MalformedId( 'The given id is invalid.' )

        repository = suc.get_repository_in_agent_shed( trans.app, id )
        if repository is None:
            raise ObjectNotFound( 'Unable to locate repository for the given id.' )
        repository_dict = repository.to_dict( view='element',
                                              value_mapper=self.__get_value_mapper( trans ) )
        # TODO the following property would be better suited in the to_dict method
        repository_dict[ 'category_ids' ] = \
            [ trans.security.encode_id( x.category.id ) for x in repository.categories ]
        return repository_dict

    @expose_api
    def update( self, trans, id, **kwd ):
        """
        PATCH /api/repositories/{encoded_repository_id}
        Updates information about a repository in the Agent Shed.

        :param id: the encoded id of the Repository object

        :param payload: dictionary structure containing::
            'name':                  repo's name (optional)
            'synopsis':              repo's synopsis (optional)
            'description':           repo's description (optional)
            'remote_repository_url': repo's remote repo (optional)
            'homepage_url':          repo's homepage url (optional)
            'category_ids':          list of existing encoded TS category ids
                                     the updated repo should be associated with (optional)
        :type payload: dict

        :returns:   detailed repository information
        :rtype:     dict

        :raises: RequestParameterInvalidException, InsufficientPermissionsException
        """
        payload = kwd.get( 'payload', None )
        if not payload:
            raise RequestParameterMissingException( "You did not specify any payload." )

        name = payload.get( 'name', None )
        synopsis = payload.get( 'synopsis', None )
        description = payload.get( 'description', None )
        remote_repository_url = payload.get( 'remote_repository_url', None )
        homepage_url = payload.get( 'homepage_url', None )
        category_ids = payload.get( 'category_ids', None )
        if category_ids is not None:
            # We need to know if it was actually passed, and listify turns None into []
            category_ids = util.listify( category_ids )

        update_kwds = dict(
            name=name,
            description=synopsis,
            long_description=description,
            remote_repository_url=remote_repository_url,
            homepage_url=homepage_url,
            category_ids=category_ids,
        )

        repo, message = repository_util.update_repository( app=trans.app, trans=trans, id=id, **update_kwds )
        if repo is None:
            if "You are not the owner" in message:
                raise InsufficientPermissionsException( message )
            else:
                raise ActionInputError( message )

        repository_dict = repo.to_dict( view='element', value_mapper=self.__get_value_mapper( trans ) )
        repository_dict[ 'category_ids' ] = \
            [ trans.security.encode_id( x.category.id ) for x in repo.categories ]
        return repository_dict

    @expose_api
    def create( self, trans, **kwd ):
        """
        create( self, trans, payload, **kwd )
        * POST /api/repositories:
            Creates a new repository.
            Only ``name`` and ``synopsis`` parameters are required.

        :param payload: dictionary structure containing::
            'name':                  new repo's name (required)
            'synopsis':              new repo's synopsis (required)
            'description':           new repo's description (optional)
            'remote_repository_url': new repo's remote repo (optional)
            'homepage_url':          new repo's homepage url (optional)
            'category_ids[]':        list of existing encoded TS category ids
                                     the new repo should be associated with (optional)
            'type':                  new repo's type, defaults to ``unrestricted`` (optional)

        :type payload: dict

        :returns:   detailed repository information
        :rtype:     dict

        :raises: RequestParameterMissingException, RequestParameterInvalidException
        """
        payload = kwd.get( 'payload', None )
        if not payload:
            raise RequestParameterMissingException( "You did not specify any payload." )
        name = payload.get( 'name', None )
        if not name:
            raise RequestParameterMissingException( "Missing required parameter 'name'." )
        synopsis = payload.get( 'synopsis', None )
        if not synopsis:
            raise RequestParameterMissingException( "Missing required parameter 'synopsis'." )

        description = payload.get( 'description', '' )
        remote_repository_url = payload.get( 'remote_repository_url', '' )
        homepage_url = payload.get( 'homepage_url', '' )
        category_ids = util.listify( payload.get( 'category_ids[]', '' ) )

        repo_type = payload.get( 'type', rt_util.UNRESTRICTED )
        if repo_type not in rt_util.types:
            raise RequestParameterInvalidException( 'This repository type is not valid' )

        invalid_message = repository_util.validate_repository_name( trans.app, name, trans.user )
        if invalid_message:
            raise RequestParameterInvalidException( invalid_message )

        repo, message = repository_util.create_repository( app=trans.app,
                                                           name=name,
                                                           type=repo_type,
                                                           description=synopsis,
                                                           long_description=description,
                                                           user_id=trans.user.id,
                                                           category_ids=category_ids,
                                                           remote_repository_url=remote_repository_url,
                                                           homepage_url=homepage_url )

        repository_dict = repo.to_dict( view='element', value_mapper=self.__get_value_mapper( trans ) )
        repository_dict[ 'category_ids' ] = \
            [ trans.security.encode_id( x.category.id ) for x in repo.categories ]
        return repository_dict

    @web.expose_api
    def create_changeset_revision( self, trans, id, payload, **kwd ):
        """
        POST /api/repositories/{encoded_repository_id}/changeset_revision

        Create a new agent shed repository commit - leaving PUT on parent
        resource open for updating meta-attributes of the repository (and
        Galaxy doesn't allow PUT multipart data anyway
        https://trello.com/c/CQwmCeG6).

        :param id: the encoded id of the Repository object

        The following parameters may be included in the payload.
        :param commit_message: hg commit message for update.
        """

        # Example URL: http://localhost:9009/api/repositories/f9cad7b01a472135
        rdah = attribute_handlers.RepositoryDependencyAttributeHandler( trans.app, unpopulate=False )
        tdah = attribute_handlers.AgentDependencyAttributeHandler( trans.app, unpopulate=False )

        repository = suc.get_repository_in_agent_shed( trans.app, id )

        if not ( trans.user_is_admin() or
                 trans.app.security_agent.user_can_administer_repository( trans.user, repository ) or
                 trans.app.security_agent.can_push( trans.app, trans.user, repository ) ):
            trans.response.status = 400
            return {
                "err_msg": "You do not have permission to update this repository.",
            }

        repo_dir = repository.repo_path( trans.app )
        repo = hg_util.get_repo_for_repository( trans.app, repository=None, repo_path=repo_dir, create=False )

        upload_point = commit_util.get_upload_point( repository, **kwd )
        tip = repository.tip( trans.app )

        file_data = payload.get('file')
        # Code stolen from gx's upload_common.py
        if isinstance( file_data, FieldStorage ):
            assert not isinstance( file_data.file, StringIO.StringIO )
            assert file_data.file.name != '<fdopen>'
            local_filename = util.mkstemp_ln( file_data.file.name, 'upload_file_data_' )
            file_data.file.close()
            file_data = dict( filename=file_data.filename,
                              local_filename=local_filename )
        elif type( file_data ) == dict and 'local_filename' not in file_data:
            raise Exception( 'Uploaded file was encoded in a way not understood.' )

        commit_message = kwd.get( 'commit_message', 'Uploaded' )

        uploaded_file = open(file_data['local_filename'], 'rb')
        uploaded_file_name = file_data['local_filename']

        isgzip = False
        isbz2 = False
        isgzip = checkers.is_gzip( uploaded_file_name )
        if not isgzip:
            isbz2 = checkers.is_bz2( uploaded_file_name )
        if ( isgzip or isbz2 ):
            # Open for reading with transparent compression.
            tar = tarfile.open( uploaded_file_name, 'r:*' )
        else:
            tar = tarfile.open( uploaded_file_name )

        new_repo_alert = False
        remove_repo_files_not_in_tar = True

        ok, message, files_to_remove, content_alert_str, undesirable_dirs_removed, undesirable_files_removed = \
            repository_content_util.upload_tar(
                trans,
                rdah,
                tdah,
                repository,
                tar,
                uploaded_file,
                upload_point,
                remove_repo_files_not_in_tar,
                commit_message,
                new_repo_alert
            )
        if ok:
            # Update the repository files for browsing.
            hg_util.update_repository( repo )
            # Get the new repository tip.
            if tip == repository.tip( trans.app ):
                trans.response.status = 400
                message = 'No changes to repository.'
                ok = False
            else:
                rmm = repository_metadata_manager.RepositoryMetadataManager( app=trans.app,
                                                                             user=trans.user,
                                                                             repository=repository )
                status, error_message = \
                    rmm.set_repository_metadata_due_to_new_tip( trans.request.host,
                                                                content_alert_str=content_alert_str,
                                                                **kwd )
                if error_message:
                    ok = False
                    trans.response.status = 500
                    message = error_message
        else:
            trans.response.status = 500
        if os.path.exists( uploaded_file_name ):
            os.remove( uploaded_file_name )
        if not ok:
            return {
                "err_msg": message,
                "content_alert": content_alert_str
            }
        else:
            return {
                "message": message,
                "content_alert": content_alert_str
            }
