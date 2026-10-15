"""Keeps a model's accepted answer per request, so the same inputs give the same stage output.

The key is a hash of the system prompt and the exact user message. The answer is saved only
after the stage has accepted it, so unusable output is never reused.
"""

import hashlib
import json
from pathlib import Path

from app.workflow.harvest_stage import write_json


def request_key(system: str, user: str) -> str:
    return hashlib.sha256(f"{system}\n{user}".encode("utf-8")).hexdigest()


def saved_answer(run_dir: Path, name: str, key: str) -> str | None:
    try:
        saved = json.loads((Path(run_dir) / name).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(saved, dict) and saved.get("key") == key and isinstance(saved.get("response"), str):
        return saved["response"]
    return None


def save_answer(run_dir: Path, name: str, key: str, response: str) -> None:
    write_json(Path(run_dir) / name, {"key": key, "response": response})
