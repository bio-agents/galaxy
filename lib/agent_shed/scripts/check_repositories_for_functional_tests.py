#!/usr/bin/env python

import ConfigParser
import logging
import os
import shutil
import sys
import tempfile
import time
from optparse import OptionParser
from time import strftime

sys.path[1:1] = [ os.path.join( os.path.dirname( __file__ ), os.pardir, os.pardir ),
                  os.path.join( os.path.dirname( __file__ ), os.pardir, os.pardir, os.pardir, 'test' ) ]

from mercurial import __version__
from sqlalchemy import and_, false, true

import galaxy.webapps.agent_shed.config as agent_shed_config
import agent_shed.util.shed_util_common as suc
from galaxy.util import listify
from install_and_test_agent_shed_repositories.base.util import get_database_version
from install_and_test_agent_shed_repositories.base.util import get_repository_current_revision
from install_and_test_agent_shed_repositories.base.util import RepositoryMetadataApplication
from agent_shed.util import hg_util

log = logging.getLogger( 'check_repositories_for_functional_tests' )
assert sys.version_info[ :2 ] >= ( 2, 6 )


def check_and_update_repository_metadata( app, info_only=False, verbosity=1 ):
    """
    This method will iterate through all records in the repository_metadata
    table, checking each one for agent metadata, then checking the agent
    metadata for tests.  Each agent's metadata should look something like:
    {
      "add_to_agent_panel": true,
      "description": "",
      "guid": "agentshed.url:9009/repos/owner/name/agent_id/1.2.3",
      "id": "agent_wrapper",
      "name": "Map with Agent Wrapper",
      "requirements": [],
      "tests": [],
      "agent_config": "database/community_files/000/repo_1/agent_wrapper.xml",
      "agent_type": "default",
      "version": "1.2.3",
      "version_string_cmd": null
    }
    If the "tests" attribute is missing or empty, this script will mark the metadata record (which is specific to a changeset revision of a repository)
    not to be tested. If each "agents" attribute has at least one valid "tests" entry, this script will do nothing, and leave it available for the install
    and test repositories script to process. If the tested changeset revision does not have a test-data directory, this script will also mark the revision
    not to be tested.
    """
    start = time.time()
    skip_metadata_ids = []
    checked_repository_ids = []
    agent_count = 0
    has_tests = 0
    no_tests = 0
    valid_revisions = 0
    invalid_revisions = 0
    records_checked = 0
    # Do not check metadata records that have an entry in the skip_agent_tests table, since they won't be tested anyway.
    print '# -------------------------------------------------------------------------------------------'
    print '# The skip_agent_test setting has been set for the following repository revision, so they will not be tested.'
    skip_metadata_ids = []
    for skip_agent_test in app.sa_session.query( app.model.SkipAgentTest ):
        print '# repository_metadata_id: %s, changeset_revision: %s' % \
            ( str( skip_agent_test.repository_metadata_id ), str( skip_agent_test.initial_changeset_revision ) )
        print 'reason: %s' % str( skip_agent_test.comment )
        skip_metadata_ids.append( skip_agent_test.repository_metadata_id )
    # Get the list of metadata records to check for functional tests and test data. Limit this to records that have not been flagged do_not_test,
    # since there's no need to check them again if they won't be tested anyway. Also filter out changeset revisions that are not downloadable,
    # because it's redundant to test a revision that a user can't install.
    for repository_metadata in app.sa_session.query( app.model.RepositoryMetadata ) \
                                             .filter( and_( app.model.RepositoryMetadata.table.c.downloadable == true(),
                                                            app.model.RepositoryMetadata.table.c.includes_agents == true(),
                                                            app.model.RepositoryMetadata.table.c.do_not_test == false() ) ):
        # Initialize some items.
        missing_test_components = []
        revision_has_test_data = False
        testable_revision = False
        repository = repository_metadata.repository
        records_checked += 1
        # Check the next repository revision.
        changeset_revision = str( repository_metadata.changeset_revision )
        name = repository.name
        owner = repository.user.username
        metadata = repository_metadata.metadata
        repository = repository_metadata.repository
        if repository.id not in checked_repository_ids:
            checked_repository_ids.append( repository.id )
        print '# -------------------------------------------------------------------------------------------'
        print '# Checking revision %s of %s owned by %s.' % ( changeset_revision, name, owner )
        if repository_metadata.id in skip_metadata_ids:
            print'# Skipping revision %s of %s owned by %s because the skip_agent_test setting has been set.' % ( changeset_revision, name, owner )
            continue
        # If this changeset revision has no agents, we don't need to do anything here, the install and test script has a filter for returning
        # only repositories that contain agents.
        agent_dicts = metadata.get( 'agents', None )
        if agent_dicts is not None:
            # Clone the repository up to the changeset revision we're checking.
            repo_dir = repository.repo_path( app )
            hg_util.get_repo_for_repository( app, repository=None, repo_path=repo_dir, create=False )
            work_dir = tempfile.mkdtemp( prefix="tmp-agentshed-cafr"  )
            cloned_ok, error_message = hg_util.clone_repository( repo_dir, work_dir, changeset_revision )
            if cloned_ok:
                # Iterate through all the directories in the cloned changeset revision and determine whether there's a
                # directory named test-data. If this directory is not present update the metadata record for the changeset
                # revision we're checking.
                for root, dirs, files in os.walk( work_dir ):
                    if '.hg' in dirs:
                        dirs.remove( '.hg' )
                    if 'test-data' in dirs:
                        revision_has_test_data = True
                        test_data_path = os.path.join( root, dirs[ dirs.index( 'test-data' ) ] )
                        break
            if revision_has_test_data:
                print '# Test data directory found in changeset revision %s of repository %s owned by %s.' % ( changeset_revision, name, owner )
            else:
                print '# Test data directory missing in changeset revision %s of repository %s owned by %s.' % ( changeset_revision, name, owner )
            print '# Checking for functional tests in changeset revision %s of %s, owned by %s.' % \
                ( changeset_revision, name, owner )
            # Inspect each agent_dict for defined functional tests.  If there
            # are no tests, this agent should not be tested, since the agent
            # functional tests only report failure if the test itself fails,
            # not if it's missing or undefined. Filtering out those
            # repositories at this step will reduce the number of "false
            # negatives" the automated functional test framework produces.
            for agent_dict in agent_dicts:
                failure_reason = ''
                problem_found = False
                agent_has_defined_tests = False
                agent_has_test_files = False
                missing_test_files = []
                agent_count += 1
                agent_id = agent_dict[ 'id' ]
                agent_version = agent_dict[ 'version' ]
                agent_guid = agent_dict[ 'guid' ]
                if verbosity >= 1:
                    print "# Checking agent ID '%s' in changeset revision %s of %s." % ( agent_id, changeset_revision, name )
                defined_test_dicts = agent_dict.get( 'tests', None )
                if defined_test_dicts is not None:
                    # We need to inspect the <test> tags because the following tags...
                    # <tests>
                    # </tests>
                    # ...will produce the following metadata:
                    # "tests": []
                    # And the following tags...
                    # <tests>
                    #     <test>
                    #    </test>
                    # </tests>
                    # ...will produce the following metadata:
                    # "tests":
                    #    [{"inputs": [], "name": "Test-1", "outputs": [], "required_files": []}]
                    for defined_test_dict in defined_test_dicts:
                        inputs = defined_test_dict.get( 'inputs', [] )
                        outputs = defined_test_dict.get( 'outputs', [] )
                        if inputs and outputs:
                            # At least one agent within the repository has a valid <test> tag.
                            agent_has_defined_tests = True
                            break
                if agent_has_defined_tests:
                    print "# Agent ID '%s' in changeset revision %s of %s has one or more valid functional tests defined." % \
                        ( agent_id, changeset_revision, name )
                    has_tests += 1
                else:
                    print '# No functional tests defined for %s.' % agent_id
                    no_tests += 1
                if agent_has_defined_tests and revision_has_test_data:
                    missing_test_files = check_for_missing_test_files( defined_test_dicts, test_data_path )
                    if missing_test_files:
                        print "# Agent id '%s' in changeset revision %s of %s is missing one or more required test files: %s" % \
                            ( agent_id, changeset_revision, name, ', '.join( missing_test_files ) )
                    else:
                        agent_has_test_files = True
                if not revision_has_test_data:
                    failure_reason += 'Repository does not have a test-data directory. '
                    problem_found = True
                if not agent_has_defined_tests:
                    failure_reason += 'Functional test definitions missing for %s. ' % agent_id
                    problem_found = True
                if missing_test_files:
                    failure_reason += 'One or more test files are missing for agent %s: %s' % ( agent_id, ', '.join( missing_test_files ) )
                    problem_found = True
                test_errors = dict( agent_id=agent_id, agent_version=agent_version, agent_guid=agent_guid, missing_components=failure_reason )
                # Only append this error dict if it hasn't already been added.
                if problem_found:
                    if test_errors not in missing_test_components:
                        missing_test_components.append( test_errors )
                if agent_has_defined_tests and agent_has_test_files:
                    print '# Revision %s of %s owned by %s is a testable revision.' % ( changeset_revision, name, owner )
                    testable_revision = True
            # Remove the cloned repository path. This has to be done after the check for required test files, for obvious reasons.
            if os.path.exists( work_dir ):
                shutil.rmtree( work_dir )
            if not missing_test_components:
                valid_revisions += 1
                print '# All agents have functional tests in changeset revision %s of repository %s owned by %s.' % ( changeset_revision, name, owner )
            else:
                invalid_revisions += 1
                print '# Some agents have problematic functional tests in changeset revision %s of repository %s owned by %s.' % ( changeset_revision, name, owner )
                if verbosity >= 1:
                    for missing_test_component in missing_test_components:
                        if 'missing_components' in missing_test_component:
                            print '# %s' % missing_test_component[ 'missing_components' ]
            if not info_only:
                # Get or create the list of agent_test_results dictionaries.
                if repository_metadata.agent_test_results is not None:
                    # We'll listify the column value in case it uses the old approach of storing the results of only a single test run.
                    agent_test_results_dicts = listify( repository_metadata.agent_test_results )
                else:
                    agent_test_results_dicts = []
                if agent_test_results_dicts:
                    # Inspect the agent_test_results_dict for the last test run in case it contains only a test_environment
                    # entry.  This will occur with multiple runs of this script without running the associated
                    # install_and_test_agent_sed_repositories.sh script which will further populate the agent_test_results_dict.
                    agent_test_results_dict = agent_test_results_dicts[ 0 ]
                    if len( agent_test_results_dict ) <= 1:
                        # We can re-use the mostly empty agent_test_results_dict for this run because it is either empty or it contains only
                        # a test_environment entry.  If we use it we need to temporarily eliminate it from the list of agent_test_results_dicts
                        # since it will be re-inserted later.
                        agent_test_results_dict = agent_test_results_dicts.pop( 0 )
                    elif (len( agent_test_results_dict ) == 2 and
                          'test_environment' in agent_test_results_dict and 'missing_test_components' in agent_test_results_dict):
                        # We can re-use agent_test_results_dict if its only entries are "test_environment" and "missing_test_components".
                        # In this case, some agents are missing tests components while others are not.
                        agent_test_results_dict = agent_test_results_dicts.pop( 0 )
                    else:
                        # The latest agent_test_results_dict has been populated with the results of a test run, so it cannot be used.
                        agent_test_results_dict = {}
                else:
                    # Create a new dictionary for the most recent test run.
                    agent_test_results_dict = {}
                test_environment_dict = agent_test_results_dict.get( 'test_environment', {} )
                # Add the current time as the approximate time that this test run occurs.  A similar value will also be
                # set to the repository_metadata.time_last_tested column, but we also store it here because the Agent Shed
                # may be configured to store multiple test run results, so each must be associated with a time stamp.
                now = time.strftime( "%Y-%m-%d %H:%M:%S" )
                test_environment_dict[ 'time_tested' ] = now
                test_environment_dict[ 'agent_shed_database_version' ] = get_database_version( app )
                test_environment_dict[ 'agent_shed_mercurial_version' ] = __version__.version
                test_environment_dict[ 'agent_shed_revision' ] = get_repository_current_revision( os.getcwd() )
                agent_test_results_dict[ 'test_environment' ] = test_environment_dict
                # The repository_metadata.time_last_tested column is not changed by this script since no testing is performed here.
                if missing_test_components:
                    # If functional test definitions or test data are missing, set do_not_test = True if no agent with valid tests has been
                    # found in this revision, and:
                    # a) There are multiple downloadable revisions, and the revision being tested is not the most recent downloadable revision.
                    #    In this case, the revision will never be updated with the missing components, and re-testing it would be redundant.
                    # b) There are one or more downloadable revisions, and the provided changeset revision is the most recent downloadable
                    #    revision. In this case, if the repository is updated with test data or functional tests, the downloadable
                    #    changeset revision that was tested will either be replaced with the new changeset revision, or a new downloadable
                    #    changeset revision will be created, either of which will be automatically checked and flagged as appropriate.
                    #    In the install and test script, this behavior is slightly different, since we do want to always run functional
                    #    tests on the most recent downloadable changeset revision.
                    if should_set_do_not_test_flag( app, repository, changeset_revision, testable_revision ):
                        print "# Setting do_not_test to True on revision %s of %s owned by %s because it is missing test components" % (
                            changeset_revision, name, owner
                        )
                        print "# and it is not the latest downloadable revision."
                        repository_metadata.do_not_test = True
                    if not testable_revision:
                        # Even though some agents may be missing test components, it may be possible to test other agents.  Since the
                        # install and test framework filters out repositories marked as missing test components, we'll set it only if
                        # no agents can be tested.
                        print '# Setting missing_test_components to True for revision %s of %s owned by %s because all agents are missing test components.' % (
                            changeset_revision, name, owner
                        )
                        repository_metadata.missing_test_components = True
                        print "# Setting agents_functionally_correct to False on revision %s of %s owned by %s because it is missing test components" % (
                            changeset_revision, name, owner
                        )
                        repository_metadata.agents_functionally_correct = False
                    agent_test_results_dict[ 'missing_test_components' ] = missing_test_components
                # Store only the configured number of test runs.
                num_agent_test_results_saved = int( app.config.num_agent_test_results_saved )
                if len( agent_test_results_dicts ) >= num_agent_test_results_saved:
                    test_results_index = num_agent_test_results_saved - 1
                    new_agent_test_results_dicts = agent_test_results_dicts[ :test_results_index ]
                else:
                    new_agent_test_results_dicts = [ d for d in agent_test_results_dicts ]
                # Insert the new element into the first position in the list.
                new_agent_test_results_dicts.insert( 0, agent_test_results_dict )
                repository_metadata.agent_test_results = new_agent_test_results_dicts
                app.sa_session.add( repository_metadata )
                app.sa_session.flush()
    stop = time.time()
    print '# -------------------------------------------------------------------------------------------'
    print '# Checked %d repositories with %d agents in %d changeset revisions.' % ( len( checked_repository_ids ), agent_count, records_checked )
    print '# %d revisions found with functional tests and test data for all agents.' % valid_revisions
    print '# %d revisions found with one or more agents missing functional tests and/or test data.' % invalid_revisions
    print '# Found %d agents without functional tests.' % no_tests
    print '# Found %d agents with functional tests.' % has_tests
    if info_only:
        print '# Database not updated, info_only set.'
    print "# Elapsed time: ", stop - start
    print "#############################################################################"


