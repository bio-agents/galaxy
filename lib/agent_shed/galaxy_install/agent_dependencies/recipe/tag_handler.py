import logging
import os
import tempfile

from sqlalchemy import and_

from galaxy.agents.deps.resolvers import INDETERMINATE_DEPENDENCY
from galaxy.util import listify
from agent_shed.util import basic_util
from agent_shed.util import common_util
from agent_shed.util import shed_util_common as suc
from agent_shed.util import agent_dependency_util
from agent_shed.util import xml_util

from agent_shed.galaxy_install.agent_dependencies.env_manager import EnvManager
from agent_shed.galaxy_install.agent_dependencies.recipe.env_file_builder import EnvFileBuilder
from agent_shed.galaxy_install.agent_dependencies.recipe.install_environment import InstallEnvironment

log = logging.getLogger( __name__ )


class RecipeTag( object ):
    """Abstract class that defines a standard format for handling recipe tags when installing packages."""

    def process_tag_set( self, agent_shed_repository, agent_dependency, package_elem, package_name, package_version,
                         from_agent_migration_manager=False, agent_dependency_db_records=None ):
        raise "Unimplemented Method"


class SyncDatabase( object ):

    def sync_database_with_file_system( self, app, agent_shed_repository, agent_dependency_name, agent_dependency_version,
                                        agent_dependency_install_dir, agent_dependency_type='package' ):
        """
        The installation directory defined by the received agent_dependency_install_dir exists, so check for
        the presence of INSTALLATION_LOG.  If the files exists, we'll assume the agent dependency is installed,
        but not necessarily successfully (it could be in an error state on disk.  However, we can justifiably
        assume here that no matter the state, an associated database record will exist.
        """
        # This method should be reached very rarely.  It implies that either the Galaxy environment
        # became corrupted (i.e., the database records for installed agent dependencies is not synchronized
        # with agent dependencies on disk) or the Agent Shed's install and test framework is running.  The Agent
        # Shed's install and test framework installs repositories in 2 stages, those of type agent_dependency_definition
        # followed by those containing valid agents and agent functional test components.
        log.debug( "Synchronizing the database with the file system..." )
        try:
            log.debug( "The value of app.config.running_functional_tests is: %s" %
                str( app.config.running_functional_tests ) )
        except:
            pass
        sa_session = app.install_model.context
        can_install_agent_dependency = False
        agent_dependency = \
            agent_dependency_util.get_agent_dependency_by_name_version_type_repository( app,
                                                                                      agent_shed_repository,
                                                                                      agent_dependency_name,
                                                                                      agent_dependency_version,
                                                                                      agent_dependency_type )
        if agent_dependency.status == app.install_model.AgentDependency.installation_status.INSTALLING:
            # The agent dependency is in an Installing state, so we don't want to do anything to it.  If the agent
            # dependency is being installed by someone else, we don't want to interfere with that.  This assumes
            # the installation by "someone else" is not hung in an Installing state, which is a weakness if that
            # "someone else" never repaired it.
            log.debug( 'Skipping installation of agent dependency %s version %s because it has a status of %s' %
                ( str( agent_dependency.name ), str( agent_dependency.version ), str( agent_dependency.status ) ) )
        else:
            # We have a pre-existing installation directory on the file system, but our associated database record is
            # in a state that allowed us to arrive here.  At this point, we'll inspect the installation directory to
            # see if we have a "proper installation" and if so, synchronize the database record rather than reinstalling
            # the dependency if we're "running_functional_tests".  If we're not "running_functional_tests, we'll set
            # the agent dependency's installation status to ERROR.
            agent_dependency_installation_directory_contents = os.listdir( agent_dependency_install_dir )
            if basic_util.INSTALLATION_LOG in agent_dependency_installation_directory_contents:
                # Since this agent dependency's installation directory contains an installation log, we consider it to be
                # installed.  In some cases the record may be missing from the database due to some activity outside of
                # the control of the Agent Shed.  Since a new record was created for it and we don't know the state of the
                # files on disk, we will set it to an error state (unless we are running Agent Shed functional tests - see
                # below).
                log.debug( 'Skipping installation of agent dependency %s version %s because it is installed in %s' %
                    ( str( agent_dependency.name ), str( agent_dependency.version ), str( agent_dependency_install_dir ) ) )
                if app.config.running_functional_tests:
                    # If we are running functional tests, the state will be set to Installed because previously compiled
                    # agent dependencies are not deleted by default, from the "install and test" framework..
                    agent_dependency.status = app.install_model.AgentDependency.installation_status.INSTALLED
                else:
                    error_message = 'The installation directory for this agent dependency had contents but the database had no record. '
                    error_message += 'The installation log may show this agent dependency to be correctly installed, but due to the '
                    error_message += 'missing database record it is now being set to Error.'
                    agent_dependency.status = app.install_model.AgentDependency.installation_status.ERROR
                    agent_dependency.error_message = error_message
            else:
                error_message = '\nInstallation path %s for agent dependency %s version %s exists, but the expected file %s' % \
                    ( str( agent_dependency_install_dir ),
                      str( agent_dependency_name ),
                      str( agent_dependency_version ),
                      str( basic_util.INSTALLATION_LOG ) )
                error_message += ' is missing.  This indicates an installation error so the agent dependency is being'
                error_message += ' prepared for re-installation.'
                log.error( error_message )
                agent_dependency.status = app.install_model.AgentDependency.installation_status.NEVER_INSTALLED
                basic_util.remove_dir( agent_dependency_install_dir )
                can_install_agent_dependency = True
            sa_session.add( agent_dependency )
            sa_session.flush()
        try:
            log.debug( "Returning from sync_database_with_file_system with agent_dependency %s, can_install_agent_dependency %s." %
                ( str( agent_dependency.name ), str( can_install_agent_dependency ) ) )
        except Exception, e:
            log.debug( str( e ) )
        return agent_dependency, can_install_agent_dependency


