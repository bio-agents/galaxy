from funcagents import partial
import yaml

from galaxy.util import bunch
from galaxy import model
from galaxy.model import mapping
from galaxy.web.security import SecurityHelper


class MockTrans( object ):

    def __init__( self ):
        self.app = TestApp()
        self.sa_session = self.app.model.context
        self._user = None

    def save_workflow(self, workflow):
        stored_workflow = model.StoredWorkflow()
        stored_workflow.latest_workflow = workflow
        stored_workflow.user = self.user
        self.sa_session.add( stored_workflow )
        self.sa_session.flush()
        return stored_workflow

    @property
    def user(self):
        if self._user is None:
            self._user = model.User(
                email="testworkflows@bx.psu.edu",
                password="password"
            )
        return self._user


class TestApp( object ):

    def __init__( self ):
        self.config = bunch.Bunch(
            agent_secret="awesome_secret",
        )
        self.model = mapping.init(
            "/tmp",
            "sqlite:///:memory:",
            create_tables=True
        )
        self.agentbox = TestAgentbox()
        self.datatypes_registry = TestDatatypesRegistry()
        self.security = SecurityHelper(id_secret="testing")


class TestDatatypesRegistry( object ):

    def __init__( self ):
        pass

    def get_datatype_by_extension( self, ext ):
        return ext


class TestAgentbox( object ):

    def __init__( self ):
        self.agents = {}

    def get_agent( self, agent_id, agent_version=None ):
        # Real agent box returns None of missing agent also
        return self.agents.get( agent_id, None )

    def get_agent_id( self, agent_id ):
        agent = self.get_agent( agent_id )
        return agent and agent.id


def yaml_to_model(has_dict, id_offset=100):
    if isinstance(has_dict, str):
        has_dict = yaml.load(has_dict)

    workflow = model.Workflow()
    workflow.steps = []
    for i, step in enumerate(has_dict.get("steps", [])):
        workflow_step = model.WorkflowStep()
        if "order_index" not in step:
            step["order_index"] = i
        if "id" not in step:
            # Fixed Offset ids just to test against assuption order_index != id
            step["id"] = id_offset
            id_offset += 1
        step_type = step.get("type", None)
        assert step_type is not None

        if step_type == "subworkflow":
            subworkflow_dict = step["subworkflow"]
            del step["subworkflow"]
            subworkflow = yaml_to_model(subworkflow_dict, id_offset=id_offset)
            step["subworkflow"] = subworkflow
            id_offset += len(subworkflow.steps)

        for key, value in step.iteritems():
            if key == "input_connections":
                connections = []
                for conn_dict in value:
                    conn = model.WorkflowStepConnection()
                    for conn_key, conn_value in conn_dict.iteritems():
                        if conn_key == "@output_step":
                            target_step = workflow.steps[conn_value]
                            conn_value = target_step
                            conn_key = "output_step"
                        if conn_key == "@input_subworkflow_step":
                            conn_value = step["subworkflow"].step_by_index(conn_value)
                            conn_key = "input_subworkflow_step"
                        setattr(conn, conn_key, conn_value)
                    connections.append(conn)
                value = connections
            if key == "workflow_outputs":
                value = map(partial(_dict_to_workflow_output, workflow_step), value)
            setattr(workflow_step, key, value)
        workflow.steps.append( workflow_step )

    return workflow


def _dict_to_workflow_output(workflow_step, as_dict):
    output = model.WorkflowOutput(workflow_step)
    for key, value in as_dict.iteritems():
        setattr(output, key, value)
    return output
