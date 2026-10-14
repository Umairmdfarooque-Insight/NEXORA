
from urllib.parse import quote

import requests
from azure.identity import InteractiveBrowserCredential

from app.config import (
    FABRIC_WORKSPACE_ID,
    FABRIC_LAKEHOUSE_ID,
    FABRIC_LAKEHOUSE_NAME,
)

ONELAKE_TABLE_API = "https://onelake.table.fabric.microsoft.com/delta"


class FabricLakehouseConnector:
    def __init__(self) -> None:
        self.credential = InteractiveBrowserCredential()

    def _get_headers(self) -> dict:
        token = self.credential.get_token(
            "https://storage.azure.com/.default"
        ).token

        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    @property
    def lakehouse_path(self) -> str:
        return (
            f"{quote(FABRIC_WORKSPACE_ID, safe='')}/"
            f"{quote(FABRIC_LAKEHOUSE_ID, safe='')}"
        )

    @property
    def catalog_name(self) -> str:
        return f"{FABRIC_LAKEHOUSE_NAME}.Lakehouse"

    def list_schemas(self) -> list[dict]:
        url = (
            f"{ONELAKE_TABLE_API}/{self.lakehouse_path}/"
            "api/2.1/unity-catalog/schemas"
        )

        response = requests.get(
            url,
            headers=self._get_headers(),
            params={"catalog_name": self.catalog_name},
            timeout=30,
        )

        # Diagnostic output to identify the API error
        print("\n--- SCHEMA DISCOVERY DEBUG ---")
        print("Request URL:", response.url)
        print("Status:", response.status_code)
        print("Response:", response.text)
        print("--- END DEBUG ---\n")

        response.raise_for_status()

        return response.json().get("schemas", [])


    def list_tables(self, schema_name: str) -> list[dict]:
        url = (
            f"{ONELAKE_TABLE_API}/{self.lakehouse_path}/"
            "api/2.1/unity-catalog/tables"
        )

        response = requests.get(
            url,
            headers=self._get_headers(),
            params={
                "catalog_name": self.catalog_name,
                "schema_name": schema_name,
            },
            timeout=30,
        )

        print(f"\n--- TABLE DISCOVERY DEBUG: {schema_name} ---")
        print("Request URL:", response.url)
        print("Status:", response.status_code)
        print("Response:", response.text)
        print("--- END DEBUG ---\n")

        response.raise_for_status()

        return response.json().get("tables", [])

    def get_table_metadata(
        self, schema_name: str, table_name: str
    ) -> dict:
        full_table_name = (
            f"{self.catalog_name}.{schema_name}.{table_name}"
        )

        url = (
            f"{ONELAKE_TABLE_API}/{self.lakehouse_path}/"
            "api/2.1/unity-catalog/tables/"
            f"{quote(full_table_name, safe='')}"
        )

        response = requests.get(
            url,
            headers=self._get_headers(),
            timeout=30,
        )

        response.raise_for_status()

        return response.json()
    
    def discover_schema_metadata(self) -> list[dict]:
        """Discover tables and columns from the saleslt schema."""
        schema_name = "saleslt"
        tables = self.list_tables(schema_name)
        discovered_tables = []

        for table in tables:
            table_name = table["name"]

            metadata = self.get_table_metadata(
                schema_name,
                table_name,
            )

            columns = [
                {
                    "name": column["name"],
                    "data_type": column.get("type_name"),
                    "nullable": column.get("nullable"),
                }
                for column in metadata.get("columns", [])
            ]

            discovered_tables.append(
                {
                    "schema": schema_name,
                    "table_name": table_name,
                    "column_count": len(columns),
                    "columns": columns,
                }
            )

        return discovered_tables
