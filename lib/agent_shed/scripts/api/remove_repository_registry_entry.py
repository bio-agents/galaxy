#!/usr/bin/env python
"""
Remove appropriate entries from the Agent Shed's repository registry for a specified repository.

Here is a working example of how to use this script.
python ./remove_repository_registry_entry.py -a <api key> -u <agent shed url> -n <repository name> -o <repository owner>
"""

import argparse

from common import submit


def main( options ):
    api_key = options.api_key
    if api_key:
        if options.agent_shed_url and options.name and options.owner:
            base_agent_shed_url = options.agent_shed_url.rstrip( '/' )
            data = {}
            data[ 'agent_shed_url' ] = base_agent_shed_url
            data[ 'name' ] = options.name
            data[ 'owner' ] = options.owner
            url = '%s%s' % ( base_agent_shed_url, '/api/repositories/remove_repository_registry_entry' )
            response_dict = submit( url, data, api_key=api_key, return_formatted=False )
            print response_dict
        else:
            print "Invalid agent_shed: ", base_agent_shed_url, " name: ", options.name, " or owner: ", options.owner, "."
    else:
        print "An API key for an admin user in the Agent Shed is required to remove entries from the Agent Shed's repository registry."

if __name__ == '__main__':
    parser = argparse.ArgumentParser( description='Remove entries from the Agent Shed repository registry for a specified repository.' )
    parser.add_argument( "-a", "--api_key", dest="api_key", required=True, help="API Key for user removing entries from the Agent Shed's repository registry." )
    parser.add_argument( "-u", "--url", dest="agent_shed_url", required=True, help="Agent Shed URL" )
    parser.add_argument( "-n", "--name", dest='name', required=True, help="Repository name." )
    parser.add_argument( "-o", "--owner", dest='owner', required=True, help="Repository owner." )
    options = parser.parse_args()
    main( options )
