<%inherit file="/base.mako"/>
<%namespace file="/message.mako" import="render_msg" />
<%namespace file="/admin/agent_shed_repository/repository_actions_menu.mako" import="*" />

<%def name="stylesheets()">
    ${parent.stylesheets()}
    ${h.css( "library" )}
</%def>

<%def name="javascripts()">
    ${parent.javascripts()}
</%def>

${render_galaxy_repository_actions( repository )}

%if message:
    ${render_msg( message, status )}
%endif

<div class="warningmessage">
    <p>
        Purging the repository named <b>${repository.name|h}</b> will result in deletion of all records for the
        following associated items from the database.  Click the <b>Purge</b> button to purge this repository
        and its associated items.
    </p>
</div>

<div class="agentForm">
    <div class="agentFormTitle">Purge agent shed repository <b>${repository.name|h}</b></div>
        <form name="purge_repository" id="purge_repository" action="${h.url_for( controller='admin_agentshed', action='purge_repository', id=trans.security.encode_id( repository.id ) )}" method="post" >
            <%
                agent_versions = 0
                agent_dependencies = 0
                required_repositories = 0
                orphan_repository_repository_dependency_association_records = 0
                orphan_repository_dependency_records = 0
                # Count this repository's agent version lineage chain links that will be purged.
                for agent_version in repository.agent_versions:
                    for agent_version_association in agent_version.parent_agent_association:
                        agent_versions += 1
                    for agent_version_association in agent_version.child_agent_association:
                        agent_versions += 1
                    agent_versions += 1
                # Count this repository's associated agent dependencies that will be purged.
                for agent_dependency in repository.agent_dependencies:
                    agent_dependencies += 1
                # Count this repository's associated required repositories that will be purged.
                for rrda in repository.required_repositories:
                    required_repositories += 1
                # Count any "orphan" repository_dependency records associated with the repository but not with any
                # repository_repository_dependency_association records that will be purged.
                for orphan_repository_dependency in \
                    trans.sa_session.query( trans.app.install_model.RepositoryDependency ) \
                                    .filter( trans.app.install_model.RepositoryDependency.table.c.agent_shed_repository_id == repository.id ):
                    for orphan_rrda in \
                        trans.sa_session.query( trans.app.install_model.RepositoryRepositoryDependencyAssociation ) \
                                        .filter( trans.app.install_model.RepositoryRepositoryDependencyAssociation.table.c.repository_dependency_id == orphan_repository_dependency.id ):
                        orphan_repository_repository_dependency_association_records += 1
                    orphan_repository_dependency_records += 1
            %>
            <table class="grid">
                <tr><td>Agent version records</td><td>${agent_versions|h}</td><tr>
                <tr><td>Agent dependency records</td><td>${agent_dependencies|h}</td><tr>
                <tr><td>Repository dependency records</td><td>${required_repositories|h}</td><tr>
                <tr><td>Orphan repository_repository_dependency_association records</td><td>${orphan_repository_repository_dependency_association_records|h}</td><tr>
                <tr><td>Orphan repository_dependency records</td><td>${orphan_repository_dependency_records|h}</td><tr>
            </table>
            <div style="clear: both"></div>
            <div class="form-row">
                <input type="submit" name="purge_repository_button" value="Purge"/>
            </div>
        </form>
    </div>
</div>
