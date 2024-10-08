# Contains objects for using external display applications
import logging
import urllib
from galaxy.util import parse_xml, string_as_bool
from galaxy.util.odict import odict
from galaxy.util.template import fill_template
from galaxy.web import url_for
from parameters import DisplayApplicationParameter, DisplayApplicationDataParameter, DEFAULT_DATASET_NAME
from urllib import quote_plus
from util import encode_dataset_user
from copy import deepcopy

log = logging.getLogger( __name__ )

# Any basic functions that we want to provide as a basic part of parameter dict should be added to this dict
BASE_PARAMS = { 'qp': quote_plus, 'url_for': url_for }


class DisplayApplicationLink( object ):
    @classmethod
    def from_elem( cls, elem, display_application, other_values=None ):
        rval = DisplayApplicationLink( display_application )
        rval.id = elem.get( 'id', None )
        assert rval.id, 'Link elements require a id.'
        rval.name = elem.get( 'name', rval.id )
        rval.url = elem.find( 'url' )
        assert rval.url is not None, 'A url element must be provided for link elements.'
        rval.other_values = other_values
        rval.filters = elem.findall( 'filter' )
        for param_elem in elem.findall( 'param' ):
            param = DisplayApplicationParameter.from_elem( param_elem, rval )
            assert param, 'Unable to load parameter from element: %s' % param_elem
            rval.parameters[ param.name ] = param
            rval.url_param_name_map[ param.url ] = param.name
        return rval

    def __init__( self, display_application ):
        self.display_application = display_application
        self.parameters = odict()  # parameters are populated in order, allowing lower listed ones to have values of higher listed ones
        self.url_param_name_map = {}
        self.url = None
        self.id = None
        self.name = None

    def get_display_url( self, data, trans ):
        dataset_hash, user_hash = encode_dataset_user( trans, data, None )
        return url_for( controller='dataset',
                        action="display_application",
                        dataset_id=dataset_hash,
                        user_id=user_hash,
                        app_name=urllib.quote_plus( self.display_application.id ),
                        link_name=urllib.quote_plus( self.id ),
                        app_action=None )

    def get_inital_values( self, data, trans ):
        if self.other_values:
            rval = odict( self.other_values )
        else:
            rval = odict()
        rval.update( { 'BASE_URL': trans.request.base, 'APP': trans.app } )  # trans automatically appears as a response, need to add properties of trans that we want here
        for key, value in BASE_PARAMS.iteritems():  # add helper functions/variables
            rval[ key ] = value
        rval[ DEFAULT_DATASET_NAME ] = data  # always have the display dataset name available
        return rval

    def build_parameter_dict( self, data, dataset_hash, user_hash, trans, app_kwds ):
        other_values = self.get_inital_values( data, trans )
        other_values[ 'DATASET_HASH' ] = dataset_hash
        other_values[ 'USER_HASH' ] = user_hash
        ready = True
        for name, param in self.parameters.iteritems():
            assert name not in other_values, "The display parameter '%s' has been defined more than once." % name
            if param.ready( other_values ):
                if name in app_kwds and param.allow_override:
                    other_values[ name ] = app_kwds[ name ]
                else:
                    other_values[ name ] = param.get_value( other_values, dataset_hash, user_hash, trans )  # subsequent params can rely on this value
            else:
                ready = False
                other_values[ name ] = param.get_value( other_values, dataset_hash, user_hash, trans )  # subsequent params can rely on this value
                if other_values[ name ] is None:
                    # Need to stop here, next params may need this value to determine its own value
                    return False, other_values
        return ready, other_values

    def filter_by_dataset( self, data, trans ):
        context = self.get_inital_values( data, trans )
        for filter_elem in self.filters:
            if fill_template( filter_elem.text, context=context ) != filter_elem.get( 'value', 'True' ):
                return False
        return True


