import uuid

import jobs.test_rules

from galaxy.jobs.mapper import (
    JobRunnerMapper,
    ERROR_MESSAGE_NO_RULE_FUNCTION,
    ERROR_MESSAGE_RULE_FUNCTION_NOT_FOUND,
)
from galaxy.jobs import JobDestination

from galaxy.util import bunch

WORKFLOW_UUID = uuid.uuid1().hex
TOOL_JOB_DESTINATION = JobDestination()
DYNAMICALLY_GENERATED_DESTINATION = JobDestination()


def test_static_mapping():
    mapper = __mapper()
    assert mapper.get_job_destination( {} ) is TOOL_JOB_DESTINATION


def test_caching():
    mapper = __mapper()
    mapper.get_job_destination( {} )
    mapper.get_job_destination( {} )
    assert mapper.job_wrapper.agent.call_count == 1


def test_dynamic_mapping():
    mapper = __mapper( __dynamic_destination( dict( function="upload" ) ) )
    assert mapper.get_job_destination( {} ) is DYNAMICALLY_GENERATED_DESTINATION
    assert mapper.job_config.rule_response == "local_runner"


def test_dynamic_mapping_priorities():
    mapper = __mapper( __dynamic_destination( dict( function="tophat" ) ) )
    assert mapper.get_job_destination( {} ) is DYNAMICALLY_GENERATED_DESTINATION
    # Next line verifies we using definition in 20_instance.py instead of
    # 10_site.py.
    assert mapper.job_config.rule_response == "instance_dest_id"


def test_dynamic_mapping_defaults_to_agent_id_as_rule():
    mapper = __mapper( __dynamic_destination( ) )
    assert mapper.get_job_destination( {} ) is DYNAMICALLY_GENERATED_DESTINATION
    assert mapper.job_config.rule_response == "agent1_dest_id"


def test_dynamic_mapping_job_conf_params():
    mapper = __mapper( __dynamic_destination( dict( function="check_job_conf_params", param1="7" ) ) )
    assert mapper.get_job_destination( {} ) is DYNAMICALLY_GENERATED_DESTINATION
    assert mapper.job_config.rule_response == "sent_7_dest_id"


def test_dynamic_mapping_function_parameters():
    mapper = __mapper( __dynamic_destination( dict( function="check_rule_params" ) ) )
    assert mapper.get_job_destination( {} ) is DYNAMICALLY_GENERATED_DESTINATION
    assert mapper.job_config.rule_response == "all_passed"


def test_dynamic_mapping_resource_parameters():
    mapper = __mapper( __dynamic_destination( dict( function="check_resource_params" ) ) )
    assert mapper.get_job_destination( {} ) is DYNAMICALLY_GENERATED_DESTINATION
    assert mapper.job_config.rule_response == "have_resource_params"


def test_dynamic_mapping_workflow_invocation_parameter():
    mapper = __mapper( __dynamic_destination( dict( function="check_workflow_invocation_uuid" ) ) )
    assert mapper.get_job_destination( {} ) is DYNAMICALLY_GENERATED_DESTINATION
    assert mapper.job_config.rule_response == WORKFLOW_UUID


def test_dynamic_mapping_no_function():
    dest = __dynamic_destination( dict( ) )
    mapper = __mapper( dest )
    mapper.job_wrapper.agent.all_ids = [ "no_such_function" ]
    error_message = ERROR_MESSAGE_NO_RULE_FUNCTION % dest
    __assert_mapper_errors_with_message( mapper, error_message )


def test_dynamic_mapping_missing_function():
    dest = __dynamic_destination( dict( function="missing_func" ) )
    mapper = __mapper( dest )
    mapper.job_wrapper.agent.all_ids = [ "no_such_function" ]
    error_message = ERROR_MESSAGE_RULE_FUNCTION_NOT_FOUND % ( "missing_func" )
    __assert_mapper_errors_with_message( mapper, error_message )


def __assert_mapper_errors_with_message( mapper, message ):
    exception = None
    try:
        mapper.get_job_destination( {} )
    except Exception as e:
        exception = e
    assert exception
    assert str( exception ) == message, "%s != %s" % ( str( exception ), message )


def __mapper( agent_job_destination=TOOL_JOB_DESTINATION ):
    job_wrapper = MockJobWrapper( agent_job_destination )
    job_config = MockJobConfig()

    mapper = JobRunnerMapper(
        job_wrapper,
        {},
        job_config
    )
    mapper.rules_module = jobs.test_rules
    return mapper


def __dynamic_destination( params={} ):
    return JobDestination( runner="dynamic", params=params )


class MockJobConfig( object ):

    def __init__( self ):
        self.rule_response = None
        self.dynamic_params = None

    def get_destination( self, rep ):
        # Called to transform dynamic job destination rule response
        # from destination id/runner url into a dynamic job destination.
        self.rule_response = rep
        return DYNAMICALLY_GENERATED_DESTINATION


class MockJobWrapper( object ):

    def __init__( self, agent_job_destination ):
        self.agent = MockAgent( agent_job_destination )
        self.job_id = 12345
        self.app = object()

    def is_mock_job_wrapper( self ):
        return True

    def get_job(self):
        raw_params = {
            "threshold": 8,
            "__workflow_invocation_uuid__": WORKFLOW_UUID,
        }

        def get_param_values( app, ignore_errors ):
            assert app == self.app
            params = raw_params.copy()
            params[ "__job_resource" ] = {
                "__job_resource__select": "True",
                "memory": "8gb"
            }
            return params

        return bunch.Bunch(
            user=bunch.Bunch(
                id=6789,
                email="test@example.com"
            ),
            raw_param_dict=lambda: raw_params,
            get_param_values=get_param_values
        )


class MockAgent( object ):

    def __init__( self, agent_job_destination ):
        self.id = "testagentshed/devteam/agent1/23abcd13123"
        self.call_count = 0
        self.agent_job_destination = agent_job_destination
        self.all_ids = [ "testagentshed/devteam/agent1/23abcd13123", "agent1" ]

    def get_job_destination( self, params ):
        self.call_count += 1
        return self.agent_job_destination

    def is_mock_agent( self ):
        return True
