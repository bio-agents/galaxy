"""
Controller for integration with the Biostar application
"""

from galaxy.web.base.controller import BaseUIController, error, web
from galaxy.util import biostar


class BiostarController( BaseUIController ):
    """
    Provides integration with Biostar through external authentication, see: http://liondb.com/help/x/
    """

    @web.expose
    def biostar_redirect( self, trans, payload=None, biostar_action=None ):
        """
        Generate a redirect to a Biostar site using external authentication to
        pass Galaxy user information and optional information about a specific agent.
        """
        try:
            url, payload = biostar.get_biostar_url( trans.app, payload=payload, biostar_action=biostar_action )
        except Exception, e:
            return error( str( e ) )
        # Only create/log in biostar user if is registered Galaxy user
        if trans.user:
            biostar.create_cookie( trans, trans.app.config.biostar_key_name, trans.app.config.biostar_key, trans.user.email )
        if payload:
            return trans.fill_template( "biostar/post_redirect.mako", post_url=url, form_inputs=payload )
        return trans.response.send_redirect( url )

    @web.expose
    def biostar_agent_tag_redirect( self, trans, agent_id=None ):
        """
        Generate a redirect to a Biostar site using tag for agent.
        """
        # agent_id is required
        if agent_id is None:
            return error( "No agent_id provided" )
        # Load the agent
        agent_version_select_field, agents, agent = \
            self.app.agentbox.get_agent_components( agent_id, agent_version=None, get_loaded_agents_by_lineage=False, set_selected=True )
        # No matching agent, unlikely
        if not agent:
            return error( "No agent found matching '%s'" % agent_id )
        # Agent specific information for payload
        payload = biostar.populate_tag_payload( agent=agent )
        # Pass on to standard redirect method
        return self.biostar_redirect( trans, payload=payload, biostar_action='show_tags' )

    @web.expose
    def biostar_question_redirect( self, trans, payload=None ):
        """
        Generate a redirect to a Biostar site using external authentication to
        pass Galaxy user information and information about a specific agent.
        """
        # Pass on to standard redirect method
        return self.biostar_redirect( trans, payload=payload, biostar_action='new_post' )

    @web.expose
    def biostar_agent_question_redirect( self, trans, agent_id=None ):
        """
        Generate a redirect to a Biostar site using external authentication to
        pass Galaxy user information and information about a specific agent.
        """
        # agent_id is required
        if agent_id is None:
            return error( "No agent_id provided" )
        # Load the agent
        agent_version_select_field, agents, agent = \
            self.app.agentbox.get_agent_components( agent_id, agent_version=None, get_loaded_agents_by_lineage=False, set_selected=True )
        # No matching agent, unlikely
        if not agent:
            return error( "No agent found matching '%s'" % agent_id )
        # Agent specific information for payload
        payload = biostar.populate_agent_payload( agent=agent )
        # Pass on to regular question method
        return self.biostar_question_redirect( trans, payload )

    @web.expose
    def biostar_agent_bug_report( self, trans, hda=None, email=None, message=None ):
        """
        Generate a redirect to a Biostar site using external authentication to
        pass Galaxy user information and information about a specific agent error.
        """
        try:
            error_reporter = biostar.BiostarErrorReporter( hda, trans.app )
            payload = error_reporter.send_report( trans.user, email=email, message=message )
        except Exception, e:
            return error( str( e ) )
        return self.biostar_redirect( trans, payload=payload, biostar_action='new_post' )

    @web.expose
    def biostar_logout( self, trans ):
        """
        Log out of biostar
        """
        try:
            url = biostar.biostar_log_out( trans )
        except Exception, e:
            return error( str( e ) )
        if url:
            return trans.response.send_redirect( url )
        return error( "Could not determine Biostar logout URL." )
