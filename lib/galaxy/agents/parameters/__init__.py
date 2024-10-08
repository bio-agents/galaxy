"""
Classes encapsulating Galaxy agent parameters.
"""

from basic import DataCollectionAgentParameter, DataAgentParameter, SelectAgentParameter
from grouping import Conditional, Repeat, Section, UploadDataset
from galaxy.util.json import dumps, json_fix, loads

REPLACE_ON_TRUTHY = object()


def visit_input_values( inputs, input_values, callback, name_prefix="", label_prefix="", no_replacement_value=REPLACE_ON_TRUTHY ):
    """
    Given a agents parameter definition (`inputs`) and a specific set of
    parameter `values`, call `callback` for each non-grouping parameter,
    passing the parameter object, value, a constructed unique name,
    and a display label.

    If the callback returns a value, it will be replace the old value.

    FIXME: There is redundancy between this and the visit_inputs methods of
           Repeat and Group. This tracks labels and those do not. It would
           be nice to unify all the places that recursively visit inputs.
    """
    for input in inputs.itervalues():
        if isinstance( input, Repeat ) or isinstance( input, UploadDataset ):
            for i, d in enumerate( input_values[ input.name ] ):
                index = d['__index__']
                new_name_prefix = name_prefix + "%s_%d|" % ( input.name, index )
                new_label_prefix = label_prefix + "%s %d > " % ( input.title, i + 1 )
                visit_input_values( input.inputs, d, callback, new_name_prefix, new_label_prefix, no_replacement_value=no_replacement_value )
        elif isinstance( input, Conditional ):
            values = input_values[ input.name ]
            current = values["__current_case__"]
            label_prefix = label_prefix
            new_name_prefix = name_prefix + input.name + "|"
            visit_input_values( input.cases[current].inputs, values, callback, new_name_prefix, label_prefix, no_replacement_value=no_replacement_value )
        elif isinstance( input, Section ):
            values = input_values[ input.name ]
            label_prefix = label_prefix
            new_name_prefix = name_prefix + input.name + "|"
            visit_input_values( input.inputs, values, callback, new_name_prefix, label_prefix, no_replacement_value=no_replacement_value )
        else:
            new_value = callback( input,
                                  input_values[input.name],
                                  prefixed_name=name_prefix + input.name,
                                  prefixed_label=label_prefix + input.label )

            if no_replacement_value is REPLACE_ON_TRUTHY:
                replace = bool(new_value)
            else:
                replace = new_value != no_replacement_value
            if replace:
                input_values[input.name] = new_value


def check_param( trans, param, incoming_value, param_values, source='html', history=None, workflow_building_mode=False ):
    """
    Check the value of a single parameter `param`. The value in
    `incoming_value` is converted from its HTML encoding and validated.
    The `param_values` argument contains the processed values of
    previous parameters (this may actually be an ExpressionContext
    when dealing with grouping scenarios).
    """
    value = incoming_value
    error = None
    try:
        if history is None:
            history = trans.history
        if value is not None or isinstance( param, DataAgentParameter ) or isinstance( param, DataCollectionAgentParameter ):
            # Convert value from HTML representation
            if source == 'html':
                value = param.from_html( value, trans, param_values )
            else:
                value = param.from_json( value, trans, param_values )
            # Allow the value to be converted if necessary
            filtered_value = param.filter_value( value, trans, param_values )
            # Then do any further validation on the value
            param.validate( filtered_value, history, workflow_building_mode=workflow_building_mode )
        elif value is None and isinstance( param, SelectAgentParameter ):
            # An empty select list or column list
            param.validate( value, history, workflow_building_mode=workflow_building_mode )
    except ValueError, e:
        error = str( e )
    return value, error


def params_to_strings( params, param_values, app ):
    """
    Convert a dictionary of parameter values to a dictionary of strings
    suitable for persisting. The `value_to_basic` method of each parameter
    is called to convert its value to basic types, the result of which
    is then json encoded (this allowing complex nested parameters and
    such).
    """
    rval = dict()
    for key, value in param_values.iteritems():
        if key in params:
            value = params[ key ].value_to_basic( value, app )
        rval[ key ] = str( dumps( value ) )
    return rval


def params_from_strings( params, param_values, app, ignore_errors=False ):
    """
    Convert a dictionary of strings as produced by `params_to_strings`
    back into parameter values (decode the json representation and then
    allow each parameter to convert the basic types into the parameters
    preferred form).
    """
    rval = dict()
    for key, value in param_values.iteritems():
        value = json_fix( loads( value ) )
        if key in params:
            value = params[key].value_from_basic( value, app, ignore_errors )
        rval[ key ] = value
    return rval


def params_to_incoming( incoming, inputs, input_values, app, name_prefix="", to_html=True ):
    """
    Given a agent's parameter definition (`inputs`) and a specific set of
    parameter `input_values` objects, populate `incoming` with the html values.

    Useful for e.g. the rerun function.
    """
    for input in inputs.itervalues():
        if isinstance( input, Repeat ) or isinstance( input, UploadDataset ):
            for d in input_values[ input.name ]:
                index = d['__index__']
                new_name_prefix = name_prefix + "%s_%d|" % ( input.name, index )
                params_to_incoming( incoming, input.inputs, d, app, new_name_prefix, to_html=to_html)
        elif isinstance( input, Conditional ):
            values = input_values[ input.name ]
            current = values["__current_case__"]
            new_name_prefix = name_prefix + input.name + "|"
            incoming[ new_name_prefix + input.test_param.name ] = values[ input.test_param.name ]
            params_to_incoming( incoming, input.cases[current].inputs, values, app, new_name_prefix, to_html=to_html )
        elif isinstance( input, Section ):
            values = input_values[ input.name ]
            new_name_prefix = name_prefix + input.name + "|"
            params_to_incoming( incoming, input.inputs, values, app, new_name_prefix, to_html=to_html )
        else:
            value = input_values.get( input.name )
            if to_html:
                value = input.to_html_value( value, app )
            incoming[ name_prefix + input.name ] = value
