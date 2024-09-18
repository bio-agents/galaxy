<%inherit file="/base.mako"/>

<%def name="title()">Agent Errors</%def>

<h2>Agent Errors</h2>

<p>
Internal Agent Error log
</p>

<table class="manage-table colored" border="0" cellspacing="0" cellpadding="0" width="100%">
<tr class="header">
<td>Time</td>
<td>Phase</td>
<td>File</td>
<td>Error</td>
</tr>
%for error in agent_errors:
<tr>
    <td>${error['time']}</td>
    <td>${error['phase']}</td>
    <td>${error['file']}</td>
    <td>${error['error']}</td>
</tr>
%endfor
</table>

