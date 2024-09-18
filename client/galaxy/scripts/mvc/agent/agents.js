/**
 * Model, view, and controller objects for Galaxy agents and agent panel.
 */

 define([
    "libs/underscore",
    "viz/trackster/util",
    "mvc/dataset/data",
    "mvc/agent/agent-form"

], function(_, util, data, AgentForm) {
    'use strict';

/**
 * Mixin for tracking model visibility.
 */
var VisibilityMixin = {
    hidden: false,

    show: function() {
        this.set("hidden", false);
    },

    hide: function() {
        this.set("hidden", true);
    },

    toggle: function() {
        this.set("hidden", !this.get("hidden"));
    },

    is_visible: function() {
        return !this.attributes.hidden;
    }

};

/**
 * A agent parameter.
 */
var AgentParameter = Backbone.Model.extend({
    defaults: {
        name: null,
        label: null,
        type: null,
        value: null,
        html: null,
        num_samples: 5
    },

    initialize: function(options) {
        this.attributes.html = unescape(this.attributes.html);
    },

    copy: function() {
        return new AgentParameter(this.toJSON());
    },

    set_value: function(value) {
        this.set('value', value || '');
    }
});

var AgentParameterCollection = Backbone.Collection.extend({
    model: AgentParameter
});

/**
 * A data agent parameter.
 */
var DataAgentParameter = AgentParameter.extend({});

/**
 * An integer agent parameter.
 */
var IntegerAgentParameter = AgentParameter.extend({
    set_value: function(value) {
        this.set('value', parseInt(value, 10));
    },

    /**
     * Returns samples from a agent input.
     */
    get_samples: function() {
        return d3.scale.linear()
                        .domain([this.get('min'), this.get('max')])
                        .ticks(this.get('num_samples'));
    }
});

var FloatAgentParameter = IntegerAgentParameter.extend({
    set_value: function(value) {
        this.set('value', parseFloat(value));
    }
});

/**
 * A select agent parameter.
 */
var SelectAgentParameter = AgentParameter.extend({
    /**
     * Returns agent options.
     */
    get_samples: function() {
        return _.map(this.get('options'), function(option) {
            return option[0];
        });
    }
});

// Set up dictionary of parameter types.
AgentParameter.subModelTypes = {
    'integer': IntegerAgentParameter,
    'float': FloatAgentParameter,
    'data': DataAgentParameter,
    'select': SelectAgentParameter
};

/**
 * A Galaxy agent.
 */
var Agent = Backbone.Model.extend({
    // Default attributes.
    defaults: {
        id: null,
        name: null,
        description: null,
        target: null,
        inputs: [],
        outputs: []
    },

    urlRoot: Galaxy.root + 'api/agents',

    initialize: function(options) {

        // Set parameters.
        this.set('inputs', new AgentParameterCollection(_.map(options.inputs, function(p) {
            var p_class = AgentParameter.subModelTypes[p.type] || AgentParameter;
            return new p_class(p);
        })));
    },

    /**
     *
     */
    toJSON: function() {
        var rval = Backbone.Model.prototype.toJSON.call(this);

        // Convert inputs to JSON manually.
        rval.inputs = this.get('inputs').map(function(i) { return i.toJSON(); });
        return rval;
    },

    /**
     * Removes inputs of a particular type; this is useful because not all inputs can be handled by
     * client and server yet.
     */
    remove_inputs: function(types) {
        var agent = this,
            incompatible_inputs = agent.get('inputs').filter( function(input) {
                return ( types.indexOf( input.get('type') ) !== -1);
            });
        agent.get('inputs').remove(incompatible_inputs);
    },

    /**
     * Returns object copy, optionally including only inputs that can be sampled.
     */
    copy: function(only_samplable_inputs) {
        var copy = new Agent(this.toJSON());

        // Return only samplable inputs if flag is set.
        if (only_samplable_inputs) {
            var valid_inputs = new Backbone.Collection();
            copy.get('inputs').each(function(input) {
                if (input.get_samples()) {
                    valid_inputs.push(input);
                }
            });
            copy.set('inputs', valid_inputs);
        }

        return copy;
    },

    apply_search_results: function(results) {
        ( _.indexOf(results, this.attributes.id) !== -1 ? this.show() : this.hide() );
        return this.is_visible();
    },

    /**
     * Set a agent input's value.
     */
    set_input_value: function(name, value) {
        this.get('inputs').find(function(input) {
            return input.get('name') === name;
        }).set('value', value);
    },

    /**
     * Set many input values at once.
     */
    set_input_values: function(inputs_dict) {
        var self = this;
        _.each(_.keys(inputs_dict), function(input_name) {
            self.set_input_value(input_name, inputs_dict[input_name]);
        });
    },

    /**
     * Run agent; returns a Deferred that resolves to the agent's output(s).
     */
    run: function() {
        return this._run();
    },

    /**
     * Rerun agent using regions and a target dataset.
     */
    rerun: function(target_dataset, regions) {
        return this._run({
            action: 'rerun',
            target_dataset_id: target_dataset.id,
            regions: regions
        });
    },

    /**
     * Returns input dict for agent's inputs.
     */
    get_inputs_dict: function() {
        var input_dict = {};
        this.get('inputs').each(function(input) {
            input_dict[input.get('name')] = input.get('value');
        });
        return input_dict;
    },

    /**
     * Run agent; returns a Deferred that resolves to the agent's output(s).
     * NOTE: this method is a helper method and should not be called directly.
     */
    _run: function(additional_params) {
        // Create payload.
        var payload = _.extend({
                agent_id: this.id,
                inputs: this.get_inputs_dict()
            }, additional_params);

        // Because job may require indexing datasets, use server-side
        // deferred to ensure that job is run. Also use deferred that
        // resolves to outputs from agent.
        var run_deferred = $.Deferred(),
            ss_deferred = new util.ServerStateDeferred({
            ajax_settings: {
                url: this.urlRoot,
                data: JSON.stringify(payload),
                dataType: "json",
                contentType: 'application/json',
                type: "POST"
            },
            interval: 2000,
            success_fn: function(response) {
                return response !== "pending";
            }
        });

        // Run job and resolve run_deferred to agent outputs.
        $.when(ss_deferred.go()).then(function(result) {
            run_deferred.resolve(new data.DatasetCollection(result));
        });
        return run_deferred;
    }
});
_.extend(Agent.prototype, VisibilityMixin);

/**
 * Agent view.
 */
var AgentView = Backbone.View.extend({

});

/**
 * Wrap collection of agents for fast access/manipulation.
 */
var AgentCollection = Backbone.Collection.extend({
    model: Agent
});

/**
 * Label or section header in agent panel.
 */
var AgentSectionLabel = Backbone.Model.extend(VisibilityMixin);

/**
 * Section of agent panel with elements (labels and agents).
 */
var AgentSection = Backbone.Model.extend({
    defaults: {
        elems: [],
        open: false
    },

    clear_search_results: function() {
        _.each(this.attributes.elems, function(elt) {
            elt.show();
        });

        this.show();
        this.set("open", false);
    },

    apply_search_results: function(results) {
        var all_hidden = true,
            cur_label;
        _.each(this.attributes.elems, function(elt) {
            if (elt instanceof AgentSectionLabel) {
                cur_label = elt;
                cur_label.hide();
            }
            else if (elt instanceof Agent) {
                if (elt.apply_search_results(results)) {
                    all_hidden = false;
                    if (cur_label) {
                        cur_label.show();
                    }
                }
            }
        });

        if (all_hidden) {
            this.hide();
        }
        else {
            this.show();
            this.set("open", true);
        }
    }
});
_.extend(AgentSection.prototype, VisibilityMixin);

/**
 * Agent search that updates results when query is changed. Result value of null
 * indicates that query was not run; if not null, results are from search using
 * query.
 */
var AgentSearch = Backbone.Model.extend({
    defaults: {
        search_hint_string: "search agents",
        min_chars_for_search: 3,
        clear_btn_url: "",
        search_url: "",
        visible: true,
        query: "",
        results: null,
        // ESC (27) will clear the input field and agent search filters
        clear_key: 27
    },

    urlRoot: Galaxy.root + 'api/agents',

    initialize: function() {
        this.on("change:query", this.do_search);
    },

    /**
     * Do the search and update the results.
     */
    do_search: function() {
        var query = this.attributes.query;

        // If query is too short, do not search.
        if (query.length < this.attributes.min_chars_for_search) {
            this.set("results", null);
            return;
        }

        // Do search via AJAX.
        var q = query;
        // Stop previous ajax-request
        if (this.timer) {
            clearTimeout(this.timer);
        }
        // Start a new ajax-request in X ms
        $("#search-clear-btn").hide();
        $("#search-spinner").show();
        var self = this;
        this.timer = setTimeout(function () {
            // log the search to analytics if present
            if ( typeof ga !== 'undefined' ) {
                ga( 'send', 'pageview', Galaxy.root + '?q=' + q );
            }
            $.get( self.urlRoot, { q: q }, function (data) {
                self.set("results", data);
                $("#search-spinner").hide();
                $("#search-clear-btn").show();
            }, "json" );
        }, 400 );
    },

    clear_search: function() {
        this.set("query", "");
        this.set("results", null);
    }

});
_.extend(AgentSearch.prototype, VisibilityMixin);

/**
 * Agent Panel.
 */
var AgentPanel = Backbone.Model.extend({

    initialize: function(options) {
        this.attributes.agent_search = options.agent_search;
        this.attributes.agent_search.on("change:results", this.apply_search_results, this);
        this.attributes.agents = options.agents;
        this.attributes.layout = new Backbone.Collection( this.parse(options.layout) );
    },

    /**
     * Parse agent panel dictionary and return collection of agent panel elements.
     */
    parse: function(response) {
        // Recursive function to parse agent panel elements.
        var self = this,
            // Helper to recursively parse agent panel.
            parse_elt = function(elt_dict) {
                var type = elt_dict.model_class;
                // There are many types of agents; for now, anything that ends in 'Agent'
                // is treated as a generic agent.
                if ( type.indexOf('Agent') === type.length - 4 ) {
                    return self.attributes.agents.get(elt_dict.id);
                }
                else if (type === 'AgentSection') {
                    // Parse elements.
                    var elems = _.map(elt_dict.elems, parse_elt);
                    elt_dict.elems = elems;
                    return new AgentSection(elt_dict);
                }
                else if (type === 'AgentSectionLabel') {
                    return new AgentSectionLabel(elt_dict);
                }
            };

        return _.map(response, parse_elt);
    },

    clear_search_results: function() {
        this.get('layout').each(function(panel_elt) {
            if (panel_elt instanceof AgentSection) {
                panel_elt.clear_search_results();
            }
            else {
                // Label or agent, so just show.
                panel_elt.show();
            }
        });
    },

    apply_search_results: function() {
        var results = this.get('agent_search').get('results');
        if (results === null) {
            this.clear_search_results();
            return;
        }

        var cur_label = null;
        this.get('layout').each(function(panel_elt) {
            if (panel_elt instanceof AgentSectionLabel) {
                cur_label = panel_elt;
                cur_label.hide();
            }
            else if (panel_elt instanceof Agent) {
                if (panel_elt.apply_search_results(results)) {
                    if (cur_label) {
                        cur_label.show();
                    }
                }
            }
            else {
                // Starting new section, so clear current label.
                cur_label = null;
                panel_elt.apply_search_results(results);
            }
        });
    }
});

/**
 * View classes for Galaxy agents and agent panel.
 *
 * Views use the templates defined below for rendering. Views update as needed
 * based on (a) model/collection events and (b) user interactions; in this sense,
 * they are controllers are well and the HTML is the real view in the MVC architecture.
 */

/**
 * Base view that handles visibility based on model's hidden attribute.
 */
var BaseView = Backbone.View.extend({
    initialize: function() {
        this.model.on("change:hidden", this.update_visible, this);
        this.update_visible();
    },
    update_visible: function() {
        ( this.model.attributes.hidden ? this.$el.hide() : this.$el.show() );
    }
});

/**
 * Link to a agent.
 */
var AgentLinkView = BaseView.extend({
    tagName: 'div',

    render: function() {
        // create element
        var $link = $('<div/>');
        $link.append(templates.agent_link(this.model.toJSON()));

        // open upload dialog for upload agent
        if (this.model.id === 'upload1') {
            $link.find('a').on('click', function(e) {
                e.preventDefault();
                Galaxy.upload.show();
            });
        }
        else if ( this.model.get( 'model_class' ) === 'Agent' ) { // regular agents
            var self = this;
            $link.find('a').on('click', function(e) {
                e.preventDefault();
                var form = new AgentForm.View( { id : self.model.id, version : self.model.get('version') } );
                form.deferred.execute(function() {
                    Galaxy.app.display( form );
                });
            });
        }

        // add element
        this.$el.append($link);
        return this;
    }
});

/**
 * Panel label/section header.
 */
var AgentSectionLabelView = BaseView.extend({
    tagName: 'div',
    className: 'agentPanelLabel',

    render: function() {
        this.$el.append( $("<span/>").text(this.model.attributes.text) );
        return this;
    }
});

/**
 * Panel section.
 */
var AgentSectionView = BaseView.extend({
    tagName: 'div',
    className: 'agentSectionWrapper',

    initialize: function() {
        BaseView.prototype.initialize.call(this);
        this.model.on("change:open", this.update_open, this);
    },

    render: function() {
        // Build using template.
        this.$el.append( templates.panel_section(this.model.toJSON()) );

        // Add agents to section.
        var section_body = this.$el.find(".agentSectionBody");
        _.each(this.model.attributes.elems, function(elt) {
            if (elt instanceof Agent) {
                var agent_view = new AgentLinkView({model: elt, className: "agentTitle"});
                agent_view.render();
                section_body.append(agent_view.$el);
            }
            else if (elt instanceof AgentSectionLabel) {
                var label_view = new AgentSectionLabelView({model: elt});
                label_view.render();
                section_body.append(label_view.$el);
            }
            else {
                // TODO: handle nested section bodies?
            }
        });
        return this;
    },

    events: {
        'click .agentSectionTitle > a': 'toggle'
    },

    /**
     * Toggle visibility of agent section.
     */
    toggle: function() {
        this.model.set("open", !this.model.attributes.open);
    },

    /**
     * Update whether section is open or close.
     */
    update_open: function() {
        (this.model.attributes.open ?
            this.$el.children(".agentSectionBody").slideDown("fast") :
            this.$el.children(".agentSectionBody").slideUp("fast")
        );
    }
});

var AgentSearchView = Backbone.View.extend({
    tagName: 'div',
    id: 'agent-search',
    className: 'bar',

    events: {
        'click': 'focus_and_select',
        'keyup :input': 'query_changed',
        'click #search-clear-btn': 'clear'
    },

    render: function() {
        this.$el.append( templates.agent_search(this.model.toJSON()) );
        if (!this.model.is_visible()) {
            this.$el.hide();
        }
        this.$el.find('[title]').agenttip();
        return this;
    },

    focus_and_select: function() {
        this.$el.find(":input").focus().select();
    },

    clear: function() {
        this.model.clear_search();
        this.$el.find(":input").val('');
        this.focus_and_select();
        return false;
    },

    query_changed: function( evData ) {
        // check for the 'clear key' (ESC) first
        if( ( this.model.attributes.clear_key ) &&
            ( this.model.attributes.clear_key === evData.which ) ){
            this.clear();
            return false;
        }
        this.model.set("query", this.$el.find(":input").val());
    }
});

/**
 * Agent panel view. Events triggered include:
 * agent_link_click(click event, agent_model)
 */
var AgentPanelView = Backbone.View.extend({
    tagName: 'div',
    className: 'agentMenu',

    /**
     * Set up view.
     */
    initialize: function() {
        this.model.get('agent_search').on("change:results", this.handle_search_results, this);
    },

    render: function() {
        var self = this;

        // Render search.
        var search_view = new AgentSearchView( { model: this.model.get('agent_search') } );
        search_view.render();
        self.$el.append(search_view.$el);

        // Render panel.
        this.model.get('layout').each(function(panel_elt) {
            if (panel_elt instanceof AgentSection) {
                var section_title_view = new AgentSectionView({model: panel_elt});
                section_title_view.render();
                self.$el.append(section_title_view.$el);
            }
            else if (panel_elt instanceof Agent) {
                var agent_view = new AgentLinkView({model: panel_elt, className: "agentTitleNoSection"});
                agent_view.render();
                self.$el.append(agent_view.$el);
            }
            else if (panel_elt instanceof AgentSectionLabel) {
                var label_view = new AgentSectionLabelView({model: panel_elt});
                label_view.render();
                self.$el.append(label_view.$el);
            }
        });

        // Setup agent link click eventing.
        self.$el.find("a.agent-link").click(function(e) {
            // Agent id is always the first class.
            var
                agent_id = $(this).attr('class').split(/\s+/)[0],
                agent = self.model.get('agents').get(agent_id);

            self.trigger("agent_link_click", e, agent);
        });

        return this;
    },

    handle_search_results: function() {
        var results = this.model.get('agent_search').get('results');
        if (results && results.length === 0) {
            $("#search-no-results").show();
        }
        else {
            $("#search-no-results").hide();
        }
    }
});

/**
 * View for working with a agent: setting parameters and inputs and executing the agent.
 */
var AgentFormView = Backbone.View.extend({
    className: 'agentForm',

    render: function() {
        this.$el.children().remove();
        this.$el.append( templates.agent_form(this.model.toJSON()) );
    }
});

/**
 * Integrated agent menu + agent execution.
 */
var IntegratedAgentMenuAndView = Backbone.View.extend({
    className: 'agentMenuAndView',

    initialize: function() {
        this.agent_panel_view = new AgentPanelView({collection: this.collection});
        this.agent_form_view = new AgentFormView();
    },

    render: function() {
        // Render and append agent panel.
        this.agent_panel_view.render();
        this.agent_panel_view.$el.css("float", "left");
        this.$el.append(this.agent_panel_view.$el);

        // Append agent form view.
        this.agent_form_view.$el.hide();
        this.$el.append(this.agent_form_view.$el);

        // On agent link click, show agent.
        var self = this;
        this.agent_panel_view.on("agent_link_click", function(e, agent) {
            // Prevents click from activating link:
            e.preventDefault();
            // Show agent that was clicked on:
            self.show_agent(agent);
        });
    },

    /**
     * Fetch and display agent.
     */
    show_agent: function(agent) {
        var self = this;
        agent.fetch().done( function() {
            self.agent_form_view.model = agent;
            self.agent_form_view.render();
            self.agent_form_view.$el.show();
            $('#left').width("650px");
        });
    }
});

// TODO: move into relevant views
var templates = {
    // the search bar at the top of the agent panel
    agent_search : _.template([
        '<input id="agent-search-query" class="search-query parent-width" name="query" ',
                'placeholder="<%- search_hint_string %>" autocomplete="off" type="text" />',
        '<a id="search-clear-btn" title="clear search (esc)"> </a>',
        //TODO: replace with icon
        '<span id="search-spinner" class="search-spinner fa fa-spinner fa-spin"></span>',
    ].join('')),

    // the category level container in the agent panel (e.g. 'Get Data', 'Text Manipulation')
    panel_section : _.template([
        '<div class="agentSectionTitle" id="title_<%- id %>">',
            '<a href="javascript:void(0)"><span><%- name %></span></a>',
        '</div>',
        '<div id="<%- id %>" class="agentSectionBody" style="display: none;">',
            '<div class="agentSectionBg"></div>',
        '<div>'
    ].join('')),

    // a single agent's link in the agent panel; will load the agent form in the center panel
    agent_link : _.template([
        '<span class="labels">',
            '<% _.each( labels, function( label ){ %>',
            '<span class="label label-default label-<%- label %>">',
                '<%- label %>',
            '</span>',
            '<% }); %>',
        '</span>',
        '<a class="<%- id %> agent-link" href="<%= link %>" target="<%- target %>" minsizehint="<%- min_width %>">',
            '<%- name %>',
        '</a>',
        ' <%- description %>'
    ].join('')),

    // the agent form for entering agent parameters, viewing help and executing the agent
    // loaded when a agent link is clicked in the agent panel
    agent_form : _.template([
        '<div class="agentFormTitle"><%- agent.name %> (version <%- agent.version %>)</div>',
        '<div class="agentFormBody">',
            '<% _.each( agent.inputs, function( input ){ %>',
            '<div class="form-row">',
                '<label for="<%- input.name %>"><%- input.label %>:</label>',
                '<div class="form-row-input">',
                    '<%= input.html %>',
                '</div>',
                '<div class="agentParamHelp" style="clear: both;">',
                    '<%- input.help %>',
                '</div>',
                '<div style="clear: both;"></div>',
            '</div>',
            '<% }); %>',
        '</div>',
        '<div class="form-row form-actions">',
            '<input type="submit" class="btn btn-primary" name="runagent_btn" value="Execute" />',
        '</div>',
        '<div class="agentHelp">',
            '<div class="agentHelpBody"><% agent.help %></div>',
        '</div>',
    // TODO: we need scoping here because 'help' is the dom for the help menu in the masthead
    // which implies a leaky variable that I can't find
    ].join(''), { variable: 'agent' }),
};


// Exports
return {
    AgentParameter: AgentParameter,
    IntegerAgentParameter: IntegerAgentParameter,
    SelectAgentParameter: SelectAgentParameter,
    Agent: Agent,
    AgentCollection: AgentCollection,
    AgentSearch: AgentSearch,
    AgentPanel: AgentPanel,
    AgentPanelView: AgentPanelView,
    AgentFormView: AgentFormView
};

});