class DynamicDisplayApplicationBuilder( object ):

    def __init__( self, elem, display_application, build_sites ):
        filename = None
        data_table = None
        if elem.get( 'site_type', None ) is not None:
            filename = build_sites.get( elem.get( 'site_type' ) )
        else:
            filename = elem.get( 'from_file', None )
        if filename is None:
            data_table_name = elem.get( 'from_data_table', None )
            if data_table_name:
                data_table = display_application.app.agent_data_tables.get( data_table_name, None )
                assert data_table is not None, 'Unable to find data table named "%s".' % data_table_name

        assert filename is not None or data_table is not None, 'Filename or data Table is required for dynamic_links.'
        skip_startswith = elem.get( 'skip_startswith', None )
        separator = elem.get( 'separator', '\t' )
        id_col = elem.get( 'id', None )
        try:
            id_col = int( id_col )
        except:
            if data_table:
                if id_col is None:
                    id_col = data_table.columns.get( 'id', None )
                if id_col is None:
                    id_col = data_table.columns.get( 'value', None )
                try:
                    id_col = int( id_col )
                except:
                    # id is set to a string or None, use column by that name if available
                    id_col = data_table.columns.get( id_col, None )
                    id_col = int( id_col )
        name_col = elem.get( 'name', None )
        try:
            name_col = int( name_col )
        except:
            if data_table:
                if name_col is None:
                    name_col = data_table.columns.get( 'name', None )
                else:
                    name_col = data_table.columns.get( name_col, None )
            else:
                name_col = None
        if name_col is None:
            name_col = id_col
        max_col = max( id_col, name_col )
        dynamic_params = {}
        if data_table is not None:
            max_col = max(  [ max_col ] + data_table.columns.values() )
            for key, value in data_table.columns.items():
                dynamic_params[key] = { 'column': value, 'split': False, 'separator': ',' }
        for dynamic_param in elem.findall( 'dynamic_param' ):
            name = dynamic_param.get( 'name' )
            value = int( dynamic_param.get( 'value' ) )
            split = string_as_bool( dynamic_param.get( 'split', False ) )
            param_separator = dynamic_param.get( 'separator', ',' )
            max_col = max( max_col, value )
            dynamic_params[name] = { 'column': value, 'split': split, 'separator': param_separator }
        if filename:
            data_iter = open( filename )
        elif data_table:
            version, data_iter = data_table.get_version_fields()
            display_application.add_data_table_watch( data_table.name, version )
        links = []
        for line in data_iter:
            if isinstance( line, basestring ):
                if not skip_startswith or not line.startswith( skip_startswith ):
                    line = line.rstrip( '\n\r' )
                    if not line:
                        continue
                    fields = line.split( separator )
                else:
                    continue
            else:
                fields = line
            if len( fields ) > max_col:
                new_elem = deepcopy( elem )
                new_elem.set( 'id', fields[id_col] )
                new_elem.set( 'name', fields[name_col] )
                dynamic_values = {}
                for key, attributes in dynamic_params.iteritems():
                    value = fields[ attributes[ 'column' ] ]
                    if attributes['split']:
                        value = value.split( attributes['separator'] )
                    dynamic_values[key] = value
                # now populate
                links.append( DisplayApplicationLink.from_elem( new_elem, display_application, other_values=dynamic_values ) )
            else:
                log.warning( 'Invalid dynamic display application link specified in %s: "%s"' % ( filename, line ) )
        self.links = links

    def __iter__( self ):
        return iter( self.links )


class PopulatedDisplayApplicationLink( object ):
    def __init__( self, display_application_link, data, dataset_hash, user_hash, trans, app_kwds ):
        self.link = display_application_link
        self.data = data
        self.dataset_hash = dataset_hash
        self.user_hash = user_hash
        self.trans = trans
        self.ready, self.parameters = self.link.build_parameter_dict( self.data, self.dataset_hash, self.user_hash, trans, app_kwds )

    def display_ready( self ):
        return self.ready

    def get_param_value( self, name ):
        value = None
        if self.ready:
            value = self.parameters.get( name, None )
            assert value, 'Unknown parameter requested'
        return value

    def preparing_display( self ):
        if not self.ready:
            return self.link.parameters[ self.parameters.keys()[ -1 ] ].is_preparing( self.parameters )
        return False

    def prepare_display( self ):
        rval = []
        found_last = False
        if not self.ready and not self.preparing_display():
            other_values = self.parameters
            for name, param in self.link.parameters.iteritems():
                if found_last or other_values.keys()[ -1 ] == name:  # found last parameter to be populated
                    found_last = True
                    value = param.prepare( other_values, self.dataset_hash, self.user_hash, self.trans )
                    rval.append( { 'name': name, 'value': value, 'param': param } )
                    other_values[ name ] = value
                    if value is None:
                        # We can go no further until we have a value for this parameter
                        return rval
        return rval

    def get_prepare_steps( self, datasets_only=True ):
        rval = []
        for name, param in self.link.parameters.iteritems():
            if datasets_only and not isinstance( param, DisplayApplicationDataParameter ):
                continue
            value = self.parameters.get( name, None )
            rval.append( { 'name': name, 'value': value, 'param': param, 'ready': param.ready( self.parameters ) } )
        return rval

    def display_url( self ):
        assert self.display_ready(), 'Display is not yet ready, cannot generate display link'
        return fill_template( self.link.url.text, context=self.parameters )

    def get_param_name_by_url( self, url ):
        for name, parameter in self.link.parameters.iteritems():
            if parameter.build_url( self.parameters ) == url:
                return name
        raise ValueError( "Unknown URL parameter name provided: %s" % url )


