

def upload():
    return 'local_runner'


def tophat():
    return 'site_dest_id'


def agent1():
    # agent1 is id to test agent mocked out in test_mapper.py, without specify
    # function name in dynamic destination - this function should be used by
    # default.
    return 'agent1_dest_id'


def check_rule_params(
    job_id,
    agent,
    agent_id,
    job_wrapper,
    rule_helper,
    app,
    job,
    user,
    user_email,
):
    assert job_id == 12345
    assert agent.is_mock_agent()
    assert agent_id == "testagentshed/devteam/agent1/23abcd13123"
    assert job_wrapper.is_mock_job_wrapper()
    assert app == job_wrapper.app
    assert rule_helper is not None

    assert job.user == user
    assert user.id == 6789
    assert user_email == "test@example.com"

    return "all_passed"


def check_job_conf_params( param1 ):
    assert param1 == "7"
    return "sent_7_dest_id"


def check_resource_params( resource_params ):
    assert resource_params["memory"] == "8gb"
    return "have_resource_params"


def check_workflow_invocation_uuid( workflow_invocation_uuid ):
    return workflow_invocation_uuid
