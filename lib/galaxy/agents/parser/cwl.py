import logging
import os

from .interface import AgentSource
from .interface import PagesSource
from .interface import PageSource
from .interface import AgentStdioExitCode
from .yaml import YamlInputSource

from .output_actions import AgentOutputActionGroup
from .output_objects import AgentOutput

from galaxy.agents.deps import requirements
from galaxy.agents.cwl import agent_proxy

from galaxy.util.odict import odict

log = logging.getLogger(__name__)


class CwlAgentSource(AgentSource):

    def __init__(self, agent_file):
        self._cwl_agent_file = agent_file
        self._id, _ = os.path.splitext(os.path.basename(agent_file))
        self._agent_proxy = agent_proxy(agent_file)

    @property
    def agent_proxy(self):
        return self._agent_proxy

    def parse_agent_type(self):
        return 'cwl'

    def parse_id(self):
        log.warn("TOOL ID is %s" % self._id)
        return self._id

    def parse_name(self):
        return self._id

    def parse_command(self):
        return "$__cwl_command"

    def parse_environment_variables(self):
        environment_variables = []
        # TODO: Is this even possible from here, should instead this be moved
        # into the job.

        # for environment_variable_el in environment_variables_el.findall("environment_variable"):
        #    definition = {
        #        "name": environment_variable_el.get("name"),
        #        "template": environment_variable_el.text,
        #    }
        #    environment_variables.append(
        #        definition
        #    )

        return environment_variables

    def parse_help(self):
        return ""

    def parse_stdio(self):
        # TODO: remove duplication with YAML
        from galaxy.jobs.error_level import StdioErrorLevel

        # New format - starting out just using exit code.
        exit_code_lower = AgentStdioExitCode()
        exit_code_lower.range_start = float("-inf")
        exit_code_lower.range_end = -1
        exit_code_lower.error_level = StdioErrorLevel.FATAL
        exit_code_high = AgentStdioExitCode()
        exit_code_high.range_start = 1
        exit_code_high.range_end = float("inf")
        exit_code_lower.error_level = StdioErrorLevel.FATAL
        return [exit_code_lower, exit_code_high], []

    def parse_interpreter(self):
        return None

    def parse_version(self):
        return "0.0.1"

    def parse_description(self):
        return self._agent_proxy.description() or ""

    def parse_input_pages(self):
        page_source = CwlPageSource(self._agent_proxy)
        return PagesSource([page_source])

    def parse_outputs(self, agent):
        output_instances = self._agent_proxy.output_instances()
        outputs = odict()
        output_defs = []
        for output_instance in output_instances:
            output_defs.append(self._parse_output(agent, output_instance))
        # TODO: parse outputs collections
        for output_def in output_defs:
            outputs[output_def.name] = output_def
        return outputs, odict()

    def _parse_output(self, agent, output_instance):
        name = output_instance.name
        # TODO: handle filters, actions, change_format
        output = AgentOutput( name )
        output.format = "_sniff_"
        output.change_format = []
        output.format_source = None
        output.metadata_source = ""
        output.parent = None
        output.label = None
        output.count = None
        output.filters = []
        output.agent = agent
        output.from_work_dir = "__cwl_output_%s" % name
        output.hidden = ""
        output.dataset_collectors = []
        output.actions = AgentOutputActionGroup( output, None )
        return output

    def parse_requirements_and_containers(self):
        containers = []
        docker_identifier = self._agent_proxy.docker_identifier()
        if docker_identifier:
            containers.append({"type": "docker",
                               "identifier": docker_identifier})
        return requirements.parse_requirements_from_dict(dict(
            requirements=[],  # TODO: enable via extensions
            containers=containers,
        ))


class CwlPageSource(PageSource):

    def __init__(self, agent_proxy):
        cwl_instances = agent_proxy.input_instances()
        self._input_list = map(self._to_input_source, cwl_instances)

    def _to_input_source(self, input_instance):
        as_dict = input_instance.to_dict()
        return YamlInputSource(as_dict)

    def parse_input_sources(self):
        return self._input_list
