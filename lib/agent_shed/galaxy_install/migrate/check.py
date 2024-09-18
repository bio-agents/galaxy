import logging
import os
import subprocess
import sys

from migrate.versioning import repository, schema
from sqlalchemy import create_engine, MetaData, Table

from galaxy.util.odict import odict
from agent_shed.util import common_util

log = logging.getLogger( __name__ )

# Path relative to galaxy
migrate_repository_directory = os.path.abspath(os.path.dirname( __file__ )).replace( os.getcwd() + os.path.sep, '', 1 )
migrate_repository = repository.Repository( migrate_repository_directory )


def verify_agents( app, url, galaxy_config_file=None, engine_options={} ):
    # Check the value in the migrate_agents.version database table column to verify that the number is in
    # sync with the number of version scripts in ~/lib/galaxy/agents/migrate/versions.
    # Create engine and metadata
    engine = create_engine( url, **engine_options )
    meta = MetaData( bind=engine )
    # The migrate_agents table was created in database version script 0092_add_migrate_agents_table.py.
    Table( "migrate_agents", meta, autoload=True )
    # Verify that the code and the database are in sync.
    db_schema = schema.ControlledSchema( engine, migrate_repository )
    latest_agent_migration_script_number = migrate_repository.versions.latest
    if latest_agent_migration_script_number != db_schema.version:
        # The default behavior is that the agent shed is down.
        agent_shed_accessible = False
        if app.new_installation:
            # New installations will not be missing agents, so we don't need to worry about them.
            missing_agent_configs_dict = odict()
        else:
            agent_panel_configs = common_util.get_non_shed_agent_panel_configs( app )
            if agent_panel_configs:
                # The missing_agent_configs_dict contents are something like:
                # {'emboss_antigenic.xml': [('emboss', '5.0.0', 'package', '\nreadme blah blah blah\n')]}
                agent_shed_accessible, missing_agent_configs_dict = common_util.check_for_missing_agents( app,
                                                                                                       agent_panel_configs,
                                                                                                       latest_agent_migration_script_number )
            else:
                # It doesn't matter if the agent shed is accessible since there are no migrated agents defined in the local Galaxy instance, but
                # we have to set the value of agent_shed_accessible to True so that the value of migrate_agents.version can be correctly set in
                # the database.
                agent_shed_accessible = True
                missing_agent_configs_dict = odict()
        have_agent_dependencies = False
        for k, v in missing_agent_configs_dict.items():
            if v:
                have_agent_dependencies = True
                break
        if not app.config.running_functional_tests:
            if agent_shed_accessible:
                # Automatically update the value of the migrate_agents.version database table column.
                config_arg = ''
                if galaxy_config_file:
                    config_arg = " -c %s" % galaxy_config_file
                cmd = 'sh manage_agents.sh%s upgrade' % config_arg
                proc = subprocess.Popen( args=cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT )
                return_code = proc.wait()
                output = proc.stdout.read( 32768 )
                if return_code != 0:
                    raise Exception( "Error attempting to update the value of migrate_agents.version: %s" % output )
                elif missing_agent_configs_dict:
                    if len( agent_panel_configs ) == 1:
                        plural = ''
                        agent_panel_config_file_names = agent_panel_configs[ 0 ]
                    else:
                        plural = 's'
                        agent_panel_config_file_names = ', '.join( agent_panel_configs )
                    msg = "\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
                    msg += "\n\nThe list of files at the end of this message refers to agents that are configured to load into the agent panel for\n"
                    msg += "this Galaxy instance, but have been removed from the Galaxy distribution.  These agents and their dependencies can be\n"
                    msg += "automatically installed from the Galaxy agent shed at http://agentshed.g2.bx.psu.edu.\n\n"
                    msg += "To skip this process, attempt to start your Galaxy server again (e.g., sh run.sh or whatever you use).  If you do this,\n"
                    msg += "be aware that these agents will no longer be available in your Galaxy agent panel, and entries for each of them should\n"
                    msg += "be removed from your file%s named %s.\n\n" % ( plural, agent_panel_config_file_names )
                    msg += "CRITICAL NOTE IF YOU PLAN TO INSTALL\n"
                    msg += "The location in which the agent repositories will be installed is the value of the 'agent_path' attribute in the <agent>\n"
                    msg += 'tag of the file named ./migrated_agent_conf.xml (i.e., <agentbox agent_path="../shed_agents">).  The default location\n'
                    msg += "setting is '../shed_agents', which may be problematic for some cluster environments, so make sure to change it before\n"
                    msg += "you execute the installation process if appropriate.  The configured location must be outside of the Galaxy installation\n"
                    msg += "directory or it must be in a sub-directory protected by a properly configured .hgignore file if the directory is within\n"
                    msg += "the Galaxy installation directory hierarchy.  This is because agent shed repositories will be installed using mercurial's\n"
                    msg += "clone feature, which creates .hg directories and associated mercurial repository files.  Not having .hgignore properly\n"
                    msg += "configured could result in undesired behavior when modifying or updating your local Galaxy instance or the agent shed\n"
                    msg += "repositories if they are in directories that pose conflicts.  See mercurial's .hgignore documentation at the following\n"
                    msg += "URL for details.\n\nhttp://mercurial.selenic.com/wiki/.hgignore\n\n"
                    if have_agent_dependencies:
                        msg += "The following agent dependencies can also optionally be installed (see the option flag in the command below).  If you\n"
                        msg += "choose to install them (recommended), they will be installed within the location specified by the 'agent_dependency_dir'\n"
                        msg += "setting in your main Galaxy configuration file (e.g., uninverse_wsgi.ini).\n"
                        processed_agent_dependencies = []
                        for missing_agent_config, agent_dependencies in missing_agent_configs_dict.items():
                            for agent_dependencies_tup in missing_agent_configs_dict[ missing_agent_config ][ 'agent_dependencies' ]:
                                if agent_dependencies_tup not in processed_agent_dependencies:
                                    msg += "------------------------------------\n"
                                    msg += "Agent Dependency\n"
                                    msg += "------------------------------------\n"
                                    msg += "Name: %s, Version: %s, Type: %s\n" % ( agent_dependencies_tup[ 0 ],
                                                                                   agent_dependencies_tup[ 1 ],
                                                                                   agent_dependencies_tup[ 2 ] )
                                    if len( agent_dependencies_tup ) >= 4:
                                        msg += "Requirements and installation information:\n"
                                        msg += "%s\n" % agent_dependencies_tup[ 3 ]
                                    else:
                                        msg += "\n"
                                    msg += "------------------------------------\n"
                                    processed_agent_dependencies.append( agent_dependencies_tup )
                        msg += "\n"
                    msg += "%s" % output.replace( 'done', '' )
                    msg += "vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv\n"
                    msg += "sh ./scripts/migrate_agents/%04d_agents.sh\n" % latest_agent_migration_script_number
                    msg += "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n\n"
                    if have_agent_dependencies:
                        msg += "The agent dependencies listed above will be installed along with the repositories if you add the 'install_dependencies'\n"
                        msg += "option to the above command like this:\n\n"
                        msg += "vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv\n"
                        msg += "sh ./scripts/migrate_agents/%04d_agents.sh install_dependencies\n" % latest_agent_migration_script_number
                        msg += "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n\n"
                        msg += "Agent dependencies can be installed after the repositories have been installed as well.\n\n"
                    msg += "After the installation process finishes, you can start your Galaxy server.  As part of this installation process,\n"
                    msg += "entries for each of the following agent config files will be added to the file named ./migrated_agent_conf.xml, so these\n"
                    msg += "agents will continue to be loaded into your agent panel.  Because of this, existing entries for these agents have been\n"
                    msg += "removed from your file%s named %s.\n\n" % ( plural, agent_panel_config_file_names )
                    for missing_agent_config, agent_dependencies in missing_agent_configs_dict.items():
                        msg += "%s\n" % missing_agent_config
                    msg += "<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<\n"
                    raise Exception( msg )
            else:
                log.debug( "The main Galaxy agent shed is not currently available, so skipped agent migration %s until next server startup" % db_schema.version )
    else:
        log.info( "At migrate_agents version %d" % db_schema.version )


def migrate_to_current_version( engine, schema ):
    # Changes to get to current version.
    changeset = schema.changeset( None )
    for ver, change in changeset:
        nextver = ver + changeset.step
        log.info( 'Installing agents from version %s -> %s... ' % ( ver, nextver ) )
        old_stdout = sys.stdout

        class FakeStdout( object ):
            def __init__( self ):
                self.buffer = []

            def write( self, s ):
                self.buffer.append( s )

            def flush( self ):
                pass

        sys.stdout = FakeStdout()
        try:
            schema.runchange( ver, change, changeset.step )
        finally:
            for message in "".join( sys.stdout.buffer ).split( "\n" ):
                log.info( message )
            sys.stdout = old_stdout
