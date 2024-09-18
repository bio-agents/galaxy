from xml.etree import ElementTree as ET

from galaxy.agents.agentbox import AgentSection


def test_agent_section( ):
    elem = ET.Element( 'section' )
    elem.attrib[ 'name' ] = "Cool Agents"
    elem.attrib[ 'id' ] = "cool1"

    section = AgentSection( elem )
    assert section.id == "cool1"
    assert section.name == "Cool Agents"
    assert section.version == ""

    section = AgentSection( dict(
        id="cool1",
        name="Cool Agents"
    ) )
    assert section.id == "cool1"
    assert section.name == "Cool Agents"
    assert section.version == ""

    section = AgentSection()
    assert section.id == ""
    assert section.name == ""
    assert section.version == ""
