import logging

from paste.httpexceptions import HTTPBadRequest, HTTPForbidden
from time import strftime

from galaxy import util
from galaxy import web
from galaxy import exceptions
from galaxy.web import _future_expose_api as expose_api
from galaxy.util import json
from galaxy.web.base.controller import BaseAPIController

from agent_shed.galaxy_install.install_manager import InstallRepositoryManager
from agent_shed.galaxy_install.metadata.installed_repository_metadata_manager import InstalledRepositoryMetadataManager
from agent_shed.galaxy_install.repair_repository_manager import RepairRepositoryManager

from agent_shed.util import common_util
from agent_shed.util import encoding_util
from agent_shed.util import hg_util
from agent_shed.util import workflow_util
from agent_shed.util import agent_util

import agent_shed.util.shed_util_common as suc

log = logging.getLogger( __name__ )


def get_message_for_no_shed_agent_config():
    # This Galaxy instance is not configured with a shed-related agent panel configuration file.
    message = 'The agent_config_file setting in galaxy.ini must include at least one shed agent configuration file name with a <agentbox> '
    message += 'tag that includes a agent_path attribute value which is a directory relative to the Galaxy installation directory in order to '
    message += 'automatically install agents from a agent shed into Galaxy (e.g., the file name shed_agent_conf.xml whose <agentbox> tag is '
    message += '<agentbox agent_path="../shed_agents">).  For details, see the "Installation of Galaxy agent shed repository agents into a local '
    message += 'Galaxy instance" section of the Galaxy agent shed wiki at http://wiki.galaxyproject.org/InstallingRepositoriesToGalaxy#'
    message += 'Installing_Galaxy_agent_shed_repository_agents_into_a_local_Galaxy_instance.'
    return message