def check_for_missing_test_files( test_definition, test_data_path ):
    '''Process the agent's functional test definitions and check for each file specified as an input or output.'''
    missing_test_files = []
    required_test_files = []
    for test_dict in test_definition:
        for required_file in test_dict[ 'required_files' ]:
            if required_file not in required_test_files:
                required_test_files.append( required_file )
    # Make sure each specified file actually does exist in the test data path of the cloned repository.
    for required_file in required_test_files:
        required_file_full_path = os.path.join( test_data_path, required_file )
        if not os.path.exists( required_file_full_path ):
            missing_test_files.append( required_file )
    return missing_test_files


def main():
    '''Script that checks repositories to see if the agents contained within them have functional tests defined.'''
    parser = OptionParser()
    parser.add_option( "-i", "--info_only", action="store_true", dest="info_only", help="info about the requested action", default=False )
    parser.add_option( "-s", "--section", action="store", dest="section", default='server:main',
                       help=".ini file section from which to to extract the host and port" )
    parser.add_option( "-v", "--verbose", action="count", dest="verbosity", default=1, help="Control the amount of detail in the log output.")
    parser.add_option( "--verbosity", action="store", dest="verbosity", metavar='VERBOSITY', type="int",
                       help="Control the amount of detail in the log output. --verbosity=1 is the same as -v" )
    ( options, args ) = parser.parse_args()
    try:
        ini_file = args[ 0 ]
    except IndexError:
        print "Usage: python %s <agent shed .ini file> [options]" % sys.argv[ 0 ]
        sys.exit( 127 )
    config_parser = ConfigParser.ConfigParser( { 'here': os.getcwd() } )
    config_parser.read( ini_file )
    config_dict = {}
    for key, value in config_parser.items( "app:main" ):
        config_dict[ key ] = value
    config = agent_shed_config.Configuration( **config_dict )
    config_section = options.section
    now = strftime( "%Y-%m-%d %H:%M:%S" )

    print "#############################################################################"
    print "# %s - Checking repositories for agents with functional tests." % now
    print "# This agent shed is configured to listen on %s:%s." % ( config_parser.get( config_section, 'host' ),
                                                                   config_parser.get( config_section, 'port' ) )
    app = RepositoryMetadataApplication( config )
    if options.info_only:
        print "# Displaying info only ( --info_only )"
    if options.verbosity:
        print "# Displaying extra information ( --verbosity = %d )" % options.verbosity
    check_and_update_repository_metadata( app, info_only=options.info_only, verbosity=options.verbosity )


