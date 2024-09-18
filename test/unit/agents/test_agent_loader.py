from tempfile import mkdtemp
from shutil import rmtree
import os

from galaxy.util import parse_xml
from galaxy.agents.loader import template_macro_params, load_agent


def test_loader():

    class TestAgentDirectory(object):
        def __init__(self):
            self.temp_directory = mkdtemp()

        def __enter__(self):
            return self

        def __exit__(self, type, value, tb):
            rmtree(self.temp_directory)

        def write(self, contents, name="agent.xml"):
            open(os.path.join(self.temp_directory, name), "w").write(contents)

        def load(self, name="agent.xml", preprocess=True):
            if preprocess:
                loader = load_agent
            else:
                loader = parse_xml
            return loader(os.path.join(self.temp_directory, name))

    # Test simple macro replacement.
    with TestAgentDirectory() as agent_dir:
        agent_dir.write('''
<agent>
    <expand macro="inputs" />
    <macros>
        <macro name="inputs">
            <inputs />
        </macro>
    </macros>
</agent>''')
        xml = agent_dir.load(preprocess=False)
        assert xml.find("inputs") is None
        xml = agent_dir.load(preprocess=True)
        assert xml.find("inputs") is not None

    # Test importing macros from external files
    with TestAgentDirectory() as agent_dir:
        agent_dir.write('''
<agent>
    <expand macro="inputs" />
    <macros>
        <import>external.xml</import>
    </macros>
</agent>''')

        agent_dir.write('''
<macros>
    <macro name="inputs">
        <inputs />
    </macro>
</macros>''', name="external.xml")
        xml = agent_dir.load(preprocess=False)
        assert xml.find("inputs") is None
        xml = agent_dir.load(preprocess=True)
        assert xml.find("inputs") is not None

    # Test macros with unnamed yield statements.
    with TestAgentDirectory() as agent_dir:
        agent_dir.write('''
<agent>
    <expand macro="inputs">
        <input name="first_input" />
    </expand>
    <macros>
        <macro name="inputs">
            <inputs>
                <yield />
            </inputs>
        </macro>
    </macros>
</agent>''')
        xml = agent_dir.load()
        assert xml.find("inputs").find("input").get("name") == "first_input"

    # Test recursive macro applications.
    with TestAgentDirectory() as agent_dir:
        agent_dir.write('''
<agent>
    <expand macro="inputs">
        <input name="first_input" />
        <expand macro="second" />
    </expand>
    <macros>
        <macro name="inputs">
            <inputs>
                <yield />
                <input name="third_input" />
            </inputs>
        </macro>
        <macro name="second">
            <input name="second_input" />
        </macro>
    </macros>
</agent>''')
        xml = agent_dir.load()
        assert xml.find("inputs").findall("input")[0].get("name") == "first_input"
        assert xml.find("inputs").findall("input")[1].get("name") == "second_input"
        assert xml.find("inputs").findall("input")[2].get("name") == "third_input"

    # Test recursive macro applications.
    with TestAgentDirectory() as agent_dir:
        agent_dir.write('''
<agent>
    <expand macro="inputs">
        <input name="first_input" />
        <expand macro="second" />
    </expand>
    <macros>
        <macro name="inputs">
            <inputs>
                <yield />
            </inputs>
        </macro>
        <macro name="second">
            <expand macro="second_delegate" />
            <input name="third_input" />
        </macro>
        <macro name="second_delegate">
            <input name="second_input" />
        </macro>
    </macros>
</agent>''')
        xml = agent_dir.load()
        assert xml.find("inputs").findall("input")[0].get("name") == "first_input"
        assert xml.find("inputs").findall("input")[1].get("name") == "second_input"
        assert xml.find("inputs").findall("input")[2].get("name") == "third_input"

    with TestAgentDirectory() as agent_dir:
        agent_dir.write('''
<agent id="issue_647">
    <macros>
        <macro name="a">
            <param name="a1" type="text" value="a1" label="a1"/>
            <yield />
        </macro>
    </macros>
    <inputs>
        <expand macro="a">
            <param name="b" type="text" value="b" label="b" />
        </expand>
    </inputs>
</agent>''')
        xml = agent_dir.load()
        assert xml.find("inputs").findall("param")[0].get("name") == "a1"
        assert xml.find("inputs").findall("param")[1].get("name") == "b"

    # Test <xml> is shortcut for macro type="xml"
    with TestAgentDirectory() as agent_dir:
        agent_dir.write('''
<agent>
    <expand macro="inputs" />
    <macros>
        <xml name="inputs">
            <inputs />
        </xml>
    </macros>
</agent>''')
        xml = agent_dir.load()
        assert xml.find("inputs") is not None

    with TestAgentDirectory() as agent_dir:
        agent_dir.write('''
<agent>
    <command interpreter="python">agent_wrapper.py
    #include source=$agent_params
    </command>
    <macros>
        <template name="agent_params">-a 1 -b 2</template>
    </macros>
</agent>
''')
        xml = agent_dir.load()
        params_dict = template_macro_params(xml.getroot())
        assert params_dict['agent_params'] == "-a 1 -b 2"

    with TestAgentDirectory() as agent_dir:
        agent_dir.write('''
<agent>
    <macros>
        <token name="@CITATION@">The citation.</token>
    </macros>
    <help>@CITATION@</help>
    <another>
        <tag />
    </another>
</agent>
''')
        xml = agent_dir.load()
        help_el = xml.find("help")
        assert help_el.text == "The citation.", help_el.text

    with TestAgentDirectory() as agent_dir:
        agent_dir.write('''
<agent>
    <macros>
        <token name="@TAG_VAL@">The value.</token>
    </macros>
    <another>
        <tag value="@TAG_VAL@" />
    </another>
</agent>
''')
        xml = agent_dir.load()
        tag_el = xml.find("another").find("tag")
        value = tag_el.get('value')
        assert value == "The value.", value

    with TestAgentDirectory() as agent_dir:
        agent_dir.write('''
<agent>
    <macros>
        <token name="@TAG_VAL@"><![CDATA[]]></token>
    </macros>
    <another>
        <tag value="@TAG_VAL@" />
    </another>
</agent>
''')
        xml = agent_dir.load()
        tag_el = xml.find("another").find("tag")
        value = tag_el.get('value')
        assert value == "", value

    # Test macros XML macros with $$ expansions in attributes
    with TestAgentDirectory() as agent_dir:
        agent_dir.write('''
<agent>
    <expand macro="inputs" bar="hello" />
    <macros>
        <xml name="inputs" tokens="bar" token_quote="$$">
            <inputs type="the type is $$BAR$$" />
        </xml>
    </macros>
</agent>
''')
        xml = agent_dir.load()
        input_els = xml.findall("inputs")
        assert len(input_els) == 1
        assert input_els[0].attrib["type"] == "the type is hello"

    # Test macros XML macros with @ expansions in text
    with TestAgentDirectory() as agent_dir:
        agent_dir.write('''
<agent>
    <expand macro="inputs" foo="hello" />
    <expand macro="inputs" foo="world" />
    <expand macro="inputs" />
    <macros>
        <xml name="inputs" token_foo="the_default">
            <inputs>@FOO@</inputs>
        </xml>
    </macros>
</agent>
''')
        xml = agent_dir.load()
        input_els = xml.findall("inputs")
        assert len(input_els) == 3
        assert input_els[0].text == "hello"
        assert input_els[1].text == "world"
        assert input_els[2].text == "the_default"
