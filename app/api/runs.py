"""Run endpoints. Handlers only call the RunStore and shape the response."""

from pathlib import Path

from fastapi import APIRouter, Depends, Query

from app.api.deps import (
    get_connector_factory,
    get_fabric_client,
    get_llm,
    get_relationship_llm,
    get_runs_root,
    get_sql_connector_factory,
    get_store,
)
from app.api.schemas import (
    AnalyzeRelationshipsRequest,
    AnalyzeRelationshipsResponse,
    AnswerRequest,
    ApprovalRequest,
    ApprovalResponse,
    ArtifactItem,
    CompileResponse,
    CreateRunRequest,
    DataGapRequest,
    DismissRequest,
    ExceptionRequest,
    ExceptionResponse,
    HarvestRequest,
    HarvestResponse,
    HarvestSummary,
    KpiEditRequest,
    KpiEditResponse,
    ProfileRequest,
    ProfileResponse,
    QuestionResponse,
    RunDetail,
    RunList,
    RunSummary,
    ScopeRequest,
)
from app.api.security import Principal, current_user
from app.connectors.fabric_api import FabricApiClient
from app.store.base import RunStore
from app.workflow.approval import ApprovalRecord, check_g1, list_approvals, perform
from app.workflow.clarification import (
    NotFound,
    answer_question,
    dismiss_question,
    edit_kpi,
)
from app.workflow.compile_stage import compile_run, current_contract, open_questions
from app.contracts.metadata_inventory import MetadataInventory
from app.workflow.gates import GateResult
from app.workflow.inventory_review import (
    add_exception,
    check_g2,
    list_data_gaps,
    raise_data_gap,
)
from app.workflow.harvest_stage import ARTIFACT as INVENTORY, harvest_run, load_inventory, summary
from app.contracts.metadata_inventory import RelationshipEvidence
from app.discovery.relationship_candidates import Candidate
from app.workflow.profile_stage import profile_run, summarize
from app.workflow.relationship_stage import analyze_run, list_relationships
from app.workflow.relationship_stage import summarize as summarize_relationships
from app.workflow.scope import bind_scope
from app.workflow.states import RunState

router = APIRouter(
    prefix="/runs", tags=["runs"], dependencies=[Depends(current_user)]
)

def detail(run, runs_root: Path, warnings: list[str] | None = None) -> RunDetail:
    """The run with its open questions and current contract."""
    return RunDetail.from_run(
        run,
        warnings,
        open_questions=open_questions(runs_root, run.run_id),
        contract=current_contract(runs_root, run.run_id),
        data_gaps=list_data_gaps(runs_root, run.run_id),
    )


# The store has no count query yet, so total is taken from an unbounded list.
ALL_RUNS = 1_000_000


@router.post("", status_code=201, response_model=RunDetail)
def create_run(
    body: CreateRunRequest,
    store: RunStore = Depends(get_store),
    user: Principal = Depends(current_user),
):
    run = store.create(
        body.prompt,
        body.subject_area,
        body.desired_outputs,
        body.constraints,
        created_by=user.model_dump(),
    )
    return RunDetail.from_run(run)


@router.get("", response_model=RunList)
def list_runs(
    state: RunState | None = None,
    limit: int = Query(50, ge=1, le=200),
    store: RunStore = Depends(get_store),
):
    runs = store.list(state, limit=ALL_RUNS)
    return RunList(
        items=[RunSummary.from_run(r) for r in runs[:limit]], total=len(runs)
    )


@router.get("/{run_id}", response_model=RunDetail)
def get_run(
    run_id: str,
    store: RunStore = Depends(get_store),
    runs_root: Path = Depends(get_runs_root),
):
    run = store.get(run_id)
    return detail(run, runs_root)


@router.post("/{run_id}/compile", response_model=CompileResponse)
def compile_requirement(
    run_id: str,
    store: RunStore = Depends(get_store),
    runs_root: Path = Depends(get_runs_root),
    llm=Depends(get_llm),
    user: Principal = Depends(current_user),
):
    run, contract = compile_run(store, runs_root, run_id, actor=user.upn, llm=llm)
    questions = open_questions(runs_root, run_id)
    return CompileResponse(
        run=detail(run, runs_root),
        contract=contract,
        blocking_questions=sum(1 for q in questions if q["blocking"]),
    )


