var LeftPanel = require( 'layout/panel' ).LeftPanel,
    Agents = require( 'mvc/agent/agents' ),
    Upload = require( 'mvc/upload/upload-view' ),
    _l = require( 'utils/localization' );

/* Builds the agent menu panel on the left of the analysis page */
var AgentPanel = LeftPanel.extend({

    title : _l( 'Agents' ),

    initialize: function( options ){
        LeftPanel.prototype.initialize.call( this, options );
        this.log( this + '.initialize:', options );

        /** @type {Object[]} descriptions of user's workflows to be shown in the agent menu */
        this.stored_workflow_menu_entries = options.stored_workflow_menu_entries || [];

        // create agent search, agent panel, and agent panel view.
        var agent_search = new Agents.AgentSearch({
            search_url  : options.search_url,
            hidden      : false
        });
        var agents = new Agents.AgentCollection( options.agentbox );
        this.agent_panel = new Agents.AgentPanel({
            agent_search : agent_search,
            agents       : agents,
            layout      : options.agentbox_in_panel
        });
        this.agent_panel_view = new Agents.AgentPanelView({ model: this.agent_panel });

        // add upload modal
        this.uploadButton = new Upload({
            nginx_upload_path   : options.nginx_upload_path,
            ftp_upload_site     : options.ftp_upload_site,
            default_genome      : options.default_genome,
            default_extension   : options.default_extension,
        });
    },

    render : function(){
        var self = this;
        LeftPanel.prototype.render.call( self );
        self.$( '.panel-header-buttons' ).append( self.uploadButton.$el );

        // if there are agents, render panel and display everything
        if (self.agent_panel.get( 'layout' ).size() > 0) {
            self.agent_panel_view.render();
            //TODO: why the hide/show?
            self.$( '.agentMenu' ).show();
        }
        self.$( '.agentMenuContainer' ).prepend( self.agent_panel_view.$el );

        self._renderWorkflowMenu();

        // if a agent link has the minsizehint attribute, handle it here (gen. by hiding the agent panel)
        self.$( 'a[minsizehint]' ).click( function() {
            if ( parent.handle_minwidth_hint ) {
                parent.handle_minwidth_hint( $( self ).attr( 'minsizehint' ) );
            }
        });
    },

    /** build the dom for the workflow portion of the agent menu */
    _renderWorkflowMenu : function(){
        var self = this;
        // add internal workflow list
        self.$( '#internal-workflows' ).append( self._templateAgent({
            title   : _l( 'All workflows' ),
            href    : 'workflow/list_for_run'
        }));
        _.each( self.stored_workflow_menu_entries, function( menu_entry ){
            self.$( '#internal-workflows' ).append( self._templateAgent({
                title : menu_entry.stored_workflow.name,
                href  : 'workflow/run?id=' + menu_entry.encoded_stored_workflow_id
            }));
        });
    },

    /** build a link to one agent */
    _templateAgent: function( agent ) {
        return [
            '<div class="agentTitle">',
                // global
                '<a href="', Galaxy.root, agent.href, '" target="galaxy_main">', agent.title, '</a>',
            '</div>'
        ].join('');
    },

    /** override to include inital menu dom and workflow section */
    _templateBody : function(){
        return [
            '<div class="unified-panel-body unified-panel-body-background">',
                '<div class="agentMenuContainer">',
                    '<div class="agentMenu" style="display: none">',
                        '<div id="search-no-results" style="display: none; padding-top: 5px">',
                            '<em><strong>', _l( 'Search did not match any agents.' ), '</strong></em>',
                        '</div>',
                    '</div>',
                    '<div class="agentSectionPad"/>',
                    '<div class="agentSectionPad"/>',
                    '<div class="agentSectionTitle" id="title_XXinternalXXworkflow">',
                        '<span>', _l( 'Workflows' ), '</span>',
                    '</div>',
                    '<div id="internal-workflows" class="agentSectionBody">',
                        '<div class="agentSectionBg"/>',
                    '</div>',
                '</div>',
            '</div>'
        ].join('');
    },

    toString : function(){ return 'AgentPanel'; }
});

module.exports = AgentPanel;