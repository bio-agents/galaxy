<%def name="render_repository_status( repository )">
    <%
        from markupsafe import escape
        if repository.status in [ trans.install_model.AgentShedRepository.installation_status.CLONING,
                                  trans.install_model.AgentShedRepository.installation_status.SETTING_TOOL_VERSIONS,
                                  trans.install_model.AgentShedRepository.installation_status.INSTALLING_TOOL_DEPENDENCIES,
                                  trans.install_model.AgentShedRepository.installation_status.LOADING_PROPRIETARY_DATATYPES ]:
            bgcolor = trans.install_model.AgentShedRepository.states.INSTALLING
        elif repository.status in [ trans.install_model.AgentShedRepository.installation_status.NEW,
                                    trans.install_model.AgentShedRepository.installation_status.UNINSTALLED ]:
            bgcolor = trans.install_model.AgentShedRepository.states.UNINSTALLED
        elif repository.status in [ trans.install_model.AgentShedRepository.installation_status.ERROR ]:
            bgcolor = trans.install_model.AgentShedRepository.states.ERROR
        elif repository.status in [ trans.install_model.AgentShedRepository.installation_status.DEACTIVATED ]:
            bgcolor = trans.install_model.AgentShedRepository.states.WARNING
        elif repository.status in [ trans.install_model.AgentShedRepository.installation_status.INSTALLED ]:
            if repository.missing_agent_dependencies or repository.missing_repository_dependencies:
                bgcolor = trans.install_model.AgentShedRepository.states.WARNING
            else:
                bgcolor = trans.install_model.AgentShedRepository.states.OK
        else:
            bgcolor = trans.install_model.AgentShedRepository.states.ERROR
        rval = '<div class="count-box state-color-%s" id="RepositoryStatus-%s">' % ( bgcolor, trans.security.encode_id( repository.id ) )
        rval += '%s</div>' % escape( repository.status )
        return rval
    %>    
    ${rval}
</%def>

${render_repository_status( repository )}
