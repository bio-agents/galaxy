<%inherit file="/base.mako"/>
<%namespace file="/admin/agent_shed_repository/common.mako" import="*" />

<%def name="javascripts()">
   ${parent.javascripts()}
   ${repository_installation_status_updater()}
   ${repository_installation_updater()}
   ${self.repository_installation_javascripts()}
</%def>

<%def name="repository_installation_javascripts()">
    <script type="text/javascript">
        $(document).ready(function( ){
            initiate_repository_installation( "${initiate_repository_installation_ids}", "${encoded_kwd}", "${reinstalling}" );
        });
        var initiate_repository_installation = function ( iri_ids, encoded_kwd, reinstalling ) {
            // Make ajax call
            $.ajax( {
                type: "POST",
                url: "${h.url_for( controller='admin_agentshed', action='manage_repositories' )}",
                dataType: "html",
                data: { operation: "install", agent_shed_repository_ids: iri_ids, encoded_kwd: encoded_kwd, reinstalling: reinstalling },
                success : function ( data ) {
                    //alert( "Initializing repository installation succeeded" );
                },
            });
        };
    </script>
</%def>

%if agent_shed_repositories:
    <div class="agentForm">
        <div class="agentFormTitle">Monitor installing agent shed repositories</div>
        <div class="agentFormBody">
            <table class="grid">
                <tr>
                    <td>Name</td>
                    <td>Description</td>
                    <td>Owner</td>
                    <td>Revision</td>
                    <td>Status</td>
                </tr>
                %for agent_shed_repository in agent_shed_repositories:
                    <%
                        encoded_repository_id = trans.security.encode_id( agent_shed_repository.id )
                        ids_of_agent_dependencies_missing_or_being_installed = [ trans.security.encode_id( td.id ) for td in agent_shed_repository.agent_dependencies_missing_or_being_installed ]
                        link_to_manage_agent_dependencies = agent_shed_repository.status in [ trans.install_model.AgentShedRepository.installation_status.INSTALLING_TOOL_DEPENDENCIES ]
                    %>
                    <tr>
                        <td>
                            %if link_to_manage_agent_dependencies:
                                <a class="view-info" href="${h.url_for( controller='admin_agentshed', action='manage_agent_dependencies', agent_dependency_ids=ids_of_agent_dependencies_missing_or_being_installed )}">
                                    ${agent_shed_repository.name|h}
                                </a>
                            %else:
                                <a class="view-info" href="${h.url_for( controller='admin_agentshed', action='manage_repository', id=encoded_repository_id )}">
                                    ${agent_shed_repository.name|h}
                                </a>
                            %endif
                        </td>
                        <td>${agent_shed_repository.description}</td>
                        <td>${agent_shed_repository.owner}</td>
                        <td>${agent_shed_repository.changeset_revision}</td>
                        <td><div id="RepositoryStatus-${encoded_repository_id}">${agent_shed_repository.status|h}</div></td>
                    </tr>
                %endfor
            </table>
            <br clear="left"/>
        </div>
    </div>
%endif
