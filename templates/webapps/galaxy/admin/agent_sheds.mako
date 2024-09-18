<%inherit file="/base.mako"/>
<%namespace file="/message.mako" import="render_msg" />

<%def name="title()">Configured Galaxy agent sheds</%def>

<%def name="stylesheets()">
    ${parent.stylesheets()}
    ${h.css( "library" )}
</%def>

%if message:
    ${render_msg( message, status )}
%endif

<div class="agentForm">
    <div class="agentFormTitle">Accessible Galaxy agent sheds</div>
    <div class="agentFormBody">
        <div class="form-row">
            <table class="grid">
                <% shed_id = 0 %>
                %for name, url in trans.app.agent_shed_registry.agent_sheds.items():
                    <tr class="libraryTitle">
                        <td>
                            <div style="float: left; margin-left: 1px;" class="menubutton split popup" id="dataset-${shed_id}-popup">
                                <a class="view-info" href="${h.url_for( controller='admin_agentshed', action='browse_agent_shed', agent_shed_url=url )}">${name|h}</a>
                            </div>
                            <div popupmenu="dataset-${shed_id}-popup">
                                <a class="action-button" href="${h.url_for( controller='admin_agentshed', action='browse_agent_shed', agent_shed_url=url )}">Browse valid repositories</a>
                                <a class="action-button" href="${h.url_for( controller='admin_agentshed', action='find_agents_in_agent_shed', agent_shed_url=url )}">Search for valid agents</a>
                                <a class="action-button" href="${h.url_for( controller='admin_agentshed', action='find_workflows_in_agent_shed', agent_shed_url=url )}">Search for workflows</a>
                            </div>
                        </td>
                    </tr>
                    <% shed_id += 1 %>
                %endfor
                </tr>
            </table>
        </div>
        <div style="clear: both"></div>
    </div>
</div>
