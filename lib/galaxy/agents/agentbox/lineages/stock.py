import threading

from distutils.version import LooseVersion

from .interface import AgentLineage
from .interface import AgentLineageVersion


class StockLineage(AgentLineage):
    """ Simple agent's loaded directly from file system with lineage
    determined solely by distutil's LooseVersion naming scheme.
    """
    lineages_by_id = {}
    lock = threading.Lock()

    def __init__(self, agent_id, **kwds):
        self.agent_id = agent_id
        self.agent_versions = set()

    @staticmethod
    def from_agent( agent ):
        agent_id = agent.id
        lineages_by_id = StockLineage.lineages_by_id
        with StockLineage.lock:
            if agent_id not in lineages_by_id:
                lineages_by_id[ agent_id ] = StockLineage( agent_id )
        lineage = lineages_by_id[ agent_id ]
        lineage.register_version( agent.version )
        return lineage

    def register_version( self, agent_version ):
        assert agent_version is not None
        self.agent_versions.add( agent_version )

    def get_versions( self, reverse=False ):
        versions = [ AgentLineageVersion( self.agent_id, v ) for v in self.agent_versions ]
        # Sort using LooseVersion which defines an appropriate __cmp__
        # method for comparing agent versions.
        return sorted( versions, key=_to_loose_version, reverse=reverse )

    def to_dict(self):
        return dict(
            agent_id=self.agent_id,
            agent_versions=list(self.agent_versions),
            lineage_type='stock',
        )


def _to_loose_version( agent_lineage_version ):
    version = str( agent_lineage_version.version )
    return LooseVersion( version )