def _question_response(run, contract, runs_root: Path) -> QuestionResponse:
    return QuestionResponse(
        run=detail(run, runs_root),
        contract=contract,
    )


@router.post("/{run_id}/questions/{qid}/answer", response_model=QuestionResponse)
def answer(
    run_id: str,
    qid: str,
    body: AnswerRequest,
    store: RunStore = Depends(get_store),
    runs_root: Path = Depends(get_runs_root),
    llm=Depends(get_llm),
    user: Principal = Depends(current_user),
):
    run, contract = answer_question(
        store, runs_root, run_id, qid, body.answer, actor=user.upn, llm=llm
    )
    return _question_response(run, contract, runs_root)


@router.post("/{run_id}/questions/{qid}/dismiss", response_model=QuestionResponse)
def dismiss(
    run_id: str,
    qid: str,
    body: DismissRequest,
    store: RunStore = Depends(get_store),
    runs_root: Path = Depends(get_runs_root),
):
    run, contract = dismiss_question(store, runs_root, run_id, qid, body.reason)
    return _question_response(run, contract, runs_root)


@router.put("/{run_id}/contract/kpis/{kpi_name}", response_model=KpiEditResponse)
def update_kpi(
    run_id: str,
    kpi_name: str,
    body: KpiEditRequest,
    store: RunStore = Depends(get_store),
    runs_root: Path = Depends(get_runs_root),
):
    changes = body.model_dump(exclude={"expected_hash"}, exclude_unset=True, mode="json")
    contract = edit_kpi(store, runs_root, run_id, kpi_name, changes, body.expected_hash)
    return KpiEditResponse(contract=contract)


@router.post("/{run_id}/gates/{gate}/check", response_model=GateResult)
def check_gate(
    run_id: str,
    gate: str,
    store: RunStore = Depends(get_store),
    runs_root: Path = Depends(get_runs_root),
):
    if gate == "G1":
        return check_g1(store, runs_root, run_id)
    if gate == "G2":
        return check_g2(store, runs_root, run_id)
    raise NotFound(f"No gate {gate!r}; only G1 and G2 are available")


@router.post("/{run_id}/approvals", response_model=ApprovalResponse)
def approve(
    run_id: str,
    body: ApprovalRequest,
    store: RunStore = Depends(get_store),
    runs_root: Path = Depends(get_runs_root),
    llm=Depends(get_llm),
    user: Principal = Depends(current_user),
):
    outcome = perform(
        store,
        runs_root,
        run_id,
        body.artifact,
        body.action,
        {"oid": user.oid, "upn": user.upn},
        body.expected_hash,
        comment=body.comment,
        edits=body.edits.model_dump(exclude_unset=True, mode="json") if body.edits else None,
        llm=llm,
    )
    return ApprovalResponse(
        approval=outcome.approval,
        run=detail(outcome.run, runs_root),
        gate_result=outcome.gate_result,
        explanation=outcome.explanation,
    )


@router.get("/{run_id}/approvals", response_model=list[ApprovalRecord])
def get_approvals(
    run_id: str,
    store: RunStore = Depends(get_store),
    runs_root: Path = Depends(get_runs_root),
):
    return list_approvals(store, runs_root, run_id)


@router.post("/{run_id}/exceptions", status_code=201, response_model=ExceptionResponse)
def approve_exception(
    run_id: str,
    body: ExceptionRequest,
    store: RunStore = Depends(get_store),
    runs_root: Path = Depends(get_runs_root),
    user: Principal = Depends(current_user),
):
    record = add_exception(
        store, runs_root, run_id, {"oid": user.oid, "upn": user.upn}, body.table, body.rationale
    )
    return ExceptionResponse(
        exception_id=record.approval_id,
        table=record.artifact.split(":", 1)[1],
        approved_by=record.user["upn"],
        at=record.at,
    )


