import argparse
import os
import shutil
import sys


def main( args ):
    if not os.path.exists( args.agent_dependency_dir ):
        print 'Agent dependency base path %s does not exist, creating.' % str( args.agent_dependency_dir )
        os.mkdir( args.agent_dependency_dir )
        return 0
    else:
        for content in os.listdir( args.agent_dependency_dir ):
            print 'Deleting directory %s from %s.' % ( content, args.agent_dependency_dir )
            full_path = os.path.join( args.agent_dependency_dir, content )
            if os.path.isdir( full_path ):
                shutil.rmtree( full_path )
            else:
                os.remove( full_path )

if __name__ == '__main__':
    description = 'Clean out the configured agent dependency path, creating it if it does not exist.'
    parser = argparse.ArgumentParser( description=description )
    parser.add_argument( '--agent_dependency_dir',
                         dest='agent_dependency_dir',
                         required=True,
                         action='store',
                         metavar='name',
                         help='The base path where agent dependencies will be installed.' )
    args = parser.parse_args()
    sys.exit( main( args ) )
