import fnmatch
import glob
import os
import re
from ..agents import loader

import yaml

from galaxy.util import checkers

import sys

import logging
log = logging.getLogger(__name__)

PATH_DOES_NOT_EXIST_ERROR = "Could not load agents from path [%s] - this path does not exist."
PATH_AND_RECURSIVE_ERROR = "Cannot specify a single file and recursive."
LOAD_FAILURE_ERROR = "Failed to load agent with path %s."
TOOL_LOAD_ERROR = object()
TOOL_REGEX = re.compile(r"<agent\s")

YAML_EXTENSIONS = [".yaml", ".yml", ".json"]
CWL_EXTENSIONS = YAML_EXTENSIONS + [".cwl"]


def load_exception_handler(path, exc_info):
    log.warn(LOAD_FAILURE_ERROR % path, exc_info=exc_info)


def find_possible_agents_from_path(
    path,
    recursive=False,
    enable_beta_formats=False,
):
    possible_agent_files = []
    for possible_agent_file in __find_agent_files(
        path, recursive=recursive,
        enable_beta_formats=enable_beta_formats
    ):
        try:
            does_look_like_a_agent = looks_like_a_agent(possible_agent_file)
        except IOError:
            # Some problem reading the agent file, skip.
            continue

        if does_look_like_a_agent:
            possible_agent_files.append(possible_agent_file)

    return possible_agent_files


def load_agent_elements_from_path(
    path,
    load_exception_handler=load_exception_handler,
    recursive=False,
    register_load_errors=False,
):
    agent_elements = []
    for possible_agent_file in find_possible_agents_from_path(
        path,
        recursive=recursive,
        enable_beta_formats=False,
    ):
        try:
            agent_elements.append((possible_agent_file, loader.load_agent(possible_agent_file)))
        except Exception:
            exc_info = sys.exc_info()
            load_exception_handler(possible_agent_file, exc_info)
            if register_load_errors:
                agent_elements.append((possible_agent_file, TOOL_LOAD_ERROR))
    return agent_elements


def is_agent_load_error(obj):
    return obj is TOOL_LOAD_ERROR


def looks_like_a_agent(path, invalid_names=[], enable_beta_formats=False):
    """ Whether true in a strict sense or not, lets say the intention and
    purpose of this procedure is to serve as a filter - all valid agents must
    "looks_like_a_agent" but not everything that looks like a agent is actually
    a valid agent.

    invalid_names may be supplid in the context of the agent shed to quickly
    rule common agent shed XML files.
    """
    looks = False

    if os.path.basename(path) in invalid_names:
        return False

    if looks_like_a_agent_xml(path):
        looks = True

    if not looks and enable_beta_formats:
        for agent_checker in BETA_TOOL_CHECKERS.values():
            if agent_checker(path):
                looks = True
                break

    return looks


def looks_like_a_agent_xml(path):
    full_path = os.path.abspath(path)

    if not full_path.endswith(".xml"):
        return False

    if not os.path.getsize(full_path):
        return False

    if(checkers.check_binary(full_path) or
       checkers.check_image(full_path) or
       checkers.check_gzip(full_path)[0] or
       checkers.check_bz2(full_path)[0] or
       checkers.check_zip(full_path)):
        return False

    with open(path, "r") as f:
        start_contents = f.read(5 * 1024)
        if TOOL_REGEX.search(start_contents):
            return True

    return False


def looks_like_a_agent_yaml(path):
    if not _has_extension(path, YAML_EXTENSIONS):
        return False

    with open(path, "r") as f:
        try:
            as_dict = yaml.safe_load(f)
        except Exception:
            return False

    if not isinstance(as_dict, dict):
        return False

    file_class = as_dict.get("class", None)
    return file_class == "GalaxyAgent"


def looks_like_a_agent_cwl(path):
    if _has_extension(path, CWL_EXTENSIONS):
        return False

    with open(path, "r") as f:
        try:
            as_dict = yaml.safe_load(f)
        except Exception:
            return False

    if not isinstance(as_dict, dict):
        return False

    file_class = as_dict.get("class", None)
    file_cwl_version = as_dict.get("cwlVersion", None)
    return file_class == "CommandLineAgent" and file_cwl_version


def __find_agent_files(path, recursive, enable_beta_formats):
    is_file = not os.path.isdir(path)
    if not os.path.exists(path):
        raise Exception(PATH_DOES_NOT_EXIST_ERROR)
    elif is_file and recursive:
        raise Exception(PATH_AND_RECURSIVE_ERROR)
    elif is_file:
        return [os.path.abspath(path)]
    else:
        if enable_beta_formats:
            if not recursive:
                files = glob.glob(path + "/*")
            else:
                files = _find_files(path, "*")
        else:
            if not recursive:
                files = glob.glob(path + "/*.xml")
            else:
                files = _find_files(path, "*.xml")
        return map(os.path.abspath, files)


def _has_extension(path, extensions):
    return any(map(lambda e: path.endswith(e), extensions))


def _find_files(directory, pattern='*'):
    if not os.path.exists(directory):
        raise ValueError("Directory not found {}".format(directory))

    matches = []
    for root, dirnames, filenames in os.walk(directory):
        for filename in filenames:
            full_path = os.path.join(root, filename)
            if fnmatch.filter([full_path], pattern):
                matches.append(os.path.join(root, filename))
    return matches


BETA_TOOL_CHECKERS = {
    'yaml': looks_like_a_agent_yaml,
    'cwl': looks_like_a_agent_cwl,
}
