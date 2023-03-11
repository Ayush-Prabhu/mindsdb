from typing import Optional
from collections import OrderedDict

from pyignite import Client
import pandas as pd

from mindsdb_sql import parse_sql
from mindsdb_sql.render.sqlalchemy_render import SqlalchemyRender
from mindsdb.integrations.libs.base import DatabaseHandler

from mindsdb_sql.parser.ast.base import ASTNode

from mindsdb.utilities import log
from mindsdb.integrations.libs.response import (
    HandlerStatusResponse as StatusResponse,
    HandlerResponse as Response,
    RESPONSE_TYPE
)
from mindsdb.integrations.libs.const import HANDLER_CONNECTION_ARG_TYPE as ARG_TYPE


class IgniteHandler(DatabaseHandler):
    """
    This handler handles connection and execution of the Apache Ignite statements.
    """

    name = 'ignite'

    def __init__(self, name: str, connection_data: Optional[dict], **kwargs):
        """
        Initialize the handler.
        Args:
            name (str): name of particular handler instance
            connection_data (dict): parameters for connecting to the database
            **kwargs: arbitrary keyword arguments.
        """
        super().__init__(name)
        self.parser = parse_sql
        self.dialect = 'ignite'
        self.connection_data = connection_data
        self.kwargs = kwargs

        self.client = None
        self.connection = None
        self.is_connected = False

    def __del__(self):
        if self.is_connected is True:
            self.disconnect()

    def connect(self) -> StatusResponse:
        """
        Set up the connection required by the handler.
        Returns:
            HandlerStatusResponse
        """

        if self.is_connected is True:
            return self.connection

        self.client = Client(
            username=self.connection_data['username'],
            password=self.connection_data['password']
        )

        nodes = [(self.connection_data['host'], self.connection_data['port'])]
        self.connection = self.client.connect(nodes)
        self.is_connected = True

        return self.client, self.connection

    def disconnect(self):
        """
        Close any existing connections.
        """

        if self.is_connected is False:
            return

        self.client.close()
        self.is_connected = False
        return self.is_connected

    def check_connection(self) -> StatusResponse:
        """
        Check connection to the handler.
        Returns:
            HandlerStatusResponse
        """

        response = StatusResponse(False)
        need_to_close = self.is_connected is False

        try:
            self.connect()
            response.success = True
        except Exception as e:
            log.logger.error(f'Error connecting to Apache Ignite!')
            response.error_message = str(e)
        finally:
            if response.success is True and need_to_close:
                self.disconnect()
            if response.success is False and self.is_connected is True:
                self.is_connected = False

        return response

    def native_query(self, query: str) -> StatusResponse:
        """
        Receive raw query and act upon it somehow.
        Args:
            query (str): query in native format
        Returns:
            HandlerResponse
        """

        need_to_close = self.is_connected is False

        client, connection = self.connect()

        try:
            with connection:
                with client.sql(query, include_field_names=True, schema=self.connection_data['schema']) as cursor:
                    result = list(cursor)
                    if result and result[0][0] != 'UPDATED':
                        response = Response(
                            RESPONSE_TYPE.TABLE,
                            data_frame=pd.DataFrame(
                                result[1:],
                                columns=[result[0]]
                            )
                        )
                    else:
                        response = Response(RESPONSE_TYPE.OK)
        except Exception as e:
            log.logger.error(f'Error running query: {query} on Apache Ignite!')
            response = Response(
                RESPONSE_TYPE.ERROR,
                error_message=str(e)
            )

        cursor.close()
        if need_to_close is True:
            self.disconnect()

        return response

    def query(self, query: ASTNode) -> StatusResponse:
        """
        Receive query as AST (abstract syntax tree) and act upon it somehow.
        Args:
            query (ASTNode): sql query represented as AST. May be any kind
                of query: SELECT, INTSERT, DELETE, etc
        Returns:
            HandlerResponse
        """

        # if isinstance(query, ASTNode):
        #     query_str = query.to_string()
        # else:
        #     query_str = str(query)
        #
        # return self.native_query(query_str)
        renderer = SqlalchemyRender('ignite')
        query_str = renderer.get_string(query, with_failback=True)
        return self.native_query(query_str)

    def get_tables(self) -> StatusResponse:
        """
        Return list of entities that will be accessible as tables.
        Returns:
            HandlerResponse
        """

        pass

    def get_columns(self, table_name: str) -> StatusResponse:
        """
        Returns a list of entity columns.
        Args:
            table_name (str): name of one of tables returned by self.get_tables()
        Returns:
            HandlerResponse
        """

        pass