"""The MetadataInventory artifact (spec §10, T-301): tables and columns of a run's scope."""

from typing import Any

from pydantic import BaseModel, Field

SCHEMA_VERSION = 1


class InventoryScope(BaseModel):
    workspace_id: str
    lakehouse_id: str
    schemas: list[str] = Field(default_factory=list)


class InventoryColumn(BaseModel):
    name: str
    data_type: str | None = None
    nullable: bool | None = None
    description: str | None = None


class InventoryError(BaseModel):
    code: str
    message: str


class InventoryTable(BaseModel):
    schema_name: str = Field(alias="schema")
    table_name: str
    description: str | None = None
    columns: list[InventoryColumn] = Field(default_factory=list)
    profile: dict[str, Any] | None = None  # filled by T-302
    errors: list[InventoryError] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class InventoryRunError(BaseModel):
    table: str
    code: str
    message: str


class MetadataInventory(BaseModel):
    schema_version: int = SCHEMA_VERSION
    run_id: str
    version: int
    harvested_at: str
    scope: InventoryScope
    tables: list[InventoryTable] = Field(default_factory=list)
    relationship_evidence: list[dict[str, Any]] = Field(default_factory=list)  # filled by T-303
    errors: list[InventoryRunError] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", by_alias=True)
