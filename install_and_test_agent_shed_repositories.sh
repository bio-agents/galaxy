#!/bin/sh

# Enable verbose test errors for install and test framework.
GALAXY_TEST_VERBOSE_ERRORS="True"
export GALAXY_TEST_VERBOSE_ERRORS

# A good place to look for nose info: http://somethingaboutorange.com/mrl/projects/nose/

# The test/install_and_test_agent_shed_repositories/functional_tests.py cannot be executed directly because it must
# have certain functional test definitions in sys.argv.  Running it through this shell script is the best way to
# ensure that it has the required definitions.

# This script requires setting of the following environment variables:
# GALAXY_INSTALL_TEST_TOOL_SHED_API_KEY - must be set to the API key for the agent shed that is being checked.
# GALAXY_INSTALL_TEST_TOOL_SHED_URL - must be set to a URL that the agent shed is listening on.

# If the agent shed url is not specified in agent_sheds_conf.xml, GALAXY_INSTALL_TEST_TOOL_SHEDS_CONF must be set to
# a agent sheds configuration file that does specify that url or repository installation will fail.

# This script accepts the command line option -w to select which set of tests to run. The default behavior is to test
# first agent_dependency_definition repositories and then repositories with agents. Provide the value 'dependencies'
# to test only agent_dependency_definition repositories or 'agents' to test only repositories with agents. 

if [ -z $GALAXY_INSTALL_TEST_TOOL_SHED_API_KEY ] ; then
	echo "This script requires the GALAXY_INSTALL_TEST_TOOL_SHED_API_KEY environment variable to be set and non-empty."
	exit 1
fi

if [ -z $GALAXY_INSTALL_TEST_TOOL_DEPENDENCY_DIR ] ; then
	echo "This script requires the GALAXY_INSTALL_TEST_TOOL_DEPENDENCY_DIR environment variable to be set to your configured agent dependency path."
	exit 1
fi

if [ -z $GALAXY_INSTALL_TEST_TOOL_SHED_URL ] ; then
	echo "This script requires the GALAXY_INSTALL_TEST_TOOL_SHED_URL environment variable to be set and non-empty."
	exit 1
fi

if [ -z "$GALAXY_INSTALL_TEST_TOOL_SHEDS_CONF" ] ; then
	if grep --quiet $GALAXY_INSTALL_TEST_TOOL_SHED_URL config/agent_sheds_conf.xml.sample; then
		echo "Agent sheds configuration agent_sheds_conf.xml ok, proceeding."
	else
		echo "ERROR: Agent sheds configuration agent_sheds_conf.xml does not have an entry for $GALAXY_INSTALL_TEST_TOOL_SHED_URL."
		exit 1
	fi
else
	if grep --quiet $GALAXY_INSTALL_TEST_TOOL_SHED_URL $GALAXY_INSTALL_TEST_TOOL_SHEDS_CONF; then
		echo "Agent sheds configuration $GALAXY_INSTALL_TEST_TOOL_SHEDS_CONF ok, proceeding."
	else
		echo "ERROR: Agent sheds configuration $GALAXY_INSTALL_TEST_TOOL_SHEDS_CONF does not have an entry for $GALAXY_INSTALL_TEST_TOOL_SHED_URL"
		exit 1
	fi
fi

if [ -z $GALAXY_INSTALL_TEST_SHED_TOOL_PATH ] ; then
	export GALAXY_INSTALL_TEST_SHED_TOOL_PATH='/tmp/shed_agents'
fi

if [ ! -d $GALAXY_INSTALL_TEST_SHED_TOOL_PATH ] ; then
	mkdir -p $GALAXY_INSTALL_TEST_SHED_TOOL_PATH
fi

if [ ! -d $GALAXY_INSTALL_TEST_TOOL_DEPENDENCY_DIR ] ; then
    mkdir -p $GALAXY_INSTALL_TEST_TOOL_DEPENDENCY_DIR
fi

test_agent_dependency_definitions () {
    # Test installation of repositories of type agent_dependency_definition.
	if [ -f $GALAXY_INSTALL_TEST_TOOL_DEPENDENCY_DIR/stage_1_complete ] ; then
		rm $GALAXY_INSTALL_TEST_TOOL_DEPENDENCY_DIR/stage_1_complete
	fi
    echo "Starting stage 1, agent dependency definitions."
    python test/install_and_test_agent_shed_repositories/agent_dependency_definitions/functional_tests.py $* -v --with-nosehtml --html-report-file \
        test/install_and_test_agent_shed_repositories/agent_dependency_definitions/run_functional_tests.html \
        test/install_and_test_agent_shed_repositories/functional/test_install_repositories.py \
        test/functional/test_agentbox.py
    echo "Stage 1 complete, exit code $?"
    touch $GALAXY_INSTALL_TEST_TOOL_DEPENDENCY_DIR/stage_1_complete
}

test_repositories_with_agents () {
	if [ ! -f $GALAXY_INSTALL_TEST_TOOL_DEPENDENCY_DIR/stage_1_complete ] ; then
		echo 'Stage 1 did not complete its run, exiting.'
		exit 1
	fi
    echo "Starting stage 2, repositories with agents."
    # Test installation of repositories that contain valid agents with defined functional tests and a test-data directory containing test files.
    python test/install_and_test_agent_shed_repositories/repositories_with_agents/functional_tests.py $* -v --with-nosehtml --html-report-file \
        test/install_and_test_agent_shed_repositories/repositories_with_agents/run_functional_tests.html \
        test/install_and_test_agent_shed_repositories/functional/test_install_repositories.py \
        test/functional/test_agentbox.py
    echo "Stage 2 complete, exit code $?"
    rm $GALAXY_INSTALL_TEST_TOOL_DEPENDENCY_DIR/stage_1_complete
}

which='both'

while getopts "w:" arg; do
    case $arg in
        w)
            which=$OPTARG
            ;;
    esac
done

case $which in
    # Use "-w agent_dependency_definitions" when you want to test repositories of type agent_dependency_definition.
    agent_dependency_definitions)
        test_agent_dependency_definitions
        ;;
    # Use "-w repositories_with_agents" parameter when you want to test repositories that contain agents.
    repositories_with_agents)
        touch $GALAXY_INSTALL_TEST_TOOL_DEPENDENCY_DIR/stage_1_complete
        test_repositories_with_agents
        ;;
    # No received parameters or any received parameter not in [ agent_dependency_definitions, repositories_with_agents ]
    # will execute both scripts.
    *)
        test_agent_dependency_definitions
        test_repositories_with_agents
        ;;
esac        
