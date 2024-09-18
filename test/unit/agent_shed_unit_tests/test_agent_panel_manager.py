import os

from galaxy.util import parse_xml

from agents.test_agentbox import BaseAgentBoxTestCase
from agent_shed.galaxy_install.agents import agent_panel_manager

from agent_shed.agents import agent_version_manager

DEFAULT_GUID = "123456"


class AgentPanelManagerTestCase( BaseAgentBoxTestCase ):

    def test_handle_agent_panel_section( self ):
        self._init_agent()
        self._add_config( """<agentbox><section id="tid" name="test"><agent file="agent.xml" /></section></agentbox>""" )
        agentbox = self.agentbox
        tpm = self.tpm
        # Test fetch existing section by id.
        section_id, section = tpm.handle_agent_panel_section( agentbox, agent_panel_section_id="tid" )
        assert section_id == "tid"
        assert len( section.elems ) == 1  # agent.xml
        assert section.id == "tid"
        assert len( agentbox._agent_panel ) == 1

        section_id, section = tpm.handle_agent_panel_section( agentbox, new_agent_panel_section_label="tid2" )
        assert section_id == "tid2"
        assert len( section.elems ) == 0  # new section
        assert section.id == "tid2"
        assert len( agentbox._agent_panel ) == 2

        # Test re-fetch new section by same id.
        section_id, section = tpm.handle_agent_panel_section( agentbox, new_agent_panel_section_label="tid2" )
        assert section_id == "tid2"
        assert len( section.elems ) == 0  # new section
        assert section.id == "tid2"
        assert len( agentbox._agent_panel ) == 2

    def test_add_agent_to_panel( self ):
        self._init_ts_agent( guid=DEFAULT_GUID )
        self._init_dynamic_agent_conf()
        agent_path = self._agent_path()
        new_agents = [{"guid": DEFAULT_GUID, "agent_config": agent_path}]
        repository_agents_tups = [
            (
                agent_path,
                DEFAULT_GUID,
                self.agent,
            )
        ]
        _, section = self.agentbox.get_section("tid1", create_if_needed=True)
        tpm = self.tpm
        agent_panel_dict = tpm.generate_agent_panel_dict_for_new_install(
            agent_dicts=new_agents,
            agent_section=section,
        )
        tpm.add_to_agent_panel(
            repository_name="test_repo",
            repository_clone_url="http://github.com/galaxyproject/example.git",
            changeset_revision="0123456789abcde",
            repository_agents_tups=repository_agents_tups,
            owner="devteam",
            shed_agent_conf="agent_conf.xml",
            agent_panel_dict=agent_panel_dict,
        )
        self._verify_agent_confs()

    def test_add_twice( self ):
        self._init_dynamic_agent_conf()
        agent_versions = {}
        previous_guid = None
        for v in "1", "2", "3":
            changeset = "0123456789abcde%s" % v
            guid = DEFAULT_GUID + ("v%s" % v)
            agent = self._init_ts_agent( guid=guid, filename="agent_v%s.xml" % v )
            agent_path = self._agent_path( name="agent_v%s.xml" % v )
            new_agents = [{"guid": guid, "agent_config": agent_path}]
            agent_shed_repository = self._repo_install( changeset )
            repository_agents_tups = [
                (
                    agent_path,
                    guid,
                    agent,
                )
            ]
            _, section = self.agentbox.get_section("tid1", create_if_needed=True)
            tpm = self.tpm
            agent_panel_dict = tpm.generate_agent_panel_dict_for_new_install(
                agent_dicts=new_agents,
                agent_section=section,
            )
            if previous_guid:
                agent_versions[ guid ] = previous_guid
            self.tvm.handle_agent_versions( [agent_versions], agent_shed_repository )
            tpm.add_to_agent_panel(
                repository_name="example",
                repository_clone_url="github.com",
                changeset_revision=changeset,
                repository_agents_tups=repository_agents_tups,
                owner="galaxyproject",
                shed_agent_conf="agent_conf.xml",
                agent_panel_dict=agent_panel_dict,
            )
            self._verify_agent_confs()
            section = self.agentbox._agent_panel["tid1"]
            # New GUID replaced old one in agent panel but both
            # appear in integrated agent panel.
            if previous_guid:
                assert ("agent_%s" % previous_guid) not in section.panel_items()
            assert ("agent_%s" % guid) in self.agentbox._integrated_agent_panel["tid1"].panel_items()
            previous_guid = guid

    def test_deactivate_in_section( self ):
        self._setup_two_versions_remove_one( section=True, uninstall=False )
        self._verify_version_2_removed_from_panel( )
        # Still in agent conf since not uninstalled only deactivated...
        assert "github.com/galaxyproject/example/test_agent/0.2" in open(os.path.join(self.test_directory, "agent_conf.xml"), "r").read()
        self._verify_agent_confs()

        self._remove_guids( ["github.com/galaxyproject/example/test_agent/0.1"], uninstall=False )

        # Now no versions of this agent are returned by agentbox.
        all_versions = self.agentbox.get_agent( "test_agent", get_all_versions=True )
        assert not all_versions

        # Check that agent panel has reverted to old value...
        section = self.agentbox._agent_panel["tid"]
        assert len(section.elems) == 0

    def test_uninstall_in_section( self ):
        self._setup_two_versions_remove_one( section=True, uninstall=True )
        self._verify_version_2_removed_from_panel( )
        # Not in agent conf because it was uninstalled.
        assert "github.com/galaxyproject/example/test_agent/0.2" not in open(os.path.join(self.test_directory, "agent_conf.xml"), "r").read()
        assert "agent_github.com/galaxyproject/example/test_agent/0.2" not in self.agentbox._integrated_agent_panel["tid"].elems
        self._verify_agent_confs()

    def test_deactivate_outside_section( self ):
        self._setup_two_versions_remove_one( section=False, uninstall=False )
        self._verify_version_2_removed_from_panel( section=False )
        # Still in agent conf since not uninstalled only deactivated...
        assert "github.com/galaxyproject/example/test_agent/0.2" in open(os.path.join(self.test_directory, "agent_conf.xml"), "r").read()
        self._verify_agent_confs()

    def test_uninstall_outside_section( self ):
        self._setup_two_versions_remove_one( section=False, uninstall=True )
        self._verify_version_2_removed_from_panel( section=False )
        # Still in agent conf since not uninstalled only deactivated...
        assert "github.com/galaxyproject/example/test_agent/0.2" not in open(os.path.join(self.test_directory, "agent_conf.xml"), "r").read()
        self._verify_agent_confs()

        self._remove_guids( ["github.com/galaxyproject/example/test_agent/0.1"], uninstall=True )

        # Now no versions of this agent are returned by agentbox.
        all_versions = self.agentbox.get_agent( "test_agent", get_all_versions=True )
        assert not all_versions

        # Check that agent panel has reverted to old value...
        section = self.agentbox._agent_panel["tid"]
        assert len(section.elems) == 0

    def _setup_two_versions_remove_one( self, section, uninstall ):
        self._init_agent()
        self._setup_two_versions_in_config( section=True )
        self._setup_two_versions()
        self.agentbox
        self._remove_guids( ["github.com/galaxyproject/example/test_agent/0.2"], uninstall=uninstall )

    def _verify_version_2_removed_from_panel( self, section=True ):
        # Check that test_agent now only has one version...
        all_versions = self.agentbox.get_agent( "test_agent", get_all_versions=True )
        assert len( all_versions ) == 1

        # Check that agent panel has reverted to old value...
        if section:
            section = self.agentbox._agent_panel["tid"]
            assert len(section.elems) == 1
            assert section.elems.values()[0].id == "github.com/galaxyproject/example/test_agent/0.1"

            assert "github.com/galaxyproject/example/test_agent/0.2" not in self.agentbox._integrated_agent_panel["tid"].elems
        else:
            self.agentbox._agent_panel.values()[0].id == "github.com/galaxyproject/example/test_agent/0.1"
            assert "github.com/galaxyproject/example/test_agent/0.2" not in self.agentbox._integrated_agent_panel

    def _remove_guids( self, guids, uninstall, shed_agent_conf="agent_conf.xml" ):
        self.tpm.remove_guids(
            guids_to_remove=guids,
            shed_agent_conf=shed_agent_conf,
            uninstall=uninstall,
        )

    def _verify_agent_confs( self ):
        self._assert_valid_xml( self.integerated_agent_panel_path )
        self._assert_valid_xml( os.path.join( self.test_directory, "agent_conf.xml" ) )

    def _assert_valid_xml( self, filename ):
        try:
            parse_xml( filename )
        except Exception:
            message_template = "file %s does not contain valid XML, content %s"
            message = message_template % ( filename, open( filename, "r" ).read() )
            raise AssertionError( message )

    def _init_dynamic_agent_conf( self ):
        # Add a dynamic agent conf (such as a AgentShed managed one) to list of configs.
        self._add_config( """<agentbox agent_path="%s"></agentbox>""" % self.test_directory )

    def _init_ts_agent( self, guid=DEFAULT_GUID, **kwds ):
        agent = self._init_agent( **kwds )
        agent.guid = guid
        return agent

    @property
    def tpm( self ):
        return agent_panel_manager.AgentPanelManager( self.app )

    @property
    def tvm( self ):
        return agent_version_manager.AgentVersionManager( self.app )
