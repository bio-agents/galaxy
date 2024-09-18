#!/usr/bin/env python
##Dan Blankenberg
##Very simple example of using the API to run Data Managers
##Script makes the naive assumption that dbkey==sequence id, which in many cases is not true nor desired
##*** This script is not recommended for use as-is on a production server ***

import os
import sys
import optparse
import urlparse
import time

sys.path.insert( 0, os.path.dirname( __file__ ) )

from common import post, get

DEFAULT_SLEEP_TIME = 3
FETCH_GENOME_TOOL_ID = 'testagentshed.g2.bx.psu.edu/repos/blankenberg/data_manager_fetch_genome_all_fasta/data_manager_fetch_genome_all_fasta/0.0.1'
BUILD_INDEX_TOOLS_ID = [ 'testagentshed.g2.bx.psu.edu/repos/blankenberg/data_manager_bwa_index_builder/bwa_index_builder_data_manager/0.0.1',
                        'testagentshed.g2.bx.psu.edu/repos/blankenberg/data_manager_bwa_index_builder/bwa_color_space_index_builder_data_manager/0.0.1' ]

def run_agent( agent_id, history_id, params, api_key, galaxy_url, wait=True, sleep_time=None, **kwargs ):
    sleep_time = sleep_time or DEFAULT_SLEEP_TIME
    agents_url = urlparse.urljoin( galaxy_url, 'api/agents' )
    payload = {
        'agent_id'       : agent_id,
    }
    if history_id:
        payload['history_id'] = history_id
    payload[ 'inputs' ] = params
    rval = post( api_key, agents_url, payload )
    if wait:
        outputs = list( rval['outputs'] )
        while outputs:
            finished_datasets = []
            for i, dataset_dict in enumerate( outputs ):
                if dataset_is_terminal( dataset_dict['id'], api_key=api_key, galaxy_url=galaxy_url ):
                    finished_datasets.append( i )
            for i in reversed( finished_datasets ):
                outputs.pop( 0 )
            if wait and outputs:
                time.sleep( sleep_time )
                
    return rval

def get_dataset_state( hda_id, api_key, galaxy_url ):
    datasets_url = urlparse.urljoin( galaxy_url, 'api/datasets/%s' % hda_id )
    dataset_info = get( api_key, datasets_url )
    return dataset_info['state']

def dataset_is_terminal( hda_id, api_key, galaxy_url ):
    dataset_state = get_dataset_state( hda_id, api_key, galaxy_url )
    return dataset_state in [ 'ok', 'error' ]
  
if __name__ == '__main__':
    #Parse Command Line
    parser = optparse.OptionParser()
    parser.add_option( '-k', '--key', dest='api_key', action='store', type="string", default=None, help='API Key.' )
    parser.add_option( '-u', '--url', dest='base_url', action='store', type="string", default='http://localhost:8080', help='Base URL of Galaxy Server' )
    parser.add_option( '-d', '--dbkey', dest='dbkeys', action='append', type="string", default=[], help='List of dbkeys to download and Index' )
    parser.add_option( '-s', '--sleep_time', dest='sleep_time', action='store', type="int", default=DEFAULT_SLEEP_TIME, help='How long to sleep between check loops' )
    (options, args) = parser.parse_args()
    
    #check options
    assert options.api_key is not None, ValueError( 'You must specify an API key.' )
    assert options.dbkeys, ValueError( 'You must specify at least one dbkey to use.' )
    
    #check user is admin
    configuration_options =  get( options.api_key, urlparse.urljoin( options.base_url, 'api/configuration' ) )
    if 'library_import_dir' not in configuration_options: #hack to check if is admin user
        print "Warning: Data Managers are only available to admin users. The API Key provided does not appear to belong to an admin user. Will attempt to run anyway."
    
    #Fetch Genomes
    dbkeys = {}
    for dbkey in options.dbkeys:
        if dbkey not in dbkeys:
            dbkeys[ dbkey ] = run_agent( FETCH_GENOME_TOOL_ID, None, { 'dbkey':dbkey, 'reference_source|reference_source_selector': 'ucsc', 'reference_source|requested_dbkey': dbkey }, options.api_key, options.base_url, wait=False )
        else:
            "dbkey (%s) was specified more than once, skipping additional specification." % ( dbkey )
    
    print 'Genomes Queued for downloading.'
    
    #Start indexers
    indexing_agents = []
    while dbkeys:
        for dbkey, value in dbkeys.items():
            if dataset_is_terminal( value['outputs'][0]['id'], options.api_key, options.base_url ):
                del dbkeys[ dbkey ]
                for agent_id in BUILD_INDEX_TOOLS_ID:
                    indexing_agents.append( run_agent( agent_id, None, { 'all_fasta_source':dbkey }, options.api_key, options.base_url, wait=False ) )
        if dbkeys:
            time.sleep( options.sleep_time )
    
    print 'All genomes downloaded and indexers now queued.'
    
    #Wait for indexers to finish
    while indexing_agents:
        for i, indexing_agent_value in enumerate( indexing_agents ):
            if dataset_is_terminal( indexing_agent_value['outputs'][0]['id'], options.api_key, options.base_url ):
                print 'Finished:', indexing_agent_value
                del indexing_agents[i]
                break
        if indexing_agents:
            time.sleep( options.sleep_time )
    
    print 'All indexers have been run, please check results.'
