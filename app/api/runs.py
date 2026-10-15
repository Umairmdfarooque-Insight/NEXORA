"""Run endpoints. Handlers only call the RunStore and shape the response."""

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_store
from app.api.schemas import (
    ArtifactItem,
    CreateRunRequest,
    RunDetail,
    RunList,
    RunSummary,
)
from app.store.base import RunStore
from app.workflow.states import RunState

router = APIRouter(prefix="/runs", tags=["runs"])

# The store has no count query yet, so total is taken from an unbounded list.
ALL_RUNS = 1_000_000


@router.post("", status_code=201, response_model=RunDetail)
def create_run(body: CreateRunRequest, store: RunStore = Depends(get_store)):
    run = store.create(
        body.prompt, body.subject_area, body.desired_outputs, body.constraints
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
