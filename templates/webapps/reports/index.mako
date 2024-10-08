<%inherit file="/webapps/reports/base_panels.mako"/>

<%def name="init()">
    <%
        self.has_left_panel=True
        self.has_right_panel=False
        self.active_view="reports"
    %>
</%def>

<%def name="stylesheets()">
    ${parent.stylesheets()}    
    ## Include "base.css" for styling agent menu and forms (details)
    ${h.css( "base", "autocomplete_tagging", "agent_menu" )}

    ## But make sure styles for the layout take precedence
    ${parent.stylesheets()}

    <style type="text/css">
        body { margin: 0; padding: 0; overflow: hidden; }
        #left {
            background: #C1C9E5 url("${h.url_for('/static/style/menu_bg.png')}") top repeat-x;
        }
    </style>
</%def>

<%def name="javascripts()">
    ${parent.javascripts()}
</%def>

<%def name="left_panel()">
    <%
        from datetime import datetime
        from time import mktime, strftime, localtime
    %>
    <div class="unified-panel-header" unselectable="on">
        <div class='unified-panel-header-inner'><span>Reports</span>
            <a target="galaxy_main" href="${h.url_for( controller='home', action='run_stats' )}">
                <button id="reports_home" data-toggle="agenttip" data-placement="top" title="Dashboard" class="btn btn-default primary-button" type="button"><span class="fa fa-home"></span></button>
            </a>
        </div>
    </div>
    <div class="page-container reports-panel-container">
        <div class="agentMenu">
            <div class="agentSectionList">
                <div class="agentSectionPad"></div>
                <div class="agentSectionTitle">
                    <span>Jobs</span>
                </div>
                <div class="agentSectionBody">
                    <div class="agentSectionBg">
                        <div class="agentTitle"><a target="galaxy_main" href="${h.url_for( controller='jobs', action='specified_date_handler', specified_date=datetime.utcnow().strftime( "%Y-%m-%d" ), sort_id='default', order='default' )}">Today's jobs</a></div>
                        <div class="agentTitle"><a target="galaxy_main" href="${h.url_for( controller='jobs', action='specified_month_all', sort_id='default', order='default' )}">Jobs per day this month</a></div>
                        <div class="agentTitle"><a target="galaxy_main" href="${h.url_for( controller='jobs', action='specified_month_in_error', sort_id='default', order='default' )}">Jobs in error per day this month</a></div>
                        <div class="agentTitle"><a target="galaxy_main" href="${h.url_for( controller='jobs', action='specified_date_handler', operation='unfinished', sort_id='default', order='default' )}">All unfinished jobs</a></div>
                        <div class="agentTitle"><a target="galaxy_main" href="${h.url_for( controller='jobs', action='per_month_all', sort_id='default', order='default' )}">Jobs per month</a></div>
                        <div class="agentTitle"><a target="galaxy_main" href="${h.url_for( controller='jobs', action='per_month_in_error', sort_id='default', order='default' )}">Jobs in error per month</a></div>
                        <div class="agentTitle"><a target="galaxy_main" href="${h.url_for( controller='jobs', action='per_user', sort_id='default', order='default' )}">Jobs per user</a></div>
                        <div class="agentTitle"><a target="galaxy_main" href="${h.url_for( controller='jobs', action='per_agent', sort_id='default', order='default' )}">Jobs per agent</a></div>
                        <div class="agentTitle"><a target="galaxy_main" href="${h.url_for( controller='jobs', action='errors_per_agent', sort_id='default', order='default', spark_time='')}">Errors per agent</a></div>
                    </div>
                </div>
                <div class="agentSectionPad"></div>
                <div class="agentSectionPad"></div>
                <div class="agentSectionTitle">
                    <span>Sample Tracking</span>
                </div>
                <div class="agentSectionBody">
                    <div class="agentSectionBg">
                        <div class="agentTitle"><a target="galaxy_main" href="${h.url_for( controller='sample_tracking', action='per_month_all' )}">Sequencing requests per month</a></div>
                        <div class="agentTitle"><a target="galaxy_main" href="${h.url_for( controller='sample_tracking', action='per_user' )}">Sequencing requests per user</a></div>
                    </div>
                </div>
                <div class="agentSectionPad"></div>
                <div class="agentSectionPad"></div>
                <div class="agentSectionTitle">
                    <span>Workflows</span>
                </div>
                <div class="agentSectionBody">
                    <div class="agentSectionBg">
                        <div class="agentTitle"><a target="galaxy_main" href="${h.url_for( controller='workflows', action='per_workflow', sort_id='default', order='default' )}">Runs per Workflows</a></div>
                        <div class="agentTitle"><a target="galaxy_main" href="${h.url_for( controller='workflows', action='per_month_all', sort_id='default', order='default' )}">Workflows per month</a></div>
                        <div class="agentTitle"><a target="galaxy_main" href="${h.url_for( controller='workflows', action='per_user', sort_id='default', order='default' )}">Workflows per user</a></div>
                    </div>
                </div>
                <div class="agentSectionPad"></div>
                <div class="agentSectionPad"></div>
                <div class="agentSectionTitle">
                    <span>Users</span>
                </div>
                <div class="agentSectionBody">
                    <div class="agentSectionBg">
                        <div class="agentTitle"><a target="galaxy_main" href="${h.url_for( controller='users', action='registered_users' )}">Registered users</a></div>
                        <div class="agentTitle"><a target="galaxy_main" href="${h.url_for( controller='users', action='last_access_date', sort_id='default', order='default' )}">Date of last login</a></div>
                        <div class="agentTitle"><a target="galaxy_main" href="${h.url_for( controller='users', action='user_disk_usage', sort_id='default', order='default' )}">User disk usage</a></div>
                    </div>
                </div>
                <div class="agentSectionPad"></div>
                <div class="agentSectionPad"></div>
                <div class="agentSectionTitle">
                    <span>System</span>
                </div>
                  <div class="agentSectionBody">
                    <div class="agentSectionBg">
                        <div class="agentTitle"><a target="galaxy_main" href="${h.url_for( controller='system', action='index' )}">Disk space maintenance</a></div>
                    </div>
                </div>
            </div>
        </div>    
    </div>
</%def>

<%def name="center_panel()">
    <% center_url = h.url_for( controller='home', action='run_stats' ) %>
    <iframe name="galaxy_main" id="galaxy_main" frameborder="0" style="position: absolute; width: 100%; height: 100%;" src="${center_url}"> </iframe>
</%def>
