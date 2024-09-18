<%inherit file="/base.mako"/>
<%namespace file="/message.mako" import="render_msg" />

%if message:
    ${render_msg( message, status )}
%endif
</br>
</br>

<ul class="manage-table-actions">
    <li>
        <a class="action-button"  href="${h.url_for( controller='user', action='index', cntrller=cntrller )}">User preferences</a>
    </li>
</ul>

%if agent_filters or section_filters or label_filters:
    <div class="agentForm">
        <form name="agentbox_filter" id="agentbox_filter" action="${h.url_for( controller='user', action='edit_agentbox_filters', cntrller=cntrller )}" method="post" >
            % if agent_filters:
                <div class="agentFormTitle">Edit AgentBox filters :: Agents</div>
                <div class="agentFormBody">
                    % for filter in agent_filters:
                        <div class="form-row">
                            <div style="float: left; width: 40px; margin-right: 10px;">
                                % if filter['checked']:
                                    <input type="checkbox" name="t_${filter['filterpath']}" checked="checked">
                                % else:
                                    <input type="checkbox" name="t_${filter['filterpath']}">
                                % endif
                            </div>
                            <div style="float: left; margin-right: 10px;">
                                ${filter['short_desc']}
                                <div class="agentParamHelp" style="clear: both;">${filter['desc']}</div>
                            </div>
                            <div style="clear: both"></div>
                        </div>
                    % endfor
                </div>
            % endif

            % if section_filters:
                <div class="agentFormTitle">Edit AgentBox filters :: Sections</div>
                <div class="agentFormBody">
                    % for filter in section_filters:
                        <div class="form-row">
                            <div style="float: left; width: 40px; margin-right: 10px;">
                                % if filter['checked']:
                                    <input type="checkbox" name="s_${filter['filterpath']}" checked="checked">
                                % else:
                                    <input type="checkbox" name="s_${filter['filterpath']}">
                                % endif
                            </div>
                            <div style="float: left; margin-right: 10px;">
                                ${filter['short_desc']}
                                <div class="agentParamHelp" style="clear: both;">${filter['desc']}</div>
                            </div>
                            <div style="clear: both"></div>
                        </div>
                    % endfor
                </div>
            % endif

            % if label_filters:
                <div class="agentFormTitle">Edit AgentBox filters :: Labels</div>
                <div class="agentFormBody">
                    % for filter in label_filters:
                        <div class="form-row">
                            <div style="float: left; width: 40px; margin-right: 10px;">
                                % if filter['checked']:
                                    <input type="checkbox" name="l_${filter['filterpath']}" checked="checked">
                                % else:
                                    <input type="checkbox" name="l_${filter['filterpath']}">
                                % endif
                            </div>
                            <div style="float: left; margin-right: 10px;">
                                ${filter['short_desc']}
                                <div class="agentParamHelp" style="clear: both;">${filter['desc']}</div>
                            </div>
                            <div style="clear: both"></div>
                        </div>
                    % endfor
                </div>
            % endif
            <div class="form-row">
                <input type="submit" name="edit_agentbox_filter_button" value="Save changes">
            </div>
        </form>
    </div>
%else:
    ${render_msg( 'No filters available. Contact your system administrator or check your configuration file.', 'info' )}
%endif
