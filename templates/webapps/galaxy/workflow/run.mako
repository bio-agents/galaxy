<%inherit file="/base.mako"/>

## TEMPORARY SWITCH FOR THE NEW TOOL FORM
%if util.string_as_bool(trans.app.config.get('run_workflow_agentform_upgrade',  False)):
    ${h.js("libs/bibtex", "libs/jquery/jquery-ui")}
    ${h.css('jquery-ui/smoothness/jquery-ui')}
    <%
        from galaxy.agents.parameters import params_to_incoming
        from galaxy.jobs.actions.post import ActionBox
        step_models = []
        for i, step in enumerate( steps ):
            step_model = None
            if step.type in [ 'data_input', 'data_collection_input' ]:
                type_filter = []
                for oc in step.output_connections:
                    for ic in oc.input_step.module.get_data_inputs():
                        if 'extensions' in ic and ic[ 'name' ] == oc.input_name:
                            type_filter += ic[ 'extensions' ]
                if not type_filter:
                    type_filter = [ 'data' ]
                d = step.module.get_runtime_inputs( type_filter )
                input = d[ 'input' ].to_dict( trans );
                step_model = {
                    'name'   : input[ 'label' ],
                    'inputs' : [ input ]
                }
            elif step.type == 'agent':
                incoming = {}
                agent = trans.app.agentbox.get_agent( step.agent_id )
                params_to_incoming( incoming, agent.inputs, step.state.inputs, trans.app, to_html=False )
                step_model = agent.to_json( trans, incoming, workflow_mode=True )
                step_model[ 'post_job_actions' ] = [{
                    'short_str'         : ActionBox.get_short_str( pja ),
                    'action_type'       : pja.action_type,
                    'output_name'       : pja.output_name,
                    'action_arguments'  : pja.action_arguments
                } for pja in step.post_job_actions ]
            step_model[ 'step_id' ] = step.id
            step_model[ 'step_type' ] = step.type
            step_model[ 'order_index' ] = step.order_index
            step_model[ 'output_connections' ] = [ {
                'input_step_id'     : oc.input_step_id,
                'output_step_id'    : oc.output_step_id,
                'input_name'        : oc.input_name,
                'output_name'       : oc.output_name
            } for oc in step.output_connections ]
            if step.annotations:
                step_model[ 'annotation' ] = step.annotations[0].annotation
            step_models.append( step_model )
        self.form_config = {
            'id'                : app.security.encode_id( workflow.id ),
            'name'              : workflow.name,
            'history_id'        : history_id,
            'steps'             : step_models
        }
    %>
    <script>
        require(['mvc/agent/agent-form-composite'], function( AgentForm ) {
            $(function() {
                var form = new AgentForm.View(${ h.dumps( self.form_config ) });
            });
        });
    </script>
%else:

