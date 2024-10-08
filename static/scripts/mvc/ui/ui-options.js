define(["utils/utils","mvc/ui/ui-buttons"],function(a,b){var c=Backbone.View.extend({initialize:function(c){var d=this;this.options=a.merge(c,{visible:!0,data:[],id:a.uid(),error_text:"No options available.",wait_text:"Please wait...",multiple:!1}),this.setElement('<div class="ui-options"/>'),this.$message=$("<div/>"),this.$options=$(this._template(c)),this.$menu=$('<div class="ui-options-menu"/>'),this.$el.append(this.$message),this.$el.append(this.$menu),this.$el.append(this.$options),this.options.multiple&&(this.all_button=new b.ButtonCheck({onclick:function(){d.$("input").prop("checked",0!==d.all_button.value()),d.trigger("change")}}),this.$menu.append(this.all_button.$el)),this.options.visible||this.$el.hide(),this.update(this.options.data),void 0!==this.options.value&&this.value(this.options.value),this.on("change",function(){this.options.onchange&&this.options.onchange(this.value())})},update:function(a){var b=this._getValue();if(this.$options.empty(),this._templateOptions)this.$options.append(this._templateOptions(a));else for(var c in a){var d=$(this._templateOption(a[c]));d.addClass("ui-option"),d.agenttip({title:a[c].agenttip,placement:"bottom"}),this.$options.append(d)}var e=this;this.$("input").on("change",function(){e.value(e._getValue()),e.trigger("change")}),this.value(b),this.unwait()},value:function(a){if(void 0!==a&&(this.$("input").prop("checked",!1),null!==a)){a instanceof Array||(a=[a]);for(var b in a)this.$('input[value="'+a[b]+'"]').first().prop("checked",!0)}var c=this._getValue();if(this.all_button){var d=c;d=d instanceof Array?d.length:0,this.all_button.value(d,this._size())}return c},exists:function(a){if(void 0!==a){a instanceof Array||(a=[a]);for(var b in a)if(this.$('input[value="'+a[b]+'"]').length>0)return!0}return!1},first:function(){var a=this.$("input").first();return a.length>0?a.val():null},wait:function(){0==this._size()&&(this._messageShow(this.options.wait_text,"info"),this.$options.hide(),this.$menu.hide())},unwait:function(){var a=this._size();0==a?(this._messageShow(this.options.error_text,"danger"),this.$options.hide(),this.$menu.hide()):(this._messageHide(),this.$options.css("display","inline-block"),this.$menu.show())},_getValue:function(){var b=[];return this.$(":checked").each(function(){b.push($(this).val())}),a.validate(b)?this.options.multiple?b:b[0]:null},_size:function(){return this.$(".ui-option").length},_messageShow:function(a,b){this.$message.show(),this.$message.removeClass(),this.$message.addClass("ui-message alert alert-"+b),this.$message.html(a)},_messageHide:function(){this.$message.hide()},_template:function(){return'<div class="ui-options-list"/>'}}),d=c.extend({_templateOption:function(b){var c=a.uid();return'<div class="ui-option"><input id="'+c+'" type="'+this.options.type+'" name="'+this.options.id+'" value="'+b.value+'"/><label class="ui-options-label" for="'+c+'">'+b.label+"</label></div>"}}),e={};e.View=d.extend({initialize:function(a){a.type="radio",d.prototype.initialize.call(this,a)}});var f={};f.View=d.extend({initialize:function(a){a.multiple=!0,a.type="checkbox",d.prototype.initialize.call(this,a)}});var g={};return g.View=c.extend({initialize:function(a){c.prototype.initialize.call(this,a)},value:function(a){return void 0!==a&&(this.$("input").prop("checked",!1),this.$("label").removeClass("active"),this.$('[value="'+a+'"]').prop("checked",!0).closest("label").addClass("active")),this._getValue()},_templateOption:function(a){var b="fa "+a.icon;a.label||(b+=" no-padding");var c='<label class="btn btn-default">';return a.icon&&(c+='<i class="'+b+'"/>'),c+='<input type="radio" name="'+this.options.id+'" value="'+a.value+'"/>',a.label&&(c+=a.label),c+="</label>"},_template:function(){return'<div class="btn-group ui-radiobutton" data-toggle="buttons"/>'}}),{Base:c,BaseIcons:d,Radio:e,RadioButton:g,Checkbox:f}});
//# sourceMappingURL=../../../maps/mvc/ui/ui-options.js.map