def should_set_do_not_test_flag( app, repository, changeset_revision, testable_revision ):
    """
    The received testable_revision is True if the agent has defined tests and test files are in the repository
    This method returns True if the received repository has multiple downloadable revisions and the received
    changeset_revision is not the most recent downloadable revision and the received testable_revision is False.
    In this case, the received changeset_revision will never be updated with correct data, and re-testing it
    would be redundant.
    """
    if not testable_revision:
        repo = hg_util.get_repo_for_repository( app, repository=repository, repo_path=None, create=False )
        changeset_revisions = [ revision[ 1 ] for revision in suc.get_metadata_revisions( repository, repo ) ]
        if len( changeset_revisions ) > 1:
            latest_downloadable_revision = changeset_revisions[ -1 ]
            if changeset_revision != latest_downloadable_revision:
                return True
    return False

if __name__ == "__main__":
    # The repository_metadata.agent_test_results json value should have the following list structure:
    # [
    # {
    #     "test_environment":
    #         {
    #              "galaxy_revision": "9001:abcd1234",
    #              "galaxy_database_version": "114",
    #              "agent_shed_revision": "9001:abcd1234",
    #              "agent_shed_mercurial_version": "2.3.1",
    #              "agent_shed_database_version": "17",
    #              "python_version": "2.7.2",
    #              "architecture": "x86_64",
    #              "system": "Darwin 12.2.0"
    #         },
    #      "passed_tests":
    #         [
    #             {
    #                 "test_id": "The test ID, generated by twill",
    #                 "agent_id": "The agent ID that was tested",
    #                 "agent_version": "The agent version that was tested",
    #             },
    #         ]
    #     "failed_tests":
    #         [
    #             {
    #                 "test_id": "The test ID, generated by twill",
    #                 "agent_id": "The agent ID that was tested",
    #                 "agent_version": "The agent version that was tested",
    #                 "stderr": "The output of the test, or a more detailed description of what was tested and what the outcome was."
    #                 "traceback": "The captured traceback."
    #             },
    #         ]
    #     "installation_errors":
    #         {
    #              'agent_dependencies':
    #                  [
    #                      {
    #                         'type': 'Type of agent dependency, e.g. package, set_environment, etc.',
    #                         'name': 'Name of the agent dependency.',
    #                         'version': 'Version if this is a package, otherwise blank.',
    #                         'error_message': 'The error message returned when installation was attempted.',
    #                      },
    #                  ],
    #              'repository_dependencies':
    #                  [
    #                      {
    #                         'agent_shed': 'The agent shed that this repository was installed from.',
    #                         'name': 'The name of the repository that failed to install.',
    #                         'owner': 'Owner of the failed repository.',
    #                         'changeset_revision': 'Changeset revision of the failed repository.',
    #                         'error_message': 'The error message that was returned when the repository failed to install.',
    #                      },
    #                  ],
    #              'current_repository':
    #                  [
    #                      {
    #                         'agent_shed': 'The agent shed that this repository was installed from.',
    #                         'name': 'The name of the repository that failed to install.',
    #                         'owner': 'Owner of the failed repository.',
    #                         'changeset_revision': 'Changeset revision of the failed repository.',
    #                         'error_message': 'The error message that was returned when the repository failed to install.',
    #                      },
    #                  ],
    #             {
    #                 "name": "The name of the repository.",
    #                 "owner": "The owner of the repository.",
    #                 "changeset_revision": "The changeset revision of the repository.",
    #                 "error_message": "The message stored in agent_dependency.error_message."
    #             },
    #         }
    #      "missing_test_components":
    #         [
    #             {
    #                 "agent_id": "The agent ID that missing components.",
    #                 "agent_version": "The version of the agent."
    #                 "agent_guid": "The guid of the agent."
    #                 "missing_components": "Which components are missing, e.g. the test data filename, or the test-data directory."
    #             },
    #         ]
    # }
    # ]
    #
    # Optionally, "traceback" may be included in a test_errors dict, if it is relevant. No script should overwrite anything other
    # than the list relevant to what it is testing.
    main()
