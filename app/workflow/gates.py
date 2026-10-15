"""Gate results (CONTRACTS.md#gate-result) and the automated checks of Gate G1.

Checks are deterministic code, never an LLM. A gate passes only when no check failed.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.contracts import business_contract as bc
from app.workflow.run import utc_now

REQUIRED_KPI_FIELDS = ("formula_intent", "grain", "currency")


class GateCheck(BaseModel):
    id: str
    description: str
    status: Literal["pass", "fail", "warning"]
    evidence: dict[str, Any] = Field(default_factory=dict)


class GateResult(BaseModel):
    gate: str
    artifact: str
    artifact_hash: str
    passed: bool
    checked_at: str
    checks: list[GateCheck]


def _check(id_: str, description: str, ok: bool, evidence: dict | None = None, failed: str = "fail") -> GateCheck:
    return GateCheck(
        id=id_, description=description, status="pass" if ok else failed, evidence=evidence or {}
    )


def run_g1(contract: bc.BusinessContract, artifact_hash: str) -> GateResult:
    """Gate G1 (spec §12): is the BusinessContract ready for the business owner's approval?"""
    # G1.1 re-validates the contract exactly as saved, so a hand-edited file can't pass.
    _, issues = bc.check(contract.model_dump(mode="json"))
    blocking = [q.id for q in bc.open_blocking_questions(contract)]
    missing = {
        kpi.name: [f for f in REQUIRED_KPI_FIELDS if not (getattr(kpi, f) or "").strip()]
        for kpi in contract.kpis
    }
    missing = {name: fields for name, fields in missing.items() if fields}
    gaps = [k.name for k in contract.kpis if k.status is bc.KpiStatus.DATA_GAP]
    assessed = {f.kpi.strip().lower() for f in contract.feasibility}
    unassessed = [k.name for k in contract.kpis if k.name.strip().lower() not in assessed]

    checks = [
        _check("G1.1", "The contract passes schema validation", not issues, {"issues": issues}),
        _check("G1.2", "No blocking question is open", not blocking, {"open_blocking": blocking}),
        _check(
            "G1.3",
            "Every KPI has formula_intent, grain and currency",
            bool(contract.kpis) and not missing,
            {"missing": missing} if missing else ({} if contract.kpis else {"reason": "no KPI defined"}),
        ),
        _check("G1.4", "No KPI has status data_gap", not gaps, {"data_gap": gaps}),
    ]
    if not contract.feasibility:
        # T-402 fills the flags. Until then they are simply not assessed yet.
        checks.append(
            GateCheck(
                id="G1.5",
                description="Feasibility flags are present",
                status="warning",
                evidence={"reason": "not yet assessed"},
            )
        )
    else:
        checks.append(
            _check(
                "G1.5",
                "Feasibility flags are present",
                not unassessed,
                {"not_assessed": unassessed},
            )
        )
    return GateResult(
        gate="G1",
        artifact="BusinessContract",
        artifact_hash=artifact_hash,
        passed=not any(c.status == "fail" for c in checks),
        checked_at=utc_now(),
        checks=checks,
    )


def save_gate_result(runs_root: Path, run_id: str, result: GateResult) -> str:
    """Write runs/<id>/gates/<gate>-<timestamp>.json. Returns the path relative to the run."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    relative = f"gates/{result.gate}-{stamp}.json"
    target = Path(runs_root) / run_id / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes((json.dumps(result.model_dump(mode="json"), indent=2) + "\n").encode("utf-8"))
    return relative