class DisplayApplication( object ):
    @classmethod
    def from_file( cls, filename, app ):
        return cls.from_elem( parse_xml( filename ).getroot(), app, filename=filename )

    @classmethod
    def from_elem( cls, elem, app, filename=None ):
        att_dict = cls._get_attributes_from_elem( elem )
        rval = DisplayApplication( att_dict['id'], att_dict['name'], app, att_dict['version'], filename=filename, elem=elem )
        rval._load_links_from_elem( elem )
        return rval

    @classmethod
    def _get_attributes_from_elem( cls, elem ):
        display_id = elem.get( 'id', None )
        assert display_id, "ID tag is required for a Display Application"
        name = elem.get( 'name', display_id )
        version = elem.get( 'version', None )
        return dict( id=display_id, name=name, version=version )

    def __init__( self, display_id, name, app, version=None, filename=None, elem=None ):
        self.id = display_id
        self.name = name
        self.app = app
        if version is None:
            version = "1.0.0"
        self.version = version
        self.links = odict()
        self._filename = filename
        self._elem = elem
        self._data_table_versions = {}

    def _load_links_from_elem( self, elem ):
        for link_elem in elem.findall( 'link' ):
            link = DisplayApplicationLink.from_elem( link_elem, self )
            if link:
                self.links[ link.id ] = link
        try:
            for dynamic_links in elem.findall( 'dynamic_links' ):
                for link in DynamicDisplayApplicationBuilder( dynamic_links, self, self.app.datatypes_registry.build_sites ):
                    self.links[ link.id ] = link
        except Exception as e:
            log.error( "Error loading a set of Dynamic Display Application links: %s", e )

    def get_link( self, link_name, data, dataset_hash, user_hash, trans, app_kwds ):
        # returns a link object with data knowledge to generate links
        self._check_and_reload()
        return PopulatedDisplayApplicationLink( self.links[ link_name ], data, dataset_hash, user_hash, trans, app_kwds )

    def filter_by_dataset( self, data, trans ):
        self._check_and_reload()
        filtered = DisplayApplication( self.id, self.name, self.app, version=self.version )
        for link_name, link_value in self.links.iteritems():
            if link_value.filter_by_dataset( data, trans ):
                filtered.links[link_name] = link_value
        return filtered

    def reload( self ):
        if self._filename:
            elem = parse_xml( self._filename ).getroot()
        elif self._elem:
            elem = self._elem
        else:
            raise Exception( "Unable to reload DisplayApplication %s." % ( self.name ) )
        # All agentshed-specific attributes added by e.g the registry will remain
        attr_dict = self._get_attributes_from_elem( elem )
        # We will not allow changing the id at this time (we'll need to fix several mappings upstream to handle this case)
        assert attr_dict.get( 'id' ) == self.id, ValueError( "You cannot reload a Display application where the ID has changed. You will need to restart the server instead." )
        # clear old links
        for key in self.links.keys():
            del self.links[key]
        # clear data table versions:
        for key in self._data_table_versions.keys():
            del self._data_table_versions[ key ]
        # Set new attributes
        for key, value in attr_dict.iteritems():
            setattr( self, key, value )
        # Load new links
        self._load_links_from_elem( elem )
        return self

    def add_data_table_watch( self, table_name, version=None ):
        self._data_table_versions[ table_name ] = version

    def _requires_reload( self ):
        for key, value in self._data_table_versions.iteritems():
            table = self.app.agent_data_tables.get( key, None )
            if table and not table.is_current_version( value ):
                return True
        return False

    def _check_and_reload( self ):
        if self._requires_reload():
            self.reload()
