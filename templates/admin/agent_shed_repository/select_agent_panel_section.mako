<%inherit file="/base.mako"/>
<%namespace file="/message.mako" import="render_msg" />
<%namespace file="/admin/agent_shed_repository/common.mako" import="render_dependencies_section" />
<%namespace file="/admin/agent_shed_repository/common.mako" import="render_readme_section" />
<%namespace file="/webapps/agent_shed/repository/common.mako" import="*" />

<%def name="stylesheets()">
    ${parent.stylesheets()}
    ${h.css( "library" )}
</%def>

<%def name="javascripts()">
    ${parent.javascripts()}
    ${h.js("libs/jquery/jquery.rating", "libs/jquery/jstorage" )}
    ${container_javascripts()}
</%def>

<%
    # Handle the case where an uninstalled repository encountered errors during the process of being reinstalled.  In
    # this case, the repository metadata is an empty dictionary, but one or both of has_repository_dependencies
    # and includes_agent_dependencies may be True.  If either of these are True but we have no metadata, we cannot install
    # repository dependencies on this pass.
    if has_repository_dependencies:
        repository_dependencies = containers_dict[ 'repository_dependencies' ]
        missing_repository_dependencies = containers_dict[ 'missing_repository_dependencies' ]
        if repository_dependencies or missing_repository_dependencies:
            can_display_repository_dependencies = True
        else:
            can_display_repository_dependencies = False
    else:
        can_display_repository_dependencies = False
    if includes_agent_dependencies:
        agent_dependencies = containers_dict[ 'agent_dependencies' ]
        missing_agent_dependencies = containers_dict[ 'missing_agent_dependencies' ]
        if agent_dependencies or missing_agent_dependencies:
            can_display_agent_dependencies = True
        else:
            can_display_agent_dependencies = False
    else:
        can_display_agent_dependencies = False
%>

%if message:
    ${render_msg( message, status )}
%endif

<div class="warningmessage">
    <p>
        The Galaxy development team does not maintain the contents of many Galaxy Agent Shed repositories.  Some
        repository agents may include code that produces malicious behavior, so be aware of what you are installing.
    </p>
    <p>
        If you discover a repository that causes problems after installation, contact <a href="https://wiki.galaxyproject.org/Support" target="_blank">Galaxy support</a>,
        sending all necessary information, and appropriate action will be taken.
    </p>
    <p>
        <a href="https://wiki.galaxyproject.org/AgentShedRepositoryFeatures#Contact_repository_owner" target="_blank">Contact the repository owner</a> for 
        general questions or concerns.
    </p>
</div>
<div class="agentForm">
    <div class="agentFormBody">
        <form name="select_agent_panel_section" id="select_agent_panel_section" action="${h.url_for( controller='admin_agentshed', action='prepare_for_install' )}" method="post" >
            <div class="form-row">
                <input type="hidden" name="includes_agents" value="${includes_agents}" />
                <input type="hidden" name="includes_agent_dependencies" value="${includes_agent_dependencies}" />
                <input type="hidden" name="includes_agents_for_display_in_agent_panel" value="${includes_agents_for_display_in_agent_panel}" />
                <input type="hidden" name="agent_shed_url" value="${agent_shed_url}" />
                <input type="hidden" name="encoded_repo_info_dicts" value="${encoded_repo_info_dicts}" />
                <input type="hidden" name="updating" value="${updating}" />
                <input type="hidden" name="updating_repository_id" value="${updating_repository_id}" />
                <input type="hidden" name="updating_to_ctx_rev" value="${updating_to_ctx_rev}" />
                <input type="hidden" name="updating_to_changeset_revision" value="${updating_to_changeset_revision}" />
                <input type="hidden" name="encoded_updated_metadata" value="${encoded_updated_metadata}" />
            </div>
            <div style="clear: both"></div>
            <% readme_files_dict = containers_dict.get( 'readme_files', None ) %>
            %if readme_files_dict:
                <div class="form-row">
                    <table class="colored" width="100%">
                        <th bgcolor="#EBD9B2">Repository README file - may contain important installation or license information</th>
                    </table>
                </div>
                ${render_readme_section( containers_dict )}
                <div style="clear: both"></div>
            %endif
            %if can_display_repository_dependencies or can_display_agent_dependencies:
                <div class="form-row">
                    <table class="colored" width="100%">
                        <th bgcolor="#EBD9B2">Confirm dependency installation</th>
                    </table>
                </div>
                ${render_dependencies_section( install_repository_dependencies_check_box, install_agent_dependencies_check_box, containers_dict, revision_label=None, export=False )}
                <div style="clear: both"></div>
            %endif
            %if shed_agent_conf_select_field:
                <div class="form-row">
                    <table class="colored" width="100%">
                        <th bgcolor="#EBD9B2">Choose the agent panel section to contain the installed agents (optional)</th>
                    </table>
                </div>
                <%
                    if len( shed_agent_conf_select_field.options ) == 1:
                        select_help = "Your Galaxy instance is configured with 1 shed-related agent configuration file, so repositories will be "
                        select_help += "installed using its <b>agent_path</b> setting."
                    else:
                        select_help = "Your Galaxy instance is configured with %d shed-related agent configuration files, " % len( shed_agent_conf_select_field.options )
                        select_help += "so select the file whose <b>agent_path</b> setting you want used for installing repositories."
                %>
                <div class="form-row">
                    <label>Shed agent configuration file:</label>
                    ${shed_agent_conf_select_field.get_html()}
                    <div class="agentParamHelp" style="clear: both;">
                        ${select_help|h}
                    </div>
                </div>
                <div style="clear: both"></div>
            %else:
                <input type="hidden" name="shed_agent_conf" value="${shed_agent_conf|h}"/>
            %endif
            <div class="form-row">
                <label>Add new agent panel section:</label>
                <input name="new_agent_panel_section_label" type="textfield" value="${new_agent_panel_section_label|h}" size="40"/>
                <div class="agentParamHelp" style="clear: both;">
                    Add a new agent panel section to contain the installed agents (optional).
                </div>
            </div>
            <div class="form-row">
                <label>Select existing agent panel section:</label>
                ${agent_panel_section_select_field.get_html()}
                <div class="agentParamHelp" style="clear: both;">
                    Choose an existing section in your agent panel to contain the installed agents (optional).  
                </div>
            </div>
            <div class="form-row">
                <input type="submit" name="select_agent_panel_section_button" value="Install"/>
                <div class="agentParamHelp" style="clear: both;">
                    Clicking <b>Install</b> without selecting a agent panel section will load the installed agents into the agent panel outside of any sections.
                </div>
            </div>
        </form>
    </div>
</div>
