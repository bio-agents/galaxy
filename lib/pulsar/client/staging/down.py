from os.path import join
from os.path import relpath
from re import compile
from contextlib import contextmanager

from ..staging import COMMAND_VERSION_FILENAME
from ..action_mapper import FileActionMapper


from logging import getLogger
log = getLogger(__name__)

# All output files marked with from_work_dir attributes will copied or downloaded
# this pattern picks up attiditional files to copy back - such as those
# associated with multiple outputs and metadata configuration. Set to .* to just
# copy everything
COPY_FROM_WORKING_DIRECTORY_PATTERN = compile(r"primary_.*|galaxy.json|metadata_.*|dataset_\d+\.dat|__instrument_.*|dataset_\d+_files.+")


def finish_job(client, cleanup_job, job_completed_normally, client_outputs, pulsar_outputs):
    """ Responsible for downloading results from remote server and cleaning up
    Pulsar staging directory (if needed.)
    """
    collection_failure_exceptions = []
    if job_completed_normally:
        output_collector = ClientOutputCollector(client)
        action_mapper = FileActionMapper(client)
        results_stager = ResultsCollector(output_collector, action_mapper, client_outputs, pulsar_outputs)
        collection_failure_exceptions = results_stager.collect()
    __clean(collection_failure_exceptions, cleanup_job, client)
    return collection_failure_exceptions


class ClientOutputCollector(object):

    def __init__(self, client):
        self.client = client

    def collect_output(self, results_collector, output_type, action, name):
        # This output should have been handled by the Pulsar.
        if not action.staging_action_local:
            return False

        working_directory = results_collector.client_outputs.working_directory
        self.client.fetch_output(
            path=action.path,
            name=name,
            working_directory=working_directory,
            output_type=output_type,
            action_type=action.action_type
        )
        return True


class ResultsCollector(object):

    def __init__(self, output_collector, action_mapper, client_outputs, pulsar_outputs):
        self.output_collector = output_collector
        self.action_mapper = action_mapper
        self.client_outputs = client_outputs
        self.pulsar_outputs = pulsar_outputs
        self.downloaded_working_directory_files = []
        self.exception_tracker = DownloadExceptionTracker()
        self.output_files = client_outputs.output_files
        self.working_directory_contents = pulsar_outputs.working_directory_contents or []

    def collect(self):
        self.__collect_working_directory_outputs()
        self.__collect_outputs()
        self.__collect_version_file()
        self.__collect_other_working_directory_files()
        return self.exception_tracker.collection_failure_exceptions

    def __collect_working_directory_outputs(self):
        working_directory = self.client_outputs.working_directory
        # Fetch explicit working directory outputs.
        for source_file, output_file in self.client_outputs.work_dir_outputs:
            name = relpath(source_file, working_directory)
            pulsar = self.pulsar_outputs.path_helper.remote_name(name)
            if self._attempt_collect_output('output_workdir', path=output_file, name=pulsar):
                self.downloaded_working_directory_files.append(pulsar)
            # Remove from full output_files list so don't try to download directly.
            try:
                self.output_files.remove(output_file)
            except ValueError:
                raise Exception("Failed to remove %s from %s" % (output_file, self.output_files))

    def __collect_outputs(self):
        # Legacy Pulsar not returning list of files, iterate over the list of
        # expected outputs for agent.
        for output_file in self.output_files:
            # Fetch output directly...
            output_generated = self.pulsar_outputs.has_output_file(output_file)
            if output_generated:
                self._attempt_collect_output('output', output_file)

            for galaxy_path, pulsar in self.pulsar_outputs.output_extras(output_file).items():
                self._attempt_collect_output('output', path=galaxy_path, name=pulsar)
            # else not output generated, do not attempt download.

    def __collect_version_file(self):
        version_file = self.client_outputs.version_file
        pulsar_output_directory_contents = self.pulsar_outputs.output_directory_contents
        if version_file and COMMAND_VERSION_FILENAME in pulsar_output_directory_contents:
            self._attempt_collect_output('output', version_file, name=COMMAND_VERSION_FILENAME)

    def __collect_other_working_directory_files(self):
        working_directory = self.client_outputs.working_directory
        # Fetch remaining working directory outputs of interest.
        for name in self.working_directory_contents:
            if name in self.downloaded_working_directory_files:
                continue
            if self.client_outputs.dynamic_match(name):
                log.debug("collecting dynamic output %s" % name)
                output_file = join(working_directory, self.pulsar_outputs.path_helper.local_name(name))
                if self._attempt_collect_output(output_type='output_workdir', path=output_file, name=name):
                    self.downloaded_working_directory_files.append(name)

    def _attempt_collect_output(self, output_type, path, name=None):
        # path is final path on galaxy server (client)
        # name is the 'name' of the file on the Pulsar server (possible a relative)
        # path.
        collected = False
        with self.exception_tracker():
            action = self.action_mapper.action(path, output_type)
            if self._collect_output(output_type, action, name):
                collected = True

        return collected

    def _collect_output(self, output_type, action, name):
        log.info("collecting output %s with action %s" % (name, action))
        return self.output_collector.collect_output(self, output_type, action, name)


class DownloadExceptionTracker(object):

    def __init__(self):
        self.collection_failure_exceptions = []

    @contextmanager
    def __call__(self):
        try:
            yield
        except Exception as e:
            self.collection_failure_exceptions.append(e)


def __clean(collection_failure_exceptions, cleanup_job, client):
    failed = (len(collection_failure_exceptions) > 0)
    if (not failed and cleanup_job != "never") or cleanup_job == "always":
        try:
            client.clean()
        except Exception:
            log.warn("Failed to cleanup remote Pulsar job")

__all__ = ['finish_job']
