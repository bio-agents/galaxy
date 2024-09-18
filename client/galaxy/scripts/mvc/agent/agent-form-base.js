/**
    This is the base class of the agent form plugin. This class is e.g. inherited by the regular and the workflow agent form.
*/
define(['utils/utils', 'utils/deferred', 'mvc/ui/ui-misc', 'mvc/form/form-view',
        'mvc/agent/agent-template', 'mvc/citation/citation-model', 'mvc/citation/citation-view'],
    function(Utils, Deferred, Ui, FormBase, AgentTemplate, CitationModel, CitationView) {
    return FormBase.extend({
        initialize: function(options) {
            var self = this;
            FormBase.prototype.initialize.call(this, options);
            this.deferred = new Deferred();
            if (options.inputs) {
                this._buildForm(options);
                options.needs_update && this.deferred.execute( function( process ) {
                    self._updateModel( process );
                });
            } else {
                this.deferred.execute(function(process) {
                    self._buildModel(process, options, true);
                });
            }
        },

        /** Wait for deferred build processes before removal */
        remove: function() {
            var self = this;
            this.$el.hide();
            this.deferred.execute(function(){
                FormBase.prototype.remove.call(self);
                Galaxy.emit.debug('agent-form-base::remove()', 'Destroy view.');
            });
        },

        /** Build form */
        _buildForm: function(options) {
            var self = this;
            this.options = Utils.merge(options, this.options);
            this.options = Utils.merge({
                icon            : ( (options.icon === undefined) && 'fa-wrench' ) || '',
                title           : '<b>' + options.name + '</b> ' + options.description + ' (Galaxy Version ' + options.version + ')',
                operations      : this._operations(),
                onchange        : function() {
                    self.deferred.reset();
                    self.deferred.execute(function(process) {
                        self._updateModel(process);
                    });
                }
            }, this.options);
            this.options.customize && this.options.customize( this.options );
            this.render();
            if ( !this.options.collapsible ) {
                this.$el.append( $( '<div/>' ).addClass( 'ui-margin-top-large' ).append( this._footer() ) );
            }
        },

        /** Builds a new model through api call and recreates the entire form
        */
        _buildModel: function(process, options, hide_message) {
            var self = this;
            this.options.id = options.id;
            this.options.version = options.version;

            // build request url
            var build_url = '';
            var build_data = {};
            if ( options.job_id ) {
                build_url = Galaxy.root + 'api/jobs/' + options.job_id + '/build_for_rerun';
            } else {
                build_url = Galaxy.root + 'api/agents/' + options.id + '/build';
                if ( Galaxy.params && Galaxy.params.agent_id == options.id ) {
                    build_data = $.extend( {}, Galaxy.params );
                    options.version && ( build_data[ 'agent_version' ] = options.version );
                }
            }

            // get initial model
            Utils.request({
                type    : 'GET',
                url     : build_url,
                data    : build_data,
                success : function(new_model) {
                    self._buildForm(new_model['agent_model'] || new_model);
                    !hide_message && self.message.update({
                        status      : 'success',
                        message     : 'Now you are using \'' + self.options.name + '\' version ' + self.options.version + ', id \'' + self.options.id + '\'.',
                        persistent  : false
                    });
                    Galaxy.emit.debug('agent-form-base::initialize()', 'Initial agent model ready.', new_model);
                    process.resolve();

                },
                error   : function(response) {
                    var error_message = ( response && response.err_msg ) || 'Uncaught error.';
                    if ( self.$el.is(':empty') ) {
                        self.$el.prepend((new Ui.Message({
                            message     : error_message,
                            status      : 'danger',
                            persistent  : true,
                            large       : true
                        })).$el);
                    } else {
                        Galaxy.modal.show({
                            title   : 'Agent request failed',
                            body    : error_message,
                            buttons : {
                                'Close' : function() {
                                    Galaxy.modal.hide();
                                }
                            }
                        });
                    }
                    Galaxy.emit.debug('agent-form::initialize()', 'Initial agent model request failed.', response);
                    process.reject();
                }
            });
        },

        /** Request a new model for an already created agent form and updates the form inputs
        */
        _updateModel: function(process) {
            // link this
            var self = this;
            var model_url = this.options.update_url || Galaxy.root + 'api/agents/' + this.options.id + '/build';
            var current_state = {
                agent_id         : this.options.id,
                agent_version    : this.options.version,
                inputs          : $.extend(true, {}, self.data.create())
            }
            this.wait(true);

            // log agent state
            Galaxy.emit.debug('agent-form-base::_updateModel()', 'Sending current state.', current_state);

            // post job
            Utils.request({
                type    : 'POST',
                url     : model_url,
                data    : current_state,
                success : function(new_model) {
                    self.update(new_model['agent_model'] || new_model);
                    self.options.update && self.options.update(new_model);
                    self.wait(false);
                    Galaxy.emit.debug('agent-form-base::_updateModel()', 'Received new model.', new_model);
                    process.resolve();
                },
                error   : function(response) {
                    Galaxy.emit.debug('agent-form-base::_updateModel()', 'Refresh request failed.', response);
                    process.reject();
                }
            });
        },

        /** Create agent operation menu
        */
        _operations: function() {
            var self = this;
            var options = this.options;

            // button for version selection
            var versions_button = new Ui.ButtonMenu({
                icon    : 'fa-cubes',
                title   : (!options.narrow && 'Versions') || null,
                agenttip : 'Select another agent version'
            });
            if (!options.sustain_version && options.versions && options.versions.length > 1) {
                for (var i in options.versions) {
                    var version = options.versions[i];
                    if (version != options.version) {
                        versions_button.addMenu({
                            title   : 'Switch to ' + version,
                            version : version,
                            icon    : 'fa-cube',
                            onclick : function() {
                                // here we update the agent version (some agents encode the version also in the id)
                                var id = options.id.replace(options.version, this.version);
                                var version = this.version;
                                // queue model request
                                self.deferred.reset();
                                self.deferred.execute(function(process) {
                                    self._buildModel(process, {id: id, version: version})
                                });
                            }
                        });
                    }
                }
            } else {
                versions_button.$el.hide();
            }

            // button for options e.g. search, help
            var menu_button = new Ui.ButtonMenu({
                icon    : 'fa-caret-down',
                title   : (!options.narrow && 'Options') || null,
                agenttip : 'View available options'
            });
            if(options.biostar_url) {
                menu_button.addMenu({
                    icon    : 'fa-question-circle',
                    title   : 'Question?',
                    agenttip : 'Ask a question about this agent (Biostar)',
                    onclick : function() {
                        window.open(options.biostar_url + '/p/new/post/');
                    }
                });
                menu_button.addMenu({
                    icon    : 'fa-search',
                    title   : 'Search',
                    agenttip : 'Search help for this agent (Biostar)',
                    onclick : function() {
                        window.open(options.biostar_url + '/local/search/page/?q=' + options.name);
                    }
                });
            };
            menu_button.addMenu({
                icon    : 'fa-share',
                title   : 'Share',
                agenttip : 'Share this agent',
                onclick : function() {
                    prompt('Copy to clipboard: Ctrl+C, Enter', window.location.origin + Galaxy.root + 'root?agent_id=' + options.id);
                }
            });

            // add admin operations
            if (Galaxy.user && Galaxy.user.get('is_admin')) {
                menu_button.addMenu({
                    icon    : 'fa-download',
                    title   : 'Download',
                    agenttip : 'Download this agent',
                    onclick : function() {
                        window.location.href = Galaxy.root + 'api/agents/' + options.id + '/download';
                    }
                });
            }

            // button for version selection
            if (options.requirements && options.requirements.length > 0) {
                menu_button.addMenu({
                    icon    : 'fa-info-circle',
                    title   : 'Requirements',
                    agenttip : 'Display agent requirements',
                    onclick : function() {
                        if (!this.visible) {
                            this.visible = true;
                            self.message.update({
                                persistent  : true,
                                message     : AgentTemplate.requirements(options),
                                status      : 'info'
                            });
                        } else {
                            this.visible = false;
                            self.message.update({
                                message     : ''
                            });
                        }
                    }
                });
            }

            // add agentshed url
            if (options.sharable_url) {
                menu_button.addMenu({
                    icon    : 'fa-external-link',
                    title   : 'See in Agent Shed',
                    agenttip : 'Access the repository',
                    onclick : function() {
                        window.open(options.sharable_url);
                    }
                });
            }

            return {
                menu        : menu_button,
                versions    : versions_button
            }
        },

        /** Create footer
        */
        _footer: function() {
            var options = this.options;
            var $el = $( '<div/>' ).append( AgentTemplate.help( options ) );
            if ( options.citations ) {
                var $citations = $( '<div/>' );
                var citations = new CitationModel.AgentCitationCollection();
                citations.agent_id = options.id;
                var citation_list_view = new CitationView.CitationListView({ el: $citations, collection: citations });
                citation_list_view.render();
                citations.fetch();
                $el.append( $citations );
            }
            return $el;
        }
    });
});
