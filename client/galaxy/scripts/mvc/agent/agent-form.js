/**
    This is the regular agent form.
*/
define(['utils/utils', 'mvc/ui/ui-misc', 'mvc/agent/agent-form-base', 'mvc/agent/agent-template'],
    function( Utils, Ui, AgentFormBase, AgentTemplate ) {
    var View = AgentFormBase.extend({
        initialize: function( options ) {
            var self = this;
            AgentFormBase.prototype.initialize.call( this, Utils.merge({
                customize       : function( options ) {
                    // build execute button
                    options.buttons = {
                        execute : execute_btn = new Ui.Button({
                            icon     : 'fa-check',
                            agenttip  : 'Execute: ' + options.name + ' (' + options.version + ')',
                            title    : 'Execute',
                            cls      : 'btn btn-primary',
                            floating : 'clear',
                            onclick  : function() {
                                execute_btn.wait();
                                self.portlet.disable();
                                self.submit( options, function() {
                                    execute_btn.unwait();
                                    self.portlet.enable();
                                } );
                            }
                        })
                    };
                    // remap feature
                    if ( options.job_id && options.job_remap ) {
                        options.inputs[ 'rerun_remap_job_id' ] = {
                            label       : 'Resume dependencies from this job',
                            name        : 'rerun_remap_job_id',
                            type        : 'select',
                            display     : 'radio',
                            ignore      : '__ignore__',
                            value       : '__ignore__',
                            options     : [ [ 'Yes', options.job_id ], [ 'No', '__ignore__' ] ],
                            help        : 'The previous run of this agent failed and other agents were waiting for it to finish successfully. Use this option to resume those agents using the new output(s) of this agent run.'
                        }
                    }
                }
            }, options ) );
        },

        /** Submit a regular job.
         * @param{dict}     options   - Specifies agent id and version
         * @param{function} callback  - Called when request has completed
         */
        submit: function( options, callback ) {
            var self = this;
            var job_def = {
                agent_id         : options.id,
                agent_version    : options.version,
                inputs          : this.data.create()
            }
            this.trigger( 'reset' );
            if ( !self.validate( job_def ) ) {
                Galaxy.emit.debug( 'agent-form::submit()', 'Submission canceled. Validation failed.' );
                callback && callback();
                return;
            }
            Galaxy.emit.debug( 'agent-form::submit()', 'Validation complete.', job_def );
            Utils.request({
                type    : 'POST',
                url     : Galaxy.root + 'api/agents',
                data    : job_def,
                success : function( response ) {
                    callback && callback();
                    self.$el.empty().append( AgentTemplate.success( response ) );
                    parent.Galaxy && parent.Galaxy.currHistoryPanel && parent.Galaxy.currHistoryPanel.refreshContents();
                },
                error   : function( response ) {
                    callback && callback();
                    Galaxy.emit.debug( 'agent-form::submit', 'Submission failed.', response );
                    if ( response && response.err_data ) {
                        var error_messages = self.data.matchResponse( response.err_data );
                        for (var input_id in error_messages) {
                            self.highlight( input_id, error_messages[ input_id ]);
                            break;
                        }
                    } else {
                        self.modal.show({
                            title   : 'Job submission failed',
                            body    : ( response && response.err_msg ) || AgentTemplate.error( job_def ),
                            buttons : {
                                'Close' : function() {
                                    self.modal.hide();
                                }
                            }
                        });
                    }
                }
            });
        },

        /** Validate job dictionary.
         * @param{dict}     job_def   - Job execution dictionary
        */
        validate: function( job_def ) {
            var job_inputs  = job_def.inputs;
            var batch_n     = -1;
            var batch_src   = null;
            for ( var job_input_id in job_inputs ) {
                var input_value = job_inputs[ job_input_id ];
                var input_id    = this.data.match( job_input_id );
                var input_field = this.field_list[ input_id ];
                var input_def   = this.input_list[ input_id ];
                if ( !input_id || !input_def || !input_field ) {
                    Galaxy.emit.debug('agent-form::validate()', 'Retrieving input objects failed.');
                    continue;
                }
                if ( !input_def.optional && input_value == null ) {
                    this.highlight( input_id );
                    return false;
                }
                if ( input_value && input_value.batch ) {
                    var n = input_value.values.length;
                    var src = n > 0 && input_value.values[ 0 ] && input_value.values[ 0 ].src;
                    if ( src ) {
                        if ( batch_src === null ) {
                            batch_src = src;
                        } else if ( batch_src !== src ) {
                            this.highlight( input_id, 'Please select either dataset or dataset list fields for all batch mode fields.' );
                            return false;
                        }
                    }
                    if ( batch_n === -1 ) {
                        batch_n = n;
                    } else if ( batch_n !== n ) {
                        this.highlight( input_id, 'Please make sure that you select the same number of inputs for all batch mode fields. This field contains <b>' + n + '</b> selection(s) while a previous field contains <b>' + batch_n + '</b>.' );
                        return false;
                    }
                }
            }
            return true;
        }
    });

    return {
        View: View
    };
});