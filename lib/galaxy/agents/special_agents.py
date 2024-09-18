import logging
log = logging.getLogger( __name__ )

SPECIAL_TOOLS = {
    "history export": "galaxy/agents/imp_exp/exp_history_to_archive.xml",
    "history import": "galaxy/agents/imp_exp/imp_history_from_archive.xml",
}


def load_lib_agents( agentbox ):
    for name, path in SPECIAL_TOOLS.items():
        agent = agentbox.load_hidden_lib_agent( path )
        log.debug( "Loaded %s agent: %s", ( name, agent.id ) )
