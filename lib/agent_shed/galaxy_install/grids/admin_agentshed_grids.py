import logging

from sqlalchemy import false, or_

import agent_shed.util.shed_util_common as suc
from galaxy import util
from galaxy.model import agent_shed_install
from galaxy.web import url_for
from galaxy.web.framework.helpers import iff, grids
from agent_shed.util import agent_dependency_util

log = logging.getLogger( __name__ )


def generate_deprecated_repository_img_str( include_mouse_over=False ):
    if include_mouse_over:
        deprecated_tip_str = 'class="icon-button" title="This repository is deprecated in the Agent Shed"'
    else:
        deprecated_tip_str = ''
    return '<img src="%s/images/icon_error_sml.gif" %s/>' % ( url_for( '/static' ), deprecated_tip_str )


def generate_includes_workflows_img_str( include_mouse_over=False ):
    if include_mouse_over:
        deprecated_tip_str = 'class="icon-button" title="This repository contains exported workflows"'
    else:
        deprecated_tip_str = ''
    return '<img src="%s/images/fugue/gear.png" %s/>' % ( url_for( '/static' ), deprecated_tip_str )


def generate_latest_revision_img_str( include_mouse_over=False ):
    if include_mouse_over:
        latest_revision_tip_str = 'class="icon-button" title="This is the latest installable revision of this repository"'
    else:
        latest_revision_tip_str = ''
    return '<img src="%s/june_2007_style/blue/ok_small.png" %s/>' % ( url_for( '/static' ), latest_revision_tip_str )


def generate_revision_updates_img_str( include_mouse_over=False ):
    if include_mouse_over:
        revision_updates_tip_str = 'class="icon-button" title="Updates are available in the Agent Shed for this revision"'
    else:
        revision_updates_tip_str = ''
    return '<img src="%s/images/icon_warning_sml.gif" %s/>' % ( url_for( '/static' ), revision_updates_tip_str )


def generate_revision_upgrades_img_str( include_mouse_over=False ):
    if include_mouse_over:
        revision_upgrades_tip_str = 'class="icon-button" title="A newer installable revision is available for this repository"'
    else:
        revision_upgrades_tip_str = ''
    return '<img src="%s/images/up.gif" %s/>' % ( url_for( '/static' ), revision_upgrades_tip_str )


def generate_unknown_img_str( include_mouse_over=False ):
    if include_mouse_over:
        unknown_tip_str = 'class="icon-button" title="Unable to get information from the Agent Shed"'
    else:
        unknown_tip_str = ''
    return '<img src="%s/june_2007_style/blue/question-octagon-frame.png" %s/>' % ( url_for( '/static' ), unknown_tip_str )


