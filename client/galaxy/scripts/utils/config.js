define(['libs/underscore', 'viz/trackster/util', 'utils/config'], function(_, util_mod, config_mod) {

/**
 * A configuration setting. Currently key is used as id.
 */
var ConfigSetting = Backbone.Model.extend({

    initialize: function(options) {
        // Use key as id for now.
        var key = this.get('key');
        this.set('id', key);

        // Set defaults based on key.
        var defaults = _.find(ConfigSetting.known_settings_defaults, function(s) { return s.key === key; });
        if (defaults) {
            this.set(_.extend({}, defaults, options));
        }

        if (this.get('value') === undefined && this.get('default_value') !== undefined) {
            // Use default to set value (if present).
            this.set_value(this.get('default_value'));

            // If no default value for color config, set random color.
            if (!this.get('value') && this.get('type') === 'color') {
                // For color setting, set random color.
                this.set('value', util_mod.get_random_color());
            }
        }
    },

    /**
     * Cast and set value. This should be instead of
     *  setting.set('value', new_value)
     */
    set_value: function(value, options) {
        var type = this.get('type');

        if (type === 'float') {
            value = parseFloat(value);
        }
        else if (type === 'int') {
            value = parseInt(value, 10);
        }
        // TODO: handle casting from string to bool?

        this.set({value: value}, options);
    }
}, {
    // This is a master list of default settings for known settings.
    known_settings_defaults: [
        { key: 'name', label: 'Name', type: 'text', default_value: '' },
        { key: 'color', label: 'Color', type: 'color', default_value: null },
        { key: 'min_value', label: 'Min Value', type: 'float', default_value: null },
        { key: 'max_value', label: 'Max Value', type: 'float', default_value: null },
        { key: 'mode', type: 'string', default_value: this.mode, hidden: true },
        { key: 'height', type: 'int', default_value: 32, hidden: true },
        { key: 'pos_color', label: 'Positive Color', type: 'color', default_value: "#FF8C00" },
        { key: 'neg_color', label: 'Negative Color', type: 'color', default_value: "#4169E1" },
        { key: 'block_color', label: 'Block color', type: 'color', default_value: null },
        { key: 'label_color', label: 'Label color', type: 'color', default_value: 'black' },
        { key: 'show_insertions', label: 'Show insertions', type: 'bool', default_value: false },
        { key: 'show_counts', label: 'Show summary counts', type: 'bool', default_value: true },
        { key: 'mode', type: 'string', default_value: this.mode, hidden: true },
        { key: 'reverse_strand_color', label: 'Antisense strand color', type: 'color', default_value: null },
        { key: 'show_differences', label: 'Show differences only', type: 'bool', default_value: true },
        { key: 'mode', type: 'string', default_value: this.mode, hidden: true }
    ]
});

/**
 * Collection of config settings.
 */
var ConfigSettingCollection = Backbone.Collection.extend({
    model: ConfigSetting,

    /**
     * Save settings as a dictionary of key-value pairs.
     * This function is needed for backwards compatibility.
     */
    to_key_value_dict: function() {
        var rval = {};
        this.each(function(setting) {
            rval[setting.get('key')] = setting.get('value');
        });

        return rval;
    },

    /**
     * Returns value for a given key. Returns undefined if there is no setting with the specified key.
     */
    get_value: function(key) {
        var s = this.get(key);
        if (s) {
            return s.get('value');
        }

        return undefined;
    },

    /**
     * Set value for a setting.
     */
    set_value: function(key, value, options) {
        var s = this.get(key);
        if (s) {
            return s.set_value(value, options);
        }

        return undefined;
     },

     /**
      * Set default value for a setting.
      */
     set_default_value: function(key, default_value) {
        var s = this.get(key);
        if (s) {
            return s.set('default_value', default_value);
        }

        return undefined;
     }
},
{
    /**
     * Utility function that creates a ConfigSettingsCollection from a set of models
     * and a saved_values dictionary.
     */
    from_models_and_saved_values: function(models, saved_values) {
        // If there are saved values, copy models and update with saved values.
        if (saved_values) {
            models = _.map(models, function(m) {
                return _.extend({}, m, { value: saved_values[m.key] });
            });
        }

        return new ConfigSettingCollection(models);
    }
});

/**
 * Viewer for config settings collection.
 */
var ConfigSettingCollectionView = Backbone.View.extend({
    className: 'config-settings-view',

    /**
     * Renders form for editing configuration settings.
     */
    render: function() {
        var container = this.$el;

        this.collection.each(function(param, index) {
            // Hidden params have no representation in the form
            if (param.get('hidden')) { return; }

            // Build row for param.
            var id = 'param_' + index,
                type = param.get('type'),
                value = param.get('value');
            var row = $("<div class='form-row' />").appendTo(container);
            row.append($('<label />').attr("for", id ).text(param.get('label') + ":" ));
            // Draw parameter as checkbox
            if ( type === 'bool' ) {
                row.append( $('<input type="checkbox" />').attr("id", id ).attr("name", id ).attr( 'checked', value ) );
            }
            // Draw parameter as textbox
            else if ( type === 'text' ) {
                row.append( $('<input type="text"/>').attr("id", id ).val(value).click( function() { $(this).select(); }));
            }
            // Draw parameter as select area
            else if ( type === 'select' ) {
                var select = $('<select />').attr("id", id);
                _.each(param.get('options'), function(option) {
                    $("<option/>").text( option.label ).attr( "value", option.value ).appendTo( select );
                });
                select.val( value );
                row.append( select );

            }
            // Draw parameter as color picker
            else if ( type === 'color' ) {
                var
                    container_div = $("<div/>").appendTo(row),
                    input = $('<input />').attr("id", id ).attr("name", id ).val( value ).css("float", "left")
                        .appendTo(container_div).click(function(e) {
                        // Hide other pickers.
                        $(".agenttip").removeClass( "in" );

                        // Show input's color picker.
                        var tip = $(this).siblings(".agenttip").addClass( "in" );
                        tip.css( {
                            // left: $(this).position().left + ( $(input).width() / 2 ) - 60,
                            // top: $(this).position().top + $(this.height)
                            left: $(this).position().left + $(this).width() + 5,
                            top: $(this).position().top - ( $(tip).height() / 2 ) + ( $(this).height() / 2 )
                            } ).show();

                        // Click management:

                        // Keep showing tip if clicking in tip.
                        tip.click(function(e) {
                            e.stopPropagation();
                        });

                        // Hide tip if clicking outside of tip.
                        $(document).bind( "click.color-picker", function() {
                            tip.hide();
                            $(document).unbind( "click.color-picker" );
                        });

                        // No propagation to avoid triggering document click (and tip hiding) above.
                        e.stopPropagation();
                    }),
                    // Icon for setting a new random color; behavior set below.
                    new_color_icon = $("<a href='javascript:void(0)'/>").addClass("icon-button arrow-circle").appendTo(container_div)
                                     .attr("title", "Set new random color").agenttip(),
                    // Color picker in agent tip style.
                    tip = $( "<div class='agenttip right' style='position: absolute;' />" ).appendTo(container_div).hide(),
                    // Inner div for padding purposes
                    tip_inner = $("<div class='agenttip-inner' style='text-align: inherit'></div>").appendTo(tip),
                    tip_arrow = $("<div class='agenttip-arrow'></div>").appendTo(tip),
                    farb_obj = $.farbtastic(tip_inner, { width: 100, height: 100, callback: input, color: value });

                // Clear floating.
                container_div.append( $("<div/>").css("clear", "both"));

                // Use function to fix farb_obj value.
                (function(fixed_farb_obj) {
                    new_color_icon.click(function() {
                        fixed_farb_obj.setColor(util_mod.get_random_color());
                    });
                })(farb_obj);

            }
            else {
                row.append( $('<input />').attr("id", id ).attr("name", id ).val( value ) );
            }
            // Help text
            if ( param.help ) {
                row.append( $("<div class='help'/>").text( param.help ) );
            }
        });

        return this;
    },

    /**
     * Render view in modal.
     */
    render_in_modal: function(title) {
        // Set up handlers for cancel, ok button and for handling esc key.
        var self = this,
            cancel_fn = function() { Galaxy.modal.hide(); $(window).unbind("keypress.check_enter_esc"); },
            ok_fn = function() {
                Galaxy.modal.hide();
                $(window).unbind("keypress.check_enter_esc");
                self.update_from_form();
            },
            check_enter_esc = function(e) {
                if ((e.keyCode || e.which) === 27) { // Escape key
                    cancel_fn();
                } else if ((e.keyCode || e.which) === 13) { // Enter key
                    ok_fn();
                }
            };

        // Set keypress handler.
        $(window).bind("keypress.check_enter_esc", check_enter_esc);

        // Show modal.
        if (this.$el.children().length === 0) {
            this.render();
        }
        Galaxy.modal.show({
            title: title || "Configure",
            body: this.$el,
            buttons: {
                "Cancel": cancel_fn,
                "OK": ok_fn
            }
        });
    },

    /**
     * Update settings with new values entered via form.
     */
    update_from_form: function() {
        var self = this;
        this.collection.each(function(setting, index) {
            if ( !setting.get('hidden') ) {
                // Set value from view.
                var id = 'param_' + index;
                var value = self.$el.find( '#' + id ).val();
                if ( setting.get('type') === 'bool' ) {
                    value = self.$el.find( '#' + id ).is( ':checked' );
                }
                setting.set_value(value);
            }
        });
    }

});

return {
    ConfigSetting: ConfigSetting,
    ConfigSettingCollection: ConfigSettingCollection,
    ConfigSettingCollectionView: ConfigSettingCollectionView
};

});