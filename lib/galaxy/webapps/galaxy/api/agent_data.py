import os

from galaxy import exceptions
from galaxy import web
from galaxy.web import _future_expose_api as expose_api
from galaxy.web import _future_expose_api_raw as expose_api_raw
from galaxy.web.base.controller import BaseAPIController
import galaxy.queue_worker


class AgentData( BaseAPIController ):
    """
    RESTful controller for interactions with agent data
    """

    @web.require_admin
    @expose_api
    def index( self, trans, **kwds ):
        """
        GET /api/agent_data: returns a list agent_data tables::

        """
        return list( a.to_dict() for a in self._data_tables.values() )

    @web.require_admin
    @expose_api
    def show( self, trans, id, **kwds ):
        return self._data_table(id).to_dict(view='element')

    @web.require_admin
    @expose_api
    def reload( self, trans, id, **kwd ):
        """
        GET /api/agent_data/{id}/reload

        Reloads a agent_data table.
        """
        decoded_agent_data_id = id
        data_table = trans.app.agent_data_tables.data_tables.get(decoded_agent_data_id)
        data_table.reload_from_files()
        galaxy.queue_worker.send_control_task( trans.app, 'reload_agent_data_tables',
                                               noop_self=True,
                                               kwargs={'table_name': decoded_agent_data_id} )
        return self._data_table( decoded_agent_data_id ).to_dict( view='element' )

    @web.require_admin
    @expose_api
    def delete( self, trans, id, **kwd ):
        """
        DELETE /api/agent_data/{id}
        Removes an item from a data table

        :type   id:     str
        :param  id:     the id of the data table containing the item to delete
        :type   kwd:    dict
        :param  kwd:    (required) dictionary structure containing:

            * payload:     a dictionary itself containing:
                * values:   <TAB> separated list of column contents, there must be a value for all the columns of the data table
        """
        decoded_agent_data_id = id

        try:
            data_table = trans.app.agent_data_tables.data_tables.get(decoded_agent_data_id)
        except:
            data_table = None
        if not data_table:
            trans.response.status = 400
            return "Invalid data table id ( %s ) specified." % str( decoded_agent_data_id )

        values = None
        if kwd.get( 'payload', None ):
            values = kwd['payload'].get( 'values', '' )

        if not values:
            trans.response.status = 400
            return "Invalid data table item ( %s ) specified." % str( values )

        split_values = values.split("\t")

        if len(split_values) != len(data_table.get_column_name_list()):
            trans.response.status = 400
            return "Invalid data table item ( %s ) specified. Wrong number of columns (%s given, %s required)." % ( str( values ), str(len(split_values)), str(len(data_table.get_column_name_list())))

        data_table.remove_entry(split_values)
        galaxy.queue_worker.send_control_task( trans.app, 'reload_agent_data_tables',
                                               noop_self=True,
                                               kwargs={'table_name': decoded_agent_data_id} )
        return self._data_table( decoded_agent_data_id ).to_dict( view='element' )

    @web.require_admin
    @expose_api
    def show_field( self, trans, id, value, **kwds ):
        """
        GET /api/agent_data/<id>/fields/<value>

        Get information about a partiular field in a agent_data table
        """
        return self._data_table_field( id, value ).to_dict()

    @web.require_admin
    @expose_api_raw
    def download_field_file( self, trans, id, value, path, **kwds ):
        field_value = self._data_table_field( id, value )
        base_dir = field_value.get_base_dir()
        full_path = os.path.join( base_dir, path )
        if full_path not in field_value.get_files():
            raise exceptions.ObjectNotFound("No such path in data table field.")
        return open(full_path, "r")

    def _data_table_field( self, id, value ):
        out = self._data_table(id).get_field(value)
        if out is None:
            raise exceptions.ObjectNotFound("No such field %s in data table %s." % (value, id))
        return out

    def _data_table( self, id ):
        try:
            return self._data_tables[id]
        except IndexError:
            raise exceptions.ObjectNotFound("No such data table %s" % id)

    @property
    def _data_tables( self ):
        return self.app.agent_data_tables.data_tables
