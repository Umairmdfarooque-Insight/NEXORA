"""The model validation stage (T-504, Gate G4): deploy the current TMDL version to the sandbox,
refresh it, run the G4 checks and record them in ValidationReport.json.

A plain function, deterministic apart from the reconciliation SQL (see `model/recon_sql.py`). If
any check fails the run moves MODEL_GENERATING -> MODEL_FAILED; if all pass it stays in
MODEL_GENERATING, awaiting the review of T-507. Source data is only read, and the only writes go to
the sandbox model. A refresh or deployment that Fabric rejects is recorded as a failed G4.DAX check
and the checks that need the deployed model are marked skipped; anything else that goes wrong
(access denied, throttling, timeouts) is an upstream error and changes nothing.
"""

from pathlib import Path
from typing import Any

from app.compiler.critical_terms import ConfigError
from app.connectors.powerbi_api import PowerBiClient, RefreshFailed
from app.contracts.model_plan import ModelSpec, load_yaml
from app.contracts.validation_report import ValidationRun, load_report, save_report
from app.deploy.fabric_items import FabricItemsClient, FabricOperationFailed, get_sandbox_workspace_id
from app.model.recon_sql import LlmCall, ReconSql, propose_recon_sql
from app.model.tmdl_reader import read_model
from app.model.validation_config import load_tolerance
from app.model.validators import (
    Context,
    check,
    check_dax,
    check_reconciliation,
    check_references,
    check_relationships,
    check_rls,
    skipped,
)
from app.store.base import RunStore
from app.workflow.clarification import NotFound
from app.workflow.compile_stage import WrongState, load_current_contract
from app.workflow.harvest_stage import ScopeMissing, canonical_hash, load_inventory
from app.workflow.llm_cache import CachedLlm, read_answers, write_answers
from app.workflow.model_stage import TMDL_ARTIFACT, folder_hash
from app.workflow.plan_stage import MODEL_FILE
from app.workflow.run import ArtifactRef, Run, utc_now
from app.workflow.states import RunState

REPORT_ARTIFACT = "ValidationReport"
REPORT_FILE = "ValidationReport.json"
CACHE = "recon_suggestions.json"
VALIDATE_STATES = (RunState.MODEL_GENERATING,)


def validate_model(
    store: RunStore,
    runs_root: Path,
    run_id: str,
    *,
    items_client: FabricItemsClient,
    pbi: PowerBiClient,
    sql_connector_factory: Any,
    recon_llm: LlmCall,
    user_upn: str | None = None,
    actor: str = "system",
) -> tuple[ValidationRun, Run]:
    """`POST /runs/{id}/model/validate`: returns this validation run's entry and the run."""
    run = store.get(run_id)
    if run.state not in VALIDATE_STATES:
        raise WrongState("Validating the model", run.state, VALIDATE_STATES)
    tmdl_ref = run.artifacts.get(TMDL_ARTIFACT)
    run_dir = Path(runs_root) / run_id
    if tmdl_ref is None or not (run_dir / tmdl_ref.path).is_dir():
        raise NotFound("The model hasn't been generated yet: POST /runs/{id}/model/generate first")
    if run.scope is None:
        raise ScopeMissing()
    if run.scope.sql_endpoint is None:
        raise ScopeMissing("The run's Lakehouse has no SQL endpoint, so the model can't be reconciled.")
    workspace_id = get_sandbox_workspace_id()
    if not workspace_id:
        raise ConfigError("SANDBOX_WORKSPACE_ID is not set. Models are only validated in the sandbox workspace.")
    tolerance = load_tolerance()  # CONFIG_ERROR before anything is deployed
    contract = load_current_contract(runs_root, run_id)
    if contract is None:
        raise NotFound("The run has no business contract yet")
    inventory = load_inventory(runs_root, run_id)
    spec = load_yaml(ModelSpec, run_dir / MODEL_FILE)

    folder = run_dir / tmdl_ref.path
    digest = folder_hash(folder)
    started = utc_now()
    tmdl = read_model(folder)

    cache = read_answers(run_dir, CACHE)
    accepted: dict[str, str] = {}
    memo: dict[str, ReconSql] = {}

    def recon_for(kpi) -> ReconSql:
        if kpi.name not in memo:
            cached = CachedLlm(recon_llm, cache)
            memo[kpi.name] = propose_recon_sql(kpi, spec, inventory, cached)
            accepted[cached.last_key] = cached.last_raw
        return memo[kpi.name]

    ctx = Context(
        spec=spec, contract=contract, tmdl=tmdl, tolerance=tolerance, workspace_id=workspace_id,
        dataset_id="", pbi=pbi, sql_connector=sql_connector_factory(run.scope), recon_for=recon_for, user_upn=user_upn,
    )

    checks = []
    if digest != tmdl_ref.hash:
        checks.append(check("G4.REF", "model", "warning", f"The TMDL files differ from generated version {tmdl_ref.version}: the files as they are now were validated", "FILES_CHANGED"))
    checks += check_references(ctx)

    failure = None
    deployed: dict | None = None
    try:
        deployed = items_client.upsert_semantic_model(workspace_id, f"Nexora_{run_id[:8]}", folder)
        ctx.dataset_id = deployed["item_id"]
        pbi.refresh(workspace_id, ctx.dataset_id)
    except RefreshFailed as exc:
        failure = ("REFRESH_FAILED", f"The refresh failed: {exc}")
    except FabricOperationFailed as exc:
        failure = ("DEPLOY_FAILED", f"Fabric rejected the model: {exc}")

    if failure:
        code, message = failure
        evidence = {"workspace_id": workspace_id, "item": deployed}
        checks.append(check("G4.DAX", "model", "fail", message, code, evidence))
        for id_ in ("G4.REL", "G4.RECON", "G4.RLS"):
            checks.append(skipped(id_, "model", message))
    else:
        checks += check_dax(ctx)
        with ctx.sql_connector.connect() as connection:
            checks += check_relationships(ctx, connection)
            checks += check_reconciliation(ctx, connection)
        checks += check_rls(ctx)

    report = load_report(run_dir / REPORT_FILE, run_id)
    entry = ValidationRun(
        artifact_version=tmdl_ref.version,
        artifact_hash=digest,
        attempt=len(report.runs) + 1,
        started_at=started,
        passed=not any(c.status == "fail" for c in checks),
        checks=checks,
    )
    report.runs.append(entry)
    data = save_report(report, run_dir / REPORT_FILE)
    if accepted:
        write_answers(run_dir, CACHE, {**cache, **accepted})

    run = store.get(run_id)
    run.artifacts[REPORT_ARTIFACT] = ArtifactRef(
        path=REPORT_FILE,
        version=entry.attempt,
        hash=canonical_hash(data),
        status="passed" if entry.passed else "failed",
        based_on={TMDL_ARTIFACT: digest},
        updated_at=utc_now(),
    )
    store.save(run)
    if not entry.passed:
        failed = sum(1 for c in checks if c.status == "fail")
        run = store.transition(run_id, RunState.MODEL_FAILED, f"Model validation failed: {failed} check(s)", actor)
    return entry, run
