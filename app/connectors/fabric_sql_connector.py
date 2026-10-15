
import pyodbc

from app.auth import SQL_SCOPE, get_token
from app.config import (
    FABRIC_SQL_SERVER,
    FABRIC_SQL_DATABASE,
)


class FabricSQLConnector:
    """Connects to a Fabric SQL endpoint.

    Defaults to the Lakehouse endpoint from FABRIC_SQL_*. Pass `server` and
    `database` to reach another one, such as the control database.
    """

    def __init__(self, server: str | None = None, database: str | None = None):
        self.server = server or FABRIC_SQL_SERVER
        self.database = database or FABRIC_SQL_DATABASE

    def connect(self):
        token = get_token(SQL_SCOPE)

        # SQL Server ODBC expects the access token as UTF-16-LE bytes,
        # prefixed with its 4-byte length.
        token_bytes = token.encode("utf-16-le")
        token_struct = (
            len(token_bytes).to_bytes(4, byteorder="little")
            + token_bytes
        )

        connection_string = (
            "Driver={ODBC Driver 18 for SQL Server};"
            f"Server=tcp:{self.server},1433;"
            f"Database={self.database};"
            "Encrypt=yes;"
            "TrustServerCertificate=no;"
            "Connection Timeout=30;"
        )

        return pyodbc.connect(
            connection_string,
            attrs_before={1256: token_struct},
            timeout=30,
        )

    def test_connection(self) -> None:
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT DB_NAME()")
            row = cursor.fetchone()
            print("Connected successfully.")
            print("Database:", row[0])
