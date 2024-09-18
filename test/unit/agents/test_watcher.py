from contextlib import contextmanager
from os import path
from shutil import rmtree
import tempfile
import time

from galaxy.agents.agentbox import watcher
from galaxy.util import bunch


def test_watcher():
    if not watcher.can_watch:
        from nose.plugins.skip import SkipTest
        raise SkipTest()

    with __test_directory() as t:
        agent_path = path.join(t, "test.xml")
        agentbox = Agentbox()
        open(agent_path, "w").write("a")
        agent_watcher = watcher.get_agent_watcher(agentbox, bunch.Bunch(
            watch_agents=True
        ))
        agent_watcher.watch_file(agent_path, "cool_agent")
        assert not agentbox.was_reloaded("cool_agent")
        open(agent_path, "w").write("b")
        wait_for_reload(lambda: agentbox.was_reloaded("cool_agent"))
        agent_watcher.shutdown()
        assert not agent_watcher.observer.is_alive()


def test_agent_conf_watcher():
    if not watcher.can_watch:
        from nose.plugins.skip import SkipTest
        raise SkipTest()

    callback = CallbackRecorder()
    conf_watcher = watcher.get_agent_conf_watcher(callback.call)

    with __test_directory() as t:
        agent_conf_path = path.join(t, "test_conf.xml")
        conf_watcher.watch_file(agent_conf_path)

        open(agent_conf_path, "w").write("b")
        wait_for_reload(lambda: callback.called)
        conf_watcher.shutdown()
        assert not conf_watcher.thread.is_alive()


def wait_for_reload(check):
    reloaded = False
    for i in range(10):
        reloaded = check()
        if reloaded:
            break
        time.sleep(.2)
    assert reloaded


class Agentbox(object):

    def __init__(self):
        self.reloaded = {}

    def reload_agent_by_id( self, agent_id ):
        self.reloaded[ agent_id ] = True

    def was_reloaded(self, agent_id):
        return self.reloaded.get( agent_id, False )


class CallbackRecorder(object):

    def __init__(self):
        self.called = False

    def call(self):
        self.called = True


@contextmanager
def __test_directory():
    base_path = tempfile.mkdtemp()
    try:
        yield base_path
    finally:
        rmtree(base_path)
