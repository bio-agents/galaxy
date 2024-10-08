/**
    This class creates a form section and populates it with input elements. It also handles repeat blocks and conditionals by recursively creating new sub sections.
*/
define(['utils/utils',
        'mvc/ui/ui-table',
        'mvc/ui/ui-misc',
        'mvc/ui/ui-portlet',
        'mvc/form/form-repeat',
        'mvc/form/form-input',
        'mvc/form/form-parameters'],
    function(Utils, Table, Ui, Portlet, Repeat, InputElement, Parameters) {
    var View = Backbone.View.extend({
        initialize: function(app, options) {
            this.app = app;
            this.inputs = options.inputs;

            // fix table style
            options.cls = 'ui-table-plain';

            // add table class for tr tag
            // this assist in transforming the form into a json structure
            options.cls_tr = 'section-row';

            // create/render views
            this.table = new Table.View(options);
            this.parameters = new Parameters(app, options);
            this.setElement(this.table.$el);
            this.render();
        },

        /** Render section view
        */
        render: function() {
            this.table.delAll();
            for (var i in this.inputs) {
                this.add(this.inputs[i]);
            }
        },

        /** Add a new input element
        */
        add: function(input) {
            var self = this;
            var input_def = jQuery.extend(true, {}, input);
            input_def.id = input.id = Utils.uid();

            // add to sequential list of inputs
            this.app.input_list[input_def.id] = input_def;

            // identify field type
            var type = input_def.type;
            switch(type) {
                case 'conditional':
                    this._addConditional(input_def);
                    break;
                case 'repeat':
                    this._addRepeat(input_def);
                    break;
                case 'section':
                    this._addSection(input_def);
                    break;
                default:
                    this._addRow(input_def);
            }
        },

        /** Add a conditional block
        */
        _addConditional: function(input_def) {
            var self = this;
            input_def.test_param.id = input_def.id;
            this.app.options.sustain_conditionals && ( input_def.test_param.disabled = true );
            var field = this._addRow( input_def.test_param );

            // set onchange event for test parameter
            field.options.onchange = function(value) {
                var selectedCase = self.app.data.matchCase(input_def, value);
                for (var i in input_def.cases) {
                    var case_def = input_def.cases[i];
                    var section_id = input_def.id + '-section-' + i;
                    var section_row = self.table.get(section_id);
                    var nonhidden = false;
                    for (var j in case_def.inputs) {
                        if (!case_def.inputs[j].hidden) {
                            nonhidden = true;
                            break;
                        }
                    }
                    if (i == selectedCase && nonhidden) {
                        section_row.fadeIn('fast');
                    } else {
                        section_row.hide();
                    }
                }
                self.app.trigger('change');
            };

            // add conditional sub sections
            for (var i in input_def.cases) {
                var sub_section_id = input_def.id + '-section-' + i;
                var sub_section = new View(this.app, {
                    inputs  : input_def.cases[i].inputs
                });
                sub_section.$el.addClass('ui-table-section');
                this.table.add(sub_section.$el);
                this.table.append(sub_section_id);
            }

            // trigger refresh on conditional input field after all input elements have been created
            field.trigger('change');
        },

        /** Add a repeat block
        */
        _addRepeat: function(input_def) {
            var self = this;
            var block_index = 0;

            // create repeat block element
            var repeat = new Repeat.View({
                title           : input_def.title || 'Repeat',
                title_new       : input_def.title || '',
                min             : input_def.min,
                max             : input_def.max,
                onnew           : function() {
                    create(input_def.inputs);
                    self.app.trigger('change');
                }
            });

            // helper function to create new repeat blocks
            function create (inputs) {
                var sub_section_id = input_def.id + '-section-' + (block_index++);
                var sub_section = new View(self.app, {
                    inputs  : inputs
                });
                repeat.add({
                    id      : sub_section_id,
                    $el     : sub_section.$el,
                    ondel   : function() {
                        repeat.del(sub_section_id);
                        self.app.trigger('change');
                    }
                });
            }

            //
            // add parsed/minimum number of repeat blocks
            //
            var n_min   = input_def.min;
            var n_cache = _.size(input_def.cache);
            for (var i = 0; i < Math.max(n_cache, n_min); i++) {
                var inputs = null;
                if (i < n_cache) {
                    inputs = input_def.cache[i];
                } else {
                    inputs = input_def.inputs;
                }
                create(inputs);
            }

            // hide options
            this.app.options.sustain_repeats && repeat.hideOptions();

            // create input field wrapper
            var input_element = new InputElement(this.app, {
                label   : input_def.title || input_def.name,
                help    : input_def.help,
                field   : repeat
            });
            this.table.add(input_element.$el);
            this.table.append(input_def.id);
        },

        /** Add a customized section
        */
        _addSection: function(input_def) {
            var self = this;

            // create sub section
            var sub_section = new View(self.app, {
                inputs  : input_def.inputs
            });

            // delete button
            var button_visible = new Ui.ButtonIcon({
                icon    : 'fa-eye-slash',
                agenttip : 'Show/hide section',
                cls     : 'ui-button-icon-plain'
            });

            // create portlet for sub section
            var portlet = new Portlet.View({
                title       : input_def.title || input_def.name,
                cls         : 'ui-portlet-section',
                collapsible : true,
                collapsed   : true,
                operations  : {
                    button_visible: button_visible
                }
            });
            portlet.append( sub_section.$el );
            portlet.append( $( '<div/>' ).addClass( 'ui-form-info' ).html( input_def.help ) );
            portlet.setOperation( 'button_visible', function() {
                if( portlet.collapsed ) {
                    portlet.expand();
                } else {
                    portlet.collapse();
                }
            });

            // add expansion event handler
            portlet.on( 'expanded', function() {
                button_visible.setIcon( 'fa-eye' );
            });
            portlet.on( 'collapsed', function() {
                button_visible.setIcon( 'fa-eye-slash' );
            });
            this.app.on( 'expand', function( input_id ) {
                ( portlet.$( '#' + input_id ).length > 0 ) && portlet.expand();
            });

            // show sub section if requested
            input_def.expanded && portlet.expand();

            // create table row
            this.table.add(portlet.$el);
            this.table.append(input_def.id);
        },

        /** Add a single input field element
        */
        _addRow: function(input_def) {
            var id = input_def.id;
            var field = this.parameters.create(input_def);
            this.app.field_list[id] = field;
            var input_element = new InputElement(this.app, {
                name                : input_def.name,
                label               : input_def.label || input_def.name,
                value               : input_def.value,
                default_value       : input_def.default_value,
                text_value          : input_def.text_value || input_def.value,
                collapsible_value   : input_def.collapsible_value,
                collapsible_preview : input_def.collapsible_preview,
                help                : input_def.help,
                argument            : input_def.argument,
                disabled            : input_def.disabled,
                field               : field
            });
            this.app.element_list[id] = input_element;
            this.table.add(input_element.$el);
            this.table.append(id);
            input_def.hidden && this.table.get(id).hide();
            return field;
        }
    });

    return {
        View: View
    };
});