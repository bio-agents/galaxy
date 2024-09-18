import logging
import os.path
import threading
import time

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
    from watchdog.observers.polling import PollingObserver
    can_watch = True
except ImportError:
    Observer = None
    FileSystemEventHandler = object
    PollingObserver = None
    can_watch = False

log = logging.getLogger( __name__ )


def get_observer_class(config_value, default, monitor_what_str):
    """
    """
    config_value = config_value or default
    config_value = str(config_value).lower()
    if config_value in ("true", "yes", "on", "auto"):
        expect_observer = config_value != "auto"
        observer_class = Observer
    elif config_value == "polling":
        expect_observer = True
        observer_class = PollingObserver
    else:
        expect_observer = False
        observer_class = None

    if observer_class is None:
        message = "Watchdog library unavailble, cannot monitor %s." % monitor_what_str
        log.info(message)
        if expect_observer:
            raise Exception(message)

    return observer_class


def get_agent_conf_watcher(reload_callback):
    return AgentConfWatcher(reload_callback)


def get_agent_watcher(agentbox, config):
    config_value = getattr(config, "watch_agents", None)
    observer_class = get_observer_class(config_value, default="False", monitor_what_str="agents")

    if observer_class is not None:
        return AgentWatcher(agentbox, observer_class=observer_class)
    else:
        return NullWatcher()


class AgentConfWatcher(object):

    def __init__(self, reload_callback):
        self.paths = {}
        self._active = False
        self._lock = threading.Lock()
        self.thread = threading.Thread(target=self.check)
        self.thread.daemon = True
        self.event_handler = AgentConfFileEventHandler(reload_callback)

    def start(self):
        if not self._active:
            self._active = True
            self.thread.start()

    def shutdown(self):
        if self._active:
            self._active = False
            self.thread.join()

    def check(self):
        while self._active:
            do_reload = False
            with self._lock:
                paths = list(self.paths.keys())
            for path in paths:
                if not os.path.exists(path):
                    continue
                mod_time = self.paths[path]
                new_mod_time = None
                if os.path.exists(path):
                    new_mod_time = time.ctime(os.path.getmtime(path))
                if new_mod_time != mod_time:
                    self.paths[path] = new_mod_time
                    do_reload = True

            if do_reload:
                t = threading.Thread(target=lambda: self.event_handler.on_any_event(None))
                t.daemon = True
                t.start()
            time.sleep(1)

    def monitor(self, path):
        mod_time = None
        if os.path.exists(path):
            mod_time = time.ctime(os.path.getmtime(path))
        with self._lock:
            self.paths[path] = mod_time
        self.start()

    def watch_file(self, agent_conf_file):
        self.monitor(agent_conf_file)


class NullAgentConfWatcher(object):

    def start(self):
        pass

    def shutdown(self):
        pass

    def monitor(self, conf_path):
        pass

    def watch_file(self, agent_file, agent_id):
        pass


class AgentConfFileEventHandler(FileSystemEventHandler):

    def __init__(self, reload_callback):
        self.reload_callback = reload_callback

    def on_any_event(self, event):
        self._handle(event)

    def _handle(self, event):
        self.reload_callback()


class AgentWatcher(object):

    def __init__(self, agentbox, observer_class):
        self.agentbox = agentbox
        self.agent_file_ids = {}
        self.agent_dir_callbacks = {}
        self.monitored_dirs = {}
        self.observer = observer_class()
        self.event_handler = AgentFileEventHandler(self)
        self.start()

    def start(self):
        self.observer.start()

    def shutdown(self):
        self.observer.stop()
        self.observer.join()

    def monitor(self, dir):
        self.observer.schedule(self.event_handler, dir, recursive=False)

    def watch_file(self, agent_file, agent_id):
        agent_file = os.path.abspath( agent_file )
        self.agent_file_ids[agent_file] = agent_id
        agent_dir = os.path.dirname( agent_file )
        if agent_dir not in self.monitored_dirs:
            self.monitored_dirs[ agent_dir ] = agent_dir
            self.monitor( agent_dir )

    def watch_directory(self, agent_dir, callback):
        agent_dir = os.path.abspath( agent_dir )
        self.agent_dir_callbacks[agent_dir] = callback
        if agent_dir not in self.monitored_dirs:
            self.monitored_dirs[ agent_dir ] = agent_dir
            self.monitor( agent_dir )


class AgentFileEventHandler(FileSystemEventHandler):

    def __init__(self, agent_watcher):
        self.agent_watcher = agent_watcher

    def on_any_event(self, event):
        self._handle(event)

    def _handle(self, event):
        # modified events will only have src path, move events will
        # have dest_path and src_path but we only care about dest. So
        # look at dest if it exists else use src.
        path = getattr( event, 'dest_path', None ) or event.src_path
        path = os.path.abspath( path )
        agent_id = self.agent_watcher.agent_file_ids.get( path, None )
        if agent_id:
            try:
                self.agent_watcher.agentbox.reload_agent_by_id(agent_id)
            except Exception:
                pass
        elif path.endswith(".xml"):
            directory = os.path.dirname( path )
            dir_callback = self.agent_watcher.agent_dir_callbacks.get( directory, None )
            if dir_callback:
                agent_file = event.src_path
                agent_id = dir_callback( agent_file )
                if agent_id:
                    self.agent_watcher.agent_file_ids[ agent_file ] = agent_id


class NullWatcher(object):

    def start(self):
        pass

    def shutdown(self):
        pass

    def watch_file(self, agent_file, agent_id):
        pass

    def watch_directory(self, agent_dir, callback):
        pass
