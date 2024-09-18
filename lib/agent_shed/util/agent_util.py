import logging
import os
import shutil

import galaxy.agents
from galaxy import util
from galaxy.util import checkers
from galaxy.util.expressions import ExpressionContext
from galaxy.web.form_builder import SelectField

from agent_shed.util import basic_util

log = logging.getLogger( __name__ )


def build_shed_agent_conf_select_field( app ):
    """Build a SelectField whose options are the keys in app.agentbox.shed_agent_confs."""
    options = []
    for dynamic_agent_conf_filename in app.agentbox.dynamic_conf_filenames():
        if dynamic_agent_conf_filename.startswith( './' ):
            option_label = dynamic_agent_conf_filename.replace( './', '', 1 )
        else:
            option_label = dynamic_agent_conf_filename
        options.append( ( option_label, dynamic_agent_conf_filename ) )
    select_field = SelectField( name='shed_agent_conf' )
    for option_tup in options:
        select_field.add_option( option_tup[ 0 ], option_tup[ 1 ] )
    return select_field


def build_agent_panel_section_select_field( app ):
    """Build a SelectField whose options are the sections of the current in-memory agentbox."""
    options = []
    for section_id, section_name in app.agentbox.get_sections():
        options.append( ( section_name, section_id ) )
    select_field = SelectField( name='agent_panel_section_id', display='radio' )
    for option_tup in options:
        select_field.add_option( option_tup[ 0 ], option_tup[ 1 ] )
    return select_field


def copy_sample_file( app, filename, dest_path=None ):
    """
    Copy xxx.sample to dest_path/xxx.sample and dest_path/xxx.  The default value for dest_path
    is ~/agent-data.
    """
    if dest_path is None:
        dest_path = os.path.abspath( app.config.agent_data_path )
    sample_file_name = basic_util.strip_path( filename )
    copied_file = sample_file_name.replace( '.sample', '' )
    full_source_path = os.path.abspath( filename )
    full_destination_path = os.path.join( dest_path, sample_file_name )
    # Don't copy a file to itself - not sure how this happens, but sometimes it does...
    if full_source_path != full_destination_path:
        # It's ok to overwrite the .sample version of the file.
        shutil.copy( full_source_path, full_destination_path )
    # Only create the .loc file if it does not yet exist.  We don't overwrite it in case it
    # contains stuff proprietary to the local instance.
    if not os.path.exists( os.path.join( dest_path, copied_file ) ):
        shutil.copy( full_source_path, os.path.join( dest_path, copied_file ) )


def copy_sample_files( app, sample_files, agent_path=None, sample_files_copied=None, dest_path=None ):
    """
    Copy all appropriate files to dest_path in the local Galaxy environment that have not
    already been copied.  Those that have been copied are contained in sample_files_copied.
    The default value for dest_path is ~/agent-data.  We need to be careful to copy only
    appropriate files here because agent shed repositories can contain files ending in .sample
    that should not be copied to the ~/agent-data directory.
    """
    filenames_not_to_copy = [ 'agent_data_table_conf.xml.sample' ]
    sample_files_copied = util.listify( sample_files_copied )
    for filename in sample_files:
        filename_sans_path = os.path.split( filename )[ 1 ]
        if filename_sans_path not in filenames_not_to_copy and filename not in sample_files_copied:
            if agent_path:
                filename = os.path.join( agent_path, filename )
            # Attempt to ensure we're copying an appropriate file.
            if is_data_index_sample_file( filename ):
                copy_sample_file( app, filename, dest_path=dest_path )


def generate_message_for_invalid_agents( app, invalid_file_tups, repository, metadata_dict, as_html=True,
                                        displaying_invalid_agent=False ):
    if as_html:
        new_line = '<br/>'
        bold_start = '<b>'
        bold_end = '</b>'
    else:
        new_line = '\n'
        bold_start = ''
        bold_end = ''
    message = ''
    if app.name == 'galaxy':
        tip_rev = str( repository.changeset_revision )
    else:
        tip_rev = str( repository.tip( app ) )
    if not displaying_invalid_agent:
        if metadata_dict:
            message += "Metadata may have been defined for some items in revision '%s'.  " % tip_rev
            message += "Correct the following problems if necessary and reset metadata.%s" % new_line
        else:
            message += "Metadata cannot be defined for revision '%s' so this revision cannot be automatically " % tip_rev
            message += "installed into a local Galaxy instance.  Correct the following problems and reset metadata.%s" % new_line
    for itc_tup in invalid_file_tups:
        agent_file, exception_msg = itc_tup
        if exception_msg.find( 'No such file or directory' ) >= 0:
            exception_items = exception_msg.split()
            missing_file_items = exception_items[ 7 ].split( '/' )
            missing_file = missing_file_items[ -1 ].rstrip( '\'' )
            if missing_file.endswith( '.loc' ):
                sample_ext = '%s.sample' % missing_file
            else:
                sample_ext = missing_file
            correction_msg = "This file refers to a missing file %s%s%s.  " % \
                ( bold_start, str( missing_file ), bold_end )
            correction_msg += "Upload a file named %s%s%s to the repository to correct this error." % \
                ( bold_start, sample_ext, bold_end )
        else:
            if as_html:
                correction_msg = exception_msg
            else:
                correction_msg = exception_msg.replace( '<br/>', new_line ).replace( '<b>', bold_start ).replace( '</b>', bold_end )
        message += "%s%s%s - %s%s" % ( bold_start, agent_file, bold_end, correction_msg, new_line )
    return message


