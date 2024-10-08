<%inherit file="/webapps/agent_shed/base_panels.mako"/>
<%namespace file="/message.mako" import="render_msg" />

<%def name="stylesheets()">
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
            margin-left: 10px;
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
        self.active_view="agents"
    %>
    %if trans.app.config.require_login and not trans.user:
        <script type="text/javascript">
            if ( window != top ) {
                top.location.href = location.href;
            }
        </script>
    %endif
</%def>

<%def name="left_panel()">
    <% can_review_repositories = trans.app.security_agent.user_can_review_repositories( trans.user ) %>
    <div class="unified-panel-header" unselectable="on">
        <div class='unified-panel-header-inner'>Administration</div>
    </div>
    <div class="unified-panel-body">
        <div class="agentMenu">
            <div class="agentSectionList">
                <div class="agentSectionTitle">
                    Repositories
                </div>
                <div class="agentSectionBody">
                    <div class="agentSectionBg">
                        <div class="agentTitle">
                            <a target="galaxy_main" href="${h.url_for( controller='repository', action='browse_categories' )}">Browse by category</a>
                        </div>
                        <div class="agentTitle">
                            <a target="galaxy_main" href="${h.url_for( controller='admin', action='browse_repositories' )}">Browse all repositories</a>
                        </div>
                        <div class="agentTitle">
                            <a target="galaxy_main" href="${h.url_for( controller='admin', action='reset_metadata_on_selected_repositories_in_agent_shed' )}">Reset selected metadata</a>
                        </div>
                        <div class="agentTitle">
                            <a target="galaxy_main" href="${h.url_for( controller='admin', action='browse_repository_metadata' )}">Browse metadata</a>
                        </div>
                    </div>
                </div>
                <div class="agentSectionPad"></div>
                <div class="agentSectionTitle">
                    Categories
                </div>
                <div class="agentSectionBody">
                    <div class="agentSectionBg">
                        <div class="agentTitle">
                            <a target="galaxy_main" href="${h.url_for( controller='admin', action='manage_categories' )}">Manage categories</a>
                        </div>
                    </div>
                </div>
                <div class="agentSectionPad"></div>
                <div class="agentSectionTitle">
                    Security
                </div>
                <div class="agentSectionBody">
                    <div class="agentSectionBg">
                        <div class="agentTitle">
                            <a target="galaxy_main" href="${h.url_for( controller='admin', action='users' )}">Manage users</a>
                        </div>
                        <div class="agentTitle">
                            <a target="galaxy_main" href="${h.url_for( controller='admin', action='groups' )}">Manage groups</a>
                        </div>
                        <div class="agentTitle">
                            <a target="galaxy_main" href="${h.url_for( controller='admin', action='roles' )}">Manage roles</a>
                        </div>
                    </div>
                </div>
                <div class="agentSectionPad"></div>
                <div class="agentSectionTitle">
                    Statistics
                </div>
                <div class="agentSectionBody">
                    <div class="agentTitle">
                        <a target="galaxy_main" href="${h.url_for( controller='admin', action='regenerate_statistics' )}">View shed statistics</a>
                    </div>
                </div>
            </div>
        </div>    
    </div>
</%def>

<%def name="center_panel()">
    <%
        center_url = h.url_for(controller='admin', action='center' )
    %>
    <iframe name="galaxy_main" id="galaxy_main" frameborder="0" style="position: absolute; width: 100%; height: 100%;" src="${center_url}"> </iframe>
</%def>