@router.post("/{run_id}/data-gaps", response_model=RunDetail)
def raise_gap(
    run_id: str,
    body: DataGapRequest,
    store: RunStore = Depends(get_store),
    runs_root: Path = Depends(get_runs_root),
    user: Principal = Depends(current_user),
):
    run = raise_data_gap(store, runs_root, run_id, body.description, user.upn)
    return detail(run, runs_root)


@router.put("/{run_id}/scope", response_model=RunDetail)
def set_scope(
    run_id: str,
    body: ScopeRequest,
    store: RunStore = Depends(get_store),
    runs_root: Path = Depends(get_runs_root),
    fabric: FabricApiClient = Depends(get_fabric_client),
    connector_for_scope=Depends(get_connector_factory),
):
    run, warnings = bind_scope(
        store,
        fabric,
        connector_for_scope,
        run_id,
        body.workspace_id,
        body.lakehouse_id,
        body.schemas,
    )
    return detail(run, runs_root, warnings)


@router.post("/{run_id}/harvest", response_model=HarvestResponse)
def harvest(
    run_id: str,
    body: HarvestRequest | None = None,
    store: RunStore = Depends(get_store),
    runs_root: Path = Depends(get_runs_root),
    connector_for_scope=Depends(get_connector_factory),
    user: Principal = Depends(current_user),
):
    run, inventory = harvest_run(
        store,
        runs_root,
        run_id,
        connector_for_scope,
        schemas=body.schemas if body else None,
        actor=user.upn,
    )
    ref = run.artifacts[INVENTORY]
    return HarvestResponse(
        summary=HarvestSummary(**summary(inventory)),
        artifact=ArtifactItem(
            name=INVENTORY,
            version=ref.version,
            path=ref.path,
            hash=ref.hash,
            status=ref.status,
            updated_at=ref.updated_at,
        ),
        warnings=inventory.warnings,
    )


@router.post("/{run_id}/profile", response_model=ProfileResponse)
def profile(
    run_id: str,
    body: ProfileRequest | None = None,
    store: RunStore = Depends(get_store),
    runs_root: Path = Depends(get_runs_root),
    sql_connector_for_scope=Depends(get_sql_connector_factory),
):
    profiles = profile_run(
        store,
        runs_root,
        run_id,
        sql_connector_for_scope,
        tables=body.tables if body else None,
    )
    return ProfileResponse(**summarize(profiles))


@router.post("/{run_id}/relationships/analyze", response_model=AnalyzeRelationshipsResponse)
def analyze_relationships(
    run_id: str,
    body: AnalyzeRelationshipsRequest | None = None,
    store: RunStore = Depends(get_store),
    runs_root: Path = Depends(get_runs_root),
    sql_connector_for_scope=Depends(get_sql_connector_factory),
    llm=Depends(get_relationship_llm),
):
    extra = [
        Candidate("user", c.from_.table, c.from_.column, c.to.table, c.to.column)
        for c in (body.candidates if body else [])
    ]
    evidence, warnings = analyze_run(
        store, runs_root, run_id, sql_connector_for_scope, llm=llm, extra=extra
    )
    return AnalyzeRelationshipsResponse(**summarize_relationships(evidence), warnings=warnings)


@router.get("/{run_id}/relationships", response_model=list[RelationshipEvidence])
def get_relationships(
    run_id: str,
    store: RunStore = Depends(get_store),
    runs_root: Path = Depends(get_runs_root),
):
    store.get(run_id)
    return list_relationships(runs_root, run_id)


@router.get("/{run_id}/inventory", response_model=MetadataInventory, response_model_by_alias=True)
def get_inventory(
    run_id: str,
    store: RunStore = Depends(get_store),
    runs_root: Path = Depends(get_runs_root),
):
    store.get(run_id)
    return load_inventory(runs_root, run_id)


@router.get("/{run_id}/artifacts", response_model=list[ArtifactItem])
def list_artifacts(run_id: str, store: RunStore = Depends(get_store)):
    run = store.get(run_id)
    return [
        ArtifactItem(
            name=name,
            version=a.version,
            path=a.path,
            hash=a.hash,
            status=a.status,
            updated_at=a.updated_at,
        )
        for name, a in run.artifacts.items()
    ]
