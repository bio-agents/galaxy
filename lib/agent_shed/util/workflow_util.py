""" Agent shed helper methods for dealing with workflows - only two methods are
utilized outside of this modules - generate_workflow_image and import_workflow.
"""
import logging
import os

import galaxy.agents
import galaxy.agents.parameters
from galaxy.util import json
from galaxy.util.sanitize_html import sanitize_html
from galaxy.workflow.render import WorkflowCanvas
from galaxy.workflow.steps import attach_ordered_steps
from galaxy.workflow.modules import module_types
from galaxy.workflow.modules import AgentModule
from galaxy.workflow.modules import WorkflowModuleFactory

from agent_shed.agents import agent_validator

from agent_shed.util import encoding_util
from agent_shed.util import metadata_util
from agent_shed.util import shed_util_common as suc

log = logging.getLogger( __name__ )


class RepoAgentModule( AgentModule ):

    type = "agent"

    def __init__( self, trans, repository_id, changeset_revision, agents_metadata, agent_id ):
        self.trans = trans
        self.agents_metadata = agents_metadata
        self.agent_id = agent_id
        self.agent = None
        self.errors = None
        self.tv = agent_validator.AgentValidator( trans.app )
        if trans.webapp.name == 'agent_shed':
            # We're in the agent shed.
            for agent_dict in agents_metadata:
                if self.agent_id in [ agent_dict[ 'id' ], agent_dict[ 'guid' ] ]:
                    repository, self.agent, message = self.tv.load_agent_from_changeset_revision( repository_id,
                                                                                                changeset_revision,
                                                                                                agent_dict[ 'agent_config' ] )
                    if message and self.agent is None:
                        self.errors = 'unavailable'
                    break
        else:
            # We're in Galaxy.
            self.agent = trans.app.agentbox.get_agent( self.agent_id )
            if self.agent is None:
                self.errors = 'unavailable'
        self.post_job_actions = {}
        self.workflow_outputs = []
        self.state = None

    @classmethod
    def from_dict( Class, trans, step_dict, repository_id, changeset_revision, agents_metadata, secure=True ):
        agent_id = step_dict[ 'agent_id' ]
        module = Class( trans, repository_id, changeset_revision, agents_metadata, agent_id )
        module.state = galaxy.agents.DefaultAgentState()
        if module.agent is not None:
            module.state.decode( step_dict[ "agent_state" ], module.agent, module.trans.app, secure=secure )
        module.errors = step_dict.get( "agent_errors", None )
        return module

    @classmethod
    def from_workflow_step( Class, trans, step, repository_id, changeset_revision, agents_metadata ):
        module = Class( trans, repository_id, changeset_revision, agents_metadata, step.agent_id )
        module.state = galaxy.agents.DefaultAgentState()
        if module.agent:
            module.state.inputs = module.agent.params_from_strings( step.agent_inputs, trans.app, ignore_errors=True )
        else:
            module.state.inputs = {}
        module.errors = step.agent_errors
        return module

    def get_data_inputs( self ):
        data_inputs = []

        def callback( input, value, prefixed_name, prefixed_label ):
            if isinstance( input, galaxy.agents.parameters.basic.DataAgentParameter ):
                data_inputs.append( dict( name=prefixed_name,
                                          label=prefixed_label,
                                          extensions=input.extensions ) )
        if self.agent:
            try:
                galaxy.agents.parameters.visit_input_values( self.agent.inputs, self.state.inputs, callback )
            except:
                # TODO have this actually use default parameters?  Fix at
                # refactor, needs to be discussed wrt: reproducibility though.
                log.exception("Agent parse failed for %s -- this indicates incompatibility of local agent version with expected version by the workflow." % self.agent.id)
        return data_inputs

    def get_data_outputs( self ):
        data_outputs = []
        if self.agent:
            data_inputs = None
            for name, agent_output in self.agent.outputs.iteritems():
                if agent_output.format_source is not None:
                    # Default to special name "input" which remove restrictions on connections
                    formats = [ 'input' ]
                    if data_inputs is None:
                        data_inputs = self.get_data_inputs()
                    # Find the input parameter referenced by format_source
                    for di in data_inputs:
                        # Input names come prefixed with conditional and repeat names separated by '|',
                        # so remove prefixes when comparing with format_source.
                        if di[ 'name' ] is not None and di[ 'name' ].split( '|' )[ -1 ] == agent_output.format_source:
                            formats = di[ 'extensions' ]
                else:
                    formats = [ agent_output.format ]
                for change_elem in agent_output.change_format:
                    for when_elem in change_elem.findall( 'when' ):
                        format = when_elem.get( 'format', None )
                        if format and format not in formats:
                            formats.append( format )
                data_outputs.append( dict( name=name, extensions=formats ) )
        return data_outputs


