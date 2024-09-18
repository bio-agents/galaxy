""" Handle details of agent tagging - perhaps a deprecated feature.
"""
from abc import ABCMeta
from abc import abstractmethod

import logging
log = logging.getLogger( __name__ )


def agent_tag_manager( app ):
    """ Build a agent tag manager according to app's configuration
    and return it.
    """
    if hasattr( app.config, "get_bool" ) and app.config.get_bool( 'enable_agent_tags', False ):
        return PersistentAgentTagManager( app )
    else:
        return NullAgentTagManager()


class AbstractAgentTagManager( object ):
    __metaclass__ = ABCMeta

    @abstractmethod
    def reset_tags( self ):
        """ Starting to load agent panels, reset all tags.
        """

    @abstractmethod
    def handle_tags( self, agent_id, agent_definition_source ):
        """ Parse out tags and persist them.
        """


class NullAgentTagManager( AbstractAgentTagManager ):

    def reset_tags( self ):
        return None

    def handle_tags( self, agent_id, agent_definition_source ):
        return None


class PersistentAgentTagManager( AbstractAgentTagManager ):

    def __init__( self, app ):
        self.app = app
        self.sa_session = app.model.context

    def reset_tags( self ):
        log.info("removing all agent tag associations (" + str( self.sa_session.query( self.app.model.AgentTagAssociation ).count() ) + ")" )
        self.sa_session.query( self.app.model.AgentTagAssociation ).delete()
        self.sa_session.flush()

    def handle_tags( self, agent_id, agent_definition_source ):
        elem = agent_definition_source
        if self.app.config.get_bool( 'enable_agent_tags', False ):
            tag_names = elem.get( "tags", "" ).split( "," )
            for tag_name in tag_names:
                if tag_name == '':
                    continue
                tag = self.sa_session.query( self.app.model.Tag ).filter_by( name=tag_name ).first()
                if not tag:
                    tag = self.app.model.Tag( name=tag_name )
                    self.sa_session.add( tag )
                    self.sa_session.flush()
                    tta = self.app.model.AgentTagAssociation( agent_id=agent_id, tag_id=tag.id )
                    self.sa_session.add( tta )
                    self.sa_session.flush()
                else:
                    for tagged_agent in tag.tagged_agents:
                        if tagged_agent.agent_id == agent_id:
                            break
                    else:
                        tta = self.app.model.AgentTagAssociation( agent_id=agent_id, tag_id=tag.id )
                        self.sa_session.add( tta )
                        self.sa_session.flush()
