import tempfile
import logging

log = logging.getLogger( __name__ )

from agent_shed.galaxy_install import install_manager
from agent_shed.galaxy_install.repository_dependencies import repository_dependency_manager
from agent_shed.galaxy_install.agents import agent_panel_manager

from agent_shed.util import hg_util
from agent_shed.util import basic_util
from agent_shed.util import common_util
from agent_shed.util import container_util
from agent_shed.util import shed_util_common as suc
from agent_shed.util import repository_util
from agent_shed.util import agent_dependency_util


class RepairRepositoryManager():

    def __init__( self, app ):
        self.app = app

    def get_installed_repositories_from_repository_dependencies( self, repository_dependencies_dict ):
        installed_repositories = []
        if repository_dependencies_dict and isinstance( repository_dependencies_dict, dict ):
            for rd_key, rd_vals in repository_dependencies_dict.items():
                if rd_key in [ 'root_key', 'description' ]:
                    continue
                # rd_key is something like: 'http://localhost:9009__ESEP__package_rdkit_2012_12__ESEP__test__ESEP__d635ffb9c665__ESEP__True'
                # rd_val is something like: [['http://localhost:9009', 'package_numpy_1_7', 'test', 'cddd64ecd985', 'True']]
                repository_components_tuple = container_util.get_components_from_key( rd_key )
                components_list = suc.extract_components_from_tuple( repository_components_tuple )
                agent_shed, name, owner, changeset_revision = components_list[ 0:4 ]
                installed_repository = suc.get_installed_repository( self.app,
                                                                     agent_shed=agent_shed,
                                                                     name=name,
                                                                     owner=owner,
                                                                     changeset_revision=changeset_revision )
                if ( installed_repository ) and ( installed_repository not in installed_repositories ):
                    installed_repositories.append( installed_repository )
                for rd_val in rd_vals:
                    agent_shed, name, owner, changeset_revision = rd_val[ 0:4 ]
                    installed_repository = suc.get_installed_repository( self.app,
                                                                         agent_shed=agent_shed,
                                                                         name=name,
                                                                         owner=owner,
                                                                         changeset_revision=changeset_revision )
                    if ( installed_repository ) and ( installed_repository not in installed_repositories ):
                        installed_repositories.append( installed_repository )
        return installed_repositories

    def get_repair_dict( self, repository ):
        """
        Inspect the installed repository dependency hierarchy for a specified repository
        and attempt to make sure they are all properly installed as well as each repository's
        agent dependencies.  This method is called only from Galaxy when attempting to correct
        issues with an installed repository that has installation problems somewhere in its
        dependency hierarchy.
        """
        rdim = repository_dependency_manager.RepositoryDependencyInstallManager( self.app )
        tsr_ids = []
        repo_info_dicts = []
        agent_panel_section_keys = []
        repair_dict = {}
        irm = install_manager.InstallRepositoryManager( self.app )
        # Get a dictionary of all repositories upon which the contents of the current repository_metadata
        # record depend.
        repository_dependencies_dict = rdim.get_repository_dependencies_for_installed_agent_shed_repository( self.app,
                                                                                                            repository )
        if repository_dependencies_dict:
            # Generate the list of installed repositories from the information contained in the
            # repository_dependencies dictionary.
            installed_repositories = self.get_installed_repositories_from_repository_dependencies( repository_dependencies_dict )
            # Some repositories may have repository dependencies that are required to be installed before
            # the dependent repository, so we'll order the list of tsr_ids to ensure all repositories are
            # repaired in the required order.
            installed_repositories.append(repository)
            for installed_repository in installed_repositories:
                tsr_ids.append( self.app.security.encode_id( installed_repository.id ) )
                repo_info_dict, agent_panel_section_key = self.get_repo_info_dict_for_repair( rdim,
                                                                                             installed_repository )
                agent_panel_section_keys.append( agent_panel_section_key )
                repo_info_dicts.append( repo_info_dict )
        else:
            # The received repository has no repository dependencies.
            tsr_ids.append( self.app.security.encode_id( repository.id ) )
            repo_info_dict, agent_panel_section_key = self.get_repo_info_dict_for_repair( rdim,
                                                                                         repository )
            agent_panel_section_keys.append( agent_panel_section_key )
            repo_info_dicts.append( repo_info_dict )
        ordered_tsr_ids, ordered_repo_info_dicts, ordered_agent_panel_section_keys = \
            irm.order_components_for_installation( tsr_ids,
                                                   repo_info_dicts,
                                                   agent_panel_section_keys=agent_panel_section_keys )
        repair_dict[ 'ordered_tsr_ids' ] = ordered_tsr_ids
        repair_dict[ 'ordered_repo_info_dicts' ] = ordered_repo_info_dicts
        repair_dict[ 'ordered_agent_panel_section_keys' ] = ordered_agent_panel_section_keys
        return repair_dict

    def get_repo_info_dict_for_repair( self, rdim, repository ):
        agent_panel_section_key = None
        repository_clone_url = common_util.generate_clone_url_for_installed_repository( self.app, repository )
        repository_dependencies = rdim.get_repository_dependencies_for_installed_agent_shed_repository( self.app,
                                                                                                       repository )
        metadata = repository.metadata
        if metadata:
            agent_dependencies = metadata.get( 'agent_dependencies', None )
            agent_panel_section_dict = metadata.get( 'agent_panel_section', None )
            if agent_panel_section_dict:
                # The repository must be in the uninstalled state.  The structure of agent_panel_section_dict is:
                # {<agent guid> :
                # [{ 'id':<section id>, 'name':<section name>, 'version':<section version>, 'agent_config':<agent config file name> }]}
                # Here is an example:
                # {"localhost:9009/repos/test/filter/Filter1/1.1.0":
                # [{"id": "filter_and_sort", "name": "Filter and Sort", "agent_config": "filtering.xml", "version": ""}]}
                # Currently all agents contained within an installed agent shed repository must be loaded into the same
                # section in the agent panel, so we can get the section id of the first guid in the agent_panel_section_dict.
                # In the future, we'll have to handle different sections per guid.
                guid = agent_panel_section_dict.keys()[ 0 ]
                section_dicts = agent_panel_section_dict[ guid ]
                section_dict = section_dicts[ 0 ]
                agent_panel_section_id = section_dict[ 'id' ]
                agent_panel_section_name = section_dict[ 'name' ]
                if agent_panel_section_id:
                    tpm = agent_panel_manager.AgentPanelManager( self.app )
                    agent_panel_section_key, _ = \
                        tpm.get_or_create_agent_section( self.app.agentbox,
                                                        agent_panel_section_id=agent_panel_section_id,
                                                        new_agent_panel_section_label=agent_panel_section_name )
        else:
            agent_dependencies = None
        repo_info_dict = repository_util.create_repo_info_dict( app=self.app,
                                                                repository_clone_url=repository_clone_url,
                                                                changeset_revision=repository.changeset_revision,
                                                                ctx_rev=repository.ctx_rev,
                                                                repository_owner=repository.owner,
                                                                repository_name=repository.name,
                                                                repository=None,
                                                                repository_metadata=None,
                                                                agent_dependencies=agent_dependencies,
                                                                repository_dependencies=repository_dependencies )
        return repo_info_dict, agent_panel_section_key

    def repair_agent_shed_repository( self, repository, repo_info_dict ):

        def add_repair_dict_entry( repository_name, error_message ):
            if repository_name in repair_dict:
                repair_dict[ repository_name ].append( error_message )
            else:
                repair_dict[ repository_name ] = [ error_message ]
            return repair_dict

        metadata = repository.metadata
        repair_dict = {}
        tpm = agent_panel_manager.AgentPanelManager( self.app )
        if repository.status in [ self.app.install_model.AgentShedRepository.installation_status.DEACTIVATED ]:
            try:
                self.app.installed_repository_manager.activate_repository( repository )
            except Exception, e:
                error_message = "Error activating repository %s: %s" % ( repository.name, str( e ) )
                log.debug( error_message )
                repair_dict[ repository.name ] = error_message
        elif repository.status not in [ self.app.install_model.AgentShedRepository.installation_status.INSTALLED ]:
            shed_agent_conf, agent_path, relative_install_dir = \
                suc.get_agent_panel_config_agent_path_install_dir( self.app, repository )
            # Reset the repository attributes to the New state for installation.
            if metadata:
                _, agent_panel_section_key = \
                    tpm.handle_agent_panel_selection( self.app.agentbox,
                                                     metadata,
                                                     no_changes_checked=True,
                                                     agent_panel_section_id=None,
                                                     new_agent_panel_section_label=None )
            else:
                # The agents will be loaded outside of any sections in the agent panel.
                agent_panel_section_key = None
            suc.set_repository_attributes( self.app,
                                           repository,
                                           status=self.app.install_model.AgentShedRepository.installation_status.NEW,
                                           error_message=None,
                                           deleted=False,
                                           uninstalled=False,
                                           remove_from_disk=True )
            irm = install_manager.InstallRepositoryManager( self.app, tpm )
            irm.install_agent_shed_repository( repository,
                                              repo_info_dict,
                                              agent_panel_section_key,
                                              shed_agent_conf,
                                              agent_path,
                                              install_agent_dependencies=True,
                                              reinstalling=True )
            if repository.status in [ self.app.install_model.AgentShedRepository.installation_status.ERROR ]:
                repair_dict = add_repair_dict_entry( repository.name, repository.error_message )
        else:
            irm = install_manager.InstallRepositoryManager( self.app, tpm )
            # We have an installed agent shed repository, so handle agent dependencies if necessary.
            if repository.missing_agent_dependencies and metadata and 'agent_dependencies' in metadata:
                work_dir = tempfile.mkdtemp( prefix="tmp-agentshed-itdep" )
                # Reset missing agent dependencies.
                for agent_dependency in repository.missing_agent_dependencies:
                    if agent_dependency.status in [ self.app.install_model.AgentDependency.installation_status.ERROR,
                                                   self.app.install_model.AgentDependency.installation_status.INSTALLING ]:
                        agent_dependency = \
                            agent_dependency_util.set_agent_dependency_attributes( self.app,
                                                                                 agent_dependency=agent_dependency,
                                                                                 status=self.app.install_model.AgentDependency.installation_status.UNINSTALLED )
                # Install agent dependencies.
                irm.update_agent_shed_repository_status( repository,
                                                        self.app.install_model.AgentShedRepository.installation_status.INSTALLING_TOOL_DEPENDENCIES )
                # Get the agent_dependencies.xml file from the repository.
                agent_dependencies_config = hg_util.get_config_from_disk( 'agent_dependencies.xml', repository.repo_path( self.app ) )
                itdm = install_manager.InstallAgentDependencyManager( self.app )
                installed_agent_dependencies = itdm.install_specified_agent_dependencies( agent_shed_repository=repository,
                                                                                        agent_dependencies_config=agent_dependencies_config,
                                                                                        agent_dependencies=repository.agent_dependencies,
                                                                                        from_agent_migration_manager=False )
                for installed_agent_dependency in installed_agent_dependencies:
                    if installed_agent_dependency.status in [ self.app.install_model.AgentDependency.installation_status.ERROR ]:
                        repair_dict = add_repair_dict_entry( repository.name, installed_agent_dependency.error_message )
                basic_util.remove_dir( work_dir )
            irm.update_agent_shed_repository_status( repository,
                                                    self.app.install_model.AgentShedRepository.installation_status.INSTALLED )
        return repair_dict
