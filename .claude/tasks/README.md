# Nexora — Sequential Task Plan

Derived from [`../spec/`](../spec/README.md) and [`../technical-documentation/`](../technical-documentation/README.md). Tasks are ordered so that each one builds only on tasks above it. Every task ends with **acceptance criteria** a reviewer can test by hand to confirm it works before the next task starts.

## How to use this plan

- Work top to bottom. Don't start a task until every task in its **Depends on** list has passed its acceptance criteria.
- Shared data shapes, run states, the error envelope, approval records, gate results and validation reports are defined once in [CONTRACTS.md](CONTRACTS.md). Tasks reference that file instead of repeating them.

### Task format

Every task has a header line and six sections:

| Section | Contents |
|---|---|
| **Depends on · Spec** | The tasks that must be `Done` first, and the spec references (FR/NFR/§) |
| **Problem statement** | What is wrong or missing today, and why it matters |
| **Functional requirements** | What the task must do, as numbered requirements |
| **API contracts** | Inputs, outputs and data shapes: endpoints, CLI commands, function signatures, file formats and config files |
| **Constraints** | Rules the implementation must follow: spec rules, security, determinism and limits |
| **Edge cases and error handling** | A table of each case and the expected behavior, using the error codes from [CONTRACTS.md](CONTRACTS.md#error-envelope) |
| **Acceptance criteria** | Numbered checks to run by hand. Each has its steps and an **Expected** result. Passing all of them means the task is done. |
- Until the Rayfin UI exists (T-104), acceptance criteria are tested through the API's Swagger page (`http://localhost:8000/docs`) or the CLI.
- Record progress in the [status tracker](../technical-documentation/roadmap-risks-decisions.md#project-status-tracking) and in the table below. Status values: `Not started` → `In progress` → `Awaiting manual test` → `Done`.
- To have Claude implement a task, run `/implement-task <milestone file | task ID>` (for example `/implement-task M0-baseline.md` or `/implement-task T-101`). After the acceptance criteria pass, run `/implement-task done T-xxx`.

## Working assumptions for open decisions

The spec leaves these [open](../technical-documentation/roadmap-risks-decisions.md#open-decisions). The plan uses the defaults below so work can start. **Confirm or change them before the task that depends on them.**

| Decision | Default used in this plan | First needed at |
|---|---|---|
| Backend runtime | Python FastAPI (matches the existing `app/` code) | T-102 |
| Orchestration | **Decided: hybrid.** An explicit state machine with `RunStore` owns run state, approvals and audit. LangGraph stage graphs run the LLM loops inside a stage. See [CONTRACTS.md#stage-graphs](CONTRACTS.md#stage-graphs). | T-101 (state machine), T-202 (first stage graph) |
| Control store | Local file store under `runs/<run_id>/` behind a store interface, swappable for Fabric SQL Database later | T-101 |
| Model authoring route | Canonical TMDL files generated deterministically; MCP optional later | T-502 |
| Report authoring route | Deterministic PBIR generator | T-602 |
| Sandbox topology | One dedicated sandbox workspace per environment | T-501 |
| Approval roles | Roles from [product-definition.md](../spec/product-definition.md#users-and-responsibilities); one person may hold several roles during development | T-204 |
| Initial domain | Sales (the existing `saleslt` data) | T-202 |
| Retry limits | 3 attempts per artifact section | T-505 |

## Task index

| ID | Task | Milestone | Status | Branch |
|---|---|---|---|---|
| T-001 | Fix dependencies and configuration loading | [M0 Baseline](M0-baseline.md) | Not started |  |
| T-002 | Share one Azure credential across connectors | M0 | Not started |  |
| T-003 | Environment smoke-check command | M0 | Not started |  |
| T-004 | Test fixtures in the sandbox Lakehouse | M0 | Not started |  |
| T-101 | Run model, state machine and run store | [M1 Foundation](M1-foundation.md) | Not started |  |
| T-102 | Orchestration API skeleton | M1 | Not started |  |
| T-103 | Workspace and Lakehouse selection | M1 | Not started |  |
| T-104 | Rayfin UI shell | M1 | Not started |  |
| T-105 | Entra authentication | M1 | Not started |  |
| T-201 | BusinessContract schema | [M2 Requirement control](M2-requirement-control.md) | Not started |  |
| T-202 | Requirement Compiler with ambiguity detection | M2 | Not started |  |
| T-203 | Clarification loop | M2 | Not started |  |
| T-204 | Approval service and Gate G1 | M2 | Not started |  |
| T-205 | Clarification and contract review UI | M2 | Not started |  |
| T-301 | Metadata Harvester per run | [M3 Data understanding](M3-data-understanding.md) | Not started |  |
| T-302 | Generic data profiler | M3 | Not started |  |
| T-303 | Relationship evidence | M3 | Not started |  |
| T-304 | Gate G2 and inventory UI | M3 | Not started |  |
| T-401 | Entity-to-source mapping and conformed-table resolver | [M4 Planning](M4-planning.md) | Not started |  |
| T-402 | KPI feasibility and Data Gap | M4 | Not started |  |
| T-403 | Bridge-table detection and proposal | M4 | Not started |  |
| T-404 | ExecutionPlan and ModelSpec generation | M4 | Not started |  |
| T-405 | Gate G3 and plan review UI | M4 | Not started |  |
| T-501 | Sandbox deployment client | [M5 Semantic model](M5-semantic-model.md) | Not started |  |
| T-502 | TMDL generator | M5 | Not started |  |
| T-503 | DAX measure generation | M5 | Not started |  |
| T-504 | Model validators and Gate G4 | M5 | Not started |  |
| T-505 | Validation and Repair service | M5 | Not started |  |
| T-506 | Bridge-table generation | M5 | Not started |  |
| T-507 | Model review and approval UI | M5 | Not started |  |
| T-601 | Report planner | [M6 Report](M6-report.md) | Not started |  |
| T-602 | PBIR generator and sandbox publish | M6 | Not started |  |
| T-603 | Report validators and Gate G5 | M6 | Not started |  |
| T-604 | Report review and approval UI | M6 | Not started |  |
| T-701 | Impact analysis and stale marking | [M7 Operational controls](M7-operational-controls.md) | Not started |  |
| T-702 | Promotion deployment, smoke tests and rollback | M7 | Not started |  |
| T-703 | Audit trail and traceability view | M7 | Not started |  |
| T-704 | Observability | M7 | Not started |  |
| T-705 | Security hardening | M7 | Not started |  |
| T-706 | End-to-end vertical slice acceptance | M7 | Not started |  |

## Milestone exit checks

Each milestone ends with the exit deliverable from the [roadmap](../technical-documentation/roadmap-risks-decisions.md#implementation-sequence-and-milestones):

| Milestone | Exit deliverable | Proven by |
|---|---|---|
| M0 | Existing code runs reliably and test data exists | T-003, T-004 |
| M1 | User can initiate and inspect a run | T-105 |
| M2 | Approved requirement contract | T-205 |
| M3 | Validated metadata inventory | T-304 |
| M4 | Approved execution and model plan | T-405 |
| M5 | Approved semantic model | T-507 |
| M6 | Approved report artifact | T-604 |
| M7 | Repeatable end-to-end workflow | T-706 |