class RepoWorkflowModuleFactory( WorkflowModuleFactory ):

    def __init__( self, module_types ):
        self.module_types = module_types

    def from_dict( self, trans, repository_id, changeset_revision, step_dict, agents_metadata, **kwd ):
        """Return module initialized from the data in dictionary `step_dict`."""
        type = step_dict[ 'type' ]
        assert type in self.module_types
        module_method_kwds = dict( **kwd )
        if type == "agent":
            module_method_kwds[ 'repository_id' ] = repository_id
            module_method_kwds[ 'changeset_revision' ] = changeset_revision
            module_method_kwds[ 'agents_metadata' ] = agents_metadata
        return self.module_types[ type ].from_dict( trans, step_dict, **module_method_kwds )

    def from_workflow_step( self, trans, repository_id, changeset_revision, agents_metadata, step ):
        """Return module initialized from the WorkflowStep object `step`."""
        type = step.type
        module_method_kwds = dict( )
        if type == "agent":
            module_method_kwds[ 'repository_id' ] = repository_id
            module_method_kwds[ 'changeset_revision' ] = changeset_revision
            module_method_kwds[ 'agents_metadata' ] = agents_metadata
        return self.module_types[ type ].from_workflow_step( trans, step, **module_method_kwds )

agent_shed_module_types = module_types.copy()
agent_shed_module_types[ 'agent' ] = RepoAgentModule
module_factory = RepoWorkflowModuleFactory( agent_shed_module_types )


def generate_workflow_image( trans, workflow_name, repository_metadata_id=None, repository_id=None ):
    """
    Return an svg image representation of a workflow dictionary created when the workflow was exported.  This method is called
    from both Galaxy and the agent shed.  When called from the agent shed, repository_metadata_id will have a value and repository_id
    will be None.  When called from Galaxy, repository_metadata_id will be None and repository_id will have a value.
    """
    workflow_name = encoding_util.agent_shed_decode( workflow_name )
    if trans.webapp.name == 'agent_shed':
        # We're in the agent shed.
        repository_metadata = metadata_util.get_repository_metadata_by_id( trans.app, repository_metadata_id )
        repository_id = trans.security.encode_id( repository_metadata.repository_id )
        changeset_revision = repository_metadata.changeset_revision
        metadata = repository_metadata.metadata
    else:
        # We're in Galaxy.
        repository = suc.get_agent_shed_repository_by_id( trans.app, repository_id )
        changeset_revision = repository.changeset_revision
        metadata = repository.metadata
    # metadata[ 'workflows' ] is a list of tuples where each contained tuple is
    # [ <relative path to the .ga file in the repository>, <exported workflow dict> ]
    for workflow_tup in metadata[ 'workflows' ]:
        workflow_dict = workflow_tup[1]
        if workflow_dict[ 'name' ] == workflow_name:
            break
    if 'agents' in metadata:
        agents_metadata = metadata[ 'agents' ]
    else:
        agents_metadata = []
    workflow, missing_agent_tups = get_workflow_from_dict( trans=trans,
                                                          workflow_dict=workflow_dict,
                                                          agents_metadata=agents_metadata,
                                                          repository_id=repository_id,
                                                          changeset_revision=changeset_revision )
    workflow_canvas = WorkflowCanvas()
    canvas = workflow_canvas.canvas
    # Store px width for boxes of each step.
    for step in workflow.steps:
        step.upgrade_messages = {}
        module = module_factory.from_workflow_step( trans, repository_id, changeset_revision, agents_metadata, step )
        agent_errors = module.type == 'agent' and not module.agent
        module_data_inputs = get_workflow_data_inputs( step, module )
        module_data_outputs = get_workflow_data_outputs( step, module, workflow.steps )
        module_name = get_workflow_module_name( module, missing_agent_tups )
        workflow_canvas.populate_data_for_step(
            step,
            module_name,
            module_data_inputs,
            module_data_outputs,
            agent_errors=agent_errors
        )
    workflow_canvas.add_steps( highlight_errors=True )
    workflow_canvas.finish( )
    trans.response.set_content_type( "image/svg+xml" )
    return canvas.standalone_xml()


