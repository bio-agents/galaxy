from __future__ import print_function
import inspect
from galaxy.util import submodules

LEVEL_ALL = "all"
LEVEL_WARN = "warn"
LEVEL_ERROR = "error"


def lint_xml(agent_xml, level=LEVEL_ALL, fail_level=LEVEL_WARN, extra_modules=[], skip_types=[]):
    lint_context = LintContext(level=level, skip_types=skip_types)
    lint_xml_with(lint_context, agent_xml, extra_modules)

    return not lint_context.failed(fail_level)


def lint_xml_with(lint_context, agent_xml, extra_modules=[]):
    import galaxy.agents.linters
    linter_modules = submodules.submodules(galaxy.agents.linters)
    linter_modules.extend(extra_modules)
    for module in linter_modules:
        for (name, value) in inspect.getmembers(module):
            if callable(value) and name.startswith("lint_"):
                lint_context.lint(name, value, agent_xml)


class LintContext(object):

    def __init__(self, level, skip_types=[]):
        self.skip_types = skip_types
        self.level = level
        self.found_errors = False
        self.found_warns = False

    def lint(self, name, lint_func, lint_target):
        name = name.replace("tsts", "tests")[len("lint_"):]
        if name in self.skip_types:
            return
        self.printed_linter_info = False
        self.valid_messages = []
        self.info_messages = []
        self.warn_messages = []
        self.error_messages = []
        lint_func(lint_target, self)
        # TODO: colorful emoji if in click CLI.
        if self.error_messages:
            status = "FAIL"
        elif self.warn_messages:
            status = "WARNING"
        else:
            status = "CHECK"

        def print_linter_info():
            if self.printed_linter_info:
                return
            self.printed_linter_info = True
            print("Applying linter %s... %s" % (name, status))

        for message in self.error_messages:
            self.found_errors = True
            print_linter_info()
            print(".. ERROR: %s" % message)

        if self.level != LEVEL_ERROR:
            for message in self.warn_messages:
                self.found_warns = True
                print_linter_info()
                print(".. WARNING: %s" % message)

        if self.level == LEVEL_ALL:
            for message in self.info_messages:
                print_linter_info()
                print(".. INFO: %s" % message)
            for message in self.valid_messages:
                print_linter_info()
                print(".. CHECK: %s" % message)

    def __handle_message(self, message_list, message, *args):
        if args:
            message = message % args
        message_list.append(message)

    def valid(self, message, *args):
        self.__handle_message(self.valid_messages, message, *args)

    def info(self, message, *args):
        self.__handle_message(self.info_messages, message, *args)

    def error(self, message, *args):
        self.__handle_message(self.error_messages, message, *args)

    def warn(self, message, *args):
        self.__handle_message(self.warn_messages, message, *args)

    def failed(self, fail_level):
        found_warns = self.found_warns
        found_errors = self.found_errors
        if fail_level == LEVEL_WARN:
            lint_fail = (found_warns or found_errors)
        else:
            lint_fail = found_errors
        return lint_fail
