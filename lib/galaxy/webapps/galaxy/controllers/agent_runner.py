"""
Controller handles external agent related requests
"""
import logging

from markupsafe import escape

import galaxy.util
from galaxy import web
from galaxy.agents import DataSourceAgent
from galaxy.web import error, url_for
from galaxy.web.base.controller import BaseUIController

log = logging.getLogger( __name__ )


class AgentRunner( BaseUIController ):

    # Hack to get biomart to work, ideally, we could pass agent_id to biomart and receive it back
    @web.expose
    def biomart(self, trans, agent_id='biomart', **kwd):
        """Catches the agent id and redirects as needed"""
        return self.index(trans, agent_id=agent_id, **kwd)

    # test to get hapmap to work, ideally, we could pass agent_id to hapmap biomart and receive it back
    @web.expose
    def hapmapmart(self, trans, agent_id='hapmapmart', **kwd):
        """Catches the agent id and redirects as needed"""
        return self.index(trans, agent_id=agent_id, **kwd)

    @web.expose
    def default(self, trans, agent_id=None, **kwd):
        """Catches the agent id and redirects as needed"""
        return self.index(trans, agent_id=agent_id, **kwd)

    def __get_agent( self, agent_id, agent_version=None, get_loaded_agents_by_lineage=False, set_selected=False ):
        agent_version_select_field, agents, agent = self.get_agentbox().get_agent_components( agent_id, agent_version, get_loaded_agents_by_lineage, set_selected )
        return agent

    @web.expose
    def index( self, trans, agent_id=None, from_noframe=None, **kwd ):
        # agent id not available, redirect to main page
        if agent_id is None:
            return trans.response.send_redirect( url_for( controller='root', action='welcome' ) )
        agent = self.__get_agent( agent_id )
        # agent id is not matching, display an error
        if not agent or not agent.allow_user_access( trans.user ):
            log.error( 'index called with agent id \'%s\' but no such agent exists', agent_id )
            trans.log_event( 'Agent id \'%s\' does not exist' % agent_id )
            trans.response.status = 404
            return trans.show_error_message('Agent \'%s\' does not exist.' % ( escape(agent_id) ))
        if agent.require_login and not trans.user:
            redirect = url_for( controller='agent_runner', action='index', agent_id=agent_id, **kwd )
            return trans.response.send_redirect( url_for( controller='user',
                                                          action='login',
                                                          cntrller='user',
                                                          status='info',
                                                          message='You must be logged in to use this agent.',
                                                          redirect=redirect ) )
        if agent.agent_type == 'default':
            return trans.response.send_redirect( url_for( controller='root', agent_id=agent_id ) )

        # execute agent without displaying form (used for datasource agents)
        params = galaxy.util.Params( kwd, sanitize=False )
        # do param translation here, used by datasource agents
        if agent.input_translator:
            agent.input_translator.translate( params )
        # We may be visiting Galaxy for the first time ( e.g., sending data from UCSC ),
        # so make sure to create a new history if we've never had one before.
        history = agent.get_default_history_by_trans( trans, create=True )
        try:
            vars = agent.handle_input( trans, params.__dict__, history=history )
        except Exception, e:
            error( str( e ) )
        if len( params ) > 0:
            trans.log_event( 'Agent params: %s' % ( str( params ) ), agent_id=agent_id )
        return trans.fill_template( 'root/agent_runner.mako', **vars )

    @web.expose
    def rerun( self, trans, id=None, job_id=None, **kwd ):
        """
        Given a HistoryDatasetAssociation id, find the job and that created
        the dataset, extract the parameters, and display the appropriate agent
        form with parameters already filled in.
        """
        if job_id is None:
            if not id:
                error( "'id' parameter is required" )
            try:
                id = int( id )
            except:
                # it's not an un-encoded id, try to parse as encoded
                try:
                    id = trans.security.decode_id( id )
                except:
                    error( "Invalid value for 'id' parameter" )
            # Get the dataset object
            data = trans.sa_session.query( trans.app.model.HistoryDatasetAssociation ).get( id )
            # only allow rerunning if user is allowed access to the dataset.
            if not ( trans.user_is_admin() or trans.app.security_agent.can_access_dataset( trans.get_current_user_roles(), data.dataset ) ):
                error( "You are not allowed to access this dataset" )
            # Get the associated job, if any.
            job = data.creating_job
            if job:
                job_id = trans.security.encode_id( job.id )
            else:
                raise Exception("Failed to get job information for dataset hid %d" % data.hid)
        return trans.response.send_redirect( url_for( controller="root", job_id=job_id ) )

    @web.expose
    def data_source_redirect( self, trans, agent_id=None ):
        """
        Redirects a user accessing a Data Source agent to its target action link.
        This method will subvert mix-mode content blocking in several browsers when
        accessing non-https data_source agents from an https galaxy server.

        Tested as working on Safari 7.0 and FireFox 26
        Subverting did not work on Chrome 31
        """
        if agent_id is None:
            return trans.response.send_redirect( url_for( controller="root", action="welcome" ) )
        agent = self.__get_agent( agent_id )
        # No agent matching the agent id, display an error (shouldn't happen)
        if not agent:
            log.error( "data_source_redirect called with agent id '%s' but no such agent exists", agent_id )
            trans.log_event( "Agent id '%s' does not exist" % agent_id )
            trans.response.status = 404
            return trans.show_error_message("Agent '%s' does not exist." % ( escape(agent_id) ))

        if isinstance( agent, DataSourceAgent ):
            link = url_for( agent.action, **agent.get_static_param_values( trans ) )
        else:
            link = url_for( controller='agent_runner', agent_id=agent.id )
        return trans.response.send_redirect( link )

    @web.expose
    def redirect( self, trans, redirect_url=None, **kwd ):
        if not redirect_url:
            return trans.show_error_message( "Required URL for redirection missing" )
        trans.log_event( "Redirecting to: %s" % redirect_url )
        return trans.fill_template( 'root/redirect.mako', redirect_url=redirect_url )
