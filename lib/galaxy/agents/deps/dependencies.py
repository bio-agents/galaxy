from galaxy.agents.deps.requirements import AgentRequirement
from galaxy.util import bunch


class DependenciesDescription(object):
    """ Capture (in a readily serializable way) context related a agent
    dependencies - both the agent's listed requirements and the agent shed
    related context required to resolve dependencies via the
    AgentShedPackageDependencyResolver.

    This is meant to enable remote resolution of dependencies, by the Pulsar or
    other potential remote execution mechanisms.
    """

    def __init__(self, requirements=[], installed_agent_dependencies=[]):
        self.requirements = requirements
        # agent shed installed agent dependencies...
        self.installed_agent_dependencies = installed_agent_dependencies

    def to_dict(self):
        return dict(
            requirements=[r.to_dict() for r in self.requirements],
            installed_agent_dependencies=[DependenciesDescription._agentshed_install_dependency_to_dict(d) for d in self.installed_agent_dependencies]
        )

    @staticmethod
    def from_dict(as_dict):
        if as_dict is None:
            return None

        requirements_dicts = as_dict.get('requirements', [])
        requirements = [AgentRequirement.from_dict(r) for r in requirements_dicts]
        installed_agent_dependencies_dicts = as_dict.get('installed_agent_dependencies', [])
        installed_agent_dependencies = map(DependenciesDescription._agentshed_install_dependency_from_dict, installed_agent_dependencies_dicts)
        return DependenciesDescription(
            requirements=requirements,
            installed_agent_dependencies=installed_agent_dependencies
        )

    @staticmethod
    def _agentshed_install_dependency_from_dict(as_dict):
        # Rather than requiring full models in Pulsar, just use simple objects
        # containing only properties and associations used to resolve
        # dependencies for agent execution.
        repository_object = bunch.Bunch(
            name=as_dict['repository_name'],
            owner=as_dict['repository_owner'],
            installed_changeset_revision=as_dict['repository_installed_changeset'],
        )
        dependency_object = bunch.Bunch(
            name=as_dict['dependency_name'],
            version=as_dict['dependency_version'],
            type=as_dict['dependency_type'],
            agent_shed_repository=repository_object,
        )
        return dependency_object

    @staticmethod
    def _agentshed_install_dependency_to_dict(agent_dependency):
        agent_shed_repository = agent_dependency.agent_shed_repository
        return dict(
            dependency_name=agent_dependency.name,
            dependency_version=agent_dependency.version,
            dependency_type=agent_dependency.type,
            repository_name=agent_shed_repository.name,
            repository_owner=agent_shed_repository.owner,
            repository_installed_changeset=agent_shed_repository.installed_changeset_revision,
        )
