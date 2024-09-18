import logging
import urllib2

from galaxy.util.odict import odict
from agent_shed.util import common_util, xml_util

log = logging.getLogger( __name__ )


class Registry( object ):

    def __init__( self, root_dir=None, config=None ):
        self.agent_sheds = odict()
        self.agent_sheds_auth = odict()
        if root_dir and config:
            # Parse agent_sheds_conf.xml
            tree, error_message = xml_util.parse_xml( config )
            if tree is None:
                log.warning( "Unable to load references to agent sheds defined in file %s" % str( config ) )
            else:
                root = tree.getroot()
                log.debug( 'Loading references to agent sheds from %s' % config )
                for elem in root.findall( 'agent_shed' ):
                    try:
                        name = elem.get( 'name', None )
                        url = elem.get( 'url', None )
                        username = elem.get( 'user', None )
                        password = elem.get( 'pass', None )
                        if name and url:
                            self.agent_sheds[ name ] = url
                            self.agent_sheds_auth[ name ] = None
                            log.debug( 'Loaded reference to agent shed: %s' % name )
                        if name and url and username and password:
                            pass_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
                            pass_mgr.add_password( None, url, username, password )
                            self.agent_sheds_auth[ name ] = pass_mgr
                    except Exception, e:
                        log.warning( 'Error loading reference to agent shed "%s", problem: %s' % ( name, str( e ) ) )

    def password_manager_for_url( self, url ):
        """
        If the agent shed is using external auth, the client to the agent shed must authenticate to that
        as well.  This provides access to the urllib2.HTTPPasswordMgrWithdefaultRealm() object for the
        url passed in.

        Following more what galaxy.demo_sequencer.controllers.common does might be more appropriate at
        some stage...
        """
        url_sans_protocol = common_util.remove_protocol_from_agent_shed_url( url )
        for shed_name, shed_url in self.agent_sheds.items():
            shed_url_sans_protocol = common_util.remove_protocol_from_agent_shed_url( shed_url )
            if shed_url_sans_protocol.find( url_sans_protocol ) >= 0:
                return self.agent_sheds_auth[ shed_name ]
        log.debug( "Invalid url '%s' received by agent shed registry's password_manager_for_url method." % str( url ) )
        return None