class AgentShedRepositoriesController( BaseAPIController ):
    """RESTful controller for interactions with agent shed repositories."""

    def __ensure_can_install_repos( self, trans ):
        # Make sure this Galaxy instance is configured with a shed-related agent panel configuration file.
        if not suc.have_shed_agent_conf_for_install( trans.app ):
            message = get_message_for_no_shed_agent_config()
            log.debug( message )
            return dict( status='error', error=message )
        # Make sure the current user's API key proves he is an admin user in this Galaxy instance.
        if not trans.user_is_admin():
            raise exceptions.AdminRequiredException( 'You are not authorized to request the latest installable revision for a repository in this Galaxy instance.' )

    @expose_api
    def exported_workflows( self, trans, id, **kwd ):
        """
        GET /api/agent_shed_repositories/{encoded_agent_shed_repository_id}/exported_workflows

        Display a list of dictionaries containing information about this agent shed repository's exported workflows.

        :param id: the encoded id of the AgentShedRepository object
        """
        # Example URL: http://localhost:8763/api/agent_shed_repositories/f2db41e1fa331b3e/exported_workflows
        # Since exported workflows are dictionaries with very few attributes that differentiate them from each
        # other, we'll build the list based on the following dictionary of those few attributes.
        exported_workflows = []
        repository = suc.get_agent_shed_repository_by_id( trans.app, id )
        metadata = repository.metadata
        if metadata:
            exported_workflow_tups = metadata.get( 'workflows', [] )
        else:
            exported_workflow_tups = []
        for index, exported_workflow_tup in enumerate( exported_workflow_tups ):
            # The exported_workflow_tup looks like ( relative_path, exported_workflow_dict ), where the value of
            # relative_path is the location on disk (relative to the root of the installed repository) where the
            # exported_workflow_dict file (.ga file) is located.
            exported_workflow_dict = exported_workflow_tup[ 1 ]
            annotation = exported_workflow_dict.get( 'annotation', '' )
            format_version = exported_workflow_dict.get( 'format-version', '' )
            workflow_name = exported_workflow_dict.get( 'name', '' )
            # Since we don't have an in-memory object with an id, we'll identify the exported workflow via its
            # location (i.e., index) in the list.
            display_dict = dict( index=index, annotation=annotation, format_version=format_version, workflow_name=workflow_name )
            exported_workflows.append( display_dict )
        return exported_workflows

    @expose_api
    def get_latest_installable_revision( self, trans, payload, **kwd ):
        """
        POST /api/agent_shed_repositories/get_latest_installable_revision
        Get the latest installable revision of a specified repository from a specified Agent Shed.

        :param key: the current Galaxy admin user's API key

        The following parameters are included in the payload.
        :param agent_shed_url (required): the base URL of the Agent Shed from which to retrieve the Repository revision.
        :param name (required): the name of the Repository
        :param owner (required): the owner of the Repository
        """
        # Get the information about the repository to be installed from the payload.
        agent_shed_url, name, owner = self.__parse_repository_from_payload( payload )
        # Make sure the current user's API key proves he is an admin user in this Galaxy instance.
        if not trans.user_is_admin():
            raise exceptions.AdminRequiredException( 'You are not authorized to request the latest installable revision for a repository in this Galaxy instance.' )
        params = dict(name=name, owner=owner)
        pathspec = ['api', 'repositories', 'get_ordered_installable_revisions']
        try:
            raw_text = common_util.agent_shed_get( trans.app, agent_shed_url, pathspec, params )
        except Exception, e:
            message = "Error attempting to retrieve the latest installable revision from agent shed %s for repository %s owned by %s: %s" % \
                ( str( agent_shed_url ), str( name ), str( owner ), str( e ) )
            log.debug( message )
            return dict( status='error', error=message )
        if raw_text:
            # If successful, the response from get_ordered_installable_revisions will be a list of
            # changeset_revision hash strings.
            changeset_revisions = json.loads( raw_text )
            if len( changeset_revisions ) >= 1:
                return changeset_revisions[ -1 ]
        return hg_util.INITIAL_CHANGELOG_HASH

    def __get_value_mapper( self, trans, agent_shed_repository ):
        value_mapper = { 'id' : trans.security.encode_id( agent_shed_repository.id ),
                         'error_message' : agent_shed_repository.error_message or '' }
        return value_mapper

    @expose_api
    def import_workflow( self, trans, payload, **kwd ):
        """
        POST /api/agent_shed_repositories/import_workflow

        Import the specified exported workflow contained in the specified installed agent shed repository into Galaxy.

        :param key: the API key of the Galaxy user with which the imported workflow will be associated.
        :param id: the encoded id of the AgentShedRepository object

        The following parameters are included in the payload.
        :param index: the index location of the workflow tuple in the list of exported workflows stored in the metadata for the specified repository
        """
        api_key = kwd.get( 'key', None )
        if api_key is None:
            raise HTTPBadRequest( detail="Missing required parameter 'key' whose value is the API key for the Galaxy user importing the specified workflow." )
        agent_shed_repository_id = kwd.get( 'id', '' )
        if not agent_shed_repository_id:
            raise HTTPBadRequest( detail="Missing required parameter 'id'." )
        index = payload.get( 'index', None )
        if index is None:
            raise HTTPBadRequest( detail="Missing required parameter 'index'." )
        repository = suc.get_agent_shed_repository_by_id( trans.app, agent_shed_repository_id )
        exported_workflows = json.loads( self.exported_workflows( trans, agent_shed_repository_id ) )
        # Since we don't have an in-memory object with an id, we'll identify the exported workflow via its location (i.e., index) in the list.
        exported_workflow = exported_workflows[ int( index ) ]
        workflow_name = exported_workflow[ 'workflow_name' ]
        workflow, status, error_message = workflow_util.import_workflow( trans, repository, workflow_name )
        if status == 'error':
            log.debug( error_message )
            return {}
        return workflow.to_dict( view='element' )

    @expose_api
    def import_workflows( self, trans, **kwd ):
        """
        POST /api/agent_shed_repositories/import_workflows

        Import all of the exported workflows contained in the specified installed agent shed repository into Galaxy.

        :param key: the API key of the Galaxy user with which the imported workflows will be associated.
        :param id: the encoded id of the AgentShedRepository object
        """
        api_key = kwd.get( 'key', None )
        if api_key is None:
            raise HTTPBadRequest( detail="Missing required parameter 'key' whose value is the API key for the Galaxy user importing the specified workflow." )
        agent_shed_repository_id = kwd.get( 'id', '' )
        if not agent_shed_repository_id:
            raise HTTPBadRequest( detail="Missing required parameter 'id'." )
        repository = suc.get_agent_shed_repository_by_id( trans.app, agent_shed_repository_id )
        exported_workflows = json.loads( self.exported_workflows( trans, agent_shed_repository_id ) )
        imported_workflow_dicts = []
        for exported_workflow_dict in exported_workflows:
            workflow_name = exported_workflow_dict[ 'workflow_name' ]
            workflow, status, error_message = workflow_util.import_workflow( trans, repository, workflow_name )
            if status == 'error':
                log.debug( error_message )
            else:
                imported_workflow_dicts.append( workflow.to_dict( view='element' ) )
        return imported_workflow_dicts

    @expose_api
    def index( self, trans, **kwd ):
        """
        GET /api/agent_shed_repositories
        Display a list of dictionaries containing information about installed agent shed repositories.
        """
        # Example URL: http://localhost:8763/api/agent_shed_repositories
        agent_shed_repository_dicts = []
        for agent_shed_repository in trans.install_model.context.query( trans.app.install_model.AgentShedRepository ) \
                                                               .order_by( trans.app.install_model.AgentShedRepository.table.c.name ):
            agent_shed_repository_dict = \
                agent_shed_repository.to_dict( value_mapper=self.__get_value_mapper( trans, agent_shed_repository ) )
            agent_shed_repository_dict[ 'url' ] = web.url_for( controller='agent_shed_repositories',
                                                              action='show',
                                                              id=trans.security.encode_id( agent_shed_repository.id ) )
            agent_shed_repository_dicts.append( agent_shed_repository_dict )
        return agent_shed_repository_dicts

    @expose_api
    def install_repository_revision( self, trans, payload, **kwd ):
        """
        POST /api/agent_shed_repositories/install_repository_revision
        Install a specified repository revision from a specified agent shed into Galaxy.

        :param key: the current Galaxy admin user's API key

        The following parameters are included in the payload.
        :param agent_shed_url (required): the base URL of the Agent Shed from which to install the Repository
        :param name (required): the name of the Repository
        :param owner (required): the owner of the Repository
        :param changeset_revision (required): the changeset_revision of the RepositoryMetadata object associated with the Repository
        :param new_agent_panel_section_label (optional): label of a new section to be added to the Galaxy agent panel in which to load
                                                        agents contained in the Repository.  Either this parameter must be an empty string or
                                                        the agent_panel_section_id parameter must be an empty string or both must be an empty
                                                        string (both cannot be used simultaneously).
        :param agent_panel_section_id (optional): id of the Galaxy agent panel section in which to load agents contained in the Repository.
                                                 If this parameter is an empty string and the above new_agent_panel_section_label parameter is an
                                                 empty string, agents will be loaded outside of any sections in the agent panel.  Either this
                                                 parameter must be an empty string or the agent_panel_section_id parameter must be an empty string
                                                 of both must be an empty string (both cannot be used simultaneously).
        :param install_repository_dependencies (optional): Set to True if you want to install repository dependencies defined for the specified
                                                           repository being installed.  The default setting is False.
        :param install_agent_dependencies (optional): Set to True if you want to install agent dependencies defined for the specified repository being
                                                     installed.  The default setting is False.
        :param shed_agent_conf (optional): The shed-related agent panel configuration file configured in the "agent_config_file" setting in the Galaxy config file
                                          (e.g., galaxy.ini).  At least one shed-related agent panel config file is required to be configured. Setting
                                          this parameter to a specific file enables you to choose where the specified repository will be installed because
                                          the agent_path attribute of the <agentbox> from the specified file is used as the installation location
                                          (e.g., <agentbox agent_path="../shed_agents">).  If this parameter is not set, a shed-related agent panel configuration
                                          file will be selected automatically.
        """
        # Get the information about the repository to be installed from the payload.
        agent_shed_url, name, owner, changeset_revision = self.__parse_repository_from_payload( payload, include_changeset=True )
        self.__ensure_can_install_repos( trans )
        install_repository_manager = InstallRepositoryManager( trans.app )
        installed_agent_shed_repositories = install_repository_manager.install( agent_shed_url,
                                                                               name,
                                                                               owner,
                                                                               changeset_revision,
                                                                               payload )

        def to_dict( agent_shed_repository ):
            agent_shed_repository_dict = agent_shed_repository.as_dict( value_mapper=self.__get_value_mapper( trans, agent_shed_repository ) )
            agent_shed_repository_dict[ 'url' ] = web.url_for( controller='agent_shed_repositories',
                                                              action='show',
                                                              id=trans.security.encode_id( agent_shed_repository.id ) )
            return agent_shed_repository_dict
        if installed_agent_shed_repositories:
            return map( to_dict, installed_agent_shed_repositories )
        message = "No repositories were installed, possibly because the selected repository has already been installed."
        return dict( status="ok", message=message )

    @expose_api
    def install_repository_revisions( self, trans, payload, **kwd ):
        """
        POST /api/agent_shed_repositories/install_repository_revisions
        Install one or more specified repository revisions from one or more specified agent sheds into Galaxy.  The received parameters
        must be ordered lists so that positional values in agent_shed_urls, names, owners and changeset_revisions are associated.

        It's questionable whether this method is needed as the above method for installing a single repository can probably cover all
        desired scenarios.  We'll keep this one around just in case...

        :param key: the current Galaxy admin user's API key

        The following parameters are included in the payload.
        :param agent_shed_urls: the base URLs of the Agent Sheds from which to install a specified Repository
        :param names: the names of the Repositories to be installed
        :param owners: the owners of the Repositories to be installed
        :param changeset_revisions: the changeset_revisions of each RepositoryMetadata object associated with each Repository to be installed
        :param new_agent_panel_section_label: optional label of a new section to be added to the Galaxy agent panel in which to load
                                             agents contained in the Repository.  Either this parameter must be an empty string or
                                             the agent_panel_section_id parameter must be an empty string, as both cannot be used.
        :param agent_panel_section_id: optional id of the Galaxy agent panel section in which to load agents contained in the Repository.
                                      If not set, agents will be loaded outside of any sections in the agent panel.  Either this
                                      parameter must be an empty string or the agent_panel_section_id parameter must be an empty string,
                                      as both cannot be used.
        :param install_repository_dependencies (optional): Set to True if you want to install repository dependencies defined for the specified
                                                           repository being installed.  The default setting is False.
        :param install_agent_dependencies (optional): Set to True if you want to install agent dependencies defined for the specified repository being
                                                     installed.  The default setting is False.
        :param shed_agent_conf (optional): The shed-related agent panel configuration file configured in the "agent_config_file" setting in the Galaxy config file
                                          (e.g., galaxy.ini).  At least one shed-related agent panel config file is required to be configured. Setting
                                          this parameter to a specific file enables you to choose where the specified repository will be installed because
                                          the agent_path attribute of the <agentbox> from the specified file is used as the installation location
                                          (e.g., <agentbox agent_path="../shed_agents">).  If this parameter is not set, a shed-related agent panel configuration
                                          file will be selected automatically.
        """
        self.__ensure_can_install_repos( trans )
        # Get the information about all of the repositories to be installed.
        agent_shed_urls = util.listify( payload.get( 'agent_shed_urls', '' ) )
        names = util.listify( payload.get( 'names', '' ) )
        owners = util.listify( payload.get( 'owners', '' ) )
        changeset_revisions = util.listify( payload.get( 'changeset_revisions', '' ) )
        num_specified_repositories = len( agent_shed_urls )
        if len( names ) != num_specified_repositories or \
                len( owners ) != num_specified_repositories or \
                len( changeset_revisions ) != num_specified_repositories:
            message = 'Error in agent_shed_repositories API in install_repository_revisions: the received parameters must be ordered '
            message += 'lists so that positional values in agent_shed_urls, names, owners and changeset_revisions are associated.'
            log.debug( message )
            return dict( status='error', error=message )
        # Get the information about the Galaxy components (e.g., agent pane section, agent config file, etc) that will contain information
        # about each of the repositories being installed.
        # TODO: we may want to enhance this method to allow for each of the following to be associated with each repository instead of
        # forcing all repositories to use the same settings.
        install_repository_dependencies = payload.get( 'install_repository_dependencies', False )
        install_agent_dependencies = payload.get( 'install_agent_dependencies', False )
        new_agent_panel_section_label = payload.get( 'new_agent_panel_section_label', '' )
        shed_agent_conf = payload.get( 'shed_agent_conf', None )
        agent_panel_section_id = payload.get( 'agent_panel_section_id', '' )
        all_installed_agent_shed_repositories = []
        for agent_shed_url, name, owner, changeset_revision in zip( agent_shed_urls, names, owners, changeset_revisions ):
            current_payload = dict( agent_shed_url=agent_shed_url,
                                    name=name,
                                    owner=owner,
                                    changeset_revision=changeset_revision,
                                    new_agent_panel_section_label=new_agent_panel_section_label,
                                    agent_panel_section_id=agent_panel_section_id,
                                    install_repository_dependencies=install_repository_dependencies,
                                    install_agent_dependencies=install_agent_dependencies,
                                    shed_agent_conf=shed_agent_conf )
            installed_agent_shed_repositories = self.install_repository_revision( trans, **current_payload )
            if isinstance( installed_agent_shed_repositories, dict ):
                # We encountered an error.
                return installed_agent_shed_repositories
            elif isinstance( installed_agent_shed_repositories, list ):
                all_installed_agent_shed_repositories.extend( installed_agent_shed_repositories )
        return all_installed_agent_shed_repositories

    @expose_api
    def repair_repository_revision( self, trans, payload, **kwd ):
        """
        POST /api/agent_shed_repositories/repair_repository_revision
        Repair a specified repository revision previously installed into Galaxy.

        :param key: the current Galaxy admin user's API key

        The following parameters are included in the payload.
        :param agent_shed_url (required): the base URL of the Agent Shed from which the Repository was installed
        :param name (required): the name of the Repository
        :param owner (required): the owner of the Repository
        :param changeset_revision (required): the changeset_revision of the RepositoryMetadata object associated with the Repository
        """
        # Get the information about the repository to be installed from the payload.
        agent_shed_url, name, owner, changeset_revision = self.__parse_repository_from_payload( payload, include_changeset=True )
        agent_shed_repositories = []
        agent_shed_repository = suc.get_installed_repository( trans.app,
                                                             agent_shed=agent_shed_url,
                                                             name=name,
                                                             owner=owner,
                                                             changeset_revision=changeset_revision )
        rrm = RepairRepositoryManager( trans.app )
        repair_dict = rrm.get_repair_dict( agent_shed_repository )
        ordered_tsr_ids = repair_dict.get( 'ordered_tsr_ids', [] )
        ordered_repo_info_dicts = repair_dict.get( 'ordered_repo_info_dicts', [] )
        if ordered_tsr_ids and ordered_repo_info_dicts:
            for index, tsr_id in enumerate( ordered_tsr_ids ):
                repository = trans.install_model.context.query( trans.install_model.AgentShedRepository ).get( trans.security.decode_id( tsr_id ) )
                repo_info_dict = ordered_repo_info_dicts[ index ]
                # TODO: handle errors in repair_dict.
                repair_dict = rrm.repair_agent_shed_repository( repository,
                                                               encoding_util.agent_shed_encode( repo_info_dict ) )
                repository_dict = repository.to_dict( value_mapper=self.__get_value_mapper( trans, repository ) )
                repository_dict[ 'url' ] = web.url_for( controller='agent_shed_repositories',
                                                        action='show',
                                                        id=trans.security.encode_id( repository.id ) )
                if repair_dict:
                    errors = repair_dict.get( repository.name, [] )
                    repository_dict[ 'errors_attempting_repair' ] = '  '.join( errors )
                agent_shed_repositories.append( repository_dict )
        # Display the list of repaired repositories.
        return agent_shed_repositories

    def __parse_repository_from_payload( self, payload, include_changeset=False ):
        # Get the information about the repository to be installed from the payload.
        agent_shed_url = payload.get( 'agent_shed_url', '' )
        if not agent_shed_url:
            raise exceptions.RequestParameterMissingException( "Missing required parameter 'agent_shed_url'." )
        name = payload.get( 'name', '' )
        if not name:
            raise exceptions.RequestParameterMissingException( "Missing required parameter 'name'." )
        owner = payload.get( 'owner', '' )
        if not owner:
            raise exceptions.RequestParameterMissingException( "Missing required parameter 'owner'." )
        if not include_changeset:
            return agent_shed_url, name, owner

        changeset_revision = payload.get( 'changeset_revision', '' )
        if not changeset_revision:
            raise HTTPBadRequest( detail="Missing required parameter 'changeset_revision'." )

        return agent_shed_url, name, owner, changeset_revision

    @expose_api
    def reset_metadata_on_installed_repositories( self, trans, payload, **kwd ):
        """
        PUT /api/agent_shed_repositories/reset_metadata_on_installed_repositories

        Resets all metadata on all repositories installed into Galaxy in an "orderly fashion".

        :param key: the API key of the Galaxy admin user.
        """
        start_time = strftime( "%Y-%m-%d %H:%M:%S" )
        results = dict( start_time=start_time,
                        successful_count=0,
                        unsuccessful_count=0,
                        repository_status=[] )
        # Make sure the current user's API key proves he is an admin user in this Galaxy instance.
        if not trans.user_is_admin():
            raise HTTPForbidden( detail='You are not authorized to reset metadata on repositories installed into this Galaxy instance.' )
        irmm = InstalledRepositoryMetadataManager( trans.app )
        query = irmm.get_query_for_setting_metadata_on_repositories( order=False )
        # Now reset metadata on all remaining repositories.
        for repository in query:
            try:
                irmm.set_repository( repository )
                irmm.reset_all_metadata_on_installed_repository()
                irmm_invalid_file_tups = irmm.get_invalid_file_tups()
                if irmm_invalid_file_tups:
                    message = agent_util.generate_message_for_invalid_agents( trans.app,
                                                                            irmm_invalid_file_tups,
                                                                            repository,
                                                                            None,
                                                                            as_html=False )
                    results[ 'unsuccessful_count' ] += 1
                else:
                    message = "Successfully reset metadata on repository %s owned by %s" % \
                        ( str( repository.name ), str( repository.owner ) )
                    results[ 'successful_count' ] += 1
            except Exception, e:
                message = "Error resetting metadata on repository %s owned by %s: %s" % \
                    ( str( repository.name ), str( repository.owner ), str( e ) )
                results[ 'unsuccessful_count' ] += 1
            results[ 'repository_status' ].append( message )
        stop_time = strftime( "%Y-%m-%d %H:%M:%S" )
        results[ 'stop_time' ] = stop_time
        return json.dumps( results, sort_keys=True, indent=4 )

    @expose_api
    def show( self, trans, id, **kwd ):
        """
        GET /api/agent_shed_repositories/{encoded_agent_shed_repsository_id}
        Display a dictionary containing information about a specified agent_shed_repository.

        :param id: the encoded id of the AgentShedRepository object
        """
        # Example URL: http://localhost:8763/api/agent_shed_repositories/df7a1f0c02a5b08e
        agent_shed_repository = suc.get_agent_shed_repository_by_id( trans.app, id )
        if agent_shed_repository is None:
            log.debug( "Unable to locate agent_shed_repository record for id %s." % ( str( id ) ) )
            return {}
        agent_shed_repository_dict = agent_shed_repository.as_dict( value_mapper=self.__get_value_mapper( trans, agent_shed_repository ) )
        agent_shed_repository_dict[ 'url' ] = web.url_for( controller='agent_shed_repositories',
                                                          action='show',
                                                          id=trans.security.encode_id( agent_shed_repository.id ) )
        return agent_shed_repository_dict
