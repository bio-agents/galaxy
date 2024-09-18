import logging
import os
import string

from markupsafe import escape
from six.moves.urllib.parse import urlparse
from six import iteritems

from galaxy.exceptions import ObjectNotFound

from galaxy.util.dictifiable import Dictifiable

from galaxy.util.odict import odict
from galaxy.util import listify
from galaxy.util import parse_xml
from galaxy.util import string_as_bool
from galaxy.util.bunch import Bunch

from .parser import get_agentbox_parser, ensure_agent_conf_item

from .panel import AgentPanelElements
from .panel import AgentSectionLabel
from .panel import AgentSection
from .panel import panel_item_types
from .integrated_panel import ManagesIntegratedAgentPanelMixin

from .lineages import LineageMap
from .tags import agent_tag_manager

from .filters import FilterFactory
from .watcher import get_agent_watcher
from .watcher import get_agent_conf_watcher

# Extra agent dependency not used by AbstractAgentBox but by
# BaseGalaxyAgentBox
from galaxy.agents.loader_directory import looks_like_a_agent
from galaxy.agents.deps import build_dependency_manager


log = logging.getLogger( __name__ )


class AbstractAgentBox( Dictifiable, ManagesIntegratedAgentPanelMixin, object ):
    """
    Abstract container for managing a AgentPanel - containing agents and
    workflows optionally in labelled sections.
    """

    def __init__( self, config_filenames, agent_root_dir, app ):
        """
        Create a agentbox from the config files named by `config_filenames`, using
        `agent_root_dir` as the base directory for finding individual agent config files.
        """
        # The _dynamic_agent_confs list contains dictionaries storing
        # information about the agents defined in each shed-related
        # shed_agent_conf.xml file.
        self._dynamic_agent_confs = []
        self._agents_by_id = {}
        self._integrated_section_by_agent = {}
        # Agent lineages can contain chains of related agents with different ids
        # so each will be present once in the above dictionary. The following
        # dictionary can instead hold multiple agents with different versions.
        self._agent_versions_by_id = {}
        self._workflows_by_id = {}
        # In-memory dictionary that defines the layout of the agent panel.
        self._agent_panel = AgentPanelElements()
        self._index = 0
        self.data_manager_agents = odict()
        self._lineage_map = LineageMap( app )
        # Sets self._integrated_agent_panel and self._integrated_agent_panel_config_has_contents
        self._init_integrated_agent_panel( app.config )
        # The following refers to the agent_path config setting for backward compatibility.  The shed-related
        # (e.g., shed_agent_conf.xml) files include the agent_path attribute within the <agentbox> tag.
        self._agent_root_dir = agent_root_dir
        self.app = app
        self._agent_watcher = get_agent_watcher( self, app.config )
        self._agent_conf_watcher = get_agent_conf_watcher( lambda: app.reload_agentbox() )
        self._filter_factory = FilterFactory( self )
        self._agent_tag_manager = agent_tag_manager( app )
        self._init_agents_from_configs( config_filenames )
        if self.app.name == 'galaxy' and self._integrated_agent_panel_config_has_contents:
            # Load self._agent_panel based on the order in self._integrated_agent_panel.
            self._load_agent_panel()
        self._save_integrated_agent_panel()

    def create_agent( self, config_file, repository_id=None, guid=None, **kwds ):
        raise NotImplementedError()

    def _init_agents_from_configs( self, config_filenames ):
        """ Read through all agent config files and initialize agents in each
        with init_agents_from_config below.
        """
        self._agent_tag_manager.reset_tags()
        config_filenames = listify( config_filenames )
        for config_filename in config_filenames:
            if os.path.isdir( config_filename ):
                directory_contents = sorted( os.listdir( config_filename ) )
                directory_config_files = [ config_file for config_file in directory_contents if config_file.endswith( ".xml" ) ]
                config_filenames.remove( config_filename )
                config_filenames.extend( directory_config_files )
        for config_filename in config_filenames:
            try:
                self._init_agents_from_config( config_filename )
            except:
                log.exception( "Error loading agents defined in config %s", config_filename )

    def _init_agents_from_config( self, config_filename ):
        """
        Read the configuration file and load each agent.  The following tags are currently supported:

        .. raw:: xml

            <agentbox>
                <agent file="data_source/upload.xml"/>                 # agents outside sections
                <label text="Basic Agents" id="basic_agents" />         # labels outside sections
                <workflow id="529fd61ab1c6cc36" />                    # workflows outside sections
                <section name="Get Data" id="getext">                 # sections
                    <agent file="data_source/biomart.xml" />           # agents inside sections
                    <label text="In Section" id="in_section" />       # labels inside sections
                    <workflow id="adb5f5c93f827949" />                # workflows inside sections
                    <agent file="data_source/foo.xml" labels="beta" /> # label for a single agent
                </section>
            </agentbox>

        """
        log.info( "Parsing the agent configuration %s" % config_filename )
        agent_conf_source = get_agentbox_parser(config_filename)
        agent_path = agent_conf_source.parse_agent_path()
        if agent_path:
            # We're parsing a shed_agent_conf file since we have a agent_path attribute.
            parsing_shed_agent_conf = True
            # Keep an in-memory list of xml elements to enable persistence of the changing agent config.
            config_elems = []
        else:
            parsing_shed_agent_conf = False
        agent_path = self.__resolve_agent_path(agent_path, config_filename)
        # Only load the panel_dict under certain conditions.
        load_panel_dict = not self._integrated_agent_panel_config_has_contents
        for item in agent_conf_source.parse_items():
            index = self._index
            self._index += 1
            if parsing_shed_agent_conf:
                config_elems.append( item.elem )
            self.load_item(
                item,
                agent_path=agent_path,
                load_panel_dict=load_panel_dict,
                guid=item.get( 'guid' ),
                index=index,
                internal=True
            )

        if parsing_shed_agent_conf:
            shed_agent_conf_dict = dict( config_filename=config_filename,
                                        agent_path=agent_path,
                                        config_elems=config_elems )
            self._dynamic_agent_confs.append( shed_agent_conf_dict )

        if agent_conf_source.parse_monitor():
            self._agent_conf_watcher.watch_file(config_filename)

    def load_item( self, item, agent_path, panel_dict=None, integrated_panel_dict=None, load_panel_dict=True, guid=None, index=None, internal=False ):
        item = ensure_agent_conf_item(item)
        item_type = item.type
        if item_type not in ['agent', 'section'] and not internal:
            # External calls from agent shed code cannot load labels or agent
            # directories.
            return

        if panel_dict is None:
            panel_dict = self._agent_panel
        if integrated_panel_dict is None:
            integrated_panel_dict = self._integrated_agent_panel
        if item_type == 'agent':
            self._load_agent_tag_set( item, panel_dict=panel_dict, integrated_panel_dict=integrated_panel_dict, agent_path=agent_path, load_panel_dict=load_panel_dict, guid=guid, index=index )
        elif item_type == 'workflow':
            self._load_workflow_tag_set( item, panel_dict=panel_dict, integrated_panel_dict=integrated_panel_dict, load_panel_dict=load_panel_dict, index=index )
        elif item_type == 'section':
            self._load_section_tag_set( item, agent_path=agent_path, load_panel_dict=load_panel_dict, index=index )
        elif item_type == 'label':
            self._load_label_tag_set( item, panel_dict=panel_dict, integrated_panel_dict=integrated_panel_dict, load_panel_dict=load_panel_dict, index=index )
        elif item_type == 'agent_dir':
            self._load_agentdir_tag_set( item, panel_dict, agent_path, integrated_panel_dict, load_panel_dict=load_panel_dict )

    def get_shed_config_dict_by_filename( self, filename, default=None ):
        for shed_config_dict in self._dynamic_agent_confs:
            if shed_config_dict[ 'config_filename' ] == filename:
                return shed_config_dict
        return default

    def update_shed_config( self, shed_conf, integrated_panel_changes=True ):
        """ Update the in-memory descriptions of agents and write out the changes
        to integrated agent panel unless we are just deactivating a agent (since
        that doesn't affect that file).
        """
        app = self.app
        for index, my_shed_agent_conf in enumerate( self._dynamic_agent_confs ):
            if shed_conf['config_filename'] == my_shed_agent_conf['config_filename']:
                self._dynamic_agent_confs[ index ] = shed_conf
        if integrated_panel_changes:
            self._save_integrated_agent_panel()
        app.reindex_agent_search()

    def get_section( self, section_id, new_label=None, create_if_needed=False ):
        agent_panel_section_key = str( section_id )
        if agent_panel_section_key in self._agent_panel:
            # Appending a agent to an existing section in agentbox._agent_panel
            agent_section = self._agent_panel[ agent_panel_section_key ]
            log.debug( "Appending to agent panel section: %s" % str( agent_section.name ) )
        elif create_if_needed:
            # Appending a new section to agentbox._agent_panel
            if new_label is None:
                # This might add an ugly section label to the agent panel, but, oh well...
                new_label = section_id
            section_dict = {
                'name': new_label,
                'id': section_id,
                'version': '',
            }
            agent_section = AgentSection( section_dict )
            self._agent_panel.append_section( agent_panel_section_key, agent_section )
            log.debug( "Loading new agent panel section: %s" % str( agent_section.name ) )
        else:
            agent_section = None
        return agent_panel_section_key, agent_section

    def get_integrated_section_for_agent( self, agent ):
        agent_id = agent.id

        if agent_id in self._integrated_section_by_agent:
            return self._integrated_section_by_agent[agent_id]

        return None, None

    def __resolve_agent_path(self, agent_path, config_filename):
        if not agent_path:
            # Default to backward compatible config setting.
            agent_path = self._agent_root_dir
        else:
            # Allow use of __agent_conf_dir__ in agentbox config files.
            agent_conf_dir = os.path.dirname(config_filename)
            agent_path_vars = {"agent_conf_dir": agent_conf_dir}
            agent_path = string.Template(agent_path).safe_substitute(agent_path_vars)
        return agent_path

    def __add_agent_to_agent_panel( self, agent, panel_component, section=False ):
        # See if a version of this agent is already loaded into the agent panel.
        # The value of panel_component will be a AgentSection (if the value of
        # section=True) or self._agent_panel (if section=False).
        agent_id = str( agent.id )
        agent = self._agents_by_id[ agent_id ]
        if section:
            panel_dict = panel_component.elems
        else:
            panel_dict = panel_component

        related_agent = self._lineage_in_panel( panel_dict, agent=agent )
        if related_agent:
            if self._newer_agent( agent, related_agent ):
                panel_dict.replace_agent(
                    previous_agent_id=related_agent.id,
                    new_agent_id=agent_id,
                    agent=agent,
                )
                log.debug( "Loaded agent id: %s, version: %s into agent panel." % ( agent.id, agent.version ) )
        else:
            inserted = False
            index = self._integrated_agent_panel.index_of_agent_id( agent_id )
            if index:
                panel_dict.insert_agent( index, agent )
                inserted = True
            if not inserted:
                # Check the agent's installed versions.
                versions = []
                if hasattr( agent, 'lineage' ):
                    versions = agent.lineage.get_versions()
                for agent_lineage_version in versions:
                    lineage_id = agent_lineage_version.id
                    index = self._integrated_agent_panel.index_of_agent_id( lineage_id )
                    if index:
                        panel_dict.insert_agent( index, agent )
                        inserted = True
                if not inserted:
                    if (
                        agent.guid is None or
                        agent.agent_shed is None or
                        agent.repository_name is None or
                        agent.repository_owner is None or
                        agent.installed_changeset_revision is None
                    ):
                        # We have a agent that was not installed from the Agent
                        # Shed, but is also not yet defined in
                        # integrated_agent_panel.xml, so append it to the agent
                        # panel.
                        panel_dict.append_agent( agent )
                        log.debug( "Loaded agent id: %s, version: %s into agent panel.." % ( agent.id, agent.version ) )
                    else:
                        # We are in the process of installing the agent.

                        agent_lineage = self._lineage_map.get( agent_id )
                        already_loaded = self._lineage_in_panel( panel_dict, agent_lineage=agent_lineage ) is not None
                        if not already_loaded:
                            # If the agent is not defined in integrated_agent_panel.xml, append it to the agent panel.
                            panel_dict.append_agent( agent )
                            log.debug( "Loaded agent id: %s, version: %s into agent panel...." % ( agent.id, agent.version ) )

    def _load_agent_panel( self ):
        for key, item_type, val in self._integrated_agent_panel.panel_items_iter():
            if item_type == panel_item_types.TOOL:
                agent_id = key.replace( 'agent_', '', 1 )
                if agent_id in self._agents_by_id:
                    self.__add_agent_to_agent_panel( val, self._agent_panel, section=False )
                    self._integrated_section_by_agent[agent_id] = '', ''
            elif item_type == panel_item_types.WORKFLOW:
                workflow_id = key.replace( 'workflow_', '', 1 )
                if workflow_id in self._workflows_by_id:
                    workflow = self._workflows_by_id[ workflow_id ]
                    self._agent_panel[ key ] = workflow
                    log.debug( "Loaded workflow: %s %s" % ( workflow_id, workflow.name ) )
            elif item_type == panel_item_types.LABEL:
                self._agent_panel[ key ] = val
            elif item_type == panel_item_types.SECTION:
                section_dict = {
                    'id': val.id or '',
                    'name': val.name or '',
                    'version': val.version or '',
                }
                section = AgentSection( section_dict )
                log.debug( "Loading section: %s" % section_dict.get( 'name' ) )
                for section_key, section_item_type, section_val in val.panel_items_iter():
                    if section_item_type == panel_item_types.TOOL:
                        agent_id = section_key.replace( 'agent_', '', 1 )
                        if agent_id in self._agents_by_id:
                            self.__add_agent_to_agent_panel( section_val, section, section=True )
                            self._integrated_section_by_agent[agent_id] = key, val.name
                    elif section_item_type == panel_item_types.WORKFLOW:
                        workflow_id = section_key.replace( 'workflow_', '', 1 )
                        if workflow_id in self._workflows_by_id:
                            workflow = self._workflows_by_id[ workflow_id ]
                            section.elems[ section_key ] = workflow
                            log.debug( "Loaded workflow: %s %s" % ( workflow_id, workflow.name ) )
                    elif section_item_type == panel_item_types.LABEL:
                        if section_val:
                            section.elems[ section_key ] = section_val
                            log.debug( "Loaded label: %s" % ( section_val.text ) )
                self._agent_panel[ key ] = section

    def _load_integrated_agent_panel_keys( self ):
        """
        Load the integrated agent panel keys, setting values for agents and
        workflows to None.  The values will be reset when the various agent
        panel config files are parsed, at which time the agents and workflows
        are loaded.
        """
        tree = parse_xml( self._integrated_agent_panel_config )
        root = tree.getroot()
        for elem in root:
            key = elem.get( 'id' )
            if elem.tag == 'agent':
                self._integrated_agent_panel.stub_agent( key )
            elif elem.tag == 'workflow':
                self._integrated_agent_panel.stub_workflow( key )
            elif elem.tag == 'section':
                section = AgentSection( elem )
                for section_elem in elem:
                    section_id = section_elem.get( 'id' )
                    if section_elem.tag == 'agent':
                        section.elems.stub_agent( section_id )
                    elif section_elem.tag == 'workflow':
                        section.elems.stub_workflow( section_id )
                    elif section_elem.tag == 'label':
                        section.elems.stub_label( section_id )
                self._integrated_agent_panel.append_section( key, section )
            elif elem.tag == 'label':
                self._integrated_agent_panel.stub_label( key )

    def get_agent( self, agent_id, agent_version=None, get_all_versions=False, exact=False ):
        """Attempt to locate a agent in the agent box."""
        if agent_version:
            agent_version = str( agent_version )

        if get_all_versions and exact:
            raise AssertionError("Cannot specify get_agent with both get_all_versions and exact as True")

        if "/repos/" in agent_id:  # test if agent came from a agentshed
            agent_id_without_agent_shed = agent_id.split("/repos/")[1]
            available_agent_sheds = self.app.agent_shed_registry.agent_sheds.values()
            available_agent_sheds = [ urlparse(agent_shed) for agent_shed in available_agent_sheds ]
            available_agent_sheds = [ url.geturl().replace(url.scheme + "://", '', 1) for url in available_agent_sheds]
            agent_ids = [ agent_shed + "repos/" + agent_id_without_agent_shed for agent_shed in available_agent_sheds]
            if agent_id in agent_ids:  # move original agent_id to the top of agent_ids
                agent_ids.remove(agent_id)
            agent_ids.insert(0, agent_id)
        else:
            agent_ids = [agent_id]
        for agent_id in agent_ids:
            if agent_id in self._agents_by_id and not get_all_versions:
                if agent_version and agent_version in self._agent_versions_by_id[ agent_id ]:
                    return self._agent_versions_by_id[ agent_id ][ agent_version ]
                # agent_id exactly matches an available agent by id (which is 'old' agent_id or guid)
                return self._agents_by_id[ agent_id ]
            # exact agent id match not found, or all versions requested, search for other options, e.g. migrated agents or different versions
            rval = []
            agent_lineage = self._lineage_map.get( agent_id )
            if agent_lineage:
                lineage_agent_versions = agent_lineage.get_versions( )
                for lineage_agent_version in lineage_agent_versions:
                    lineage_agent = self._agent_from_lineage_version( lineage_agent_version )
                    if lineage_agent:
                        rval.append( lineage_agent )
            if not rval:
                # still no agent, do a deeper search and try to match by old ids
                for agent in self._agents_by_id.itervalues():
                    if agent.old_id == agent_id:
                        rval.append( agent )
            if rval:
                if get_all_versions:
                    return rval
                else:
                    if agent_version:
                        # return first agent with matching version
                        for agent in rval:
                            if agent.version == agent_version:
                                return agent
                    # No agent matches by version, simply return the first available agent found
                    return rval[0]
            # We now likely have a Agentshed guid passed in, but no supporting database entries
            # If the agent exists by exact id and is loaded then provide exact match within a list
            if agent_id in self._agents_by_id:
                return[ self._agents_by_id[ agent_id ] ]
        return None

    def has_agent( self, agent_id, agent_version=None, exact=False ):
        return self.get_agent( agent_id, agent_version=agent_version, exact=exact ) is not None

    def get_agent_id( self, agent_id ):
        """ Take a agent id (potentially from a different Galaxy instance or that
        is no longer loaded  - and find the closest match to the currently loaded
        agents (using get_agent for inexact matches which currently returns the oldest
        agent shed installed agent with the same short id).
        """
        if agent_id not in self._agents_by_id:
            agent = self.get_agent( agent_id )
            if agent:
                agent_id = agent.id
            else:
                agent_id = None
        # else exact match - leave unmodified.
        return agent_id

    def get_loaded_agents_by_lineage( self, agent_id ):
        """Get all loaded agents associated by lineage to the agent whose id is agent_id."""
        agent_lineage = self._lineage_map.get( agent_id )
        if agent_lineage:
            lineage_agent_versions = agent_lineage.get_versions( )
            available_agent_versions = []
            for lineage_agent_version in lineage_agent_versions:
                agent = self._agent_from_lineage_version( lineage_agent_version )
                if agent:
                    available_agent_versions.append( agent )
            return available_agent_versions
        else:
            if agent_id in self._agents_by_id:
                agent = self._agents_by_id[ agent_id ]
                return [ agent ]
        return []

    def agents( self ):
        return iteritems(self._agents_by_id)

    def dynamic_confs( self, include_migrated_agent_conf=False ):
        confs = []
        for dynamic_agent_conf_dict in self._dynamic_agent_confs:
            dynamic_agent_conf_filename = dynamic_agent_conf_dict[ 'config_filename' ]
            if include_migrated_agent_conf or (dynamic_agent_conf_filename != self.app.config.migrated_agents_config):
                confs.append( dynamic_agent_conf_dict )
        return confs

    def dynamic_conf_filenames( self, include_migrated_agent_conf=False ):
        """ Return list of dynamic agent configuration filenames (shed_agents).
        These must be used with various dynamic agent configuration update
        operations (e.g. with update_shed_config).
        """
        for dynamic_agent_conf_dict in self.dynamic_confs( include_migrated_agent_conf=include_migrated_agent_conf ):
            yield dynamic_agent_conf_dict[ 'config_filename' ]

    def remove_from_panel( self, agent_id, section_key='', remove_from_config=True ):

        def remove_from_dict( has_elems, integrated_has_elems ):
            agent_key = 'agent_%s' % str( agent_id )
            available_agent_versions = self.get_loaded_agents_by_lineage( agent_id )
            if agent_key in has_elems:
                if available_agent_versions:
                    available_agent_versions.reverse()
                    replacement_agent_key = None
                    replacement_agent_version = None
                    # Since we are going to remove the agent from the section, replace it with
                    # the newest loaded version of the agent.
                    for available_agent_version in available_agent_versions:
                        available_agent_section_id, available_agent_section_name = available_agent_version.get_panel_section()
                        # I suspect "available_agent_version.id in has_elems.keys()" doesn't
                        # belong in the following line or at least I don't understand what
                        # purpose it might serve. -John
                        if available_agent_version.id in has_elems.keys() or (available_agent_section_id == section_key):
                            replacement_agent_key = 'agent_%s' % str( available_agent_version.id )
                            replacement_agent_version = available_agent_version
                            break
                    if replacement_agent_key and replacement_agent_version:
                        # Get the index of the agent_key in the agent_section.
                        for agent_panel_index, key in enumerate( has_elems.keys() ):
                            if key == agent_key:
                                break
                        # Remove the agent from the agent panel.
                        del has_elems[ agent_key ]
                        # Add the replacement agent at the same location in the agent panel.
                        has_elems.insert( agent_panel_index,
                                          replacement_agent_key,
                                          replacement_agent_version )
                        self._integrated_section_by_agent[ agent_id ] = available_agent_section_id, available_agent_section_name
                    else:
                        del has_elems[ agent_key ]

                        if agent_id in self._integrated_section_by_agent:
                            del self._integrated_section_by_agent[ agent_id ]
                else:
                    del has_elems[ agent_key ]

                    if agent_id in self._integrated_section_by_agent:
                        del self._integrated_section_by_agent[ agent_id ]
            if remove_from_config:
                itegrated_items = integrated_has_elems.panel_items()
                if agent_key in itegrated_items:
                    del itegrated_items[ agent_key ]

        if section_key:
            _, agent_section = self.get_section( section_key )
            if agent_section:
                remove_from_dict( agent_section.elems, self._integrated_agent_panel.get( section_key, {} ) )
        else:
            remove_from_dict( self._agent_panel, self._integrated_agent_panel )

    def _load_agent_tag_set( self, item, panel_dict, integrated_panel_dict, agent_path, load_panel_dict, guid=None, index=None ):
        try:
            path = item.get( "file" )
            repository_id = None

            agent_shed_repository = None
            can_load_into_panel_dict = True
            if guid is not None:
                # The agent is contained in an installed agent shed repository, so load
                # the agent only if the repository has not been marked deleted.
                agent_shed = item.elem.find( "agent_shed" ).text
                repository_name = item.elem.find( "repository_name" ).text
                repository_owner = item.elem.find( "repository_owner" ).text
                installed_changeset_revision_elem = item.elem.find( "installed_changeset_revision" )
                if installed_changeset_revision_elem is None:
                    # Backward compatibility issue - the tag used to be named 'changeset_revision'.
                    installed_changeset_revision_elem = item.elem.find( "changeset_revision" )
                installed_changeset_revision = installed_changeset_revision_elem.text
                try:
                    splitted_path = path.split('/')
                    assert splitted_path[0] == agent_shed
                    assert splitted_path[2] == repository_owner
                    assert splitted_path[3] == repository_name
                    if splitted_path[4] != installed_changeset_revision:
                        # This can happen if the Agent Shed repository has been
                        # updated to a new revision and the installed_changeset_revision
                        # element in shed_agent_conf.xml file has been updated too
                        log.debug("The installed_changeset_revision for agent %s is %s, using %s instead", path, installed_changeset_revision, splitted_path[4])
                        installed_changeset_revision = splitted_path[4]
                except Exception as e:
                    log.debug("Error while loading agent %s : %s", path, e)
                    pass
                agent_shed_repository = self._get_agent_shed_repository( agent_shed,
                                                                       repository_name,
                                                                       repository_owner,
                                                                       installed_changeset_revision )
                if agent_shed_repository:
                    # Only load agents if the repository is not deactivated or uninstalled.
                    can_load_into_panel_dict = not agent_shed_repository.deleted
                    repository_id = self.app.security.encode_id( agent_shed_repository.id )
                # Else there is not yet a agent_shed_repository record, we're in the process of installing
                # a new repository, so any included agents can be loaded into the agent panel.
            agent = self.load_agent( os.path.join( agent_path, path ), guid=guid, repository_id=repository_id )
            if string_as_bool(item.get( 'hidden', False )):
                agent.hidden = True
            key = 'agent_%s' % str( agent.id )
            if can_load_into_panel_dict:
                if guid is not None:
                    agent.agent_shed = agent_shed
                    agent.repository_name = repository_name
                    agent.repository_owner = repository_owner
                    agent.installed_changeset_revision = installed_changeset_revision
                    agent.guid = guid
                    agent.version = item.elem.find( "version" ).text
                # Make sure the agent has a agent_version.
                agent_lineage = self._lineage_map.register( agent, agent_shed_repository=agent_shed_repository )
                # Load the agent's lineage ids.
                agent.lineage = agent_lineage
                if item.has_elem:
                    self._agent_tag_manager.handle_tags( agent.id, item.elem )
                self.__add_agent( agent, load_panel_dict, panel_dict )
            # Always load the agent into the integrated_panel_dict, or it will not be included in the integrated_agent_panel.xml file.
            integrated_panel_dict.update_or_append( index, key, agent )
            # If labels were specified in the agentbox config, attach them to
            # the agent.
            labels = item.labels
            if labels is not None:
                agent.labels = labels
        except IOError:
            log.error( "Error reading agent configuration file from path: %s." % path )
        except Exception:
            log.exception( "Error reading agent from path: %s" % path )

    def _get_agent_shed_repository( self, agent_shed, name, owner, installed_changeset_revision ):
        # Abstract class does't have a dependency on the database, for full agent shed
        # support the actual Galaxy AgentBox implement this method and return a AgentShd repository.
        return None

    def __add_agent( self, agent, load_panel_dict, panel_dict ):
        # Allow for the same agent to be loaded into multiple places in the
        # agent panel.  We have to handle the case where the agent is contained
        # in a repository installed from the agent shed, and the Galaxy
        # administrator has retrieved updates to the installed repository.  In
        # this case, the agent may have been updated, but the version was not
        # changed, so the agent should always be reloaded here.  We used to
        # only load the agent if it was not found in self._agents_by_id, but
        # performing that check did not enable this scenario.
        self.register_agent( agent )
        if load_panel_dict:
            self.__add_agent_to_agent_panel( agent, panel_dict, section=isinstance( panel_dict, AgentSection ) )

    def _load_workflow_tag_set( self, item, panel_dict, integrated_panel_dict, load_panel_dict, index=None ):
        try:
            # TODO: should id be encoded?
            workflow_id = item.get( 'id' )
            workflow = self._load_workflow( workflow_id )
            self._workflows_by_id[ workflow_id ] = workflow
            key = 'workflow_' + workflow_id
            if load_panel_dict:
                panel_dict[ key ] = workflow
            # Always load workflows into the integrated_panel_dict.
            integrated_panel_dict.update_or_append( index, key, workflow )
        except:
            log.exception( "Error loading workflow: %s" % workflow_id )

    def _load_label_tag_set( self, item, panel_dict, integrated_panel_dict, load_panel_dict, index=None ):
        label = AgentSectionLabel( item )
        key = 'label_' + label.id
        if load_panel_dict:
            panel_dict[ key ] = label
        integrated_panel_dict.update_or_append( index, key, label )

    def _load_section_tag_set( self, item, agent_path, load_panel_dict, index=None ):
        key = item.get( "id" )
        if key in self._agent_panel:
            section = self._agent_panel[ key ]
            elems = section.elems
        else:
            section = AgentSection( item )
            elems = section.elems
        if key in self._integrated_agent_panel:
            integrated_section = self._integrated_agent_panel[ key ]
            integrated_elems = integrated_section.elems
        else:
            integrated_section = AgentSection( item )
            integrated_elems = integrated_section.elems
        for sub_index, sub_item in enumerate( item.items ):
            self.load_item(
                sub_item,
                agent_path=agent_path,
                panel_dict=elems,
                integrated_panel_dict=integrated_elems,
                load_panel_dict=load_panel_dict,
                guid=sub_item.get( 'guid' ),
                index=sub_index,
                internal=True,
            )

        # Ensure each agent's section is stored
        for section_key, section_item_type, section_item in integrated_elems.panel_items_iter():
            if section_item_type == panel_item_types.TOOL:
                if section_item:
                    agent_id = section_key.replace( 'agent_', '', 1 )
                    self._integrated_section_by_agent[agent_id] = integrated_section.id, integrated_section.name

        if load_panel_dict:
            self._agent_panel[ key ] = section
        # Always load sections into the integrated_agent_panel.
        self._integrated_agent_panel.update_or_append( index, key, integrated_section )

    def _load_agentdir_tag_set(self, item, elems, agent_path, integrated_elems, load_panel_dict):
        directory = os.path.join( agent_path, item.get("dir") )
        recursive = string_as_bool( item.get("recursive", True) )
        self.__watch_directory( directory, elems, integrated_elems, load_panel_dict, recursive, force_watch=True )

    def __watch_directory( self, directory, elems, integrated_elems, load_panel_dict, recursive, force_watch=False ):

        def quick_load( agent_file, async=True ):
            try:
                agent = self.load_agent( agent_file )
                self.__add_agent( agent, load_panel_dict, elems )
                # Always load the agent into the integrated_panel_dict, or it will not be included in the integrated_agent_panel.xml file.
                key = 'agent_%s' % str( agent.id )
                integrated_elems[ key ] = agent

                if async:
                    self._load_agent_panel()
                    self._save_integrated_agent_panel()
                return agent.id
            except Exception:
                log.exception("Failed to load potential agent %s." % agent_file)
                return None

        agent_loaded = False
        for name in os.listdir( directory ):
            child_path = os.path.join(directory, name)
            if os.path.isdir(child_path) and recursive:
                self.__watch_directory(child_path, elems, integrated_elems, load_panel_dict, recursive)
            elif self._looks_like_a_agent(child_path):
                quick_load( child_path, async=False )
                agent_loaded = True
        if agent_loaded or force_watch:
            self._agent_watcher.watch_directory( directory, quick_load )

    def load_agent( self, config_file, guid=None, repository_id=None, use_cached=True, **kwds ):
        """Load a single agent from the file named by `config_file` and return an instance of `Agent`."""
        # Parse XML configuration file and get the root element
        agent_cache = getattr( self.app, 'agent_cache', None )
        agent = use_cached and agent_cache and agent_cache.get_agent( config_file )
        if not agent:
            agent = self.create_agent( config_file=config_file, repository_id=repository_id, guid=guid, **kwds )
            if agent_cache:
                self.app.agent_cache.cache_agent(config_file, agent)
        agent_id = agent.id
        if not agent_id.startswith("__"):
            # do not monitor special agents written to tmp directory - no reason
            # to monitor such a large directory.
            self._agent_watcher.watch_file( config_file, agent.id )
        return agent

    def load_hidden_lib_agent( self, path ):
        agent_xml = os.path.join( os.getcwd(), "lib", path )
        return self.load_hidden_agent( agent_xml )

    def load_hidden_agent( self, config_file, **kwds ):
        """ Load a hidden agent (in this context meaning one that does not
        appear in the agent panel) and register it in _agents_by_id.
        """
        agent = self.load_agent( config_file, **kwds )
        self.register_agent( agent )
        return agent

    def register_agent( self, agent ):
        agent_id = agent.id
        version = agent.version or None
        if agent_id not in self._agent_versions_by_id:
            self._agent_versions_by_id[ agent_id ] = { version: agent }
        else:
            self._agent_versions_by_id[ agent_id ][ version ] = agent
        if agent_id in self._agents_by_id:
            related_agent = self._agents_by_id[ agent_id ]
            # This one becomes the default un-versioned agent
            # if newer.
            if self._newer_agent( agent, related_agent ):
                self._agents_by_id[ agent_id ] = agent
        else:
            self._agents_by_id[ agent_id ] = agent

    def package_agent( self, trans, agent_id ):
        """
        Create a tarball with the agent's xml, help images, and test data.
        :param trans: the web transaction
        :param agent_id: the agent ID from app.agentbox
        :returns: tuple of tarball filename, success True/False, message/None
        """
        # Make sure the agent is actually loaded.
        if agent_id not in self._agents_by_id:
            raise ObjectNotFound("No agent found with id '%s'." % escape( agent_id ))
        else:
            agent = self._agents_by_id[ agent_id ]
            return agent.to_archive()

    def reload_agent_by_id( self, agent_id ):
        """
        Attempt to reload the agent identified by 'agent_id', if successful
        replace the old agent.
        """
        if agent_id not in self._agents_by_id:
            message = "No agent with id %s" % escape( agent_id )
            status = 'error'
        else:
            old_agent = self._agents_by_id[ agent_id ]
            new_agent = self.load_agent( old_agent.config_file )
            # The agent may have been installed from a agent shed, so set the agent shed attributes.
            # Since the agent version may have changed, we don't override it here.
            new_agent.id = old_agent.id
            new_agent.guid = old_agent.guid
            new_agent.agent_shed = old_agent.agent_shed
            new_agent.repository_name = old_agent.repository_name
            new_agent.repository_owner = old_agent.repository_owner
            new_agent.installed_changeset_revision = old_agent.installed_changeset_revision
            new_agent.old_id = old_agent.old_id
            # Replace old_agent with new_agent in self._agent_panel
            agent_key = 'agent_' + agent_id
            for key, val in self._agent_panel.items():
                if key == agent_key:
                    self._agent_panel[ key ] = new_agent
                    break
                elif key.startswith( 'section' ):
                    if agent_key in val.elems:
                        self._agent_panel[ key ].elems[ agent_key ] = new_agent
                        break
            # (Re-)Register the reloaded agent, this will handle
            #  _agents_by_id and _agent_versions_by_id
            self.register_agent( new_agent )
            message = "Reloaded the agent:<br/>"
            message += "<b>name:</b> %s<br/>" % escape( old_agent.name )
            message += "<b>id:</b> %s<br/>" % escape( old_agent.id )
            message += "<b>version:</b> %s" % escape( old_agent.version )
            status = 'done'
        return message, status

    def remove_agent_by_id( self, agent_id, remove_from_panel=True ):
        """
        Attempt to remove the agent identified by 'agent_id'. Ignores
        agent lineage - so to remove a agent with potentially multiple
        versions send remove_from_panel=False and handle the logic of
        promoting the next newest version of the agent into the panel
        if needed.
        """
        if agent_id not in self._agents_by_id:
            message = "No agent with id %s" % escape( agent_id )
            status = 'error'
        else:
            agent = self._agents_by_id[ agent_id ]
            del self._agents_by_id[ agent_id ]
            agent_cache = getattr( self.app, 'agent_cache', None )
            if agent_cache:
                agent_cache.expire_agent( agent_id )
            if remove_from_panel:
                agent_key = 'agent_' + agent_id
                for key, val in self._agent_panel.items():
                    if key == agent_key:
                        del self._agent_panel[ key ]
                        break
                    elif key.startswith( 'section' ):
                        if agent_key in val.elems:
                            del self._agent_panel[ key ].elems[ agent_key ]
                            break
                if agent_id in self.data_manager_agents:
                    del self.data_manager_agents[ agent_id ]
            # TODO: do we need to manually remove from the integrated panel here?
            message = "Removed the agent:<br/>"
            message += "<b>name:</b> %s<br/>" % escape( agent.name )
            message += "<b>id:</b> %s<br/>" % escape( agent.id )
            message += "<b>version:</b> %s" % escape( agent.version )
            status = 'done'
        return message, status

    def get_sections( self ):
        for k, v in self._agent_panel.items():
            if isinstance( v, AgentSection ):
                yield (v.id, v.name)

    def find_section_id( self, agent_panel_section_id ):
        """
        Find the section ID referenced by the key or return '' indicating
        no such section id.
        """
        if not agent_panel_section_id:
            agent_panel_section_id = ''
        else:
            if agent_panel_section_id not in self._agent_panel:
                # Hack introduced without comment in a29d54619813d5da992b897557162a360b8d610c-
                # not sure why it is needed.
                fixed_agent_panel_section_id = 'section_%s' % agent_panel_section_id
                if fixed_agent_panel_section_id in self._agent_panel:
                    agent_panel_section_id = fixed_agent_panel_section_id
                else:
                    agent_panel_section_id = ''
        return agent_panel_section_id

    def _load_workflow( self, workflow_id ):
        """
        Return an instance of 'Workflow' identified by `id`,
        which is encoded in the agent panel.
        """
        id = self.app.security.decode_id( workflow_id )
        stored = self.app.model.context.query( self.app.model.StoredWorkflow ).get( id )
        return stored.latest_workflow

    def agent_panel_contents( self, trans, **kwds ):
        """ Filter agent_panel contents for displaying for user.
        """
        filter_method = self._build_filter_method( trans )
        for _, item_type, elt in self._agent_panel.panel_items_iter():
            elt = filter_method( elt, item_type )
            if elt:
                yield elt

    def to_dict( self, trans, in_panel=True, **kwds ):
        """
        to_dict agentbox.
        """
        if in_panel:
            panel_elts = list( self.agent_panel_contents( trans, **kwds ) )
            # Produce panel.
            rval = []
            kwargs = dict(
                trans=trans,
                link_details=True
            )
            for elt in panel_elts:
                rval.append( elt.to_dict( **kwargs ) )
        else:
            filter_method = self._build_filter_method( trans )
            agents = []
            for id, agent in self._agents_by_id.items():
                agent = filter_method( agent, panel_item_types.TOOL )
                if not agent:
                    continue
                agents.append( agent.to_dict( trans, link_details=True ) )
            rval = agents

        return rval

    def shutdown(self):
        exception = None
        try:
            self._agent_watcher.shutdown()
        except Exception as e:
            exception = e

        try:
            self._agent_conf_watcher.shutdown()
        except Exception as e:
            exception = exception or e

        if exception:
            raise exception

    def _lineage_in_panel( self, panel_dict, agent=None, agent_lineage=None ):
        """ If agent with same lineage already in panel (or section) - find
        and return it. Otherwise return None.
        """
        if agent_lineage is None:
            assert agent is not None
            if not hasattr( agent, "lineage" ):
                return None
            agent_lineage = agent.lineage
        lineage_agent_versions = agent_lineage.get_versions( reverse=True )
        for lineage_agent_version in lineage_agent_versions:
            lineage_agent = self._agent_from_lineage_version( lineage_agent_version )
            if lineage_agent:
                lineage_id = lineage_agent.id
                if panel_dict.has_agent_with_id( lineage_id ):
                    return panel_dict.get_agent_with_id( lineage_id )
        return None

    def _newer_agent( self, agent1, agent2 ):
        """ Return True if agent1 is considered "newer" given its own lineage
        description.
        """
        if not hasattr( agent1, "lineage" ):
            return True
        lineage_agent_versions = agent1.lineage.get_versions()
        for lineage_agent_version in lineage_agent_versions:
            lineage_agent = self._agent_from_lineage_version( lineage_agent_version )
            if lineage_agent is agent1:
                return False
            if lineage_agent is agent2:
                return True
        return True

    def _agent_from_lineage_version( self, lineage_agent_version ):
        if lineage_agent_version.id_based:
            return self._agents_by_id.get( lineage_agent_version.id, None )
        else:
            return self._agent_versions_by_id.get( lineage_agent_version.id, {} ).get( lineage_agent_version.version, None )

    def _build_filter_method( self, trans ):
        context = Bunch( agentbox=self, trans=trans )
        filters = self._filter_factory.build_filters( trans )
        return lambda element, item_type: _filter_for_panel(element, item_type, filters, context)


