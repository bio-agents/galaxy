"""
This script will start up its own web application which includes a AgentMigrationManager (~/lib/galaxy/agent_shed/agent_migration_manager.py).
For each agent discovered missing, the agent shed repository that contains it will be installed on disk and a new entry will be
created for it in the migrated_agents_conf.xml file.  These entries will be made so that the agent panel will be displayed the same
as it was before the agents were eliminated from the Galaxy distribution.  The AgentMigrationManager will properly handle entries in
migrated_agents_conf.xml for agents outside agent panel sections as well as agents inside agent panel sections, depending upon the
layout of the local agent_conf.xml file.  Entries will not be created in migrated_agents_conf.xml for agents included in the agent
shed repository but not defined in agent_conf.xml.
"""
import os
import sys

new_path = [ os.path.join( os.getcwd(), "lib" ) ]
# Remove scripts/ from the path.
new_path.extend( sys.path[ 1: ] )
sys.path = new_path

from agent_shed.galaxy_install.migrate.common import MigrateAgentsApplication

app = MigrateAgentsApplication( sys.argv[ 1 ] )
non_shed_agent_confs = app.agent_migration_manager.proprietary_agent_confs
if len( non_shed_agent_confs ) == 1:
    plural = ''
    file_names = non_shed_agent_confs[ 0 ]
else:
    plural = 's'
    file_names = ', '.join( non_shed_agent_confs )
msg = "\nThe installation process is finished.  All agents associated with this migration that were defined in your file%s named\n" % plural
msg += "%s, have been removed.  You may now start your Galaxy server.\n" % file_names
print msg
app.shutdown()
sys.exit( 0 )
