from abc import ABCMeta
from abc import abstractmethod

from galaxy.util import parse_xml, string_as_bool
import yaml

DEFAULT_MONITOR = False


class AgentConfSource(object):
    """ This interface represents an abstract source to parse agent
    information from.
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def parse_items(self):
        """ Return a list of AgentConfItem
        """

    @abstractmethod
    def parse_agent_path(self):
        """ Return agent_path for agents in this agentbox.
        """

    def parse_monitor(self):
        """ Monitor the agentbox configuration source for changes and
        reload. """
        return DEFAULT_MONITOR


class XmlAgentConfSource(AgentConfSource):

    def __init__(self, config_filename):
        tree = parse_xml(config_filename)
        self.root = tree.getroot()

    def parse_agent_path(self):
        return self.root.get('agent_path')

    def parse_items(self):
        return map(ensure_agent_conf_item, self.root.getchildren())

    def parse_monitor(self):
        return string_as_bool(self.root.get('monitor', DEFAULT_MONITOR))


class YamlAgentConfSource(AgentConfSource):

    def __init__(self, config_filename):
        with open(config_filename, "r") as f:
            as_dict = yaml.load(f)
        self.as_dict = as_dict

    def parse_agent_path(self):
        return self.as_dict.get('agent_path')

    def parse_items(self):
        return map(AgentConfItem.from_dict, self.as_dict.get('items'))

    def parse_monitor(self):
        return self.as_dict.get('monitor', DEFAULT_MONITOR)


class AgentConfItem(object):
    """ This interface represents an abstract source to parse agent
    information from.
    """

    def __init__(self, type, attributes, elem=None):
        self.type = type
        self.attributes = attributes
        self._elem = elem

    @classmethod
    def from_dict(cls, _as_dict):
        as_dict = _as_dict.copy()
        type = as_dict.get('type')
        del as_dict['type']
        attributes = as_dict
        if type == 'section':
            items = map(cls.from_dict, as_dict['items'])
            del as_dict['items']
            item = AgentConfSection(attributes, items)
        else:
            item = AgentConfItem(type, attributes)
        return item

    def get(self, key, default=None):
        return self.attributes.get(key, default)

    @property
    def has_elem(self):
        return self._elem is not None

    @property
    def elem(self):
        if self._elem is None:
            raise Exception("item.elem called on agentbox element from non-XML source")
        return self._elem

    @property
    def labels(self):
        labels = None
        if "labels" in self.attributes:
            labels = [ label.strip() for label in self.attributes["labels"].split( "," ) ]
        return labels


class AgentConfSection(AgentConfItem):

    def __init__(self, attributes, items, elem=None):
        super(AgentConfSection, self).__init__('section', attributes, elem)
        self.items = items


def ensure_agent_conf_item(xml_or_item):
    if xml_or_item is None:
        return None
    elif isinstance(xml_or_item, AgentConfItem):
        return xml_or_item
    else:
        elem = xml_or_item
        type = elem.tag
        attributes = elem.attrib
        if type != "section":
            return AgentConfItem(type, attributes, elem)
        else:
            items = map(ensure_agent_conf_item, elem.getchildren())
            return AgentConfSection(attributes, items, elem=elem)


def get_agentbox_parser(config_filename):
    is_yaml = any(map(lambda e: config_filename.endswith(e), [".yml", ".yaml", ".json"]))
    if is_yaml:
        return YamlAgentConfSource(config_filename)
    else:
        return XmlAgentConfSource(config_filename)
