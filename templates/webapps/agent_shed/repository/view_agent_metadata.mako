<%inherit file="/base.mako"/>
<%namespace file="/message.mako" import="render_msg" />
<%namespace file="/webapps/agent_shed/common/common.mako" import="*" />
<%namespace file="/webapps/agent_shed/repository/common.mako" import="*" />
<%namespace file="/webapps/agent_shed/common/repository_actions_menu.mako" import="*" />

<%
    is_new = repository.is_new( trans.app )

    can_push = trans.app.security_agent.can_push( trans.app, trans.user, repository )
    can_download = not is_new and ( not is_malicious or can_push )
    can_view_change_log = trans.webapp.name == 'agent_shed' and not is_new
%>

<%!
   def inherit(context):
       if context.get('use_panels'):
           return '/webapps/agent_shed/base_panels.mako'
       else:
           return '/base.mako'
%>
<%inherit file="${inherit(context)}"/>

%if render_repository_actions_for == 'agent_shed':
    ${render_agent_shed_repository_actions( repository=repository, metadata=metadata, changeset_revision=changeset_revision )}
%else:
    ${render_galaxy_repository_actions( repository=repository )}
%endif

%if message:
    ${render_msg( message, status )}
%endif

<div class="agentForm">
    <div class="agentFormTitle">Repository revision</div>
    <div class="agentFormBody">
        <div class="form-row">
            <label>Revision:</label>
            %if can_view_change_log:
                <a href="${h.url_for( controller='repository', action='view_changelog', id=trans.app.security.encode_id( repository.id ) )}">${revision_label}</a>
            %else:
                ${revision_label}
            %endif
        </div>
    </div>
</div>
<p/>
%if can_download:
    <div class="agentForm">
        <div class="agentFormTitle">Repository '${repository.name | h}'</div>
        <div class="agentFormBody">
            <div class="form-row">
                <label>Clone this repository:</label>
                ${render_clone_str( repository )}
            </div>
        </div>
    </div>
%else:
    <b>Repository name:</b><br/>
    ${repository.name}
