from copy import deepcopy
import sys
import logging

from galaxy.util import listify

log = logging.getLogger( __name__ )


class FilterFactory( object ):
    """
    An instance of this class is responsible for filtering the list
    of agents presented to a given user in a given context.
    """

    def __init__( self, agentbox ):
        self.agentbox = agentbox

        # Prepopulate dict containing filters that are always checked,
        # other filters that get checked depending on context (e.g. coming from
        # trackster or no user found are added in build filters).
        self.default_filters = dict( agent=[ _not_hidden, _handle_authorization ], section=[], label=[] )
        # Add dynamic filters to these default filters.
        config = agentbox.app.config
        self.__base_modules = listify( getattr( config, "agentbox_filter_base_modules", "galaxy.agents.filters" ) )
        self.__init_filters( "agent", getattr( config, "agent_filters", "" ), self.default_filters )
        self.__init_filters( "section", getattr( config, "agent_section_filters", "" ), self.default_filters )
        self.__init_filters( "label", getattr( config, "agent_label_filters", "" ), self.default_filters )

    def build_filters( self, trans, **kwds ):
        """
        Build list of filters to check agents against given current context.
        """
        filters = deepcopy( self.default_filters )
        if trans.user:
            for name, value in trans.user.preferences.items():
                if value.strip():
                    user_filters = listify( value, do_strip=True )
                    category = ''
                    if name == 'agentbox_agent_filters':
                        category = "agent"
                    elif name == 'agentbox_section_filters':
                        category = "section"
                    elif name == 'agentbox_label_filters':
                        category = "label"
                    if category:
                        validate = getattr( trans.app.config, 'user_%s_filters' % category, [] )
                        self.__init_filters( category, user_filters, filters, validate=validate )
        else:
            if kwds.get( "trackster", False ):
                filters[ "agent" ].append( _has_trackster_conf )

        return filters

    def __init_filters( self, key, filters, agentbox_filters, validate=None ):
        for filter in filters:
            if validate is None or filter in validate or filter in self.default_filters:
                filter_function = self.__build_filter_function( filter )
                agentbox_filters[ key ].append( filter_function )
            else:
                log.warning( "Refusing to load %s filter '%s' which is not defined in config", key, filter )
        return agentbox_filters

    def __build_filter_function( self, filter_name ):
        """Obtain python function (importing a submodule if needed)
        corresponding to filter_name.
        """
        if ":" in filter_name:
            # Should be a submodule of filters (e.g. examples:restrict_development_agents)
            (module_name, function_name) = filter_name.rsplit(":", 1)
            function = self._import_filter( module_name, function_name )
        else:
            # No module found, just load a function from this file or
            # one that has be explicitly imported.
            function = getattr( globals(), filter_name.strip() )
        return function

    def _import_filter( self, module_name, function_name ):
        function_name = function_name.strip()
        for base_module in self.__base_modules:
            full_module_name = "%s.%s" % ( base_module, module_name.strip() )
            try:
                __import__( full_module_name )
            except ImportError:
                # log.debug("Failed to load module.", exc_info=True)
                continue
            module = sys.modules[ full_module_name ]
            if hasattr( module, function_name ):
                return getattr( module, function_name )
        raise Exception("Failed to find filter %s.%s" % (module_name, function_name))


# Stock Filter Functions
def _not_hidden( context, agent ):
    return not agent.hidden


def _handle_authorization( context, agent ):
    user = context.trans.user
    if agent.require_login and not user:
        return False
    if not agent.allow_user_access( user, attempting_access=False ):
        return False
    return True


def _has_trackster_conf( context, agent ):
    return agent.trackster_conf