<%def name="javascripts()">
    ${parent.javascripts()}
    <script type="text/javascript">

        // jQuery plugin to prevent double submission of forms
        // Ref: http://stackoverflow.com/questions/2830542/prevent-double-submission-of-forms-in-jquery
        jQuery.fn.preventDoubleSubmission = function() {
            $(this).on('submit',function(e){
                var $form = $(this);

                if ($form.data('submitted') === true) {
                    // Previously submitted - don't submit again
                    e.preventDefault();
                } else {
                    // Mark it so that the next submit can be ignored
                    $form.data('submitted', true);
                }
            });
            // Keep chainability
            return this;
        };

        $.fn.outerHTML = function(s) {
            return s ? this.before(s).remove() : jQuery("<p>").append(this.eq(0).clone()).html();
        };
        $( function() {
            function show_agent_body(title){
                title.parent().show().css('border-bottom-width', '1px');
                title.next().show('fast');
                if ('${hide_fixed_params}'.toLowerCase() == 'true') {
                    // show previously hidden parameters
                    title.next().children(".form-row").show();
                }
            }
            function hide_agent_body(title){
                title.parent().css('border-bottom-width', '0px');
                title.next().hide('fast');
            }
            function toggle_agent_body(title) {
                if (title.next().is(':visible')){
                    hide_agent_body(title);
                }else{
                    show_agent_body(title);
                }
            }
            function toggle_multiinput(select) {
                var placeholder;
                if (select.attr('multiple')) {
                    $('.multiinput').removeClass('disabled');
                    if (select.val()) {
                        select.val(select.val()[0]);
                    } else {
                        select.val($('option:last', select).val());
                    }
                    select.closest('.form-row').children('label').children('span.mode-icon').hide();
                    select.removeAttr('multiple').removeAttr('size');
                    placeholder = 'type to filter';
                } else {
                    $('.multiinput', select.closest('.form-row')).removeClass('disabled');
                    select.closest('.form-row').children('label').children('span.mode-icon').show();
                    select.attr('multiple', 'multiple').attr('size', 8);
                    placeholder = 'type to filter, [enter] to select all';
                }
                $('input.multiinput-filter', select.parent()).attr(
                    'placeholder', placeholder);
            }
            $( "select[refresh_on_change='true']").change( function() {
                $( "#agent_form" ).submit();
            });
            $("div.agentFormTitle").click(function(){
                toggle_agent_body($(this));
            });
            if ('${hide_fixed_params}'.toLowerCase() == 'true') {
                // hide parameters that are not runtime inputs
                $("div.form-row:not(:has(select, textarea, input[type!=hidden], .wfpspan))").hide();
                $("div.agentForm:not(:has(select, textarea, input[type!=hidden], .wfpspan))").hide();
            }
            else {
                // Collapse non-interactive run-workflow panels by default.
                $("div.agentFormBody:not(:has(.runtime-form-row))").hide().parent().css('border-bottom-width', '0px');
            }
            $("#show_all_agent_body").click(function(){
                $("div.agentFormTitle").each(function(){
                    show_agent_body($(this));
                });
            });
            $("#hide_all_agent_body").click(function(){
                $("div.agentFormTitle").each(function(){
                    hide_agent_body($(this));
                });
            });
            $("#new_history_cbx").click(function(){
                $("#new_history_input").toggle(this.checked);
            });
            $('span.multiinput_wrap select[name*="|input"]').removeAttr('multiple').each(function(i, s) {
                var select = $(s);
                // The destroy on the following line is temporary and prevents
                // select2 use on Input Dataset Steps, but allows elsewhere.  We
                // need a new widget to better handle pairwise matching.
                select.select2("destroy");
                var new_width = Math.max(200, select.width()) + 20;
                // Find the label for this element.
                select.closest('.form-row').children('label').append(
                    $('<span class="icon-button multiinput"></span>').click(function() {
                        if ($(this).hasClass('disabled')) return;
                        toggle_multiinput(select);
                        select.focus();
                    }).attr('title',
                            'Enable/disable selection of multiple input ' +
                            'files. Each selected file will have an ' +
                            'instance of the workflow.').agenttip({placement: 'bottom'})
                );
                var filter = $('<input type="text" class="multiinput-filter" ' +
                               'placeholder="type to filter">');
                var filter_timeout = false;
                var original_rows = select.find('option');
                var previous_filter = '';
                // Todo: might have to choose keypress, depending on browser
                filter.keydown(function(e) {
                    var filter_select = function() {
                        var f = $.trim(filter.val());
                        var filtered_rows = original_rows;
                        if (f.length >= 1) {
                            filtered_rows = original_rows.filter(function() {
                                return new RegExp(f, 'ig').test($(this).text());
                            });
                        }
                        select.html('');
                        select.html(filtered_rows);
                    };
                    if (e.which == 13) { // 13 = enter key
                        e.preventDefault();
                        multi = select.attr('multiple');
                        if (typeof multi !== 'undefined' && multi !== false) {
                            if (!select.find('option:not(:selected)').length) {
                                select.find('option').removeAttr('selected');
                            } else {
                                select.find('option').attr('selected', 'selected');
                            }
                        }
                        return;
                    }
                    if (filter.val() != previous_filter) {
                        if (filter_timeout) clearTimeout(filter_timeout);
                        timeout = setTimeout(filter_select, 300);
                        previous_filter = filter.val();
                    }
                }).width(new_width).css('display', 'block');
                select.after(filter);
                select.width(new_width);
            });
        // Editable Workflow

        var readyParameter = function(icon) {
            icon.attr("name", "edit");
            icon.attr('title', "Modify default value for this workflow parameter.");
            icon.removeClass("workflow-edit-button-editing");
            icon.addClass("workflow-edit-button-ready");
            icon.addClass("fa-edit");
            icon.removeClass("fa-undo");
        };

        var editingParameter = function(icon) {
            icon.attr("name", "revert");
            icon.attr('title', "Restore workflow default value for this parameter.");
            icon.addClass("workflow-edit-button-editing");
            icon.removeClass("workflow-edit-button-ready");
            icon.removeClass("fa-edit");
            icon.addClass("fa-undo");
        };

         $(".workflow-edit-button").on("click",function(){
                var state = $(this).attr("name");
                var stepAgentBox = $(this).parent().parent().find('.editable-param').find('input:not([class]):not([type="hidden"]), select:not([class])');
                var labels = $(this).parent().parent().find('.editable-param').find('label');
                var split_name = stepAgentBox.attr("name").split("|");
                var step_id = split_name[0];
                var step_name = split_name.slice(2, split_name.length).join("|");
                var hidden_html = "<input type='hidden' name='"+step_id+"|__runtime__"+step_name+"' value='true' />";
                var html = "";
                if (state === "edit"){
                    stepAgentBoxClone = stepAgentBox.clone();
                    stepAgentBoxClone.each(function(index){$(stepAgentBoxClone[index]).attr({"name":step_id+"|"+step_name})});
                    stepAgentBoxClone.show();
                    if (labels.length > 0){
                        stepAgentBoxClone.each(function(index){
                        html += stepAgentBoxClone[index].outerHTML + labels[index].outerHTML + "<br/>"});
                    }
                    else{
                        html = stepAgentBoxClone.outerHTML();
                    }
                    $(this).parent().find(".editable").show();
                    $(this).parent().parent().find(".uneditable_field").hide();
                    $(this).parent().find(".editable").html(html+hidden_html);
                    editingParameter($(this));
                }
                else{
                    $(this).parent().find(".editable").hide();
                    $(this).parent().find(".editable").empty();
                    $(this).parent().parent().find(".uneditable_field").show();
                    $(this).attr("name", "edit");
                    readyParameter($(this));
                }
            }).each(function(i, icon) {
                var conditionalStart = $(this).closest(".form-row").prev().hasClass("conditional-start");
                if(! conditionalStart ) {
                    readyParameter($(icon));
                }
            });

            // Augment hidden fields with icons.
            // http://stackoverflow.com/a/2088430
            $(function(){
                $(".multi-mode").each(function(){
                    if($(this).val() == "matched") {
                        $(this).closest('.form-row').children('label').append($('<span class="icon-button link mode-icon" title="This input is linked and will be run in matched order with other input datasets (ex: use this for matching forward and reverse reads)."></span>')
                            .attr({id:$(this).attr("id")})
                            .css("display", $(this).css("display"))
                            .agenttip({placement: 'bottom'}));
                    } else {
                        $(this).closest('.form-row').children('label').append($('<span class="icon-button link-broken mode-icon" title="This input is not linked and each selection will be run against *all* other inputs."></span>')
                            .attr({id:$(this).attr("id")})
                            .css("display", $(this).css("display"))
                            .agenttip({placement: 'bottom'}));
                    }
                });
                $("span.mode-icon").click(function(){
                    i= $(this).closest('.form-row').find("input[type=hidden]");
                    if($(this).hasClass("link")) {
                        $(this).removeClass("link").addClass("link-broken");
                        $(i).val("product");
                    } else {
                        $(this).removeClass("link-broken").addClass("link");
                        $(i).val("matched");
                    }
                });
            });
            $("#agent_form").preventDoubleSubmission().submit(function(e) {
                var matchLength = -1;
                $('span.multiinput_wrap select[name*="|input"]').each(function() {
                    var value = $(this).val();
                    if(value instanceof Array) {
                        // Multi-value
                        if($(this).siblings("input[type=hidden]").val() == "matched") {
                            var length = $(this).val().length;
                            if(matchLength == -1) {
                                matchLength = length;
                            } else if(length != matchLength) {
                                e.preventDefault();
                                alert("Linked inputs must be submitted in equal number.");
                                return false;
                            }
                        }
                    }
                });
                return true;
            });
        });
    </script>
