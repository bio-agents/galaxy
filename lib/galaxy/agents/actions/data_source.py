from __init__ import DefaultAgentAction

import logging
log = logging.getLogger( __name__ )


class DataSourceAgentAction( DefaultAgentAction ):
    """Agent action used for Data Source Agents"""

    def _get_default_data_name( self, dataset, agent, on_text=None, trans=None, incoming=None, history=None, params=None, job_params=None, **kwd ):
        if incoming and 'name' in incoming:
            return incoming[ 'name' ]
        return super( DataSourceAgentAction, self )._get_default_data_name( dataset, agent, on_text=on_text, trans=trans, incoming=incoming, history=history, params=params, job_params=job_params )
