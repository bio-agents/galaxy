import config
import sys
import time
import galaxy.datatypes.registry
import galaxy.quota
import galaxy.agents.data
import galaxy.webapps.agent_shed.model
from galaxy import agents
from galaxy.managers.tags import CommunityTagManager
from galaxy.openid.providers import OpenIDProviders
from galaxy.util.dbkeys import GenomeBuilds
from galaxy.web import security
import agent_shed.repository_registry
import agent_shed.repository_types.registry
from agent_shed.grids.repository_grid_filter_manager import RepositoryGridFilterManager
import logging
log = logging.getLogger( __name__ )


class UniverseApplication( object ):
    """Encapsulates the state of a Universe application"""

    def __init__( self, **kwd ):
        log.debug( "python path is: %s", ", ".join( sys.path ) )
        self.name = "agent_shed"
        # Read the agent_shed.ini configuration file and check for errors.
        self.config = config.Configuration( **kwd )
        self.config.check()
        config.configure_logging( self.config )
        # Initialize the  Galaxy datatypes registry.
        self.datatypes_registry = galaxy.datatypes.registry.Registry()
        self.datatypes_registry.load_datatypes( self.config.root, self.config.datatypes_config )
        # Initialize the Agent Shed repository_types registry.
        self.repository_types_registry = agent_shed.repository_types.registry.Registry()
        # Initialize the RepositoryGridFilterManager.
        self.repository_grid_filter_manager = RepositoryGridFilterManager()
        # Determine the Agent Shed database connection string.
        if self.config.database_connection:
            db_url = self.config.database_connection
        else:
            db_url = "sqlite:///%s?isolation_level=IMMEDIATE" % self.config.database
        # Initialize the Agent Shed database and check for appropriate schema version.
        from galaxy.webapps.agent_shed.model.migrate.check import create_or_verify_database
        create_or_verify_database( db_url, self.config.database_engine_options )
        # Set up the Agent Shed database engine and ORM.
        from galaxy.webapps.agent_shed.model import mapping
        self.model = mapping.init( self.config.file_path,
                                   db_url,
                                   self.config.database_engine_options )
        # Initialize the Agent Shed security helper.
        self.security = security.SecurityHelper( id_secret=self.config.id_secret )
        # initialize the Agent Shed tag handler.
        self.tag_handler = CommunityTagManager( self )
        # Initialize the Agent Shed agent data tables.  Never pass a configuration file here
        # because the Agent Shed should always have an empty dictionary!
        self.agent_data_tables = galaxy.agents.data.AgentDataTableManager( self.config.agent_data_path )
        self.genome_builds = GenomeBuilds( self )
        from galaxy import auth
        self.auth_manager = auth.AuthManager( self )
        # Citation manager needed to load agents.
        from galaxy.managers.citations import CitationsManager
        self.citations_manager = CitationsManager( self )
        # The Agent Shed makes no use of a Galaxy agentbox, but this attribute is still required.
        self.agentbox = agents.AgentBox( [], self.config.agent_path, self )
        # Initialize the Agent Shed security agent.
        self.security_agent = self.model.security_agent
        # The Agent Shed makes no use of a quota, but this attribute is still required.
        self.quota_agent = galaxy.quota.NoQuotaAgent( self.model )
        # TODO: Add OpenID support
        self.openid_providers = OpenIDProviders()
        # Initialize the baseline Agent Shed statistics component.
        self.shed_counter = self.model.shed_counter
        # Let the Agent Shed's HgwebConfigManager know where the hgweb.config file is located.
        self.hgweb_config_manager = self.model.hgweb_config_manager
        self.hgweb_config_manager.hgweb_config_dir = self.config.hgweb_config_dir
        # Initialize the repository registry.
        self.repository_registry = agent_shed.repository_registry.Registry( self )
        #  used for cachebusting -- refactor this into a *SINGLE* UniverseApplication base.
        self.server_starttime = int(time.time())
        log.debug( "Agent shed hgweb.config file is: %s", self.hgweb_config_manager.hgweb_config )

    def shutdown( self ):
        pass
