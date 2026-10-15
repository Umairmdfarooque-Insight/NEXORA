"""The compile stage service (T-202): check the run state, run the compile graph, write the
contract version and make the state transition.

The graph (app/graphs/compile.py) only proposes and validates. This service owns the
artifact files, the manifest entry and the transition, as CONTRACTS.md#stage-graphs requires.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from app.compiler.requirement_compiler import LlmCall, compile_requirement
from app.contracts import business_contract as bc
from app.llm.errors import LlmInvalidOutput
from app.store.base import RunStore
from app.workflow.run import ArtifactRef, Run, utc_now
from app.workflow.states import RunState

ARTIFACT = "BusinessContract"
CURRENT = "BusinessContract.yaml"
COMPILE_STATES = (RunState.CREATED, RunState.NEEDS_CLARIFICATION)
_VERSION_FILE = re.compile(r"BusinessContract\.v(\d+)\.yaml$")


class WrongState(Exception):
    def __init__(self, action: str, state: RunState, allowed: tuple[RunState, ...]):
        self.state = state
        self.allowed = allowed
        names = " or ".join(s.value for s in allowed)
        super().__init__(f"{action} is only allowed in {names}, not {state.value}")


def load_current_contract(runs_root: Path, run_id: str) -> bc.BusinessContract | None:
    path = Path(runs_root) / run_id / CURRENT
    if not path.is_file():
        return None
    return bc.load(path)


def open_questions(runs_root: Path, run_id: str) -> list[dict]:
    """Open questions of the run's current contract, for the run detail. Never raises."""
    try:
        contract = load_current_contract(runs_root, run_id)
    except (bc.ContractInvalid, OSError):
        return []
    if contract is None:
        return []
    return [
        q.model_dump(mode="json")
        for q in contract.open_questions
        if q.status is bc.QuestionStatus.OPEN
    ]


def _next_version(contracts_dir: Path, wanted: int) -> int:
    existing = [
        int(m.group(1))
        for p in contracts_dir.glob("BusinessContract.v*.yaml")
        if (m := _VERSION_FILE.search(p.name))
    ]
    return max([wanted, *(n + 1 for n in existing)])


def _write_failure_log(runs_root: Path, run_id: str, attempts: list[dict]) -> None:
    logs = Path(runs_root) / run_id / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    body = {"run_id": run_id, "stage": "compile", "at": utc_now(), "attempts": attempts}
    (logs / f"compile-{stamp}.json").write_text(
        json.dumps(body, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def compile_run(
    store: RunStore,
    runs_root: Path,
    run_id: str,
    actor: str = "system",
    llm: LlmCall | None = None,
) -> tuple[Run, bc.BusinessContract]:
    """Compile the run's prompt into the next contract version.

    State afterwards: NEEDS_CLARIFICATION while a blocking question is open, otherwise
    CREATED. A state that doesn't change adds no history entry.
    """
    run = store.get(run_id)
    if run.state not in COMPILE_STATES:
        raise WrongState("Compiling the requirement", run.state, COMPILE_STATES)

    previous = load_current_contract(runs_root, run_id)
    try:
        contract = compile_requirement(run, previous, llm=llm)
    except LlmInvalidOutput as exc:
        _write_failure_log(runs_root, run_id, exc.attempts)
        raise

    run_dir = Path(runs_root) / run_id
    contracts_dir = run_dir / "contracts"
    version = _next_version(contracts_dir, contract.version)
    if version != contract.version:
        contract = contract.model_copy(update={"version": version})

    digest = bc.save(contract, contracts_dir / f"BusinessContract.v{version}.yaml")
    bc.save(contract, run_dir / CURRENT)

    run.artifacts[ARTIFACT] = ArtifactRef(
        path=CURRENT,
        version=version,
        hash=digest,
        status="draft",
        based_on={},
        updated_at=utc_now(),
    )
    store.save(run)

    blocking = len(bc.open_blocking_questions(contract))
    target = RunState.NEEDS_CLARIFICATION if blocking else RunState.CREATED
    if target is not run.state:
        reason = (
            f"{blocking} blocking question(s) open"
            if blocking
            else "No blocking questions; draft contract ready"
        )
        store.transition(run_id, target, reason, actor)
    return store.get(run_id), contract
