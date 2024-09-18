import argparse
import os
import sys

sys.path.insert(1, os.path.join( os.path.dirname( __file__ ), os.pardir, os.pardir ) )

import galaxy.config as galaxy_config
import galaxy.model
import galaxy.model.agent_shed_install.mapping as install_mapper


class CleanUpDependencyApplication( object ):
    """Application that enables querying the database using the agent_shed_install model."""

    def __init__( self, config ):
        self.config = config
        # Setup the database engine and ORM
        self.model = install_mapper.init( self.config.database_connection, engine_options={}, create_tables=False )

    @property
    def sa_session( self ):
        """Returns a SQLAlchemy session."""
        return self.model.context.current

    def shutdown( self ):
        pass


def main( args, app ):
    if not os.path.exists( args.basepath ):
        print 'Agent dependency base path %s does not exist.' % str( args.basepath )
        return
    print 'Checking agent dependency path %s' % args.basepath
    agent_dependency_dirs = get_agent_dependency_dirs( app )
    for agent_dependency_dir in agent_dependency_dirs:
        path = os.path.join( args.basepath, agent_dependency_dir )
        if os.path.exists( path ):
            path_contents = os.listdir( path )
            if len( path_contents ) > 0:
                print 'Found non-empty agent dependency installation directory %s.' % path
                print 'Directory has the following contents: \n   %s' % '\n   '.join( path_contents )


def get_agent_dependency_dirs( app ):
    dependency_paths = []
    for agent_dependency in app.sa_session.query( galaxy.model.agent_shed_install.AgentDependency ).all():
        dependency_paths.append( agent_dependency.installation_directory( app ) )
    return dependency_paths

if __name__ == '__main__':
    description = 'Clean out or list the contents any agent dependency directory under the provided'
    description += 'agent dependency path. Remove any non-empty directories found if the '
    description += '--delete command line argument is provided.'
    parser = argparse.ArgumentParser( description=description )
    parser.add_argument( '--basepath',
                         dest='basepath',
                         required=True,
                         action='store',
                         metavar='name',
                         help='The base path where agent dependencies are installed.' )
    parser.add_argument( '--dburi',
                         dest='dburi',
                         required=True,
                         action='store',
                         metavar='dburi',
                         help='The database URI to connect to.' )
    args = parser.parse_args()
    database_connection = args.dburi
    config_dict = dict( database_connection=database_connection, agent_dependency_dir=args.basepath )
    config = galaxy_config.Configuration( **config_dict )
    app = CleanUpDependencyApplication( config )
    sys.exit( main( args, app ) )
