"""Shared FastAPI dependencies."""

from functools import lru_cache

from app.connectors.fabric_api import FabricApiClient
from app.connectors.fabric_lakehouse import FabricLakehouseConnector
from app.store.base import RunStore
from app.store.factory import get_run_store


@lru_cache(maxsize=1)
def _store() -> RunStore:
    return get_run_store()


def get_store() -> RunStore:
    return _store()


def get_fabric_client() -> FabricApiClient:
    return FabricApiClient()


def get_connector_factory():
    return FabricLakehouseConnector.for_scope