class Install( RecipeTag, SyncDatabase ):

    def __init__( self, app ):
        self.app = app
        self.tag = 'install'

    def process_tag_set( self, agent_shed_repository, agent_dependency, package_elem, package_name, package_version,
                         from_agent_migration_manager=False, agent_dependency_db_records=None ):
        # <install version="1.0">
        # Get the installation directory for agent dependencies that will be installed for the received agent_shed_repository.
        actions_elem_tuples = []
        proceed_with_install = False
        install_dir = \
            agent_dependency_util.get_agent_dependency_install_dir( app=self.app,
                                                                  repository_name=agent_shed_repository.name,
                                                                  repository_owner=agent_shed_repository.owner,
                                                                  repository_changeset_revision=agent_shed_repository.installed_changeset_revision,
                                                                  agent_dependency_type='package',
                                                                  agent_dependency_name=package_name,
                                                                  agent_dependency_version=package_version )
        if os.path.exists( install_dir ):
            # The agent_migration_manager handles agent migration stages and the sync_database_with_file_system()
            # method handles two scenarios: (1) where a Galaxy file system environment related to installed
            # Agent Shed repositories and agent dependencies has somehow gotten out of sync with the Galaxy
            # database tables associated with these installed items, and (2) the Agent Shed's install and test
            # framework which installs repositories in 2 stages, those of type agent_dependency_definition
            # followed by those containing valid agents and agent functional test components.  Neither of these
            # scenarios apply when the install manager is running.
            if from_agent_migration_manager:
                proceed_with_install = True
            else:
                # Notice that we'll throw away the following agent_dependency if it can be installed.
                agent_dependency, proceed_with_install = self.sync_database_with_file_system( self.app,
                                                                                             agent_shed_repository,
                                                                                             package_name,
                                                                                             package_version,
                                                                                             install_dir,
                                                                                             agent_dependency_type='package' )
                if not proceed_with_install:
                    log.debug( "Agent dependency %s version %s cannot be installed (it was probably previously installed), so returning it." %
                        ( str( agent_dependency.name ), str( agent_dependency.version ) ) )
                    return agent_dependency, proceed_with_install, actions_elem_tuples
        else:
            proceed_with_install = True
        if proceed_with_install:
            package_install_version = package_elem.get( 'version', '1.0' )
            status = self.app.install_model.AgentDependency.installation_status.INSTALLING
            agent_dependency = \
                agent_dependency_util.create_or_update_agent_dependency( app=self.app,
                                                                       agent_shed_repository=agent_shed_repository,
                                                                       name=package_name,
                                                                       version=package_version,
                                                                       type='package',
                                                                       status=status,
                                                                       set_status=True )
            # Get the information about the current platform in case the agent dependency definition includes tag sets
            # for installing compiled binaries.
            platform_info_dict = agent_dependency_util.get_platform_info_dict()
            if package_install_version == '1.0':
                # Handle agent dependency installation using a fabric method included in the Galaxy framework.
                actions_elem_tuples = agent_dependency_util.parse_package_elem( package_elem,
                                                                               platform_info_dict=platform_info_dict,
                                                                               include_after_install_actions=True )
                if not actions_elem_tuples:
                    proceed_with_install = False
                    error_message = 'Version %s of the %s package cannot be installed because ' % ( str( package_version ), str( package_name ) )
                    error_message += 'the recipe for installing the package is missing either an &lt;actions&gt; tag set or an &lt;actions_group&gt; '
                    error_message += 'tag set.'
                    # Since there was an installation error, update the agent dependency status to Error.
                    # The remove_installation_path option must be left False here.
                    agent_dependency = agent_dependency_util.set_agent_dependency_attributes(self.app,
                                                                                          agent_dependency=agent_dependency,
                                                                                          status=self.app.install_model.AgentDependency.installation_status.ERROR,
                                                                                          error_message=error_message)
            else:
                raise NotImplementedError( 'Only install version 1.0 is currently supported (i.e., change your tag to be <install version="1.0">).' )
        return agent_dependency, proceed_with_install, actions_elem_tuples


