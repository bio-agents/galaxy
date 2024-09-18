"""
Modules used in building workflows
"""

import logging
import re

from xml.etree.ElementTree import Element

import galaxy.agents
from galaxy import exceptions
from galaxy import model
from galaxy import web
from galaxy.dataset_collections import matching
from galaxy.web.framework import formbuilder
from galaxy.jobs.actions.post import ActionBox
from galaxy.model import PostJobAction
from galaxy.agents.parameters import check_param, visit_input_values
from galaxy.agents.parameters.basic import (
    parameter_types,
    DataCollectionAgentParameter,
    DataAgentParameter,
    DummyDataset,
    RuntimeValue,
)
from galaxy.agents.parameters.wrapped import make_dict_copy
from galaxy.agents.execute import execute
from galaxy.util.bunch import Bunch
from galaxy.util import odict
from galaxy.util.json import loads
from galaxy.util.json import dumps
from agent_shed.util import common_util

log = logging.getLogger( __name__ )

# Key into Agent state to describe invocation-specific runtime properties.
RUNTIME_STEP_META_STATE_KEY = "__STEP_META_STATE__"
# Key into step runtime state dict describing invocation-specific post job
# actions (i.e. PJA specified at runtime on top of the workflow-wide defined
# ones.
RUNTIME_POST_JOB_ACTIONS_KEY = "__POST_JOB_ACTIONS__"
NO_REPLACEMENT = object()


class WorkflowModule( object ):

    def __init__( self, trans ):
        self.trans = trans

    # ---- Creating modules from various representations ---------------------

    @classmethod
    def new( Class, trans, content_id=None ):
        """
        Create a new instance of the module with default state
        """
        return Class( trans )

    @classmethod
    def from_dict( Class, trans, d ):
        """
        Create a new instance of the module initialized from values in the
        dictionary `d`.
        """
        return Class( trans )

    @classmethod
    def from_workflow_step( Class, trans, step ):
        return Class( trans )

    # ---- Saving in various forms ------------------------------------------

    def save_to_step( self, step ):
        step.type = self.type

    # ---- General attributes -----------------------------------------------

    def get_type( self ):
        return self.type

    def get_name( self ):
        return self.name

    def get_content_id( self ):
        """ If this component has an identifier external to the step (such
        as a agent or another workflow) return the identifier for that content.
        """
        return None

    def get_agenttip( self, static_path='' ):
        return None

    # ---- Configuration time -----------------------------------------------

    def get_state( self, secure=True ):
        """ Return a serializable representation of the persistable state of
        the step - for agents it DefaultAgentState.encode returns a string and
        for simpler module types a json description is dumped out.
        """
        return None

    def update_state( self, incoming ):
        """ Update the current state of the module against the user supplied
        parameters in the dict-like object `incoming`.
        """
        pass

    def get_errors( self ):
        """ It seems like this is effectively just used as boolean - some places
        in the agent shed self.errors is set to boolean, other places 'unavailable',
        likewise in Galaxy it stores a list containing a string with an unrecognized
        agent id error message.
        """
        return None

    def get_data_inputs( self ):
        """ Get configure time data input descriptions. """
        return []

    def get_data_outputs( self ):
        return []

    def get_runtime_input_dicts( self, step_annotation ):
        """ Get runtime inputs (inputs and parameters) as simple dictionary. """
        return []

    def get_config_form( self ):
        """ Render form that is embedded in workflow editor for modifying the
        step state of a node.
        """
        raise TypeError( "Abstract method" )

    def check_and_update_state( self ):
        """
        If the state is not in sync with the current implementation of the
        module, try to update. Returns a list of messages to be displayed
        """
        pass

    def add_dummy_datasets( self, connections=None):
        # Replaced connected inputs with DummyDataset values.
        pass

    # ---- Run time ---------------------------------------------------------

    def get_runtime_inputs( self, **kwds ):
        """ Used internally by modules and when displaying inputs in workflow
        editor and run workflow templates.

        Note: The AgentModule doesn't implement this and these templates contain
        specialized logic for dealing with the agent and state directly in the
        case of AgentModules.
        """
        raise TypeError( "Abstract method" )

    def encode_runtime_state( self, trans, state ):
        """ Encode the default runtime state at return as a simple `str` for
        use in a hidden parameter on the workflow run submission form.

        This default runtime state will be combined with user supplied
        parameters in `compute_runtime_state` below at workflow invocation time to
        actually describe how each step will be executed.
        """
        raise TypeError( "Abstract method" )

    def compute_runtime_state( self, trans, step_updates=None, source="html" ):
        """ Determine the runtime state (potentially different from self.state
        which describes configuration state). This (again unlike self.state) is
        currently always a `DefaultAgentState` object.

        If `step_updates` is `None`, this is likely for rendering the run form
        for instance and no runtime properties are available and state must be
        solely determined by the default runtime state described by the step.

        If `step_updates` are available they describe the runtime properties
        supplied by the workflow runner (potentially including a `agent_state`
        parameter which is the serialized default encoding state created with
        encode_runtime_state above).
        """
        raise TypeError( "Abstract method" )

    def execute( self, trans, progress, invocation, step ):
        """ Execute the given workflow step in the given workflow invocation.
        Use the supplied workflow progress object to track outputs, find
        inputs, etc...
        """
        raise TypeError( "Abstract method" )

    def do_invocation_step_action( self, step, action ):
        """ Update or set the workflow invocation state action - generic
        extension point meant to allows users to interact with interactive
        workflow modules. The action object returned from this method will
        be attached to the WorkflowInvocationStep and be available the next
        time the workflow scheduler visits the workflow.
        """
        raise exceptions.RequestParameterInvalidException( "Attempting to perform invocation step action on module that does not support actions." )

    def recover_mapping( self, step, step_invocations, progress ):
        """ Re-populate progress object with information about connections
        from previously executed steps recorded via step_invocations.
        """
        raise TypeError( "Abstract method" )


