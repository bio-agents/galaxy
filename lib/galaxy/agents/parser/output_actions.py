"""
Support for dynamically modifying output attributes.
"""

import logging
import os.path
import string
import re
from galaxy import util

log = logging.getLogger( __name__ )

# Attributes agent developer may want to query on dataset collections.
COLLECTION_ATTRIBUTES = [ "collection_type" ]


class AgentOutputActionGroup( object ):
    """
    Manages a set of agent output dataset actions directives
    """
    tag = "group"

    def __init__( self, parent, config_elem ):
        self.parent = parent
        self.actions = []
        if config_elem is not None:
            for elem in config_elem:
                if elem.tag == "conditional":
                    self.actions.append( AgentOutputActionConditional( self, elem ) )
                elif elem.tag == "action":
                    self.actions.append( AgentOutputAction.from_elem( self, elem ) )
                else:
                    log.debug( "Unknown AgentOutputAction tag specified: %s" % elem.tag )

    def apply_action( self, output_dataset, other_values ):
        for action in self.actions:
            action.apply_action( output_dataset, other_values )

    @property
    def agent( self ):
        return self.parent.agent

    def __len__( self ):
        return len( self.actions )


class AgentOutputActionConditionalWhen( AgentOutputActionGroup ):
    tag = "when"

    @classmethod
    def from_elem( cls, parent, when_elem ):
        """Loads the proper when by attributes of elem"""
        when_value = when_elem.get( "value", None )
        if when_value is not None:
            return ValueAgentOutputActionConditionalWhen( parent, when_elem, when_value )
        else:
            when_value = when_elem.get( "datatype_isinstance", None )
            if when_value is not None:
                return DatatypeIsInstanceAgentOutputActionConditionalWhen( parent, when_elem, when_value )
        raise TypeError( "When type not implemented" )

    def __init__( self, parent, config_elem, value ):
        super( AgentOutputActionConditionalWhen, self ).__init__( parent, config_elem )
        self.value = value

    def is_case( self, output_dataset, other_values ):
        raise TypeError( "Not implemented" )

    def get_ref( self, output_dataset, other_values ):
        ref = other_values
        for ref_name in self.parent.name:
            assert ref_name in ref, "Required dependency '%s' not found in incoming values" % ref_name
            ref = ref.get( ref_name )
        return ref

    def apply_action( self, output_dataset, other_values ):
        if self.is_case( output_dataset, other_values ):
            return super( AgentOutputActionConditionalWhen, self ).apply_action( output_dataset, other_values )


class ValueAgentOutputActionConditionalWhen( AgentOutputActionConditionalWhen ):
    tag = "when value"

    def is_case( self, output_dataset, other_values ):
        ref = self.get_ref( output_dataset, other_values )
        return bool( str( ref ) == self.value )


class DatatypeIsInstanceAgentOutputActionConditionalWhen( AgentOutputActionConditionalWhen ):
    tag = "when datatype_isinstance"

    def __init__( self, parent, config_elem, value ):
        super( DatatypeIsInstanceAgentOutputActionConditionalWhen, self ).__init__( parent, config_elem, value )
        self.value = type( self.agent.app.datatypes_registry.get_datatype_by_extension( value ) )

    def is_case( self, output_dataset, other_values ):
        ref = self.get_ref( output_dataset, other_values )
        return isinstance( ref.datatype, self.value )


class AgentOutputActionConditional( object ):
    tag = "conditional"

    def __init__( self, parent, config_elem ):
        self.parent = parent
        self.name = config_elem.get( 'name', None )
        assert self.name is not None, "Required 'name' attribute missing from AgentOutputActionConditional"
        self.name = self.name.split( '.' )
        self.cases = []
        for when_elem in config_elem.findall( 'when' ):
            self.cases.append( AgentOutputActionConditionalWhen.from_elem( self, when_elem ) )

    def apply_action( self, output_dataset, other_values ):
        for case in self.cases:
            case.apply_action( output_dataset, other_values )

    @property
    def agent( self ):
        return self.parent.agent


class AgentOutputAction( object ):
    tag = "action"

    @classmethod
    def from_elem( cls, parent, elem ):
        """Loads the proper action by the type attribute of elem"""
        action_type = elem.get( 'type', None )
        assert action_type is not None, "Required 'type' attribute missing from AgentOutputAction"
        return action_types[ action_type ]( parent, elem )

    def __init__( self, parent, elem ):
        self.parent = parent
        self.default = elem.get( 'default', None )
        option_elem = elem.find( 'option' )
        self.option = AgentOutputActionOption.from_elem( self, option_elem )

    def apply_action( self, output_dataset, other_values ):
        raise TypeError( "Not implemented" )

    @property
    def agent( self ):
        return self.parent.agent


