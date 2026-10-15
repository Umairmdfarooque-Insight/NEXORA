"""Request and response shapes for the API."""

import uuid
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, Field, StringConstraints

from app.contracts.business_contract import BusinessContract
from app.workflow.next_action import next_action
from app.workflow.run import MAX_PROMPT_LENGTH, Run
from app.workflow.states import RunState

PREVIEW_LENGTH = 80


def _guid(value: str) -> str:
    try:
        return str(uuid.UUID(value.strip()))
    except ValueError:
        raise ValueError("must be a GUID") from None


Guid = Annotated[str, AfterValidator(_guid)]


class CreateRunRequest(BaseModel):
    prompt: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=1, max_length=MAX_PROMPT_LENGTH
        ),
    ]
    subject_area: str | None = None
    desired_outputs: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)


class RunSummary(BaseModel):
    run_id: str
    state: RunState
    prompt_preview: str
    created_at: str
    created_by: dict[str, Any] | None = None

    @classmethod
    def from_run(cls, run: Run) -> "RunSummary":
        return cls(
            run_id=run.run_id,
            state=run.state,
            prompt_preview=" ".join(run.prompt.split())[:PREVIEW_LENGTH],
            created_at=run.created_at,
            created_by=run.created_by,
        )


class RunList(BaseModel):
    items: list[RunSummary]
    total: int


class RunDetail(Run):
    next_action: str
    open_questions: list[dict[str, Any]] = Field(default_factory=list)  # open questions of the current contract
    warnings: list[str] = Field(default_factory=list)

    @classmethod
    def from_run(
        cls,
        run: Run,
        warnings: list[str] | None = None,
        open_questions: list[dict[str, Any]] | None = None,
    ) -> "RunDetail":
        return cls(
            **run.model_dump(),
            next_action=next_action(run.state),
            open_questions=open_questions or [],
            warnings=warnings or [],
        )


class CompileResponse(BaseModel):
    run: RunDetail
    contract: BusinessContract
    blocking_questions: int


class ScopeRequest(BaseModel):
    workspace_id: Guid
    lakehouse_id: Guid
    schemas: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]] = Field(
        default_factory=list
    )


class WorkspaceItem(BaseModel):
    id: str
    display_name: str
    type: str


class SqlEndpointItem(BaseModel):
    server: str
    database: str


class LakehouseItem(BaseModel):
    id: str
    display_name: str
    workspace_id: str
    sql_endpoint: SqlEndpointItem | None = None


class ArtifactItem(BaseModel):
    name: str
    version: int
    path: str
    hash: str
    status: str
    updated_at: str


class Health(BaseModel):
    status: str
    app: str
    version: str
