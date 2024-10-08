"""
API operations allowing clients to determine datatype supported by Galaxy.
"""

from galaxy.web import _future_expose_api as expose_api
from galaxy.web import require_admin
from galaxy.web.base.controller import BaseAPIController

from galaxy.agents.deps import views


import logging
log = logging.getLogger( __name__ )


class AgentDependenciesAPIController( BaseAPIController ):

    def __init__(self, app):
        super(AgentDependenciesAPIController, self).__init__(app)
        self._view = views.DependencyResolversView(app)

    @expose_api
    @require_admin
    def index(self, trans):
        """
        GET /api/dependencies_resolvers
        """
        return self._view.index()

    @expose_api
    @require_admin
    def show(self, trans, id):
        """
        GET /api/dependencies_resolver/<id>
        """
        return self._view.show(id)

    @expose_api
    @require_admin
    def update(self, trans):
        """
        PUT /api/dependencies_resolvers

        Reload agent dependency resolution configuration.
        """
        return self._view.reload()

    @expose_api
    @require_admin
    def resolver_dependency(self, trans, id, **kwds):
        """
        GET /api/dependencies_resolver/{index}/dependency

        Resolve described requirement against specified dependency resolver.

        :type   index:    int
        :param  index:    index of the dependency resolver
        :type   kwds:     dict
        :param  kwds:     dictionary structure containing extra parameters
        :type   name:     str
        :param  name:     name of the requirement to find a dependency for (required)
        :type   version:  str
        :param  version:  version of the requirement to find a dependency for (required)
        :type   exact:    bool
        :param  exact:    require an exact match to specify requirement (do not discard
                          version information to resolve dependency).

        :rtype:     dict
        :returns:   a dictified description of the dependency, with attribute
                    ``dependency_type: null`` if no match was found.
        """
        return self._view.resolver_dependency(id, **kwds)

    def manager_dependency(self, trans, **kwds):
        """
        GET /api/dependencies_resolvers/dependency

        Resolve described requirement against all dependency resolvers, returning
        the match with highest priority.

        :type   index:    int
        :param  index:    index of the dependency resolver
        :type   kwds:     dict
        :param  kwds:     dictionary structure containing extra parameters
        :type   name:     str
        :param  name:     name of the requirement to find a dependency for (required)
        :type   version:  str
        :param  version:  version of the requirement to find a dependency for (required)
        :type   exact:    bool
        :param  exact:    require an exact match to specify requirement (do not discard
                          version information to resolve dependency).

        :rtype:     dict
        :returns:   a dictified description of the dependency, with type: null
                    if no match was found.
        """
        return self._view.manager_dependency(**kwds)

    @expose_api
    @require_admin
    def resolver_requirements(self, trans, id, **kwds):
        """
        GET /api/dependencies_resolver/{index}/requirements

        Find all "simple" requirements that could be resolved "exactly"
        by this dependency resolver. The dependency resolver must implement
        ListDependencyResolver.

        :type   index:    int
        :param  index:    index of the dependency resolver

        :rtype:     dict
        :returns:   a dictified description of the requirement that could
                    be resolved.
        """
        return self._view.resolver_requirements(id)

    @expose_api
    @require_admin
    def manager_requirements(self, trans, **kwds):
        """
        GET /api/dependencies_resolver/requirements

        Find all "simple" requirements that could be resolved "exactly"
        by all dependency resolvers that support this operation.

        :type   index:    int
        :param  index:    index of the dependency resolver

        :rtype:     dict
        :returns:   a dictified description of the requirement that could
                    be resolved (keyed on 'requirement') and the index of
                    the corresponding resolver (keyed on 'index').
        """
        return self._view.manager_requirements()
