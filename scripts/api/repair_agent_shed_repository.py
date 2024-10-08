#!/usr/bin/env python
"""
Repair a specified repository revision previously installed into Galaxy.

Here is a working example of how to use this script to repair a repository installed into Galaxy.
./repair_agent_shed_repository.py --api <api key> --local <galaxy base url> --url http://testagentshed.g2.bx.psu.edu --name gregs_filter --owner greg --revision f28d5018f9cb
"""

import os
import sys
import argparse
sys.path.insert( 0, os.path.dirname( __file__ ) )
from common import display
from common import submit

def clean_url( url ):
    if url.find( '//' ) > 0:
        # We have an url that includes a protocol, something like: http://localhost:9009
        items = url.split( '//' )
        return items[ 1 ].rstrip( '/' )
    return url.rstrip( '/' )
        
def main( options ):
    """Collect all user data and install the agents via the Galaxy API."""
    api_key = options.api
    base_galaxy_url = options.local_url.rstrip( '/' )
    base_agent_shed_url = options.agent_shed_url.rstrip( '/' )
    cleaned_agent_shed_url = clean_url( base_agent_shed_url )
    installed_agent_shed_repositories_url = '%s/api/%s' % ( base_galaxy_url, 'agent_shed_repositories' )
    data = {}
    data[ 'agent_shed_url' ] = cleaned_agent_shed_url
    data[ 'name' ] = options.name
    data[ 'owner' ] = options.owner
    data[ 'changeset_revision' ] = options.changeset_revision
    agent_shed_repository_id = None
    installed_agent_shed_repositories = display( api_key, installed_agent_shed_repositories_url, return_formatted=False )
    for installed_agent_shed_repository in installed_agent_shed_repositories:
        agent_shed = str( installed_agent_shed_repository[ 'agent_shed' ] )
        name = str( installed_agent_shed_repository[ 'name' ] )
        owner = str( installed_agent_shed_repository[ 'owner' ] )
        changeset_revision = str( installed_agent_shed_repository[ 'changeset_revision' ] )
        if agent_shed == cleaned_agent_shed_url and name == options.name and owner == options.owner and changeset_revision == options.changeset_revision:
            agent_shed_repository_id = installed_agent_shed_repository[ 'id' ]
            break
    if agent_shed_repository_id:
        url = '%s%s' % ( base_galaxy_url, '/api/agent_shed_repositories/%s/repair_repository_revision' % str( agent_shed_repository_id ) )
        submit( options.api, url, data )
    else:
        print "Invalid agent_shed / name / owner / changeset_revision."

if __name__ == '__main__':
    parser = argparse.ArgumentParser( description='Installation of agent shed repositories via the Galaxy API.' )
    parser.add_argument( "-u", "--url", dest="agent_shed_url", required=True, help="Agent Shed URL" )
    parser.add_argument( "-a", "--api", dest="api", required=True, help="API Key" )
    parser.add_argument( "-l", "--local", dest="local_url", required=True, help="URL of the galaxy instance." )
    parser.add_argument( "-n", "--name", required=True, help="Repository name." )
    parser.add_argument( "-o", "--owner", required=True, help="Repository owner." )
    parser.add_argument( "-r", "--revision", dest="changeset_revision", required=True, help="Repository owner." )
    options = parser.parse_args()
    main( options )