class InstalledRepositoryGrid( grids.Grid ):

    class AgentShedStatusColumn( grids.TextColumn ):

        def get_value( self, trans, grid, agent_shed_repository ):
            if agent_shed_repository.agent_shed_status:
                agent_shed_status_str = ''
                if agent_shed_repository.is_deprecated_in_agent_shed:
                    agent_shed_status_str += generate_deprecated_repository_img_str( include_mouse_over=True )
                if agent_shed_repository.is_latest_installable_revision:
                    agent_shed_status_str += generate_latest_revision_img_str( include_mouse_over=True )
                if agent_shed_repository.revision_update_available:
                    agent_shed_status_str += generate_revision_updates_img_str( include_mouse_over=True )
                if agent_shed_repository.upgrade_available:
                    agent_shed_status_str += generate_revision_upgrades_img_str( include_mouse_over=True )
                if agent_shed_repository.includes_workflows:
                    agent_shed_status_str += generate_includes_workflows_img_str( include_mouse_over=True )
            else:
                agent_shed_status_str = generate_unknown_img_str( include_mouse_over=True )
            return agent_shed_status_str

    class NameColumn( grids.TextColumn ):

        def get_value( self, trans, grid, agent_shed_repository ):
            return str( agent_shed_repository.name )

    class DescriptionColumn( grids.TextColumn ):

        def get_value( self, trans, grid, agent_shed_repository ):
            return util.unicodify( agent_shed_repository.description )

    class OwnerColumn( grids.TextColumn ):

        def get_value( self, trans, grid, agent_shed_repository ):
            return str( agent_shed_repository.owner )

    class RevisionColumn( grids.TextColumn ):

        def get_value( self, trans, grid, agent_shed_repository ):
            return str( agent_shed_repository.changeset_revision )

    class StatusColumn( grids.TextColumn ):

        def get_value( self, trans, grid, agent_shed_repository ):
            return suc.get_agent_shed_repository_status_label( trans.app, agent_shed_repository )

    class AgentShedColumn( grids.TextColumn ):

        def get_value( self, trans, grid, agent_shed_repository ):
            return agent_shed_repository.agent_shed

    class DeletedColumn( grids.DeletedColumn ):

            def get_accepted_filters( self ):
                """ Returns a list of accepted filters for this column. """
                accepted_filter_labels_and_vals = { "Active" : "False", "Deactivated or uninstalled" : "True", "All": "All" }
                accepted_filters = []
                for label, val in accepted_filter_labels_and_vals.items():
                    args = { self.key: val }
                    accepted_filters.append( grids.GridColumnFilter( label, args) )
                return accepted_filters

    # Grid definition
    title = "Installed agent shed repositories"
    model_class = agent_shed_install.AgentShedRepository
    template = '/admin/agent_shed_repository/grid.mako'
    default_sort_key = "name"
    columns = [
        AgentShedStatusColumn( label="" ),
        NameColumn( label="Name",
                    key="name",
                    link=( lambda item: iff( item.status in [ agent_shed_install.AgentShedRepository.installation_status.CLONING ],
                                             None,
                                             dict( operation="manage_repository", id=item.id ) ) ),
                    attach_popup=True ),
        DescriptionColumn( label="Description" ),
        OwnerColumn( label="Owner" ),
        RevisionColumn( label="Revision" ),
        StatusColumn( label="Installation Status",
                      filterable="advanced" ),
        AgentShedColumn( label="Agent shed" ),
        # Columns that are valid for filtering but are not visible.
        DeletedColumn( label="Status",
                       key="deleted",
                       visible=False,
                       filterable="advanced" )
    ]
    columns.append( grids.MulticolFilterColumn( "Search repository name",
                                                cols_to_filter=[ columns[ 1 ] ],
                                                key="free-text-search",
                                                visible=False,
                                                filterable="standard" ) )
    global_actions = [
        grids.GridAction( label="Update agent shed status",
                          url_args=dict( controller='admin_agentshed',
                                         action='update_agent_shed_status_for_installed_repository',
                                         all_installed_repositories=True ),
                         inbound=False )
    ]
    operations = [ grids.GridOperation( label="Update agent shed status",
                                        condition=( lambda item: not item.deleted ),
                                        allow_multiple=False,
                                        url_args=dict( controller='admin_agentshed',
                                                       action='browse_repositories',
                                                       operation='update agent shed status' ) ),
                   grids.GridOperation( label="Get updates",
                                        condition=( lambda item:
                                                    not item.deleted and
                                                    item.revision_update_available and
                                                    item.status not in [
                                                        agent_shed_install.AgentShedRepository.installation_status.ERROR,
                                                        agent_shed_install.AgentShedRepository.installation_status.NEW ] ),
                                        allow_multiple=False,
                                        url_args=dict( controller='admin_agentshed',
                                                       action='browse_repositories',
                                                       operation='get updates' ) ),
                   grids.GridOperation( label="Install latest revision",
                                        condition=( lambda item: item.upgrade_available ),
                                        allow_multiple=False,
                                        url_args=dict( controller='admin_agentshed',
                                                       action='browse_repositories',
                                                       operation='install latest revision' ) ),
                   grids.GridOperation( label="Install",
                                        condition=( lambda item:
                                                    not item.deleted and
                                                    item.status == agent_shed_install.AgentShedRepository.installation_status.NEW ),
                                        allow_multiple=False,
                                        url_args=dict( controller='admin_agentshed',
                                                       action='manage_repository',
                                                       operation='install' ) ),
                   grids.GridOperation( label="Deactivate or uninstall",
                                        condition=( lambda item:
                                                    not item.deleted and
                                                    item.status != agent_shed_install.AgentShedRepository.installation_status.NEW ),
                                        allow_multiple=True,
                                        url_args=dict( controller='admin_agentshed',
                                                       action='browse_repositories',
                                                       operation='deactivate or uninstall' ) ),
                   grids.GridOperation( label="Reset to install",
                                        condition=( lambda item:
                                                    ( item.status == agent_shed_install.AgentShedRepository.installation_status.ERROR ) ),
                                        allow_multiple=False,
                                        url_args=dict( controller='admin_agentshed',
                                                       action='browse_repositories',
                                                       operation='reset to install' ) ),
                   grids.GridOperation( label="Activate or reinstall",
                                        condition=( lambda item: item.deleted ),
                                        allow_multiple=False,
                                        target=None,
                                        url_args=dict( controller='admin_agentshed',
                                                       action='browse_repositories',
                                                       operation='activate or reinstall' ) ),
                   grids.GridOperation( label="Purge",
                                        condition=( lambda item: item.is_new ),
                                        allow_multiple=False,
                                        target=None,
                                        url_args=dict( controller='admin_agentshed',
                                                       action='browse_repositories',
                                                       operation='purge' ) ) ]
    standard_filters = []
    default_filter = dict( deleted="False" )
    num_rows_per_page = 50
    preserve_state = False
    use_paging = False

    def build_initial_query( self, trans, **kwd ):
        return trans.install_model.context.query( self.model_class ) \
                                          .order_by( self.model_class.table.c.agent_shed,
                                                     self.model_class.table.c.name,
                                                     self.model_class.table.c.owner,
                                                     self.model_class.table.c.ctx_rev )

    @property
    def legend( self ):
        legend_str = '%s&nbsp;&nbsp;Updates are available in the Agent Shed for this revision<br/>' % generate_revision_updates_img_str()
        legend_str += '%s&nbsp;&nbsp;A newer installable revision is available for this repository<br/>' % generate_revision_upgrades_img_str()
        legend_str += '%s&nbsp;&nbsp;This is the latest installable revision of this repository<br/>' % generate_latest_revision_img_str()
        legend_str += '%s&nbsp;&nbsp;This repository is deprecated in the Agent Shed<br/>' % generate_deprecated_repository_img_str()
        legend_str += '%s&nbsp;&nbsp;This repository contains exported workflows<br/>' % generate_includes_workflows_img_str()
        legend_str += '%s&nbsp;&nbsp;Unable to get information from the Agent Shed<br/>' % generate_unknown_img_str()
        return legend_str


