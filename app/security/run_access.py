"""Run authorization (T-705, NFR-002): who may read or act on a run.

A user may if they created it, or if they can access the workspace the run is scoped to. Access to the
workspace is read from Fabric, as the user (their own workspace list), and cached for 5 minutes, so a
user removed from a workspace loses its runs within 5 minutes. The cache is keyed by tenant, workspace
and user, so nothing one scope learned is used for another.

A run with no `created_by` was created through the CLI, which has no signed-in user; it has no owner to
protect and stays open to any signed-in user. A run with an owner and no scope is the owner's alone.
"""

import time
from collections.abc import Callable
from typing import Any

from app.config import ENTRA_TENANT_ID
from app.workflow.run import Run

TTL_SECONDS = 5 * 60


class RunAccessDenied(Exception):
    """The signed-in user may not read or act on this run."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        super().__init__("You don't have access to this run: it was created by someone else and you can't access its workspace")


class AccessCache:
    def __init__(self, ttl: float = TTL_SECONDS, clock: Callable[[], float] = time.monotonic):
        self.ttl, self.clock = ttl, clock
        self._items: dict[tuple, tuple[float, bool]] = {}

    def get(self, key: tuple) -> bool | None:
        found = self._items.get(key)
        if found is None or self.clock() - found[0] >= self.ttl:
            self._items.pop(key, None)
            return None
        return found[1]

    def set(self, key: tuple, value: bool) -> None:
        self._items[key] = (self.clock(), value)

    def clear(self) -> None:
        self._items.clear()


cache = AccessCache()


def can_access(run: Run, oid: str, upn: str, list_workspaces: Callable[[], list[dict[str, Any]]], access: AccessCache | None = None) -> bool:
    """True if the user created the run, or the run has no owner, or Fabric lists its workspace for them.
    A workspace list that can't be read is a refusal (and isn't cached), never a pass."""
    owner = run.created_by
    if owner is None:
        return True
    if owner.get("oid") == oid or str(owner.get("upn", "")).casefold() == upn.casefold():
        return True
    if run.scope is None:
        return False
    store = access or cache
    workspace = run.scope.workspace_id.casefold()
    key = ((ENTRA_TENANT_ID or "").casefold(), workspace, oid)
    known = store.get(key)
    if known is not None:
        return known
    try:
        allowed = any(str(w.get("id", "")).casefold() == workspace for w in list_workspaces())
    except Exception:
        return False
    store.set(key, allowed)
    return allowed