def get_workflow_data_inputs( step, module ):
    if module.type == 'agent':
        if module.agent:
            return module.get_data_inputs()
        else:
            data_inputs = []
            for wfsc in step.input_connections:
                data_inputs_dict = {}
                data_inputs_dict[ 'extensions' ] = [ '' ]
                data_inputs_dict[ 'name' ] = wfsc.input_name
                data_inputs_dict[ 'label' ] = 'Unknown'
                data_inputs.append( data_inputs_dict )
            return data_inputs
    return module.get_data_inputs()


def get_workflow_data_outputs( step, module, steps ):
    if module.type == 'agent':
        if module.agent:
            return module.get_data_outputs()
        else:
            data_outputs = []
            data_outputs_dict = {}
            data_outputs_dict[ 'extensions' ] = [ 'input' ]
            found = False
            for workflow_step in steps:
                for wfsc in workflow_step.input_connections:
                    if step.name == wfsc.output_step.name:
                        data_outputs_dict[ 'name' ] = wfsc.output_name
                        found = True
                        break
                if found:
                    break
            if not found:
                # We're at the last step of the workflow.
                data_outputs_dict[ 'name' ] = 'output'
            data_outputs.append( data_outputs_dict )
            return data_outputs
    return module.get_data_outputs()


def get_workflow_from_dict( trans, workflow_dict, agents_metadata, repository_id, changeset_revision ):
    """
    Return an in-memory Workflow object from the dictionary object created when it was exported.  This method is called from
    both Galaxy and the agent shed to retrieve a Workflow object that can be displayed as an SVG image.  This method is also
    called from Galaxy to retrieve a Workflow object that can be used for saving to the Galaxy database.
    """
    trans.workflow_building_mode = True
    workflow = trans.model.Workflow()
    workflow.name = workflow_dict[ 'name' ]
    workflow.has_errors = False
    steps = []
    # Keep ids for each step that we need to use to make connections.
    steps_by_external_id = {}
    # Keep track of agents required by the workflow that are not available in
    # the agent shed repository.  Each tuple in the list of missing_agent_tups
    # will be ( agent_id, agent_name, agent_version ).
    missing_agent_tups = []
    # First pass to build step objects and populate basic values
    for step_dict in workflow_dict[ 'steps' ].itervalues():
        # Create the model class for the step
        step = trans.model.WorkflowStep()
        step.label = step_dict.get('label', None)
        step.name = step_dict[ 'name' ]
        step.position = step_dict[ 'position' ]
        module = module_factory.from_dict( trans, repository_id, changeset_revision, step_dict, agents_metadata=agents_metadata, secure=False )
        if module.type == 'agent' and module.agent is None:
            # A required agent is not available in the current repository.
            step.agent_errors = 'unavailable'
            missing_agent_tup = ( step_dict[ 'agent_id' ], step_dict[ 'name' ], step_dict[ 'agent_version' ] )
            if missing_agent_tup not in missing_agent_tups:
                missing_agent_tups.append( missing_agent_tup )
        module.save_to_step( step )
        if step.agent_errors:
            workflow.has_errors = True
        # Stick this in the step temporarily.
        step.temp_input_connections = step_dict[ 'input_connections' ]
        if trans.webapp.name == 'galaxy':
            annotation = step_dict.get( 'annotation', '')
            if annotation:
                annotation = sanitize_html( annotation, 'utf-8', 'text/html' )
                new_step_annotation = trans.model.WorkflowStepAnnotationAssociation()
                new_step_annotation.annotation = annotation
                new_step_annotation.user = trans.user
                step.annotations.append( new_step_annotation )
        # Unpack and add post-job actions.
        post_job_actions = step_dict.get( 'post_job_actions', {} )
        for pja_dict in post_job_actions.values():
            trans.model.PostJobAction( pja_dict[ 'action_type' ],
                                       step,
                                       pja_dict[ 'output_name' ],
                                       pja_dict[ 'action_arguments' ] )
        steps.append( step )
        steps_by_external_id[ step_dict[ 'id' ] ] = step
    # Second pass to deal with connections between steps.
    for step in steps:
        # Input connections.
        for input_name, conn_dict in step.temp_input_connections.iteritems():
            if conn_dict:
                output_step = steps_by_external_id[ conn_dict[ 'id' ] ]
                conn = trans.model.WorkflowStepConnection()
                conn.input_step = step
                conn.input_name = input_name
                conn.output_step = output_step
                conn.output_name = conn_dict[ 'output_name' ]
                step.input_connections.append( conn )
        del step.temp_input_connections
    # Order the steps if possible.
    attach_ordered_steps( workflow, steps )
    # Return the in-memory Workflow object for display or later persistence to the Galaxy database.
    return workflow, missing_agent_tups