def get_headers( fname, sep, count=60, is_multi_byte=False ):
    """Returns a list with the first 'count' lines split by 'sep'."""
    headers = []
    for idx, line in enumerate( file( fname ) ):
        line = line.rstrip( '\n\r' )
        if is_multi_byte:
            line = unicode( line, 'utf-8' )
            sep = sep.encode( 'utf-8' )
        headers.append( line.split( sep ) )
        if idx == count:
            break
    return headers


def get_agent_path_install_dir( partial_install_dir, shed_agent_conf_dict, agent_dict, config_elems ):
    for elem in config_elems:
        if elem.tag == 'agent':
            if elem.get( 'guid' ) == agent_dict[ 'guid' ]:
                agent_path = shed_agent_conf_dict[ 'agent_path' ]
                relative_install_dir = os.path.join( agent_path, partial_install_dir )
                return agent_path, relative_install_dir
        elif elem.tag == 'section':
            for section_elem in elem:
                if section_elem.tag == 'agent':
                    if section_elem.get( 'guid' ) == agent_dict[ 'guid' ]:
                        agent_path = shed_agent_conf_dict[ 'agent_path' ]
                        relative_install_dir = os.path.join( agent_path, partial_install_dir )
                        return agent_path, relative_install_dir
    return None, None


def handle_missing_index_file( app, agent_path, sample_files, repository_agents_tups, sample_files_copied ):
    """
    Inspect each agent to see if it has any input parameters that are dynamically
    generated select lists that depend on a .loc file.  This method is not called
    from the agent shed, but from Galaxy when a repository is being installed.
    """
    for index, repository_agents_tup in enumerate( repository_agents_tups ):
        tup_path, guid, repository_agent = repository_agents_tup
        params_with_missing_index_file = repository_agent.params_with_missing_index_file
        for param in params_with_missing_index_file:
            options = param.options
            missing_file_name = basic_util.strip_path( options.missing_index_file )
            if missing_file_name not in sample_files_copied:
                # The repository must contain the required xxx.loc.sample file.
                for sample_file in sample_files:
                    sample_file_name = basic_util.strip_path( sample_file )
                    if sample_file_name == '%s.sample' % missing_file_name:
                        copy_sample_file( app, sample_file )
                        if options.agent_data_table and options.agent_data_table.missing_index_file:
                            options.agent_data_table.handle_found_index_file( options.missing_index_file )
                        sample_files_copied.append( options.missing_index_file )
                        break
        # Reload the agent into the local list of repository_agents_tups.
        repository_agent = app.agentbox.load_agent( os.path.join( agent_path, tup_path ), guid=guid, use_cached=False )
        repository_agents_tups[ index ] = ( tup_path, guid, repository_agent )
    return repository_agents_tups, sample_files_copied


def is_column_based( fname, sep='\t', skip=0, is_multi_byte=False ):
    """See if the file is column based with respect to a separator."""
    headers = get_headers( fname, sep, is_multi_byte=is_multi_byte )
    count = 0
    if not headers:
        return False
    for hdr in headers[ skip: ]:
        if hdr and hdr[ 0 ] and not hdr[ 0 ].startswith( '#' ):
            if len( hdr ) > 1:
                count = len( hdr )
            break
    if count < 2:
        return False
    for hdr in headers[ skip: ]:
        if hdr and hdr[ 0 ] and not hdr[ 0 ].startswith( '#' ):
            if len( hdr ) != count:
                return False
    return True


def is_data_index_sample_file( file_path ):
    """
    Attempt to determine if a .sample file is appropriate for copying to ~/agent-data when
    a agent shed repository is being installed into a Galaxy instance.
    """
    # Currently most data index files are tabular, so check that first.  We'll assume that
    # if the file is tabular, it's ok to copy.
    if is_column_based( file_path ):
        return True
    # If the file is any of the following, don't copy it.
    if checkers.check_html( file_path ):
        return False
    if checkers.check_image( file_path ):
        return False
    if checkers.check_binary( name=file_path ):
        return False
    if checkers.is_bz2( file_path ):
        return False
    if checkers.is_gzip( file_path ):
        return False
    if checkers.check_zip( file_path ):
        return False
    # Default to copying the file if none of the above are true.
    return True


def new_state( trans, agent, invalid=False ):
    """Create a new `DefaultAgentState` for the received agent.  Only inputs on the first page will be initialized."""
    state = galaxy.agents.DefaultAgentState()
    state.inputs = {}
    if invalid:
        # We're attempting to display a agent in the agent shed that has been determined to have errors, so is invalid.
        return state
    try:
        # Attempt to generate the agent state using the standard Galaxy-side code
        return agent.new_state( trans )
    except Exception, e:
        # Fall back to building agent state as below
        log.debug( 'Failed to build agent state for agent "%s" using standard method, will try to fall back on custom method: %s', agent.id, e )
    inputs = agent.inputs_by_page[ 0 ]
    context = ExpressionContext( state.inputs, parent=None )
    for input in inputs.itervalues():
        try:
            state.inputs[ input.name ] = input.get_initial_value( trans, context )
        except:
            # FIXME: not all values should be an empty list
            state.inputs[ input.name ] = []
    return state


def panel_entry_per_agent( agent_section_dict ):
    # Return True if agent_section_dict looks like this.
    # {<Agent guid> :
    #    [{ agent_config : <agent_config_file>,
    #       id: <AgentSection id>,
    #       version : <AgentSection version>,
    #       name : <TooSection name>}]}
    # But not like this.
    # { id: <AgentSection id>, version : <AgentSection version>, name : <TooSection name>}
    if not agent_section_dict:
        return False
    if len( agent_section_dict ) != 3:
        return True
    for k, v in agent_section_dict:
        if k not in [ 'id', 'version', 'name' ]:
            return True
    return False


def reload_upload_agents( app ):
    if hasattr( app, 'agentbox' ):
        app.agentbox.handle_datatypes_changed()