class RepositoryInstallationGrid( grids.Grid ):

    class NameColumn( grids.TextColumn ):

        def get_value( self, trans, grid, agent_shed_repository ):
            return agent_shed_repository.name

    class DescriptionColumn( grids.TextColumn ):

        def get_value( self, trans, grid, agent_shed_repository ):
            return agent_shed_repository.description

    class OwnerColumn( grids.TextColumn ):

        def get_value( self, trans, grid, agent_shed_repository ):
            return agent_shed_repository.owner

    class RevisionColumn( grids.TextColumn ):

        def get_value( self, trans, grid, agent_shed_repository ):
            return agent_shed_repository.changeset_revision

    class StatusColumn( grids.TextColumn ):

        def get_value( self, trans, grid, agent_shed_repository ):
            status_label = agent_shed_repository.status
            if agent_shed_repository.status in [ trans.install_model.AgentShedRepository.installation_status.CLONING,
                                                trans.install_model.AgentShedRepository.installation_status.SETTING_TOOL_VERSIONS,
                                                trans.install_model.AgentShedRepository.installation_status.INSTALLING_TOOL_DEPENDENCIES,
                                                trans.install_model.AgentShedRepository.installation_status.LOADING_PROPRIETARY_DATATYPES ]:
                bgcolor = trans.install_model.AgentShedRepository.states.INSTALLING
            elif agent_shed_repository.status in [ trans.install_model.AgentShedRepository.installation_status.NEW,
                                                 trans.install_model.AgentShedRepository.installation_status.UNINSTALLED ]:
                bgcolor = trans.install_model.AgentShedRepository.states.UNINSTALLED
            elif agent_shed_repository.status in [ trans.install_model.AgentShedRepository.installation_status.ERROR ]:
                bgcolor = trans.install_model.AgentShedRepository.states.ERROR
            elif agent_shed_repository.status in [ trans.install_model.AgentShedRepository.installation_status.DEACTIVATED ]:
                bgcolor = trans.install_model.AgentShedRepository.states.WARNING
            elif agent_shed_repository.status in [ trans.install_model.AgentShedRepository.installation_status.INSTALLED ]:
                if agent_shed_repository.missing_agent_dependencies or agent_shed_repository.missing_repository_dependencies:
                    bgcolor = trans.install_model.AgentShedRepository.states.WARNING
                if agent_shed_repository.missing_agent_dependencies and not agent_shed_repository.missing_repository_dependencies:
                    status_label = '%s, missing agent dependencies' % status_label
                if agent_shed_repository.missing_repository_dependencies and not agent_shed_repository.missing_agent_dependencies:
                    status_label = '%s, missing repository dependencies' % status_label
                if agent_shed_repository.missing_agent_dependencies and agent_shed_repository.missing_repository_dependencies:
                    status_label = '%s, missing both agent and repository dependencies' % status_label
                if not agent_shed_repository.missing_agent_dependencies and not agent_shed_repository.missing_repository_dependencies:
                    bgcolor = trans.install_model.AgentShedRepository.states.OK
            else:
                bgcolor = trans.install_model.AgentShedRepository.states.ERROR
            rval = '<div class="count-box state-color-%s" id="RepositoryStatus-%s">%s</div>' % \
                ( bgcolor, trans.security.encode_id( agent_shed_repository.id ), status_label )
            return rval

    title = "Monitor installing agent shed repositories"
    template = "admin/agent_shed_repository/repository_installation_grid.mako"
    model_class = agent_shed_install.AgentShedRepository
    default_sort_key = "-create_time"
    num_rows_per_page = 50
    preserve_state = True
    use_paging = False
    columns = [
        NameColumn( "Name",
                    link=( lambda item: iff( item.status in
                                             [ agent_shed_install.AgentShedRepository.installation_status.NEW,
                                               agent_shed_install.AgentShedRepository.installation_status.CLONING,
                                               agent_shed_install.AgentShedRepository.installation_status.SETTING_TOOL_VERSIONS,
                                               agent_shed_install.AgentShedRepository.installation_status.INSTALLING_REPOSITORY_DEPENDENCIES,
                                               agent_shed_install.AgentShedRepository.installation_status.INSTALLING_TOOL_DEPENDENCIES,
                                               agent_shed_install.AgentShedRepository.installation_status.LOADING_PROPRIETARY_DATATYPES,
                                               agent_shed_install.AgentShedRepository.installation_status.UNINSTALLED ],
                                             None, dict( action="manage_repository", id=item.id ) ) ),
                    filterable="advanced" ),
        DescriptionColumn( "Description",
                    filterable="advanced" ),
        OwnerColumn( "Owner",
                    filterable="advanced" ),
        RevisionColumn( "Revision",
                    filterable="advanced" ),
        StatusColumn( "Installation Status",
                      filterable="advanced",
                      label_id_prefix="RepositoryStatus-" )
    ]
    operations = []

    def build_initial_query( self, trans, **kwd ):
        clause_list = []
        agent_shed_repository_ids = util.listify( kwd.get( 'agent_shed_repository_ids', None ) )
        if agent_shed_repository_ids:
            for agent_shed_repository_id in agent_shed_repository_ids:
                clause_list.append( self.model_class.table.c.id == trans.security.decode_id( agent_shed_repository_id ) )
            if clause_list:
                return trans.install_model.context.query( self.model_class ) \
                                                  .filter( or_( *clause_list ) )
        for agent_shed_repository in trans.install_model.context.query( self.model_class ) \
                                                               .filter( self.model_class.table.c.deleted == false() ):
            if agent_shed_repository.status in [ trans.install_model.AgentShedRepository.installation_status.NEW,
                                               trans.install_model.AgentShedRepository.installation_status.CLONING,
                                               trans.install_model.AgentShedRepository.installation_status.SETTING_TOOL_VERSIONS,
                                               trans.install_model.AgentShedRepository.installation_status.INSTALLING_TOOL_DEPENDENCIES,
                                               trans.install_model.AgentShedRepository.installation_status.LOADING_PROPRIETARY_DATATYPES ]:
                clause_list.append( self.model_class.table.c.id == agent_shed_repository.id )
        if clause_list:
            return trans.install_model.context.query( self.model_class ) \
                                              .filter( or_( *clause_list ) )
        return trans.install_model.context.query( self.model_class ) \
                                          .filter( self.model_class.table.c.status == trans.install_model.AgentShedRepository.installation_status.NEW )

    def apply_query_filter( self, trans, query, **kwd ):
        agent_shed_repository_id = kwd.get( 'agent_shed_repository_id', None )
        if agent_shed_repository_id:
            return query.filter_by( agent_shed_repository_id=trans.security.decode_id( agent_shed_repository_id ) )
        return query


