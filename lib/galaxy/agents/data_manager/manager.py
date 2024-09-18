import errno
import json
import os

from galaxy import util
from galaxy.util.odict import odict
from galaxy.util.template import fill_template
from galaxy.agents.data import TabularAgentDataTable
from agent_shed.util import common_util
import agent_shed.util.shed_util_common as suc
import galaxy.queue_worker

# set up logger
import logging
log = logging.getLogger( __name__ )

SUPPORTED_DATA_TABLE_TYPES = ( TabularAgentDataTable )
VALUE_TRANSLATION_FUNCTIONS = dict( abspath=os.path.abspath )
DEFAULT_VALUE_TRANSLATION_TYPE = 'template'


class DataManagers( object ):
    def __init__( self, app, xml_filename=None ):
        self.app = app
        self.data_managers = odict()
        self.managed_data_tables = odict()
        self.agent_path = None
        self.filename = xml_filename or self.app.config.data_manager_config_file
        for filename in util.listify( self.filename ):
            if not filename:
                continue
            self.load_from_xml( filename )
        if self.app.config.shed_data_manager_config_file:
            self.load_from_xml( self.app.config.shed_data_manager_config_file, store_agent_path=False, replace_existing=True )

    def load_from_xml( self, xml_filename, store_agent_path=True, replace_existing=False ):
        try:
            tree = util.parse_xml( xml_filename )
        except Exception, e:
            log.error( 'There was an error parsing your Data Manager config file "%s": %s' % ( xml_filename, e ) )
            return  # we are not able to load any data managers
        root = tree.getroot()
        if root.tag != 'data_managers':
            log.error( 'A data managers configuration must have a "data_managers" tag as the root. "%s" is present' % ( root.tag ) )
            return
        if store_agent_path:
            agent_path = root.get( 'agent_path', None )
            if agent_path is None:
                agent_path = self.app.config.agent_path
            if not agent_path:
                agent_path = '.'
            self.agent_path = agent_path
        for data_manager_elem in root.findall( 'data_manager' ):
            self.load_manager_from_elem( data_manager_elem, replace_existing=replace_existing )

    def load_manager_from_elem( self, data_manager_elem, agent_path=None, add_manager=True, replace_existing=False ):
        try:
            data_manager = DataManager( self, data_manager_elem, agent_path=agent_path )
        except Exception, e:
            log.error( "Error loading data_manager '%s':\n%s" % ( e, util.xml_to_string( data_manager_elem ) ) )
            return None
        if add_manager:
            self.add_manager( data_manager, replace_existing=replace_existing )
        log.debug( 'Loaded Data Manager: %s' % ( data_manager.id ) )
        return data_manager

    def add_manager( self, data_manager, replace_existing=False ):
        if not replace_existing:
            assert data_manager.id not in self.data_managers, "A data manager has been defined twice: %s" % ( data_manager.id )
        elif data_manager.id in self.data_managers:
            # Data Manager already exists, remove first one and replace with new one
            log.warning( "A data manager has been defined twice and will be replaced with the last loaded version: %s" % ( data_manager.id ) )
            self.remove_manager( data_manager.id  )
        self.data_managers[ data_manager.id ] = data_manager
        for data_table_name in data_manager.data_tables.keys():
            if data_table_name not in self.managed_data_tables:
                self.managed_data_tables[ data_table_name ] = []
            self.managed_data_tables[ data_table_name ].append( data_manager )

    def get_manager( self, *args, **kwds ):
        return self.data_managers.get( *args, **kwds )

    def remove_manager( self, manager_ids ):
        if not isinstance( manager_ids, list ):
            manager_ids = [ manager_ids ]
        for manager_id in manager_ids:
            data_manager = self.get_manager( manager_id, None )
            if data_manager is not None:
                del self.data_managers[ manager_id ]
                # remove agent from agentbox
                if data_manager.agent:
                    self.app.agentbox.remove_agent_by_id( data_manager.agent.id )
                # determine if any data_tables are no longer tracked
                for data_table_name in data_manager.data_tables.keys():
                    remove_data_table_tracking = True
                    for other_data_manager in self.data_managers.itervalues():
                        if data_table_name in other_data_manager.data_tables:
                            remove_data_table_tracking = False
                            break
                    if remove_data_table_tracking and data_table_name in self.managed_data_tables:
                        del self.managed_data_tables[ data_table_name ]