class Package( RecipeTag ):

    def __init__( self, app ):
        self.app = app
        self.tag = 'package'

    def process_tag_set( self, agent_shed_repository, agent_dependency, package_elem, package_name, package_version,
                         from_agent_migration_manager=False, agent_dependency_db_records=None ):
        action_elem_tuples = []
        proceed_with_install = False
        # Only install the agent_dependency if it is not already installed and it is associated with a database
        # record in the received agent_dependencies.
        if package_name and package_version:
            dependencies_ignored = not self.app.agentbox.dependency_manager.uses_agent_shed_dependencies()
            if dependencies_ignored:
                log.debug( "Skipping installation of agent dependency package %s because agent shed dependency resolver not enabled." %
                    str( package_name ) )
                # Agent dependency resolves have been configured and they do not include the agent shed. Do not install package.
                if self.app.agentbox.dependency_manager.find_dep( package_name, package_version, type='package') != INDETERMINATE_DEPENDENCY:
                    # TODO: Do something here such as marking it installed or configured externally.
                    pass
                agent_dependency = \
                    agent_dependency_util.set_agent_dependency_attributes( self.app,
                                                                         agent_dependency=agent_dependency,
                                                                         status=self.app.install_model.AgentDependency.installation_status.ERROR )
            else:
                proceed_with_install = True
        return agent_dependency, proceed_with_install, action_elem_tuples


class ReadMe( RecipeTag ):

    def __init__( self, app ):
        self.app = app
        self.tag = 'readme'

    def process_tag_set( self, agent_shed_repository, agent_dependency, package_elem, package_name, package_version,
                         from_agent_migration_manager=False, agent_dependency_db_records=None ):
        # Nothing to be done.
        action_elem_tuples = []
        proceed_with_install = False
        return agent_dependency, proceed_with_install, action_elem_tuples


