import json
import logging
from collections import namedtuple
from galaxy import web
from galaxy import util
from galaxy.web import _future_expose_api_raw_anonymous_and_sessionless as expose_api_raw_anonymous_and_sessionless
from galaxy.web.base.controller import BaseAPIController
from galaxy.webapps.agent_shed.search.agent_search import AgentSearch
from galaxy.exceptions import NotImplemented
from galaxy.exceptions import RequestParameterInvalidException
from galaxy.exceptions import ConfigDoesNotAllowException

log = logging.getLogger( __name__ )


class AgentsController( BaseAPIController ):
    """RESTful controller for interactions with agents in the Agent Shed."""

    @expose_api_raw_anonymous_and_sessionless
    def index( self, trans, **kwd ):
        """
        GET /api/agents
        Displays a collection of agents with optional criteria.

        :param q:        (optional)if present search on the given query will be performed
        :type  q:        str

        :param page:     (optional)requested page of the search
        :type  page:     int

        :param page_size:     (optional)requested page_size of the search
        :type  page_size:     int

        :param jsonp:    (optional)flag whether to use jsonp format response, defaults to False
        :type  jsonp:    bool

        :param callback: (optional)name of the function to wrap callback in
                         used only when jsonp is true, defaults to 'callback'
        :type  callback: str

        :returns dict:   object containing list of results and metadata

        Examples:
            GET http://localhost:9009/api/agents
            GET http://localhost:9009/api/agents?q=fastq
        """
        q = kwd.get( 'q', '' )
        if not q:
            raise NotImplemented( 'Listing of all the agents is not implemented. Provide parameter "q" to search instead.' )
        else:
            page = kwd.get( 'page', 1 )
            page_size = kwd.get( 'page_size', 10 )
            try:
                page = int( page )
                page_size = int( page_size )
            except ValueError:
                raise RequestParameterInvalidException( 'The "page" and "page_size" have to be integers.' )
            return_jsonp = util.asbool( kwd.get( 'jsonp', False ) )
            callback = kwd.get( 'callback', 'callback' )
            search_results = self._search( trans, q, page, page_size )
            if return_jsonp:
                response = str( '%s(%s);' % ( callback, json.dumps( search_results ) ) )
            else:
                response = json.dumps( search_results )
            return response

    def _search( self, trans, q, page=1, page_size=10 ):
        """
        Perform the search over TS agents index.
        Note that search works over the Whoosh index which you have
        to pre-create with scripts/agent_shed/build_ts_whoosh_index.sh manually.
        Also TS config option agentshed_search_on has to be True and
        whoosh_index_dir has to be specified.
        """
        conf = self.app.config
        if not conf.agentshed_search_on:
            raise ConfigDoesNotAllowException( 'Searching the TS through the API is turned off for this instance.' )
        if not conf.whoosh_index_dir:
            raise ConfigDoesNotAllowException( 'There is no directory for the search index specified. Please contact the administrator.' )
        search_term = q.strip()
        if len( search_term ) < 3:
            raise RequestParameterInvalidException( 'The search term has to be at least 3 characters long.' )

        agent_search = AgentSearch()

        Boosts = namedtuple( 'Boosts', [ 'agent_name_boost',
                                         'agent_description_boost',
                                         'agent_help_boost',
                                         'agent_repo_owner_username_boost' ] )
        boosts = Boosts( float( conf.get( 'agent_name_boost', 1.2 ) ),
                         float( conf.get( 'agent_description_boost', 0.6 ) ),
                         float( conf.get( 'agent_help_boost', 0.4 ) ),
                         float( conf.get( 'agent_repo_owner_username_boost', 0.3 ) ) )

        results = agent_search.search( trans,
                                      search_term,
                                      page,
                                      page_size,
                                      boosts )
        results[ 'hostname' ] = web.url_for( '/', qualified=True )
        return results
