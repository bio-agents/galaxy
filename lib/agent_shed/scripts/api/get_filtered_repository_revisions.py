#!/usr/bin/env python
"""
Get a list of dictionaries, each of which defines a repository revision, that is filtered by a combination of one or more
of the following.

- do_not_test : true / false
- downloadable : true / false
- includes_agents : true / false
- malicious : true / false
- missing_test_components : true / false
- skip_agent_test : true / false
- test_install_error : true / false
- agents_functionally_correct : true / false

Results can also be restricted to the latest downloadable revision of each repository.

This script is useful for analyzing the Agent Shed's install and test framework.

Here is a working example of how to use this script.
./get_filtered_repository_revisions.py --url http://testagentshed.g2.bx.psu.edu
"""

import argparse
import os
import sys
import urllib

sys.path.insert(1, os.path.join( os.path.dirname( __file__ ), os.pardir, os.pardir, os.pardir ) )
from galaxy.util import asbool
from agent_shed.util import hg_util

from common import get_api_url, get_repository_dict, json_from_url


def main( options ):
    base_agent_shed_url = options.agent_shed_url.rstrip( '/' )
    latest_revision_only = asbool( options.latest_revision_only )
    do_not_test = str( options.do_not_test )
    downloadable = str( options.downloadable )
    includes_agents = str( options.includes_agents )
    malicious = str( options.malicious )
    missing_test_components = str( options.missing_test_components )
    skip_agent_test = str( options.skip_agent_test )
    test_install_error = str( options.test_install_error )
    agents_functionally_correct = str( options.agents_functionally_correct )
    parts = [ 'repository_revisions' ]
    params = urllib.urlencode( dict( do_not_test=do_not_test,
                                     downloadable=downloadable,
                                     includes_agents=includes_agents,
                                     malicious=malicious,
                                     missing_test_components=missing_test_components,
                                     skip_agent_test=skip_agent_test,
                                     test_install_error=test_install_error,
                                     agents_functionally_correct=agents_functionally_correct ) )
    api_url = get_api_url( base=base_agent_shed_url, parts=parts, params=params )
    baseline_repository_dicts, error_message = json_from_url( api_url )
    if baseline_repository_dicts is None or error_message:
        print error_message
    else:
        repository_dicts = []
        for baseline_repository_dict in baseline_repository_dicts:
            # We need to get additional details from the agent shed API to pass on to the
            # module that will generate the install methods.
            repository_dict, error_message = get_repository_dict( base_agent_shed_url, baseline_repository_dict )
            if error_message:
                print 'Error getting additional details from the API: ', error_message
                repository_dicts.append( baseline_repository_dict )
            else:
                # Don't test empty repositories.
                changeset_revision = baseline_repository_dict.get( 'changeset_revision', hg_util.INITIAL_CHANGELOG_HASH )
                if changeset_revision != hg_util.INITIAL_CHANGELOG_HASH:
                    # Merge the dictionary returned from /api/repository_revisions with the detailed repository_dict and
                    # append it to the list of repository_dicts to install and test.
                    if latest_revision_only:
                        latest_revision = repository_dict.get( 'latest_revision', hg_util.INITIAL_CHANGELOG_HASH )
                        if changeset_revision == latest_revision:
                            repository_dicts.append( dict( repository_dict.items() + baseline_repository_dict.items() ) )
                    else:
                        repository_dicts.append( dict( repository_dict.items() + baseline_repository_dict.items() ) )
        print '\n\n', repository_dicts
        print '\nThe url:\n\n', api_url, '\n\nreturned ', len( repository_dicts ), ' repository dictionaries...'

if __name__ == '__main__':
    parser = argparse.ArgumentParser( description='Get a filtered list of repository dictionaries.' )
    parser.add_argument( "-u", "--url", dest="agent_shed_url", required=True, help="Agent Shed URL" )
    parser.add_argument( "-l", "--latest_revision_only", dest="latest_revision_only", default=True,
                         help="Restrict results to latest downloadable revision only" )
    parser.add_argument( "-n", "--do_not_test", help="do_not_test", default=False )
    parser.add_argument( "-d", "--downloadable", help="downloadable", default=True )
    parser.add_argument( "-i", "--includes_agents", help="includes_agents", default=True )
    parser.add_argument( "-m", "--malicious", help="malicious", default=False )
    parser.add_argument( "-c", "--missing_test_components", help="missing_test_components", default=False )
    parser.add_argument( "-s", "--skip_agent_test", help="skip_agent_test", default=False )
    parser.add_argument( "-e", "--test_install_error", help="test_install_error", default=False )
    parser.add_argument( "-t", "--agents_functionally_correct", help="agents_functionally_correct", default=True )
    options = parser.parse_args()
    main( options )