class SimpleWorkflowModule( WorkflowModule ):

    @classmethod
    def new( Class, trans, content_id=None ):
        module = Class( trans )
        module.state = Class.default_state()
        module.label = None
        return module

    @classmethod
    def from_dict( Class, trans, d, secure=True ):
        module = Class( trans )
        state = loads( d["agent_state"] )
        module.recover_state( state )
        module.label = d.get("label", None) or None
        return module

    @classmethod
    def from_workflow_step( Class, trans, step ):
        module = Class( trans )
        module.recover_state( step.agent_inputs )
        module.label = step.label
        return module

    @classmethod
    def default_state( Class ):
        """ This method should return a dictionary describing each
        configuration property and its default value.
        """
        raise TypeError( "Abstract method" )

    def save_to_step( self, step ):
        step.type = self.type
        step.agent_id = None
        step.agent_version = None
        step.agent_inputs = self.state

    def get_state( self, secure=True ):
        return dumps( self.state )

    def update_state( self, incoming ):
        self.recover_state( incoming )

    def recover_runtime_state( self, runtime_state ):
        """ Take secure runtime state from persisted invocation and convert it
        into a DefaultAgentState object for use during workflow invocation.
        """
        fake_agent = Bunch( inputs=self.get_runtime_inputs() )
        state = galaxy.agents.DefaultAgentState()
        state.decode( runtime_state, fake_agent, self.trans.app, secure=False )
        return state

    def normalize_runtime_state( self, runtime_state ):
        fake_agent = Bunch( inputs=self.get_runtime_inputs() )
        return runtime_state.encode( fake_agent, self.trans.app, secure=False )

    def encode_runtime_state( self, trans, state ):
        fake_agent = Bunch( inputs=self.get_runtime_inputs() )
        return state.encode( fake_agent, trans.app )

    def decode_runtime_state( self, trans, string ):
        fake_agent = Bunch( inputs=self.get_runtime_inputs() )
        state = galaxy.agents.DefaultAgentState()
        if string:
            state.decode( string, fake_agent, trans.app )
        return state

    def update_runtime_state( self, trans, state, values ):
        errors = {}
        for name, param in self.get_runtime_inputs().iteritems():
            value, error = check_param( trans, param, values.get( name, None ), values )
            state.inputs[ name ] = value
            if error:
                errors[ name ] = error
        return errors

    def compute_runtime_state( self, trans, step_updates=None, source="html" ):
        if step_updates and "agent_state" in step_updates:
            # Fix this for multiple inputs
            state = self.decode_runtime_state( trans, step_updates.pop( "agent_state" ) )
            step_errors = self.update_runtime_state( trans, state, step_updates )
        else:
            state = self.get_runtime_state()
            step_errors = {}

        return state, step_errors

    def recover_state( self, state, **kwds ):
        """ Recover state `dict` from simple dictionary describing configuration
        state (potentially from persisted step state).

        Sub-classes should supply `default_state` method and `state_fields`
        attribute which are used to build up the state `dict`.
        """
        self.state = self.default_state()
        for key in self.state_fields:
            if state and key in state:
                self.state[ key ] = state[ key ]

    def get_config_form( self ):
        form = self._abstract_config_form( )
        return self.trans.fill_template( "workflow/editor_generic_form.mako",
                                         module=self, form=form )


