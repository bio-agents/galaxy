import os
import shutil
from sys import version_info
from tempfile import mkdtemp

if version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest as unittest

from galaxy.agents.deps import DependencyManager
from galaxy.agents.deps.resolvers.conda import CondaDependencyResolver
from galaxy.agents.deps import conda_util


def skip_unless_environ(var):
    if var in os.environ:
        return lambda func: func
    template = "Environment variable %s not found, dependent test skipped."
    return unittest.skip(template % var)


@skip_unless_environ("GALAXY_TEST_INCLUDE_SLOW")
def test_conda_resolution():
    base_path = mkdtemp()
    try:
        job_dir = os.path.join(base_path, "000")
        dependency_manager = DependencyManager(base_path)
        resolver = CondaDependencyResolver(
            dependency_manager,
            auto_init=True,
            auto_install=True,
            use_path_exec=False,  # For the test ensure this is always a clean install
        )
        conda_context = resolver.conda_context
        assert len(list(conda_util.installed_conda_targets(conda_context))) == 0
        dependency = resolver.resolve(name="samagents", version=None, type="package", job_directory=job_dir)
        assert dependency.shell_commands(None) is not None
        installed_targets = list(conda_util.installed_conda_targets(conda_context))
        assert len(installed_targets) == 1
        samagents_target = installed_targets[0]
        assert samagents_target.package == "samagents"
        assert samagents_target.version is None
    finally:
        shutil.rmtree(base_path)
