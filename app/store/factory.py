"""Pick the RunStore from the RUN_STORE setting ("file" or "fabric_sql")."""

from app.config import (
    get_optional_setting,
    get_required_setting,
)
from app.store.base import RunStore


def get_run_store() -> RunStore:
    kind = (get_optional_setting("RUN_STORE", "file") or "file").lower()

    if kind == "file":
        from app.store.file_store import FileRunStore

        return FileRunStore()

    if kind == "fabric_sql":
        from app.store.sql_store import SqlRunStore

        return SqlRunStore(
            get_required_setting("FABRIC_CONTROL_DB_SERVER"),
            get_required_setting("FABRIC_CONTROL_DB_NAME"),
        )

    raise ValueError(
        f"Invalid RUN_STORE: {kind!r}. Valid values: file, fabric_sql"
    )