class AgentOutputActionOption( object ):
    tag = "object"

    @classmethod
    def from_elem( cls, parent, elem ):
        """Loads the proper action by the type attribute of elem"""
        if elem is None:
            option_type = NullAgentOutputActionOption.tag  # no AgentOutputActionOption's have been defined, use implicit NullAgentOutputActionOption
        else:
            option_type = elem.get( 'type', None )
        assert option_type is not None, "Required 'type' attribute missing from AgentOutputActionOption"
        return option_types[ option_type ]( parent, elem )

    def __init__( self, parent, elem ):
        self.parent = parent
        self.filters = []
        if elem is not None:
            for filter_elem in elem.findall( 'filter' ):
                self.filters.append( AgentOutputActionOptionFilter.from_elem( self, filter_elem ) )

    def get_value( self, other_values ):
        raise TypeError( "Not implemented" )

    @property
    def agent( self ):
        return self.parent.agent


class NullAgentOutputActionOption( AgentOutputActionOption ):
    tag = "null_option"

    def get_value( self, other_values ):
        return None


class FromFileAgentOutputActionOption( AgentOutputActionOption ):
    tag = "from_file"

    def __init__( self, parent, elem ):
        super( FromFileAgentOutputActionOption, self ).__init__( parent, elem )
        self.name = elem.get( 'name', None )
        assert self.name is not None, "Required 'name' attribute missing from FromFileAgentOutputActionOption"
        self.column = elem.get( 'column', None )
        assert self.column is not None, "Required 'column' attribute missing from FromFileAgentOutputActionOption"
        self.column = int( self.column )
        self.offset = elem.get( 'offset', -1 )
        self.offset = int( self.offset )
        self.separator = elem.get( 'separator', '\t' )
        self.options = []
        data_file = self.name
        if not os.path.isabs( data_file ):
            data_file = os.path.join( self.agent.app.config.agent_data_path, data_file )
        for line in open( data_file ):
            self.options.append( line.rstrip( '\n\r' ).split( self.separator ) )

    def get_value( self, other_values ):
        options = self.options
        for filter in self.filters:
            options = filter.filter_options( options, other_values )
        try:
            if options:
                return str( options[ self.offset ][ self.column ] )
        except Exception as e:
            log.debug( "Error in FromFileAgentOutputActionOption get_value: %s" % e )
        return None


class FromParamAgentOutputActionOption( AgentOutputActionOption ):
    tag = "from_param"

    def __init__( self, parent, elem ):
        super( FromParamAgentOutputActionOption, self ).__init__( parent, elem )
        self.name = elem.get( 'name', None )
        assert self.name is not None, "Required 'name' attribute missing from FromFileAgentOutputActionOption"
        self.name = self.name.split( '.' )
        self.column = elem.get( 'column', 0 )
        self.column = int( self.column )
        self.offset = elem.get( 'offset', -1 )
        self.offset = int( self.offset )
        self.param_attribute = elem.get( 'param_attribute', [] )
        if self.param_attribute:
            self.param_attribute = self.param_attribute.split( '.' )

    def get_value( self, other_values ):
        value = other_values
        for ref_name in self.name:
            assert ref_name in value, "Required dependency '%s' not found in incoming values" % ref_name
            value = value.get( ref_name )
        for attr_name in self.param_attribute:
            # if the value is a list from a repeat tag you can access the first element of the repeat with
            # artifical 'first' attribute_name. For example: .. param_attribute="first.input_mate1.ext"
            if isinstance(value, list) and attr_name == 'first':
                value = value[0]
            elif isinstance(value, dict):
                value = value[ attr_name ]
            elif hasattr( value, "collection" ) and value not in COLLECTION_ATTRIBUTES:
                # if this is an HDCA for instance let reverse.ext grab
                # the reverse element and then continue for loop to grab
                # dataset extension
                value = value.collection[ attr_name ].element_object
            elif hasattr( value, "collection" ) and value in COLLECTION_ATTRIBUTES:
                value = getattr( value.collection, attr_name )
            else:
                value = getattr( value, attr_name )
        options = [ [ str( value ) ] ]
        for filter in self.filters:
            options = filter.filter_options( options, other_values )
        try:
            if options:
                return str( options[ self.offset ][ self.column ] )
        except Exception as e:
            log.debug( "Error in FromParamAgentOutputActionOption get_value: %s" % e )
        return None


