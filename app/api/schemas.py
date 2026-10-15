"""Request and response shapes for the API."""

import uuid
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, Field, StringConstraints, model_validator

from app.contracts.business_contract import BusinessContract, ExpectedExample
from app.workflow.approval import Action, ApprovalRecord
from app.workflow.gates import GateResult
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
    contract: BusinessContract | None = None  # the run's current contract (T-205)
    warnings: list[str] = Field(default_factory=list)

    @classmethod
    def from_run(
        cls,
        run: Run,
        warnings: list[str] | None = None,
        open_questions: list[dict[str, Any]] | None = None,
        contract: BusinessContract | None = None,
    ) -> "RunDetail":
        return cls(
            **run.model_dump(),
            next_action=next_action(run.state),
            open_questions=open_questions or [],
            warnings=warnings or [],
            contract=contract,
        )


class CompileResponse(BaseModel):
    run: RunDetail
    contract: BusinessContract
    blocking_questions: int


class MeResponse(BaseModel):
    oid: str
    upn: str
    name: str
    roles: list[str]


class AnswerRequest(BaseModel):
    answer: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class DismissRequest(BaseModel):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class QuestionResponse(BaseModel):
    run: RunDetail
    contract: BusinessContract


class KpiChanges(BaseModel):
    """Partial Kpi: only the fields sent are changed."""

    model_config = {"extra": "forbid"}

    formula_intent: str | None = None
    grain: str | None = None
    filters: list[str] | None = None
    time_logic: str | None = None
    exclusions: list[str] | None = None
    currency: str | None = None
    expected_examples: list[ExpectedExample] | None = None
    rationale: str | None = None


class KpiEditRequest(KpiChanges):
    expected_hash: str


class ContractEdits(BaseModel):
    """The `edits` of an EDIT approval: partial KPI changes by KPI name."""

    model_config = {"extra": "forbid"}

    kpis: dict[str, KpiChanges] = Field(default_factory=dict)


class ApprovalRequest(BaseModel):
    artifact: str
    action: Action
    comment: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None
    edits: ContractEdits | None = None
    expected_hash: str

    @model_validator(mode="after")
    def _action_rules(self) -> "ApprovalRequest":
        if self.action is Action.REJECT and not self.comment:
            raise ValueError("a comment is required to reject")
        if self.action is Action.EDIT and not (self.edits and self.edits.kpis):
            raise ValueError("edits.kpis is required for an edit")
        return self


class ApprovalResponse(BaseModel):
    approval: ApprovalRecord
    run: RunDetail
    gate_result: GateResult | None = None
    explanation: dict[str, Any] | None = None


class KpiEditResponse(BaseModel):
    contract: BusinessContract


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


class HarvestRequest(BaseModel):
    schemas: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]] | None = None


class HarvestSummary(BaseModel):
    tables: int
    columns: int
    errors: int


class HarvestResponse(BaseModel):
    summary: HarvestSummary
    artifact: ArtifactItem
    warnings: list[str] = Field(default_factory=list)


class Health(BaseModel):
    status: str
    app: str
    version: str
