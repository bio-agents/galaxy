// MMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM
// === MAIN TOOLSHED GROUP MODULE ====
// MMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM

define([
        'agentshed/scripts/mvc/groups/group-list-view',
        'agentshed/scripts/mvc/groups/group-detail-view',
        'agentshed/scripts/mvc/groups/group-model'
    ],
    function(
        mod_group_list,
        mod_group_detail,
        mod_group_model
    ) {

// ============================================================================
// ROUTER
var AgentshedRouter = Backbone.Router.extend({
    routes: {
        ""                        : "groups",
        ":group_id"               : "group_page"
    }

});

var AgentshedGroups = Backbone.View.extend({
    groupListView: null,
    groupDetailView: null,
    collection: null,

    initialize : function(){
        window.globalTS.groups = this;

        this.ts_router = new AgentshedRouter();
        this.ts_router.on( 'route:groups', function() {
            window.globalTS.groups.groupListView = new mod_group_list.GroupListView();
        });

        this.ts_router.on( 'route:group_page', function( group_id ) {
            window.globalTS.groups.groupDetailView = new mod_group_detail.GroupDetailView( { group_id: group_id } );
        });
        
        Backbone.history.start({pushState: false});
    }
});

return {
    AgentshedGroups: AgentshedGroups
};

});
