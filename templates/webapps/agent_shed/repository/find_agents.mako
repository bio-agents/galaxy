<%inherit file="/base.mako"/>
<%namespace file="/message.mako" import="render_msg" />
<%namespace file="/webapps/agent_shed/common/repository_actions_menu.mako" import="render_galaxy_repository_actions" />

<%!
   def inherit(context):
       if context.get('use_panels'):
           return '/webapps/agent_shed/base_panels.mako'
       else:
           return '/base.mako'
%>
<%inherit file="${inherit(context)}"/>

%if trans.webapp.name == 'galaxy':
    ${render_galaxy_repository_actions( repository=None )}
%endif

%if message:
    ${render_msg( message, status )}
%endif

<div class="agentForm">
    <div class="agentFormTitle">Search repositories for valid agents</div>
    <div class="agentFormBody">
        <div class="form-row">
            Valid agents are those that properly load in Galaxy.  Enter any combination of the following agent attributes to find repositories that contain 
            valid agents matching the search criteria.<br/><br/>
            Comma-separated strings may be entered in each field to expand search criteria.  Each field must contain the same number of comma-separated
            strings if these types of search strings are entered in more than one field.
        </div>
        <div style="clear: both"></div>
        <form name="find_agents" id="find_agents" action="${h.url_for( controller='repository', action='find_agents' )}" method="post" >
            <div class="form-row">
                <label>Agent id:</label>
                <input name="agent_id" type="textfield" value="${agent_id | h}" size="40"/>
            </div>
            <div style="clear: both"></div>
            <div class="form-row">
                <label>Agent name:</label>
                <input name="agent_name" type="textfield" value="${agent_name | h}" size="40"/>
            </div>
            <div style="clear: both"></div>
            <div class="form-row">
                <label>Agent version:</label>
                <input name="agent_version" type="textfield" value="${agent_version | h}" size="40"/>
            </div>
            <div style="clear: both"></div>
            <div class="form-row">
                <label>Exact matches only:</label>
                ${exact_matches_check_box.get_html()}
                <div class="agentParamHelp" style="clear: both;">
                    Check the box to match text exactly (text case doesn't matter as all strings are forced to lower case).
                </div>
            </div>
            <div style="clear: both"></div>
            <div class="form-row">
                <input type="submit" value="Search repositories"/>
            </div>
        </form>
    </div>
</div>