class Repository( RecipeTag, SyncDatabase ):

    def __init__( self, app ):
        self.app = app
        self.tag = 'repository'

    def create_temporary_agent_dependencies_config( self, agent_shed_url, name, owner, changeset_revision ):
        """Make a call to the agent shed to get the required repository's agent_dependencies.xml file."""
        agent_shed_url = common_util.get_agent_shed_url_from_agent_shed_registry( self.app, agent_shed_url )
        if agent_shed_url is None or name is None or owner is None or changeset_revision is None:
            message = "Unable to retrieve required agent_dependencies.xml file from the Agent Shed because one or more of the "
            message += "following required parameters is None: agent_shed_url: %s, name: %s, owner: %s, changeset_revision: %s " % \
                ( str( agent_shed_url ), str( name ), str( owner ), str( changeset_revision ) )
            raise Exception( message )
        params = dict( name=name,
                       owner=owner,
                       changeset_revision=changeset_revision )
        pathspec = [ 'repository', 'get_agent_dependencies_config_contents' ]
        text = common_util.agent_shed_get( self.app, agent_shed_url, pathspec=pathspec, params=params )
        if text:
            # Write the contents to a temporary file on disk so it can be reloaded and parsed.
            fh = tempfile.NamedTemporaryFile( 'wb', prefix="tmp-agentshed-cttdc"  )
            tmp_filename = fh.name
            fh.close()
            fh = open( tmp_filename, 'wb' )
            fh.write( text )
            fh.close()
            return tmp_filename
        else:
            message = "Unable to retrieve required agent_dependencies.xml file from the Agent Shed for revision "
            message += "%s of installed repository %s owned by %s." % ( str( changeset_revision ), str( name ), str( owner ) )
            raise Exception( message )
            return None

    def create_agent_dependency_with_initialized_env_sh_file( self, dependent_install_dir, agent_shed_repository,
                                                             required_repository, package_name, package_version,
                                                             agent_dependencies_config ):
        """
        Create or get a agent_dependency record that is defined by the received package_name and package_version.
        An env.sh file will be created for the agent_dependency in the received dependent_install_dir.
        """
        # The received required_repository refers to a agent_shed_repository record that is defined as a complex
        # repository dependency for this agent_dependency.  The required_repository may or may not be currently
        # installed (it doesn't matter).  If it is installed, it is associated with a agent_dependency that has
        # an env.sh file that this new agent_dependency must be able to locate and "source".  If it is not installed,
        # we can still determine where that env.sh file will be, so we'll initialize this new agent_dependency's env.sh
        # file in either case.  If the required repository ends up with an installation error, this new agent
        # dependency will still be fine because its containing repository will be defined as missing dependencies.
        agent_dependencies = []
        if not os.path.exists( dependent_install_dir ):
            os.makedirs( dependent_install_dir )
        required_agent_dependency_env_file_path = None
        if agent_dependencies_config:
            required_td_tree, error_message = xml_util.parse_xml( agent_dependencies_config )
            if required_td_tree:
                required_td_root = required_td_tree.getroot()
                for required_td_elem in required_td_root:
                    # Find the appropriate package name and version.
                    if required_td_elem.tag == 'package':
                        # <package name="bwa" version="0.5.9">
                        required_td_package_name = required_td_elem.get( 'name', None )
                        required_td_package_version = required_td_elem.get( 'version', None )
                        # Check the database to see if we have a record for the required agent dependency (we may not which is ok).  If we
                        # find a record, we need to see if it is in an error state and if so handle it appropriately.
                        required_agent_dependency = \
                            agent_dependency_util.get_agent_dependency_by_name_version_type_repository( self.app,
                                                                                                      required_repository,
                                                                                                      required_td_package_name,
                                                                                                      required_td_package_version,
                                                                                                      'package' )
                        if required_td_package_name == package_name and required_td_package_version == package_version:
                            # Get or create a database agent_dependency record with which the installed package on disk will be associated.
                            agent_dependency = \
                                agent_dependency_util.create_or_update_agent_dependency( app=self.app,
                                                                                       agent_shed_repository=agent_shed_repository,
                                                                                       name=package_name,
                                                                                       version=package_version,
                                                                                       type='package',
                                                                                       status=self.app.install_model.AgentDependency.installation_status.NEVER_INSTALLED,
                                                                                       set_status=True )
                            # Create an env.sh file for the agent_dependency whose first line will source the env.sh file located in
                            # the path defined by required_agent_dependency_env_file_path.  It doesn't matter if the required env.sh
                            # file currently exists..
                            required_agent_dependency_env_file_path = \
                                self.get_required_repository_package_env_sh_path( package_name,
                                                                                  package_version,
                                                                                  required_repository )
                            env_file_builder = EnvFileBuilder( agent_dependency.installation_directory( self.app ) )
                            env_file_builder.append_line( action="source", value=required_agent_dependency_env_file_path )
                            return_code = env_file_builder.return_code
                            if return_code:
                                error_message = 'Error defining env.sh file for package %s, return_code: %s' % \
                                    ( str( package_name ), str( return_code ) )
                                agent_dependency = \
                                    agent_dependency_util.set_agent_dependency_attributes(self.app,
                                                                                        agent_dependency=agent_dependency,
                                                                                        status=self.app.install_model.AgentDependency.installation_status.ERROR,
                                                                                        error_message=error_message)
                            elif required_agent_dependency is not None and required_agent_dependency.in_error_state:
                                error_message = "This agent dependency's required agent dependency %s version %s has status %s." % \
                                    ( str( required_agent_dependency.name ), str( required_agent_dependency.version ), str( required_agent_dependency.status ) )
                                agent_dependency = \
                                    agent_dependency_util.set_agent_dependency_attributes(self.app,
                                                                                        agent_dependency=agent_dependency,
                                                                                        status=self.app.install_model.AgentDependency.installation_status.ERROR,
                                                                                        error_message=error_message)
                            else:
                                agent_dependency = \
                                    agent_dependency_util.set_agent_dependency_attributes( self.app,
                                                                                         agent_dependency=agent_dependency,
                                                                                         status=self.app.install_model.AgentDependency.installation_status.INSTALLED )
                            agent_dependencies.append( agent_dependency )
        return agent_dependencies

    def get_required_repository_package_env_sh_path( self, package_name, package_version, required_repository ):
        """Return path to env.sh file in required repository if the required repository has been installed."""
        env_sh_file_dir = \
            agent_dependency_util.get_agent_dependency_install_dir( app=self.app,
                                                                  repository_name=required_repository.name,
                                                                  repository_owner=required_repository.owner,
                                                                  repository_changeset_revision=required_repository.installed_changeset_revision,
                                                                  agent_dependency_type='package',
                                                                  agent_dependency_name=package_name,
                                                                  agent_dependency_version=package_version )
        env_sh_file_path = os.path.join( env_sh_file_dir, 'env.sh' )
        return env_sh_file_path

    def get_agent_shed_repository_by_agent_shed_name_owner_changeset_revision( self, agent_shed_url, name, owner, changeset_revision ):
        sa_session = self.app.install_model.context
        # The protocol is not stored, but the port is if it exists.
        agent_shed = common_util.remove_protocol_from_agent_shed_url( agent_shed_url )
        agent_shed_repository = sa_session.query( self.app.install_model.AgentShedRepository ) \
                                         .filter( and_( self.app.install_model.AgentShedRepository.table.c.agent_shed == agent_shed,
                                                        self.app.install_model.AgentShedRepository.table.c.name == name,
                                                        self.app.install_model.AgentShedRepository.table.c.owner == owner,
                                                        self.app.install_model.AgentShedRepository.table.c.changeset_revision == changeset_revision ) ) \
                                         .first()
        if agent_shed_repository:
            return agent_shed_repository
        # The agent_shed_repository must have been updated to a newer changeset revision than the one defined in the repository_dependencies.xml file,
        # so call the agent shed to get all appropriate newer changeset revisions.
        text = suc.get_updated_changeset_revisions_from_agent_shed( self.app, agent_shed_url, name, owner, changeset_revision )
        if text:
            changeset_revisions = listify( text )
            for changeset_revision in changeset_revisions:
                agent_shed_repository = sa_session.query( self.app.install_model.AgentShedRepository ) \
                                                 .filter( and_( self.app.install_model.AgentShedRepository.table.c.agent_shed == agent_shed,
                                                                self.app.install_model.AgentShedRepository.table.c.name == name,
                                                                self.app.install_model.AgentShedRepository.table.c.owner == owner,
                                                                self.app.install_model.AgentShedRepository.table.c.changeset_revision == changeset_revision ) ) \
                                                 .first()
                if agent_shed_repository:
                    return agent_shed_repository
        return None

    def handle_complex_repository_dependency_for_package( self, elem, package_name, package_version, agent_shed_repository,
                                                          from_agent_migration_manager=False ):
        """
        Inspect the repository defined by a complex repository dependency definition and take certain steps to
        enable installation of the received package name and version to proceed.  The received elem is the
        <repository> tag set which defines the complex repository dependency.  The received agent_shed_repository
        is the installed agent shed repository for which the agent dependency defined by the received package_name
        and package_version is being installed.
        """
        handled_agent_dependencies = []
        agent_shed = elem.attrib[ 'agentshed' ]
        # The protocol is not stored, but the port is if it exists.
        agent_shed = common_util.remove_protocol_from_agent_shed_url( agent_shed )
        required_repository_name = elem.attrib[ 'name' ]
        required_repository_owner = elem.attrib[ 'owner' ]
        default_required_repository_changeset_revision = elem.attrib[ 'changeset_revision' ]
        required_repository = \
            self.get_agent_shed_repository_by_agent_shed_name_owner_changeset_revision( agent_shed,
                                                                                      required_repository_name,
                                                                                      required_repository_owner,
                                                                                      default_required_repository_changeset_revision )
        tmp_filename = None
        if required_repository:
            required_repository_changeset_revision = required_repository.installed_changeset_revision
            # Define the installation directory for the required agent dependency package in the required repository.
            required_repository_package_install_dir = \
                agent_dependency_util.get_agent_dependency_install_dir( app=self.app,
                                                                      repository_name=required_repository_name,
                                                                      repository_owner=required_repository_owner,
                                                                      repository_changeset_revision=required_repository_changeset_revision,
                                                                      agent_dependency_type='package',
                                                                      agent_dependency_name=package_name,
                                                                      agent_dependency_version=package_version )
            # Define this dependent repository's agent dependency installation directory that will contain
            # the env.sh file with a path to the required repository's installed agent dependency package.
            dependent_install_dir = \
                agent_dependency_util.get_agent_dependency_install_dir( app=self.app,
                                                                      repository_name=agent_shed_repository.name,
                                                                      repository_owner=agent_shed_repository.owner,
                                                                      repository_changeset_revision=agent_shed_repository.installed_changeset_revision,
                                                                      agent_dependency_type='package',
                                                                      agent_dependency_name=package_name,
                                                                      agent_dependency_version=package_version )
            if os.path.exists( dependent_install_dir ):
                # The install manager handles agent migration stages and the sync_database_with_file_system()
                # method handles two scenarios: (1) where a Galaxy file system environment related to installed
                # Agent Shed repositories and agent dependencies has somehow gotten out of sync with the Galaxy
                # database tables associated with these installed items, and (2) the Agent Shed's install and test
                # framework which installs repositories in 2 stages, those of type agent_dependency_definition
                # followed by those containing valid agents and agent functional test components.  Neither of these
                # scenarios apply when the install manager is running.
                if from_agent_migration_manager:
                    can_install_agent_dependency = True
                else:
                    # Notice that we'll throw away the following agent_dependency if it can be installed.
                    agent_dependency, can_install_agent_dependency = self.sync_database_with_file_system( self.app,
                                                                                                        agent_shed_repository,
                                                                                                        package_name,
                                                                                                        package_version,
                                                                                                        dependent_install_dir,
                                                                                                        agent_dependency_type='package' )
                    if not can_install_agent_dependency:
                        log.debug( "Agent dependency %s version %s cannot be installed (it was probably previously installed), " %
                            ( str( agent_dependency.name, str( agent_dependency.version ) ) ) )
                        log.debug( "so appending it to the list of handled agent dependencies." )
                        handled_agent_dependencies.append( agent_dependency )
            else:
                can_install_agent_dependency = True
            if can_install_agent_dependency:
                # Set this dependent repository's agent dependency env.sh file with a path to the required repository's
                # installed agent dependency package.  We can get everything we need from the discovered installed
                # required_repository.
                if required_repository.is_deactivated_or_installed:
                    if not os.path.exists( required_repository_package_install_dir ):
                        log.error( 'Missing required agent dependency directory %s' % str( required_repository_package_install_dir ) )
                    repo_files_dir = required_repository.repo_files_directory( self.app )
                    if not repo_files_dir:
                        message = "Unable to locate the repository directory for revision %s of installed repository %s owned by %s." % \
                            ( str( required_repository.changeset_revision ), str( required_repository.name ), str( required_repository.owner ) )
                        raise Exception( message )
                    agent_dependencies_config = suc.get_absolute_path_to_file_in_repository( repo_files_dir, 'agent_dependencies.xml' )
                    if agent_dependencies_config:
                        config_to_use = agent_dependencies_config
                    else:
                        message = "Unable to locate required agent_dependencies.xml file for revision %s of installed repository %s owned by %s." % \
                            ( str( required_repository.changeset_revision ), str( required_repository.name ), str( required_repository.owner ) )
                        raise Exception( message )
                else:
                    # Make a call to the agent shed to get the changeset revision to which the current value of required_repository_changeset_revision
                    # should be updated if it's not current.
                    text = suc.get_updated_changeset_revisions_from_agent_shed( app=self.app,
                                                                               agent_shed_url=agent_shed,
                                                                               name=required_repository_name,
                                                                               owner=required_repository_owner,
                                                                               changeset_revision=required_repository_changeset_revision )
                    if text:
                        updated_changeset_revisions = listify( text )
                        # The list of changeset revisions is in reverse order, so the newest will be first.
                        required_repository_changeset_revision = updated_changeset_revisions[ 0 ]
                    # Make a call to the agent shed to get the required repository's agent_dependencies.xml file.
                    tmp_filename = self.create_temporary_agent_dependencies_config( agent_shed,
                                                                                   required_repository_name,
                                                                                   required_repository_owner,
                                                                                   required_repository_changeset_revision )
                    config_to_use = tmp_filename
                handled_agent_dependencies = \
                    self.create_agent_dependency_with_initialized_env_sh_file( dependent_install_dir=dependent_install_dir,
                                                                              agent_shed_repository=agent_shed_repository,
                                                                              required_repository=required_repository,
                                                                              package_name=package_name,
                                                                              package_version=package_version,
                                                                              agent_dependencies_config=config_to_use )
                self.remove_file( tmp_filename )
        else:
            message = "Unable to locate required agent shed repository named %s owned by %s with revision %s." % \
                ( str( required_repository_name ), str( required_repository_owner ), str( default_required_repository_changeset_revision ) )
            raise Exception( message )
        return handled_agent_dependencies

    def process_tag_set( self, agent_shed_repository, agent_dependency, package_elem, package_name, package_version,
                         from_agent_migration_manager=False, agent_dependency_db_records=None ):
        # We have a complex repository dependency definition.
        action_elem_tuples = []
        proceed_with_install = False
        rd_agent_dependencies = self.handle_complex_repository_dependency_for_package( package_elem,
                                                                                      package_name,
                                                                                      package_version,
                                                                                      agent_shed_repository,
                                                                                      from_agent_migration_manager=from_agent_migration_manager )
        for rd_agent_dependency in rd_agent_dependencies:
            if rd_agent_dependency.status == self.app.install_model.AgentDependency.installation_status.ERROR:
                # We'll log the error here, but continue installing packages since some may not require this dependency.
                log.error( "Error installing agent dependency for required repository: %s" % str( rd_agent_dependency.error_message ) )
        return agent_dependency, proceed_with_install, action_elem_tuples

    def remove_file( self, file_name ):
        """Attempt to remove a file from disk."""
        if file_name:
            if os.path.exists( file_name ):
                try:
                    os.remove( file_name )
                except:
                    pass


