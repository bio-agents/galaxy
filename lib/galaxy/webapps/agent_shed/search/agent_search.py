"""Module for searching the agentshed agents within all repositories"""
import os
import logging
from galaxy import exceptions
from galaxy.exceptions import ObjectNotFound
import whoosh.index
from whoosh import scoring
from whoosh.fields import Schema, STORED, TEXT
from whoosh.qparser import MultifieldParser

log = logging.getLogger( __name__ )

agent_schema = Schema(
    name=TEXT( stored=True ),
    description=TEXT( stored=True ),
    owner=TEXT( stored=True ),
    id=TEXT( stored=True ),
    help=TEXT( stored=True ),
    version=TEXT( stored=True),
    repo_name=TEXT( stored=True ),
    repo_owner_username=TEXT( stored=True ),
    repo_id=STORED )


class AgentSearch( object ):

    def search( self, trans, search_term, page, page_size, boosts ):
        """
        Perform the search on the given search_term

        :param search_term: unicode encoded string with the search term(s)

        :returns results: dictionary containing number of hits, hits themselves and matched terms for each
        """
        agent_index_dir = os.path.join( trans.app.config.whoosh_index_dir, 'agents' )
        index_exists = whoosh.index.exists_in( agent_index_dir )
        if index_exists:
            index = whoosh.index.open_dir( agent_index_dir )
            try:
                # Some literature about BM25F:
                # http://trec.nist.gov/pubs/trec13/papers/microsoft-cambridge.web.hard.pdf
                # http://en.wikipedia.org/wiki/Okapi_BM25
                # __Basically__ the higher number the bigger weight.
                agent_weighting = scoring.BM25F( field_B={
                                                'name_B' : boosts.agent_name_boost,
                                                'description_B' : boosts.agent_description_boost,
                                                'help_B' : boosts.agent_help_boost,
                                                'repo_owner_username_B' : boosts.agent_repo_owner_username_boost } )
                searcher = index.searcher( weighting=agent_weighting )

                parser = MultifieldParser( [
                    'name',
                    'description',
                    'help',
                    'repo_owner_username' ], schema=agent_schema )

                user_query = parser.parse( '*' + search_term + '*' )

                try:
                    hits = searcher.search_page( user_query, page, pagelen=page_size, terms=True )
                except ValueError:
                    raise ObjectNotFound( 'The requested page does not exist.' )

                log.debug( 'searching agents for: #' + str( search_term ) )
                log.debug( 'total hits: ' + str( len( hits ) ) )
                log.debug( 'scored hits: ' + str( hits.scored_length() ) )
                results = {}
                results[ 'total_results'] = str( len( hits ) )
                results[ 'page'] = str( page )
                results[ 'page_size'] = str( page_size )
                results[ 'hits' ] = []
                for hit in hits:
                    hit_dict = {}
                    hit_dict[ 'id' ] = hit.get( 'id' )
                    hit_dict[ 'repo_owner_username' ] = hit.get( 'repo_owner_username' )
                    hit_dict[ 'repo_name' ] = hit.get( 'repo_name' )
                    hit_dict[ 'name' ] = hit.get( 'name' )
                    hit_dict[ 'description' ] = hit.get( 'description' )
                    results[ 'hits' ].append( {'agent': hit_dict, 'matched_terms': hit.matched_terms(), 'score': hit.score } )
                return results
            finally:
                searcher.close()
        else:
            raise exceptions.InternalServerError( 'The search index file is missing.' )
