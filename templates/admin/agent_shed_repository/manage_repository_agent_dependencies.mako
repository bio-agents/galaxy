<%inherit file="/base.mako"/>
<%namespace file="/message.mako" import="render_msg" />
<%namespace file="/admin/agent_shed_repository/repository_actions_menu.mako" import="*" />
<%namespace file="/webapps/agent_shed/common/common.mako" import="common_misc_javascripts" />

<%def name="stylesheets()">
    ${parent.stylesheets()}
    ${h.css( "library" )}
</%def>

<%def name="javascripts()">
    ${parent.javascripts()}
    ${common_misc_javascripts()}
</%def>

${render_galaxy_repository_actions( repository )}

%if message:
    ${render_msg( message, status )}
%endif

<div class="agentForm">
    <div class="agentFormTitle">Agent shed repository '${repository.name|h}' agent dependencies</div>
        <%
            can_install = False
            can_uninstall = False
        %>
        <br/><br/>
        <table class="grid">
            <tr><th  bgcolor="#D8D8D8">Name</th><th  bgcolor="#D8D8D8">Version</th><th  bgcolor="#D8D8D8">Type</th><th bgcolor="#D8D8D8">Status</th><th bgcolor="#D8D8D8">Error</th></tr>
            %for agent_dependency in repository.agent_dependencies:
                <%
                    if agent_dependency.error_message:
                        from agent_shed.util.basic_util import to_html_string
                        error_message = to_html_string( agent_dependency.error_message )
                    else:
                        error_message = ''
                    if not can_install:
                        if agent_dependency.status in [ trans.install_model.AgentDependency.installation_status.NEVER_INSTALLED,
                                                       trans.install_model.AgentDependency.installation_status.UNINSTALLED ]:
                            can_install = True
                    if not can_uninstall:
                        if agent_dependency.status not in [ trans.install_model.AgentDependency.installation_status.NEVER_INSTALLED,
                                                           trans.install_model.AgentDependency.installation_status.UNINSTALLED ]:
                            can_uninstall = True
                %>
                <tr>
                    <td>
                        %if agent_dependency.status not in [ trans.install_model.AgentDependency.installation_status.UNINSTALLED ]:
                            <a target="galaxy_main" href="${h.url_for( controller='admin_agentshed', action='manage_repository_agent_dependencies', operation='browse', agent_dependency_ids=trans.security.encode_id( agent_dependency.id ), repository_id=trans.security.encode_id( repository.id ) )}">
                                ${agent_dependency.name|h}
                            </a>
                        %else:
                            ${agent_dependency.name|h}
                        %endif
                    </td>
                    <td>${agent_dependency.version|h}</td>
                    <td>${agent_dependency.type|h}</td>
                    <td>${agent_dependency.status|h}</td>
                    <td>${error_message}</td>
                </tr>
            %endfor
        </table>
        %if can_install:
            <br/>
            <form name="install_agent_dependencies" id="install_agent_dependencies" action="${h.url_for( controller='admin_agentshed', action='manage_agent_dependencies', operation='install', repository_id=trans.security.encode_id( repository.id ) )}" method="post" >
                <div class="form-row">
                    Check each agent dependency that you want to install and click <b>Install</b>.
                </div>
                <div style="clear: both"></div>
                <div class="form-row">
                    <input type="checkbox" id="checkAllUninstalled" name="select_all_uninstalled_agent_dependencies_checkbox" value="true" onclick="checkAllUninstalledAgentDependencyIdFields(1);"/><input type="hidden" name="select_all_uninstalled_agent_dependencies_checkbox" value="true"/><b>Select/unselect all agent dependencies</b>
                </div>
                <div style="clear: both"></div>
                <div class="form-row">
                    ${uninstalled_agent_dependencies_select_field.get_html()}
                </div>
                <div style="clear: both"></div>
                <div class="form-row">
                    <input type="submit" name="install_button" value="Install"/></td>
                </div>
            </form>
            <br/>
        %endif
        %if can_uninstall:
            <br/>
            <form name="uninstall_agent_dependencies" id="uninstall_agent_dependencies" action="${h.url_for( controller='admin_agentshed', action='manage_repository_agent_dependencies', operation='uninstall', repository_id=trans.security.encode_id( repository.id ) )}" method="post" >
                <div class="form-row">
                    Check each agent dependency that you want to uninstall and click <b>Uninstall</b>.
                </div>
                <div style="clear: both"></div>
                <div class="form-row">
                    <input type="checkbox" id="checkAllInstalled" name="select_all_installed_agent_dependencies_checkbox" value="true" onclick="checkAllInstalledAgentDependencyIdFields(1);"/><input type="hidden" name="select_all_installed_agent_dependencies_checkbox" value="true"/><b>Select/unselect all agent dependencies</b>
                </div>
                <div style="clear: both"></div>
                <div class="form-row">
                    ${installed_agent_dependencies_select_field.get_html()}
                </div>
                <div style="clear: both"></div>
                <div class="form-row">
                    <input type="submit" name="uninstall_button" value="Uninstall"/></td>
                </div>
            </form>
            <br/>
        %endif
    </div>
</div>
