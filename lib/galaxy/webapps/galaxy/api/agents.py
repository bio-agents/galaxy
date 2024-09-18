import urllib

from galaxy import exceptions
from galaxy import web, util
from galaxy import managers
from galaxy.web import _future_expose_api_anonymous_and_sessionless as expose_api_anonymous_and_sessionless
from galaxy.web import _future_expose_api_anonymous as expose_api_anonymous
from galaxy.web import _future_expose_api as expose_api
from galaxy.web.base.controller import BaseAPIController
from galaxy.web.base.controller import UsesVisualizationMixin
from galaxy.visualization.genomes import GenomeRegion
from galaxy.util.json import dumps
from galaxy.managers.collections_util import dictify_dataset_collection_instance

import galaxy.queue_worker


import logging
log = logging.getLogger( __name__ )


class AgentsController( BaseAPIController, UsesVisualizationMixin ):
    """
    RESTful controller for interactions with agents.
    """

    def __init__( self, app ):
        super( AgentsController, self ).__init__( app )
        self.history_manager = managers.histories.HistoryManager( app )
        self.hda_manager = managers.hdas.HDAManager( app )

    @expose_api_anonymous_and_sessionless
    def index( self, trans, **kwds ):
        """
        GET /api/agents: returns a list of agents defined by parameters::

            parameters:

                in_panel  - if true, agents are returned in panel structure,
                            including sections and labels
                trackster - if true, only agents that are compatible with
                            Trackster are returned
                q         - if present search on the given query will be performed
                agent_id   - if present the given agent_id will be searched for
                            all installed versions
        """

        # Read params.
        in_panel = util.string_as_bool( kwds.get( 'in_panel', 'True' ) )
        trackster = util.string_as_bool( kwds.get( 'trackster', 'False' ) )
        q = kwds.get( 'q', '' )
        agent_id = kwds.get( 'agent_id', '' )

        # Find whether to search.
        if q:
            hits = self._search( q )
            results = []
            if hits:
                for hit in hits:
                    agent = self._get_agent( hit )
                    if agent:
                        results.append( agent.id )
            return results

        # Find whether to detect.
        if agent_id:
            detected_versions = self._detect( trans, agent_id )
            return detected_versions

        # Return everything.
        try:
            return self.app.agentbox.to_dict( trans, in_panel=in_panel, trackster=trackster)
        except Exception:
            raise exceptions.InternalServerError( "Error: Could not convert agentbox to dictionary" )

    @expose_api_anonymous_and_sessionless
    def show( self, trans, id, **kwd ):
        """
        GET /api/agents/{agent_id}
        Returns agent information, including parameters and inputs.
        """
        io_details = util.string_as_bool( kwd.get( 'io_details', False ) )
        link_details = util.string_as_bool( kwd.get( 'link_details', False ) )
        agent = self._get_agent( id, user=trans.user )
        return agent.to_dict( trans, io_details=io_details, link_details=link_details )

    @expose_api_anonymous
    def build( self, trans, id, **kwd ):
        """
        GET /api/agents/{agent_id}/build
        Returns a agent model including dynamic parameters and updated values, repeats block etc.
        """
        if 'payload' in kwd:
            kwd = kwd.get('payload')
        agent_version = kwd.get( 'agent_version', None )
        agent = self._get_agent( id, agent_version=agent_version, user=trans.user )
        return agent.to_json(trans, kwd.get('inputs', kwd))

    @expose_api
    @web.require_admin
    def reload( self, trans, id, **kwd ):
        """
        GET /api/agents/{agent_id}/reload
        Reload specified agent.
        """
        galaxy.queue_worker.send_control_task( trans.app, 'reload_agent', noop_self=True, kwargs={ 'agent_id': id } )
        message, status = trans.app.agentbox.reload_agent_by_id( id )
        return { status: message }

    @expose_api
    @web.require_admin
    def diagnostics( self, trans, id, **kwd ):
        """
        GET /api/agents/{agent_id}/diagnostics
        Return diagnostic information to help debug panel
        and dependency related problems.
        """
        # TODO: Move this into agent.
        def to_dict(x):
            return x.to_dict()

        agent = self._get_agent( id, user=trans.user )
        if hasattr( agent, 'lineage' ):
            lineage_dict = agent.lineage.to_dict()
        else:
            lineage_dict = None
        agent_shed_dependencies = agent.installed_agent_dependencies
        if agent_shed_dependencies:
            agent_shed_dependencies_dict = map(to_dict, agent_shed_dependencies)
        else:
            agent_shed_dependencies_dict = None
        return {
            "agent_id": agent.id,
            "agent_version": agent.version,
            "dependency_shell_commands": agent.build_dependency_shell_commands(),
            "lineage": lineage_dict,
            "requirements": map(to_dict, agent.requirements),
            "installed_agent_shed_dependencies": agent_shed_dependencies_dict,
            "agent_dir": agent.agent_dir,
            "agent_shed": agent.agent_shed,
            "repository_name": agent.repository_name,
            "repository_owner": agent.repository_owner,
            "installed_changeset_revision": None,
            "guid": agent.guid,
        }

    def _detect( self, trans, agent_id ):
        """
        Detect whether the agent with the given id is installed.

        :param agent_id: exact id of the agent
        :type agent_id:  str

        :return:      list with available versions
        "return type: list
        """
        agents = self.app.agentbox.get_agent( agent_id, get_all_versions=True )
        detected_versions = []
        if agents:
            for agent in agents:
                if agent and agent.allow_user_access( trans.user ):
                    detected_versions.append( agent.version )
        return detected_versions

    def _search( self, q ):
        """
        Perform the search on the given query.
        Boosts and numer of results are configurable in galaxy.ini file.

        :param q: the query to search with
        :type  q: str

        :return:      Dictionary containing the agents' ids of the best hits.
        :return type: dict
        """
        agent_name_boost = self.app.config.get( 'agent_name_boost', 9 )
        agent_section_boost = self.app.config.get( 'agent_section_boost', 3 )
        agent_description_boost = self.app.config.get( 'agent_description_boost', 2 )
        agent_help_boost = self.app.config.get( 'agent_help_boost', 0.5 )
        agent_search_limit = self.app.config.get( 'agent_search_limit', 20 )

        results = self.app.agentbox_search.search( q=q,
                                                  agent_name_boost=agent_name_boost,
                                                  agent_section_boost=agent_section_boost,
                                                  agent_description_boost=agent_description_boost,
                                                  agent_help_boost=agent_help_boost,
                                                  agent_search_limit=agent_search_limit )
        return results

    @expose_api_anonymous_and_sessionless
    def citations( self, trans, id, **kwds ):
        agent = self._get_agent( id, user=trans.user )
        rval = []
        for citation in agent.citations:
            rval.append( citation.to_dict( 'bibtex' ) )
        return rval

    @web.expose_api_raw
    @web.require_admin
    def download( self, trans, id, **kwds ):
        agent_tarball = trans.app.agentbox.package_agent(trans, id)
        trans.response.set_content_type('application/x-gzip')
        download_file = open(agent_tarball, "rb")
        trans.response.headers[ "Content-Disposition" ] = 'attachment; filename="%s.tgz"' % (id)
        return download_file

    @expose_api_anonymous
    def create( self, trans, payload, **kwd ):
        """
        POST /api/agents
        Executes agent using specified inputs and returns agent's outputs.
        """
        # HACK: for now, if action is rerun, rerun agent.
        action = payload.get( 'action', None )
        if action == 'rerun':
            return self._rerun_agent( trans, payload, **kwd )

        # -- Execute agent. --

        # Get agent.
        agent_version = payload.get( 'agent_version', None )
        agent = trans.app.agentbox.get_agent( payload[ 'agent_id' ] , agent_version ) if 'agent_id' in payload else None
        if not agent or not agent.allow_user_access( trans.user ):
            raise exceptions.MessageException( 'Agent not found or not accessible.' )

        # Set running history from payload parameters.
        # History not set correctly as part of this API call for
        # dataset upload.
        history_id = payload.get('history_id', None)
        if history_id:
            decoded_id = self.decode_id( history_id )
            target_history = self.history_manager.get_owned( decoded_id, trans.user, current_history=trans.history )
        else:
            target_history = None

        # Set up inputs.
        inputs = payload.get( 'inputs', {} )
        # Find files coming in as multipart file data and add to inputs.
        for k, v in payload.iteritems():
            if k.startswith('files_') or k.startswith('__files_'):
                inputs[k] = v

        # for inputs that are coming from the Library, copy them into the history
        input_patch = {}
        for k, v in inputs.iteritems():
            if isinstance(v, dict) and v.get('src', '') == 'ldda' and 'id' in v:
                ldda = trans.sa_session.query( trans.app.model.LibraryDatasetDatasetAssociation ).get( self.decode_id(v['id']) )
                if trans.user_is_admin() or trans.app.security_agent.can_access_dataset( trans.get_current_user_roles(), ldda.dataset ):
                    input_patch[k] = ldda.to_history_dataset_association(target_history, add_to_history=True)

        for k, v in input_patch.iteritems():
            inputs[k] = v

        # TODO: encode data ids and decode ids.
        # TODO: handle dbkeys
        params = util.Params( inputs, sanitize=False )
        incoming = params.__dict__
        vars = agent.handle_input( trans, incoming, history=target_history, source='json' )

        # TODO: check for errors and ensure that output dataset(s) are available.
        output_datasets = vars.get( 'out_data', [] )
        rval = { 'outputs': [], 'output_collections': [], 'jobs': [], 'implicit_collections': [] }

        job_errors = vars.get( 'job_errors', [] )
        if job_errors:
            # If we are here - some jobs were successfully executed but some failed.
            rval[ 'errors' ] = job_errors

        outputs = rval[ 'outputs' ]
        # TODO:?? poss. only return ids?
        for output_name, output in output_datasets:
            output_dict = output.to_dict()
            # add the output name back into the output data structure
            # so it's possible to figure out which newly created elements
            # correspond with which agent file outputs
            output_dict[ 'output_name' ] = output_name
            outputs.append( trans.security.encode_dict_ids( output_dict ) )

        for job in vars.get('jobs', []):
            rval[ 'jobs' ].append( self.encode_all_ids( trans, job.to_dict( view='collection' ), recursive=True ) )

        for output_name, collection_instance in vars.get('output_collections', []):
            history = target_history or trans.history
            output_dict = dictify_dataset_collection_instance( collection_instance, security=trans.security, parent=history )
            output_dict[ 'output_name' ] = output_name
            rval[ 'output_collections' ].append( output_dict )

        for output_name, collection_instance in vars.get( 'implicit_collections', {} ).iteritems():
            history = target_history or trans.history
            output_dict = dictify_dataset_collection_instance( collection_instance, security=trans.security, parent=history )
            output_dict[ 'output_name' ] = output_name
            rval[ 'implicit_collections' ].append( output_dict )

        return rval

    #
    # -- Helper methods --
    #
    def _get_agent( self, id, agent_version=None, user=None ):
        id = urllib.unquote_plus( id )
        agent = self.app.agentbox.get_agent( id, agent_version )
        if not agent or not agent.allow_user_access( user ):
            raise exceptions.ObjectNotFound("Could not find agent with id '%s'" % id)
        return agent

    def _rerun_agent( self, trans, payload, **kwargs ):
        """
        Rerun a agent to produce a new output dataset that corresponds to a
        dataset that a user is currently viewing.
        """

        #
        # TODO: refactor to use same code as run_agent.
        #

        # Run agent on region if region is specificied.
        run_on_regions = False
        regions = payload.get( 'regions', None )
        if regions:
            if isinstance( regions, dict ):
                # Regions is a single region.
                regions = [ GenomeRegion.from_dict( regions ) ]
            elif isinstance( regions, list ):
                # There is a list of regions.
                regions = [ GenomeRegion.from_dict( r ) for r in regions ]

                if len( regions ) > 1:
                    # Sort by chrom name, start so that data is not fetched out of order.
                    regions = sorted(regions, key=lambda r: (r.chrom.lower(), r.start))

                    # Merge overlapping regions so that regions do not overlap
                    # and hence data is not included multiple times.
                    prev = regions[0]
                    cur = regions[1]
                    index = 1
                    while True:
                        if cur.chrom == prev.chrom and cur.start <= prev.end:
                            # Found overlapping regions, so join them into prev.
                            prev.end = cur.end
                            del regions[ index ]
                        else:
                            # No overlap, move to next region.
                            prev = cur
                            index += 1

                        # Get next region or exit.
                        if index == len( regions ):
                            # Done.
                            break
                        else:
                            cur = regions[ index ]

            run_on_regions = True

        # Dataset check.
        decoded_dataset_id = self.decode_id( payload.get( 'target_dataset_id' ) )
        original_dataset = self.hda_manager.get_accessible( decoded_dataset_id, user=trans.user )
        original_dataset = self.hda_manager.error_if_uploading( original_dataset )
        msg = self.hda_manager.data_conversion_status( original_dataset )
        if msg:
            return msg

        # Set agent parameters--except non-hidden dataset parameters--using combination of
        # job's previous parameters and incoming parameters. Incoming parameters
        # have priority.
        #
        original_job = self.hda_manager.creating_job( original_dataset )
        agent = trans.app.agentbox.get_agent( original_job.agent_id )
        if not agent or not agent.allow_user_access( trans.user ):
            return trans.app.model.Dataset.conversion_messages.NO_TOOL
        agent_params = dict( [ ( p.name, p.value ) for p in original_job.parameters ] )

        # TODO: rather than set new inputs using dict of json'ed value, unpack parameters and set using set_param_value below.
        # TODO: need to handle updates to conditional parameters; conditional
        # params are stored in dicts (and dicts within dicts).
        new_inputs = payload[ 'inputs' ]
        agent_params.update( dict( [ ( key, dumps( value ) ) for key, value in new_inputs.items() if key in agent.inputs and new_inputs[ key ] is not None ] ) )
        agent_params = agent.params_from_strings( agent_params, self.app )

        #
        # If running agent on region, convert input datasets (create indices) so
        # that can regions of data can be quickly extracted.
        #
        data_provider_registry = trans.app.data_provider_registry
        messages_list = []
        if run_on_regions:
            for jida in original_job.input_datasets:
                input_dataset = jida.dataset
                data_provider = data_provider_registry.get_data_provider( trans, original_dataset=input_dataset, source='data' )
                if data_provider and ( not data_provider.converted_dataset or
                                       data_provider.converted_dataset.state != trans.app.model.Dataset.states.OK ):
                    # Can convert but no converted dataset yet, so return message about why.
                    data_sources = input_dataset.datatype.data_sources
                    msg = input_dataset.convert_dataset( trans, data_sources[ 'data' ] )
                    if msg is not None:
                        messages_list.append( msg )

        # Return any messages generated during conversions.
        return_message = self._get_highest_priority_msg( messages_list )
        if return_message:
            return return_message

        #
        # Set target history (the history that agent will use for inputs/outputs).
        # If user owns dataset, put new data in original dataset's history; if
        # user does not own dataset (and hence is accessing dataset via sharing),
        # put new data in user's current history.
        #
        if original_dataset.history.user == trans.user:
            target_history = original_dataset.history
        else:
            target_history = trans.get_history( create=True )
        hda_permissions = trans.app.security_agent.history_get_default_permissions( target_history )

        def set_param_value( param_dict, param_name, param_value ):
            """
            Set new parameter value in a agent's parameter dictionary.
            """

            # Recursive function to set param value.
            def set_value( param_dict, group_name, group_index, param_name, param_value ):
                if group_name in param_dict:
                    param_dict[ group_name ][ group_index ][ param_name ] = param_value
                    return True
                elif param_name in param_dict:
                    param_dict[ param_name ] = param_value
                    return True
                else:
                    # Recursive search.
                    return_val = False
                    for value in param_dict.values():
                        if isinstance( value, dict ):
                            return_val = set_value( value, group_name, group_index, param_name, param_value)
                            if return_val:
                                return return_val
                    return False

            # Parse parameter name if necessary.
            if param_name.find( "|" ) == -1:
                # Non-grouping parameter.
                group_name = group_index = None
            else:
                # Grouping parameter.
                group, param_name = param_name.split( "|" )
                index = group.rfind( "_" )
                group_name = group[ :index ]
                group_index = int( group[ index + 1: ] )

            return set_value( param_dict, group_name, group_index, param_name, param_value )

        # Set parameters based agent's trackster config.
        params_set = {}
        for action in agent.trackster_conf.actions:
            success = False
            for joda in original_job.output_datasets:
                if joda.name == action.output_name:
                    set_param_value( agent_params, action.name, joda.dataset )
                    params_set[ action.name ] = True
                    success = True
                    break

            if not success:
                return trans.app.model.Dataset.conversion_messages.ERROR

        #
        # Set input datasets for agent. If running on regions, extract and use subset
        # when possible.
        #
        if run_on_regions:
            regions_str = ",".join( [ str( r ) for r in regions ] )
        for jida in original_job.input_datasets:
            # If param set previously by config actions, do nothing.
            if jida.name in params_set:
                continue

            input_dataset = jida.dataset
            if input_dataset is None:  # optional dataset and dataset wasn't selected
                agent_params[ jida.name ] = None
            elif run_on_regions and 'data' in input_dataset.datatype.data_sources:
                # Dataset is indexed and hence a subset can be extracted and used
                # as input.

                # Look for subset.
                subset_dataset_association = trans.sa_session.query( trans.app.model.HistoryDatasetAssociationSubset ) \
                                                             .filter_by( hda=input_dataset, location=regions_str ) \
                                                             .first()
                if subset_dataset_association:
                    # Data subset exists.
                    subset_dataset = subset_dataset_association.subset
                else:
                    # Need to create subset.
                    data_source = input_dataset.datatype.data_sources[ 'data' ]
                    input_dataset.get_converted_dataset( trans, data_source )
                    input_dataset.get_converted_dataset_deps( trans, data_source )

                    # Create new HDA for input dataset's subset.
                    new_dataset = trans.app.model.HistoryDatasetAssociation( extension=input_dataset.ext,
                                                                             dbkey=input_dataset.dbkey,
                                                                             create_dataset=True,
                                                                             sa_session=trans.sa_session,
                                                                             name="Subset [%s] of data %i" %
                                                                                  ( regions_str, input_dataset.hid ),
                                                                             visible=False )
                    target_history.add_dataset( new_dataset )
                    trans.sa_session.add( new_dataset )
                    trans.app.security_agent.set_all_dataset_permissions( new_dataset.dataset, hda_permissions )

                    # Write subset of data to new dataset
                    data_provider = data_provider_registry.get_data_provider( trans, original_dataset=input_dataset, source='data' )
                    trans.app.object_store.create( new_dataset.dataset )
                    data_provider.write_data_to_file( regions, new_dataset.file_name )

                    # TODO: (a) size not working; (b) need to set peek.
                    new_dataset.set_size()
                    new_dataset.info = "Data subset for trackster"
                    new_dataset.set_dataset_state( trans.app.model.Dataset.states.OK )

                    # Set metadata.
                    # TODO: set meta internally if dataset is small enough?
                    trans.app.datatypes_registry.set_external_metadata_agent.agent_action.execute( trans.app.datatypes_registry.set_external_metadata_agent,
                                                                                                 trans, incoming={ 'input1': new_dataset },
                                                                                                 overwrite=False, job_params={ "source" : "trackster" } )
                    # Add HDA subset association.
                    subset_association = trans.app.model.HistoryDatasetAssociationSubset( hda=input_dataset, subset=new_dataset, location=regions_str )
                    trans.sa_session.add( subset_association )

                    subset_dataset = new_dataset

                trans.sa_session.flush()

                # Add dataset to agent's parameters.
                if not set_param_value( agent_params, jida.name, subset_dataset ):
                    return { "error" : True, "message" : "error setting parameter %s" % jida.name }

        #
        # Execute agent and handle outputs.
        #
        try:
            subset_job, subset_job_outputs = agent.execute( trans, incoming=agent_params,
                                                           history=target_history,
                                                           job_params={ "source" : "trackster" } )
        except Exception, e:
            # Lots of things can go wrong when trying to execute agent.
            return { "error" : True, "message" : e.__class__.__name__ + ": " + str(e) }
        if run_on_regions:
            for output in subset_job_outputs.values():
                output.visible = False
            trans.sa_session.flush()

        #
        # Return new track that corresponds to the original dataset.
        #
        output_name = None
        for joda in original_job.output_datasets:
            if joda.dataset == original_dataset:
                output_name = joda.name
                break
        for joda in subset_job.output_datasets:
            if joda.name == output_name:
                output_dataset = joda.dataset

        dataset_dict = output_dataset.to_dict()
        dataset_dict[ 'id' ] = trans.security.encode_id( dataset_dict[ 'id' ] )
        dataset_dict[ 'track_config' ] = self.get_new_track_config( trans, output_dataset )
        return dataset_dict
