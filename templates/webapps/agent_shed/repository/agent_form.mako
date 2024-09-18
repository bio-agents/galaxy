<%inherit file="/base.mako"/>
<%namespace file="/message.mako" import="render_msg" />
<%namespace file="/webapps/agent_shed/common/repository_actions_menu.mako" import="*" />

<%
    from galaxy.util.expressions import ExpressionContext
    from galaxy import util
    from galaxy.agents.parameters.basic import DataAgentParameter, ColumnListParameter, GenomeBuildParameter, SelectAgentParameter
    from galaxy.web.form_builder import SelectField
%>

<html>
    <head>
        <title>Galaxy agent preview</title>
        <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
        ${h.css( "base" )}
    </head>
    <body>
        <%def name="do_inputs( inputs, agent_state, prefix, other_values=None )">
            <% other_values = ExpressionContext( agent_state, other_values ) %>
            %for input_index, input in enumerate( inputs.itervalues() ):
                %if not input.visible:
                    <% pass %>
                %elif input.type in ["repeat", "section"]:
                    <div class="repeat-group">
                        <div class="form-title-row">
                            <b>${input.title_plural}</b>
                        </div>
                        <div class="repeat-group-item">
                            <div class="form-title-row">
                                <b>${input.title} 0</b>
                            </div>
                        </div>
                    </div>
                %elif input.type == "conditional":
                    %if agent_state.items():
                        <%
                            try:
                                group_state = agent_state[ input.name ][ 0 ]
                            except Exception, e:
                                group_state = agent_state[ input.name ]
                            current_case = group_state[ '__current_case__' ]
                            group_prefix = prefix + input.name + "|"
                        %>
                        %if input.value_ref_in_group:
                            ${row_for_param( group_prefix, input.test_param, group_state, other_values )}
                        %endif
                        ${do_inputs( input.cases[current_case].inputs, group_state, group_prefix, other_values )}
                    %endif
                %elif input.type == "upload_dataset":
                    %if input.get_datatype( trans, other_values ).composite_type is None:
                        ## Have non-composite upload appear as before
                        ${do_inputs( input.inputs, 'files', prefix + input.name + "_" + str( 0 ) + "|", other_values )}
                    %else:
                        <div class="repeat-group">
                            <div class="form-title-row">
                                <b>${input.group_title( other_values )}</b>
                            </div>
                            <div class="repeat-group-item">
                            <div class="form-title-row">
                                <b>File Contents for ${input.title_by_index( trans, 0, other_values )}</b>
                            </div>
                        </div>
                    %endif
                %else:
                    ${row_for_param( prefix, input, agent_state, other_values )}
                %endif
            %endfor  
        </%def>
        
        <%def name="row_for_param( prefix, param, parent_state, other_values )">
            <%
                # Disable refresh_on_change for select lists displayed in the agent shed. 
                param.refresh_on_change = False
                label = param.get_label()
                if isinstance( param, DataAgentParameter ) or isinstance( param, ColumnListParameter ) or isinstance( param, GenomeBuildParameter ):
                    field = SelectField( param.name )
                    field.add_option( param.name, param.name )
                    field_html = field.get_html()
                elif isinstance( param, SelectAgentParameter ) and hasattr( param, 'data_ref' ):
                    field = SelectField( param.name, display=param.display, multiple=param.multiple )
                    field.add_option( param.data_ref, param.data_ref )
                    field_html = field.get_html( prefix )
                elif isinstance( param, SelectAgentParameter ) and param.is_dynamic:
                    field = SelectField( param.name, display=param.display, multiple=param.multiple )
                    dynamic_options = param.options
                    if dynamic_options is not None:
                        if dynamic_options.index_file:
                            option_label = "Dynamically generated from entries in file %s" % str( dynamic_options.index_file )
                            field.add_option( option_label, "none" )
                        elif dynamic_options.missing_index_file:
                            option_label = "Dynamically generated from entries in missing file %s" % str( dynamic_options.missing_index_file )
                            field.add_option( option_label, "none" )
                    else:
                        field.add_option( "Dynamically generated from old-style Dynamic Options.", "none" )
                    field_html = field.get_html( prefix )
                else:
                    field = param.get_html_field( trans, None, other_values )
                    field_html = field.get_html( prefix )
            %>
            <div class="form-row">
                %if label:
                    <label for="${param.name}">${label}:</label>
                %endif
                <div class="form-row-input">${field_html}</div>
                %if param.help:
                    <div class="agentParamHelp" style="clear: both;">
                        ${param.help}
                    </div>
                %endif
                <div style="clear: both"></div>     
            </div>
        </%def>

        %if render_repository_actions_for == 'galaxy':
            ${render_galaxy_repository_actions( repository=repository )}
        %else:
            ${render_agent_shed_repository_actions( repository, metadata=None, changeset_revision=None )}
        %endif

        %if message:
            ${render_msg( message, status )}
        %endif

        %if agent:
            <div class="agentForm" id="${agent.id | h}">
                <div class="agentFormTitle">${agent.name | h} (version ${agent.version | h})</div>
                <div class="agentFormBody">
                    <form id="agent_form" name="agent_form" action="" method="get">
                        <input type="hidden" name="agent_state" value="${util.object_to_string( agent_state.encode( agent, app ) )}">
                        ${do_inputs( agent.inputs_by_page[ agent_state.page ], agent_state.inputs, "" )}
                    </form>
                </div>
            </div>
            %if agent.help:
                <div class="agentHelp">
                    <div class="agentHelpBody">
                        <%
                            agent_help = agent.help
                            # Help is Mako template, so render using current static path.
                            agent_help = agent_help.render( static_path=h.url_for( '/static' ) )
                            # Convert to unicode to display non-ascii characters.
                            if type( agent_help ) is not unicode:
                                agent_help = unicode( agent_help, 'utf-8')
                        %>
                        ${agent_help}
                    </div>
                </div>
            %endif
        %else:
            Agent not properly loaded.
        %endif
    </body>
</html>
