<%inherit file="/base.mako"/>
<%namespace file="/message.mako" import="render_msg" />
<%namespace file="/admin/agent_shed_repository/common.mako" import="*" />
<%namespace file="/admin/agent_shed_repository/repository_actions_menu.mako" import="*" />

<%
repository = context.get( 'repository', None )
if isinstance( repository, list ):
    repositories = repository
else:
    repositories = [ repository ]
%>

%if len( repositories ) == 1:
    ${render_galaxy_repository_actions( repositories[0] )}
%endif

%if message:
    ${render_msg( message, status )}
%endif

<div class="agentForm">
<form name="deactivate_or_uninstall_repository" id="deactivate_or_uninstall_repository" action="${ h.url_for( controller='admin_agentshed', action='deactivate_or_uninstall_repository' ) }" method="post" >
%for repository in repositories:
    <input type="hidden" name="id" value="${ trans.security.encode_id( repository.id ) | h }" />
    <div class="agentFormTitle">${repository.name|h}</div>
    <div class="agentFormBody">
            <div class="form-row">
                <label>Description:</label>
                ${repository.description|h}
                <div style="clear: both"></div>
            </div>
            <div class="form-row">
                <label>Revision:</label>
                ${repository.changeset_revision|h}</a>
            </div>
            <div class="form-row">
                <label>Agent shed:</label>
                ${repository.agent_shed|h}
                <div style="clear: both"></div>
            </div>
            <div class="form-row">
                <label>Owner:</label>
                ${repository.owner|h}
            </div>
            <div class="form-row">
                <label>Deleted:</label>
                ${repository.deleted|h}
            </div>
            <div class="form-row">
                <%
                    can_deactivate_repository = repository.can_deactivate
                    can_uninstall_repository = repository.can_uninstall
                %>
                %if can_deactivate_repository:
                    <table width="100%" border="0" cellpadding="0" cellspacing="0">
                        <tr>
                            <td bgcolor="#D8D8D8">
                                <label>Deactivating this repository will result in the following:</label>
                            </td>
                        </tr>
                    </table>
                    <div class="agentParamHelp" style="clear: both;">
                            * The repository and all of its contents will remain on disk and can still be used by dependent items.
                    </div>
                    %if repository.includes_agents_for_display_in_agent_panel:
                        <div class="agentParamHelp" style="clear: both;">
                            * The repository's agents will not be loaded into the agent panel.
                        </div>
                    %endif
                    %if repository.includes_agent_dependencies:
                        <div class="agentParamHelp" style="clear: both;">
                            * The repository's installed agent dependencies will remain on disk.
                        </div>
                    %endif
                    %if repository.includes_datatypes:
                        <div class="agentParamHelp" style="clear: both;">
                            * The repository's datatypes, datatype converters and display applications will be eliminated from the datatypes registry.
                        </div>
                    %endif
                    <div class="agentParamHelp" style="clear: both;">
                        * The repository record's deleted column in the agent_shed_repository database table will be set to True.
                    </div>
                    <br/>
                %endif
                %if can_uninstall_repository:
                    <table width="100%" border="0" cellpadding="0" cellspacing="0">
                        <tr>
                            <td bgcolor="#D8D8D8">
                                <label>Uninstalling this repository will result in the following:</label>
                            </td>
                        </tr>
                    </table>
                    <div class="agentParamHelp" style="clear: both;">
                        * The repository and all of its contents will be removed from disk and can no longer be used by dependent items.
                    </div>
                    %if repository.includes_agents_for_display_in_agent_panel:
                        <div class="agentParamHelp" style="clear: both;">
                            * The repository's agent tag sets will be removed from the agent config file in which they are defined.
                        </div>
                    %endif
                    %if repository.includes_agent_dependencies:
                        <div class="agentParamHelp" style="clear: both;">
                            * The repository's installed agent dependencies will be removed from disk and can no longer be used by dependent items.
                        </div>
                        <div class="agentParamHelp" style="clear: both;">
                            * Each associated agent dependency record's status column in the agent_dependency database table will be set to 'Uninstalled'.
                        </div>
                    %endif
                    %if repository.includes_datatypes:
                        <div class="agentParamHelp" style="clear: both;">
                            * The repository's datatypes, datatype converters and display applications will be eliminated from the datatypes registry.
                        </div>
                    %endif
                    <div class="agentParamHelp" style="clear: both;">
                        * The repository record's deleted column in the agent_shed_repository database table will be set to True.
                    </div>
                    <div class="agentParamHelp" style="clear: both;">
                        * The repository record's uninstalled column in the agent_shed_repository database table will be set to True.
                    </div>
                    <div style="clear: both"></div>
                    <br/>
                    <%                        
                        irm = trans.app.installed_repository_manager
                        repository_tup = irm.get_repository_tuple_for_installed_repository_manager( repository )

                        # Get installed repositories that this repository requires.
                        installed_dependent_repositories = []
                        installed_runtime_dependent_agent_dependencies = []
                        installed_dependent_repositories = irm.installed_dependent_repositories_of_installed_repositories.get( repository_tup, [] )

                        # Get this repository's installed agent dependencies.
                        installed_agent_dependencies = irm.installed_agent_dependencies_of_installed_repositories.get( repository_tup, [] )

                        # Get installed runtime dependent agent dependencies of this repository's installed agent dependencies.
                        installed_runtime_dependent_agent_dependencies = []
                        for itd_tup in installed_agent_dependencies:
                            installed_dependent_td_tups = \
                                irm.installed_runtime_dependent_agent_dependencies_of_installed_agent_dependencies.get( itd_tup, [] )
                            if installed_dependent_td_tups:
                                installed_runtime_dependent_agent_dependencies.extend( installed_dependent_td_tups )
                    %>
                    %if installed_dependent_repositories or installed_runtime_dependent_agent_dependencies:
                        <table width="100%" border="0" cellpadding="0" cellspacing="0">
                            <tr>
                                <td bgcolor="#D8D8D8">
                                    <label>Uninstalling this repository will affect the following dependent items:</label>
                                </td>
                            </tr>
                        </table>
                        %if installed_dependent_repositories:
                            <label>Dependent repositories:</label>
                            <ul>
                            %for installed_dependent_repository_tup in installed_dependent_repositories:
                                <%
                                    agent_shed, name, owner, installed_changeset_revision = installed_dependent_repository_tup
                                %>
                                <li>Revision <b>${ installed_changeset_revision | h}</b> of repository <b>${name | h}</b> owned by <b>${owner | h}</b></li>
                            %endfor
                            </ul>
                        %endif
                        %if installed_runtime_dependent_agent_dependencies:
                            <label>Runtime dependent agent dependencies of this repository's agent dependencies:</label>
                            <ul>
                                %for td_tup in installed_runtime_dependent_agent_dependencies:
                                    <%
                                        agent_shed_repository_id, name, version, type = td_tup
                                        containing_repository = irm.get_containing_repository_for_agent_dependency( td_tup )
                                        repository_name = containing_repository.name
                                        changeset_revision = containing_repository.changeset_revision
                                        owner = containing_repository.owner
                                    %>
                                    <li>
                                        Version <b>${version | h}</b> of ${type | h} <b>${name | h}</b> contained in revision 
                                        <b>${changeset_revision | h}</b> of repository <b>${repository_name | h}</b> owned by <b>${owner | h}</b>
                                    </li>
                                %endfor
                            </ul>
                        %endif
                        <br/>
                    %endif
                %endif
            </div>
        </div>
%endfor
            <div class="form-row">
                <%
                    can_deactivate_repository = True in map( lambda x: x.can_deactivate, repositories )
                    can_uninstall_repository = True in map( lambda x: x.can_uninstall, repositories )
                %>
                %if can_deactivate_repository and can_uninstall_repository:
                    <% deactivate_uninstall_button_text = "Deactivate or Uninstall" %>
                    ${remove_from_disk_check_box.get_html()}
                    <label for="remove_from_disk" style="display: inline;font-weight:normal;">Check to uninstall or leave blank to deactivate</label>
                    <br/><br/>
                %elif can_deactivate_repository:
                    <% deactivate_uninstall_button_text = "Deactivate" %>
                %else:
                    <% deactivate_uninstall_button_text = "Uninstall" %>
                    ##hack to mimic check box
                    <input type="hidden" name="remove_from_disk" value="true"/><input type="hidden" name="remove_from_disk" value="true"/>
                %endif
                <input type="submit" name="deactivate_or_uninstall_repository_button" value="${deactivate_uninstall_button_text|h}"/>
            </div>
        </form>
    </div>
</div>
