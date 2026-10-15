"""What happens next for a run in each state (FR-021)."""

from app.workflow.states import RunState

S = RunState

NEXT_ACTION: dict[RunState, str] = {
    S.CREATED: "Compile requirement",
    S.NEEDS_CLARIFICATION: "Answer open questions",
    S.REQUIREMENT_APPROVED: "Harvest metadata",
    S.DATA_PROFILED: "Build plan",
    S.PLAN_APPROVED: "Generate semantic model",
    S.MODEL_GENERATING: "Validate and review model",
    S.MODEL_FAILED: "Repair model",
    S.MODEL_APPROVED: "Generate report",
    S.REPORT_GENERATING: "Validate and review report",
    S.REPORT_FAILED: "Repair report",
    S.REPORT_APPROVED: "Deploy",
    S.DEPLOYING: "Wait for deployment",
    S.COMPLETED: "None",
    S.NEEDS_INPUT: "Provide input",
    S.ROLLED_BACK: "Investigate and redeploy",
}


def next_action(state: RunState) -> str:
    return NEXT_ACTION[state]
