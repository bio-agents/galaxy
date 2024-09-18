#!/usr/bin/env python
"""
This script will retrieve a list of dictionaries (one for each category) from the Agent Shed defined
by the --from_agent_shed parameter, which should be a base Agent Shed URL.  It will retrieve the category
name and description from each dictionary and create a new category with that name and description in
the Agent Shed defined by the --to_agent_shed parameter (a different base Agent Shed URL).  Categories
that already exist with a specified name in the Agent Shed in which the categories are being created
will not be affected.

This script is very useful for populating a new development Agent Shed with the set of categories that
currently exist in either the test or main public Galaxy Agent Sheds.  This will streamline building
new repository hierarchies in the development Agent Shed and exporting them into a capsule that can be
imported into one of the public Agent Sheds.

Here is a working example of how to use this script to retrieve the current set of categories that are
available in the test public Agent Shed and create each of them in a local development Agent Shed.

./create_categories.py -a <api key> -f http://testagentshed.g2.bx.psu.edu -t http://localhost:9009
"""

import argparse

from common import get, submit


def main( options ):
    api_key = options.api
    from_agent_shed = options.from_agent_shed.rstrip( '/' )
    to_agent_shed = options.to_agent_shed.rstrip( '/' )
    # Get the categories from the specified Agent Shed.
    url = '%s/api/categories' % from_agent_shed
    category_dicts = get( url )
    create_response_dicts = []
    for category_dict in category_dicts:
        name = category_dict.get( 'name', None )
        description = category_dict.get( 'description', None )
        if name is not None and description is not None:
            data = dict( name=name,
                         description=description )
            url = '%s/api/categories' % to_agent_shed
            try:
                response = submit( url, data, api_key )
            except Exception, e:
                response = str( e )
                print "Error attempting to create category using URL: ", url, " exception: ", str( e )
            create_response_dict = dict( response=response )
            create_response_dicts.append( create_response_dict )

if __name__ == '__main__':
    parser = argparse.ArgumentParser( description='Retrieve a list of categories from a Agent Shed and create them in another Agent Shed.' )
    parser.add_argument( "-a", "--api", dest="api", required=True, help="API Key for Agent Shed in which categories will be created" )
    parser.add_argument( "-f", "--from_agent_shed", dest="from_agent_shed", required=True, help="URL of Agent Shed from which to retrieve the categories" )
    parser.add_argument( "-t", "--to_agent_shed", dest="to_agent_shed", required=True, help="URL of Agent Shed in which to create the categories" )
    options = parser.parse_args()
    main( options )
