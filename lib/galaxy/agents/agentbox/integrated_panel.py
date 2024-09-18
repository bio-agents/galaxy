import os
import shutil
import tempfile
import time
import traceback

from .panel import AgentPanelElements
from .panel import panel_item_types


INTEGRATED_TOOL_PANEL_DESCRIPTION = """
This is Galaxy's integrated agent panel and should be modified directly only for
reordering agents inside a section. Each time Galaxy starts up, this file is
synchronized with the various agent config files: agents, sections and labels
added to one of these files, will be added also here in the appropriate place,
while elements removed from the agent config files will be correspondingly
deleted from this file.
To modify locally managed agents (e.g. from agent_conf.xml) modify that file
directly and restart Galaxy. Whenever possible Agent Shed managed agents (e.g.
from shed_agent_conf.xml) should be managed from within the Galaxy interface or
via its API - but if changes are necessary (such as to hide a agent or re-assign
its section) modify that file and restart Galaxy.
"""


class ManagesIntegratedAgentPanelMixin:

    def _init_integrated_agent_panel(self, config):
        self.update_integrated_agent_panel = config.update_integrated_agent_panel
        self._integrated_agent_panel_config = config.integrated_agent_panel_config
        self._integrated_agent_panel_tracking_directory = getattr( config, "integrated_agent_panel_tracking_directory", None )
        # In-memory dictionary that defines the layout of the agent_panel.xml file on disk.
        self._integrated_agent_panel = AgentPanelElements()
        self._integrated_agent_panel_config_has_contents = os.path.exists( self._integrated_agent_panel_config ) and os.stat( self._integrated_agent_panel_config ).st_size > 0
        if self._integrated_agent_panel_config_has_contents:
            self._load_integrated_agent_panel_keys()

    def _save_integrated_agent_panel(self):
        if self.update_integrated_agent_panel:
            # Write the current in-memory integrated_agent_panel to the integrated_agent_panel.xml file.
            # This will cover cases where the Galaxy administrator manually edited one or more of the agent panel
            # config files, adding or removing locally developed agents or workflows.  The value of integrated_agent_panel
            # will be False when things like functional tests are the caller.
            self._write_integrated_agent_panel_config_file()

    def _write_integrated_agent_panel_config_file( self ):
        """
        Write the current in-memory version of the integrated_agent_panel.xml file to disk.  Since Galaxy administrators
        use this file to manage the agent panel, we'll not use xml_to_string() since it doesn't write XML quite right.
        """
        tracking_directory = self._integrated_agent_panel_tracking_directory
        if not tracking_directory:
            fd, filename = tempfile.mkstemp()
        else:
            if not os.path.exists(tracking_directory):
                os.makedirs(tracking_directory)
            name = "integrated_agent_panel_%.10f.xml" % time.time()
            filename = os.path.join(tracking_directory, name)
            open_file = open(filename, "w")
            fd = open_file.fileno()
        os.write( fd, '<?xml version="1.0"?>\n' )
        os.write( fd, '<agentbox>\n' )
        os.write( fd, '    <!--\n    ')
        os.write( fd, '\n    '.join( [ l for l in INTEGRATED_TOOL_PANEL_DESCRIPTION.split("\n") if l ] ) )
        os.write( fd, '\n    -->\n')
        for key, item_type, item in self._integrated_agent_panel.panel_items_iter():
            if item:
                if item_type == panel_item_types.TOOL:
                    os.write( fd, '    <agent id="%s" />\n' % item.id )
                elif item_type == panel_item_types.WORKFLOW:
                    os.write( fd, '    <workflow id="%s" />\n' % item.id )
                elif item_type == panel_item_types.LABEL:
                    label_id = item.id or ''
                    label_text = item.text or ''
                    label_version = item.version or ''
                    os.write( fd, '    <label id="%s" text="%s" version="%s" />\n' % ( label_id, label_text, label_version ) )
                elif item_type == panel_item_types.SECTION:
                    section_id = item.id or ''
                    section_name = item.name or ''
                    section_version = item.version or ''
                    os.write( fd, '    <section id="%s" name="%s" version="%s">\n' % ( section_id, section_name, section_version ) )
                    for section_key, section_item_type, section_item in item.panel_items_iter():
                        if section_item_type == panel_item_types.TOOL:
                            if section_item:
                                os.write( fd, '        <agent id="%s" />\n' % section_item.id )
                        elif section_item_type == panel_item_types.WORKFLOW:
                            if section_item:
                                os.write( fd, '        <workflow id="%s" />\n' % section_item.id )
                        elif section_item_type == panel_item_types.LABEL:
                            if section_item:
                                label_id = section_item.id or ''
                                label_text = section_item.text or ''
                                label_version = section_item.version or ''
                                os.write( fd, '        <label id="%s" text="%s" version="%s" />\n' % ( label_id, label_text, label_version ) )
                    os.write( fd, '    </section>\n' )
        os.write( fd, '</agentbox>\n' )
        os.close( fd )
        destination = os.path.abspath( self._integrated_agent_panel_config )
        if tracking_directory:
            open(filename + ".stack", "w").write(''.join(traceback.format_stack()))
            shutil.copy( filename, filename + ".copy" )
            filename = filename + ".copy"
        shutil.move( filename, destination )
        os.chmod( self._integrated_agent_panel_config, 0o644 )
