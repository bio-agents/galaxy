from abc import abstractmethod

from galaxy.util.odict import odict
from galaxy.util import bunch
from galaxy.util.dictifiable import Dictifiable
from .parser import ensure_agent_conf_item

from six import iteritems

panel_item_types = bunch.Bunch(
    TOOL="TOOL",
    WORKFLOW="WORKFLOW",
    SECTION="SECTION",
    LABEL="LABEL",
)


class HasPanelItems:
    """
    """

    @abstractmethod
    def panel_items( self ):
        """ Return an ordered dictionary-like object describing agent panel
        items (such as workflows, agents, labels, and sections).
        """

    def panel_items_iter( self ):
        """ Iterate through panel items each represented as a tuple of
        (panel_key, panel_type, panel_content).
        """
        for panel_key, panel_value in iteritems(self.panel_items()):
            if panel_value is None:
                continue
            panel_type = panel_item_types.SECTION
            if panel_key.startswith("agent_"):
                panel_type = panel_item_types.TOOL
            elif panel_key.startswith("label_"):
                panel_type = panel_item_types.LABEL
            elif panel_key.startswith("workflow_"):
                panel_type = panel_item_types.WORKFLOW
            yield (panel_key, panel_type, panel_value)


class AgentSection( Dictifiable, HasPanelItems, object ):
    """
    A group of agents with similar type/purpose that will be displayed as a
    group in the user interface.
    """

    dict_collection_visible_keys = ( 'id', 'name', 'version' )

    def __init__( self, item=None ):
        """ Build a AgentSection from an ElementTree element or a dictionary.
        """
        if item is None:
            item = dict()
        self.name = item.get('name') or ''
        self.id = item.get('id') or ''
        self.version = item.get('version') or ''
        self.elems = AgentPanelElements()

    def copy( self ):
        copy = AgentSection()
        copy.name = self.name
        copy.id = self.id
        copy.version = self.version
        copy.elems = self.elems.copy()
        return copy

    def to_dict( self, trans, link_details=False ):
        """ Return a dict that includes section's attributes. """

        section_dict = super( AgentSection, self ).to_dict()
        section_elts = []
        kwargs = dict(
            trans=trans,
            link_details=link_details
        )
        for elt in self.elems.values():
            section_elts.append( elt.to_dict( **kwargs ) )
        section_dict[ 'elems' ] = section_elts

        return section_dict

    def panel_items( self ):
        return self.elems


class AgentSectionLabel( Dictifiable, object ):
    """
    A label for a set of agents that can be displayed above groups of agents
    and sections in the user interface
    """

    dict_collection_visible_keys = ( 'id', 'text', 'version' )

    def __init__( self, item ):
        """ Build a AgentSectionLabel from an ElementTree element or a
        dictionary.
        """
        item = ensure_agent_conf_item(item)
        self.text = item.get( "text" )
        self.id = item.get( "id" )
        self.version = item.get( "version" ) or ''

    def to_dict( self, **kwds ):
        return super( AgentSectionLabel, self ).to_dict()


class AgentPanelElements( HasPanelItems, odict ):
    """ Represents an ordered dictionary of agent entries - abstraction
    used both by agent panel itself (normal and integrated) and its sections.
    """

    def update_or_append( self, index, key, value ):
        if key in self or index is None:
            self[ key ] = value
        else:
            self.insert( index, key, value )

    def has_agent_with_id( self, agent_id ):
        key = 'agent_%s' % agent_id
        return key in self

    def replace_agent( self, previous_agent_id, new_agent_id, agent ):
        previous_key = 'agent_%s' % previous_agent_id
        new_key = 'agent_%s' % new_agent_id
        index = self.keys().index( previous_key )
        del self[ previous_key ]
        self.insert( index, new_key, agent )

    def index_of_agent_id( self, agent_id ):
        query_key = 'agent_%s' % agent_id
        for index, target_key in enumerate( self.keys() ):
            if query_key == target_key:
                return index
        return None

    def insert_agent( self, index, agent ):
        key = "agent_%s" % agent.id
        self.insert( index, key, agent )

    def get_agent_with_id( self, agent_id ):
        key = "agent_%s" % agent_id
        return self[ key ]

    def append_agent( self, agent ):
        key = "agent_%s" % agent.id
        self[ key ] = agent

    def stub_agent( self, key ):
        key = "agent_%s" % key
        self[ key ] = None

    def stub_workflow( self, key ):
        key = 'workflow_%s' % key
        self[ key ] = None

    def stub_label( self, key ):
        key = 'label_%s' % key
        self[ key ] = None

    def append_section( self, key, section_elems ):
        self[ key ] = section_elems

    def panel_items( self ):
        return self