class DataManager( object ):
    GUID_TYPE = 'data_manager'
    DEFAULT_VERSION = "0.0.1"

    def __init__( self, data_managers, elem=None, agent_path=None ):
        self.data_managers = data_managers
        self.declared_id = None
        self.name = None
        self.description = None
        self.version = self.DEFAULT_VERSION
        self.guid = None
        self.agent = None
        self.data_tables = odict()
        self.output_ref_by_data_table = {}
        self.move_by_data_table_column = {}
        self.value_translation_by_data_table_column = {}
        self.agent_shed_repository_info_dict = None
        self.undeclared_tables = False
        if elem is not None:
            self.load_from_element( elem, agent_path or self.data_managers.agent_path )

    def load_from_element( self, elem, agent_path ):
        assert elem.tag == 'data_manager', 'A data manager configuration must have a "data_manager" tag as the root. "%s" is present' % ( elem.tag )
        self.declared_id = elem.get( 'id', None )
        self.guid = elem.get( 'guid', None )
        path = elem.get( 'agent_file', None )
        self.version = elem.get( 'version', self.version )
        agent_shed_repository_id = None
        agent_guid = None
        if path is None:
            agent_elem = elem.find( 'agent' )
            assert agent_elem is not None, "Error loading agent for data manager. Make sure that a agent_file attribute or a agent tag set has been defined:\n%s" % ( util.xml_to_string( elem ) )
            path = agent_elem.get( "file", None )
            agent_guid = agent_elem.get( "guid", None )
            # need to determine repository info so that dependencies will work correctly
            agent_shed_url = agent_elem.find( 'agent_shed' ).text
            # Handle protocol changes.
            agent_shed_url = common_util.get_agent_shed_url_from_agent_shed_registry( self.data_managers.app, agent_shed_url )
            # The protocol is not stored in the database.
            agent_shed = common_util.remove_protocol_from_agent_shed_url( agent_shed_url )
            repository_name = agent_elem.find( 'repository_name' ).text
            repository_owner = agent_elem.find( 'repository_owner' ).text
            installed_changeset_revision = agent_elem.find( 'installed_changeset_revision' ).text
            self.agent_shed_repository_info_dict = dict( agent_shed=agent_shed,
                                                        name=repository_name,
                                                        owner=repository_owner,
                                                        installed_changeset_revision=installed_changeset_revision )
            agent_shed_repository = \
                suc.get_installed_repository( self.data_managers.app,
                                              agent_shed=agent_shed,
                                              name=repository_name,
                                              owner=repository_owner,
                                              installed_changeset_revision=installed_changeset_revision )
            if agent_shed_repository is None:
                log.warning( 'Could not determine agent shed repository from database. This should only ever happen when running tests.' )
                # we'll set agent_path manually here from shed_conf_file
                agent_shed_repository_id = None
                try:
                    agent_path = util.parse_xml( elem.get( 'shed_conf_file' ) ).getroot().get( 'agent_path', agent_path )
                except Exception, e:
                    log.error( 'Error determining agent_path for Data Manager during testing: %s', e )
            else:
                agent_shed_repository_id = self.data_managers.app.security.encode_id( agent_shed_repository.id )
            # use shed_conf_file to determine agent_path
            shed_conf_file = elem.get( "shed_conf_file", None )
            if shed_conf_file:
                shed_conf = self.data_managers.app.agentbox.get_shed_config_dict_by_filename( shed_conf_file, None )
                if shed_conf:
                    agent_path = shed_conf.get( "agent_path", agent_path )
        assert path is not None, "A agent file path could not be determined:\n%s" % ( util.xml_to_string( elem ) )
        self.load_agent( os.path.join( agent_path, path ),
                        guid=agent_guid,
                        data_manager_id=self.id,
                        agent_shed_repository_id=agent_shed_repository_id )
        self.name = elem.get( 'name', self.agent.name )
        self.description = elem.get( 'description', self.agent.description )
        self.undeclared_tables = util.asbool( elem.get( 'undeclared_tables', self.undeclared_tables ) )

        for data_table_elem in elem.findall( 'data_table' ):
            data_table_name = data_table_elem.get( "name" )
            assert data_table_name is not None, "A name is required for a data table entry"
            if data_table_name not in self.data_tables:
                self.data_tables[ data_table_name ] = odict()
            output_elem = data_table_elem.find( 'output' )
            if output_elem is not None:
                for column_elem in output_elem.findall( 'column' ):
                    column_name = column_elem.get( 'name', None )
                    assert column_name is not None, "Name is required for column entry"
                    data_table_coumn_name = column_elem.get( 'data_table_name', column_name )
                    self.data_tables[ data_table_name ][ data_table_coumn_name ] = column_name
                    output_ref = column_elem.get( 'output_ref', None )
                    if output_ref is not None:
                        if data_table_name not in self.output_ref_by_data_table:
                            self.output_ref_by_data_table[ data_table_name ] = {}
                        self.output_ref_by_data_table[ data_table_name ][ data_table_coumn_name ] = output_ref
                    value_translation_elems = column_elem.findall( 'value_translation' )
                    if value_translation_elems is not None:
                        for value_translation_elem in value_translation_elems:
                            value_translation = value_translation_elem.text
                            if value_translation is not None:
                                value_translation_type = value_translation_elem.get( 'type', DEFAULT_VALUE_TRANSLATION_TYPE )
                                if data_table_name not in self.value_translation_by_data_table_column:
                                    self.value_translation_by_data_table_column[ data_table_name ] = {}
                                if data_table_coumn_name not in self.value_translation_by_data_table_column[ data_table_name ]:
                                    self.value_translation_by_data_table_column[ data_table_name ][ data_table_coumn_name ] = []
                                if value_translation_type == 'function':
                                    if value_translation in VALUE_TRANSLATION_FUNCTIONS:
                                        value_translation = VALUE_TRANSLATION_FUNCTIONS[ value_translation ]
                                    else:
                                        raise ValueError( "Unsupported value translation function: '%s'" % ( value_translation ) )
                                else:
                                    assert value_translation_type == DEFAULT_VALUE_TRANSLATION_TYPE, ValueError( "Unsupported value translation type: '%s'" % ( value_translation_type ) )
                                self.value_translation_by_data_table_column[ data_table_name ][ data_table_coumn_name ].append( value_translation )

                    for move_elem in column_elem.findall( 'move' ):
                        move_type = move_elem.get( 'type', 'directory' )
                        relativize_symlinks = move_elem.get( 'relativize_symlinks', False )  # TODO: should we instead always relativize links?
                        source_elem = move_elem.find( 'source' )
                        if source_elem is None:
                            source_base = None
                            source_value = ''
                        else:
                            source_base = source_elem.get( 'base', None )
                            source_value = source_elem.text
                        target_elem = move_elem.find( 'target' )
                        if target_elem is None:
                            target_base = None
                            target_value = ''
                        else:
                            target_base = target_elem.get( 'base', None )
                            target_value = target_elem.text
                        if data_table_name not in self.move_by_data_table_column:
                            self.move_by_data_table_column[ data_table_name ] = {}
                        self.move_by_data_table_column[ data_table_name ][ data_table_coumn_name ] = \
                            dict( type=move_type,
                                  source_base=source_base,
                                  source_value=source_value,
                                  target_base=target_base,
                                  target_value=target_value,
                                  relativize_symlinks=relativize_symlinks )

    @property
    def id( self ):
        return self.guid or self.declared_id  # if we have a guid, we will use that as the data_manager id

    def load_agent( self, agent_filename, guid=None, data_manager_id=None, agent_shed_repository_id=None ):
        agentbox = self.data_managers.app.agentbox
        agent = agentbox.load_hidden_agent( agent_filename,
                                         guid=guid,
                                         data_manager_id=data_manager_id,
                                         repository_id=agent_shed_repository_id )
        self.data_managers.app.agentbox.data_manager_agents[ agent.id ] = agent
        self.agent = agent
        return agent

    def process_result( self, out_data ):
        data_manager_dicts = {}
        data_manager_dict = {}
        # TODO: fix this merging below
        for output_name, output_dataset in out_data.iteritems():
            try:
                output_dict = json.loads( open( output_dataset.file_name ).read() )
            except Exception, e:
                log.warning( 'Error reading DataManagerAgent json for "%s": %s' % ( output_name, e ) )
                continue
            data_manager_dicts[ output_name ] = output_dict
            for key, value in output_dict.iteritems():
                if key not in data_manager_dict:
                    data_manager_dict[ key ] = {}
                data_manager_dict[ key ].update( value )
            data_manager_dict.update( output_dict )

        data_tables_dict = data_manager_dict.get( 'data_tables', {} )
        for data_table_name in self.data_tables.iterkeys():
            data_table_values = data_tables_dict.pop( data_table_name, None )
            if not data_table_values:
                log.warning( 'No values for data table "%s" were returned by the data manager "%s".' % ( data_table_name, self.id ) )
                continue  # next data table
            data_table = self.data_managers.app.agent_data_tables.get( data_table_name, None )
            if data_table is None:
                log.error( 'The data manager "%s" returned an unknown data table "%s" with new entries "%s". These entries will not be created. Please confirm that an entry for "%s" exists in your "%s" file.' % ( self.id, data_table_name, data_table_values, data_table_name, 'agent_data_table_conf.xml' ) )
                continue  # next table name
            if not isinstance( data_table, SUPPORTED_DATA_TABLE_TYPES ):
                log.error( 'The data manager "%s" returned an unsupported data table "%s" with type "%s" with new entries "%s". These entries will not be created. Please confirm that the data table is of a supported type (%s).' % ( self.id, data_table_name, type( data_table ), data_table_values, SUPPORTED_DATA_TABLE_TYPES ) )
                continue  # next table name
            output_ref_values = {}
            if data_table_name in self.output_ref_by_data_table:
                for data_table_column, output_ref in self.output_ref_by_data_table[ data_table_name ].iteritems():
                    output_ref_dataset = out_data.get( output_ref, None )
                    assert output_ref_dataset is not None, "Referenced output was not found."
                    output_ref_values[ data_table_column ] = output_ref_dataset

            if not isinstance( data_table_values, list ):
                data_table_values = [ data_table_values ]
            for data_table_row in data_table_values:
                data_table_value = dict( **data_table_row )  # keep original values here
                for name, value in data_table_row.iteritems():  # FIXME: need to loop through here based upon order listed in data_manager config
                    if name in output_ref_values:
                        self.process_move( data_table_name, name, output_ref_values[ name ].extra_files_path, **data_table_value )
                        data_table_value[ name ] = self.process_value_translation( data_table_name, name, **data_table_value )
                data_table.add_entry( data_table_value, persist=True, entry_source=self )
                galaxy.queue_worker.send_control_task(self.data_managers.app, 'reload_agent_data_tables',
                                                      noop_self=True,
                                                      kwargs={'table_name': data_table_name} )
        if self.undeclared_tables and data_tables_dict:
            # We handle the data move, by just moving all the data out of the extra files path
            # moving a directory and the target already exists, we move the contents instead
            log.debug( 'Attempting to add entries for undeclared tables: %s.', ', '.join( data_tables_dict.keys() ) )
            for ref_file in out_data.values():
                util.move_merge( ref_file.extra_files_path, self.data_managers.app.config.galaxy_data_manager_data_path )
            path_column_names = [ 'path' ]
            for data_table_name, data_table_values in data_tables_dict.iteritems():
                data_table = self.data_managers.app.agent_data_tables.get( data_table_name, None )
                if not isinstance( data_table_values, list ):
                    data_table_values = [ data_table_values ]
                for data_table_row in data_table_values:
                    data_table_value = dict( **data_table_row )  # keep original values here
                    for name, value in data_table_row.iteritems():
                        if name in path_column_names:
                            data_table_value[ name ] = os.path.abspath( os.path.join( self.data_managers.app.config.galaxy_data_manager_data_path, value ) )
                    data_table.add_entry( data_table_value, persist=True, entry_source=self )
                    galaxy.queue_worker.send_control_task(self.data_managers.app, 'reload_agent_data_tables',
                                                          noop_self=True,
                                                          kwargs={'table_name': data_table_name} )
        else:
            for data_table_name, data_table_values in data_tables_dict.iteritems():
                # agent returned extra data table entries, but data table was not declared in data manager
                # do not add these values, but do provide messages
                log.warning( 'The data manager "%s" returned an undeclared data table "%s" with new entries "%s". These entries will not be created. Please confirm that an entry for "%s" exists in your "%s" file.' % ( self.id, data_table_name, data_table_values, data_table_name, self.data_managers.filename ) )

    def process_move( self, data_table_name, column_name, source_base_path, relative_symlinks=False, **kwd ):
        if data_table_name in self.move_by_data_table_column and column_name in self.move_by_data_table_column[ data_table_name ]:
            move_dict = self.move_by_data_table_column[ data_table_name ][ column_name ]
            source = move_dict[ 'source_base' ]
            if source is None:
                source = source_base_path
            else:
                source = fill_template( source, GALAXY_DATA_MANAGER_DATA_PATH=self.data_managers.app.config.galaxy_data_manager_data_path, **kwd )
            if move_dict[ 'source_value' ]:
                source = os.path.join( source, fill_template( move_dict[ 'source_value' ], GALAXY_DATA_MANAGER_DATA_PATH=self.data_managers.app.config.galaxy_data_manager_data_path, **kwd )  )
            target = move_dict[ 'target_base' ]
            if target is None:
                target = self.data_managers.app.config.galaxy_data_manager_data_path
            else:
                target = fill_template( target, GALAXY_DATA_MANAGER_DATA_PATH=self.data_managers.app.config.galaxy_data_manager_data_path, **kwd )
            if move_dict[ 'target_value' ]:
                target = os.path.join( target, fill_template( move_dict[ 'target_value' ], GALAXY_DATA_MANAGER_DATA_PATH=self.data_managers.app.config.galaxy_data_manager_data_path, **kwd  ) )

            if move_dict[ 'type' ] == 'file':
                dirs = os.path.split( target )[0]
                try:
                    os.makedirs( dirs )
                except OSError, e:
                    if e.errno != errno.EEXIST:
                        raise e
            # moving a directory and the target already exists, we move the contents instead
            util.move_merge( source, target )

            if move_dict.get( 'relativize_symlinks', False ):
                util.relativize_symlinks( target )

            return True
        return False

    def process_value_translation( self, data_table_name, column_name, **kwd ):
        value = kwd.get( column_name )
        if data_table_name in self.value_translation_by_data_table_column and column_name in self.value_translation_by_data_table_column[ data_table_name ]:
            for value_translation in self.value_translation_by_data_table_column[ data_table_name ][ column_name ]:
                if isinstance( value_translation, basestring ):
                    value = fill_template( value_translation, GALAXY_DATA_MANAGER_DATA_PATH=self.data_managers.app.config.galaxy_data_manager_data_path, **kwd  )
                else:
                    value = value_translation( value )
        return value

    def get_agent_shed_repository_info_dict( self ):
        return self.agent_shed_repository_info_dict