</%def>

<%def name="stylesheets()">
    ${parent.stylesheets()}
    ${h.css( "autocomplete_tagging" )}
    <style type="text/css">
    #new_history_p{
        line-height:2.5em;
        margin:0em 0em .5em 0em;
    }
    #new_history_cbx{
        margin-right:.5em;
    }
    #new_history_input{
        display:none;
        line-height:1em;
    }
    #ec_button_container{
        float:right;
    }
    div.agentForm{
        margin-top: 10px;
        margin-bottom: 10px;
    }
    div.agentFormTitle{
        cursor:pointer;
    }
    .title_ul_text{
        text-decoration:underline;
    }
    .step-annotation {
        margin-top: 0.25em;
        font-weight: normal;
        font-size: 97%;
    }
    .workflow-annotation {
        margin-bottom: 1em;
    }
    .editable {
        display: none;
    }
    .editable-param {
        display: none;
    }

    .workflow-edit-button-editing {
        color: black;
    }

    .workflow-edit-button-default {
        color: Gray;
    }

    .workflow-edit-button:hover {
        color: green; // TODO: Use a history panel green.
    }

    </style>
</%def>

<%
from galaxy.agents.parameters.basic import DataCollectionAgentParameter, DataAgentParameter, RuntimeValue
from galaxy.jobs.actions.post import ActionBox
import re
import colorsys
import random

