"""Shared FastAPI dependencies."""

from functools import lru_cache
from pathlib import Path

from fastapi import Depends

from app.api.obo import get_msal_app, obo_token_provider
from app.api.security import user_token
from app.auth import FABRIC_SCOPE, STORAGE_SCOPE
from app.connectors.fabric_api import FabricApiClient
from app.compiler.requirement_compiler import LlmCall, default_llm
from app.config import PROJECT_ROOT
from app.connectors.fabric_lakehouse import FabricLakehouseConnector
from app.store.base import RunStore
from app.store.factory import get_run_store


@lru_cache(maxsize=1)
def _store() -> RunStore:
    return get_run_store()


def get_store() -> RunStore:
    return _store()


def get_runs_root() -> Path:
    """Where run artifact files (contracts, logs) live. Both stores keep them here."""
    return PROJECT_ROOT / "runs"


def get_llm() -> LlmCall:
    return default_llm()


def get_fabric_client(
    token: str = Depends(user_token), msal_app=Depends(get_msal_app)
) -> FabricApiClient:
    """A Fabric client that calls Fabric as the signed-in user (OBO)."""
    return FabricApiClient(
        token_provider=obo_token_provider(msal_app, token, FABRIC_SCOPE)
    )


def get_connector_factory(
    token: str = Depends(user_token), msal_app=Depends(get_msal_app)
):
    """Builds Lakehouse connectors that read OneLake as the signed-in user."""
    provider = obo_token_provider(msal_app, token, STORAGE_SCOPE)
    return lambda scope: FabricLakehouseConnector.for_scope(
        scope, token_provider=provider
    )
