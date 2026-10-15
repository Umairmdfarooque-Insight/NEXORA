"""Shared FastAPI dependencies."""

from functools import lru_cache

from app.store.base import RunStore
from app.store.factory import get_run_store


@lru_cache(maxsize=1)
def _store() -> RunStore:
    return get_run_store()


def get_store() -> RunStore:
    return _store()