used_accumulator = []

wf_parms = {}
for step in steps:
    for v in [ActionBox.get_short_str(pja) for pja in step.post_job_actions] + step.state.inputs.values():
        if isinstance(v, basestring):
            for rematch in re.findall('\$\{.+?\}', v):
                if rematch[2:-1] not in wf_parms:
                    wf_parms[rematch[2:-1]] = ""
if wf_parms:
    hue_offset = 1.0 / len(wf_parms)
    hue = 0.0
    for k in wf_parms.iterkeys():
        wf_parms[k] = "#%X%X%X" % tuple([int(x * 255) for x in colorsys.hsv_to_rgb(hue, .1, .9)])
        hue += hue_offset
%>

<%def name="do_inputs( inputs, values, errors, prefix, step, other_values = None, already_used = None )">
  <%
  from galaxy.util.expressions import ExpressionContext
  other_values = ExpressionContext( values, other_values )
  %>
  %for input_index, input in enumerate( inputs.itervalues() ):
    %if input.type == "repeat":
      <div class="repeat-group">
          <div class="form-title-row"><b>${input.title_plural}</b></div>
          <% repeat_values = values[input.name] %>
          %for i in range( len( repeat_values ) ):
            %if input.name in errors:
                <% rep_errors = errors[input.name][i] %>
            %else:
                <% rep_errors = dict() %>
            %endif
            <div class="repeat-group-item">
            <% index = repeat_values[i]['__index__'] %>
            <div class="form-title-row"><b>${input.title} ${i + 1}</b></div>
            ${do_inputs( input.inputs, repeat_values[ i ], rep_errors,  prefix + input.name + "_" + str(index) + "|", step, other_values, already_used )}
            ## <div class="form-row"><input type="submit" name="${step.id}|${prefix}${input.name}_${i}_remove" value="Remove ${input.title} ${i+1}" /></div>
            </div>
          %endfor
          ## <div class="form-row"><input type="submit" name="${step.id}|${prefix}${input.name}_add" value="Add new ${input.title}" /></div>
      </div>
    %elif input.type == "conditional":
      %if input.is_job_resource_conditional:
        <% continue %>
      %endif
      <% group_values = values[input.name] %>
      <% current_case = group_values['__current_case__'] %>
      <% new_prefix = prefix + input.name + "|" %>
      <% group_errors = errors.get( input.name, {} ) %>
      <span class="conditional-start"></span>
      ${row_for_param( input.test_param, group_values[ input.test_param.name ], other_values, group_errors, prefix, step, already_used )}
      ${do_inputs( input.cases[ current_case ].inputs, group_values, group_errors, new_prefix, step, other_values, already_used )}
    %elif input.type != "section":
      ${row_for_param( input, values[ input.name ], other_values, errors, prefix, step, already_used )}
    %endif
  %endfor
