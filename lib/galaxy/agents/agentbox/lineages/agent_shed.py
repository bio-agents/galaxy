from .interface import AgentLineage
from .interface import AgentLineageVersion

try:
    from galaxy.model.agent_shed_install import AgentVersion
except ImportError:
    AgentVersion = None


class AgentShedLineage(AgentLineage):
    """ Representation of agent lineage derived from agent shed repository
    installations. """

    def __init__(self, app, agent_version, agent_shed_repository=None):
        if AgentVersion is None:
            raise Exception("Agent shed models not present, can't create agent shed lineages.")
        self.app = app
        self.agent_version_id = agent_version.id
        # Only used for logging
        self._agent_shed_repository = agent_shed_repository

    @staticmethod
    def from_agent( app, agent, agent_shed_repository ):
        # Make sure the agent has a agent_version.
        if not get_install_agent_version( app, agent.id ):
            agent_version = AgentVersion( agent_id=agent.id, agent_shed_repository=agent_shed_repository )
            app.install_model.context.add( agent_version )
            app.install_model.context.flush()
        return AgentShedLineage( app, agent.agent_version )

    @staticmethod
    def from_agent_id( app, agent_id ):
        agent_version = get_install_agent_version( app, agent_id )
        if agent_version:
            return AgentShedLineage( app, agent_version )
        else:
            return None

    def get_version_ids( self, reverse=False ):
        agent_version = self.app.install_model.context.query( AgentVersion ).get( self.agent_version_id )
        return agent_version.get_version_ids( self.app, reverse=reverse )

    def get_versions( self, reverse=False ):
        return map( AgentLineageVersion.from_guid, self.get_version_ids( reverse=reverse ) )

    def to_dict(self):
        agent_shed_repository = self._agent_shed_repository
        rval = dict(
            agent_version_id=self.agent_version_id,
            agent_versions=map(lambda v: v.to_dict(), self.get_versions()),
            agent_shed_repository=agent_shed_repository if agent_shed_repository is not None else None,
            lineage_type='agent_shed',
        )
        return rval


def get_install_agent_version( app, agent_id ):
    return app.install_model.context.query(
        app.install_model.AgentVersion
    ).filter(
        app.install_model.AgentVersion.table.c.agent_id == agent_id
    ).first()

__all__ = [ "AgentShedLineage" ]