def _filter_for_panel( item, item_type, filters, context ):
    """
    Filters agent panel elements so that only those that are compatible
    with provided filters are kept.
    """
    def _apply_filter( filter_item, filter_list ):
        for filter_method in filter_list:
            if not filter_method( context, filter_item ):
                return False
        return True
    if item_type == panel_item_types.TOOL:
        if _apply_filter( item, filters[ 'agent' ] ):
            return item
    elif item_type == panel_item_types.LABEL:
        if _apply_filter( item, filters[ 'label' ] ):
            return item
    elif item_type == panel_item_types.SECTION:
        # Filter section item-by-item. Only show a label if there are
        # non-filtered agents below it.

        if _apply_filter( item, filters[ 'section' ] ):
            cur_label_key = None
            agents_under_label = False
            filtered_elems = item.elems.copy()
            for key, section_item_type, section_item in item.panel_items_iter():
                if section_item_type == panel_item_types.TOOL:
                    # Filter agent.
                    if _apply_filter( section_item, filters[ 'agent' ] ):
                        agents_under_label = True
                    else:
                        del filtered_elems[ key ]
                elif section_item_type == panel_item_types.LABEL:
                    # If there is a label and it does not have agents,
                    # remove it.
                    if ( cur_label_key and not agents_under_label ) or not _apply_filter( section_item, filters[ 'label' ] ):
                        del filtered_elems[ cur_label_key ]

                    # Reset attributes for new label.
                    cur_label_key = key
                    agents_under_label = False

            # Handle last label.
            if cur_label_key and not agents_under_label:
                del filtered_elems[ cur_label_key ]

            # Only return section if there are elements.
            if len( filtered_elems ) != 0:
                copy = item.copy()
                copy.elems = filtered_elems
                return copy

    return None


class BaseGalaxyAgentBox(AbstractAgentBox):
    """
    Extend the AbstractAgentBox with more Galaxy agenting-specific
    functionality. Adds dependencies on dependency resolution and
    agent loading modules, that an abstract description of panels
    shouldn't really depend on.
    """

    def __init__(self, config_filenames, agent_root_dir, app):
        super(BaseGalaxyAgentBox, self).__init__(config_filenames, agent_root_dir, app)
        self._init_dependency_manager()

    @property
    def sa_session( self ):
        """
        Returns a SQLAlchemy session
        """
        return self.app.model.context

    def _looks_like_a_agent(self, path):
        return looks_like_a_agent(path, enable_beta_formats=getattr(self.app.config, "enable_beta_agent_formats", False))

    def _init_dependency_manager( self ):
        self.dependency_manager = build_dependency_manager( self.app.config )

    def reload_dependency_manager(self):
        self._init_dependency_manager()
