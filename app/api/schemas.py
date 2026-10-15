"""Request and response shapes for the API."""

from typing import Annotated, Any

from pydantic import BaseModel, Field, StringConstraints

from app.workflow.next_action import next_action
from app.workflow.run import MAX_PROMPT_LENGTH, Run
from app.workflow.states import RunState

PREVIEW_LENGTH = 80


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
    open_questions: list[Any] = Field(default_factory=list)  # filled from T-202

    @classmethod
    def from_run(cls, run: Run) -> "RunDetail":
        return cls(**run.model_dump(), next_action=next_action(run.state))


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
