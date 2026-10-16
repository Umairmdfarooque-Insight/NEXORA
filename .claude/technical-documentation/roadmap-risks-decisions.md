# Roadmap, Risks and Open Decisions

## Implementation Sequence and Milestones

| Milestone | Workstream | Key Build Items | Exit Deliverable |
|---|---|---|---|
| M1 | Foundation | Rayfin shell, authentication, run store, workspace/Lakehouse selection | User can initiate and inspect a run |
| M2 | Requirement control | Prompt parser, clarification, BusinessContract schema, KPI approval | Approved requirement contract |
| M3 | Data understanding | Metadata adapters, profiling, relationship evidence, inventory UI | Validated metadata inventory |
| M4 | Planning | Entity mapping, table resolver, plan/spec schemas, plan approval | Approved execution and model plan |
| M5 | Semantic model | TMDL/DAX generation, MCP integration, sandbox deployment, model validators | Approved semantic model |
| M6 | Report | Report plan, PBIR/PBIP generation, report validation and rendering | Approved report artifact |
| M7 | Operational controls | Retry, impact analysis, deployment, rollback, telemetry and audit | Repeatable end-to-end workflow |

## Project Status Tracking

Status values: Not started / In progress / Done.

| Workstream | Status | Evidence / Link | Current Blocker | Next Decision |
|---|---|---|---|---|
| Rayfin UI | In progress | T-104, T-105, T-205, T-304, T-405, T-507, T-604, T-703: `rayfin-ui/`, [MANUAL_TESTING.md](../MANUAL_TESTING.md); live acceptance: [T-706-evidence.md](../tasks/T-706-evidence.md) | Live acceptance (T-706) | Set to Done when the live check passes |
| Requirement contract | In progress | T-201 to T-205: `app/compiler/`, `app/contracts/business_contract.py`; live acceptance: [T-706-evidence.md](../tasks/T-706-evidence.md) | Live acceptance (T-706) | Set to Done when the live check passes |
| Metadata discovery | In progress | T-301, T-303, T-304: `app/discovery/harvester.py`; live acceptance: [T-706-evidence.md](../tasks/T-706-evidence.md) | Live acceptance (T-706) | Set to Done when the live check passes |
| Data profiling | In progress | T-302: `app/discovery/data_profiler.py`; live acceptance: [T-706-evidence.md](../tasks/T-706-evidence.md) | Live acceptance (T-706) | Set to Done when the live check passes |
| Planning engine | In progress | T-401 to T-405: `app/discovery/model_planner.py`; live acceptance: [T-706-evidence.md](../tasks/T-706-evidence.md) | Live acceptance (T-706) | Set to Done when the live check passes |
| Semantic model generation | In progress | T-502, T-503, T-506: `app/model/`; live acceptance: [T-706-evidence.md](../tasks/T-706-evidence.md) | Live acceptance (T-706) | Set to Done when the live check passes |
| Semantic model validation | In progress | T-504, T-505: `app/model/validators.py`, `app/repair/`; live acceptance: [T-706-evidence.md](../tasks/T-706-evidence.md) | Live acceptance (T-706) | Set to Done when the live check passes |
| Report generation | In progress | T-601, T-602: `app/report/`; live acceptance: [T-706-evidence.md](../tasks/T-706-evidence.md) | Live acceptance (T-706) | Set to Done when the live check passes |
| Report validation | In progress | T-603, T-604: `app/report/validators.py`; live acceptance: [T-706-evidence.md](../tasks/T-706-evidence.md) | Live acceptance (T-706) | Set to Done when the live check passes |
| Human approvals | In progress | T-204, T-405, T-507, T-604, T-702: `app/workflow/approval.py`; live acceptance: [T-706-evidence.md](../tasks/T-706-evidence.md) | Live acceptance (T-706) | Set to Done when the live check passes |
| Sandbox deployment | In progress | T-501, T-702: `app/deploy/`, `app/workflow/promotion.py`; live acceptance: [T-706-evidence.md](../tasks/T-706-evidence.md) | Live acceptance (T-706) | Set to Done when the live check passes |
| Observability and audit | In progress | T-703, T-704, T-705: `app/workflow/audit.py`, `app/observability/`, `app/security/`; live acceptance: [T-706-evidence.md](../tasks/T-706-evidence.md) | Live acceptance (T-706) | Set to Done when the live check passes |

## Key Risks and Mitigations

| Risk | Impact | Planned Mitigation |
|---|---|---|
| Incorrect business interpretation | Correct code implements the wrong KPI | Early ambiguity detection, approved contract and sample result checks |
| Poor source metadata | Weak table and relationship recommendations | Profile actual data, show confidence, request input and block low-confidence progression |
| Invalid DAX or TMDL | Model cannot deploy or returns wrong values | Parse, execute, reconcile and use targeted regeneration |
| Many-to-many ambiguity | Incorrect filtering or double counting | Bridge analysis, mapping validation and human model approval |
| LLM variability | Inconsistent proposals | Schema-constrained outputs, deterministic templates, caching and validators |
| Unbounded regeneration | Cost and repeated invalid results | Retry limits, no-progress detection and user escalation |
| Production impact | Incorrect model/report reaches users | Sandbox-first deployment, approval gates, smoke tests and rollback |
| Scope expansion | Delayed delivery | Milestone exit criteria and one-domain vertical slice first |

## Open Decisions

All decisions except Orchestration are currently **Open** with no owner assigned.

| Decision | Options / Question |
|---|---|
| Backend runtime | Python FastAPI or .NET? |
| Orchestration | **Decided: hybrid.** An explicit run state machine with the control store owns run state, approvals and audit. LangGraph stage graphs run the bounded LLM loops inside a stage (compile, DAX generation, repair). See [CONTRACTS.md#stage-graphs](../tasks/CONTRACTS.md#stage-graphs). |
| Control store | Fabric SQL Database, Warehouse or other approved store? |
| Model authoring route | Canonical TMDL files, MCP object operations, or combined approach? |
| Report authoring route | PBIR generator, report skill/CLI, or combined approach? |
| Sandbox topology | Dedicated workspace per environment, per team or per run? |
| Approval roles | Who approves KPI, model, security, report and deployment? |
| Initial domain | Sales, Retail or another domain? |
| Retry limits | Maximum attempts by artifact type? |

## Document Approval

The document requires sign-off (Approve / Edit / Reject) from these roles. None have signed yet:
- Business sponsor
- Product / solution owner
- Data engineering reviewer
- Power BI / semantic model reviewer
- Security / platform reviewer
