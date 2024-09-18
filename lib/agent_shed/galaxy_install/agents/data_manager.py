import logging
import os
import threading

from agent_shed.galaxy_install.agents import agent_panel_manager
from agent_shed.util import xml_util

log = logging.getLogger( __name__ )


class DataManagerHandler( object ):

    def __init__( self, app ):
        self.app = app

    def data_manager_config_elems_to_xml_file( self, config_elems, config_filename ):
        """
        Persist the current in-memory list of config_elems to a file named by the value
        of config_filename.
        """
        lock = threading.Lock()
        lock.acquire( True )
        try:
            fh = open( config_filename, 'wb' )
            fh.write( '<?xml version="1.0"?>\n<data_managers>\n' )
            for elem in config_elems:
                fh.write( xml_util.xml_to_string( elem ) )
            fh.write( '</data_managers>\n' )
            fh.close()
        except Exception, e:
            log.exception( "Exception in DataManagerHandler.data_manager_config_elems_to_xml_file: %s" % str( e ) )
        finally:
            lock.release()

    def install_data_managers( self, shed_data_manager_conf_filename, metadata_dict, shed_config_dict,
                               relative_install_dir, repository, repository_agents_tups ):
        rval = []
        if 'data_manager' in metadata_dict:
            tpm = agent_panel_manager.AgentPanelManager( self.app )
            repository_agents_by_guid = {}
            for agent_tup in repository_agents_tups:
                repository_agents_by_guid[ agent_tup[ 1 ] ] = dict( agent_config_filename=agent_tup[ 0 ], agent=agent_tup[ 2 ] )
            # Load existing data managers.
            tree, error_message = xml_util.parse_xml( shed_data_manager_conf_filename )
            if tree is None:
                return rval
            config_elems = [ elem for elem in tree.getroot() ]
            repo_data_manager_conf_filename = metadata_dict['data_manager'].get( 'config_filename', None )
            if repo_data_manager_conf_filename is None:
                log.debug( "No data_manager_conf.xml file has been defined." )
                return rval
            data_manager_config_has_changes = False
            relative_repo_data_manager_dir = os.path.join( shed_config_dict.get( 'agent_path', '' ), relative_install_dir )
            repo_data_manager_conf_filename = os.path.join( relative_repo_data_manager_dir, repo_data_manager_conf_filename )
            tree, error_message = xml_util.parse_xml( repo_data_manager_conf_filename )
            if tree is None:
                return rval
            root = tree.getroot()
            for elem in root:
                if elem.tag == 'data_manager':
                    data_manager_id = elem.get( 'id', None )
                    if data_manager_id is None:
                        log.error( "A data manager was defined that does not have an id and will not be installed:\n%s" %
                                   xml_util.xml_to_string( elem ) )
                        continue
                    data_manager_dict = metadata_dict['data_manager'].get( 'data_managers', {} ).get( data_manager_id, None )
                    if data_manager_dict is None:
                        log.error( "Data manager metadata is not defined properly for '%s'." % ( data_manager_id ) )
                        continue
                    guid = data_manager_dict.get( 'guid', None )
                    if guid is None:
                        log.error( "Data manager guid '%s' is not set in metadata for '%s'." % ( guid, data_manager_id ) )
                        continue
                    elem.set( 'guid', guid )
                    agent_guid = data_manager_dict.get( 'agent_guid', None )
                    if agent_guid is None:
                        log.error( "Data manager agent guid '%s' is not set in metadata for '%s'." % ( agent_guid, data_manager_id ) )
                        continue
                    agent_dict = repository_agents_by_guid.get( agent_guid, None )
                    if agent_dict is None:
                        log.error( "Data manager agent guid '%s' could not be found for '%s'. Perhaps the agent is invalid?" %
                                   ( agent_guid, data_manager_id ) )
                        continue
                    agent = agent_dict.get( 'agent', None )
                    if agent is None:
                        log.error( "Data manager agent with guid '%s' could not be found for '%s'. Perhaps the agent is invalid?" %
                                   ( agent_guid, data_manager_id ) )
                        continue
                    agent_config_filename = agent_dict.get( 'agent_config_filename', None )
                    if agent_config_filename is None:
                        log.error( "Data manager metadata is missing 'agent_config_file' for '%s'." % ( data_manager_id ) )
                        continue
                    elem.set( 'shed_conf_file', shed_config_dict['config_filename'] )
                    if elem.get( 'agent_file', None ) is not None:
                        del elem.attrib[ 'agent_file' ]  # remove old agent_file info
                    agent_elem = tpm.generate_agent_elem( repository.agent_shed,
                                                        repository.name,
                                                        repository.installed_changeset_revision,
                                                        repository.owner,
                                                        agent_config_filename,
                                                        agent,
                                                        None )
                    elem.insert( 0, agent_elem )
                    data_manager = \
                        self.app.data_managers.load_manager_from_elem( elem,
                                                                       agent_path=shed_config_dict.get( 'agent_path', '' ),
                                                                       replace_existing=True )
                    if data_manager:
                        rval.append( data_manager )
                else:
                    log.warning( "Encountered unexpected element '%s':\n%s" % ( elem.tag, xml_util.xml_to_string( elem ) ) )
                config_elems.append( elem )
                data_manager_config_has_changes = True
            # Persist the altered shed_data_manager_config file.
            if data_manager_config_has_changes:
                self.data_manager_config_elems_to_xml_file( config_elems, shed_data_manager_conf_filename  )
        return rval

    def remove_from_data_manager( self, repository ):
        metadata_dict = repository.metadata
        if metadata_dict and 'data_manager' in metadata_dict:
            shed_data_manager_conf_filename = self.app.config.shed_data_manager_config_file
            tree, error_message = xml_util.parse_xml( shed_data_manager_conf_filename )
            if tree:
                root = tree.getroot()
                assert root.tag == 'data_managers', 'The file provided (%s) for removing data managers from is not a valid data manager xml file.' % ( shed_data_manager_conf_filename )
                guids = [ data_manager_dict.get( 'guid' ) for data_manager_dict in metadata_dict.get( 'data_manager', {} ).get( 'data_managers', {} ).itervalues() if 'guid' in data_manager_dict ]
                load_old_data_managers_by_guid = {}
                data_manager_config_has_changes = False
                config_elems = []
                for elem in root:
                    # Match Data Manager elements by guid and installed_changeset_revision
                    elem_matches_removed_data_manager = False
                    if elem.tag == 'data_manager':
                        guid = elem.get( 'guid', None )
                        if guid in guids:
                            agent_elem = elem.find( 'agent' )
                            if agent_elem is not None:
                                installed_changeset_revision_elem = agent_elem.find( 'installed_changeset_revision' )
                                if installed_changeset_revision_elem is not None:
                                    if installed_changeset_revision_elem.text == repository.installed_changeset_revision:
                                        elem_matches_removed_data_manager = True
                                    else:
                                        # This is a different version, which had been previously overridden
                                        load_old_data_managers_by_guid[ guid ] = elem
                    if elem_matches_removed_data_manager:
                        data_manager_config_has_changes = True
                    else:
                        config_elems.append( elem )
                # Remove data managers from in memory
                self.app.data_managers.remove_manager( guids )
                # Load other versions of any now uninstalled data managers, if any
                for elem in load_old_data_managers_by_guid.itervalues():
                    self.app.data_managers.load_manager_from_elem( elem )
                # Persist the altered shed_data_manager_config file.
                if data_manager_config_has_changes:
                    self.data_manager_config_elems_to_xml_file( config_elems, shed_data_manager_conf_filename  )
