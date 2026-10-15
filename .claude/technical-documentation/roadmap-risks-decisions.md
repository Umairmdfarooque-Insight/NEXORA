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
| Rayfin UI |  |  |  |  |
| Requirement contract |  |  |  |  |
| Metadata discovery |  |  |  |  |
| Data profiling |  |  |  |  |
| Planning engine |  |  |  |  |
| Semantic model generation |  |  |  |  |
| Semantic model validation |  |  |  |  |
| Report generation |  |  |  |  |
| Report validation |  |  |  |  |
| Human approvals |  |  |  |  |
| Sandbox deployment |  |  |  |  |
| Observability and audit |  |  |  |  |

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
