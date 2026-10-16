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
| Backend runtime | **Decided: Python FastAPI** (matches the existing `app/` code) | T-102 |
| Orchestration | **Decided: hybrid.** An explicit state machine with `RunStore` owns run state, approvals and audit. LangGraph stage graphs run the LLM loops inside a stage. See [CONTRACTS.md#stage-graphs](CONTRACTS.md#stage-graphs). | T-101 (state machine), T-202 (first stage graph) |
| Control store | **Decided: both.** Local file store under `runs/<run_id>/` is the default (`RUN_STORE=file`). A Fabric SQL Database store (`RUN_STORE=fabric_sql`, settings `FABRIC_CONTROL_DB_SERVER` and `FABRIC_CONTROL_DB_NAME`) sits behind the same `RunStore` interface. | T-101 |
| Model authoring route | **Decided: canonical TMDL files generated deterministically (T-502), plus an optional MCP writer behind the same interface.** The MCP server and its tools are not chosen yet, so the writer isn't built. | T-502 |
| Report authoring route | **Decided: deterministic PBIR generator** (confirmed at T-602) | T-602 |
| Sandbox topology | **Decided: one dedicated sandbox workspace per environment** (`SANDBOX_WORKSPACE_ID`) | T-501 |
| Approval roles | **Decided: spec roles in a committed `config/roles.yaml`** (real UPNs in the public repo, one person may hold several roles during development) | T-204 |
| Initial domain | **Decided: Sales** (the existing `saleslt` data) | T-202 |
| Retry limits | **Decided: 3 attempts per repair call** (`max_attempts` in `config/repair_policy.yaml`), plus an earlier stop when an attempt makes no progress | T-505 |

## Task index

| ID | Task | Milestone | Status | Branch |
|---|---|---|---|---|
| T-001 | Fix dependencies and configuration loading | [M0 Baseline](M0-baseline.md) | Done | task/T-001-fix-dependencies-and-configuration-loading |
| T-002 | Share one Azure credential across connectors | M0 | Done | task/T-002-share-one-azure-credential |
| T-003 | Environment smoke-check command | M0 | Done | task/T-003-environment-smoke-check-command |
| T-004 | Test fixtures in the sandbox Lakehouse | M0 | Done | task/T-004-test-fixtures-sandbox-lakehouse |
| T-101 | Run model, state machine and run store | [M1 Foundation](M1-foundation.md) | Done | task/T-101-run-model-state-machine-and-run-store |
| T-102 | Orchestration API skeleton | M1 | Done | task/T-102-orchestration-api-skeleton |
| T-103 | Workspace and Lakehouse selection | M1 | Done | task/T-103-workspace-and-lakehouse-selection |
| T-104 | Rayfin UI shell | M1 | Done | task/T-104-rayfin-ui-shell |
| T-105 | Entra authentication | M1 | Done | task/T-105-entra-authentication |
| T-201 | BusinessContract schema | [M2 Requirement control](M2-requirement-control.md) | Done | task/T-201-businesscontract-schema |
| T-202 | Requirement Compiler with ambiguity detection | M2 | Done | task/T-202-requirement-compiler-ambiguity-detection |
| T-203 | Clarification loop | M2 | Done | task/T-203-clarification-loop |
| T-204 | Approval service and Gate G1 | M2 | Done | task/T-204-approval-service-gate-g1 |
| T-205 | Clarification and contract review UI | M2 | Done | task/T-205-clarification-contract-review-ui |
| T-301 | Metadata Harvester per run | [M3 Data understanding](M3-data-understanding.md) | Done | task/T-301-metadata-harvester-per-run |
| T-302 | Generic data profiler | M3 | Done | task/T-302-generic-data-profiler |
| T-303 | Relationship evidence | M3 | Done | task/T-303-relationship-evidence |
| T-304 | Gate G2 and inventory UI | M3 | Done | task/T-304-gate-g2-inventory-ui |
| T-401 | Entity-to-source mapping and conformed-table resolver | [M4 Planning](M4-planning.md) | Done | task/T-401-entity-source-mapping-conformed-resolver |
| T-402 | KPI feasibility and Data Gap | M4 | Done | task/T-402-kpi-feasibility-and-data-gap |
| T-403 | Bridge-table detection and proposal | M4 | Done | task/T-403-bridge-table-detection-proposal |
| T-404 | ExecutionPlan and ModelSpec generation | M4 | Done | task/T-404-executionplan-modelspec-generation |
| T-405 | Gate G3 and plan review UI | M4 | Done | task/T-405-gate-g3-plan-review-ui |
| T-501 | Sandbox deployment client | [M5 Semantic model](M5-semantic-model.md) | Done | task/T-501-sandbox-deployment-client |
| T-502 | TMDL generator | M5 | Done | task/T-502-tmdl-generator |
| T-503 | DAX measure generation | M5 | Done | task/T-503-dax-measure-generation |
| T-504 | Model validators and Gate G4 | M5 | Done | task/T-504-model-validators-gate-g4 |
| T-505 | Validation and Repair service | M5 | Done | task/T-505-validation-repair-service |
| T-506 | Bridge-table generation | M5 | Done | task/T-506-bridge-table-generation |
| T-507 | Model review and approval UI | M5 | Done | task/T-507-model-review-approval-ui |
| T-601 | Report planner | [M6 Report](M6-report.md) | Done | task/T-601-report-planner |
| T-602 | PBIR generator and sandbox publish | M6 | Done | task/T-602-pbir-generator-sandbox-publish |
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