class SubWorkflowModule( WorkflowModule ):
    state_fields = [ ]
    type = "subworkflow"
    name = "Subworkflow"
    default_name = "Subworkflow"

    @classmethod
    def new( Class, trans, content_id=None ):
        module = Class( trans )
        module.subworkflow = SubWorkflowModule.subworkflow_from_content_id( trans, content_id )
        module.label = None
        return module

    @classmethod
    def from_dict( Class, trans, d, secure=True ):
        module = Class( trans )
        if "subworkflow" in d:
            module.subworkflow = d["subworkflow"]
        elif "content_id" in d:
            content_id = d["content_id"]
            module.subworkflow = SubWorkflowModule.subworkflow_from_content_id( trans, content_id )
        module.label = d.get("label", None) or None
        return module

    @classmethod
    def from_workflow_step( Class, trans, step ):
        module = Class( trans )
        module.subworkflow = step.subworkflow
        module.label = step.label
        return module

    def save_to_step( self, step ):
        step.type = self.type
        step.subworkflow = self.subworkflow

    @classmethod
    def default_state( Class ):
        return dict( )

    def get_name( self ):
        if hasattr( self, 'subworkflow' ) and hasattr( self.subworkflow, 'name' ):
            return self.subworkflow.name
        return self.name

    def get_errors( self ):
        return None

    def get_data_inputs( self ):
        """ Get configure time data input descriptions. """
        # Filter subworkflow steps and get inputs
        step_to_input_type = {
            "data_input": "dataset",
            "data_collection_input": "dataset_collection",
        }
        inputs = []
        for step in self.subworkflow.input_steps:
            name = step.label
            if name is None:
                # trans shouldn't really be needed for data inputs...
                step_module = module_factory.from_workflow_step(self.trans, step)
                name = step_module.get_runtime_input_dicts(None)[0]["name"]

            if not name:
                raise Exception("Failed to find name for workflow module.")
            step_type = step.type
            assert step_type in step_to_input_type
            input = dict(
                input_subworkflow_step_id=step.order_index,
                name=name,
                label=name,
                multiple=False,
                extensions="input",
                input_type=step_to_input_type[step_type],
            )
            inputs.append(input)

        return inputs

    def get_data_outputs( self ):
        outputs = []
        for workflow_output in self.subworkflow.workflow_outputs:
            output_step = workflow_output.workflow_step
            label = name = workflow_output.label
            if name is None:
                name = "%s:%s" % (output_step.order_index, workflow_output.output_name)
                label = name
            output = dict(
                name=name,
                label=label,
                extensions=['input'],  # TODO
            )
            outputs.append(output)
        return outputs

    def get_runtime_input_dicts( self, step_annotation ):
        """ Get runtime inputs (inputs and parameters) as simple dictionary. """
        return []

    def get_content_id( self ):
        return self.trans.security.encode_id(self.subworkflow.id)

    def recover_runtime_state( self, runtime_state ):
        """ Take secure runtime state from persisted invocation and convert it
        into a DefaultAgentState object for use during workflow invocation.
        """
        fake_agent = Bunch( inputs=self.get_runtime_inputs() )
        state = galaxy.agents.DefaultAgentState()
        state.decode( runtime_state, fake_agent, self.trans.app, secure=False )
        return state

    def normalize_runtime_state( self, runtime_state ):
        fake_agent = Bunch( inputs=self.get_runtime_inputs() )
        return runtime_state.encode( fake_agent, self.trans.app, secure=False )

    def encode_runtime_state( self, trans, state ):
        fake_agent = Bunch( inputs=self.get_runtime_inputs() )
        return state.encode( fake_agent, trans.app )

    def decode_runtime_state( self, trans, string ):
        fake_agent = Bunch( inputs=self.get_runtime_inputs() )
        state = galaxy.agents.DefaultAgentState()
        if string:
            state.decode( string, fake_agent, trans.app )
        return state

    def update_runtime_state( self, trans, state, values ):
        errors = {}
        for name, param in self.get_runtime_inputs().iteritems():
            value, error = check_param( trans, param, values.get( name, None ), values )
            state.inputs[ name ] = value
            if error:
                errors[ name ] = error
        return errors

    def compute_runtime_state( self, trans, step_updates=None, source="html" ):
        state = self.get_runtime_state()
        step_errors = {}
        return state, step_errors

    def recover_state( self, state, **kwds ):
        """ Recover state `dict` from simple dictionary describing configuration
        state (potentially from persisted step state).

        Sub-classes should supply `default_state` method and `state_fields`
        attribute which are used to build up the state `dict`.
        """
        self.state = self.default_state()
        for key in self.state_fields:
            if state and key in state:
                self.state[ key ] = state[ key ]

    def get_config_form( self ):
        form = self._abstract_config_form( )
        return self.trans.fill_template( "workflow/editor_generic_form.mako",
                                         module=self, form=form )

    def _abstract_config_form( self ):
        form = formbuilder.FormBuilder( title=self.get_name() )
        return form

    def check_and_update_state( self ):
        """
        If the state is not in sync with the current implementation of the
        module, try to update. Returns a list of messages to be displayed
        """
        return None

    def add_dummy_datasets( self, connections=None):
        # Replaced connected inputs with DummyDataset values.
        return None

    def get_runtime_inputs( self, **kwds ):
        # Two step improvements to this...
        # - First pass verify nested workflow doesn't have an RuntimeInputs
        # - Second pass actually turn RuntimeInputs into inputs here if possible.
        return {}

    def execute( self, trans, progress, invocation, step ):
        """ Execute the given workflow step in the given workflow invocation.
        Use the supplied workflow progress object to track outputs, find
        inputs, etc...
        """
        subworkflow_invoker = progress.subworkflow_invoker( trans, step )
        subworkflow_invoker.invoke()
        subworkflow = subworkflow_invoker.workflow
        subworkflow_progress = subworkflow_invoker.progress
        outputs = {}
        for workflow_output in subworkflow.workflow_outputs:
            workflow_output_label = workflow_output.label
            replacement = subworkflow_progress.get_replacement_workflow_output( workflow_output )
            outputs[ workflow_output_label ] = replacement

        progress.set_step_outputs( step, outputs )
        return None

    def recover_mapping( self, step, step_invocations, progress ):
        """ Re-populate progress object with information about connections
        from previously executed steps recorded via step_invocations.
        """
        raise TypeError( "Abstract method" )

    def get_runtime_state( self ):
        state = galaxy.agents.DefaultAgentState()
        state.inputs = dict( )
        return state

    @classmethod
    def subworkflow_from_content_id(clazz, trans, content_id):
        from galaxy.managers.workflows import WorkflowsManager
        workflow_manager = WorkflowsManager(trans.app)
        subworkflow = workflow_manager.get_owned_workflow( trans, content_id )
        return subworkflow


class InputModule( SimpleWorkflowModule ):

    def get_runtime_state( self ):
        state = galaxy.agents.DefaultAgentState()
        state.inputs = dict( input=None )
        return state

    def get_runtime_input_dicts( self, step_annotation ):
        name = self.state.get( "name", self.default_name )
        return [ dict( name=name, description=step_annotation ) ]

    def get_data_inputs( self ):
        return []

    def execute( self, trans, progress, invocation, step ):
        job, step_outputs = None, dict( output=step.state.inputs['input'])

        # Web controller may set copy_inputs_to_history, API controller always sets
        # inputs.
        if invocation.copy_inputs_to_history:
            for input_dataset_hda in step_outputs.values():
                content_type = input_dataset_hda.history_content_type
                if content_type == "dataset":
                    new_hda = input_dataset_hda.copy( copy_children=True )
                    invocation.history.add_dataset( new_hda )
                    step_outputs[ 'input_ds_copy' ] = new_hda
                elif content_type == "dataset_collection":
                    new_hdca = input_dataset_hda.copy()
                    invocation.history.add_dataset_collection( new_hdca )
                    step_outputs[ 'input_ds_copy' ] = new_hdca
                else:
                    raise Exception("Unknown history content encountered")
        # If coming from UI - we haven't registered invocation inputs yet,
        # so do that now so dependent steps can be recalculated. In the future
        # everything should come in from the API and this can be eliminated.
        if not invocation.has_input_for_step( step.id ):
            content = step_outputs.values()[ 0 ]
            if content:
                invocation.add_input( content, step.id )
        progress.set_outputs_for_input( step, step_outputs )
        return job

    def recover_mapping( self, step, step_invocations, progress ):
        progress.set_outputs_for_input( step )


class InputDataModule( InputModule ):
    type = "data_input"
    name = "Input dataset"
    default_name = "Input Dataset"
    state_fields = [ "name" ]

    @classmethod
    def default_state( Class ):
        return dict( name=Class.default_name )

    def _abstract_config_form( self ):
        form = formbuilder.FormBuilder( title=self.name ) \
            .add_text( "name", "Name", value=self.state['name'] )
        return form

    def get_data_outputs( self ):
        return [ dict( name='output', extensions=['input'] ) ]

    def get_runtime_inputs( self, filter_set=['data'] ):
        label = self.state.get( "name", "Input Dataset" )
        return dict( input=DataAgentParameter( None, Element( "param", name="input", label=label, multiple=True, type="data", format=', '.join(filter_set) ), self.trans ) )