class FromDataTableOutputActionOption( AgentOutputActionOption ):
    tag = "from_data_table"

    # TODO: allow accessing by column 'name' not just index
    def __init__( self, parent, elem ):
        super( FromDataTableOutputActionOption, self ).__init__( parent, elem )
        self.name = elem.get( 'name', None )
        assert self.name is not None, "Required 'name' attribute missing from FromDataTableOutputActionOption"
        self.missing_agent_data_table_name = None
        if self.name in self.agent.app.agent_data_tables:
            self.options = self.agent.app.agent_data_tables[ self.name ].get_fields()
            self.column = elem.get( 'column', None )
            assert self.column is not None, "Required 'column' attribute missing from FromDataTableOutputActionOption"
            self.column = int( self.column )
            self.offset = elem.get( 'offset', -1 )
            self.offset = int( self.offset )
        else:
            self.options = []
            self.missing_agent_data_table_name = self.name

    def get_value( self, other_values ):
        if self.options:
            options = self.options
        else:
            options = []
        for filter in self.filters:
            options = filter.filter_options( options, other_values )
        try:
            if options:
                return str( options[ self.offset ][ self.column ] )
        except Exception as e:
            log.debug( "Error in FromDataTableOutputActionOption get_value: %s" % e )
        return None


class MetadataAgentOutputAction( AgentOutputAction ):
    tag = "metadata"

    def __init__( self, parent, elem ):
        super( MetadataAgentOutputAction, self ).__init__( parent, elem )
        self.name = elem.get( 'name', None )
        assert self.name is not None, "Required 'name' attribute missing from MetadataAgentOutputAction"

    def apply_action( self, output_dataset, other_values ):
        value = self.option.get_value( other_values )
        if value is None and self.default is not None:
            value = self.default
        if value is not None:
            setattr( output_dataset.metadata, self.name, value )


class FormatAgentOutputAction( AgentOutputAction ):
    tag = "format"

    def __init__( self, parent, elem ):
        super( FormatAgentOutputAction, self ).__init__( parent, elem )
        self.default = elem.get( 'default', None )

    def apply_action( self, output_dataset, other_values ):
        value = self.option.get_value( other_values )
        if value is None and self.default is not None:
            value = self.default
        if value is not None:
            output_dataset.extension = value


class AgentOutputActionOptionFilter( object ):
    tag = "filter"

    @classmethod
    def from_elem( cls, parent, elem ):
        """Loads the proper action by the type attribute of elem"""
        filter_type = elem.get( 'type', None )
        assert filter_type is not None, "Required 'type' attribute missing from AgentOutputActionOptionFilter"
        return filter_types[ filter_type ]( parent, elem )

    def __init__( self, parent, elem ):
        self.parent = parent

    def filter_options( self, options, other_values ):
        raise TypeError( "Not implemented" )

    @property
    def agent( self ):
        return self.parent.agent


class ParamValueAgentOutputActionOptionFilter( AgentOutputActionOptionFilter ):
    tag = "param_value"

    def __init__( self, parent, elem ):
        super( ParamValueAgentOutputActionOptionFilter, self ).__init__( parent, elem )
        self.ref = elem.get( 'ref', None )
        if self.ref:
            self.ref = self.ref.split( '.' )
        self.value = elem.get( 'value', None )
        assert self.ref != self.value, "Required 'ref' or 'value' attribute missing from ParamValueAgentOutputActionOptionFilter"
        self.column = elem.get( 'column', None )
        assert self.column is not None, "Required 'column' attribute missing from ParamValueAgentOutputActionOptionFilter"
        self.column = int( self.column )
        self.keep = util.string_as_bool( elem.get( "keep", 'True' ) )
        self.compare = parse_compare_type( elem.get( 'compare', None ) )
        self.cast = parse_cast_attribute( elem.get( "cast", None ) )
        self.param_attribute = elem.get( 'param_attribute', [] )
        if self.param_attribute:
            self.param_attribute = self.param_attribute.split( '.' )

    def filter_options( self, options, other_values ):
        if self.ref:
            # find ref value
            value = other_values
            for ref_name in self.ref:
                assert ref_name in value, "Required dependency '%s' not found in incoming values" % ref_name
                value = value.get( ref_name )
            for attr_name in self.param_attribute:
                value = getattr( value, attr_name )
            value = str( value )
        else:
            value = self.value
        value = self.cast( value )
        rval = []
        for fields in options:
            try:
                if self.keep == ( self.compare( self.cast( fields[self.column] ), value ) ):
                    rval.append( fields )
            except Exception as e:
                log.debug(e)
                continue  # likely a bad cast or column out of range
        return rval


