import logging
import os
import shutil

from xml.etree import ElementTree as XmlET

from agent_shed.util import hg_util, xml_util

log = logging.getLogger( __name__ )


class AgentDataTableManager( object ):

    def __init__( self, app ):
        self.app = app

    def generate_repository_info_elem( self, agent_shed, repository_name, changeset_revision, owner,
                                       parent_elem=None, **kwd ):
        """Create and return an ElementTree repository info Element."""
        if parent_elem is None:
            elem = XmlET.Element( 'agent_shed_repository' )
        else:
            elem = XmlET.SubElement( parent_elem, 'agent_shed_repository' )
        agent_shed_elem = XmlET.SubElement( elem, 'agent_shed' )
        agent_shed_elem.text = agent_shed
        repository_name_elem = XmlET.SubElement( elem, 'repository_name' )
        repository_name_elem.text = repository_name
        repository_owner_elem = XmlET.SubElement( elem, 'repository_owner' )
        repository_owner_elem.text = owner
        changeset_revision_elem = XmlET.SubElement( elem, 'installed_changeset_revision' )
        changeset_revision_elem.text = changeset_revision
        # add additional values
        # TODO: enhance additional values to allow e.g. use of dict values that will recurse
        for key, value in kwd.iteritems():
            new_elem = XmlET.SubElement( elem, key )
            new_elem.text = value
        return elem

    def generate_repository_info_elem_from_repository( self, agent_shed_repository, parent_elem=None, **kwd ):
        return self.generate_repository_info_elem( agent_shed_repository.agent_shed,
                                                   agent_shed_repository.name,
                                                   agent_shed_repository.installed_changeset_revision,
                                                   agent_shed_repository.owner,
                                                   parent_elem=parent_elem,
                                                   **kwd )

    def get_agent_index_sample_files( self, sample_files ):
        """
        Try to return the list of all appropriate agent data sample files included
        in the repository.
        """
        agent_index_sample_files = []
        for s in sample_files:
            # The problem with this is that Galaxy does not follow a standard naming
            # convention for file names.
            if s.endswith( '.loc.sample' ) or s.endswith( '.xml.sample' ) or s.endswith( '.txt.sample' ):
                agent_index_sample_files.append( str( s ) )
        return agent_index_sample_files

    def handle_missing_data_table_entry( self, relative_install_dir, agent_path, repository_agents_tups ):
        """
        Inspect each agent to see if any have input parameters that are dynamically
        generated select lists that require entries in the agent_data_table_conf.xml
        file.  This method is called only from Galaxy (not the agent shed) when a
        repository is being installed or reinstalled.
        """
        missing_data_table_entry = False
        for index, repository_agents_tup in enumerate( repository_agents_tups ):
            tup_path, guid, repository_agent = repository_agents_tup
            if repository_agent.params_with_missing_data_table_entry:
                missing_data_table_entry = True
                break
        if missing_data_table_entry:
            # The repository must contain a agent_data_table_conf.xml.sample file that includes
            # all required entries for all agents in the repository.
            sample_agent_data_table_conf = hg_util.get_config_from_disk( 'agent_data_table_conf.xml.sample',
                                                                        relative_install_dir )
            if sample_agent_data_table_conf:
                # Add entries to the AgentDataTableManager's in-memory data_tables dictionary.
                error, message = self.handle_sample_agent_data_table_conf_file( sample_agent_data_table_conf,
                                                                               persist=True )
                if error:
                    # TODO: Do more here than logging an exception.
                    log.debug( message )
            # Reload the agent into the local list of repository_agents_tups.
            repository_agent = self.app.agentbox.load_agent( os.path.join( agent_path, tup_path ), guid=guid, use_cached=False )
            repository_agents_tups[ index ] = ( tup_path, guid, repository_agent )
            # Reset the agent_data_tables by loading the empty agent_data_table_conf.xml file.
            self.reset_agent_data_tables()
        return repository_agents_tups

    def handle_sample_agent_data_table_conf_file( self, filename, persist=False ):
        """
        Parse the incoming filename and add new entries to the in-memory
        self.app.agent_data_tables dictionary.  If persist is True (should
        only occur if call is from the Galaxy side, not the agent shed), the
        new entries will be appended to Galaxy's shed_agent_data_table_conf.xml
        file on disk.
        """
        error = False
        message = ''
        try:
            new_table_elems, message = self.app.agent_data_tables \
                .add_new_entries_from_config_file( config_filename=filename,
                                                   agent_data_path=self.app.config.shed_agent_data_path,
                                                   shed_agent_data_table_config=self.app.config.shed_agent_data_table_config,
                                                   persist=persist )
            if message:
                error = True
        except Exception, e:
            message = str( e )
            error = True
        return error, message

    def get_target_install_dir( self, agent_shed_repository ):
        agent_path, relative_target_dir = agent_shed_repository.get_agent_relative_path( self.app )
        # This is where index files will reside on a per repo/installed version basis.
        target_dir = os.path.join( self.app.config.shed_agent_data_path, relative_target_dir )
        if not os.path.exists( target_dir ):
            os.makedirs( target_dir )
        return target_dir, agent_path, relative_target_dir

    def install_agent_data_tables( self, agent_shed_repository, agent_index_sample_files ):
        TOOL_DATA_TABLE_FILE_NAME = 'agent_data_table_conf.xml'
        TOOL_DATA_TABLE_FILE_SAMPLE_NAME = '%s.sample' % ( TOOL_DATA_TABLE_FILE_NAME )
        SAMPLE_SUFFIX = '.sample'
        SAMPLE_SUFFIX_OFFSET = -len( SAMPLE_SUFFIX )
        target_dir, agent_path, relative_target_dir = self.get_target_install_dir( agent_shed_repository )
        for sample_file in agent_index_sample_files:
            path, filename = os.path.split( sample_file )
            target_filename = filename
            if target_filename.endswith( SAMPLE_SUFFIX ):
                target_filename = target_filename[ : SAMPLE_SUFFIX_OFFSET ]
            source_file = os.path.join( agent_path, sample_file )
            # We're not currently uninstalling index files, do not overwrite existing files.
            target_path_filename = os.path.join( target_dir, target_filename )
            if not os.path.exists( target_path_filename ) or target_filename == TOOL_DATA_TABLE_FILE_NAME:
                shutil.copy2( source_file, target_path_filename )
            else:
                log.debug( "Did not copy sample file '%s' to install directory '%s' because file already exists.", filename, target_dir )
            # For provenance and to simplify introspection, let's keep the original data table sample file around.
            if filename == TOOL_DATA_TABLE_FILE_SAMPLE_NAME:
                shutil.copy2( source_file, os.path.join( target_dir, filename ) )
        agent_data_table_conf_filename = os.path.join( target_dir, TOOL_DATA_TABLE_FILE_NAME )
        elems = []
        if os.path.exists( agent_data_table_conf_filename ):
            tree, error_message = xml_util.parse_xml( agent_data_table_conf_filename )
            if tree:
                for elem in tree.getroot():
                    # Append individual table elems or other elemes, but not tables elems.
                    if elem.tag == 'tables':
                        for table_elem in elems:
                            elems.append( elem )
                    else:
                        elems.append( elem )
        else:
            log.debug( "The '%s' data table file was not found, but was expected to be copied from '%s' during repository installation.",
                       agent_data_table_conf_filename, TOOL_DATA_TABLE_FILE_SAMPLE_NAME )
        for elem in elems:
            if elem.tag == 'table':
                for file_elem in elem.findall( 'file' ):
                    path = file_elem.get( 'path', None )
                    if path:
                        file_elem.set( 'path', os.path.normpath( os.path.join( target_dir, os.path.split( path )[1] ) ) )
                # Store repository info in the table tag set for trace-ability.
                self.generate_repository_info_elem_from_repository( agent_shed_repository, parent_elem=elem )
        if elems:
            # Remove old data_table
            os.unlink( agent_data_table_conf_filename )
            # Persist new data_table content.
            self.app.agent_data_tables.to_xml_file( agent_data_table_conf_filename, elems )
        return agent_data_table_conf_filename, elems

    def reset_agent_data_tables( self ):
        # Reset the agent_data_tables to an empty dictionary.
        self.app.agent_data_tables.data_tables = {}
