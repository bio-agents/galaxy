from abc import ABCMeta
from abc import abstractmethod

NOT_IMPLEMENTED_MESSAGE = "Galaxy agent format does not yet support this agent feature."


class AgentSource(object):
    """ This interface represents an abstract source to parse agent
    information from.
    """
    __metaclass__ = ABCMeta
    default_is_multi_byte = False

    @abstractmethod
    def parse_id(self):
        """ Parse an ID describing the abstract agent. This is not the
        GUID tracked by the agent shed but the simple id (there may be
        multiple agents loaded in Galaxy with this same simple id).
        """

    @abstractmethod
    def parse_version(self):
        """ Parse a version describing the abstract agent.
        """

    def parse_agent_module(self):
        """ Load Agent class from a custom module. (Optional).

        If not None, return pair containing module and class (as strings).
        """
        return None

    def parse_action_module(self):
        """ Load Agent class from a custom module. (Optional).

        If not None, return pair containing module and class (as strings).
        """
        return None

    def parse_agent_type(self):
        """ Load simple agent type string (e.g. 'data_source', 'default').
        """
        return None

    @abstractmethod
    def parse_name(self):
        """ Parse a short name for agent (required). """

    @abstractmethod
    def parse_description(self):
        """ Parse a description for agent. Longer than name, shorted than help. """

    def parse_is_multi_byte(self):
        """ Parse is_multi_byte from agent - TODO: figure out what this is and
        document.
        """
        return self.default_is_multi_byte

    def parse_display_interface(self, default):
        """ Parse display_interface - fallback to default for the agent type
        (supplied as default parameter) if not specified.
        """
        return default

    def parse_require_login(self, default):
        """ Parse whether the agent requires login (as a bool).
        """
        return default

    def parse_request_param_translation_elem(self):
        """ Return an XML element describing require parameter translation.

        If we wish to support this feature for non-XML based agents this should
        be converted to return some sort of object interface instead of a RAW
        XML element.
        """
        return None

    @abstractmethod
    def parse_command(self):
        """ Return string contianing command to run.
        """

    @abstractmethod
    def parse_environment_variables(self):
        """ Return environment variable templates to expose.
        """

    @abstractmethod
    def parse_interpreter(self):
        """ Return string containing the interpreter to prepend to the command
        (for instance this might be 'python' to run a Python wrapper located
        adjacent to the agent).
        """

    def parse_redirect_url_params_elem(self):
        """ Return an XML element describing redirect_url_params.

        If we wish to support this feature for non-XML based agents this should
        be converted to return some sort of object interface instead of a RAW
        XML element.
        """
        return None

    def parse_version_command(self):
        """ Parse command used to determine version of primary application
        driving the agent. Return None to not generate or record such a command.
        """
        return None

    def parse_version_command_interpreter(self):
        """ Parse command used to determine version of primary application
        driving the agent. Return None to not generate or record such a command.
        """
        return None

    def parse_parallelism(self):
        """ Return a galaxy.jobs.ParallismInfo object describing task splitting
        or None.
        """
        return None

    def parse_hidden(self):
        """ Return boolean indicating whether agent should be hidden in the agent menu.
        """
        return False

    @abstractmethod
    def parse_requirements_and_containers(self):
        """ Return pair of AgentRequirement and ContainerDescription lists. """

    @abstractmethod
    def parse_input_pages(self):
        """ Return a PagesSource representing inputs by page for agent. """

    @abstractmethod
    def parse_outputs(self, agent):
        """ Return a pair of output and output collections ordered
        dictionaries for use by Agent.
        """

    @abstractmethod
    def parse_stdio(self):
        """ Builds lists of AgentStdioExitCode and AgentStdioRegex objects
        to describe agent execution error conditions.
        """
        return [], []

    @abstractmethod
    def parse_help(self):
        """ Return RST definition of help text for agent or None if the agent
        doesn't define help text.
        """

    def parse_tests_to_dict(self):
        return {'tests': []}


class PagesSource(object):
    """ Contains a list of Pages - each a list of InputSources -
    each item in the outer list representing a page of inputs.
    Pages are deprecated so ideally this outer list will always
    be exactly a singleton.
    """
    def __init__(self, page_sources):
        self.page_sources = page_sources

    @property
    def inputs_defined(self):
        return True