</%def>

<%def name="row_for_param( param, value, other_values, error_dict, prefix, step, already_used )">
    ## -- ${param.name} -- ${step.state.inputs} --
    %if error_dict.has_key( param.name ):
        <% cls = "form-row form-row-error" %>
    %else:
        <% cls = "form-row" %>
    %endif
    <div class="${cls}">
        <label>${param.get_label() | h}</label>
        <div>
            %if isinstance( param, DataAgentParameter ) or isinstance( param, DataCollectionAgentParameter ):
                %if ( prefix + param.name ) in step.input_connections_by_name:
                    <%
                        conns = step.input_connections_by_name[ prefix + param.name ]
                        if not isinstance(conns, list):
                            conns = [conns]
                        vals = ["Output dataset '%s' from step %d" % (conn.output_name, int(conn.output_step.order_index)+1) for conn in conns]
                    %>
                    ${",".join(vals)}
                %else:
                    ## FIXME: Initialize in the controller
                    <%
                    if value is None:
                        value = other_values[ param.name ] = param.get_initial_value_from_history_prevent_repeats( t, other_values, already_used )
                        if not enable_unique_defaults:
                            del already_used[:]
                    %>
                    %if step.type in [ 'data_input', 'data_collection_input' ]:
                    ##Input Dataset Step, wrap for multiinput.
                        <span class="runtime-form-row">
                            <span class='multiinput_wrap'>
                            <input class="multi-mode" type="hidden" name="${str(step.id)}|multi_mode" id="${str(step.id)}|multi_mode" value="matched" />
                            ${param.get_html_field( t, value, other_values ).get_html( str(step.id) + "|" + prefix )}
                            </span>
                        </span>
                    %else:
                        <span class="runtime-form-row">
                            ${param.get_html_field( t, value, other_values ).get_html( str(step.id) + "|" + prefix )}
                        </span>
                    %endif

                    <input type="hidden" name="${step.id}|__force_update__${prefix}${param.name}" value="true" />
                %endif
            %elif isinstance( value, RuntimeValue ) or ( str(step.id) + '|__runtime__' + prefix + param.name ) in incoming:
                ## On the first load we may see a RuntimeValue, so we write
                ## an input field using the initial value for the param.
                ## Subsequents posts will no longer have the runtime value
                ## (since an actualy value will be posted) so we add a hidden
                ## field so we know to continue drawing form for this param.
                ## FIXME: This logic shouldn't be in the template. The
                ## controller should go through the inputs on the first
                ## load, fill in initial values where needed, and mark
                ## all that are runtime modifiable in some way.
                <%
                    value = other_values[ param.name ] = param.get_initial_value_from_history_prevent_repeats( t, other_values, already_used )
                    if not enable_unique_defaults:
                        del already_used[:]
                %>
                <span class="runtime-form-row">
                    ${param.get_html_field( t, value, other_values ).get_html( str(step.id) + "|" + prefix )}
                    <input type="hidden" name="${step.id}|__runtime__${prefix}${param.name}" value="true" />
                </span>
            %else:
                <%
                p_text = param.value_to_display_text( value, app )
                replacements = []
                if isinstance(p_text, basestring):
                    for rematch in re.findall('\$\{.+?\}', p_text):
                        if rematch[2:-1] in wf_parms:
                            replacements.append('wf_parm__%s' % rematch[2:-1])
                            p_text = p_text.replace(rematch, '<span style="background-color:%s" class="runtime-form-row wfpspan wf_parm__%s">%s</span>' % (wf_parms[rematch[2:-1]], rematch[2:-1], rematch[2:-1]))
                %>
                %if replacements:
                    <span style="display:none" class="parm_wrap ${' '.join(replacements)}">
                    ${param.get_html_field( t, value, other_values ).get_html( str(step.id) + "|" + prefix )}
                    </span>
                    <span class="p_text_wrapper">${p_text}</span>
                    <input type="hidden" name="${step.id}|__runtime__${prefix}${param.name}" value="true" />
                %else:
                <span class="workflow_parameters">
                    <span class="uneditable_field">
                        ${param.value_to_display_text( value, app ) | h}
                    </span>
                    <span class="editable_field">
                        <span class="editable">
                        </span>

                        <i class="fa workflow-edit-button"></i>
                    </span>
                    <span class="editable-param">
                        <!-- Pristine variant of param, this will be cloned
                             and modified when the user opts to make this
                             editable.
                        -->
                        ${param.get_html_field( t, value, other_values).get_html( str(step.id) + "|"+ "editable" + "|" + prefix )}
                    </span>
                </span>
                %endif
            %endif
        </div>
        %if step.upgrade_messages and param.name in step.upgrade_messages:
        <div class="warningmark">${step.upgrade_messages[param.name]}</div>
        %endif
        %if error_dict.has_key( param.name ):
        <div style="color: red; font-weight: bold; padding-top: 1px; padding-bottom: 3px;">
            <div style="width: 300px;"><img style="vertical-align: middle;" src="${h.url_for('/static/style/error_small.png')}">&nbsp;<span style="vertical-align: middle;">${error_dict[param.name]}</span></div>
        </div>
        %endif
        <div style="clear: both"></div>
    </div>
