

class AgentCache(object):
    """ Cache agent defintions to allow quickly reloading the whole
    agentbox.
    """

    def __init__(self):
        self._agents_by_path = {}
        self._agent_paths_by_id = {}

    def get_agent(self, config_filename):
        """ Get the agent from the cache if the agent is up to date.
        """
        return self._agents_by_path.get(config_filename, None)

    def expire_agent(self, agent_id):
        if agent_id in self._agent_paths_by_id:
            config_filename = self._agent_paths_by_id[agent_id]
            del self._agent_paths_by_id[agent_id]
            del self._agents_by_path[config_filename]

    def cache_agent(self, config_filename, agent):
        agent_id = str( agent.id )
        self._agent_paths_by_id[agent_id] = config_filename
        self._agents_by_path[config_filename] = agent
