"""ValidationReport.json (spec §10, CONTRACTS.md#validation-report): one entry per validation run.

Written by the model validation stage (T-504); T-505 reads it and sets `classification`.
"""

import hashlib
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 1


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ValidationCheck(_Strict):
    id: str  # G4.REF, G4.REL, G4.DAX, G4.RECON, G4.RLS
    object: str  # "measure:Net Revenue", "relationship:Sales_Product", "model"
    status: Literal["pass", "fail", "warning", "skipped"]
    severity: Literal["error", "warning", "info"]
    code: str | None = None
    message: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    fingerprint: str
    classification: Literal["deterministic", "llm", "user_input"] | None = None  # set by T-505


class ValidationRun(_Strict):
    artifact: str = "SemanticModel"
    artifact_version: int
    artifact_hash: str
    attempt: int
    started_at: str
    passed: bool
    checks: list[ValidationCheck]


class ValidationReport(_Strict):
    schema_version: int = SCHEMA_VERSION
    run_id: str
    runs: list[ValidationRun] = Field(default_factory=list)


def fingerprint(check_id: str, obj: str, code: str | None, message: str) -> str:
    """Identifies a failure across attempts, so repair can tell whether it made progress."""
    return "sha256:" + hashlib.sha256(f"{check_id}|{obj}|{code or ''}|{message}".encode("utf-8")).hexdigest()


def load_report(path: Path, run_id: str) -> ValidationReport:
    path = Path(path)
    if not path.is_file():
        return ValidationReport(run_id=run_id)
    return ValidationReport.model_validate_json(path.read_text(encoding="utf-8"))


def save_report(report: ValidationReport, path: Path) -> dict:
    """Write the report (UTF-8, LF) and return its data."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = report.model_dump(mode="json")
    import json

    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes((json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    os.replace(tmp, path)
    return data