</%def>

<div id='ec_button_container'>
    <span class="action-button" id="show_all_agent_body">Expand All</span>
    <span class="action-button" id="hide_all_agent_body">Collapse</span>
</div>

<h2>Running workflow "${h.to_unicode( workflow.name ) | h}"</h2>

%if has_upgrade_messages:
<div class="warningmessage">
    Problems were encountered when loading this workflow, likely due to agent
    version changes. Missing parameter values have been replaced with default.
    Please review the parameter values below.
</div>
%endif

%if step_version_changes:
    <div class="infomessage">
        The following agents are beinge executed with a different version from
        what was available when this workflow was last saved because the
        previous version is no longer available for use on this galaxy
        instance.
        To upgrade your workflow and dismiss this message simply edit the
        workflow and re-save it to update the stored agent version.
        <ul>
            %for vc in step_version_changes:
                <li>${vc}</li>
            %endfor
        </ul>
    </div>
%endif

%if workflow.annotation:
    <div class="workflow-annotation">${workflow.annotation}</div>
    <hr/>
%endif

<form id="agent_form" name="agent_form" method="POST">
## <input type="hidden" name="workflow_name" value="${h.to_unicode( workflow.name ) | h}" />

%if wf_parms:
<div class="metadataForm">
    <div class="metadataFormTitle">Workflow Parameters</div>
    <div class="metadataFormBody">
    %for parm in wf_parms:
        <div class='form-row'><label>${parm}<br/><input size=40 style="border:2px solid ${wf_parms[parm]};border-left-width:8px;" type="text" class='wf_parm_input ptag_${parm}' name="wf_parm|${parm}" value=""/></label></div>
    %endfor
    </div>
