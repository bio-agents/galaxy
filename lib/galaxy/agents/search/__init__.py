"""
Module for building and searching the index of agents
installed within this Galaxy.
"""
from galaxy.web.framework.helpers import to_unicode

from whoosh.filedb.filestore import RamStorage
from whoosh.fields import KEYWORD, Schema, STORED, TEXT
from whoosh.scoring import BM25F
from whoosh.qparser import MultifieldParser
schema = Schema( id=STORED,
                 name=TEXT,
                 description=TEXT,
                 section=TEXT,
                 help=TEXT,
                 labels=KEYWORD )
import logging
log = logging.getLogger( __name__ )


class AgentBoxSearch( object ):
    """
    Support searching agents in a agentbox. This implementation uses
    the Whoosh search library.
    """

    def __init__( self, agentbox, index_help=True ):
        """
        Create a searcher for `agentbox`.
        """
        self.agentbox = agentbox
        self.build_index( index_help )

    def build_index( self, index_help=True ):
        log.debug( 'Starting to build agentbox index.' )
        self.storage = RamStorage()
        self.index = self.storage.create_index( schema )
        writer = self.index.writer()
        for id, agent in self.agentbox.agents():
            #  Do not add data managers to the public index
            if agent.agent_type == 'manage_data':
                continue
            add_doc_kwds = {
                "id": id,
                "name": to_unicode( agent.name ),
                "description": to_unicode( agent.description ),
                "section": to_unicode( agent.get_panel_section()[1] if len( agent.get_panel_section() ) == 2 else '' ),
                "help": to_unicode( "" )
            }
            if agent.labels:
                add_doc_kwds['labels'] = to_unicode( " ".join( agent.labels ) )
            if index_help and agent.help:
                try:
                    add_doc_kwds['help'] = to_unicode( agent.help.render( host_url="", static_path="" ) )
                except Exception:
                    # Don't fail to build index just because a help message
                    # won't render.
                    pass
            writer.add_document( **add_doc_kwds )
        writer.commit()
        log.debug( 'Agentbox index finished.' )

    def search( self, q, agent_name_boost, agent_section_boost, agent_description_boost, agent_help_boost, agent_search_limit ):
        """
        Perform search on the in-memory index. Weight in the given boosts.
        """
        # Change field boosts for searcher
        searcher = self.index.searcher(
            weighting=BM25F(
                field_B={ 'name_B': float( agent_name_boost ),
                          'section_B': float( agent_section_boost ),
                          'description_B': float( agent_description_boost ),
                          'help_B': float( agent_help_boost ) }
            )
        )
        # Set query to search name, description, section, help, and labels.
        parser = MultifieldParser( [ 'name', 'description', 'section', 'help', 'labels' ], schema=schema )
        # Perform the search
        hits = searcher.search( parser.parse( '*' + q + '*' ), limit=float( agent_search_limit ) )
        return [ hit[ 'id' ] for hit in hits ]
