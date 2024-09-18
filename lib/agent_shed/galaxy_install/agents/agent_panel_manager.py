import logging
import threading

from xml.etree import ElementTree as XmlET

from agent_shed.util import basic_util
from agent_shed.util import common_util
from agent_shed.util import shed_util_common as suc
from agent_shed.util import xml_util

log = logging.getLogger( __name__ )


class AgentPanelManager( object ):

    def __init__( self, app ):
        self.app = app

    def add_to_shed_agent_config( self, shed_agent_conf_dict, elem_list ):
        """
        "A agent shed repository is being installed so change the shed_agent_conf file.  Parse the
        config file to generate the entire list of config_elems instead of using the in-memory list
        since it will be a subset of the entire list if one or more repositories have been deactivated.
        """
        shed_agent_conf = shed_agent_conf_dict[ 'config_filename' ]
        agent_path = shed_agent_conf_dict[ 'agent_path' ]
        config_elems = []
        tree, error_message = xml_util.parse_xml( shed_agent_conf )
        if tree:
            root = tree.getroot()
            for elem in root:
                config_elems.append( elem )
            # Add the elements to the in-memory list of config_elems.
            for elem_entry in elem_list:
                config_elems.append( elem_entry )
            # Persist the altered shed_agent_config file.
            self.config_elems_to_xml_file( config_elems, shed_agent_conf, agent_path )

    def add_to_agent_panel( self, repository_name, repository_clone_url, changeset_revision, repository_agents_tups, owner,
                           shed_agent_conf, agent_panel_dict, new_install=True ):
        """A agent shed repository is being installed or updated so handle agent panel alterations accordingly."""
        # We need to change the in-memory version and the file system version of the shed_agent_conf file.
        shed_agent_conf_dict = self.get_shed_agent_conf_dict( shed_agent_conf )
        agent_path = shed_agent_conf_dict[ 'agent_path' ]
        # Generate the list of ElementTree Element objects for each section or agent.
        elem_list = self.generate_agent_panel_elem_list( repository_name,
                                                        repository_clone_url,
                                                        changeset_revision,
                                                        agent_panel_dict,
                                                        repository_agents_tups,
                                                        owner=owner )
        if new_install:
            # Add the new elements to the shed_agent_conf file on disk.
            self.add_to_shed_agent_config( shed_agent_conf_dict, elem_list )
            # Use the new elements to add entries to the
        config_elems = shed_agent_conf_dict[ 'config_elems' ]
        for config_elem in elem_list:
            # Add the new elements to the in-memory list of config_elems.
            config_elems.append( config_elem )
            # Load the agents into the in-memory agent panel.
            self.app.agentbox.load_item(
                config_elem,
                agent_path=agent_path,
                load_panel_dict=True,
                guid=config_elem.get( 'guid' ),
            )
        # Replace the old list of in-memory config_elems with the new list for this shed_agent_conf_dict.
        shed_agent_conf_dict[ 'config_elems' ] = config_elems
        self.app.agentbox.update_shed_config( shed_agent_conf_dict )

    def config_elems_to_xml_file( self, config_elems, config_filename, agent_path ):
        """
        Persist the current in-memory list of config_elems to a file named by the
        value of config_filename.
        """
        lock = threading.Lock()
        lock.acquire( True )
        try:
            fh = open( config_filename, 'wb' )
            fh.write( '<?xml version="1.0"?>\n<agentbox agent_path="%s">\n' % str( agent_path ) )
            for elem in config_elems:
                fh.write( xml_util.xml_to_string( elem, use_indent=True ) )
            fh.write( '</agentbox>\n' )
            fh.close()
        except Exception, e:
            log.exception( "Exception in AgentPanelManager.config_elems_to_xml_file: %s" % str( e ) )
        finally:
            lock.release()

    def generate_agent_elem( self, agent_shed, repository_name, changeset_revision, owner, agent_file_path,
                            agent, agent_section ):
        """Create and return an ElementTree agent Element."""
        if agent_section is not None:
            agent_elem = XmlET.SubElement( agent_section, 'agent' )
        else:
            agent_elem = XmlET.Element( 'agent' )
        agent_elem.attrib[ 'file' ] = agent_file_path
        if not agent.guid:
            raise ValueError("agent has no guid")
        agent_elem.attrib[ 'guid' ] = agent.guid
        agent_shed_elem = XmlET.SubElement( agent_elem, 'agent_shed' )
        agent_shed_elem.text = agent_shed
        repository_name_elem = XmlET.SubElement( agent_elem, 'repository_name' )
        repository_name_elem.text = repository_name
        repository_owner_elem = XmlET.SubElement( agent_elem, 'repository_owner' )
        repository_owner_elem.text = owner
        changeset_revision_elem = XmlET.SubElement( agent_elem, 'installed_changeset_revision' )
        changeset_revision_elem.text = changeset_revision
        id_elem = XmlET.SubElement( agent_elem, 'id' )
        id_elem.text = agent.id
        version_elem = XmlET.SubElement( agent_elem, 'version' )
        version_elem.text = agent.version
        return agent_elem

    def generate_agent_panel_dict_for_new_install( self, agent_dicts, agent_section=None ):
        """
        When installing a repository that contains agents, all agents must
        currently be defined within the same agent section in the agent panel or
        outside of any sections.
        """
        agent_panel_dict = {}
        if agent_section:
            section_id = agent_section.id
            section_name = agent_section.name
            section_version = agent_section.version or ''
        else:
            section_id = ''
            section_name = ''
            section_version = ''
        for agent_dict in agent_dicts:
            if agent_dict.get( 'add_to_agent_panel', True ):
                guid = agent_dict[ 'guid' ]
                agent_config = agent_dict[ 'agent_config' ]
                agent_section_dict = dict( agent_config=agent_config, id=section_id, name=section_name, version=section_version )
                if guid in agent_panel_dict:
                    agent_panel_dict[ guid ].append( agent_section_dict )
                else:
                    agent_panel_dict[ guid ] = [ agent_section_dict ]
        return agent_panel_dict

    def generate_agent_panel_dict_for_agent_config( self, guid, agent_config, agent_sections=None ):
        """
        Create a dictionary of the following type for a single agent config file name.
        The intent is to call this method for every agent config in a repository and
        append each of these as entries to a agent panel dictionary for the repository.
        This enables each agent to be loaded into a different section in the agent panel.
        {<Agent guid> :
           [{ agent_config : <agent_config_file>,
              id: <AgentSection id>,
              version : <AgentSection version>,
              name : <TooSection name>}]}
        """
        agent_panel_dict = {}
        file_name = basic_util.strip_path( agent_config )
        agent_section_dicts = self. generate_agent_section_dicts( agent_config=file_name,
                                                                agent_sections=agent_sections )
        agent_panel_dict[ guid ] = agent_section_dicts
        return agent_panel_dict

    def generate_agent_panel_dict_from_shed_agent_conf_entries( self, repository ):
        """
        Keep track of the section in the agent panel in which this repository's
        agents will be contained by parsing the shed_agent_conf in which the
        repository's agents are defined and storing the agent panel definition
        of each agent in the repository. This method is called only when the
        repository is being deactivated or un-installed and allows for
        activation or re-installation using the original layout.
        """
        agent_panel_dict = {}
        shed_agent_conf, agent_path, relative_install_dir = \
            suc.get_agent_panel_config_agent_path_install_dir( self.app, repository )
        metadata = repository.metadata
        # Create a dictionary of agent guid and agent config file name for each agent in the repository.
        guids_and_configs = {}
        if 'agents' in metadata:
            for agent_dict in metadata[ 'agents' ]:
                guid = agent_dict[ 'guid' ]
                agent_config = agent_dict[ 'agent_config' ]
                file_name = basic_util.strip_path( agent_config )
                guids_and_configs[ guid ] = file_name
        # Parse the shed_agent_conf file in which all of this repository's agents are defined and generate the agent_panel_dict.
        tree, error_message = xml_util.parse_xml( shed_agent_conf )
        if tree is None:
            return agent_panel_dict
        root = tree.getroot()
        for elem in root:
            if elem.tag == 'agent':
                guid = elem.get( 'guid' )
                if guid in guids_and_configs:
                    # The agent is displayed in the agent panel outside of any agent sections.
                    agent_section_dict = dict( agent_config=guids_and_configs[ guid ], id='', name='', version='' )
                    if guid in agent_panel_dict:
                        agent_panel_dict[ guid ].append( agent_section_dict )
                    else:
                        agent_panel_dict[ guid ] = [ agent_section_dict ]
            elif elem.tag == 'section':
                section_id = elem.get( 'id' ) or ''
                section_name = elem.get( 'name' ) or ''
                section_version = elem.get( 'version' ) or ''
                for section_elem in elem:
                    if section_elem.tag == 'agent':
                        guid = section_elem.get( 'guid' )
                        if guid in guids_and_configs:
                            # The agent is displayed in the agent panel inside the current agent section.
                            agent_section_dict = dict( agent_config=guids_and_configs[ guid ],
                                                      id=section_id,
                                                      name=section_name,
                                                      version=section_version )
                            if guid in agent_panel_dict:
                                agent_panel_dict[ guid ].append( agent_section_dict )
                            else:
                                agent_panel_dict[ guid ] = [ agent_section_dict ]
        return agent_panel_dict

    def generate_agent_panel_elem_list( self, repository_name, repository_clone_url, changeset_revision,
                                       agent_panel_dict, repository_agents_tups, owner='' ):
        """Generate a list of ElementTree Element objects for each section or agent."""
        elem_list = []
        agent_elem = None
        cleaned_repository_clone_url = common_util.remove_protocol_and_user_from_clone_url( repository_clone_url )
        if not owner:
            owner = suc.get_repository_owner( cleaned_repository_clone_url )
        agent_shed = cleaned_repository_clone_url.split( '/repos/' )[ 0 ].rstrip( '/' )
        for guid, agent_section_dicts in agent_panel_dict.items():
            for agent_section_dict in agent_section_dicts:
                agent_section = None
                inside_section = False
                section_in_elem_list = False
                if agent_section_dict[ 'id' ]:
                    inside_section = True
                    # Create a new section element only if we haven't already created it.
                    for index, elem in enumerate( elem_list ):
                        if elem.tag == 'section':
                            section_id = elem.get( 'id', None )
                            if section_id == agent_section_dict[ 'id' ]:
                                section_in_elem_list = True
                                agent_section = elem
                                break
                    if agent_section is None:
                        agent_section = self.generate_agent_section_element_from_dict( agent_section_dict )
                # Find the tuple containing the current guid from the list of repository_agents_tups.
                for repository_agent_tup in repository_agents_tups:
                    agent_file_path, tup_guid, agent = repository_agent_tup
                    if tup_guid == guid:
                        break
                agent_elem = self.generate_agent_elem( agent_shed,
                                                     repository_name,
                                                     changeset_revision,
                                                     owner,
                                                     agent_file_path,
                                                     agent,
                                                     agent_section if inside_section else None )
                if inside_section:
                    if section_in_elem_list:
                        elem_list[ index ] = agent_section
                    else:
                        elem_list.append( agent_section )
                else:
                    elem_list.append( agent_elem )
        return elem_list

    def generate_agent_section_dicts( self, agent_config=None, agent_sections=None ):
        agent_section_dicts = []
        if agent_config is None:
            agent_config = ''
        if agent_sections:
            for agent_section in agent_sections:
                # The value of agent_section will be None if the agent is displayed outside
                # of any sections in the agent panel.
                if agent_section:
                    section_id = agent_section.id or ''
                    section_version = agent_section.version or ''
                    section_name = agent_section.name or ''
                else:
                    section_id = ''
                    section_version = ''
                    section_name = ''
                agent_section_dicts.append( dict( agent_config=agent_config,
                                                 id=section_id,
                                                 version=section_version,
                                                 name=section_name ) )
        else:
            agent_section_dicts.append( dict( agent_config=agent_config, id='', version='', name='' ) )
        return agent_section_dicts

    def generate_agent_section_element_from_dict( self, agent_section_dict ):
        # The value of agent_section_dict looks like the following.
        # { id: <AgentSection id>, version : <AgentSection version>, name : <TooSection name>}
        if agent_section_dict[ 'id' ]:
            # Create a new agent section.
            agent_section = XmlET.Element( 'section' )
            agent_section.attrib[ 'id' ] = agent_section_dict[ 'id' ]
            agent_section.attrib[ 'name' ] = agent_section_dict[ 'name' ]
            agent_section.attrib[ 'version' ] = agent_section_dict[ 'version' ]
        else:
            agent_section = None
        return agent_section

    def get_or_create_agent_section( self, agentbox, agent_panel_section_id, new_agent_panel_section_label=None ):
        return agentbox.get_section( section_id=agent_panel_section_id, new_label=new_agent_panel_section_label, create_if_needed=True )

    def get_shed_agent_conf_dict( self, shed_agent_conf ):
        """
        Return the in-memory version of the shed_agent_conf file, which is stored in
        the config_elems entry in the shed_agent_conf_dict associated with the file.
        """
        for shed_agent_conf_dict in self.app.agentbox.dynamic_confs( include_migrated_agent_conf=True ):
            if shed_agent_conf == shed_agent_conf_dict[ 'config_filename' ]:
                return shed_agent_conf_dict
            else:
                file_name = basic_util.strip_path( shed_agent_conf_dict[ 'config_filename' ] )
                if shed_agent_conf == file_name:
                    return shed_agent_conf_dict

    def handle_agent_panel_section( self, agentbox, agent_panel_section_id=None, new_agent_panel_section_label=None ):
        """Return a AgentSection object retrieved from the current in-memory agent_panel."""
        # If agent_panel_section_id is received, the section exists in the agent panel.  In this
        # case, the value of the received agent_panel_section_id must be the id retrieved from a
        # agent panel config (e.g., agent_conf.xml, which may have getext).  If new_agent_panel_section_label
        # is received, a new section will be added to the agent panel.
        if new_agent_panel_section_label:
            section_id = str( new_agent_panel_section_label.lower().replace( ' ', '_' ) )
            agent_panel_section_key, agent_section = \
                self.get_or_create_agent_section( agentbox,
                                                 agent_panel_section_id=section_id,
                                                 new_agent_panel_section_label=new_agent_panel_section_label )
        elif agent_panel_section_id:
            agent_panel_section_key, agent_section = agentbox.get_section( agent_panel_section_id)
        else:
            return None, None
        return agent_panel_section_key, agent_section

    def handle_agent_panel_selection( self, agentbox, metadata, no_changes_checked, agent_panel_section_id,
                                     new_agent_panel_section_label ):
        """
        Handle the selected agent panel location for loading agents included in
        agent shed repositories when installing or reinstalling them.
        """
        # Get the location in the agent panel in which each agent was originally loaded.
        agent_section = None
        agent_panel_section_key = None
        if 'agents' in metadata:
            # This forces everything to be loaded into the same section (or no section)
            # in the agent panel.
            if no_changes_checked:
                # Make sure the no_changes check box overrides the new_agent_panel_section_label
                # if the user checked the check box and entered something into the field.
                new_agent_panel_section_label = None
                if 'agent_panel_section' in metadata:
                    agent_panel_dict = metadata[ 'agent_panel_section' ]
                    if not agent_panel_dict:
                        agent_panel_dict = self.generate_agent_panel_dict_for_new_install( metadata[ 'agents' ] )
                else:
                    agent_panel_dict = self.generate_agent_panel_dict_for_new_install( metadata[ 'agents' ] )
                if agent_panel_dict:
                    # The agent_panel_dict is empty when agents exist but are not installed into a agent panel section.
                    agent_section_dicts = agent_panel_dict[ agent_panel_dict.keys()[ 0 ] ]
                    agent_section_dict = agent_section_dicts[ 0 ]
                    original_section_id = agent_section_dict[ 'id' ]
                    if original_section_id:
                        agent_panel_section_key, agent_section = \
                            self.get_or_create_agent_section( agentbox,
                                                             agent_panel_section_id=original_section_id,
                                                             new_agent_panel_section_label=new_agent_panel_section_label )
            else:
                # The user elected to change the agent panel section to contain the agents.
                agent_panel_section_key, agent_section = \
                    self.handle_agent_panel_section( agentbox,
                                                    agent_panel_section_id=agent_panel_section_id,
                                                    new_agent_panel_section_label=new_agent_panel_section_label )
        return agent_section, agent_panel_section_key

    def remove_from_shed_agent_config( self, shed_agent_conf_dict, guids_to_remove ):
        """
        A agent shed repository is being uninstalled so change the
        shed_agent_conf file. Parse the config file to generate the entire list
        of config_elems instead of using the in-memory list since it will be a
        subset of the entire list if one or more repositories have been
        deactivated.
        """
        shed_agent_conf = shed_agent_conf_dict[ 'config_filename' ]
        agent_path = shed_agent_conf_dict[ 'agent_path' ]
        config_elems = []
        tree, error_message = xml_util.parse_xml( shed_agent_conf )
        if tree:
            root = tree.getroot()
            for elem in root:
                config_elems.append( elem )
            config_elems_to_remove = []
            for config_elem in config_elems:
                if config_elem.tag == 'section':
                    agent_elems_to_remove = []
                    for agent_elem in config_elem:
                        if agent_elem.get( 'guid' ) in guids_to_remove:
                            agent_elems_to_remove.append( agent_elem )
                    for agent_elem in agent_elems_to_remove:
                        # Remove all of the appropriate agent sub-elements from the section element.
                        config_elem.remove( agent_elem )
                    if len( config_elem ) < 1:
                        # Keep a list of all empty section elements so they can be removed.
                        config_elems_to_remove.append( config_elem )
                elif config_elem.tag == 'agent':
                    if config_elem.get( 'guid' ) in guids_to_remove:
                        config_elems_to_remove.append( config_elem )
            for config_elem in config_elems_to_remove:
                config_elems.remove( config_elem )
            # Persist the altered in-memory version of the agent config.
            self.config_elems_to_xml_file( config_elems, shed_agent_conf, agent_path )

    def remove_repository_contents( self, repository, shed_agent_conf, uninstall ):
        """
        A agent shed repository is being deactivated or uninstalled, so handle
        agent panel alterations accordingly.
        """
        # Determine where the agents are currently defined in the agent panel and store this
        # information so the agents can be displayed in the same way when the repository is
        # activated or reinstalled.
        agent_panel_dict = self.generate_agent_panel_dict_from_shed_agent_conf_entries( repository )
        repository.metadata[ 'agent_panel_section' ] = agent_panel_dict
        self.app.install_model.context.add( repository )
        self.app.install_model.context.flush()
        # Create a list of guids for all agents that will be removed from the in-memory agent panel
        # and config file on disk.
        guids_to_remove = [ k for k in agent_panel_dict.keys() ]
        self.remove_guids( guids_to_remove, shed_agent_conf, uninstall )

    def remove_guids( self, guids_to_remove, shed_agent_conf, uninstall ):
        agentbox = self.app.agentbox
        # Remove the agents from the agentbox's agents_by_id dictionary.
        for guid_to_remove in guids_to_remove:
            # remove_from_agent_panel to false, will handling that logic below.
            agentbox.remove_agent_by_id( guid_to_remove, remove_from_panel=False )
        shed_agent_conf_dict = self.get_shed_agent_conf_dict( shed_agent_conf )
        if uninstall:
            # Remove from the shed_agent_conf file on disk.
            self.remove_from_shed_agent_config( shed_agent_conf_dict, guids_to_remove )
        config_elems = shed_agent_conf_dict[ 'config_elems' ]
        config_elems_to_remove = []
        for config_elem in config_elems:
            if config_elem.tag == 'section':
                # Get the section key for the in-memory agent panel.
                section_key = str( config_elem.get( "id" ) )
                # Generate the list of agent elements to remove.
                agent_elems_to_remove = []
                for agent_elem in config_elem:
                    if agent_elem.get( 'guid' ) in guids_to_remove:
                        agent_elems_to_remove.append( agent_elem )
                for agent_elem in agent_elems_to_remove:
                    if agent_elem in config_elem:
                        # Remove the agent sub-element from the section element.
                        config_elem.remove( agent_elem )
                    # Remove the agent from the section in the in-memory agent panel.
                    agentbox.remove_from_panel( agent_elem.get( "guid" ), section_key=section_key, remove_from_config=uninstall )
                if len( config_elem ) < 1:
                    # Keep a list of all empty section elements so they can be removed.
                    config_elems_to_remove.append( config_elem )
            elif config_elem.tag == 'agent':
                guid = config_elem.get( 'guid' )
                if guid in guids_to_remove:
                    agentbox.remove_from_panel( guid, section_key='', remove_from_config=uninstall )
                    config_elems_to_remove.append( config_elem )
        for config_elem in config_elems_to_remove:
            # Remove the element from the in-memory list of elements.
            config_elems.remove( config_elem )
        # Update the config_elems of the in-memory shed_agent_conf_dict.
        shed_agent_conf_dict[ 'config_elems' ] = config_elems
        agentbox.update_shed_config( shed_agent_conf_dict, integrated_panel_changes=uninstall )
