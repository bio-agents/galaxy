

def is_datasource(agent_xml):
    """Returns true if the agent is a datasource agent"""
    return agent_xml.getroot().attrib.get('agent_type', '') == 'data_source'
