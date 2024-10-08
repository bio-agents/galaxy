import logging
import os
import sys

galaxy_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir))
sys.path.insert(1, os.path.join(galaxy_root, 'lib'))

from galaxy.util import parse_xml

log = logging.getLogger(__name__)

# Set a 10 minute timeout for repository installation.
repository_installation_timeout = 600


def get_installed_repository_info( elem, last_galaxy_test_file_dir, last_tested_repository_name, last_tested_changeset_revision, agent_path ):
    """
    Return the GALAXY_TEST_FILE_DIR, the containing repository name and the
    change set revision for the agent elem. This only happens when testing
    agents installed from the agent shed.
    """
    agent_config_path = elem.get( 'file' )
    installed_agent_path_items = agent_config_path.split( '/repos/' )
    sans_shed = installed_agent_path_items[ 1 ]
    path_items = sans_shed.split( '/' )
    repository_owner = path_items[ 0 ]
    repository_name = path_items[ 1 ]
    changeset_revision = path_items[ 2 ]
    if repository_name != last_tested_repository_name or changeset_revision != last_tested_changeset_revision:
        # Locate the test-data directory.
        installed_agent_path = os.path.join( installed_agent_path_items[ 0 ], 'repos', repository_owner, repository_name, changeset_revision )
        for root, dirs, files in os.walk( os.path.join(agent_path, installed_agent_path )):
            if '.' in dirs:
                dirs.remove( '.hg' )
            if 'test-data' in dirs:
                return os.path.join( root, 'test-data' ), repository_name, changeset_revision
        return None, repository_name, changeset_revision
    return last_galaxy_test_file_dir, last_tested_repository_name, last_tested_changeset_revision


def parse_agent_panel_config( config, shed_agents_dict ):
    """
    Parse a shed-related agent panel config to generate the shed_agents_dict. This only happens when testing agents installed from the agent shed.
    """
    last_galaxy_test_file_dir = None
    last_tested_repository_name = None
    last_tested_changeset_revision = None
    agent_path = None
    has_test_data = False
    tree = parse_xml( config )
    root = tree.getroot()
    agent_path = root.get('agent_path')
    for elem in root:
        if elem.tag == 'agent':
            galaxy_test_file_dir, \
                last_tested_repository_name, \
                last_tested_changeset_revision = get_installed_repository_info( elem,
                                                                                last_galaxy_test_file_dir,
                                                                                last_tested_repository_name,
                                                                                last_tested_changeset_revision,
                                                                                agent_path )
            if galaxy_test_file_dir:
                if not has_test_data:
                    has_test_data = True
                if galaxy_test_file_dir != last_galaxy_test_file_dir:
                    if not os.path.isabs( galaxy_test_file_dir ):
                        galaxy_test_file_dir = os.path.join( galaxy_root, galaxy_test_file_dir )
                guid = elem.get( 'guid' )
                shed_agents_dict[ guid ] = galaxy_test_file_dir
                last_galaxy_test_file_dir = galaxy_test_file_dir
        elif elem.tag == 'section':
            for section_elem in elem:
                if section_elem.tag == 'agent':
                    galaxy_test_file_dir, \
                        last_tested_repository_name, \
                        last_tested_changeset_revision = get_installed_repository_info( section_elem,
                                                                                        last_galaxy_test_file_dir,
                                                                                        last_tested_repository_name,
                                                                                        last_tested_changeset_revision,
                                                                                        agent_path )
                    if galaxy_test_file_dir:
                        if not has_test_data:
                            has_test_data = True
                        if galaxy_test_file_dir != last_galaxy_test_file_dir:
                            if not os.path.isabs( galaxy_test_file_dir ):
                                galaxy_test_file_dir = os.path.join( galaxy_root, galaxy_test_file_dir )
                        guid = section_elem.get( 'guid' )
                        shed_agents_dict[ guid ] = galaxy_test_file_dir
                        last_galaxy_test_file_dir = galaxy_test_file_dir
    return has_test_data, shed_agents_dict
