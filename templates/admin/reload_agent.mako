<%inherit file="/base.mako"/>
<%namespace file="/message.mako" import="render_msg" />
<%
   from galaxy.agents import Agent
   from galaxy.agents.agentbox import AgentSection
%>

<script type="text/javascript">
$().ready(function() {
%if agent_id:
    var focus_el = $("input[name=reload_agent_button]");
%else:
    var focus_el = $("select[name=agent_id]");
%endif
    focus_el.focus();
});
$().ready(function() {
    $("#reload_agentbox").click(function(){
        $.ajax({
            url: "${h.url_for(controller="/api/configuration", action="agentbox")}",
            type: 'PUT'
        });
    });
});
</script>

%if message:
    ${render_msg( message, status )}
%endif

<div class="agentForm">
    <div class="agentFormTitle">Reload Agent</div>
    <div class="agentFormBody">
    <form name="reload_agent" id="reload_agent" action="${h.url_for( controller='admin', action='reload_agent' )}" method="post" >
        <div class="form-row">
            <label>
                Agent to reload:
            </label>
            <select name="agent_id">
                %for val in agentbox.agent_panel_contents( trans ):
                    %if isinstance( val, Agent ):
                        <option value="${val.id|h}">${val.name|h}</option>
                    %elif isinstance( val, AgentSection ):
                        <optgroup label="${val.name|h}">
                        <% section = val %>
                        %for section_key, section_val in section.elems.items():
                            %if isinstance( section_val, Agent ):
                                <% selected_str = "" %>
                                %if section_val.id == agent_id:
                                     <% selected_str = " selected=\"selected\"" %>
                                %endif
                                <option value="${section_val.id|h}"${selected_str}>${section_val.name|h}</option>
                            %endif
                        %endfor
                    %endif
                %endfor
            </select>
        </div>
        <div class="form-row">
            <input type="submit" name="reload_agent_button" value="Reload"/>
        </div>
    </form>
    </div>
</div>
<p>
<div class="agentForm">
    <div class="agentFormTitle">Reload Agentbox</div>
    <div class="agentFormBody">
    <form name="reload_agentbox_form" id="reload_agentbox_form" action="" method="" >
        <div class="form-row">
        Clicking <a href="#" id="reload_agentbox">here</a> will reload
        the Galaxy agentbox. This will cause newly discovered agents
        to be added, agents now missing from agent confs to be removed,
        and items in the panel reordered. Individual agents, even ones
        with modified agent descriptions willl not be reloaded.
        </div>
    </form>
    </div>
</div>
