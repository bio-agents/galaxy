<%
    ## TEMPORARY: create agent dictionary in mako while both agent forms are in use.
    ## This avoids making two separate requests since the classic form requires the mako anyway.
    from galaxy.agents.parameters import params_to_incoming
    incoming = {}
    params_to_incoming( incoming, agent.inputs, module.state.inputs, trans.app, to_html=False)
    self.form_config = agent.to_json(trans, incoming, workflow_mode=True)
    self.form_config.update({
        'id'                : agent.id,
        'job_id'            : trans.security.encode_id( job.id ) if job else None,
        'history_id'        : trans.security.encode_id( trans.history.id ),
        'container'         : '#right-content'
    })
%>
${ h.dumps(self.form_config) }