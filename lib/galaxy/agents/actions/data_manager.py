from __init__ import DefaultAgentAction

import logging
log = logging.getLogger( __name__ )


class DataManagerAgentAction( DefaultAgentAction ):
    """Agent action used for Data Manager Agents"""

    def execute( self, agent, trans, **kwds ):
        rval = super( DataManagerAgentAction, self ).execute( agent, trans, **kwds )
        if isinstance( rval, tuple ) and len( rval ) == 2 and isinstance( rval[0], trans.app.model.Job ):
            assoc = trans.app.model.DataManagerJobAssociation( job=rval[0], data_manager_id=agent.data_manager_id  )
            trans.sa_session.add( assoc )
            trans.sa_session.flush()
        else:
            log.error( "Got bad return value from DefaultAgentAction.execute(): %s" % ( rval ) )
        return rval
