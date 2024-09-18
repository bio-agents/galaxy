import json
import os
import string
import unittest

from galaxy.agents import AgentBox
from galaxy import model
from galaxy.model import agent_shed_install
from galaxy.model.agent_shed_install import mapping
import agents_support

import routes

from .test_agentbox_filters import mock_trans


CONFIG_TEST_TOOL_VERSION_TEMPLATE = string.Template(
    """    <agent file="agent.xml" guid="github.com/galaxyproject/example/test_agent/0.${version}">
            <agent_shed>github.com</agent_shed>
            <repository_name>example</repository_name>
            <repository_owner>galaxyproject</repository_owner>
            <installed_changeset_revision>${version}</installed_changeset_revision>
            <id>github.com/galaxyproject/example/test_agent/0.${version}</id>
            <version>0.${version}</version>
        </agent>
    """
)
CONFIG_TEST_TOOL_VERSION_1 = CONFIG_TEST_TOOL_VERSION_TEMPLATE.safe_substitute( dict( version="1" ) )
CONFIG_TEST_TOOL_VERSION_2 = CONFIG_TEST_TOOL_VERSION_TEMPLATE.safe_substitute( dict( version="2" ) )


class BaseAgentBoxTestCase(  unittest.TestCase, agents_support.UsesApp, agents_support.UsesAgents  ):

    @property
    def integerated_agent_panel_path( self ):
        return os.path.join(self.test_directory, "integrated_agent_panel.xml")

    def assert_integerated_agent_panel( self, exists=True ):
        does_exist = os.path.exists( self.integerated_agent_panel_path )
        if exists:
            assert does_exist
        else:
            assert not does_exist

    @property
    def agentbox( self ):
        if self.__agentbox is None:
            self.__agentbox = SimplifiedAgentBox( self )
            # wire app with this new agentbox
            self.app.agentbox = self.__agentbox
        return self.__agentbox

    def setUp( self ):
        self.reindexed = False
        self.setup_app( mock_model=False )
        install_model = mapping.init( "sqlite:///:memory:", create_tables=True )
        self.app.install_model = install_model
        self.app.reindex_agent_search = self.__reindex
        itp_config = os.path.join(self.test_directory, "integrated_agent_panel.xml")
        self.app.config.integrated_agent_panel_config = itp_config
        self.__agentbox = None
        self.config_files = []

    def _repo_install( self, changeset ):
        repository = agent_shed_install.AgentShedRepository()
        repository.agent_shed = "github.com"
        repository.owner = "galaxyproject"
        repository.name = "example"
        repository.changeset_revision = changeset
        repository.installed_changeset_revision = changeset
        repository.deleted = False
        repository.uninstalled = False
        self.app.install_model.context.add( repository )
        self.app.install_model.context.flush( )
        return repository

    def _setup_two_versions( self ):
        repository1 = self._repo_install( changeset="1" )
        version1 = agent_shed_install.AgentVersion()
        version1.agent_id = "github.com/galaxyproject/example/test_agent/0.1"
        version1.repository = repository1
        self.app.install_model.context.add( version1 )
        self.app.install_model.context.flush( )

        repository2 = self._repo_install( changeset="2" )
        version2 = agent_shed_install.AgentVersion()
        version2.agent_id = "github.com/galaxyproject/example/test_agent/0.2"
        version2.repository = repository2

        self.app.install_model.context.add( version2 )
        self.app.install_model.context.flush( )

        version_association = agent_shed_install.AgentVersionAssociation()
        version_association.parent_id = version1.id
        version_association.agent_id = version2.id

        self.app.install_model.context.add( version_association )
        self.app.install_model.context.flush( )

    def _setup_two_versions_in_config( self, section=False ):
        if section:
            template = """<agentbox agent_path="%s">
<section id="tid" name="TID" version="">
    %s
</section>
<section id="tid" name="TID" version="">
    %s
</section>
</agentbox>"""
        else:
            template = """<agentbox agent_path="%s">
<section id="tid" name="TID" version="">
    %s
</section>
<section id="tid" name="TID" version="">
    %s
</section>
</agentbox>"""
        self._add_config( template % (self.test_directory, CONFIG_TEST_TOOL_VERSION_1, CONFIG_TEST_TOOL_VERSION_2 ) )

    def _add_config( self, content, name="agent_conf.xml" ):
        is_json = name.endswith(".json")
        path = self._agent_conf_path( name=name )
        with open( path, "w" ) as f:
            if not is_json or isinstance(content, basestring):
                f.write( content )
            else:
                json.dump(content, f)
        self.config_files.append( path )

    def _agent_conf_path( self, name="agent_conf.xml" ):
        path = os.path.join( self.test_directory, name )
        return path

    def _agent_path( self, name="agent.xml" ):
        path = os.path.join( self.test_directory, name )
        return path

    def __reindex( self ):
        self.reindexed = True


