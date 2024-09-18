<%inherit file="/base.mako"/>
<%namespace file="/message.mako" import="render_msg" />
<%
   from galaxy.agents import Agent
   from galaxy.agents.agentbox import AgentSection
%>

<script type="text/javascript">
$().ready(function() {
%if agent_id:
    var focus_el = $("input[name=package_agent_button]");
%else:
    var focus_el = $("select[name=agent_id]");
%endif
    focus_el.focus();
});
</script>

%if message:
    ${render_msg( message, status )}
%endif

<div class="agentForm">
    <div class="agentFormTitle">Download Tarball For AgentShed</div>
    <div class="agentFormBody">
    <form name="package_agent" id="package_agent" action="${h.url_for( controller='admin', action='package_agent' )}" method="post" >
        <div class="form-row">
            <label>
                Agent to bundle:
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
            <input type="submit" name="package_agent_button" value="Download"/>
        </div>
    </form>
    </div>
</div>