%endif
%if agent_metadata_dict:
    <p/>
    <div class="agentForm">
        <div class="agentFormTitle">${agent_metadata_dict[ 'name' ]} agent metadata</div>
        <div class="agentFormBody">
            <div class="form-row">
                <table width="100%">
                    <tr bgcolor="#D8D8D8" width="100%"><td><b>Miscellaneous</td></tr>
                </table>
            </div>
            <div class="form-row">
                <label>Name:</label>
                <a href="${h.url_for( controller='repository', action='display_agent', repository_id=trans.security.encode_id( repository.id ), agent_config=agent_metadata_dict[ 'agent_config' ], changeset_revision=changeset_revision )}">${agent_metadata_dict[ 'name' ]}</a>
                <div style="clear: both"></div>
            </div>
            %if 'description' in agent_metadata_dict:
                <div class="form-row">
                    <label>Description:</label>
                    ${agent_metadata_dict[ 'description' ] | h}
                    <div style="clear: both"></div>
                </div>
            %endif
            %if 'id' in agent_metadata_dict:
                <div class="form-row">
                    <label>Id:</label>
                    ${agent_metadata_dict[ 'id' ] | h}
                    <div style="clear: both"></div>
                </div>
            %endif
            %if 'guid' in agent_metadata_dict:
                <div class="form-row">
                    <label>Guid:</label>
                    ${agent_metadata_dict[ 'guid' ] | h}
                    <div style="clear: both"></div>
                </div>
            %endif
            %if 'version' in agent_metadata_dict:
                <div class="form-row">
                    <label>Version:</label>
                    ${agent_metadata_dict[ 'version' ] | h}
                    <div style="clear: both"></div>
                </div>
            %endif
            %if 'version_string_cmd' in agent_metadata_dict:
                <div class="form-row">
                    <label>Version command string:</label>
                    ${agent_metadata_dict[ 'version_string_cmd' ] | h}
                    <div style="clear: both"></div>
                </div>
            %endif
            %if 'add_to_agent_panel' in agent_metadata_dict:
                <div class="form-row">
                    <label>Display in agent panel:</label>
                    ${agent_metadata_dict[ 'add_to_agent_panel' ] | h}
                    <div style="clear: both"></div>
                </div>
            %endif
            <div class="form-row">
                <table width="100%">
                    <tr bgcolor="#D8D8D8" width="100%"><td><b>Version lineage of this agent (guids ordered most recent to oldest)</td></tr>
                </table>
            </div>
            <div class="form-row">
                %if agent_lineage:
                    <table class="grid">
                        %for guid in agent_lineage:
                            <tr>
                                <td>
                                    %if guid == agent_metadata_dict[ 'guid' ]:
                                        ${guid | h} <b>(this agent)</b>
                                    %else:
                                        ${guid | h}
                                    %endif
                                </td>
                            </tr>
                        %endfor
                    </table>
                %else:
                    No agent versions are defined for this agent so it is critical that you <b>Reset all repository metadata</b> from the
                    <b>Manage repository</b> page.
                %endif
            </div>
            <div class="form-row">
                <table width="100%">
                    <tr bgcolor="#D8D8D8" width="100%"><td><b>Requirements (dependencies defined in the &lt;requirements&gt; tag set)</td></tr>
                </table>
            </div>
            <%
                if 'requirements' in agent_metadata_dict:
                    requirements = agent_metadata_dict[ 'requirements' ]
                else:
                    requirements = None
            %>
            %if requirements:
                <div class="form-row">
                    <label>Requirements:</label>
                    <table class="grid">
                        <tr>
                            <td><b>name</b></td>
                            <td><b>version</b></td>
                            <td><b>type</b></td>
                        </tr>
                        %for requirement_dict in requirements:
                            <%
                                requirement_name = requirement_dict[ 'name' ] or 'not provided'
                                requirement_version = requirement_dict[ 'version' ] or 'not provided'
                                requirement_type = requirement_dict[ 'type' ] or 'not provided'
                            %>
                            <tr>
                                <td>${requirement_name | h}</td>
                                <td>${requirement_version | h}</td>
                                <td>${requirement_type | h}</td>
                            </tr>
                        %endfor
                    </table>
                    <div style="clear: both"></div>
                </div>
            %else:
                <div class="form-row">
                    No requirements defined
                </div>
            %endif
            %if agent:
                <div class="form-row">
                    <table width="100%">
                        <tr bgcolor="#D8D8D8" width="100%"><td><b>Additional information about this agent</td></tr>
                    </table>
                </div>
                <div class="form-row">
                    <label>Command:</label>
                    <pre>${agent.command | h}</pre>
                    <div style="clear: both"></div>
                </div>
                <div class="form-row">
                    <label>Interpreter:</label>
                    ${agent.interpreter | h}
                    <div style="clear: both"></div>
                </div>
                <div class="form-row">
                    <label>Is multi-byte:</label>
                    ${agent.is_multi_byte | h}
                    <div style="clear: both"></div>
                </div>
                <div class="form-row">
                    <label>Forces a history refresh:</label>
                    ${agent.force_history_refresh | h}
                    <div style="clear: both"></div>
                </div>
                <% parallelism_info = agent.parallelism %>
                %if parallelism_info:
                    <div class="form-row">
                        <table width="100%">
                            <tr bgcolor="#D8D8D8" width="100%"><td><b>Parallelism</td></tr>
                        </table>
                    </div>
                    <div class="form-row">
                        <label>Method:</label>
                        ${parallelism_info.method | h}
                        <div style="clear: both"></div>
                    </div>
                    %for key, val in parallelism_info.attributes.items():
                        <div class="form-row">
                            <label>${key}:</label>
                            ${val | h}
                            <div style="clear: both"></div>
                        </div>
                    %endfor
                %endif
            %endif
            <div class="form-row">
                <table width="100%">
                    <tr bgcolor="#D8D8D8" width="100%"><td><b>Functional tests</td></tr>
                </table>
            </div>
            <%
                if 'tests' in agent_metadata_dict:
                    tests = agent_metadata_dict[ 'tests' ]
                else:
                    tests = None
            %>
            %if tests:
                <div class="form-row">
                    <table class="grid">
                        <tr>
                            <td><b>name</b></td>
                            <td><b>inputs</b></td>
                            <td><b>outputs</b></td>
                            <td><b>required files</b></td>
                        </tr>
                        %for test_dict in tests:
                            <%
                                inputs = test_dict[ 'inputs' ]
                                outputs = test_dict[ 'outputs' ]
                                required_files = test_dict[ 'required_files' ]
                            %>
                            <tr>
                                <td>${test_dict[ 'name' ]}</td>
                                <td>
                                    %for input in inputs:
                                        <b>${input[0]}:</b> ${input[1] | h}<br/>
                                    %endfor
                                </td>
                                <td>
                                    %for output in outputs:
                                        <b>${output[0]}:</b> ${output[1] | h}<br/>
                                    %endfor
                                </td>
                                <td>
                                    %for required_file in required_files:
                                        ${required_file | h}<br/>
                                    %endfor
                                </td>
                            </tr>
                        %endfor
                    </table>
                </div>
            %else:
                <div class="form-row">
                    No functional tests defined
                </div>
            %endif
        </div>
    </div>
%endif