class InputDataCollectionModule( InputModule ):
    default_name = "Input Dataset Collection"
    default_collection_type = "list"
    type = "data_collection_input"
    name = "Input dataset collection"
    collection_type = default_collection_type
    state_fields = [ "name", "collection_type" ]

    @classmethod
    def default_state( Class ):
        return dict( name=Class.default_name, collection_type=Class.default_collection_type )

    def get_runtime_inputs( self, filter_set=['data'] ):
        label = self.state.get( "name", self.default_name )
        collection_type = self.state.get( "collection_type", self.default_collection_type )
        input_element = Element( "param", name="input", label=label, type="data_collection", collection_type=collection_type )
        return dict( input=DataCollectionAgentParameter( None, input_element, self.trans ) )

    def _abstract_config_form( self ):
        type_hints = odict.odict()
        type_hints[ "list" ] = "List of Datasets"
        type_hints[ "paired" ] = "Dataset Pair"
        type_hints[ "list:paired" ] = "List of Dataset Pairs"

        type_input = formbuilder.DatalistInput(
            name="collection_type",
            label="Collection Type",
            value=self.state[ "collection_type" ],
            extra_attributes=dict(refresh_on_change='true'),
            options=type_hints
        )
        form = formbuilder.FormBuilder(
            title=self.name
        ).add_text(
            "name", "Name", value=self.state['name']
        )
        form.inputs.append( type_input )
        return form

    def get_data_outputs( self ):
        return [
            dict(
                name='output',
                extensions=['input_collection'],
                collection=True,
                collection_type=self.state[ 'collection_type' ]
            )
        ]


class InputParameterModule( SimpleWorkflowModule ):
    default_name = "input_parameter"
    default_parameter_type = "text"
    default_optional = False
    type = "parameter_input"
    name = default_name
    parameter_type = default_parameter_type
    optional = default_optional
    state_fields = [
        "name",
        "parameter_type",
        "optional",
    ]

    @classmethod
    def default_state( Class ):
        return dict(
            name=Class.default_name,
            parameter_type=Class.default_parameter_type,
            optional=Class.default_optional,
        )

    def _abstract_config_form( self ):
        form = formbuilder.FormBuilder(
            title=self.name
        ).add_text(
            "name", "Name", value=self.state['name']
        ).add_select(
            "parameter_type", "Parameter Type", value=self.state['parameter_type'],
            options=[
                ('text', "Text"),
                ('integer', "Integer"),
                ('float', "Float"),
                ('boolean', "Boolean (True or False)"),
                ('color', "Color"),
            ]
        ).add_checkbox(
            "optional", "Optional", value=self.state['optional']
        )

        return form

    def get_runtime_inputs( self, **kwds ):
        label = self.state.get( "name", self.default_name )
        parameter_type = self.state.get("parameter_type", self.default_parameter_type)
        optional = self.state.get("optional", self.default_optional)
        if parameter_type not in ["text", "boolean", "integer", "float", "color"]:
            raise ValueError("Invalid parameter type for workflow parameters encountered.")
        parameter_class = parameter_types[parameter_type]
        parameter_kwds = {}
        if parameter_type in ["integer", "float"]:
            parameter_kwds["value"] = str(0)

        # TODO: Use a dict-based description from YAML agent source
        element = Element("param", name="input", label=label, type=parameter_type, optional=str(optional), **parameter_kwds )
        input = parameter_class( None, element )
        return dict( input=input )

    def get_runtime_state( self ):
        state = galaxy.agents.DefaultAgentState()
        state.inputs = dict( input=None )
        return state

    def get_runtime_input_dicts( self, step_annotation ):
        name = self.state.get( "name", self.default_name )
        return [ dict( name=name, description=step_annotation ) ]

    def get_data_inputs( self ):
        return []

    def execute( self, trans, progress, invocation, step ):
        job, step_outputs = None, dict( output=step.state.inputs['input'])
        progress.set_outputs_for_input( step, step_outputs )
        return job


class PauseModule( SimpleWorkflowModule ):
    """ Initially this module will unconditionally pause a workflow - will aim
    to allow conditional pausing later on.
    """
    type = "pause"
    name = "Pause for dataset review"
    default_name = "Pause for Dataset Review"
    state_fields = [ "name" ]

    @classmethod
    def default_state( Class ):
        return dict( name=Class.default_name )

    def get_data_inputs( self ):
        input = dict(
            name="input",
            label="Dataset for Review",
            multiple=False,
            extensions='input',
            input_type="dataset",
        )
        return [ input ]

    def get_data_outputs( self ):
        return [ dict( name="output", label="Reviewed Dataset", extensions=['input'] ) ]

    def _abstract_config_form( self ):
        form = formbuilder.FormBuilder(
            title=self.name
        ).add_text( "name", "Name", value=self.state['name'] )
        return form

    def get_runtime_inputs( self, **kwds ):
        return dict( )

    def get_runtime_input_dicts( self, step_annotation ):
        return []

    def get_runtime_state( self ):
        state = galaxy.agents.DefaultAgentState()
        state.inputs = dict( )
        return state

    def execute( self, trans, progress, invocation, step ):
        progress.mark_step_outputs_delayed( step )
        return None

    def recover_mapping( self, step, step_invocations, progress ):
        if step_invocations:
            step_invocation = step_invocations[0]
            action = step_invocation.action
            if action:
                connection = step.input_connections_by_name[ "input" ][ 0 ]
                replacement = progress.replacement_for_connection( connection )
                progress.set_step_outputs( step, { 'output': replacement } )
                return
            elif action is False:
                raise CancelWorkflowEvaluation()
        raise DelayedWorkflowEvaluation()

    def do_invocation_step_action( self, step, action ):
        """ Update or set the workflow invocation state action - generic
        extension point meant to allows users to interact with interactive
        workflow modules. The action object returned from this method will
        be attached to the WorkflowInvocationStep and be available the next
        time the workflow scheduler visits the workflow.
        """
        return bool( action )


