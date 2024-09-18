<%inherit file="/webapps/galaxy/base_panels.mako"/>
<%namespace file="/message.mako" import="render_msg" />

## Default title
<%def name="title()">Galaxy Administration</%def>

<%def name="stylesheets()">
    ${parent.stylesheets()}    
    ## Include "base.css" for styling agent menu and forms (details)
    ${h.css( "base", "autocomplete_tagging", "agent_menu" )}

    ## But make sure styles for the layout take precedence
    ${parent.stylesheets()}

    <style type="text/css">
        body { margin: 0; padding: 0; overflow: hidden; }
        #left {
            background: #C1C9E5 url(${h.url_for('/static/style/menu_bg.png')}) top repeat-x;
        }

        .unified-panel-body {
            overflow: auto;
        }
        .agentMenu {
            margin: 8px 0 0 10px;
        }
    </style>
</%def>

<%def name="javascripts()">
    ${parent.javascripts()}
</%def>

<%def name="init()">
    <%
        self.has_left_panel=True
        self.has_right_panel=False
        self.active_view="admin"
    %>
</%def>

<%def name="left_panel()">
    <div class="unified-panel-header" unselectable="on">
        <div class='unified-panel-header-inner'>Administration</div>
    </div>
    <div class="unified-panel-body">
        <div class="agentMenu">
            <div class="agentSectionList">
                <div class="agentSectionTitle">Server</div>
                <div class="agentSectionBody">
                    <div class="agentSectionBg">
                        <div class="agentTitle"><a href="${h.url_for( controller='admin', action='view_datatypes_registry' )}" target="galaxy_main">Data types registry</a></div>
                        <div class="agentTitle"><a href="${h.url_for( controller='admin', action='view_agent_data_tables' )}" target="galaxy_main">Data tables registry</a></div>
                        <div class="agentTitle"><a href="${h.url_for( controller='admin', action='display_applications' )}" target="galaxy_main">Display applications</a></div>
                        <div class="agentTitle"><a href="${h.url_for( controller='admin', action='jobs' )}" target="galaxy_main">Manage jobs</a></div>
                    </div>
                </div>
                <div class="agentSectionPad"></div>
                <div class="agentSectionTitle">Agents and Agent Shed</div>
                <div class="agentSectionBody">
                    <div class="agentSectionBg">                        
                    %if trans.app.agent_shed_registry and trans.app.agent_shed_registry.agent_sheds:
                        <div class="agentTitle"><a href="${h.url_for( controller='admin_agentshed', action='browse_agent_sheds' )}" target="galaxy_main">Search Agent Shed</a></div>
                    %endif
                    %if installing_repository_ids:
                        <div class="agentTitle"><a href="${h.url_for( controller='admin_agentshed', action='monitor_repository_installation', agent_shed_repository_ids=installing_repository_ids )}" target="galaxy_main">Monitor installing repositories</a></div>
                    %endif
                    %if is_repo_installed:
                        <div class="agentTitle"><a href="${h.url_for( controller='admin_agentshed', action='browse_repositories' )}" target="galaxy_main">Manage installed agents</a></div>
                        <div class="agentTitle"><a href="${h.url_for( controller='admin_agentshed', action='reset_metadata_on_selected_installed_repositories' )}" target="galaxy_main">Reset metadata</a></div>
                    %endif
                        <div class="agentTitle"><a href="${h.url_for( controller='admin', action='package_agent' )}" target="galaxy_main">Download local agent</a></div>
                        <div class="agentTitle"><a href="${h.url_for( controller='admin', action='agent_versions' )}" target="galaxy_main">Agent lineage</a></div>
                        <div class="agentTitle"><a href="${h.url_for( controller='admin', action='reload_agent' )}" target="galaxy_main">Reload a agent's configuration</a></div>
                        <div class="agentTitle"><a href="${h.url_for( controller='admin', action='review_agent_migration_stages' )}" target="galaxy_main">Review agent migration stages</a></div>
                        <div class="agentTitle"><a href="${h.url_for( controller='admin', action='agent_errors' )}" target="galaxy_main">View Agent Error Logs</a></div>
                        <div class="agentTitle"><a href="${h.url_for( controller='admin', action='sanitize_whitelist' )}" target="galaxy_main">Manage Display Whitelist</a></div>
                    </div>
                </div>
                <div class="agentSectionPad"></div>
                <div class="agentSectionTitle">User Management</div>
                <div class="agentSectionBody">
                    <div class="agentSectionBg">
                        <div class="agentTitle"><a href="${h.url_for( controller='admin', action='users' )}" target="galaxy_main">Users</a></div>
                        <div class="agentTitle"><a href="${h.url_for( controller='admin', action='groups' )}" target="galaxy_main">Groups</a></div>
                        <div class="agentTitle"><a href="${h.url_for( controller='admin', action='roles' )}" target="galaxy_main">Roles</a></div>
                        <div class="agentTitle"><a href="${h.url_for( controller='userskeys', action='all_users' )}" target="galaxy_main">API keys</a></div>
                        %if trans.app.config.allow_user_impersonation:
                            <div class="agentTitle"><a href="${h.url_for( controller='admin', action='impersonate' )}" target="galaxy_main">Impersonate a user</a></div>
                        %endif
                    </div>
                </div>
                <div class="agentSectionPad"></div>
                <div class="agentSectionTitle">Data</div>
                <div class="agentSectionBody">
                    <div class="agentSectionBg">
                        %if trans.app.config.enable_quotas:
                            <div class="agentTitle"><a href="${h.url_for( controller='admin', action='quotas' )}" target="galaxy_main">Quotas</a></div>
                        %endif
                        <div class="agentTitle"><a href="${h.url_for( controller='library_admin', action='browse_libraries' )}" target="galaxy_main">Data libraries</a></div>
                        <div class="agentTitle"><a href="${h.url_for( controller='data_manager' )}" target="galaxy_main">Local data</a></div>
                    </div>
                </div>
                <div class="agentSectionPad"></div>
                <div class="agentSectionTitle">Form Definitions</div>
                <div class="agentSectionBody">
                    <div class="agentSectionBg">
                        <div class="agentTitle"><a href="${h.url_for( controller='forms', action='browse_form_definitions' )}" target="galaxy_main">Form definitions</a></div>
                    </div>
                </div>
                <div class="agentSectionPad"></div>
                <div class="agentSectionTitle">Sample Tracking</div>
                <div class="agentSectionBody">
                    <div class="agentSectionBg">
                        <div class="agentTitle"><a href="${h.url_for( controller='external_service', action='browse_external_services' )}" target="galaxy_main">Sequencers and external services</a></div>
                        <div class="agentTitle"><a href="${h.url_for( controller='request_type', action='browse_request_types' )}" target="galaxy_main">Request types</a></div>
                        <div class="agentTitle"><a href="${h.url_for( controller='requests_admin', action='browse_requests' )}" target="galaxy_main">Sequencing requests</a></div>
                        <div class="agentTitle"><a href="${h.url_for( controller='requests_common', action='find_samples', cntrller='requests_admin' )}" target="galaxy_main">Find samples</a></div>
                    </div>
                </div>
            </div>
        </div>    
    </div>
</%def>

<%def name="center_panel()">
    <% center_url = h.url_for( controller='admin', action='center', message=message, status=status ) %>
    <iframe name="galaxy_main" id="galaxy_main" frameborder="0" style="position: absolute; width: 100%; height: 100%;" src="${center_url}"> </iframe>
</%def>
