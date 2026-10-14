
import pyodbc

from azure.identity import InteractiveBrowserCredential
from app.config import (
    FABRIC_SQL_SERVER,
    FABRIC_SQL_DATABASE,
)


class FabricSQLConnector:
    def __init__(self) -> None:
        self.credential = InteractiveBrowserCredential()

    def connect(self):
        token = self.credential.get_token(
            "https://database.windows.net/.default"
        ).token

        # SQL Server ODBC expects the access token as UTF-16-LE bytes,
        # prefixed with its 4-byte length.
        token_bytes = token.encode("utf-16-le")
        token_struct = (
            len(token_bytes).to_bytes(4, byteorder="little")
            + token_bytes
        )

        connection_string = (
            "Driver={ODBC Driver 18 for SQL Server};"
            f"Server=tcp:{FABRIC_SQL_SERVER},1433;"
            f"Database={FABRIC_SQL_DATABASE};"
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