class InsertColumnAgentOutputActionOptionFilter( AgentOutputActionOptionFilter ):
    tag = "insert_column"

    def __init__( self, parent, elem ):
        super( InsertColumnAgentOutputActionOptionFilter, self ).__init__( parent, elem )
        self.ref = elem.get( 'ref', None )
        if self.ref:
            self.ref = self.ref.split( '.' )
        self.value = elem.get( 'value', None )
        assert self.ref != self.value, "Required 'ref' or 'value' attribute missing from InsertColumnAgentOutputActionOptionFilter"
        self.column = elem.get( 'column', None )  # None is append
        if self.column:
            self.column = int( self.column )
        self.iterate = util.string_as_bool( elem.get( "iterate", 'False' ) )

    def filter_options( self, options, other_values ):
        if self.ref:
            # find ref value
            value = other_values
            for ref_name in self.ref:
                assert ref_name in value, "Required dependency '%s' not found in incoming values" % ref_name
                value = value.get( ref_name )
            value = str( value )
        else:
            value = self.value
        if self.iterate:
            value = int( value )
        rval = []
        for fields in options:
            if self.column is None:
                rval.append( fields + [ str( value ) ] )
            else:
                fields = list( fields )
                fields.insert( self.column, str( value ) )
                rval.append( fields )
            if self.iterate:
                value += 1
        return rval


class MultipleSplitterFilter( AgentOutputActionOptionFilter ):
    tag = "multiple_splitter"

    def __init__( self, parent, elem ):
        super( MultipleSplitterFilter, self ).__init__( parent, elem )
        self.column = elem.get( 'column', None )
        assert self.column is not None, "Required 'column' attribute missing from MultipleSplitterFilter"
        self.column = int( self.column )
        self.separator = elem.get( "separator", "," )

    def filter_options( self, options, other_values ):
        rval = []
        for fields in options:
            for field in fields[self.column].split( self.separator ):
                rval.append( fields[0:self.column] + [field] + fields[self.column + 1:] )
        return rval


class ColumnStripFilter( AgentOutputActionOptionFilter ):
    tag = "column_strip"

    def __init__( self, parent, elem ):
        super( ColumnStripFilter, self ).__init__( parent, elem )
        self.column = elem.get( 'column', None )
        assert self.column is not None, "Required 'column' attribute missing from ColumnStripFilter"
        self.column = int( self.column )
        self.strip = elem.get( "strip", None )

    def filter_options( self, options, other_values ):
        rval = []
        for fields in options:
            rval.append( fields[0:self.column] + [ fields[self.column].strip( self.strip ) ] + fields[self.column + 1:] )
        return rval


class ColumnReplaceFilter( AgentOutputActionOptionFilter ):
    tag = "column_replace"

    def __init__( self, parent, elem ):
        super( ColumnReplaceFilter, self ).__init__( parent, elem )
        self.old_column = elem.get( 'old_column', None )
        self.old_value = elem.get( "old_value", None )
        self.new_value = elem.get( "new_value", None )
        self.new_column = elem.get( 'new_column', None )
        assert ( bool( self.old_column ) ^ bool( self.old_value ) and bool( self.new_column ) ^ bool( self.new_value ) ), "Required 'old_column' or 'old_value' and 'new_column' or 'new_value' attribute missing from ColumnReplaceFilter"
        self.column = elem.get( 'column', None )
        assert self.column is not None, "Required 'column' attribute missing from ColumnReplaceFilter"
        self.column = int( self.column )
        if self.old_column is not None:
            self.old_column = int( self.old_column )
        if self.new_column is not None:
            self.new_column = int( self.new_column )

    def filter_options( self, options, other_values ):
        rval = []
        for fields in options:
            if self.old_column:
                old_value = fields[self.old_column]
            else:
                old_value = self.old_value
            if self.new_column:
                new_value = fields[self.new_column]
            else:
                new_value = self.new_value
            rval.append( fields[0:self.column] + [ fields[self.column].replace( old_value, new_value ) ] + fields[self.column + 1:] )
        return rval


