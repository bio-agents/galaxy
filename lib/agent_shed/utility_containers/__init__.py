import logging
import threading

from galaxy import util
from agent_shed.util import common_util
from agent_shed.util import container_util
from agent_shed.util import readme_util

from . import utility_container_manager

log = logging.getLogger( __name__ )


class FailedTest( object ):
    """Failed agent tests object"""

    def __init__( self, id=None, stderr=None, test_id=None, agent_id=None, agent_version=None, traceback=None ):
        self.id = id
        self.stderr = stderr
        self.test_id = test_id
        self.agent_id = agent_id
        self.agent_version = agent_version
        self.traceback = traceback


class InvalidRepositoryDependency( object ):
    """Invalid repository dependency definition object"""

    def __init__( self, id=None, agentshed=None, repository_name=None, repository_owner=None, changeset_revision=None,
                  prior_installation_required=False, only_if_compiling_contained_td=False, error=None ):
        self.id = id
        self.agentshed = agentshed
        self.repository_name = repository_name
        self.repository_owner = repository_owner
        self.changeset_revision = changeset_revision
        self.prior_installation_required = prior_installation_required
        self.only_if_compiling_contained_td = only_if_compiling_contained_td
        self.error = error


class InvalidAgentDependency( object ):
    """Invalid agent dependency definition object"""

    def __init__( self, id=None, name=None, version=None, type=None, error=None ):
        self.id = id
        self.name = name
        self.version = version
        self.type = type
        self.error = error


class MissingTestComponent( object ):
    """Missing agent test components object"""

    def __init__( self, id=None, missing_components=None, agent_guid=None, agent_id=None, agent_version=None ):
        self.id = id
        self.missing_components = missing_components
        self.agent_guid = agent_guid
        self.agent_id = agent_id
        self.agent_version = agent_version


class NotTested( object ):
    """NotTested object"""

    def __init__( self, id=None, reason=None ):
        self.id = id
        self.reason = reason


class PassedTest( object ):
    """Passed agent tests object"""

    def __init__( self, id=None, test_id=None, agent_id=None, agent_version=None ):
        self.id = id
        self.test_id = test_id
        self.agent_id = agent_id
        self.agent_version = agent_version


class RepositoryInstallationError( object ):
    """Repository installation error object"""

    def __init__( self, id=None, agent_shed=None, name=None, owner=None, changeset_revision=None, error_message=None ):
        self.id = id
        self.agent_shed = agent_shed
        self.name = name
        self.owner = owner
        self.changeset_revision = changeset_revision
        self.error_message = error_message


class RepositorySuccessfulInstallation( object ):
    """Repository installation object"""

    def __init__( self, id=None, agent_shed=None, name=None, owner=None, changeset_revision=None ):
        self.id = id
        self.agent_shed = agent_shed
        self.name = name
        self.owner = owner
        self.changeset_revision = changeset_revision


class TestEnvironment( object ):
    """Agent test environment object"""

    def __init__( self, id=None, architecture=None, galaxy_database_version=None, galaxy_revision=None, python_version=None, system=None, time_tested=None,
                  agent_shed_database_version=None, agent_shed_mercurial_version=None, agent_shed_revision=None ):
        self.id = id
        self.architecture = architecture
        self.galaxy_database_version = galaxy_database_version
        self.galaxy_revision = galaxy_revision
        self.python_version = python_version
        self.system = system
        self.time_tested = time_tested
        self.agent_shed_database_version = agent_shed_database_version
        self.agent_shed_mercurial_version = agent_shed_mercurial_version
        self.agent_shed_revision = agent_shed_revision


class AgentDependencyInstallationError( object ):
    """Agent dependency installation error object"""

    def __init__( self, id=None, type=None, name=None, version=None, error_message=None ):
        self.id = id
        self.type = type
        self.name = name
        self.version = version
        self.error_message = error_message


class AgentDependencySuccessfulInstallation( object ):
    """Agent dependency installation object"""

    def __init__( self, id=None, type=None, name=None, version=None, installation_directory=None ):
        self.id = id
        self.type = type
        self.name = name
        self.version = version
        self.installation_directory = installation_directory


