"""The one shared model client (CONTRACTS.md#stage-graphs, rule 5).

Every model call in the app, stage graph nodes included, goes through `client.responses.create`, so two
things can't be skipped (T-705):
- the payload guard (`app/security/llm_guard.py`) checks what is about to be sent and refuses row-like
  data before any request is made;
- a `401` (a rotated key) re-reads the key from Key Vault and retries once.

LangSmith tracing is refused when this module loads, because it would send prompts outside the tenant.
"""

import openai
from openai import OpenAI

from app.config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_DEPLOYMENT,
    AZURE_OPENAI_ENDPOINT,
)
from app.security import secrets
from app.security.llm_guard import check_payload
from app.security.startup import assert_no_external_tracing

assert_no_external_tracing()

KEY_SECRET = "azure-openai-api-key"
_BASE_URL = f"{AZURE_OPENAI_ENDPOINT.rstrip('/')}/openai/v1/"
_state: dict = {"key": AZURE_OPENAI_API_KEY, "raw": None}


def _raw() -> OpenAI:
    if _state["raw"] is None:
        _state["raw"] = OpenAI(api_key=_state["key"], base_url=_BASE_URL)
    return _state["raw"]


def _reread_key() -> bool:
    """Re-read the key from Key Vault after a 401. False if there is no vault (nothing to re-read)."""
    fresh = secrets.refresh_secret(KEY_SECRET)
    if fresh is None:
        return False
    _state["key"], _state["raw"] = fresh, None
    return True


class _Responses:
    def create(self, **kwargs):
        # check first: a rejected payload sends nothing
        check_payload({"instructions": kwargs.get("instructions") or "", "input": kwargs.get("input") or ""})
        try:
            return _raw().responses.create(**kwargs)
        except openai.AuthenticationError:
            if not _reread_key():
                raise
            return _raw().responses.create(**kwargs)  # once


class GuardedClient:
    def __init__(self) -> None:
        self.responses = _Responses()


client = GuardedClient()


def ask_rayfin(prompt: str) -> str:
    response = client.responses.create(
        model=AZURE_OPENAI_DEPLOYMENT,
        instructions=(
        "You are Nexora, the AI engine behind the Rayfin user interface. "
        "You help users automate data engineering and analytics workflows "
        "for Microsoft Fabric. Be accurate, structured, and explicit "
        "about assumptions."
        ),
        input=prompt,
    )

    if not response.output_text:
        raise RuntimeError("The AI deployment returned an empty response.")

    return response.output_text
