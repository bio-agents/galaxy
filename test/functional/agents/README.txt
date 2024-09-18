This directory contains agents only useful for testing and
demonstrating aspects of the agent syntax. Run the test driver script
'run_tests.sh' with the '-framework' as first argument to run through
these tests. Pass in an '-id' along with one of these agent ids to test
a single agent.

Some API tests use these agents to test various features of the API,
agent, and workflow subsystems. Pass the argument
'-with_framework_test_agents' to 'run_tests.sh' in addition to '-api'
to ensure these agents get loaded during the testing process.

Finally, to play around with these agents interactively - simply
replace the 'galaxy.ini' option 'agent_config_file' with:

agent_config_file = test/functional/agents/samples_agent_conf.xml
