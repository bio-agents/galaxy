<%inherit file="/base.mako"/>
<%namespace file="/message.mako" import="render_msg" />
<%namespace file="/admin/agent_shed_repository/common.mako" import="*" />
<%namespace file="/admin/agent_shed_repository/repository_actions_menu.mako" import="*" />

<%def name="stylesheets()">
    ${parent.stylesheets()}
    ${h.css( "dynatree_skin/ui.dynatree" )}
</%def>

<%def name="javascripts()">
    ${parent.javascripts()}
    ${h.js( "libs/jquery/jquery-ui", "libs/jquery/jquery.dynatree" )}
    ${browse_files(agent_dependency.name, agent_dependency.installation_directory( trans.app ))}
</%def>

<% agent_dependency_ids = [ trans.security.encode_id( td.id ) for td in repository.agent_dependencies ] %>

${render_galaxy_repository_actions( repository )}

%if message:
    ${render_msg( message, status )}
%endif

<div class="agentForm">
    <div class="agentFormTitle">Browse agent dependency ${agent_dependency.name|h} installation directory</div>
    <div class="agentFormBody">
        <div class="form-row" >
            <label>Agent shed repository:</label>
            ${repository.name|h}
            <div style="clear: both"></div>
        </div>
        <div class="form-row" >
            <label>Agent shed repository changeset revision:</label>
            ${repository.changeset_revision|h}
            <div style="clear: both"></div>
        </div>
        <div class="form-row" >
            <label>Agent dependency status:</label>
            ${agent_dependency.status|h}
            <div style="clear: both"></div>
        </div>
        %if agent_dependency.in_error_state:
            <div class="form-row" >
                <label>Agent dependency installation error:</label>
                ${agent_dependency.error_message|h}
                <div style="clear: both"></div>
            </div>
        %endif
        <div class="form-row" >
            <label>Agent dependency installation directory:</label>
            ${agent_dependency.installation_directory( trans.app )|h}
            <div style="clear: both"></div>
        </div>
        <div class="form-row" >
            <label>Contents:</label>
            <div id="tree" >
                Loading...
            </div>
            <div style="clear: both"></div>
        </div>
        <div class="form-row">
            <div id="file_contents" class="agentParamHelp" style="clear: both;background-color:#FAFAFA;"></div>
        </div>
    </div>
</div>