class AgentModule( WorkflowModule ):

    type = "agent"

    def __init__( self, trans, agent_id, agent_version=None ):
        self.trans = trans
        self.agent_id = agent_id
        self.agent = trans.app.agentbox.get_agent( agent_id, agent_version=agent_version )
        self.post_job_actions = {}
        self.runtime_post_job_actions = {}
        self.workflow_outputs = []
        self.state = None
        self.version_changes = []
        if self.agent:
            self.errors = None
        else:
            self.errors = {}
            self.errors[ agent_id ] = 'Agent unavailable'

    @classmethod
    def new( Class, trans, content_id=None ):
        module = Class( trans, content_id )
        if module.agent is None:
            error_message = "Attempted to create new workflow module for invalid agent_id, no agent with id - %s." % content_id
            raise Exception( error_message )
        module.state = module.agent.new_state( trans )
        module.label = None
        return module

    @classmethod
    def from_dict( Class, trans, d, secure=True ):
        agent_id = d.get( 'content_id', None )
        if agent_id is None:
            agent_id = d.get( 'agent_id', None )  # Older workflows will have exported this as agent_id.
        agent_version = str( d.get( 'agent_version', None ) )
        module = Class( trans, agent_id, agent_version=agent_version )
        module.state = galaxy.agents.DefaultAgentState()
        module.label = d.get("label", None) or None
        if module.agent is not None:
            message = ""
            if agent_id != module.agent_id:
                message += "The agent (id '%s') specified in this step is not available. Using the agent with id %s instead." % (agent_id, module.agent_id)
            if d.get('agent_version', 'Unspecified') != module.get_agent_version():
                message += "%s: using version '%s' instead of version '%s' specified in this workflow." % ( agent_id, d.get( 'agent_version', 'Unspecified' ), module.get_agent_version() )
            if message:
                log.debug(message)
                module.version_changes.append(message)
            if d[ "agent_state" ]:
                module.state.decode( d[ "agent_state" ], module.agent, module.trans.app, secure=secure )
        module.errors = d.get( "agent_errors", None )
        module.post_job_actions = d.get( "post_job_actions", {} )
        module.workflow_outputs = d.get( "workflow_outputs", [] )
        return module

    @classmethod
    def from_workflow_step( Class, trans, step ):
        agentbox = trans.app.agentbox
        agent_id = step.agent_id
        if agentbox:
            # See if we have access to a different version of the agent.
            # TODO: If workflows are ever enhanced to use agent version
            # in addition to agent id, enhance the selection process here
            # to retrieve the correct version of the agent.
            agent_id = agentbox.get_agent_id( agent_id )
        if ( agentbox and agent_id ):
            if step.config:
                # This step has its state saved in the config field due to the
                # agent being previously unavailable.
                return module_factory.from_dict(trans, loads(step.config), secure=False)
            agent_version = step.agent_version
            module = Class( trans, agent_id, agent_version=agent_version )
            message = ""
            if step.agent_id != module.agent_id:  # This means the exact version of the agent is not installed. We inform the user.
                old_agent_shed = step.agent_id.split( "/repos/" )[0]
                if old_agent_shed not in agent_id:  # Only display the following warning if the agent comes from a different agent shed
                    old_agent_shed_url = common_util.get_agent_shed_url_from_agent_shed_registry( trans.app, old_agent_shed )
                    old_url = old_agent_shed_url + "/view/%s/%s/" % (module.agent.repository_owner, module.agent.repository_name)
                    new_url = module.agent.agent_shed_repository.get_sharable_url( module.agent.app ) + '/%s/' % module.agent.agent_shed_repository.changeset_revision
                    new_agent_shed_url = new_url.split( "/view" )[0]
                    message += "The agent \'%s\', version %s by the owner %s installed from <a href=\"%s\" target=\"_blank\">%s</a> is not available. " % (module.agent.name, agent_version, module.agent.repository_owner, old_url, old_agent_shed_url)
                    message += "A derivation of this agent installed from <a href=\"%s\" target=\"_blank\">%s</a> will be used instead. " % (new_url, new_agent_shed_url)
            if step.agent_version and (step.agent_version != module.agent.version):
                message += "<span title=\"agent id '%s'\">Using version '%s' instead of version '%s' specified in this workflow. " % (agent_id, module.agent.version, step.agent_version)
            if message:
                log.debug(message)
                module.version_changes.append(message)
            module.recover_state( step.agent_inputs )
            module.errors = step.agent_errors
            module.workflow_outputs = step.workflow_outputs
            module.label = step.label or None
            pjadict = {}
            for pja in step.post_job_actions:
                pjadict[pja.action_type] = pja
            module.post_job_actions = pjadict
            return module
        return None

    def recover_state( self, state, **kwds ):
        """ Recover module configuration state property (a `DefaultAgentState`
        object) using the agent's `params_from_strings` method.
        """
        app = self.trans.app
        self.state = galaxy.agents.DefaultAgentState()
        params_from_kwds = dict(
            ignore_errors=kwds.get( "ignore_errors", True )
        )
        self.state.inputs = self.agent.params_from_strings( state, app, **params_from_kwds )

    def recover_runtime_state( self, runtime_state ):
        """ Take secure runtime state from persisted invocation and convert it
        into a DefaultAgentState object for use during workflow invocation.
        """
        state = galaxy.agents.DefaultAgentState()
        app = self.trans.app
        state.decode( runtime_state, self.agent, app, secure=False )
        state_dict = loads( runtime_state )
        if RUNTIME_STEP_META_STATE_KEY in state_dict:
            self.__restore_step_meta_runtime_state( loads( state_dict[ RUNTIME_STEP_META_STATE_KEY ] ) )
        return state

    def normalize_runtime_state( self, runtime_state ):
        return runtime_state.encode( self.agent, self.trans.app, secure=False )

    def save_to_step( self, step ):
        step.type = self.type
        step.agent_id = self.agent_id
        if self.agent:
            step.agent_version = self.get_agent_version()
            step.agent_inputs = self.agent.params_to_strings( self.state.inputs, self.trans.app )
        else:
            step.agent_version = None
            step.agent_inputs = None
        step.agent_errors = self.errors
        for k, v in self.post_job_actions.iteritems():
            pja = self.__to_pja( k, v, step )
            self.trans.sa_session.add( pja )

    def __to_pja( self, key, value, step ):
        if 'output_name' in value:
            output_name = value['output_name']
        else:
            output_name = None
        if 'action_arguments' in value:
            action_arguments = value['action_arguments']
        else:
            action_arguments = None
        return PostJobAction(value['action_type'], step, output_name, action_arguments)

    def get_name( self ):
        if self.agent:
            return self.agent.name
        return 'unavailable'

    def get_content_id( self ):
        return self.agent_id

    def get_agent_version( self ):
        return self.agent.version

    def get_state( self, secure=True ):
        return self.state.encode( self.agent, self.trans.app, secure=secure )

    def get_errors( self ):
        return self.errors

    def get_agenttip( self, static_path='' ):
        if self.agent.help:
            return self.agent.help.render( host_url=web.url_for('/'), static_path=static_path )
        else:
            return None

    def get_data_inputs( self ):
        data_inputs = []

        def callback( input, value, prefixed_name, prefixed_label ):
            if isinstance( input, DataAgentParameter ):
                data_inputs.append( dict(
                    name=prefixed_name,
                    label=prefixed_label,
                    multiple=input.multiple,
                    extensions=input.extensions,
                    input_type="dataset", ) )
            if isinstance( input, DataCollectionAgentParameter ):
                data_inputs.append( dict(
                    name=prefixed_name,
                    label=prefixed_label,
                    multiple=input.multiple,
                    input_type="dataset_collection",
                    collection_types=input.collection_types,
                    extensions=input.extensions,
                ) )

        visit_input_values( self.agent.inputs, self.state.inputs, callback )
        return data_inputs

    def get_data_outputs( self ):
        data_outputs = []
        data_inputs = None
        for name, agent_output in self.agent.outputs.iteritems():
            extra_kwds = {}
            if agent_output.collection:
                extra_kwds["collection"] = True
                extra_kwds["collection_type"] = agent_output.structure.collection_type
                formats = [ 'input' ]  # TODO: fix
            elif agent_output.format_source is not None:
                formats = [ 'input' ]  # default to special name "input" which remove restrictions on connections
                if data_inputs is None:
                    data_inputs = self.get_data_inputs()
                # find the input parameter referenced by format_source
                for di in data_inputs:
                    # input names come prefixed with conditional and repeat names separated by '|'
                    # remove prefixes when comparing with format_source
                    if di['name'] is not None and di['name'].split('|')[-1] == agent_output.format_source:
                        formats = di['extensions']
            else:
                formats = [ agent_output.format ]
            for change_elem in agent_output.change_format:
                for when_elem in change_elem.findall( 'when' ):
                    format = when_elem.get( 'format', None )
                    if format and format not in formats:
                        formats.append( format )
            data_outputs.append(
                dict(
                    name=name,
                    extensions=formats,
                    **extra_kwds
                )
            )
        return data_outputs

    def get_runtime_input_dicts( self, step_annotation ):
        # Step is a agent and may have runtime inputs.
        input_dicts = []
        for name, val in self.state.inputs.items():
            input_type = type( val )
            if input_type == RuntimeValue:
                input_dicts.append( { "name": name, "description": "runtime parameter for agent %s" % self.get_name() } )
            elif input_type == dict:
                # Input type is described by a dict, e.g. indexed parameters.
                for partval in val.values():
                    if type( partval ) == RuntimeValue:
                        input_dicts.append( { "name": name, "description": "runtime parameter for agent %s" % self.get_name() } )
        return input_dicts

    def get_post_job_actions( self, incoming=None):
        if incoming is None:
            return self.post_job_actions
        else:
            return ActionBox.handle_incoming(incoming)

    def get_config_form( self ):
        self.add_dummy_datasets()
        return self.trans.fill_template( "workflow/editor_agent_form.mako", module=self,
                                         agent=self.agent, values=self.state.inputs, errors=( self.errors or {} ) )

    def encode_runtime_state( self, trans, state ):
        encoded = state.encode( self.agent, self.trans.app )
        return encoded

    def update_state( self, incoming ):
        # Build a callback that handles setting an input to be required at
        # runtime. We still process all other parameters the user might have
        # set. We also need to make sure all datasets have a dummy value
        # for dependencies to see

        self.label = incoming.get("label", None) or None
        self.post_job_actions = ActionBox.handle_incoming(incoming)

        make_runtime_key = incoming.get( 'make_runtime', None )
        make_buildtime_key = incoming.get( 'make_buildtime', None )

        def item_callback( trans, key, input, value, error, old_value, context ):
            # Dummy value for Data parameters
            if isinstance( input, DataAgentParameter ) or isinstance( input, DataCollectionAgentParameter ):
                return DummyDataset(), None
            # Deal with build/runtime (does not apply to Data parameters)
            if key == make_buildtime_key:
                return input.get_initial_value( trans, context ), None
            elif isinstance( old_value, RuntimeValue ):
                return old_value, None
            elif key == make_runtime_key:
                return RuntimeValue(), None
            elif isinstance(value, basestring) and re.search("\$\{.+?\}", str(value)):
                # Workflow Parameter Replacement, so suppress error from going to the workflow level.
                return value, None
            else:
                return value, error

        # Update state using incoming values
        errors = self.agent.update_state( self.trans, self.agent.inputs, self.state.inputs, incoming, item_callback=item_callback )
        self.errors = errors or None

    def check_and_update_state( self ):
        inputs = self.state.inputs
        return self.agent.check_and_update_param_values( inputs, self.trans, allow_workflow_parameters=True )

    def compute_runtime_state( self, trans, step_updates=None, source="html" ):
        # Warning: This method destructively modifies existing step state.
        step_errors = None
        state = self.state
        self.runtime_post_job_actions = {}
        if step_updates:
            # Get the agent
            agent = self.agent
            # Get old errors
            old_errors = state.inputs.pop( "__errors__", {} )
            # Update the state
            self.runtime_post_job_actions = step_updates.get(RUNTIME_POST_JOB_ACTIONS_KEY, {})
            step_errors = agent.update_state( trans, agent.inputs, state.inputs, step_updates,
                                             update_only=True, old_errors=old_errors, source=source )
            step_metadata_runtime_state = self.__step_meta_runtime_state()
            if step_metadata_runtime_state:
                state.inputs[ RUNTIME_STEP_META_STATE_KEY ] = step_metadata_runtime_state
        return state, step_errors

    def __step_meta_runtime_state( self ):
        """ Build a dictionary a of meta-step runtime state (state about how
        the workflow step - not the agent state) to be serialized with the Agent
        state.
        """
        return { RUNTIME_POST_JOB_ACTIONS_KEY: self.runtime_post_job_actions }

    def __restore_step_meta_runtime_state( self, step_runtime_state ):
        if RUNTIME_POST_JOB_ACTIONS_KEY in step_runtime_state:
            self.runtime_post_job_actions = step_runtime_state[ RUNTIME_POST_JOB_ACTIONS_KEY ]

    def execute( self, trans, progress, invocation, step ):
        agent = trans.app.agentbox.get_agent( step.agent_id, agent_version=step.agent_version )
        agent_state = step.state
        # Not strictly needed - but keep Agent state clean by stripping runtime
        # metadata parameters from it.
        if RUNTIME_STEP_META_STATE_KEY in agent_state.inputs:
            del agent_state.inputs[ RUNTIME_STEP_META_STATE_KEY ]
        collections_to_match = self._find_collections_to_match( agent, progress, step )
        # Have implicit collections...
        if collections_to_match.has_collections():
            collection_info = self.trans.app.dataset_collections_service.match_collections( collections_to_match )
        else:
            collection_info = None

        param_combinations = []
        if collection_info:
            iteration_elements_iter = collection_info.slice_collections()
        else:
            iteration_elements_iter = [ None ]

        for iteration_elements in iteration_elements_iter:
            execution_state = agent_state.copy()
            # TODO: Move next step into copy()
            execution_state.inputs = make_dict_copy( execution_state.inputs )

            # Connect up
            def callback( input, value, prefixed_name, prefixed_label ):
                replacement = NO_REPLACEMENT
                if isinstance( input, DataAgentParameter ) or isinstance( input, DataCollectionAgentParameter ):
                    if iteration_elements and prefixed_name in iteration_elements:
                        if isinstance( input, DataAgentParameter ):
                            # Pull out dataset instance from element.
                            replacement = iteration_elements[ prefixed_name ].dataset_instance
                        else:
                            # If collection - just use element model object.
                            replacement = iteration_elements[ prefixed_name ]
                    else:
                        replacement = progress.replacement_for_agent_input( step, input, prefixed_name )
                else:
                    replacement = progress.replacement_for_agent_input( step, input, prefixed_name )
                return replacement

            try:
                # Replace DummyDatasets with historydatasetassociations
                visit_input_values( agent.inputs, execution_state.inputs, callback, no_replacement_value=NO_REPLACEMENT )
            except KeyError, k:
                message_template = "Error due to input mapping of '%s' in '%s'.  A common cause of this is conditional outputs that cannot be determined until runtime, please review your workflow."
                message = message_template % (agent.name, k.message)
                raise exceptions.MessageException( message )
            param_combinations.append( execution_state.inputs )

        execution_tracker = execute(
            trans=self.trans,
            agent=agent,
            param_combinations=param_combinations,
            history=invocation.history,
            collection_info=collection_info,
            workflow_invocation_uuid=invocation.uuid.hex
        )
        if collection_info:
            step_outputs = dict( execution_tracker.implicit_collections )
        else:
            step_outputs = dict( execution_tracker.output_datasets )
            step_outputs.update( execution_tracker.output_collections )
        progress.set_step_outputs( step, step_outputs )
        jobs = execution_tracker.successful_jobs
        for job in jobs:
            self._handle_post_job_actions( step, job, invocation.replacement_dict )
        if execution_tracker.execution_errors:
            failed_count = len(execution_tracker.execution_errors)
            success_count = len(execution_tracker.successful_jobs)
            all_count = failed_count + success_count
            message = "Failed to create %d out of %s job(s) for workflow step." % (failed_count, all_count)
            raise Exception(message)
        return jobs

    def _find_collections_to_match( self, agent, progress, step ):
        collections_to_match = matching.CollectionsToMatch()

        def callback( input, value, prefixed_name, prefixed_label ):
            is_data_param = isinstance( input, DataAgentParameter )
            if is_data_param and not input.multiple:
                data = progress.replacement_for_agent_input( step, input, prefixed_name )
                if isinstance( data, model.HistoryDatasetCollectionAssociation ):
                    collections_to_match.add( prefixed_name, data )

            is_data_collection_param = isinstance( input, DataCollectionAgentParameter )
            if is_data_collection_param and not input.multiple:
                data = progress.replacement_for_agent_input( step, input, prefixed_name )
                history_query = input._history_query( self.trans )
                subcollection_type_description = history_query.can_map_over( data )
                if subcollection_type_description:
                    collections_to_match.add( prefixed_name, data, subcollection_type=subcollection_type_description.collection_type )

        visit_input_values( agent.inputs, step.state.inputs, callback )
        return collections_to_match

    def _handle_post_job_actions( self, step, job, replacement_dict ):
        # Create new PJA associations with the created job, to be run on completion.
        # PJA Parameter Replacement (only applies to immediate actions-- rename specifically, for now)
        # Pass along replacement dict with the execution of the PJA so we don't have to modify the object.

        # Combine workflow and runtime post job actions into the effective post
        # job actions for this execution.
        effective_post_job_actions = step.post_job_actions[:]
        for key, value in self.runtime_post_job_actions.iteritems():
            effective_post_job_actions.append( self.__to_pja( key, value, None ) )
        for pja in effective_post_job_actions:
            if pja.action_type in ActionBox.immediate_actions:
                ActionBox.execute( self.trans.app, self.trans.sa_session, pja, job, replacement_dict )
            else:
                job.add_post_job_action( pja )

    def add_dummy_datasets( self, connections=None):
        if connections:
            # Store onnections by input name
            input_connections_by_name = \
                dict( ( conn.input_name, conn ) for conn in connections )
        else:
            input_connections_by_name = {}
        # Any connected input needs to have value DummyDataset (these
        # are not persisted so we need to do it every time)

        def callback( input, value, prefixed_name, prefixed_label ):
            replacement = None
            if isinstance( input, DataAgentParameter ):
                if connections is None or prefixed_name in input_connections_by_name:
                    if input.multiple:
                        replacement = [] if not connections else [DummyDataset() for conn in connections]
                    else:
                        replacement = DummyDataset()
            elif isinstance( input, DataCollectionAgentParameter ):
                if connections is None or prefixed_name in input_connections_by_name:
                    replacement = DummyDataset()
            return replacement

        visit_input_values( self.agent.inputs, self.state.inputs, callback )

    def recover_mapping( self, step, step_invocations, progress ):
        # Grab a job representing this invocation - for normal workflows
        # there will be just one job but if this step was mapped over there
        # may be many.
        job_0 = step_invocations[ 0 ].job

        outputs = {}
        for job_output in job_0.output_datasets:
            replacement_name = job_output.name
            replacement_value = job_output.dataset
            # If was a mapping step, grab the output mapped collection for
            # replacement instead.
            if replacement_value.hidden_beneath_collection_instance:
                replacement_value = replacement_value.hidden_beneath_collection_instance
            outputs[ replacement_name ] = replacement_value
        for job_output_collection in job_0.output_dataset_collection_instances:
            replacement_name = job_output_collection.name
            replacement_value = job_output_collection.dataset_collection_instance
            outputs[ replacement_name ] = replacement_value

        progress.set_step_outputs( step, outputs )


