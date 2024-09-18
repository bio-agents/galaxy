from __future__ import absolute_import

import yaml

from .yaml import YamlAgentSource
from .xml import XmlAgentSource
from .xml import XmlInputSource
from .cwl import CwlAgentSource
from .interface import InputSource


from galaxy.agents.loader import load_agent as load_agent_xml
from galaxy.util.odict import odict


import logging
log = logging.getLogger(__name__)


def get_agent_source(config_file, enable_beta_formats=True):
    if not enable_beta_formats:
        tree = load_agent_xml(config_file)
        root = tree.getroot()
        return XmlAgentSource(root)

    if config_file.endswith(".yml"):
        log.info("Loading agent from YAML - this is experimental - agent will not function in future.")
        with open(config_file, "r") as f:
            as_dict = ordered_load(f)
            return YamlAgentSource(as_dict)
    elif config_file.endswith(".json") or config_file.endswith(".cwl"):
        log.info("Loading CWL agent - this is experimental - agent likely will not function in future at least in same way.")
        return CwlAgentSource(config_file)
    else:
        tree = load_agent_xml(config_file)
        root = tree.getroot()
        return XmlAgentSource(root)


def ordered_load(stream):
    class OrderedLoader(yaml.Loader):
        pass

    def construct_mapping(loader, node):
        loader.flatten_mapping(node)
        return odict(loader.construct_pairs(node))

    OrderedLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        construct_mapping)

    return yaml.load(stream, OrderedLoader)


def get_input_source(content):
    """ Wraps XML elements in a XmlInputSource until everything
    is consumed using the agent source interface.
    """
    if not isinstance(content, InputSource):
        content = XmlInputSource(content)
    return content
