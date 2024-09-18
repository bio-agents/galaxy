<%inherit file="/base.mako"/>
<%namespace file="/message.mako" import="render_msg" />
<%namespace file="/admin/agent_shed_repository/repository_actions_menu.mako" import="*" />

<% import os %>

${render_galaxy_repository_actions( repository )}

%if message:
    ${render_msg( message, status )}
%endif

<div class="agentForm">
    <div class="agentFormTitle">Uninstall agent dependencies</div>
    <div class="agentFormBody">
        <form name="uninstall_agent_dependenceies" id="uninstall_agent_dependenceies" action="${h.url_for( controller='admin_agentshed', action='uninstall_agent_dependencies' )}" method="post" >       
            <div class="form-row">
                <table class="grid">
                    <tr>
                        <th>Name</th>
                        <th>Version</th>
                        <th>Type</th>
                        <th>Install directory</th>
                    </tr>
                    %for agent_dependency in agent_dependencies:
                        <input type="hidden" name="agent_dependency_ids" value="${trans.security.encode_id( agent_dependency.id )}"/>
                        <%
                            if agent_dependency.type == 'package':
                                install_dir = os.path.join( trans.app.config.agent_dependency_dir,
                                                            agent_dependency.name,
                                                            agent_dependency.version,
                                                            agent_dependency.agent_shed_repository.owner,
                                                            agent_dependency.agent_shed_repository.name,
                                                            agent_dependency.agent_shed_repository.installed_changeset_revision )
                            elif agent_dependency.type == 'set_environment':
                                install_dir = os.path.join( trans.app.config.agent_dependency_dir,
                                                            'environment_settings',
                                                            agent_dependency.name,
                                                            agent_dependency.agent_shed_repository.owner,
                                                            agent_dependency.agent_shed_repository.name,
                                                            agent_dependency.agent_shed_repository.installed_changeset_revision )
                            if not os.path.exists( install_dir ):
                                install_dir = "This dependency's installation directory does not exist, click <b>Uninstall</b> to reset for installation."
                        %>
                        <tr>
                            <td>${agent_dependency.name|h}</td>
                            <td>${agent_dependency.version|h}</td>
                            <td>${agent_dependency.type|h}</td>
                            <td>${install_dir|h}</td>
                        </tr>
                    %endfor
                </table>
                <div style="clear: both"></div>
            </div>
            <div class="form-row">
                <input type="submit" name="uninstall_agent_dependencies_button" value="Uninstall"/>
                <div class="agentParamHelp" style="clear: both;">
                    Click to uninstall the agent dependencies listed above.
                </div>
            </div>
        </form>
    </div>
</div>
