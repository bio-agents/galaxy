<%inherit file="/base.mako"/>
<%namespace file="json_common.mako" import="display_item" />

<%def name="title()">${action.label} of ${param_dict['service_instance'].name} (${param_dict['service'].name}) on ${param_dict['item'].name}</%def>

<div class="agentForm">
    <div class="agentFormTitle">${action.label} of ${param_dict['service_instance'].name} (${param_dict['service'].name}) on ${param_dict['item'].name}</i></div>
    <div class="agentFormBody">
        ${display_item( result )}
    </div>
</div>
