<%inherit file="/base.mako"/>
<%namespace file="/message.mako" import="render_msg" />
<%namespace file="/admin/agent_shed_repository/repository_actions_menu.mako" import="*" />

${render_galaxy_repository_actions( repository )}

%if message:
    ${render_msg( message, status )}
%endif

%if agent_metadata:
    <p/>
    <div class="agentForm">
        <div class="agentFormTitle">${agent_metadata[ 'name' ]|h} agent metadata</div>
        <div class="agentFormBody">
            <div class="form-row">
                <table width="100%">
                    <tr bgcolor="#D8D8D8" width="100%"><td><b>Miscellaneous</td></tr>
                </table>
            </div>
            <div class="form-row">
                <label>Name:</label>
                ${agent_metadata[ 'name' ]|h}
                <div style="clear: both"></div>
            </div>
            %if 'description' in agent_metadata:
                <div class="form-row">
                    <label>Description:</label>
                    ${agent_metadata[ 'description' ]|h}
                    <div style="clear: both"></div>
                </div>
            %endif
            %if 'id' in agent_metadata:
                <div class="form-row">
                    <label>Id:</label>
                    ${agent_metadata[ 'id' ]|h}
                    <div style="clear: both"></div>
                </div>
            %endif
            %if 'guid' in agent_metadata:
                <div class="form-row">
                    <label>Guid:</label>
                    ${agent_metadata[ 'guid' ]|h}
                    <div style="clear: both"></div>
                </div>
            %endif
            %if 'version' in agent_metadata:
                <div class="form-row">
                    <label>Version:</label>
                    ${agent_metadata[ 'version' ]|h}
                    <div style="clear: both"></div>
                </div>
            %endif
            %if 'version_string_cmd' in agent_metadata:
                <div class="form-row">
                    <label>Version command string:</label>
                    ${agent_metadata[ 'version_string_cmd' ]|h}
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
                                    %if guid == agent_metadata[ 'guid' ]:
                                        ${guid|h} <b>(this agent)</b>
                                    %else:
                                        ${guid|h}
                                    %endif
                                </td>
                            </tr>
                        %endfor
                    </table>
                %else:
                    No agent versions are defined for this agent so it is critical that you <b>Set agent versions</b> from the <b>Manage repository</b> page.
                %endif
            </div>
            <div class="form-row">
                <table width="100%">
                    <tr bgcolor="#D8D8D8" width="100%"><td><b>Requirements (dependencies defined in the &lt;requirements&gt; tag set)</td></tr>
                </table>
            </div>
            <%
                if 'requirements' in agent_metadata:
                    requirements = agent_metadata[ 'requirements' ]
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
                                <td>${requirement_name|h}</td>
                                <td>${requirement_version|h}</td>
                                <td>${requirement_type|h}</td>
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
                    <pre>${agent.command|h}</pre>
                    <div style="clear: both"></div>
                </div>
                <div class="form-row">
                    <label>Interpreter:</label>
                    ${agent.interpreter|h}
                    <div style="clear: both"></div>
                </div>
                <div class="form-row">
                    <label>Is multi-byte:</label>
                    ${agent.is_multi_byte|h}
                    <div style="clear: both"></div>
                </div>
                <div class="form-row">
                    <label>Forces a history refresh:</label>
                    ${agent.force_history_refresh|h}
                    <div style="clear: both"></div>
                </div>
                <div class="form-row">
                    <label>Parallelism:</label>
                    ${agent.parallelism|h}
                    <div style="clear: both"></div>
                </div>
            %endif
            <div class="form-row">
                <table width="100%">
                    <tr bgcolor="#D8D8D8" width="100%"><td><b>Functional tests</td></tr>
                </table>
            </div>
            <%
                if 'tests' in agent_metadata:
                    tests = agent_metadata[ 'tests' ]
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
                                <td>${test_dict[ 'name' ]|h}</td>
                                <td>
                                    %for input in inputs:
                                        <b>${input[0]|h}:</b> ${input[1]|h}<br/>
                                    %endfor
                                </td>
                                <td>
                                    %for output in outputs:
                                        <b>${output[0]|h}:</b> ${output[1]|h}<br/>
                                    %endfor
                                </td>
                                <td>
                                    %for required_file in required_files:
                                        ${required_file|h}<br/>
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