def get_workflow_module_name( module, missing_agent_tups ):
    module_name = module.get_name()
    if module.type == 'agent' and module_name == 'unavailable':
        for missing_agent_tup in missing_agent_tups:
            missing_agent_id, missing_agent_name, missing_agent_version = missing_agent_tup
            if missing_agent_id == module.agent_id:
                module_name = '%s' % missing_agent_name
                break
    return module_name


def import_workflow( trans, repository, workflow_name ):
    """Import a workflow contained in an installed agent shed repository into Galaxy (this method is called only from Galaxy)."""
    status = 'done'
    message = ''
    changeset_revision = repository.changeset_revision
    metadata = repository.metadata
    workflows = metadata.get( 'workflows', [] )
    agents_metadata = metadata.get( 'agents', [] )
    workflow_dict = None
    for workflow_data_tuple in workflows:
        # The value of workflow_data_tuple is ( relative_path_to_workflow_file, exported_workflow_dict ).
        relative_path_to_workflow_file, exported_workflow_dict = workflow_data_tuple
        if exported_workflow_dict[ 'name' ] == workflow_name:
            # If the exported workflow is available on disk, import it.
            if os.path.exists( relative_path_to_workflow_file ):
                workflow_file = open( relative_path_to_workflow_file, 'rb' )
                workflow_data = workflow_file.read()
                workflow_file.close()
                workflow_dict = json.loads( workflow_data )
            else:
                # Use the current exported_workflow_dict.
                workflow_dict = exported_workflow_dict
            break
    if workflow_dict:
        # Create workflow if possible.
        workflow, missing_agent_tups = get_workflow_from_dict( trans=trans,
                                                              workflow_dict=workflow_dict,
                                                              agents_metadata=agents_metadata,
                                                              repository_id=repository.id,
                                                              changeset_revision=changeset_revision )
        # Save the workflow in the Galaxy database.  Pass workflow_dict along to create annotation at this point.
        stored_workflow = save_workflow( trans, workflow, workflow_dict )
        # Use the latest version of the saved workflow.
        workflow = stored_workflow.latest_workflow
        if workflow_name:
            workflow.name = workflow_name
        # Provide user feedback and show workflow list.
        if workflow.has_errors:
            message += "Imported, but some steps in this workflow have validation errors. "
            status = "error"
        if workflow.has_cycles:
            message += "Imported, but this workflow contains cycles.  "
            status = "error"
        else:
            message += "Workflow <b>%s</b> imported successfully.  " % workflow.name
        if missing_agent_tups:
            name_and_id_str = ''
            for missing_agent_tup in missing_agent_tups:
                agent_id, agent_name, other = missing_agent_tup
                name_and_id_str += 'name: %s, id: %s' % ( str( agent_id ), str( agent_name ) )
            message += "The following agents required by this workflow are missing from this Galaxy instance: %s.  " % name_and_id_str
    else:
        workflow = None
        message += 'The workflow named %s is not included in the metadata for revision %s of repository %s' % \
            ( str( workflow_name ), str( changeset_revision ), str( repository.name ) )
        status = 'error'
    return workflow, status, message


def save_workflow( trans, workflow, workflow_dict=None):
    """Use the received in-memory Workflow object for saving to the Galaxy database."""
    stored = trans.model.StoredWorkflow()
    stored.name = workflow.name
    workflow.stored_workflow = stored
    stored.latest_workflow = workflow
    stored.user = trans.user
    if workflow_dict and workflow_dict.get('annotation', ''):
        annotation = sanitize_html( workflow_dict['annotation'], 'utf-8', 'text/html' )
        new_annotation = trans.model.StoredWorkflowAnnotationAssociation()
        new_annotation.annotation = annotation
        new_annotation.user = trans.user
        stored.annotations.append(new_annotation)
    trans.sa_session.add( stored )
    trans.sa_session.flush()
    # Add a new entry to the Workflows menu.
    if trans.user.stored_workflow_menu_entries is None:
        trans.user.stored_workflow_menu_entries = []
    menuEntry = trans.model.StoredWorkflowMenuEntry()
    menuEntry.stored_workflow = stored
    trans.user.stored_workflow_menu_entries.append( menuEntry )
    trans.sa_session.flush()
    return stored
