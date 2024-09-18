<%inherit file="/base.mako"/>
<%namespace file="/message.mako" import="render_msg" />
<%namespace file="/webapps/agent_shed/common/common.mako" import="*" />
<%namespace file="/webapps/agent_shed/repository/common.mako" import="*" />
<%namespace file="/webapps/agent_shed/common/repository_actions_menu.mako" import="*" />

<%!
   def inherit(context):
       if context.get('use_panels'):
           return '/webapps/agent_shed/base_panels.mako'
       else:
           return '/base.mako'
%>

<%inherit file="${inherit(context)}"/>

<% from agent_shed.util.encoding_util import agent_shed_encode %>

<%def name="render_workflow( workflow_name, repository_metadata_id )">
    <% center_url = h.url_for( controller='repository', action='generate_workflow_image', workflow_name=agent_shed_encode( workflow_name ), repository_metadata_id=repository_metadata_id ) %>
    <iframe name="workflow_image" id="workflow_image" frameborder="0" style="position: absolute; width: 100%; height: 100%;" src="${center_url}"> </iframe>
</%def>

%if render_repository_actions_for == 'agent_shed':
    ${render_agent_shed_repository_actions( repository=repository )}
%else:
    ${render_galaxy_repository_actions( repository=repository )}
%endif

%if message:
    ${render_msg( message, status )}
%endif

<div class="agentFormTitle">${workflow_name | h}</div>
<div class="form-row">
    <b>Boxes are red when agents are not available in this repository</b>
    <div class="agentParamHelp" style="clear: both;">
        (this page displays SVG graphics)
    </div>
</div>
<br clear="left"/>

${render_workflow( workflow_name, repository_metadata_id )}