class AgentDependencyGrid( grids.Grid ):

    class NameColumn( grids.TextColumn ):

        def get_value( self, trans, grid, agent_dependency ):
            return agent_dependency.name

    class VersionColumn( grids.TextColumn ):

        def get_value( self, trans, grid, agent_dependency ):
            return agent_dependency.version

    class TypeColumn( grids.TextColumn ):

        def get_value( self, trans, grid, agent_dependency ):
            return agent_dependency.type

    class StatusColumn( grids.TextColumn ):

        def get_value( self, trans, grid, agent_dependency ):
            if agent_dependency.status in [ trans.install_model.AgentDependency.installation_status.INSTALLING ]:
                bgcolor = trans.install_model.AgentDependency.states.INSTALLING
            elif agent_dependency.status in [ trans.install_model.AgentDependency.installation_status.NEVER_INSTALLED,
                                             trans.install_model.AgentDependency.installation_status.UNINSTALLED ]:
                bgcolor = trans.install_model.AgentDependency.states.UNINSTALLED
            elif agent_dependency.status in [ trans.install_model.AgentDependency.installation_status.ERROR ]:
                bgcolor = trans.install_model.AgentDependency.states.ERROR
            elif agent_dependency.status in [ trans.install_model.AgentDependency.installation_status.INSTALLED ]:
                bgcolor = trans.install_model.AgentDependency.states.OK
            rval = '<div class="count-box state-color-%s" id="AgentDependencyStatus-%s">%s</div>' % \
                ( bgcolor, trans.security.encode_id( agent_dependency.id ), agent_dependency.status )
            return rval

    title = "Agent Dependencies"
    template = "admin/agent_shed_repository/agent_dependencies_grid.mako"
    model_class = agent_shed_install.AgentDependency
    default_sort_key = "-create_time"
    num_rows_per_page = 50
    preserve_state = True
    use_paging = False
    columns = [
        NameColumn( "Name",
                    link=( lambda item: iff( item.status in [ agent_shed_install.AgentDependency.installation_status.NEVER_INSTALLED,
                                                              agent_shed_install.AgentDependency.installation_status.INSTALLING,
                                                              agent_shed_install.AgentDependency.installation_status.UNINSTALLED ],
                                             None,
                                             dict( action="manage_agent_dependencies", operation='browse', id=item.id ) ) ),
                    filterable="advanced" ),
        VersionColumn( "Version",
                       filterable="advanced" ),
        TypeColumn( "Type",
                    filterable="advanced" ),
        StatusColumn( "Installation Status",
                      filterable="advanced" ),
    ]

    def build_initial_query( self, trans, **kwd ):
        agent_dependency_ids = agent_dependency_util.get_agent_dependency_ids( as_string=False, **kwd )
        if agent_dependency_ids:
            clause_list = []
            for agent_dependency_id in agent_dependency_ids:
                clause_list.append( self.model_class.table.c.id == trans.security.decode_id( agent_dependency_id ) )
            return trans.install_model.context.query( self.model_class ) \
                                              .filter( or_( *clause_list ) )
        return trans.install_model.context.query( self.model_class )

    def apply_query_filter( self, trans, query, **kwd ):
        agent_dependency_id = kwd.get( 'agent_dependency_id', None )
        if agent_dependency_id:
            return query.filter_by( agent_dependency_id=trans.security.decode_id( agent_dependency_id ) )
        return query
