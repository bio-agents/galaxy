<%inherit file="/webapps/agent_shed/base_panels.mako"/>
<%namespace file="/message.mako" import="render_msg" />

<%def name="stylesheets()">
    ## Include "base.css" for styling agent menu and forms (details)
    ${h.css( "base", "autocomplete_tagging", "agent_menu" )}

    ## But make sure styles for the layout take precedence
    ${parent.stylesheets()}

    <style type="text/css">
        body { margin: 0; padding: 0; overflow: hidden; }
        #left {
            background: #C1C9E5 url(${h.url_for('/static/style/menu_bg.png')}) top repeat-x;
        }
        .unified-panel-body {
            overflow: auto;
        }
        .agentMenu {
            margin-left: 10px;
        }
    </style>
</%def>

<%def name="javascripts()">
    ${parent.javascripts()}
</%def>

<%def name="init()">
    <%
        self.has_left_panel=True
        self.has_right_panel=False
        self.active_view="agents"
    %>
    %if trans.app.config.require_login and not trans.user:
        <script type="text/javascript">
            if ( window != top ) {
                top.location.href = location.href;
            }
        </script>
    %endif
</%def>

<%def name="left_panel()">
    <% can_review_repositories = trans.app.security_agent.user_can_review_repositories( trans.user ) %>
    <div class="unified-panel-header" unselectable="on">
        <div class='unified-panel-header-inner'>${trans.app.shed_counter.unique_valid_agents | h} valid agents on ${trans.app.shed_counter.generation_time | h}</div>
    </div>
    <div class="unified-panel-body">
        <div class="agentMenu">
            <div class="agentSectionList">
                %if user_id or repository_id:
                    ## The route in was a sharable url, and may have included a changeset_revision, although we don't check for it.
                    <div class="agentSectionPad"></div>
                    <div class="agentSectionTitle">
                        All Repositories
                    </div>
                    <div class="agentTitle">
                        <a href="${h.url_for( controller='repository', action='index' )}">Browse by category</a>
                    </div>
                %else:
                    %if repository_metadata:
                        <div class="agentSectionPad"></div>
                        <div class="agentSectionTitle">
                            Search
                        </div>
                        <div class="agentSectionBody">
                            <div class="agentTitle">
                                <a target="galaxy_main" href="${h.url_for( controller='repository', action='find_agents' )}">Search for valid agents</a>
                            </div>
                            <div class="agentTitle">
                                <a target="galaxy_main" href="${h.url_for( controller='repository', action='find_workflows' )}">Search for workflows</a>
                            </div>
                        </div>
                        <div class="agentSectionPad"></div>
                        <div class="agentSectionTitle">
                            Valid Galaxy Utilities
                        </div>
                        <div class="agentTitle">
                            <a target="galaxy_main" href="${h.url_for( controller='repository', action='browse_agents' )}">Agents</a>
                        </div>
                        <div class="agentTitle">
                            <a target="galaxy_main" href="${h.url_for( controller='repository', action='browse_datatypes' )}">Custom datatypes</a>
                        </div>
                        <div class="agentTitle">
                            <a target="galaxy_main" href="${h.url_for( controller='repository', action='browse_repository_dependencies' )}">Repository dependency definitions</a>
                        </div>
                        <div class="agentTitle">
                            <a target="galaxy_main" href="${h.url_for( controller='repository', action='browse_agent_dependencies' )}">Agent dependency definitions</a>
                        </div>
                    %endif
                    <div class="agentSectionPad"></div>
                    <div class="agentSectionTitle">
                        All Repositories
                    </div>
                    <div class="agentTitle">
                        <a target="galaxy_main" href="${h.url_for( controller='repository', action='browse_categories' )}">Browse by category</a>
                    </div>
                    %if trans.user:
                        %if trans.user.active_repositories or can_administer_repositories:
                            <div class="agentSectionPad"></div>
                            <div class="agentSectionTitle">
                                Repositories I Can Change
                            </div>
                            <div class="agentTitle">
                                <a target="galaxy_main" href="${h.url_for( controller='repository', action='browse_repositories_i_own' )}">Repositories I own</a>
                            </div>
                            %if can_administer_repositories:
                                <div class="agentTitle">
                                    <a target="galaxy_main" href="${h.url_for( controller='repository', action='browse_repositories_i_can_administer' )}">Repositories I can administer</a>
                                </div>
                            %endif
                            %if has_reviewed_repositories:
                                <div class="agentTitle">
                                    <a target="galaxy_main" href="${h.url_for( controller='repository', action='browse_repositories', operation='reviewed_repositories_i_own' )}">Reviewed repositories I own</a>
                                </div>
                            %endif
                            %if has_deprecated_repositories:
                                <div class="agentTitle">
                                    <a target="galaxy_main" href="${h.url_for( controller='repository', action='browse_deprecated_repositories_i_own' )}">Deprecated repositories I own</a>
                                </div>
                            %endif
                            <div class="agentTitle">
                                <a target="galaxy_main" href="${h.url_for( controller='repository', action='browse_my_writable_repositories' )}">My writable repositories</a>
                            </div>
                            <div class="agentTitle">
                                <a target="galaxy_main" href="${h.url_for( controller='repository', action='reset_metadata_on_my_writable_repositories_in_agent_shed' )}">Reset metadata on my repositories</a>
                            </div>
                            <div class="agentTitle">
                                <a target="galaxy_main" href="${h.url_for( controller='repository', action='browse_my_writable_repositories_missing_agent_test_components' )}">Latest revision: missing agent tests</a>
                            </div>
                            <div class="agentTitle">
                                <a target="galaxy_main" href="${h.url_for( controller='repository', action='browse_my_writable_repositories_with_install_errors' )}">Latest revision: installation errors</a>
                            </div>
                            <div class="agentTitle">
                                <a target="galaxy_main" href="${h.url_for( controller='repository', action='browse_my_writable_repositories_with_failing_agent_tests' )}">Latest revision: failing agent tests</a>
                            </div>
                            <div class="agentTitle">
                                <a target="galaxy_main" href="${h.url_for( controller='repository', action='browse_my_writable_repositories_with_skip_agent_test_checked' )}">Latest revision: skip agent tests</a>
                            </div>
                            <div class="agentTitle">
                                <a target="galaxy_main" href="${h.url_for( controller='repository', action='browse_my_writable_repositories_with_no_failing_agent_tests' )}">Latest revision: all agent tests pass</a>
                            </div>
                            <div class="agentTitle">
                                <a target="galaxy_main" href="${h.url_for( controller='repository', action='browse_my_writable_repositories_with_invalid_agents' )}">Latest revision: invalid agents</a>
                            </div>
                        %endif
                        <div class="agentSectionPad"></div>
                        <div class="agentSectionTitle">
                            Available Actions
                        </div>
                        <div class="agentTitle">
                            <a target="galaxy_main" href="${h.url_for( controller='repository', action='create_repository' )}">Create new repository</a>
                        </div>
                        <div class="agentTitle">
                            <a target="galaxy_main" href="${h.url_for( controller='repository', action='upload_capsule' )}">Import repository capsule</a>
                        </div>
                        %if trans.app.config.enable_galaxy_flavor_docker_image:
                            <div class="agentTitle">
                                <a target="galaxy_main" href="${h.url_for( controller='repository', action='create_galaxy_docker_image' )}">Create Galaxy Docker Image</a>
                            </div>
                        %endif
                        %if can_review_repositories:
                            <div class="agentSectionPad"></div>
                            <div class="agentSectionTitle">
                                Reviewing Repositories
                            </div>
                            <div class="agentSectionBody">
                                <div class="agentSectionBg">
                                    <div class="agentTitle">
                                        <a target="galaxy_main" href="${h.url_for( controller='repository_review', action='manage_repositories_ready_for_review' )}">Repositories ready for review</a>
                                    </div>
                                    <div class="agentTitle">
                                        <a target="galaxy_main" href="${h.url_for( controller='repository_review', action='manage_repositories_without_reviews' )}">All repositories with no reviews</a>
                                    </div>
                                    %if trans.user.repository_reviews:
                                        <div class="agentTitle">
                                            <a target="galaxy_main" href="${h.url_for( controller='repository_review', action='manage_repositories_reviewed_by_me' )}">Repositories reviewed by me</a>
                                        </div>
                                    %endif
                                    <div class="agentTitle">
                                        <a target="galaxy_main" href="${h.url_for( controller='repository_review', action='manage_repositories_with_reviews' )}">All reviewed repositories</a>
                                    </div>
                                    <div class="agentTitle">
                                        <a target="galaxy_main" href="${h.url_for( controller='repository_review', action='manage_components' )}">Manage review components</a>
                                    </div>
                                </div>
                            </div>
                            <div class="agentSectionPad"></div>
                            <div class="agentSectionTitle">
                                Reviewing Repositories With Agents
                            </div>
                            <div class="agentSectionBody">
                                <div class="agentSectionBg">
                                    <div class="agentTitle">
                                        <a target="galaxy_main" href="${h.url_for( controller='repository', action='browse_repositories_missing_agent_test_components' )}">Latest revision: missing agent tests</a>
                                    </div>
                                    <div class="agentTitle">
                                        <a target="galaxy_main" href="${h.url_for( controller='repository', action='browse_repositories_with_install_errors' )}">Latest revision: installation errors</a>
                                    </div>
                                    <div class="agentTitle">
                                        <a target="galaxy_main" href="${h.url_for( controller='repository', action='browse_repositories_with_failing_agent_tests' )}">Latest revision: failing agent tests</a>
                                    </div>
                                    <div class="agentTitle">
                                        <a target="galaxy_main" href="${h.url_for( controller='repository', action='browse_repositories_with_skip_agent_test_checked' )}">Latest revision: skip agent tests</a>
                                    </div>
                                    <div class="agentTitle">
                                        <a target="galaxy_main" href="${h.url_for( controller='repository', action='browse_repositories_with_no_failing_agent_tests' )}">Latest revision: all agent tests pass</a>
                                    </div>
                                    <div class="agentTitle">
                                        <a target="galaxy_main" href="${h.url_for( controller='repository', action='browse_repositories_with_invalid_agents' )}">Latest revision: invalid agents</a>
                                    </div>
                                </div>
                            </div>
                        %endif
                    %else:
                        <div class="agentSectionPad"></div>
                        <div class="agentSectionTitle">
                            Available Actions
                        </div>
                        <div class="agentTitle">
                            <a target="galaxy_main" href="${h.url_for( controller='/user', action='login' )}">Login to create a repository</a>
                        </div>
                        %if trans.app.config.enable_galaxy_flavor_docker_image:
                            <div class="agentTitle">
                                <a target="galaxy_main" href="${h.url_for( controller='repository', action='create_galaxy_docker_image' )}">Create Galaxy Docker Image</a>
                            </div>
                        %endif
                    %endif
                %endif
            </div>
        </div>    
    </div>
</%def>

<%def name="center_panel()">
    <%
        if trans.app.config.require_login and not trans.user:
            center_url = h.url_for( controller='user', action='login', message=message, status=status )
        elif repository_id and changeset_revision:
            # Route in was a sharable url: /view/{owner}/{name}/{changeset_revision}.
            center_url = h.url_for( controller='repository', action='view_repository', id=repository_id, changeset_revision=changeset_revision, message=message, status=status )
        elif repository_id:
            # Route in was a sharable url: /view/{owner}/{name}.
            center_url = h.url_for( controller='repository', action='view_repository', id=repository_id, message=message, status=status )
        elif user_id:
            # Route in was a sharable url: /view/{owner}.
            center_url = h.url_for( controller='repository', action='browse_repositories', operation="repositories_by_user", user_id=user_id, message=message, status=status )
        else:
            center_url = h.url_for( controller='repository', action='browse_categories', message=message, status=status )
    %>
    <iframe name="galaxy_main" id="galaxy_main" frameborder="0" style="position: absolute; width: 100%; height: 100%;" src="${center_url}"></iframe>
</%def>
