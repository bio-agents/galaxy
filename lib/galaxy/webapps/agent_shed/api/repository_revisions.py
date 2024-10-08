import datetime
import logging

from sqlalchemy import and_, not_, select

import agent_shed.util.shed_util_common as suc
from galaxy import util
from galaxy import web
from galaxy.web.base.controller import BaseAPIController, HTTPBadRequest
from agent_shed.capsule import capsule_manager
from agent_shed.util import hg_util
from agent_shed.util import metadata_util

log = logging.getLogger( __name__ )


class RepositoryRevisionsController( BaseAPIController ):
    """RESTful controller for interactions with agent shed repository revisions."""

    @web.expose_api_anonymous
    def export( self, trans, payload, **kwd ):
        """
        POST /api/repository_revisions/export
        Creates and saves a gzip compressed tar archive of a repository and optionally all of its repository dependencies.

        The following parameters are included in the payload.
        :param agent_shed_url (required): the base URL of the Agent Shed from which the Repository is to be exported
        :param name (required): the name of the Repository
        :param owner (required): the owner of the Repository
        :param changeset_revision (required): the changeset_revision of the RepositoryMetadata object associated with the Repository
        :param export_repository_dependencies (optional): whether to export repository dependencies - defaults to False
        :param download_dir (optional): the local directory to which to download the archive - defaults to /tmp
        """
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
        changeset_revision = payload.get( 'changeset_revision', '' )
        if not changeset_revision:
            raise HTTPBadRequest( detail="Missing required parameter 'changeset_revision'." )
        export_repository_dependencies = payload.get( 'export_repository_dependencies', False )
        # We'll currently support only gzip-compressed tar archives.
        export_repository_dependencies = util.asbool( export_repository_dependencies )
        # Get the repository information.
        repository = suc.get_repository_by_name_and_owner( trans.app, name, owner )
        if repository is None:
            error_message = 'Cannot locate repository with name %s and owner %s,' % ( str( name ), str( owner ) )
            log.debug( error_message )
            return None, error_message
        erm = capsule_manager.ExportRepositoryManager( app=trans.app,
                                                       user=trans.user,
                                                       agent_shed_url=agent_shed_url,
                                                       repository=repository,
                                                       changeset_revision=changeset_revision,
                                                       export_repository_dependencies=export_repository_dependencies,
                                                       using_api=True )
        return erm.export_repository()

    def __get_value_mapper( self, trans ):
        value_mapper = { 'id' : trans.security.encode_id,
                         'repository_id' : trans.security.encode_id,
                         'user_id' : trans.security.encode_id }
        return value_mapper

    @web.expose_api_anonymous
    def index( self, trans, **kwd ):
        """
        GET /api/repository_revisions
        Displays a collection (list) of repository revisions.
        """
        # Example URL: http://localhost:9009/api/repository_revisions
        repository_metadata_dicts = []
        # Build up an anded clause list of filters.
        clause_list = []
        # Filter by downloadable if received.
        downloadable = kwd.get( 'downloadable', None )
        if downloadable is not None:
            clause_list.append( trans.model.RepositoryMetadata.table.c.downloadable == util.asbool( downloadable ) )
        # Filter by malicious if received.
        malicious = kwd.get( 'malicious', None )
        if malicious is not None:
            clause_list.append( trans.model.RepositoryMetadata.table.c.malicious == util.asbool( malicious ) )
        # Filter by agents_functionally_correct if received.
        agents_functionally_correct = kwd.get( 'agents_functionally_correct', None )
        if agents_functionally_correct is not None:
            clause_list.append( trans.model.RepositoryMetadata.table.c.agents_functionally_correct == util.asbool( agents_functionally_correct ) )
        # Filter by missing_test_components if received.
        missing_test_components = kwd.get( 'missing_test_components', None )
        if missing_test_components is not None:
            clause_list.append( trans.model.RepositoryMetadata.table.c.missing_test_components == util.asbool( missing_test_components ) )
        # Filter by do_not_test if received.
        do_not_test = kwd.get( 'do_not_test', None )
        if do_not_test is not None:
            clause_list.append( trans.model.RepositoryMetadata.table.c.do_not_test == util.asbool( do_not_test ) )
        # Filter by includes_agents if received.
        includes_agents = kwd.get( 'includes_agents', None )
        if includes_agents is not None:
            clause_list.append( trans.model.RepositoryMetadata.table.c.includes_agents == util.asbool( includes_agents ) )
        # Filter by test_install_error if received.
        test_install_error = kwd.get( 'test_install_error', None )
        if test_install_error is not None:
            clause_list.append( trans.model.RepositoryMetadata.table.c.test_install_error == util.asbool( test_install_error ) )
        # Filter by skip_agent_test if received.
        skip_agent_test = kwd.get( 'skip_agent_test', None )
        if skip_agent_test is not None:
            skip_agent_test = util.asbool( skip_agent_test )
            skipped_metadata_ids_subquery = select( [ trans.app.model.SkipAgentTest.table.c.repository_metadata_id ] )
            if skip_agent_test:
                clause_list.append( trans.model.RepositoryMetadata.id.in_( skipped_metadata_ids_subquery ) )
            else:
                clause_list.append( not_( trans.model.RepositoryMetadata.id.in_( skipped_metadata_ids_subquery ) ) )
        for repository_metadata in trans.sa_session.query( trans.app.model.RepositoryMetadata ) \
                                                   .filter( and_( *clause_list ) ) \
                                                   .order_by( trans.app.model.RepositoryMetadata.table.c.repository_id.desc() ):
            repository_metadata_dict = repository_metadata.to_dict( view='collection',
                                                                    value_mapper=self.__get_value_mapper( trans ) )
            repository_metadata_dict[ 'url' ] = web.url_for( controller='repository_revisions',
                                                             action='show',
                                                             id=trans.security.encode_id( repository_metadata.id ) )
            repository_metadata_dicts.append( repository_metadata_dict )
        return repository_metadata_dicts

    @web.expose_api_anonymous
    def repository_dependencies( self, trans, id, **kwd ):
        """
        GET /api/repository_revisions/{encoded repository_metadata id}/repository_dependencies

        Returns a list of dictionaries that each define a specific downloadable revision of a
        repository in the Agent Shed.  This method returns dictionaries with more information in
        them than other methods in this controller.  The information about repository_metdata is
        enhanced to include information about the repository (e.g., name, owner, etc) associated
        with the repository_metadata record.

        :param id: the encoded id of the `RepositoryMetadata` object
        """
        # Example URL: http://localhost:9009/api/repository_revisions/repository_dependencies/bb125606ff9ea620
        repository_dependencies_dicts = []
        repository_metadata = metadata_util.get_repository_metadata_by_id( trans.app, id )
        if repository_metadata is None:
            log.debug( 'Invalid repository_metadata id received: %s' % str( id ) )
            return repository_dependencies_dicts
        metadata = repository_metadata.metadata
        if metadata is None:
            log.debug( 'The repository_metadata record with id %s has no metadata.' % str( id ) )
            return repository_dependencies_dicts
        if 'repository_dependencies' in metadata:
            rd_tups = metadata[ 'repository_dependencies' ][ 'repository_dependencies' ]
            for rd_tup in rd_tups:
                agent_shed, name, owner, changeset_revision = rd_tup[ 0:4 ]
                repository_dependency = suc.get_repository_by_name_and_owner( trans.app, name, owner )
                if repository_dependency is None:
                    log.dbug( 'Cannot locate repository dependency %s owned by %s.' % ( name, owner ) )
                    continue
                repository_dependency_id = trans.security.encode_id( repository_dependency.id )
                repository_dependency_repository_metadata = \
                    suc.get_repository_metadata_by_changeset_revision( trans.app, repository_dependency_id, changeset_revision )
                if repository_dependency_repository_metadata is None:
                    # The changeset_revision column in the repository_metadata table has been updated with a new
                    # value value, so find the changeset_revision to which we need to update.
                    repo = hg_util.get_repo_for_repository( trans.app,
                                                            repository=repository_dependency,
                                                            repo_path=None,
                                                            create=False )
                    new_changeset_revision = suc.get_next_downloadable_changeset_revision( repository_dependency,
                                                                                           repo,
                                                                                           changeset_revision )
                    repository_dependency_repository_metadata = \
                        suc.get_repository_metadata_by_changeset_revision( trans.app,
                                                                           repository_dependency_id,
                                                                           new_changeset_revision )
                    if repository_dependency_repository_metadata is None:
                        decoded_repository_dependency_id = trans.security.decode_id( repository_dependency_id )
                        debug_msg = 'Cannot locate repository_metadata with id %d for repository dependency %s owned by %s ' % \
                            ( decoded_repository_dependency_id, str( name ), str( owner ) )
                        debug_msg += 'using either of these changeset_revisions: %s, %s.' % \
                            ( str( changeset_revision ), str( new_changeset_revision ) )
                        log.debug( debug_msg )
                        continue
                    else:
                        changeset_revision = new_changeset_revision
                repository_dependency_metadata_dict = \
                    repository_dependency_repository_metadata.to_dict( view='element',
                                                                       value_mapper=self.__get_value_mapper( trans ) )
                repository_dependency_dict = repository_dependency.to_dict( view='element',
                                                                            value_mapper=self.__get_value_mapper( trans ) )
                # We need to be careful with the entries in our repository_dependency_dict here since this Agent Shed API
                # controller is working with repository_metadata records.  The above to_dict() method returns a dictionary
                # with an id entry for the repository record.  However, all of the other methods in this controller have
                # the id entry associated with a repository_metadata record id.  To avoid confusion, we'll update the
                # repository_dependency_metadata_dict with entries from the repository_dependency_dict without using the
                # Python dictionary update() method because we do not want to overwrite existing entries.
                for k, v in repository_dependency_dict.items():
                    if k not in repository_dependency_metadata_dict:
                        repository_dependency_metadata_dict[ k ] = v
                repository_dependency_metadata_dict[ 'url' ] = web.url_for( controller='repositories',
                                                                            action='show',
                                                                            id=repository_dependency_id )
                repository_dependencies_dicts.append( repository_dependency_metadata_dict )
        return repository_dependencies_dicts

    @web.expose_api_anonymous
    def show( self, trans, id, **kwd ):
        """
        GET /api/repository_revisions/{encoded_repository_metadata_id}
        Displays information about a repository_metadata record in the Agent Shed.

        :param id: the encoded id of the `RepositoryMetadata` object
        """
        # Example URL: http://localhost:9009/api/repository_revisions/bb125606ff9ea620
        repository_metadata = metadata_util.get_repository_metadata_by_id( trans.app, id )
        if repository_metadata is None:
            log.debug( 'Cannot locate repository_metadata with id %s' % str( id ) )
            return {}
        encoded_repository_id = trans.security.encode_id( repository_metadata.repository_id )
        repository_metadata_dict = repository_metadata.to_dict( view='element',
                                                                value_mapper=self.__get_value_mapper( trans ) )
        repository_metadata_dict[ 'url' ] = web.url_for( controller='repositories',
                                                         action='show',
                                                         id=encoded_repository_id )
        return repository_metadata_dict

    @web.expose_api
    def update( self, trans, payload, **kwd ):
        """
        PUT /api/repository_revisions/{encoded_repository_metadata_id}/{payload}
        Updates the value of specified columns of the repository_metadata table based on the key / value pairs in payload.

        :param id: the encoded id of the `RepositoryMetadata` object
        """
        repository_metadata_id = kwd.get( 'id', None )
        if repository_metadata_id is None:
            raise HTTPBadRequest( detail="Missing required parameter 'id'." )
        repository_metadata = metadata_util.get_repository_metadata_by_id( trans.app, repository_metadata_id )
        if repository_metadata is None:
            decoded_repository_metadata_id = trans.security.decode_id( repository_metadata_id )
            log.debug( 'Cannot locate repository_metadata with id %s' % str( decoded_repository_metadata_id ) )
            return {}
        else:
            decoded_repository_metadata_id = repository_metadata.id
        flush_needed = False
        for key, new_value in payload.items():
            if key == 'time_last_tested':
                repository_metadata.time_last_tested = datetime.datetime.utcnow()
                flush_needed = True
            elif hasattr( repository_metadata, key ):
                # log information when setting attributes associated with the Agent Shed's install and test framework.
                if key in [ 'do_not_test', 'includes_agents', 'missing_test_components', 'test_install_error',
                            'agents_functionally_correct' ]:
                    log.debug( 'Setting repository_metadata column %s to value %s for changeset_revision %s via the Agent Shed API.' %
                               ( str( key ), str( new_value ), str( repository_metadata.changeset_revision ) ) )
                setattr( repository_metadata, key, new_value )
                flush_needed = True
        if flush_needed:
            log.debug( 'Updating repository_metadata record with id %s and changeset_revision %s.' %
                       ( str( decoded_repository_metadata_id ), str( repository_metadata.changeset_revision ) ) )
            trans.sa_session.add( repository_metadata )
            trans.sa_session.flush()
            trans.sa_session.refresh( repository_metadata )
        repository_metadata_dict = repository_metadata.to_dict( view='element',
                                                                value_mapper=self.__get_value_mapper( trans ) )
        repository_metadata_dict[ 'url' ] = web.url_for( controller='repository_revisions',
                                                         action='show',
                                                         id=repository_metadata_id )
        return repository_metadata_dict