class PageSource(object):
    __metaclass__ = ABCMeta

    def parse_display(self):
        return None

    @abstractmethod
    def parse_input_sources(self):
        """ Return a list of InputSource objects. """


class InputSource(object):
    __metaclass__ = ABCMeta
    default_optional = False

    def elem(self):
        # For things in transition that still depend on XML - provide a way
        # to grab it and just throw an error if feature is attempted to be
        # used with other agent sources.
        raise NotImplementedError(NOT_IMPLEMENTED_MESSAGE)

    @abstractmethod
    def get(self, key, value=None):
        """ Return simple named properties as string for this input source.
        keys to be supported depend on the parameter type.
        """

    @abstractmethod
    def get_bool(self, key, default):
        """ Return simple named properties as boolean for this input source.
        keys to be supported depend on the parameter type.
        """

    def parse_label(self):
        return self.get("label")

    def parse_help(self):
        return self.get("help")

    def parse_sanitizer_elem(self):
        """ Return an XML description of sanitizers. This is a stop gap
        until we can rework galaxy.agents.parameters.sanitize to not
        explicitly depend on XML.
        """
        return None

    def parse_validator_elems(self):
        """ Return an XML description of sanitizers. This is a stop gap
        until we can rework galaxy.agents.parameters.validation to not
        explicitly depend on XML.
        """
        return []

    def parse_optional(self, default=None):
        """ Return boolean indicating wheter parameter is optional. """
        if default is None:
            default = self.default_optional
        return self.get_bool( "optional", default )

    def parse_dynamic_options_elem(self):
        """ Return an XML elemnt describing dynamic options.
        """
        return None

    def parse_static_options(self):
        """ Return list of static options if this is a select type without
        defining a dynamic options.
        """
        return []

    def parse_conversion_tuples(self):
        """ Return list of (name, extension) to describe explicit conversions.
        """
        return []

    def parse_nested_inputs_source(self):
        # For repeats
        raise NotImplementedError(NOT_IMPLEMENTED_MESSAGE)

    def parse_test_input_source(self):
        # For conditionals
        raise NotImplementedError(NOT_IMPLEMENTED_MESSAGE)

    def parse_when_input_sources(self):
        raise NotImplementedError(NOT_IMPLEMENTED_MESSAGE)


class AgentStdioRegex( object ):
    """
    This is a container for the <stdio> element's regex subelement.
    The regex subelement has a "match" attribute, a "sources"
    attribute that contains "output" and/or "error", and a "level"
    attribute that contains "warning" or "fatal".
    """
    def __init__( self ):
        self.match = ""
        self.stdout_match = False
        self.stderr_match = False
        # TODO: Define a common class or constant for error level:
        self.error_level = "fatal"
        self.desc = ""


class AgentStdioExitCode( object ):
    """
    This is a container for the <stdio> element's <exit_code> subelement.
    The exit_code element has a range of exit codes and the error level.
    """
    def __init__( self ):
        self.range_start = float( "-inf" )
        self.range_end = float( "inf" )
        # TODO: Define a common class or constant for error level:
        self.error_level = "fatal"
        self.desc = ""


class TestCollectionDef( object ):
    # TODO: do not require XML directly here.

    def __init__( self, elem, parse_param_elem ):
        self.elements = []
        attrib = dict( elem.attrib )
        self.collection_type = attrib[ "type" ]
        self.name = attrib.get( "name", "Unnamed Collection" )
        for element in elem.findall( "element" ):
            element_attrib = dict( element.attrib )
            element_identifier = element_attrib[ "name" ]
            nested_collection_elem = element.find( "collection" )
            if nested_collection_elem is not None:
                self.elements.append( ( element_identifier, TestCollectionDef( nested_collection_elem, parse_param_elem ) ) )
            else:
                self.elements.append( ( element_identifier, parse_param_elem( element ) ) )

    def collect_inputs( self ):
        inputs = []
        for element in self.elements:
            value = element[ 1 ]
            if isinstance( value, TestCollectionDef ):
                inputs.extend( value.collect_inputs() )
            else:
                inputs.append( value )
        return inputs


class TestCollectionOutputDef( object ):
    # TODO: do not require XML directly here.

    def __init__( self, name, attrib, element_tests ):
        self.name = name
        self.collection_type = attrib.get( "type", None )
        self.attrib = attrib
        self.element_tests = element_tests