class SetEnvironment( RecipeTag ):

    def __init__( self, app ):
        self.app = app
        self.tag = 'set_environment'

    def process_tag_set( self, agent_shed_repository, agent_dependency, package_elem, package_name, package_version,
                         from_agent_migration_manager=False, agent_dependency_db_records=None ):
        # We need to handle two tag sets for package_elem here, this:
        # <set_environment version="1.0">
        #    <environment_variable name="R_SCRIPT_PATH"action="set_to">$REPOSITORY_INSTALL_DIR</environment_variable>
        # </set_environment>
        # or this:
        # <environment_variable name="R_SCRIPT_PATH"action="set_to">$REPOSITORY_INSTALL_DIR</environment_variable>
        action_elem_tuples = []
        proceed_with_install = False
        if agent_dependency_db_records is None:
            attr_tups_of_dependencies_for_install = []
        else:
            attr_tups_of_dependencies_for_install = [ ( td.name, td.version, td.type ) for td in agent_dependency_db_records ]
        try:
            self.set_environment( package_elem, agent_shed_repository, attr_tups_of_dependencies_for_install )
        except Exception, e:
            error_message = "Error setting environment for agent dependency: %s" % str( e )
            log.debug( error_message )
        return agent_dependency, proceed_with_install, action_elem_tuples

    def set_environment( self, elem, agent_shed_repository, attr_tups_of_dependencies_for_install ):
        """
        Create a AgentDependency to set an environment variable.  This is different from the process used to
        set an environment variable that is associated with a package.  An example entry in a agent_dependencies.xml
        file is::

            <set_environment version="1.0">
                <environment_variable name="R_SCRIPT_PATH" action="set_to">$REPOSITORY_INSTALL_DIR</environment_variable>
            </set_environment>

        This method must also handle the sub-element tag::
            <environment_variable name="R_SCRIPT_PATH" action="set_to">$REPOSITORY_INSTALL_DIR</environment_variable>
        """
        # TODO: Add support for a repository dependency definition within this agent dependency type's tag set.  This should look something like
        # the following.  See the implementation of support for this in the agent dependency package type's method above.
        # This function is only called for set environment actions as defined below, not within an <install version="1.0"> agent
        # dependency type. Here is an example of the tag set this function does handle:
        # <action type="set_environment">
        #     <environment_variable name="PATH" action="prepend_to">$INSTALL_DIR</environment_variable>
        # </action>
        # Here is an example of the tag set this function does not handle:
        # <set_environment version="1.0">
        #    <repository agentshed="<agent shed>" name="<repository name>" owner="<repository owner>" changeset_revision="<changeset revision>" />
        # </set_environment>
        env_manager = EnvManager( self.app )
        agent_dependencies = []
        env_var_version = elem.get( 'version', '1.0' )
        agent_shed_repository_install_dir = os.path.abspath( agent_shed_repository.repo_files_directory( self.app ) )
        if elem.tag == 'environment_variable':
            # <environment_variable name="R_SCRIPT_PATH" action="set_to">$REPOSITORY_INSTALL_DIR</environment_variable>
            elems = [ elem ]
        else:
            # <set_environment version="1.0">
            #    <environment_variable name="R_SCRIPT_PATH" action="set_to">$REPOSITORY_INSTALL_DIR</environment_variable>
            # </set_environment>
            elems = [ env_var_elem for env_var_elem in elem ]
        for env_var_elem in elems:
            env_var_name = env_var_elem.get( 'name', None )
            # The value of env_var_name must match the text value of at least 1 <requirement> tag in the
            # agent config's <requirements> tag set whose "type" attribute is "set_environment" (e.g.,
            # <requirement type="set_environment">R_SCRIPT_PATH</requirement>).
            env_var_action = env_var_elem.get( 'action', None )
            if env_var_name and env_var_action:
                # Agent dependencies of type "set_environment" always have the version attribute set to None.
                attr_tup = ( env_var_name, None, 'set_environment' )
                if attr_tup in attr_tups_of_dependencies_for_install:
                    install_dir = \
                        agent_dependency_util.get_agent_dependency_install_dir( app=self.app,
                                                                              repository_name=agent_shed_repository.name,
                                                                              repository_owner=agent_shed_repository.owner,
                                                                              repository_changeset_revision=agent_shed_repository.installed_changeset_revision,
                                                                              agent_dependency_type='set_environment',
                                                                              agent_dependency_name=env_var_name,
                                                                              agent_dependency_version=None )
                    install_environment = InstallEnvironment( app=self.app,
                                                              agent_shed_repository_install_dir=agent_shed_repository_install_dir,
                                                              install_dir=install_dir )
                    env_var_dict = env_manager.create_env_var_dict( elem=env_var_elem,
                                                                    install_environment=install_environment )
                    if env_var_dict:
                        if not os.path.exists( install_dir ):
                            os.makedirs( install_dir )
                        status = self.app.install_model.AgentDependency.installation_status.INSTALLING
                        agent_dependency = \
                            agent_dependency_util.create_or_update_agent_dependency( app=self.app,
                                                                                   agent_shed_repository=agent_shed_repository,
                                                                                   name=env_var_name,
                                                                                   version=None,
                                                                                   type='set_environment',
                                                                                   status=status,
                                                                                   set_status=True )
                        if env_var_version == '1.0':
                            # Create this agent dependency's env.sh file.
                            env_file_builder = EnvFileBuilder( install_dir )
                            return_code = env_file_builder.append_line( make_executable=True, **env_var_dict )
                            if return_code:
                                error_message = 'Error creating env.sh file for agent dependency %s, return_code: %s' % \
                                    ( str( agent_dependency.name ), str( return_code ) )
                                log.debug( error_message )
                                status = self.app.install_model.AgentDependency.installation_status.ERROR
                                agent_dependency = \
                                    agent_dependency_util.set_agent_dependency_attributes( self.app,
                                                                                         agent_dependency=agent_dependency,
                                                                                         status=status,
                                                                                         error_message=error_message )
                            else:
                                if agent_dependency.status not in [ self.app.install_model.AgentDependency.installation_status.ERROR,
                                                                   self.app.install_model.AgentDependency.installation_status.INSTALLED ]:
                                    status = self.app.install_model.AgentDependency.installation_status.INSTALLED
                                    agent_dependency = \
                                        agent_dependency_util.set_agent_dependency_attributes( self.app,
                                                                                             agent_dependency=agent_dependency,
                                                                                             status=status )
                                    log.debug( 'Environment variable %s set in %s for agent dependency %s.' %
                                        ( str( env_var_name ), str( install_dir ), str( agent_dependency.name ) ) )
                        else:
                            error_message = 'Only set_environment version 1.0 is currently supported (i.e., change your tag to be <set_environment version="1.0">).'
                            status = self.app.install_model.AgentDependency.installation_status.ERROR
                            agent_dependency = \
                                agent_dependency_util.set_agent_dependency_attributes( self.app,
                                                                                     agent_dependency=agent_dependency,
                                                                                     status=status,
                                                                                     error_message=error_message )
            agent_dependencies.append( agent_dependency )
        return agent_dependencies
