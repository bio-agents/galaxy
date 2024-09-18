""" Module contains test fixtures meant to aide in the testing of jobs and
agent evaluation. Such extensive "fixtures" are something of an anti-pattern
so use of this should be limitted to tests of very 'extensive' classes.
"""

from collections import defaultdict
import os.path
import tempfile
import shutil
import string

from galaxy.util.bunch import Bunch
from galaxy.web.security import SecurityHelper
import galaxy.model
from galaxy.model import mapping
from galaxy.agents import Agent
from galaxy.util.dbkeys import GenomeBuilds
from galaxy.jobs import NoopQueue
from galaxy.agents.parser import get_agent_source
from galaxy.agents.deps.containers import NullContainerFinder


class UsesApp( object ):

    def setup_app( self, mock_model=True ):
        self.test_directory = tempfile.mkdtemp()
        self.app = MockApp( self.test_directory, mock_model=mock_model )

    def tear_down_app( self ):
        shutil.rmtree( self.test_directory )


# Simple agent with just one text parameter and output.
SIMPLE_TOOL_CONTENTS = '''<agent id="test_agent" name="Test Agent" version="$version">
    <command>echo "$param1" &lt; $out1</command>
    <inputs>
        <param type="text" name="param1" value="" />
    </inputs>
    <outputs>
        <data name="out1" format="data" label="Output ($param1)" />
    </outputs>
</agent>
'''


# A agent with data parameters (kind of like cat1) my favorite test agent :)
SIMPLE_CAT_TOOL_CONTENTS = '''<agent id="test_agent" name="Test Agent" version="$version">
    <command>cat "$param1" #for $r in $repeat# "$r.param2" #end for# &lt; $out1</command>
    <inputs>
        <param type="data" format="tabular" name="param1" value="" />
        <repeat name="repeat1" label="Repeat 1">
            <param type="data" format="tabular" name="param2" value="" />
        </repeat>
    </inputs>
    <outputs>
        <data name="out1" format="data" />
    </outputs>
</agent>
'''


class UsesAgents( object ):

    def _init_agent(
        self,
        agent_contents=SIMPLE_TOOL_CONTENTS,
        filename="agent.xml",
        version="1.0"
    ):
        self._init_app_for_agents()
        self.agent_file = os.path.join( self.test_directory, filename )
        contents_template = string.Template( agent_contents )
        agent_contents = contents_template.safe_substitute( dict( version=version ) )
        self.__write_agent( agent_contents )
        return self.__setup_agent( )

    def _init_app_for_agents( self ):
        self.app.config.drmaa_external_runjob_script = ""
        self.app.config.agent_secret = "testsecret"
        self.app.config.track_jobs_in_database = False
        self.app.job_config["get_job_agent_configurations"] = lambda ids: [Bunch(handler=Bunch())]

    def __setup_agent( self ):
        agent_source = get_agent_source( self.agent_file )
        self.agent = Agent( self.agent_file, agent_source, self.app )
        if getattr( self, "agent_action", None ):
            self.agent.agent_action = self.agent_action
        return self.agent

    def __write_agent( self, contents ):
        open( self.agent_file, "w" ).write( contents )


class MockApp( object ):

    def __init__( self, test_directory, mock_model=True ):
        # The following line is needed in order to create
        # HistoryDatasetAssociations - ideally the model classes would be
        # usable without the ORM infrastructure in place.
        in_memomry_model = mapping.init( "/tmp", "sqlite:///:memory:", create_tables=True )

        self.datatypes_registry = Bunch(
            integrated_datatypes_configs='/galaxy/integrated_datatypes_configs.xml',
            get_datatype_by_extension=lambda ext: Bunch(),
        )

        self.config = Bunch(
            outputs_to_working_directory=False,
            new_file_path=os.path.join(test_directory, "new_files"),
            agent_data_path=os.path.join(test_directory, "agents"),
            root=os.path.join(test_directory, "galaxy"),
            admin_users="mary@example.com",
            len_file_path=os.path.join( 'agent-data', 'shared', 'ucsc', 'chrom' ),
            builds_file_path=os.path.join( 'agent-data', 'shared', 'ucsc', 'builds.txt.sample' ),
            migrated_agents_config=os.path.join(test_directory, "migrated_agents_conf.xml"),
        )

        # Setup some attributes for downstream extension by specific tests.
        self.job_config = Bunch(
            dynamic_params=None,
        )

        # Two ways to handle model layer, one is to stub out some objects that
        # have an interface similar to real model (mock_model) and can keep
        # track of 'persisted' objects in a map. The other is to use a real
        # sqlalchemy layer but target an in memory database. Depending on what
        # is being tested.
        if mock_model:
            # Create self.model to mimic app.model.
            self.model = Bunch( context=MockContext() )
            for module_member_name in dir( galaxy.model ):
                module_member = getattr(galaxy.model, module_member_name)
                if type( module_member ) == type:
                    self.model[ module_member_name ] = module_member
        else:
            self.model = in_memomry_model
        self.genome_builds = GenomeBuilds( self )
        self.agentbox = None
        self.object_store = None
        self.security = SecurityHelper(id_secret="testing")
        from galaxy.security import GalaxyRBACAgent
        self.job_queue = NoopQueue()
        self.security_agent = GalaxyRBACAgent( self.model )
        self.agent_data_tables = {}
        self.dataset_collections_service = None
        self.container_finder = NullContainerFinder()
        self.name = "galaxy"


class MockContext(object):

    def __init__(self, model_objects=None):
        self.expunged_all = False
        self.flushed = False
        self.model_objects = model_objects or defaultdict( lambda: {} )
        self.created_objects = []

    def expunge_all(self):
        self.expunged_all = True

    def query(self, clazz):
        return MockQuery(self.model_objects.get(clazz))

    def flush(self):
        self.flushed = True

    def add(self, object):
        self.created_objects.append(object)


class MockQuery(object):

    def __init__(self, class_objects):
        self.class_objects = class_objects

    def filter_by(self, **kwds):
        return Bunch(first=lambda: None)

    def get(self, id):
        return self.class_objects.get(id, None)


__all__ = [ UsesApp ]