class WorkflowModuleFactory( object ):

    def __init__( self, module_types ):
        self.module_types = module_types

    def new( self, trans, type, content_id=None ):
        """
        Return module for type and (optional) agent_id intialized with
        new / default state.
        """
        assert type in self.module_types
        return self.module_types[type].new( trans, content_id )

    def from_dict( self, trans, d, **kwargs ):
        """
        Return module initialized from the data in dictionary `d`.
        """
        type = d['type']
        assert type in self.module_types
        return self.module_types[type].from_dict( trans, d, **kwargs )

    def from_workflow_step( self, trans, step ):
        """
        Return module initializd from the WorkflowStep object `step`.
        """
        type = step.type
        return self.module_types[type].from_workflow_step( trans, step )


def is_agent_module_type( module_type ):
    return not module_type or module_type == "agent"


module_types = dict(
    data_input=InputDataModule,
    data_collection_input=InputDataCollectionModule,
    parameter_input=InputParameterModule,
    pause=PauseModule,
    agent=AgentModule,
    subworkflow=SubWorkflowModule,
)
module_factory = WorkflowModuleFactory( module_types )


def load_module_sections( trans ):
    """ Get abstract description of the workflow modules this Galaxy instance
    is configured with.
    """
    module_sections = {}
    module_sections['inputs'] = {
        "name": "inputs",
        "title": "Inputs",
        "modules": [
            {
                "name": "data_input",
                "title": "Input Dataset",
                "description": "Input dataset"
            },
            {
                "name": "data_collection_input",
                "title": "Input Dataset Collection",
                "description": "Input dataset collection"
            },
        ],
    }

    if trans.app.config.enable_beta_workflow_modules:
        module_sections['experimental'] = {
            "name": "experimental",
            "title": "Experimental",
            "modules": [
                {
                    "name": "pause",
                    "title": "Pause Workflow for Dataset Review",
                    "description": "Pause for Review"
                },
                {
                    "name": "parameter_input",
                    "title": "Parameter Input",
                    "description": "Simple inputs used for workflow logic"
                },
            ],
        }

    return module_sections