class MetadataValueFilter( AgentOutputActionOptionFilter ):
    tag = "metadata_value"

    def __init__( self, parent, elem ):
        super( MetadataValueFilter, self ).__init__( parent, elem )
        self.ref = elem.get( 'ref', None )
        assert self.ref is not None, "Required 'ref' attribute missing from MetadataValueFilter"
        self.ref = self.ref.split( '.' )
        self.name = elem.get( 'name', None )
        assert self.name is not None, "Required 'name' attribute missing from MetadataValueFilter"
        self.column = elem.get( 'column', None )
        assert self.column is not None, "Required 'column' attribute missing from MetadataValueFilter"
        self.column = int( self.column )
        self.keep = util.string_as_bool( elem.get( "keep", 'True' ) )
        self.compare = parse_compare_type( elem.get( 'compare', None ) )

    def filter_options( self, options, other_values ):
        ref = other_values
        for ref_name in self.ref:
            assert ref_name in ref, "Required dependency '%s' not found in incoming values" % ref_name
            ref = ref.get( ref_name )
        value = str( getattr( ref.metadata, self.name ) )
        rval = []
        for fields in options:
            if self.keep == ( self.compare( fields[self.column], value ) ):
                rval.append( fields )
        return rval


class BooleanFilter( AgentOutputActionOptionFilter ):
    tag = "boolean"

    def __init__( self, parent, elem ):
        super( BooleanFilter, self ).__init__( parent, elem )
        self.column = elem.get( 'column', None )
        assert self.column is not None, "Required 'column' attribute missing from BooleanFilter"
        self.column = int( self.column )
        self.keep = util.string_as_bool( elem.get( "keep", 'True' ) )
        self.cast = parse_cast_attribute( elem.get( "cast", None ) )

    def filter_options( self, options, other_values ):
        rval = []
        for fields in options:
            try:
                value = fields[self.column]
                value = self.cast( value )
            except:
                value = False  # unable to cast or access value; treat as false
            if self.keep == bool( value ):
                rval.append( fields )
        return rval


class StringFunctionFilter( AgentOutputActionOptionFilter ):
    tag = "string_function"

    def __init__( self, parent, elem ):
        super( StringFunctionFilter, self ).__init__( parent, elem )
        self.column = elem.get( 'column', None )
        assert self.column is not None, "Required 'column' attribute missing from StringFunctionFilter"
        self.column = int( self.column )
        self.function = elem.get( "name", None )
        assert self.function in [ 'lower', 'upper' ], "Required function 'name' missing or invalid from StringFunctionFilter"  # add function names as needed
        self.function = getattr( string, self.function )

    def filter_options( self, options, other_values ):
        rval = []
        for fields in options:
            rval.append( fields[0:self.column] + [ self.function( fields[self.column] ) ] + fields[self.column + 1:] )
        return rval


# tag to class lookups
action_types = {}
for action_type in [ MetadataAgentOutputAction, FormatAgentOutputAction ]:
    action_types[ action_type.tag ] = action_type

option_types = {}
for option_type in [ NullAgentOutputActionOption, FromFileAgentOutputActionOption, FromParamAgentOutputActionOption, FromDataTableOutputActionOption ]:
    option_types[ option_type.tag ] = option_type

filter_types = {}
for filter_type in [ ParamValueAgentOutputActionOptionFilter, InsertColumnAgentOutputActionOptionFilter, MultipleSplitterFilter, ColumnStripFilter, MetadataValueFilter, BooleanFilter, StringFunctionFilter, ColumnReplaceFilter ]:
    filter_types[ filter_type.tag ] = filter_type


# helper classes
# determine cast function
def parse_cast_attribute( cast ):
    if cast == 'string_as_bool':
        cast = util.string_as_bool
    elif cast == 'int':
        cast = int
    elif cast == 'str':
        cast = str
    else:
        # return value as-is
        def cast(x):
            return x
    return cast


# comparison
def parse_compare_type( compare ):
    if compare is None:
        compare = 'eq'
    assert compare in compare_types, "Invalid compare type specified: %s" % compare
    return compare_types[ compare ]


def compare_eq( value1, value2  ):
    return value1 == value2


def compare_neq( value1, value2  ):
    return value1 != value2


def compare_gt( value1, value2  ):
    return value1 > value2


def compare_gte( value1, value2  ):
    return value1 >= value2


def compare_lt( value1, value2  ):
    return value1 < value2


def compare_lte( value1, value2  ):
    return value1 <= value2


def compare_in( value1, value2 ):
    return value1 in value2


def compare_startswith( value1, value2 ):
    return value1.startswith( value2 )


def compare_endswith( value1, value2 ):
    return value1.endswith( value2 )


def compare_re_search( value1, value2 ):
    # checks pattern=value2 in value1
    return bool( re.search( value2, value1 ) )

compare_types = {
    'eq': compare_eq,
    'neq': compare_neq,
    'gt': compare_gt,
    'gte': compare_gte,
    'lt': compare_lt,
    'lte': compare_lte,
    'in': compare_in,
    'startswith': compare_startswith,
    'endswith': compare_endswith,
    "re_search": compare_re_search
}