class AgentBoxTestCase( BaseAgentBoxTestCase ):

    def test_load_file( self ):
        self._init_agent()
        self._add_config( """<agentbox><agent file="agent.xml" /></agentbox>""" )

        agentbox = self.agentbox
        assert agentbox.get_agent( "test_agent" ) is not None
        assert agentbox.get_agent( "not_a_test_agent" ) is None

    def test_to_dict_in_panel( self ):
        for json_conf in [True, False]:
            self._init_agent_in_section(json=json_conf)
            mapper = routes.Mapper()
            mapper.connect( "agent_runner", "/test/agent_runner" )
            as_dict = self.agentbox.to_dict( mock_trans() )
            test_section = self._find_section(as_dict, "t")
            assert len(test_section["elems"]) == 1
            assert test_section["elems"][0]["id"] == "test_agent"

    def test_to_dict_out_of_panel( self ):
        for json_conf in [True, False]:
            self._init_agent_in_section(json=json_conf)
            mapper = routes.Mapper()
            mapper.connect( "agent_runner", "/test/agent_runner" )
            as_dict = self.agentbox.to_dict( mock_trans(), in_panel=False )
            assert as_dict[0]["id"] == "test_agent"

    def test_out_of_panel_filtering( self ):
        self._init_agent_in_section()

        mapper = routes.Mapper()
        mapper.connect( "agent_runner", "/test/agent_runner" )
        as_dict = self.agentbox.to_dict( mock_trans(), in_panel=False )
        assert len(as_dict) == 1

        def allow_user_access(user, attempting_access):
            assert not attempting_access
            return False

        # Disable access to the agent, make sure it is filtered out.
        self.agentbox.get_agent("test_agent").allow_user_access = allow_user_access
        as_dict = self.agentbox.to_dict( mock_trans(), in_panel=False )
        assert len(as_dict) == 0

    def _find_section( self, as_dict, section_id ):
        for elem in as_dict:
            if elem.get("id") == section_id:
                assert elem["model_class"] == "AgentSection"
                return elem
        assert False, "Failed to find section with id [%s]" % section_id

    def test_agent_shed_properties( self ):
        self._init_agent()
        self._setup_two_versions_in_config( section=False )
        self._setup_two_versions()

        test_agent = self.agentbox.get_agent( "test_agent" )
        assert test_agent.agent_shed == "github.com"
        assert test_agent.repository_owner == "galaxyproject"
        assert test_agent.repository_name == "example"
        # TODO: Not deterministc, probably should be?
        assert test_agent.installed_changeset_revision in ["1", "2"]

    def test_agent_shed_properties_only_on_installed_agents( self ):
        self._init_agent()
        self._add_config( """<agentbox><agent file="agent.xml" /></agentbox>""" )
        agentbox = self.agentbox
        test_agent = agentbox.get_agent( "test_agent" )
        assert test_agent.agent_shed is None
        assert test_agent.repository_name is None
        assert test_agent.repository_owner is None
        assert test_agent.installed_changeset_revision is None

    def test_load_file_in_section( self ):
        self._init_agent_in_section()

        agentbox = self.agentbox
        assert agentbox.get_agent( "test_agent" ) is not None
        assert agentbox.get_agent( "not_a_test_agent" ) is None

    def test_writes_integrate_agent_panel( self ):
        self._init_agent()
        self._add_config( """<agentbox><agent file="agent.xml" /></agentbox>""" )

        self.assert_integerated_agent_panel(exists=False)
        self.agentbox
        self.assert_integerated_agent_panel(exists=True)

    def test_groups_agents_in_section( self ):
        self._init_agent()
        self._setup_two_versions_in_config( section=True )
        self._setup_two_versions()
        self.agentbox
        self.__verify_two_test_agents( )

        # Assert only newer version of the agent loaded into the panel.
        section = self.agentbox._agent_panel["tid"]
        assert len(section.elems) == 1
        assert section.elems.values()[0].id == "github.com/galaxyproject/example/test_agent/0.2"

    def test_group_agents_out_of_section( self ):
        self._init_agent()
        self._setup_two_versions_in_config( section=False )
        self._setup_two_versions()
        self.__verify_two_test_agents( )

        # Assert agents merged in agent panel.
        assert len( self.agentbox._agent_panel ) == 1

    def test_update_shed_conf(self):
        self.__setup_shed_agent_conf()
        self.agentbox.update_shed_config( { "config_filename": "agent_conf.xml" } )
        assert self.reindexed
        self.assert_integerated_agent_panel(exists=True)

    def test_update_shed_conf_deactivate_only(self):
        self.__setup_shed_agent_conf()
        self.agentbox.update_shed_config(  { "config_filename": "agent_conf.xml" }, integrated_panel_changes=False )
        assert self.reindexed
        # No changes, should be regenerated
        self.assert_integerated_agent_panel(exists=False)

    def test_get_agent_id( self ):
        self._init_agent()
        self._setup_two_versions_in_config( )
        self._setup_two_versions()
        assert self.agentbox.get_agent_id( "test_agent" ) in [
            "github.com/galaxyproject/example/test_agent/0.1",
            "github.com/galaxyproject/example/test_agent/0.2"
        ]
        assert self.agentbox.get_agent_id( "github.com/galaxyproject/example/test_agent/0.1" ) == "github.com/galaxyproject/example/test_agent/0.1"
        assert self.agentbox.get_agent_id( "github.com/galaxyproject/example/test_agent/0.2" ) == "github.com/galaxyproject/example/test_agent/0.2"
        assert self.agentbox.get_agent_id( "github.com/galaxyproject/example/test_agent/0.3" ) is None

    def test_agent_dir( self ):
        self._init_agent()
        self._add_config( """<agentbox><agent_dir dir="%s" /></agentbox>""" % self.test_directory )

        agentbox = self.agentbox
        assert agentbox.get_agent( "test_agent" ) is not None

    def test_agent_dir_json( self ):
        self._init_agent()
        self._add_config({"items": [{"type": "agent_dir", "dir": self.test_directory}]}, name="agent_conf.json")

        agentbox = self.agentbox
        assert agentbox.get_agent( "test_agent" ) is not None

    def test_workflow_in_panel( self ):
        stored_workflow = self.__test_workflow()
        encoded_id = self.app.security.encode_id( stored_workflow.id )
        self._add_config( """<agentbox><workflow id="%s" /></agentbox>""" % encoded_id )
        assert len( self.agentbox._agent_panel ) == 1
        panel_workflow = self.agentbox._agent_panel.values()[ 0 ]
        assert panel_workflow == stored_workflow.latest_workflow
        # TODO: test to_dict with workflows

    def test_workflow_in_section( self ):
        stored_workflow = self.__test_workflow()
        encoded_id = self.app.security.encode_id( stored_workflow.id )
        self._add_config( """<agentbox><section id="tid" name="TID"><workflow id="%s" /></section></agentbox>""" % encoded_id )
        assert len( self.agentbox._agent_panel ) == 1
        section = self.agentbox._agent_panel[ 'tid' ]
        assert len( section.elems ) == 1
        panel_workflow = section.elems.values()[ 0 ]
        assert panel_workflow == stored_workflow.latest_workflow

    def test_label_in_panel( self ):
        self._add_config( """<agentbox><label id="lab1" text="Label 1" /><label id="lab2" text="Label 2" /></agentbox>""" )
        assert len( self.agentbox._agent_panel ) == 2
        self.__check_test_labels( self.agentbox._agent_panel )

    def test_label_in_section( self ):
        self._add_config( """<agentbox><section id="tid" name="TID"><label id="lab1" text="Label 1" /><label id="lab2" text="Label 2" /></section></agentbox>""" )
        assert len( self.agentbox._agent_panel ) == 1
        section = self.agentbox._agent_panel[ 'tid' ]
        self.__check_test_labels( section.elems )

    def _init_agent_in_section( self, json=False ):
        self._init_agent()
        if not json:
            self._add_config( """<agentbox><section id="t" name="test"><agent file="agent.xml" /></section></agentbox>""" )
        else:
            section = {
                "type": "section",
                "id": "t",
                "name": "test",
                "items": [{"type": "agent",
                           "file": "agent.xml"}],
            }
            self._add_config({"items": [section]}, name="agent_conf.json")

    def __check_test_labels( self, panel_dict ):
        assert panel_dict.keys() == ["label_lab1", "label_lab2"]
        label1 = panel_dict.values()[ 0 ]
        assert label1.id == "lab1"
        assert label1.text == "Label 1"

        label2 = panel_dict[ "label_lab2" ]
        assert label2.id == "lab2"
        assert label2.text == "Label 2"

    def __test_workflow( self ):
        stored_workflow = model.StoredWorkflow()
        workflow = model.Workflow()
        workflow.stored_workflow = stored_workflow
        stored_workflow.latest_workflow = workflow
        user = model.User()
        user.email = "test@example.com"
        user.password = "passw0rD1"
        stored_workflow.user = user
        self.app.model.context.add( workflow )
        self.app.model.context.add( stored_workflow )
        self.app.model.context.flush()
        return stored_workflow

    def __verify_two_test_agents( self ):
        # Assert agent versions of the agent with simple id 'test_agent'
        all_versions = self.agentbox.get_agent( "test_agent", get_all_versions=True )
        assert len( all_versions ) == 2

        # Verify lineage_ids on both agents is correctly ordered.
        for version in ["0.1", "0.2"]:
            guid = "github.com/galaxyproject/example/test_agent/" + version
            lineage_ids = self.agentbox.get_agent( guid ).lineage.get_version_ids()
            assert lineage_ids[ 0 ] == "github.com/galaxyproject/example/test_agent/0.1"
            assert lineage_ids[ 1 ] == "github.com/galaxyproject/example/test_agent/0.2"

        # Test agent_version attribute.
        assert self.agentbox.get_agent( "test_agent", agent_version="0.1" ).guid == "github.com/galaxyproject/example/test_agent/0.1"
        assert self.agentbox.get_agent( "test_agent", agent_version="0.2" ).guid == "github.com/galaxyproject/example/test_agent/0.2"

    def test_default_lineage( self ):
        self.__init_versioned_agents()
        self._add_config( """<agentbox><agent file="agent_v01.xml" /><agent file="agent_v02.xml" /></agentbox>""" )
        self.__verify_get_agent_for_default_lineage()

    def test_default_lineage_reversed( self ):
        # Run same test as above but with entries in agent_conf reversed to
        # ensure versioning is at work and not order effects.
        self.__init_versioned_agents()
        self._add_config( """<agentbox><agent file="agent_v02.xml" /><agent file="agent_v01.xml" /></agentbox>""" )
        self.__verify_get_agent_for_default_lineage()

    def test_grouping_with_default_lineage( self ):
        self.__init_versioned_agents()
        self._add_config( """<agentbox><agent file="agent_v01.xml" /><agent file="agent_v02.xml" /></agentbox>""" )
        self.__verify_agent_panel_for_default_lineage()

    def test_grouping_with_default_lineage_reversed( self ):
        # Run same test as above but with entries in agent_conf reversed to
        # ensure versioning is at work and not order effects.
        self.__init_versioned_agents()
        self._add_config( """<agentbox><agent file="agent_v02.xml" /><agent file="agent_v02.xml" /></agentbox>""" )
        self.__verify_agent_panel_for_default_lineage()

    def __init_versioned_agents( self ):
        self._init_agent( filename="agent_v01.xml", version="0.1" )
        self._init_agent( filename="agent_v02.xml", version="0.2" )

    def __verify_agent_panel_for_default_lineage( self ):
        assert len( self.agentbox._agent_panel ) == 1
        agent = self.agentbox._agent_panel["agent_test_agent"]
        assert agent.version == "0.2", agent.version
        assert agent.id == "test_agent"

    def __verify_get_agent_for_default_lineage( self ):
        agent_v01 = self.agentbox.get_agent( "test_agent", agent_version="0.1" )
        agent_v02 = self.agentbox.get_agent( "test_agent", agent_version="0.2" )
        assert agent_v02.id == "test_agent"
        assert agent_v02.version == "0.2", agent_v02.version
        assert agent_v01.id == "test_agent"
        assert agent_v01.version == "0.1"

        # Newer variant gets to be default for that id.
        default_agent = self.agentbox.get_agent( "test_agent" )
        assert default_agent.id == "test_agent"
        assert default_agent.version == "0.2"

    def __remove_itp( self ):
        os.remove( os.path)

    def __setup_shed_agent_conf( self ):
        self._add_config( """<agentbox agent_path="."></agentbox>""" )

        self.agentbox  # create agentbox
        assert not self.reindexed

        os.remove( self.integerated_agent_panel_path )


class SimplifiedAgentBox( AgentBox ):

    def __init__( self, test_case ):
        app = test_case.app
        # Handle app/config stuff needed by agentbox but not by agents.
        app.job_config.get_agent_resource_parameters = lambda agent_id: None
        app.config.update_integrated_agent_panel = True
        config_files = test_case.config_files
        agent_root_dir = test_case.test_directory
        super( SimplifiedAgentBox, self ).__init__(
            config_files,
            agent_root_dir,
            app,
        )
