from galaxy.model import agent_shed_install
from galaxy.agents.deps import requirements
from galaxy.agents.deps import dependencies


def test_serialization():
    repository = agent_shed_install.AgentShedRepository(
        owner="devteam",
        name="tophat",
        installed_changeset_revision="abcdefghijk",
    )
    dependency = agent_shed_install.AgentDependency(
        name="tophat",
        version="2.0",
        type="package",
        status=agent_shed_install.AgentDependency.installation_status.INSTALLED,
    )
    dependency.agent_shed_repository = repository
    agent_requirement = requirements.AgentRequirement(
        name="tophat",
        version="2.0",
        type="package",
    )
    descript = dependencies.DependenciesDescription(
        requirements=[agent_requirement],
        installed_agent_dependencies=[dependency],
    )
    result_descript = dependencies.DependenciesDescription.from_dict(
        descript.to_dict()
    )
    result_requirement = result_descript.requirements[0]
    assert result_requirement.name == "tophat"
    assert result_requirement.version == "2.0"
    assert result_requirement.type == "package"

    result_agent_shed_dependency = result_descript.installed_agent_dependencies[0]
    result_agent_shed_dependency.name = "tophat"
    result_agent_shed_dependency.version = "2.0"
    result_agent_shed_dependency.type = "package"
    result_agent_shed_repository = result_agent_shed_dependency.agent_shed_repository
    result_agent_shed_repository.name = "tophat"
    result_agent_shed_repository.owner = "devteam"
    result_agent_shed_repository.installed_changeset_revision = "abcdefghijk"
