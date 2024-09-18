<%inherit file="/base.mako"/>

<%def name="render_galaxy_repository_actions( repository=None )">
    <%
        from agent_shed.util.encoding_util import agent_shed_encode
        in_error_state = repository.in_error_state
        agent_dependency_ids = [ trans.security.encode_id( td.id ) for td in repository.agent_dependencies ]
        if repository.status in [ trans.install_model.AgentShedRepository.installation_status.DEACTIVATED,
                                  trans.install_model.AgentShedRepository.installation_status.ERROR,
                                  trans.install_model.AgentShedRepository.installation_status.INSTALLED ]:
            can_administer = True
        else:
            can_administer = False
    %>
    <br/><br/>
    <ul class="manage-table-actions">
        <li><a class="action-button" id="repository-${repository.id}-popup" class="menubutton">Repository Actions</a></li>
        <div popupmenu="repository-${repository.id}-popup">
            %if workflow_name:
                <li><a class="action-button" target="galaxy_main" href="${h.url_for( controller='admin_agentshed', action='import_workflow', workflow_name=agent_shed_encode( workflow_name ), repository_id=trans.security.encode_id( repository.id ) )}">Import workflow to Galaxy</a></li>
            %endif
            %if repository.can_reinstall_or_activate:
                <a class="action-button" href="${h.url_for( controller='admin_agentshed', action='browse_repositories', operation='activate or reinstall', id=trans.security.encode_id( repository.id ) )}">Activate or reinstall repository</a>
            %endif
            %if in_error_state:
                <a class="action-button" target="galaxy_main" href="${h.url_for( controller='admin_agentshed', action='reset_to_install', id=trans.security.encode_id( repository.id ), reset_repository=True )}">Reset to install</a>
            %elif repository.can_install:
                <a class="action-button" target="galaxy_main" href="${h.url_for( controller='admin_agentshed', action='manage_repository', id=trans.security.encode_id( repository.id ), operation='install' )}">Install</a>
            %elif can_administer:
                <a class="action-button" target="galaxy_main" href="${h.url_for( controller='admin_agentshed', action='manage_repository', id=trans.security.encode_id( repository.id ) )}">Manage repository</a>
                <a class="action-button" target="galaxy_main" href="${h.url_for( controller='admin_agentshed', action='browse_repository', id=trans.security.encode_id( repository.id ) )}">Browse repository files</a>
                <a class="action-button" target="galaxy_main" href="${h.url_for( controller='admin_agentshed', action='check_for_updates', id=trans.security.encode_id( repository.id ) )}">Get repository updates</a>
                %if repository.can_reset_metadata:
                    <a class="action-button" target="galaxy_main" href="${h.url_for( controller='admin_agentshed', action='reset_repository_metadata', id=trans.security.encode_id( repository.id ) )}">Reset repository metadata</a>
                %endif
                %if repository.includes_agents:
                    <a class="action-button" target="galaxy_main" href="${h.url_for( controller='admin_agentshed', action='set_agent_versions', id=trans.security.encode_id( repository.id ) )}">Set agent versions</a>
                %endif
                %if agent_dependency_ids:
                    <a class="action-button" target="galaxy_main" href="${h.url_for( controller='admin_agentshed', action='manage_repository_agent_dependencies', agent_dependency_ids=agent_dependency_ids, repository_id=trans.security.encode_id( repository.id ) )}">Manage agent dependencies</a>
                %endif
                <a class="action-button" target="galaxy_main" href="${h.url_for( controller='admin_agentshed', action='deactivate_or_uninstall_repository', id=trans.security.encode_id( repository.id ) )}">Deactivate or uninstall repository</a>
            %endif
            <a class="action-button" target="galaxy_main" href="${h.url_for( controller='admin_agentshed', action='repair_repository', id=trans.security.encode_id( repository.id ) )}">Repair repository</a>
        </div>
    </ul>
</%def>
