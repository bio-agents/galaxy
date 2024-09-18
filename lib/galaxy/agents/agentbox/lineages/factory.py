from .agent_shed import AgentShedLineage
from .stock import StockLineage


class LineageMap(object):
    """ Map each unique agent id to a lineage object.
    """

    def __init__(self, app):
        self.lineage_map = {}
        self.app = app

    def register(self, agent, **kwds):
        agent_id = agent.id
        if agent_id not in self.lineage_map:
            agent_shed_repository = kwds.get("agent_shed_repository", None)
            if agent_shed_repository:
                lineage = AgentShedLineage.from_agent(self.app, agent, agent_shed_repository)
            else:
                lineage = StockLineage.from_agent( agent )
            self.lineage_map[agent_id] = lineage
        return self.lineage_map[agent_id]

    def get(self, agent_id):
        if agent_id not in self.lineage_map:
            lineage = AgentShedLineage.from_agent_id( self.app, agent_id )
            if lineage:
                self.lineage_map[agent_id] = lineage

        return self.lineage_map.get(agent_id, None)

__all__ = ["LineageMap"]
