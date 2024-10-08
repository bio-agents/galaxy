from abc import ABCMeta
from abc import abstractmethod


class AgentLineage(object):
    """
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def get_versions( self, reverse=False ):
        """ Return an ordered list of lineages (AgentLineageVersion) in this
        chain, from oldest to newest.
        """


class AgentLineageVersion(object):
    """ Represents a single agent in a lineage. If lineage is based
    around GUIDs that somehow encode the version (either using GUID
    or a simple agent id and a version). """

    def __init__(self, id, version):
        self.id = id
        self.version = version

    @staticmethod
    def from_id_and_verion( id, version ):
        assert version is not None
        return AgentLineageVersion( id, version )

    @staticmethod
    def from_guid( guid ):
        return AgentLineageVersion( guid, None )

    @property
    def id_based( self ):
        """ Return True if the lineage is defined by GUIDs (in this
        case the indexer of the agents (i.e. the AgentBox) should ignore
        the agent_version (because it is encoded in the GUID and managed
        externally).
        """
        return self.version is None

    def to_dict(self):
        return dict(
            id=self.id,
            version=self.version,
        )
