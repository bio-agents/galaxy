define(["mvc/workflow/workflow-globals"],function(a){var b=Backbone.View.extend({className:"form-row dataRow input-data-row",initialize:function(a){this.input=a.input,this.nodeView=a.nodeView,this.terminalElement=a.terminalElement,this.$el.attr("name",this.input.name).html(this.input.label),a.skipResize||(this.$el.css({position:"absolute",left:-1e3,top:-1e3,display:"none"}),$("body").append(this.el),this.nodeView.updateMaxWidth(this.$el.outerWidth()),this.$el.css({position:"",left:"",top:"",display:""}),this.$el.remove())}}),c=Backbone.View.extend({className:"form-row dataRow",initialize:function(a){this.output=a.output,this.terminalElement=a.terminalElement,this.nodeView=a.nodeView;var b=this.output,c=b.name,e=this.nodeView.node,f=b.extensions.indexOf("input")>=0||b.extensions.indexOf("input_collection")>=0;if(f||(c=c+" ("+b.extensions.join(", ")+")"),this.$el.html(c),this.calloutView=null,["agent","subworkflow"].indexOf(e.type)>=0){var g=new d({label:c,output:b,node:e});this.calloutView=g,this.$el.append(g.el),this.$el.hover(function(){g.hoverImage()},function(){g.resetImage()})}this.$el.css({position:"absolute",left:-1e3,top:-1e3,display:"none"}),$("body").append(this.el),this.nodeView.updateMaxWidth(this.$el.outerWidth()+17),this.$el.css({position:"",left:"",top:"",display:""}).detach()},redrawWorkflowOutput:function(){this.calloutView&&this.calloutView.resetImage()}}),d=Backbone.View.extend({tagName:"div",initialize:function(b){this.label=b.label,this.node=b.node,this.output=b.output;var c=this,d=this.node;this.$el.attr("class","callout "+this.label).css({display:"none"}).append($("<div class='buttons'></div>").append($("<img/>").attr("src",Galaxy.root+"static/images/fugue/asterisk-small-outline.png").click(function(){var b=c.output.name;d.isWorkflowOutput(b)?(d.removeWorkflowOutput(b),c.$("img").attr("src",Galaxy.root+"static/images/fugue/asterisk-small-outline.png")):(d.addWorkflowOutput(b),c.$("img").attr("src",Galaxy.root+"static/images/fugue/asterisk-small.png")),a.workflow.has_changes=!0,a.canvas_manager.draw_overview()}))).agenttip({delay:500,title:"Mark dataset as a workflow output. All unmarked datasets will be hidden."}),this.$el.css({top:"50%",margin:"-8px 0px 0px 0px",right:8}),this.$el.show(),this.resetImage()},resetImage:function(){this.node.isWorkflowOutput(this.output.name)?this.$("img").attr("src",Galaxy.root+"static/images/fugue/asterisk-small.png"):this.$("img").attr("src",Galaxy.root+"static/images/fugue/asterisk-small-outline.png")},hoverImage:function(){this.$("img").attr("src",Galaxy.root+"static/images/fugue/asterisk-small-yellow.png")}});return{DataInputView:b,DataOutputView:c}});
//# sourceMappingURL=../../../maps/mvc/workflow/workflow-view-data.js.map