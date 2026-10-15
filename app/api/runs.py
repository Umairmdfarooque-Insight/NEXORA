"""Run endpoints. Handlers only call the RunStore and shape the response."""

from pathlib import Path

from fastapi import APIRouter, Depends, Query

from app.api.deps import (
    get_connector_factory,
    get_fabric_client,
    get_llm,
    get_runs_root,
    get_store,
)
from app.api.schemas import (
    AnswerRequest,
    ArtifactItem,
    CompileResponse,
    CreateRunRequest,
    DismissRequest,
    KpiEditRequest,
    KpiEditResponse,
    QuestionResponse,
    RunDetail,
    RunList,
    RunSummary,
    ScopeRequest,
)
from app.api.security import Principal, current_user
from app.connectors.fabric_api import FabricApiClient
from app.store.base import RunStore
from app.workflow.clarification import answer_question, dismiss_question, edit_kpi
from app.workflow.compile_stage import compile_run, open_questions
from app.workflow.scope import bind_scope
from app.workflow.states import RunState

router = APIRouter(
    prefix="/runs", tags=["runs"], dependencies=[Depends(current_user)]
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
    return RunDetail.from_run(run, open_questions=open_questions(runs_root, run_id))


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
        run=RunDetail.from_run(run, open_questions=questions),
        contract=contract,
        blocking_questions=sum(1 for q in questions if q["blocking"]),
    )


def _question_response(run, contract, runs_root: Path) -> QuestionResponse:
    return QuestionResponse(
        run=RunDetail.from_run(run, open_questions=open_questions(runs_root, run.run_id)),
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


@router.put("/{run_id}/scope", response_model=RunDetail)
def set_scope(
    run_id: str,
    body: ScopeRequest,
    store: RunStore = Depends(get_store),
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
    return RunDetail.from_run(run, warnings)


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
