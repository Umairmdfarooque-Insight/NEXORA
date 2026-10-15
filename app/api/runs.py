"""Run endpoints. Handlers only call the RunStore and shape the response."""

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_connector_factory, get_fabric_client, get_store
from app.api.schemas import (
    ArtifactItem,
    CreateRunRequest,
    RunDetail,
    RunList,
    RunSummary,
    ScopeRequest,
)
from app.api.security import Principal, current_user
from app.connectors.fabric_api import FabricApiClient
from app.store.base import RunStore
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
def get_run(run_id: str, store: RunStore = Depends(get_store)):
    return RunDetail.from_run(store.get(run_id))


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
