<%def name="render_agent_dependency_status( agent_dependency )">
    <%
        if agent_dependency.status in [ trans.install_model.AgentDependency.installation_status.INSTALLING ]:
            bgcolor = trans.install_model.AgentDependency.states.INSTALLING
        elif agent_dependency.status in [ trans.install_model.AgentDependency.installation_status.NEVER_INSTALLED,
                                         trans.install_model.AgentDependency.installation_status.UNINSTALLED ]:
            bgcolor = trans.install_model.AgentDependency.states.UNINSTALLED
        elif agent_dependency.status in [ trans.install_model.AgentDependency.installation_status.ERROR ]:
            bgcolor = trans.install_model.AgentDependency.states.ERROR
        elif agent_dependency.status in [ trans.install_model.AgentDependency.installation_status.INSTALLED ]:
            bgcolor = trans.install_model.AgentDependency.states.OK
        rval = '<div class="count-box state-color-%s" id="AgentDependencyStatus-%s">%s</div>' % \
            ( bgcolor, trans.security.encode_id( agent_dependency.id ), agent_dependency.status )
        return rval
    %>    
    ${rval}
</%def>

${render_agent_dependency_status( agent_dependency )}
