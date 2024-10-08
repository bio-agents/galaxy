import logging
from galaxy import web
from galaxy.web.base.controller import BaseUIController

log = logging.getLogger( __name__ )


class Group( BaseUIController ):

    @web.expose
    def index( self, trans, **kwd ):
        # define app configuration for generic mako template
        app = {
            'jscript'       : "../agentshed/scripts/agentshed.groups"
        }
        return trans.fill_template( '/webapps/agent_shed/group/index.mako',
                                    config={
                                        'title': 'Agent Shed Groups',
                                        'app': app } )