class AgentShedUtilityContainerManager( utility_container_manager.UtilityContainerManager ):

    def __init__( self, app ):
        self.app = app

    def build_invalid_repository_dependencies_root_folder( self, folder_id, invalid_repository_dependencies_dict ):
        """Return a folder hierarchy containing invalid repository dependencies."""
        label = 'Invalid repository dependencies'
        if invalid_repository_dependencies_dict:
            invalid_repository_dependency_id = 0
            folder_id += 1
            invalid_repository_dependencies_root_folder = \
                utility_container_manager.Folder( id=folder_id,
                                                  key='root',
                                                  label='root',
                                                  parent=None )
            folder_id += 1
            invalid_repository_dependencies_folder = \
                utility_container_manager.Folder( id=folder_id,
                                                  key='invalid_repository_dependencies',
                                                  label=label,
                                                  parent=invalid_repository_dependencies_root_folder )
            invalid_repository_dependencies_root_folder.folders.append( invalid_repository_dependencies_folder )
            invalid_repository_dependencies = invalid_repository_dependencies_dict[ 'repository_dependencies' ]
            for invalid_repository_dependency in invalid_repository_dependencies:
                folder_id += 1
                invalid_repository_dependency_id += 1
                agentshed, name, owner, changeset_revision, prior_installation_required, only_if_compiling_contained_td, error = \
                    common_util.parse_repository_dependency_tuple( invalid_repository_dependency, contains_error=True )
                key = container_util.generate_repository_dependencies_key_for_repository( agentshed,
                                                                                          name,
                                                                                          owner,
                                                                                          changeset_revision,
                                                                                          prior_installation_required,
                                                                                          only_if_compiling_contained_td )
                label = "Repository <b>%s</b> revision <b>%s</b> owned by <b>%s</b>" % ( name, changeset_revision, owner )
                folder = utility_container_manager.Folder( id=folder_id,
                                                           key=key,
                                                           label=label,
                                                           parent=invalid_repository_dependencies_folder )
                ird = InvalidRepositoryDependency( id=invalid_repository_dependency_id,
                                                   agentshed=agentshed,
                                                   repository_name=name,
                                                   repository_owner=owner,
                                                   changeset_revision=changeset_revision,
                                                   prior_installation_required=util.asbool( prior_installation_required ),
                                                   only_if_compiling_contained_td=util.asbool( only_if_compiling_contained_td ),
                                                   error=error )
                folder.invalid_repository_dependencies.append( ird )
                invalid_repository_dependencies_folder.folders.append( folder )
        else:
            invalid_repository_dependencies_root_folder = None
        return folder_id, invalid_repository_dependencies_root_folder

    def build_invalid_agent_dependencies_root_folder( self, folder_id, invalid_agent_dependencies_dict ):
        """Return a folder hierarchy containing invalid agent dependencies."""
        # # INvalid agent dependencies are always packages like:
        # {"R/2.15.1": {"name": "R", "readme": "some string", "type": "package", "version": "2.15.1" "error" : "some sting" }
        label = 'Invalid agent dependencies'
        if invalid_agent_dependencies_dict:
            invalid_agent_dependency_id = 0
            folder_id += 1
            invalid_agent_dependencies_root_folder = \
                utility_container_manager.Folder( id=folder_id, key='root', label='root', parent=None )
            folder_id += 1
            invalid_agent_dependencies_folder = \
                utility_container_manager.Folder( id=folder_id,
                                                  key='invalid_agent_dependencies',
                                                  label=label,
                                                  parent=invalid_agent_dependencies_root_folder )
            invalid_agent_dependencies_root_folder.folders.append( invalid_agent_dependencies_folder )
            for td_key, requirements_dict in invalid_agent_dependencies_dict.items():
                folder_id += 1
                invalid_agent_dependency_id += 1
                try:
                    name = requirements_dict[ 'name' ]
                    type = requirements_dict[ 'type' ]
                    version = requirements_dict[ 'version' ]
                    error = requirements_dict[ 'error' ]
                except Exception, e:
                    name = 'unknown'
                    type = 'unknown'
                    version = 'unknown'
                    error = str( e )
                key = self.generate_agent_dependencies_key( name, version, type )
                label = "Version <b>%s</b> of the <b>%s</b> <b>%s</b>" % ( version, name, type )
                folder = utility_container_manager.Folder( id=folder_id,
                                                           key=key,
                                                           label=label,
                                                           parent=invalid_agent_dependencies_folder )
                itd = InvalidAgentDependency( id=invalid_agent_dependency_id,
                                             name=name,
                                             version=version,
                                             type=type,
                                             error=error )
                folder.invalid_agent_dependencies.append( itd )
                invalid_agent_dependencies_folder.folders.append( folder )
        else:
            invalid_agent_dependencies_root_folder = None
        return folder_id, invalid_agent_dependencies_root_folder

    def build_repository_containers( self, repository, changeset_revision, repository_dependencies, repository_metadata,
                                     exclude=None ):
        """
        Return a dictionary of containers for the received repository's dependencies and
        contents for display in the Agent Shed.
        """
        if exclude is None:
            exclude = []
        containers_dict = dict( datatypes=None,
                                invalid_agents=None,
                                readme_files=None,
                                repository_dependencies=None,
                                agent_dependencies=None,
                                valid_agents=None,
                                workflows=None,
                                valid_data_managers=None
                                )
        if repository_metadata:
            metadata = repository_metadata.metadata
            lock = threading.Lock()
            lock.acquire( True )
            try:
                folder_id = 0
                # Datatypes container.
                if metadata:
                    if 'datatypes' not in exclude and 'datatypes' in metadata:
                        datatypes = metadata[ 'datatypes' ]
                        folder_id, datatypes_root_folder = self.build_datatypes_folder( folder_id, datatypes )
                        containers_dict[ 'datatypes' ] = datatypes_root_folder
                # Invalid repository dependencies container.
                if metadata:
                    if 'invalid_repository_dependencies' not in exclude and 'invalid_repository_dependencies' in metadata:
                        invalid_repository_dependencies = metadata[ 'invalid_repository_dependencies' ]
                        folder_id, invalid_repository_dependencies_root_folder = \
                            self.build_invalid_repository_dependencies_root_folder( folder_id,
                                                                                    invalid_repository_dependencies )
                        containers_dict[ 'invalid_repository_dependencies' ] = invalid_repository_dependencies_root_folder
                # Invalid agent dependencies container.
                if metadata:
                    if 'invalid_agent_dependencies' not in exclude and 'invalid_agent_dependencies' in metadata:
                        invalid_agent_dependencies = metadata[ 'invalid_agent_dependencies' ]
                        folder_id, invalid_agent_dependencies_root_folder = \
                            self.build_invalid_agent_dependencies_root_folder( folder_id,
                                                                              invalid_agent_dependencies )
                        containers_dict[ 'invalid_agent_dependencies' ] = invalid_agent_dependencies_root_folder
                # Invalid agents container.
                if metadata:
                    if 'invalid_agents' not in exclude and 'invalid_agents' in metadata:
                        invalid_agent_configs = metadata[ 'invalid_agents' ]
                        folder_id, invalid_agents_root_folder = \
                            self.build_invalid_agents_folder( folder_id,
                                                             invalid_agent_configs,
                                                             changeset_revision,
                                                             repository=repository,
                                                             label='Invalid agents' )
                        containers_dict[ 'invalid_agents' ] = invalid_agents_root_folder
                # Readme files container.
                if metadata:
                    if 'readme_files' not in exclude and 'readme_files' in metadata:
                        readme_files_dict = readme_util.build_readme_files_dict( self.app, repository, changeset_revision, metadata )
                        folder_id, readme_files_root_folder = self.build_readme_files_folder( folder_id, readme_files_dict )
                        containers_dict[ 'readme_files' ] = readme_files_root_folder
                if 'repository_dependencies' not in exclude:
                    # Repository dependencies container.
                    folder_id, repository_dependencies_root_folder = \
                        self.build_repository_dependencies_folder( folder_id=folder_id,
                                                                   repository_dependencies=repository_dependencies,
                                                                   label='Repository dependencies',
                                                                   installed=False )
                    if repository_dependencies_root_folder:
                        containers_dict[ 'repository_dependencies' ] = repository_dependencies_root_folder
                # Agent dependencies container.
                if metadata:
                    if 'agent_dependencies' not in exclude and 'agent_dependencies' in metadata:
                        agent_dependencies = metadata[ 'agent_dependencies' ]
                        if 'orphan_agent_dependencies' in metadata:
                            # The use of the orphan_agent_dependencies category in metadata has been deprecated,
                            # but we still need to check in case the metadata is out of date.
                            orphan_agent_dependencies = metadata[ 'orphan_agent_dependencies' ]
                            agent_dependencies.update( orphan_agent_dependencies )
                        # Agent dependencies can be categorized as orphans only if the repository contains agents.
                        if 'agents' not in exclude:
                            agents = metadata.get( 'agents', [] )
                            agents.extend( metadata.get( 'invalid_agents', [] ) )
                        folder_id, agent_dependencies_root_folder = \
                            self.build_agent_dependencies_folder( folder_id,
                                                                 agent_dependencies,
                                                                 missing=False,
                                                                 new_install=False )
                        containers_dict[ 'agent_dependencies' ] = agent_dependencies_root_folder
                # Valid agents container.
                if metadata:
                    if 'agents' not in exclude and 'agents' in metadata:
                        valid_agents = metadata[ 'agents' ]
                        folder_id, valid_agents_root_folder = self.build_agents_folder( folder_id,
                                                                                      valid_agents,
                                                                                      repository,
                                                                                      changeset_revision,
                                                                                      label='Valid agents' )
                        containers_dict[ 'valid_agents' ] = valid_agents_root_folder
                # Agent test results container.
                agent_test_results = util.listify( repository_metadata.agent_test_results )
                # Only create and populate this folder if there are actual agent test results to display.
                if self.can_display_agent_test_results( agent_test_results, exclude=exclude ):
                    folder_id, agent_test_results_root_folder = \
                        self.build_agent_test_results_folder( folder_id,
                                                             agent_test_results,
                                                             label='Agent test results' )
                    containers_dict[ 'agent_test_results' ] = agent_test_results_root_folder
                # Workflows container.
                if metadata:
                    if 'workflows' not in exclude and 'workflows' in metadata:
                        workflows = metadata[ 'workflows' ]
                        folder_id, workflows_root_folder = \
                            self.build_workflows_folder( folder_id=folder_id,
                                                         workflows=workflows,
                                                         repository_metadata_id=repository_metadata.id,
                                                         repository_id=None,
                                                         label='Workflows' )
                        containers_dict[ 'workflows' ] = workflows_root_folder
                # Valid Data Managers container
                if metadata:
                    if 'data_manager' not in exclude and 'data_manager' in metadata:
                        data_managers = metadata['data_manager'].get( 'data_managers', None )
                        folder_id, data_managers_root_folder = \
                            self.build_data_managers_folder( folder_id, data_managers, label="Data Managers" )
                        containers_dict[ 'valid_data_managers' ] = data_managers_root_folder
                        error_messages = metadata['data_manager'].get( 'error_messages', None )
                        data_managers = metadata['data_manager'].get( 'invalid_data_managers', None )
                        folder_id, data_managers_root_folder = \
                            self.build_invalid_data_managers_folder( folder_id,
                                                                     data_managers,
                                                                     error_messages,
                                                                     label="Invalid Data Managers" )
                        containers_dict[ 'invalid_data_managers' ] = data_managers_root_folder
            except Exception, e:
                log.exception( "Exception in build_repository_containers: %s" % str( e ) )
            finally:
                lock.release()
        return containers_dict

    def build_agent_test_results_folder( self, folder_id, agent_test_results_dicts, label='Agent test results' ):
        """Return a folder hierarchy containing agent dependencies."""
        # This container is displayed only in the agent shed.
        if agent_test_results_dicts:
            folder_id += 1
            agent_test_results_root_folder = utility_container_manager.Folder( id=folder_id, key='root', label='root', parent=None )
            multiple_agent_test_results_dicts = len( agent_test_results_dicts ) > 1
            if multiple_agent_test_results_dicts:
                folder_id += 1
                test_runs_folder = utility_container_manager.Folder( id=folder_id,
                                                                     key='test_runs',
                                                                     label='Test runs',
                                                                     parent=agent_test_results_root_folder )
                agent_test_results_root_folder.folders.append( test_runs_folder )
            for index, agent_test_results_dict in enumerate( agent_test_results_dicts ):
                if len( agent_test_results_dict ) < 2:
                    # Skip agent test results that have only a 'test_environment' entry since this implies that only the preparation
                    # script check_repositories_for_functional_tests.py has run for that entry.
                    continue
                # We have a dictionary that looks something like this:
                # {
                #  'missing_test_components': [],
                #  'failed_tests': [],
                #  'passed_tests':
                #        [{'agent_id': 'effectiveT3',
                #          'test_id': 'test_agent_000000 (functional.test_agentbox.TestForAgent_testagentshed.g2.bx.psu.edu/repos/...)',
                #          'agent_version': '0.0.12'},
                #         {'agent_id': 'effectiveT3',
                #          'test_id': 'test_agent_000001 (functional.test_agentbox.TestForAgent_testagentshed.g2.bx.psu.edu/repos/...)',
                #          'agent_version': '0.0.12'}],
                # 'test_environment':
                #    {'python_version': '2.7.4', 'agent_shed_mercurial_version': '2.2.3', 'system': 'Linux 3.8.0-30-generic',
                #     'agent_shed_database_version': 21, 'architecture': 'x86_64', 'galaxy_revision': '11573:a62c54ddbe2a',
                #     'galaxy_database_version': 117, 'time_tested': '2013-12-03 09:11:48', 'agent_shed_revision': '11556:228156daa575'},
                # 'installation_errors': {'current_repository': [], 'repository_dependencies': [], 'agent_dependencies': []},
                # 'successful_installations': {'current_repository': [], 'repository_dependencies': [], 'agent_dependencies': []}
                # }
                test_environment_dict = agent_test_results_dict.get( 'test_environment', None )
                if test_environment_dict is None:
                    # The test environment entry will exist only if the preparation script check_repositories_for_functional_tests.py
                    # was executed prior to the ~/install_and_test_repositories/functional_tests.py script.  If that did not occur,
                    # we'll display test result, but the test_environment entries will not be complete.
                    test_environment_dict = {}
                time_tested = test_environment_dict.get( 'time_tested', 'unknown_%d' % index )
                if multiple_agent_test_results_dicts:
                    folder_id += 1
                    containing_folder = utility_container_manager.Folder( id=folder_id,
                                                                          key='test_results',
                                                                          label=time_tested,
                                                                          parent=test_runs_folder )
                    test_runs_folder.folders.append( containing_folder )
                else:
                    containing_folder = agent_test_results_root_folder
                folder_id += 1
                test_environment_folder = utility_container_manager.Folder( id=folder_id,
                                                                            key='test_environment',
                                                                            label='Automated test environment',
                                                                            parent=containing_folder )
                containing_folder.folders.append( test_environment_folder )
                try:
                    architecture = test_environment_dict.get( 'architecture', '' )
                    galaxy_database_version = test_environment_dict.get( 'galaxy_database_version', '' )
                    galaxy_revision = test_environment_dict.get( 'galaxy_revision', '' )
                    python_version = test_environment_dict.get( 'python_version', '' )
                    system = test_environment_dict.get( 'system', '' )
                    agent_shed_database_version = test_environment_dict.get( 'agent_shed_database_version', '' )
                    agent_shed_mercurial_version = test_environment_dict.get( 'agent_shed_mercurial_version', '' )
                    agent_shed_revision = test_environment_dict.get( 'agent_shed_revision', '' )
                except Exception, e:
                    architecture = str( e )
                    galaxy_database_version = ''
                    galaxy_revision = ''
                    python_version = ''
                    system = ''
                    agent_shed_database_version = ''
                    agent_shed_mercurial_version = ''
                    agent_shed_revision = ''
                test_environment = TestEnvironment( id=1,
                                                    architecture=architecture,
                                                    galaxy_database_version=galaxy_database_version,
                                                    galaxy_revision=galaxy_revision,
                                                    python_version=python_version,
                                                    system=system,
                                                    time_tested=time_tested,
                                                    agent_shed_database_version=agent_shed_database_version,
                                                    agent_shed_mercurial_version=agent_shed_mercurial_version,
                                                    agent_shed_revision=agent_shed_revision )
                test_environment_folder.test_environments.append( test_environment )
                not_tested_dict = agent_test_results_dict.get( 'not_tested', {} )
                if len( not_tested_dict ) > 0:
                    folder_id += 1
                    not_tested_folder = utility_container_manager.Folder( id=folder_id,
                                                                          key='not_tested',
                                                                          label='Not tested',
                                                                          parent=containing_folder )
                    containing_folder.folders.append( not_tested_folder )
                    not_tested_id = 0
                    try:
                        reason = not_tested_dict.get( 'reason', '' )
                    except Exception, e:
                        reason = str( e )
                    not_tested = NotTested( id=not_tested_id, reason=reason )
                    not_tested_folder.not_tested.append( not_tested )
                passed_tests_dicts = agent_test_results_dict.get( 'passed_tests', [] )
                if len( passed_tests_dicts ) > 0:
                    folder_id += 1
                    passed_tests_folder = utility_container_manager.Folder( id=folder_id,
                                                                            key='passed_tests',
                                                                            label='Tests that passed successfully',
                                                                            parent=containing_folder )
                    containing_folder.folders.append( passed_tests_folder )
                    passed_test_id = 0
                    for passed_tests_dict in passed_tests_dicts:
                        passed_test_id += 1
                        try:
                            test_id = passed_tests_dict.get( 'test_id' '' )
                            agent_id = passed_tests_dict.get( 'agent_id', '' )
                            agent_version = passed_tests_dict.get( 'agent_version', '' )
                        except Exception, e:
                            test_id = str( e )
                            agent_id = 'unknown'
                            agent_version = 'unknown'
                        passed_test = PassedTest( id=passed_test_id,
                                                  test_id=test_id,
                                                  agent_id=agent_id,
                                                  agent_version=agent_version )
                        passed_tests_folder.passed_tests.append( passed_test )
                failed_tests_dicts = agent_test_results_dict.get( 'failed_tests', [] )
                if len( failed_tests_dicts ) > 0:
                    folder_id += 1
                    failed_tests_folder = utility_container_manager.Folder( id=folder_id,
                                                                            key='failed_tests',
                                                                            label='Tests that failed',
                                                                            parent=containing_folder )
                    containing_folder.folders.append( failed_tests_folder )
                    failed_test_id = 0
                    for failed_tests_dict in failed_tests_dicts:
                        failed_test_id += 1
                        try:
                            stderr = failed_tests_dict.get( 'stderr', '' )
                            test_id = failed_tests_dict.get( 'test_id', '' )
                            agent_id = failed_tests_dict.get( 'agent_id', '' )
                            agent_version = failed_tests_dict.get( 'agent_version', '' )
                            traceback = failed_tests_dict.get( 'traceback', '' )
                        except Exception, e:
                            stderr = 'unknown'
                            test_id = 'unknown'
                            agent_id = 'unknown'
                            agent_version = 'unknown'
                            traceback = str( e )
                        failed_test = FailedTest( id=failed_test_id,
                                                  stderr=stderr,
                                                  test_id=test_id,
                                                  agent_id=agent_id,
                                                  agent_version=agent_version,
                                                  traceback=traceback )
                        failed_tests_folder.failed_tests.append( failed_test )
                missing_test_components_dicts = agent_test_results_dict.get( 'missing_test_components', [] )
                if len( missing_test_components_dicts ) > 0:
                    folder_id += 1
                    missing_test_components_folder = \
                        utility_container_manager.Folder( id=folder_id,
                                                          key='missing_test_components',
                                                          label='Agents missing tests or test data',
                                                          parent=containing_folder )
                    containing_folder.folders.append( missing_test_components_folder )
                    missing_test_component_id = 0
                    for missing_test_components_dict in missing_test_components_dicts:
                        missing_test_component_id += 1
                        try:
                            missing_components = missing_test_components_dict.get( 'missing_components', '' )
                            agent_guid = missing_test_components_dict.get( 'agent_guid', '' )
                            agent_id = missing_test_components_dict.get( 'agent_id', '' )
                            agent_version = missing_test_components_dict.get( 'agent_version', '' )
                        except Exception, e:
                            missing_components = str( e )
                            agent_guid = 'unknown'
                            agent_id = 'unknown'
                            agent_version = 'unknown'
                        missing_test_component = MissingTestComponent( id=missing_test_component_id,
                                                                       missing_components=missing_components,
                                                                       agent_guid=agent_guid,
                                                                       agent_id=agent_id,
                                                                       agent_version=agent_version )
                        missing_test_components_folder.missing_test_components.append( missing_test_component )
                installation_error_dict = agent_test_results_dict.get( 'installation_errors', {} )
                if len( installation_error_dict ) > 0:
                    # 'installation_errors':
                    #    {'current_repository': [],
                    #     'repository_dependencies': [],
                    #     'agent_dependencies':
                    #        [{'error_message': 'some traceback string' 'type': 'package', 'name': 'MIRA', 'version': '4.0'}]
                    #    }
                    current_repository_installation_error_dicts = installation_error_dict.get( 'current_repository', [] )
                    repository_dependency_installation_error_dicts = installation_error_dict.get( 'repository_dependencies', [] )
                    agent_dependency_installation_error_dicts = installation_error_dict.get( 'agent_dependencies', [] )
                    if len( current_repository_installation_error_dicts ) > 0 or \
                            len( repository_dependency_installation_error_dicts ) > 0 or \
                            len( agent_dependency_installation_error_dicts ) > 0:
                        repository_installation_error_id = 0
                        folder_id += 1
                        installation_error_base_folder = utility_container_manager.Folder( id=folder_id,
                                                                                           key='installation_errors',
                                                                                           label='Installation errors',
                                                                                           parent=containing_folder )
                        containing_folder.folders.append( installation_error_base_folder )
                        if len( current_repository_installation_error_dicts ) > 0:
                            folder_id += 1
                            current_repository_folder = \
                                utility_container_manager.Folder( id=folder_id,
                                                                  key='current_repository_installation_errors',
                                                                  label='This repository',
                                                                  parent=installation_error_base_folder )
                            installation_error_base_folder.folders.append( current_repository_folder )
                            for current_repository_error_dict in current_repository_installation_error_dicts:
                                repository_installation_error_id += 1
                                try:
                                    r_agent_shed = str( current_repository_error_dict.get( 'agent_shed', '' ) )
                                    r_name = str( current_repository_error_dict.get( 'name', '' ) )
                                    r_owner = str( current_repository_error_dict.get( 'owner', '' ) )
                                    r_changeset_revision = str( current_repository_error_dict.get( 'changeset_revision', '' ) )
                                    r_error_message = current_repository_error_dict.get( 'error_message', '' )
                                except Exception, e:
                                    r_agent_shed = 'unknown'
                                    r_name = 'unknown'
                                    r_owner = 'unknown'
                                    r_changeset_revision = 'unknown'
                                    r_error_message = str( e )
                                repository_installation_error = RepositoryInstallationError( id=repository_installation_error_id,
                                                                                             agent_shed=r_agent_shed,
                                                                                             name=r_name,
                                                                                             owner=r_owner,
                                                                                             changeset_revision=r_changeset_revision,
                                                                                             error_message=r_error_message )
                                current_repository_folder.current_repository_installation_errors.append( repository_installation_error )
                        if len( repository_dependency_installation_error_dicts ) > 0:
                            folder_id += 1
                            repository_dependencies_folder = \
                                utility_container_manager.Folder( id=folder_id,
                                                                  key='repository_dependency_installation_errors',
                                                                  label='Repository dependencies',
                                                                  parent=installation_error_base_folder )
                            installation_error_base_folder.folders.append( repository_dependencies_folder )
                            for repository_dependency_error_dict in repository_dependency_installation_error_dicts:
                                repository_installation_error_id += 1
                                try:
                                    rd_agent_shed = str( repository_dependency_error_dict.get( 'agent_shed', '' ) )
                                    rd_name = str( repository_dependency_error_dict.get( 'name', '' ) )
                                    rd_owner = str( repository_dependency_error_dict.get( 'owner', '' ) )
                                    rd_changeset_revision = str( repository_dependency_error_dict.get( 'changeset_revision', '' ) )
                                    rd_error_message = repository_dependency_error_dict.get( 'error_message', '' )
                                except Exception, e:
                                    rd_agent_shed = 'unknown'
                                    rd_name = 'unknown'
                                    rd_owner = 'unknown'
                                    rd_changeset_revision = 'unknown'
                                    rd_error_message = str( e )
                                repository_installation_error = RepositoryInstallationError( id=repository_installation_error_id,
                                                                                             agent_shed=rd_agent_shed,
                                                                                             name=rd_name,
                                                                                             owner=rd_owner,
                                                                                             changeset_revision=rd_changeset_revision,
                                                                                             error_message=rd_error_message )
                                repository_dependencies_folder.repository_installation_errors.append( repository_installation_error )
                        if len( agent_dependency_installation_error_dicts ) > 0:
                            # [{'error_message': 'some traceback string' 'type': 'package', 'name': 'MIRA', 'version': '4.0'}]
                            folder_id += 1
                            agent_dependencies_folder = \
                                utility_container_manager.Folder( id=folder_id,
                                                                  key='agent_dependency_installation_errors',
                                                                  label='Agent dependencies',
                                                                  parent=installation_error_base_folder )
                            installation_error_base_folder.folders.append( agent_dependencies_folder )
                            agent_dependency_error_id = 0
                            for agent_dependency_error_dict in agent_dependency_installation_error_dicts:
                                agent_dependency_error_id += 1
                                try:
                                    td_type = str( agent_dependency_error_dict.get( 'type', '' ) )
                                    td_name = str( agent_dependency_error_dict.get( 'name', '' ) )
                                    td_version = str( agent_dependency_error_dict.get( 'version', '' ) )
                                    td_error_message = agent_dependency_error_dict.get( 'error_message', '' )
                                except Exception, e:
                                    td_type = 'unknown'
                                    td_name = 'unknown'
                                    td_version = 'unknown'
                                    td_error_message = str( e )
                                agent_dependency_installation_error = AgentDependencyInstallationError( id=agent_dependency_error_id,
                                                                                                      type=td_type,
                                                                                                      name=td_name,
                                                                                                      version=td_version,
                                                                                                      error_message=td_error_message )
                                agent_dependencies_folder.agent_dependency_installation_errors.append( agent_dependency_installation_error )
                successful_installation_dict = agent_test_results_dict.get( 'successful_installations', {} )
                if len( successful_installation_dict ) > 0:
                    # 'successful_installation':
                    #    {'current_repository': [],
                    #     'repository_dependencies': [],
                    #     'agent_dependencies':
                    #        [{'installation_directory': 'some path' 'type': 'package', 'name': 'MIRA', 'version': '4.0'}]
                    #    }
                    # We won't display the current repository in this container.  I fit is not displaying installation errors,
                    # then it must be a successful installation.
                    repository_dependency_successful_installation_dicts = successful_installation_dict.get( 'repository_dependencies', [] )
                    agent_dependency_successful_installation_dicts = successful_installation_dict.get( 'agent_dependencies', [] )
                    if len( repository_dependency_successful_installation_dicts ) > 0 or \
                            len( agent_dependency_successful_installation_dicts ) > 0:
                        repository_installation_success_id = 0
                        folder_id += 1
                        successful_installation_base_folder = \
                            utility_container_manager.Folder( id=folder_id,
                                                              key='successful_installations',
                                                              label='Successful installations',
                                                              parent=containing_folder )
                        containing_folder.folders.append( successful_installation_base_folder )
                        # Displaying the successful installation of the current repository is not really necessary, so we'll skip it.
                        if len( repository_dependency_successful_installation_dicts ) > 0:
                            folder_id += 1
                            repository_dependencies_folder = \
                                utility_container_manager.Folder( id=folder_id,
                                                                  key='repository_dependency_successful_installations',
                                                                  label='Repository dependencies',
                                                                  parent=successful_installation_base_folder )
                            successful_installation_base_folder.folders.append( repository_dependencies_folder )
                            for repository_dependency_successful_installation_dict in repository_dependency_successful_installation_dicts:
                                repository_installation_success_id += 1
                                try:
                                    rd_agent_shed = str( repository_dependency_successful_installation_dict.get( 'agent_shed', '' ) )
                                    rd_name = str( repository_dependency_successful_installation_dict.get( 'name', '' ) )
                                    rd_owner = str( repository_dependency_successful_installation_dict.get( 'owner', '' ) )
                                    rd_changeset_revision = \
                                        str( repository_dependency_successful_installation_dict.get( 'changeset_revision', '' ) )
                                except Exception, e:
                                    rd_agent_shed = 'unknown'
                                    rd_name = 'unknown'
                                    rd_owner = 'unknown'
                                    rd_changeset_revision = 'unknown'
                                repository_installation_success = \
                                    RepositorySuccessfulInstallation( id=repository_installation_success_id,
                                                                      agent_shed=rd_agent_shed,
                                                                      name=rd_name,
                                                                      owner=rd_owner,
                                                                      changeset_revision=rd_changeset_revision )
                                repository_dependencies_folder.repository_successful_installations.append( repository_installation_success )
                        if len( agent_dependency_successful_installation_dicts ) > 0:
                            # [{'installation_directory': 'some path' 'type': 'package', 'name': 'MIRA', 'version': '4.0'}]
                            folder_id += 1
                            agent_dependencies_folder = \
                                utility_container_manager.Folder( id=folder_id,
                                                                  key='agent_dependency_successful_installations',
                                                                  label='Agent dependencies',
                                                                  parent=successful_installation_base_folder )
                            successful_installation_base_folder.folders.append( agent_dependencies_folder )
                            agent_dependency_error_id = 0
                            for agent_dependency_successful_installation_dict in agent_dependency_successful_installation_dicts:
                                agent_dependency_error_id += 1
                                try:
                                    td_type = str( agent_dependency_successful_installation_dict.get( 'type', '' ) )
                                    td_name = str( agent_dependency_successful_installation_dict.get( 'name', '' ) )
                                    td_version = str( agent_dependency_successful_installation_dict.get( 'version', '' ) )
                                    td_installation_directory = agent_dependency_successful_installation_dict.get( 'installation_directory', '' )
                                except Exception, e:
                                    td_type = 'unknown'
                                    td_name = 'unknown'
                                    td_version = 'unknown'
                                    td_installation_directory = str( e )
                                agent_dependency_successful_installation = \
                                    AgentDependencySuccessfulInstallation( id=agent_dependency_error_id,
                                                                          type=td_type,
                                                                          name=td_name,
                                                                          version=td_version,
                                                                          installation_directory=td_installation_directory )
                                agent_dependencies_folder.agent_dependency_successful_installations.append( agent_dependency_successful_installation )
        else:
            agent_test_results_root_folder = None
        return folder_id, agent_test_results_root_folder

    def can_display_agent_test_results( self, agent_test_results_dicts, exclude=None ):
        # Only create and populate the agent_test_results container if there are actual agent test results to display.
        if exclude is None:
            exclude = []
        if 'agent_test_results' in exclude:
            return False
        for agent_test_results_dict in agent_test_results_dicts:
            # We check for more than a single entry in the agent_test_results dictionary because it may have
            # only the "test_environment" entry, but we want at least 1 of "passed_tests", "failed_tests",
            # "installation_errors", "missing_test_components" "skipped_tests", "not_tested" or any other
            # entry that may be added in the future.
            display_entries = [ 'failed_tests', 'installation_errors', 'missing_test_components',
                                'not_tested', 'passed_tests', 'skipped_tests' ]
            for k, v in agent_test_results_dict.items():
                if k in display_entries:
                    # We've discovered an entry that can be displayed, so see if it has a value since displaying
                    # empty lists is not desired.
                    if v:
                        return True
        return False

    def generate_agent_dependencies_key( self, name, version, type ):
        return '%s%s%s%s%s' % ( str( name ), container_util.STRSEP, str( version ), container_util.STRSEP, str( type ) )