class MissingAgentException( Exception ):
    """ WorkflowModuleInjector will raise this if the agent corresponding to the
    module is missing. """


class DelayedWorkflowEvaluation(Exception):
    pass


class CancelWorkflowEvaluation(Exception):
    pass


class WorkflowModuleInjector(object):
    """ Injects workflow step objects from the ORM with appropriate module and
    module generated/influenced state. """

    def __init__( self, trans, allow_agent_state_corrections=False ):
        self.trans = trans
        self.allow_agent_state_corrections = allow_agent_state_corrections

    def inject( self, step, step_args=None, source="html" ):
        """ Pre-condition: `step` is an ORM object coming from the database, if
        supplied `step_args` is the representation of the inputs for that step
        supplied via web form.

        Post-condition: The supplied `step` has new non-persistent attributes
        useful during workflow invocation. These include 'upgrade_messages',
        'state', 'input_connections_by_name', and 'module'.

        If step_args is provided from a web form this is applied to generate
        'state' else it is just obtained from the database.
        """
        trans = self.trans

        step_errors = None

        step.upgrade_messages = {}

        # Make connection information available on each step by input name.
        step.setup_input_connections_by_name()

        # Populate module.
        module = step.module = module_factory.from_workflow_step( trans, step )

        if not module:
            step.module = None
            step.state = None
            raise MissingAgentException(step.agent_id)

        # Fix any missing parameters
        step.upgrade_messages = module.check_and_update_state()

        # Any connected input needs to have value DummyDataset (these
        # are not persisted so we need to do it every time)
        module.add_dummy_datasets( connections=step.input_connections )

        state, step_errors = module.compute_runtime_state( trans, step_args, source=source )

        step.state = state

        if step.type == "subworkflow":
            subworkflow = step.subworkflow
            populate_module_and_state( self.trans, subworkflow, param_map={}, )

        return step_errors


def populate_module_and_state( trans, workflow, param_map, allow_agent_state_corrections=False, module_injector=None ):
    """ Used by API but not web controller, walks through a workflow's steps
    and populates transient module and state attributes on each.
    """
    if module_injector is None:
        module_injector = WorkflowModuleInjector( trans, allow_agent_state_corrections )
    for step in workflow.steps:
        step_args = param_map.get( step.id, {} )
        step_errors = module_injector.inject( step, step_args=step_args, source="json" )
        if step.type == 'agent' or step.type is None:
            if step_errors:
                message = "Workflow cannot be run because of validation errors in some steps: %s" % step_errors
                raise exceptions.MessageException( message )
            if step.upgrade_messages:
                if allow_agent_state_corrections:
                    log.debug( 'Workflow step "%i" had upgrade messages: %s', step.id, step.upgrade_messages )
                else:
                    message = "Workflow cannot be run because of step upgrade messages: %s" % step.upgrade_messages
                    raise exceptions.MessageException( message )
