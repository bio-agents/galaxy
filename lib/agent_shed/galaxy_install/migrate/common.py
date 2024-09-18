import ConfigParser
import os
import sys

import galaxy.config
from agent_shed.galaxy_install import agent_migration_manager, installed_repository_manager


class MigrateAgentsApplication( object, galaxy.config.ConfiguresGalaxyMixin ):
    """Encapsulates the state of a basic Galaxy Universe application in order to initiate the Install Manager"""

    def __init__( self, agents_migration_config ):
        install_dependencies = 'install_dependencies' in sys.argv
        galaxy_config_file = 'galaxy.ini'
        self.name = 'galaxy'
        if '-c' in sys.argv:
            pos = sys.argv.index( '-c' )
            sys.argv.pop( pos )
            galaxy_config_file = sys.argv.pop( pos )
        if not os.path.exists( galaxy_config_file ):
            print "Galaxy config file does not exist (hint: use '-c config.ini' for non-standard locations): %s" % galaxy_config_file
            sys.exit( 1 )
        config_parser = ConfigParser.ConfigParser( { 'here' : os.getcwd() } )
        config_parser.read( galaxy_config_file )
        galaxy_config_dict = {}
        for key, value in config_parser.items( "app:main" ):
            galaxy_config_dict[ key ] = value
        self.config = galaxy.config.Configuration( **galaxy_config_dict )

        self.config.update_integrated_agent_panel = True

        self._configure_object_store()

        self._configure_security()

        self._configure_models()

        self._configure_datatypes_registry( )

        self._configure_agent_data_tables( from_shed_config=True )

        self._configure_agentbox()

        self._configure_agent_shed_registry()

        self.installed_repository_manager = installed_repository_manager.InstalledRepositoryManager( self )

        # Get the latest agent migration script number to send to the Install manager.
        latest_migration_script_number = int( agents_migration_config.split( '_' )[ 0 ] )
        # The value of migrated_agents_config is migrated_agents_conf.xml, and is reserved for
        # containing only those agents that have been eliminated from the distribution and moved
        # to the agent shed.  A side-effect of instantiating the AgentMigrationManager is the automatic
        # installation of all appropriate agent shed repositories.
        self.agent_migration_manager = \
            agent_migration_manager.AgentMigrationManager( app=self,
                                                         latest_migration_script_number=latest_migration_script_number,
                                                         agent_shed_install_config=os.path.join( self.config.root,
                                                                                                'scripts',
                                                                                                'migrate_agents',
                                                                                                agents_migration_config ),
                                                         migrated_agents_config=self.config.migrated_agents_config,
                                                         install_dependencies=install_dependencies )

    @property
    def sa_session( self ):
        return self.model.context.current

    def shutdown( self ):
        self.object_store.shutdown()
