from os.path import abspath, join, exists

from .resolver_mixins import UsesInstalledRepositoriesMixin
from .galaxy_packages import BaseGalaxyPackageDependencyResolver, GalaxyPackageDependency
from ..resolvers import INDETERMINATE_DEPENDENCY


class AgentShedPackageDependencyResolver(BaseGalaxyPackageDependencyResolver, UsesInstalledRepositoriesMixin):
    resolver_type = "agent_shed_packages"
    # Resolution of these dependencies depends on more than just the requirement
    # tag, it depends on the agent installation context - therefore these are
    # non-simple.
    resolves_simple_dependencies = False

    def __init__(self, dependency_manager, **kwds):
        super(AgentShedPackageDependencyResolver, self).__init__(dependency_manager, **kwds)

    def _find_dep_versioned( self, name, version, type='package', **kwds ):
        installed_agent_dependency = self._get_installed_dependency( name, type, version=version, **kwds )
        if installed_agent_dependency:
            path = self._get_package_installed_dependency_path( installed_agent_dependency, name, version )
            return self._galaxy_package_dep(path, version, True)
        else:
            return INDETERMINATE_DEPENDENCY

    def _find_dep_default( self, name, type='package', **kwds ):
        if type == 'set_environment' and kwds.get('installed_agent_dependencies', None):
            installed_agent_dependency = self._get_installed_dependency( name, type, version=None, **kwds )
            if installed_agent_dependency:
                dependency = self._get_set_environment_installed_dependency_script_path( installed_agent_dependency, name )
                is_galaxy_dep = isinstance(dependency, GalaxyPackageDependency)
                has_script_dep = is_galaxy_dep and dependency.script and dependency.path
                if has_script_dep:
                    # Environment settings do not use versions.
                    return GalaxyPackageDependency(dependency.script, dependency.path, None, True)
        return INDETERMINATE_DEPENDENCY

    def _get_package_installed_dependency_path( self, installed_agent_dependency, name, version ):
        agent_shed_repository = installed_agent_dependency.agent_shed_repository
        base_path = self.base_path
        return join(
            base_path,
            name,
            version,
            agent_shed_repository.owner,
            agent_shed_repository.name,
            agent_shed_repository.installed_changeset_revision
        )

    def _get_set_environment_installed_dependency_script_path( self, installed_agent_dependency, name ):
        agent_shed_repository = installed_agent_dependency.agent_shed_repository
        base_path = self.base_path
        path = abspath( join( base_path,
                              'environment_settings',
                              name,
                              agent_shed_repository.owner,
                              agent_shed_repository.name,
                              agent_shed_repository.installed_changeset_revision ) )
        if exists( path ):
            script = join( path, 'env.sh' )
            return GalaxyPackageDependency(script, path, None, True)
        return INDETERMINATE_DEPENDENCY


__all__ = ['AgentShedPackageDependencyResolver']
