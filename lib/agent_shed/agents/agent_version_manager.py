import logging

from sqlalchemy import and_, or_

from agent_shed.util import hg_util
from agent_shed.util import shed_util_common as suc

log = logging.getLogger( __name__ )


class AgentVersionManager( object ):

    def __init__( self, app ):
        self.app = app

    def get_agent_version( self, agent_id ):
        context = self.app.install_model.context
        return context.query( self.app.install_model.AgentVersion ) \
                      .filter( self.app.install_model.AgentVersion.table.c.agent_id == agent_id ) \
                      .first()

    def get_agent_version_association( self, parent_agent_version, agent_version ):
        """
        Return a AgentVersionAssociation if one exists that associates the two
        received agent_versions. This function is called only from Galaxy.
        """
        context = self.app.install_model.context
        return context.query( self.app.install_model.AgentVersionAssociation ) \
                      .filter( and_( self.app.install_model.AgentVersionAssociation.table.c.parent_id == parent_agent_version.id,
                                     self.app.install_model.AgentVersionAssociation.table.c.agent_id == agent_version.id ) ) \
                      .first()

    def get_version_lineage_for_agent( self, repository_id, repository_metadata, guid ):
        """
        Return the agent version lineage chain in descendant order for the received
        guid contained in the received repsitory_metadata.agent_versions.  This function
        is called only from the Agent Shed.
        """
        repository = suc.get_repository_by_id( self.app, repository_id )
        repo = hg_util.get_repo_for_repository( self.app, repository=repository, repo_path=None, create=False )
        # Initialize the agent lineage
        version_lineage = [ guid ]
        # Get all ancestor guids of the received guid.
        current_child_guid = guid
        for changeset in hg_util.reversed_upper_bounded_changelog( repo, repository_metadata.changeset_revision ):
            ctx = repo.changectx( changeset )
            rm = suc.get_repository_metadata_by_changeset_revision( self.app, repository_id, str( ctx ) )
            if rm:
                parent_guid = rm.agent_versions.get( current_child_guid, None )
                if parent_guid:
                    version_lineage.append( parent_guid )
                    current_child_guid = parent_guid
        # Get all descendant guids of the received guid.
        current_parent_guid = guid
        for changeset in hg_util.reversed_lower_upper_bounded_changelog( repo,
                                                                         repository_metadata.changeset_revision,
                                                                         repository.tip( self.app ) ):
            ctx = repo.changectx( changeset )
            rm = suc.get_repository_metadata_by_changeset_revision( self.app, repository_id, str( ctx ) )
            if rm:
                agent_versions = rm.agent_versions
                for child_guid, parent_guid in agent_versions.items():
                    if parent_guid == current_parent_guid:
                        version_lineage.insert( 0, child_guid )
                        current_parent_guid = child_guid
                        break
        return version_lineage

    def handle_agent_versions( self, agent_version_dicts, agent_shed_repository ):
        """
        Using the list of agent_version_dicts retrieved from the Agent Shed (one per changeset
        revision up to the currently installed changeset revision), create the parent / child
        pairs of agent versions.  Each dictionary contains { agent id : parent agent id } pairs.
        This function is called only from Galaxy.
        """
        context = self.app.install_model.context
        for agent_version_dict in agent_version_dicts:
            for agent_guid, parent_id in agent_version_dict.items():
                agent_version_using_agent_guid = self.get_agent_version( agent_guid )
                agent_version_using_parent_id = self.get_agent_version( parent_id )
                if not agent_version_using_agent_guid:
                    agent_version_using_agent_guid = \
                        self.app.install_model.AgentVersion( agent_id=agent_guid,
                                                            agent_shed_repository=agent_shed_repository )
                    context.add( agent_version_using_agent_guid )
                    context.flush()
                if not agent_version_using_parent_id:
                    agent_version_using_parent_id = \
                        self.app.install_model.AgentVersion( agent_id=parent_id,
                                                            agent_shed_repository=agent_shed_repository )
                    context.add( agent_version_using_parent_id )
                    context.flush()
                # Remove existing wrong agent version associations having
                # agent_version_using_parent_id as parent or
                # agent_version_using_agent_guid as child.
                context.query( self.app.install_model.AgentVersionAssociation ) \
                       .filter( or_( and_( self.app.install_model.AgentVersionAssociation.table.c.parent_id == agent_version_using_parent_id.id,
                                           self.app.install_model.AgentVersionAssociation.table.c.agent_id != agent_version_using_agent_guid.id ),
                                     and_( self.app.install_model.AgentVersionAssociation.table.c.parent_id != agent_version_using_parent_id.id,
                                           self.app.install_model.AgentVersionAssociation.table.c.agent_id == agent_version_using_agent_guid.id ) ) ) \
                       .delete()
                context.flush()
                agent_version_association = \
                    self.get_agent_version_association( agent_version_using_parent_id,
                                                       agent_version_using_agent_guid )
                if not agent_version_association:
                    # Associate the two versions as parent / child.
                    agent_version_association = \
                        self.app.install_model.AgentVersionAssociation( agent_id=agent_version_using_agent_guid.id,
                                                                       parent_id=agent_version_using_parent_id.id )
                    context.add( agent_version_association )
                    context.flush()
