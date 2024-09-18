<%inherit file="/base.mako"/>
<%namespace file="/message.mako" import="render_msg" />

%if message:
    ${render_msg( message, status )}
%endif

%if not sanitize_all:
    <div><p>You currently have <strong>sanitize_all_html</strong> set to False
    in your galaxy configuration file.  This prevents Galaxy from sanitizing
    agent outputs, which is an important security feature.  For improved
    security, we recommend you disable the old-style blanket sanitization and
    manage it via this whitelist instead.</p></div>
%else:
    <div><p>This interface will allow you to mark particular agents as 'trusted'
    after which Galaxy will no longer attempt to sanitize any HTML contents of
    datasets created by these agents upon display.  Please be aware of the
    potential security implications of doing this -- bypassing sanitization
    using this whitelist disables Galaxy's security feature (for the indicated
    agents) that prevents Galaxy from displaying potentially malicious
    Javascript.<br/>
    Note that datasets originating from an archive import are still sanitized
    even when their creating agent is whitelisted since it isn't possible to
    validate the information supplied in the archive.</p></div>
    <form name="sanitize_whitelist" action="${h.url_for( controller='admin', action='sanitize_whitelist' )}">
    <div class="agentForm">
        <div class="agentFormTitle">Agent Sanitization Whitelist</div>
        <div class="agentFormBody">
            <table class="manage-table colored" border="0" cellspacing="0" cellpadding="0" width="100%">
                <tr>
                    <th bgcolor="#D8D8D8">Whitelist</th>
                    <th bgcolor="#D8D8D8">Name</th>
                    <th bgcolor="#D8D8D8">ID</th>
                </tr>
                <% ctr = 0 %>
                %for agent in agents.values():
                    %if ctr % 2 == 1:
                        <tr class="odd_row">
                    %else:
                        <tr class="tr">
                    %endif
                        <td>
                            %if agent.id in trans.app.config.sanitize_whitelist:
                                <input type="checkbox" name="agents_to_whitelist" value="${agent.id}" checked="checked"/>
                            %else:
                                <input type="checkbox" name="agents_to_whitelist" value="${agent.id}"/>
                            %endif
                        </td>
                        <td>${ agent.name | h }</td>
                        <td>${ agent.id | h }</td>
                    </tr>
                    <% ctr += 1 %>
                %endfor
            </table>
        </div>
    </div>
    <input type="submit" name="submit_whitelist" value="Submit new whitelist"/>
    </form>
%endif
