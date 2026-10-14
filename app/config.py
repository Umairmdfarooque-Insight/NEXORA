import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

FABRIC_WORKSPACE_ID = os.getenv("FABRIC_WORKSPACE_ID")
FABRIC_LAKEHOUSE_ID = os.getenv("FABRIC_LAKEHOUSE_ID")
FABRIC_WORKSPACE_NAME = os.getenv("FABRIC_WORKSPACE_NAME")
FABRIC_LAKEHOUSE_NAME = os.getenv("FABRIC_LAKEHOUSE_NAME")
FABRIC_SQL_SERVER = os.getenv("FABRIC_SQL_SERVER")
FABRIC_SQL_DATABASE = os.getenv("FABRIC_SQL_DATABASE")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


def get_required_setting(name: str) -> str:
    value = os.getenv(name)

    if not value or not value.strip():
        raise ValueError(
            f"Missing required configuration: {name}. "
            "Check your .env file."
        )

    return value.strip()


APP_NAME = os.getenv("APP_NAME", "Nexora")
UI_APP_NAME = os.getenv("UI_APP_NAME", "Rayfin")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

AZURE_OPENAI_ENDPOINT = get_required_setting(
    "AZURE_OPENAI_ENDPOINT"
).rstrip("/")

AZURE_OPENAI_DEPLOYMENT = get_required_setting(
    "AZURE_OPENAI_DEPLOYMENT"
)

AZURE_OPENAI_API_KEY = get_required_setting(
    "AZURE_OPENAI_API_KEY"
)