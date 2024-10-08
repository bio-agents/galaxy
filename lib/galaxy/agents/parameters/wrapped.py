from galaxy.agents.parameters.basic import (
    DataAgentParameter,
    DataCollectionAgentParameter,
    SelectAgentParameter
)
from galaxy.agents.wrappers import (
    InputValueWrapper,
    SelectAgentParameterWrapper,
    DatasetFilenameWrapper,
    DatasetListWrapper,
    DatasetCollectionWrapper
)
from galaxy.agents.parameters.grouping import (
    Repeat,
    Conditional,
    Section
)
PARAMS_UNWRAPPED = object()


class WrappedParameters( object ):

    def __init__( self, trans, agent, incoming ):
        self.trans = trans
        self.agent = agent
        self.incoming = incoming
        self._params = PARAMS_UNWRAPPED

    @property
    def params( self ):
        if self._params is PARAMS_UNWRAPPED:
            params = make_dict_copy( self.incoming )
            self.wrap_values( self.agent.inputs, params, skip_missing_values=not self.agent.check_values )
            self._params = params
        return self._params

    def wrap_values( self, inputs, input_values, skip_missing_values=False ):
        trans = self.trans
        agent = self.agent
        incoming = self.incoming

        # Wrap agent inputs as necessary
        for input in inputs.itervalues():
            if input.name not in input_values and skip_missing_values:
                continue
            value = input_values[ input.name ]
            if isinstance( input, Repeat ):
                for d in input_values[ input.name ]:
                    self.wrap_values( input.inputs, d, skip_missing_values=skip_missing_values )
            elif isinstance( input, Conditional ):
                values = input_values[ input.name ]
                current = values[ "__current_case__" ]
                self.wrap_values( input.cases[current].inputs, values, skip_missing_values=skip_missing_values )
            elif isinstance( input, Section ):
                values = input_values[ input.name ]
                self.wrap_values( input.inputs, values, skip_missing_values=skip_missing_values )
            elif isinstance( input, DataAgentParameter ) and input.multiple:
                value = input_values[ input.name ]
                dataset_instances = DatasetListWrapper.to_dataset_instances( value )
                input_values[ input.name ] = \
                    DatasetListWrapper( dataset_instances,
                                        datatypes_registry=trans.app.datatypes_registry,
                                        agent=agent,
                                        name=input.name )
            elif isinstance( input, DataAgentParameter ):
                input_values[ input.name ] = \
                    DatasetFilenameWrapper( input_values[ input.name ],
                                            datatypes_registry=trans.app.datatypes_registry,
                                            agent=agent,
                                            name=input.name )
            elif isinstance( input, SelectAgentParameter ):
                input_values[ input.name ] = SelectAgentParameterWrapper( input, input_values[ input.name ], agent.app, other_values=incoming )
            elif isinstance( input, DataCollectionAgentParameter ):
                input_values[ input.name ] = DatasetCollectionWrapper(
                    input_values[ input.name ],
                    datatypes_registry=trans.app.datatypes_registry,
                    agent=agent,
                    name=input.name,
                )
            else:
                input_values[ input.name ] = InputValueWrapper( input, value, incoming )


def make_dict_copy( from_dict ):
    """
    Makes a copy of input dictionary from_dict such that all values that are dictionaries
    result in creation of a new dictionary ( a sort of deepcopy ).  We may need to handle
    other complex types ( e.g., lists, etc ), but not sure...
    Yes, we need to handle lists (and now are)...
    """
    copy_from_dict = {}
    for key, value in from_dict.items():
        if type( value ).__name__ == 'dict':
            copy_from_dict[ key ] = make_dict_copy( value )
        elif isinstance( value, list ):
            copy_from_dict[ key ] = make_list_copy( value )
        else:
            copy_from_dict[ key ] = value
    return copy_from_dict


def make_list_copy( from_list ):
    new_list = []
    for value in from_list:
        if isinstance( value, dict ):
            new_list.append( make_dict_copy( value ) )
        elif isinstance( value, list ):
            new_list.append( make_list_copy( value ) )
        else:
            new_list.append( value )
    return new_list


__all__ = [ 'WrappedParameters', 'make_dict_copy' ]