</div>
    <script type="text/javascript">
    // Set the change hooks for workflow parameters.
    $(document).ready(function () {
        $('.wf_parm_input').bind('change keypress keyup', function(event){
            // DBTODO This is probably not reliable.  Ensure we have the right class.
            var new_text = $(this).val();
            if (new_text === ''){
                var tag_id = $(this).attr("class").split(' ')[1].substring(5);
                // Set text properly.
                $('.wfpspan.wf_parm__'+tag_id).text(tag_id);
            }else{
                var tag_id = $(this).attr("class").split(' ')[1].substring(5);
                // Set text properly.
                $('.wfpspan.wf_parm__'+tag_id).text(new_text);
                // Now set the hidden input to the generated text.
                $('.wfpspan.wf_parm__'+tag_id).not('.pja_wfp').each(function(){
                    var new_text = $(this).parent().text();
                    $(this).parent().siblings().children().val(new_text);
                });
            }
        });
    });
    </script>
%endif
%for i, step in enumerate( steps ):
    <!-- Only way module would be missing is if agent is missing, but
         that would cause missing_agents.mako to render instead of this
         template. -->
    <% module = step.module %>
    <input type="hidden" name="${step.id}|agent_state" value="${module.encode_runtime_state( t, step.state )}">
    %if step.type == 'agent' or step.type is None:
      <%
        agent = trans.app.agentbox.get_agent( step.agent_id )
      %>
      <div class="agentForm">
          <div class="agentFormTitle">
              <span class='title_ul_text'>Step ${int(step.order_index)+1}: ${agent.name}</span>
              %if agent.version:
                  (version ${agent.version})
              %endif
              % if step.annotations:
                <div class="step-annotation">${h.to_unicode( step.annotations[0].annotation )}</div>
              % endif
          </div>
          <div class="agentFormBody">
                ${do_inputs( agent.inputs, step.state.inputs, errors.get( step.id, dict() ), "", step, None, used_accumulator )}
                % if step.post_job_actions:
                    <hr/>
                    <div class='form-row'>
                    % if len(step.post_job_actions) > 1:
                        <label>Actions:</label>
                    % else:
                        <label>Action:</label>
                    % endif
                    <%
                    pja_ss_all = []
                    for pja_ss in [ActionBox.get_short_str(pja) for pja in step.post_job_actions]:
                        for rematch in re.findall('\$\{.+?\}', pja_ss):
                            pja_ss = pja_ss.replace(rematch, '<span style="background-color:%s" class="wfpspan wf_parm__%s pja_wfp">%s</span>' % (wf_parms[rematch[2:-1]],
                                                                                                                                                  rematch[2:-1],
                                                                                                                                                  rematch[2:-1]))
                        pja_ss_all.append(pja_ss)
                    %>
                    ${'<br/>'.join(pja_ss_all)}
                    </div>
                % endif
              </div>
          </div>
        %else:
          <div class="agentForm">
              <div class="agentFormTitle">
                  <span class='title_ul_text'>Step ${int(step.order_index)+1}: ${module.name | h}</span>
                  % if step.annotations:
                    <div class="step-annotation">${step.annotations[0].annotation}</div>
                  % endif
          </div>
          <div class="agentFormBody">
              <%
              # Filter possible inputs to data types that are valid for subsequent steps
              type_filter = []
              for oc in step.output_connections:
                  for ic in oc.input_step.module.get_data_inputs():
                      if 'extensions' in ic and ic['name'] == oc.input_name:
                          type_filter += ic['extensions']
              if not type_filter:
                  type_filter = ['data']
              %>
              ${do_inputs( module.get_runtime_inputs(filter_set=type_filter), step.state.inputs, errors.get( step.id, dict() ), "", step, None, used_accumulator )}
          </div>
      </div>
    %endif
%endfor
%if history_id is None:
    <p id='new_history_p'>
        <input type="checkbox" name='new_history' value="true" id='new_history_cbx'/><label for='new_history_cbx'>Send results to a new history </label>
        <span id="new_history_input">named: <input type='text' name='new_history_name' value='${ h.to_unicode( workflow.name ) | h }'/></span>
    </p>
%endif
<input type="submit" class="btn btn-primary" name="run_workflow" value="Run workflow" />
</form>
%endif
