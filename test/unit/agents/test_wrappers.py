import tempfile
import os

from galaxy.agents.parameters.basic import SelectAgentParameter
from galaxy.agents.parameters.basic import DrillDownSelectAgentParameter
from galaxy.agents.parameters.basic import IntegerAgentParameter
from galaxy.agents.wrappers import RawObjectWrapper
from galaxy.agents.wrappers import SelectAgentParameterWrapper
from galaxy.agents.wrappers import InputValueWrapper
from galaxy.agents.wrappers import DatasetFilenameWrapper
from galaxy.jobs.datasets import DatasetPath
from galaxy.util.bunch import Bunch
from xml.etree.ElementTree import XML
from galaxy.datatypes.metadata import MetadataSpecCollection


def with_mock_agent(func):
    def call():
        test_directory = tempfile.mkdtemp()
        app = MockApp(test_directory)
        agent = MockAgent(app)
        return func(agent)
    call.__name__ = func.__name__
    return call


@with_mock_agent
def test_select_wrapper_simple_options(agent):
    xml = XML('''<param name="blah" type="select">
        <option value="x">I am X</option>
        <option value="y" selected="true">I am Y</option>
        <option value="z">I am Z</option>
    </param>''')
    parameter = SelectAgentParameter( agent, xml )
    wrapper = SelectAgentParameterWrapper( parameter, "x", agent.app )
    assert str(wrapper) == "x"
    assert wrapper.name == "blah"
    assert wrapper.value_label == "I am X"


@with_mock_agent
def test_select_wrapper_with_drilldown(agent):
    parameter = _drilldown_parameter(agent)
    wrapper = SelectAgentParameterWrapper( parameter, ["option3"], agent.app )
    assert str(wrapper) == "option3", str(wrapper)


@with_mock_agent
def test_select_wrapper_option_file(agent):
    parameter = _setup_blast_agent(agent)
    wrapper = SelectAgentParameterWrapper( parameter, "val2", agent.app )
    assert str(wrapper) == "val2"
    assert wrapper.fields.name == "name2"
    assert wrapper.fields.path == "path2"


@with_mock_agent
def test_select_wrapper_multiple(agent):
    parameter = _setup_blast_agent(agent, multiple=True)
    wrapper = SelectAgentParameterWrapper( parameter, ["val1", "val2"], agent.app )
    assert str(wrapper) == "val1,val2"
    assert wrapper.fields.name == "name1,name2"


@with_mock_agent
def test_select_wrapper_with_path_rewritting(agent):
    parameter = _setup_blast_agent(agent, multiple=True)
    wrapper = SelectAgentParameterWrapper( parameter, ["val1", "val2"], agent.app, other_values={}, path_rewriter=lambda v: "Rewrite<%s>" % v )
    assert wrapper.fields.path == "Rewrite<path1>,Rewrite<path2>"


def test_raw_object_wrapper():
    obj = Bunch(x=4)
    wrapper = RawObjectWrapper(obj)
    assert wrapper.x == 4
    assert wrapper

    false_wrapper = RawObjectWrapper(False)
    assert not false_wrapper


@with_mock_agent
def test_input_value_wrapper(agent):
    parameter = IntegerAgentParameter( agent, XML( '<param name="blah" type="integer" size="4" value="10" min="0" />' ) )
    wrapper = InputValueWrapper( parameter, "5" )
    assert str( wrapper ) == "5"


def test_dataset_wrapper():
    dataset = MockDataset()
    wrapper = DatasetFilenameWrapper(dataset)
    assert str( wrapper ) == MOCK_DATASET_PATH
    assert wrapper.file_name == MOCK_DATASET_PATH

    assert wrapper.ext == MOCK_DATASET_EXT


def test_dataset_wrapper_false_path():
    dataset = MockDataset()
    new_path = "/new/path/dataset_123.dat"
    wrapper = DatasetFilenameWrapper(dataset, dataset_path=Bunch(false_path=new_path))
    assert str( wrapper ) == new_path
    assert wrapper.file_name == new_path


def test_dataset_false_extra_files_path():
    dataset = MockDataset()

    wrapper = DatasetFilenameWrapper(dataset)
    assert wrapper.extra_files_path == MOCK_DATASET_EXTRA_FILES_PATH

    new_path = "/new/path/dataset_123.dat"
    dataset_path = DatasetPath(123, MOCK_DATASET_PATH, false_path=new_path)
    wrapper = DatasetFilenameWrapper(dataset, dataset_path=dataset_path)
    # Setting false_path is not enough to override
    assert wrapper.extra_files_path == MOCK_DATASET_EXTRA_FILES_PATH

    new_files_path = "/new/path/dataset_123_files"
    dataset_path = DatasetPath(123, MOCK_DATASET_PATH, false_path=new_path, false_extra_files_path=new_files_path)
    wrapper = DatasetFilenameWrapper(dataset, dataset_path=dataset_path)
    assert wrapper.extra_files_path == new_files_path


def _drilldown_parameter(agent):
    xml = XML( '''<param name="some_name" type="drill_down" display="checkbox" hierarchy="recurse" multiple="true">
        <options>
            <option name="Heading 1" value="heading1">
                <option name="Option 1" value="option1"/>
                <option name="Option 2" value="option2"/>
                <option name="Heading 1" value="heading1">
                    <option name="Option 3" value="option3"/>
                    <option name="Option 4" value="option4"/>
               </option>
            </option>
           <option name="Option 5" value="option5"/>
      </options>
    </param>''' )
    parameter = DrillDownSelectAgentParameter( agent, xml )
    return parameter


def _setup_blast_agent(agent, multiple=False):
    agent.app.write_test_agent_data("blastdb.loc", "val1\tname1\tpath1\nval2\tname2\tpath2\n")
    xml = XML( '''<param name="database" type="select" label="Nucleotide BLAST database" multiple="%s">
        <options from_file="blastdb.loc">
            <column name="value" index="0"/>
            <column name="name" index="1"/>
            <column name="path" index="2"/>
        </options>
    </param>''' % multiple )
    parameter = SelectAgentParameter( agent, xml )
    return parameter


MOCK_DATASET_PATH = "/galaxy/database/files/001/dataset_123.dat"
MOCK_DATASET_EXTRA_FILES_PATH = "/galaxy/database/files/001/dataset_123.dat"
MOCK_DATASET_EXT = "bam"


class MockDataset(object):

    def __init__(self):
        self.metadata = MetadataSpecCollection({})
        self.file_name = MOCK_DATASET_PATH
        self.extra_files_path = MOCK_DATASET_EXTRA_FILES_PATH
        self.ext = MOCK_DATASET_EXT


class MockAgent(object):

    def __init__(self, app):
        self.app = app
        self.options = Bunch(sanitize=False)


class MockApp(object):

    def __init__(self, test_directory):
        self.config = Bunch(agent_data_path=test_directory)

    def write_test_agent_data(self, name, contents):
        path = os.path.join(self.config.agent_data_path, name)
        open(path, "w").write(contents)
