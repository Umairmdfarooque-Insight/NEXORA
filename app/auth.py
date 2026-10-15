import logging
import os
import threading
from pathlib import Path

from azure.core.credentials import TokenCredential
from azure.core.exceptions import ClientAuthenticationError
from azure.identity import (
    AuthenticationRecord,
    InteractiveBrowserCredential,
    TokenCachePersistenceOptions,
)

STORAGE_SCOPE = "https://storage.azure.com/.default"
SQL_SCOPE = "https://database.windows.net/.default"
FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"

CACHE_NAME = "nexora"

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_credential: TokenCredential | None = None
_cache_warned = False
_record_saved = False


def _is_cache_failure(error: Exception) -> bool:
    """True when the error comes from the encrypted token cache, not from sign-in."""
    if isinstance(error, ClientAuthenticationError):
        return False

    module = type(error).__module__ or ""
    return module.startswith("msal_extensions") or isinstance(
        error, (ImportError, OSError, ValueError)
    )


def _record_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / ".IdentityService" / f"{CACHE_NAME}_auth_record.json"


def _load_record() -> AuthenticationRecord | None:
    """Load the saved account identifiers (no tokens) used to read the cache silently."""
    try:
        return AuthenticationRecord.deserialize(
            _record_path().read_text(encoding="utf-8")
        )
    except (OSError, ValueError, KeyError):
        return None


def _save_record(record: AuthenticationRecord) -> None:
    try:
        path = _record_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(record.serialize(), encoding="utf-8")
    except OSError as error:
        logger.warning("Could not save the sign-in record (%s).", type(error).__name__)


def _build_credential(persistent: bool) -> TokenCredential:
    if persistent:
        record = _load_record()

        return InteractiveBrowserCredential(
            cache_persistence_options=TokenCachePersistenceOptions(name=CACHE_NAME),
            authentication_record=record,
        )

    return InteractiveBrowserCredential()


def get_credential() -> TokenCredential:
    """Return the one process-wide credential, creating it on first use."""
    global _credential

    with _lock:
        if _credential is None:
            _credential = _build_credential(persistent=True)

        return _credential


def _fall_back_to_memory_cache(error: Exception) -> TokenCredential:
    global _credential, _cache_warned, _record_saved

    with _lock:
        if not _cache_warned:
            logger.warning(
                "Encrypted token cache is unavailable (%s); "
                "using an in-memory cache for this process.",
                type(error).__name__,
            )
            _cache_warned = True

        _credential = _build_credential(persistent=False)
        _record_saved = True

        return _credential


def _request_token(credential: TokenCredential, scope: str) -> str:
    global _record_saved

    try:
        # Without a saved record the credential can't read the cache silently, so
        # the first sign-in captures one (account identifiers only, no tokens).
        if isinstance(credential, InteractiveBrowserCredential) and not _record_saved:
            if _load_record() is None:
                _save_record(credential.authenticate(scopes=[scope]))

            _record_saved = True

        return credential.get_token(scope).token
    except ClientAuthenticationError:
        raise ClientAuthenticationError(
            "Azure sign-in failed or was cancelled. "
            "Run the command again and complete the browser sign-in."
        ) from None


def get_token(scope: str) -> str:
    """Return an access token for `scope`, refreshing it silently when expired."""
    try:
        return _request_token(get_credential(), scope)
    except Exception as error:
        if not _is_cache_failure(error):
            raise

        return _request_token(_fall_back_to_memory_cache(error), scope)
