import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Load .env once, from the project root, so the result doesn't depend on the
# working directory. Values already set in the shell take precedence.
load_dotenv(PROJECT_ROOT / ".env", override=False)

from app.security.secrets import SecretsUnavailable, load_secret  # noqa: E402  (after .env is loaded)


def get_required_setting(name: str) -> str:
    value = os.getenv(name)

    if not value or not value.strip():
        raise ValueError(
            f"Missing required configuration: {name}. "
            "Check your .env file."
        )

    return value.strip()


def get_optional_setting(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)

    if not value or not value.strip():
        return default

    return value.strip()


APP_NAME = get_optional_setting("APP_NAME", "Nexora")
UI_APP_NAME = get_optional_setting("UI_APP_NAME", "Rayfin")
ENVIRONMENT = get_optional_setting("ENVIRONMENT", "development")

AZURE_OPENAI_ENDPOINT = get_required_setting(
    "AZURE_OPENAI_ENDPOINT"
).rstrip("/")

AZURE_OPENAI_DEPLOYMENT = get_required_setting(
    "AZURE_OPENAI_DEPLOYMENT"
)

# Secrets come from Azure Key Vault when KEY_VAULT_URL is set (T-705), from the environment otherwise.
# An unreachable vault stops the process here, with a message that names KEY_VAULT_URL.
try:
    AZURE_OPENAI_API_KEY = load_secret("AZURE_OPENAI_API_KEY", "azure-openai-api-key")
    ENTRA_API_CLIENT_SECRET = load_secret("ENTRA_API_CLIENT_SECRET", "entra-api-client-secret", required=False)
except SecretsUnavailable as _error:
    raise ValueError(f"CONFIG_ERROR: {_error}") from None

FABRIC_WORKSPACE_ID = get_optional_setting("FABRIC_WORKSPACE_ID")
FABRIC_LAKEHOUSE_ID = get_optional_setting("FABRIC_LAKEHOUSE_ID")
FABRIC_WORKSPACE_NAME = get_optional_setting("FABRIC_WORKSPACE_NAME")
FABRIC_LAKEHOUSE_NAME = get_optional_setting("FABRIC_LAKEHOUSE_NAME")
FABRIC_SQL_SERVER = get_optional_setting("FABRIC_SQL_SERVER")
FABRIC_SQL_DATABASE = get_optional_setting("FABRIC_SQL_DATABASE")

# Entra ID sign-in for the API (T-105). Optional at import so scripts and the
# CLI still run; the API refuses every protected request until they are set.
ENTRA_TENANT_ID = get_optional_setting("ENTRA_TENANT_ID")
ENTRA_API_CLIENT_ID = get_optional_setting("ENTRA_API_CLIENT_ID")
