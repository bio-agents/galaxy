import os

from ..deps import commands
from ..deps import docker_util
from ..deps.containers import docker_cache_path
from ..deps.requirements import parse_requirements_from_xml
from ...agents import loader_directory

import logging
log = logging.getLogger(__name__)


def docker_host_args(**kwds):
    return dict(
        docker_cmd=kwds["docker_cmd"],
        sudo=kwds["docker_sudo"],
        sudo_cmd=kwds["docker_sudo_cmd"],
        host=kwds["docker_host"]
    )


def dockerfile_build(path, dockerfile=None, error=log.error, **kwds):
    expected_container_names = set()
    agent_directories = set()
    for (agent_path, agent_xml) in loader_directory.load_agent_elements_from_path(path):
        requirements, containers = parse_requirements_from_xml(agent_xml)
        for container in containers:
            if container.type == "docker":
                expected_container_names.add(container.identifier)
                agent_directories.add(os.path.dirname(agent_path))
                break

    if len(expected_container_names) == 0:
        error("Could not find any docker identifiers to generate.")

    if len(expected_container_names) > 1:
        error("Multiple different docker identifiers found for selected agents [%s]", expected_container_names)

    image_identifier = expected_container_names.pop()

    dockerfile = __find_dockerfile(dockerfile, agent_directories)
    if dockerfile is not None:
        docker_command_parts = docker_util.build_command(
            image_identifier,
            dockerfile,
            **docker_host_args(**kwds)
        )
    else:
        docker_command_parts = docker_util.build_pull_command(image_identifier, **docker_host_args(**kwds))
        commands.execute(docker_command_parts)

    commands.execute(docker_command_parts)
    docker_image_cache = kwds['docker_image_cache']
    if docker_image_cache:
        destination = docker_cache_path(docker_image_cache, image_identifier)
        save_image_command_parts = docker_util.build_save_image_command(
            image_identifier,
            destination,
            **docker_host_args(**kwds)
        )
        commands.execute(save_image_command_parts)


def __find_dockerfile(dockerfile, agent_directories):
    if dockerfile is not None:
        return dockerfile
    search_directories = ["."]
    if len(agent_directories) == 1:
        agent_directory = agent_directories.pop()
        search_directories.insert(0, agent_directory)
    for directory in search_directories:
        potential_dockerfile = os.path.join(directory, "Dockerfile")
        if os.path.exists(potential_dockerfile):
            return potential_dockerfile
    return None
