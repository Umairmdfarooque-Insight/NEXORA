# Architecture

Rayfin is the web UI and workflow control surface. It talks to an **orchestration API**, which persists run state. The API calls specialized services for:
- requirement compilation
- metadata discovery
- planning
- semantic-model generation
- report generation
- validation
- deployment

## Layers

| Layer | Proposed Components | Responsibility |
|---|---|---|
| Experience | Rayfin web UI; React / Next.js; Fluent UI | Prompt intake, clarification, artifact preview, validation views and approvals |
| Identity and security | Microsoft Entra ID, managed identity, Key Vault, RBAC | Authentication, authorization, service identity and secret protection |
| API and orchestration | Python FastAPI or .NET API; hybrid orchestration: explicit run state machine plus LangGraph stage graphs ([decision](roadmap-risks-decisions.md#open-decisions)) | Run state, checkpoints, routing, retries, approvals and impact analysis. The state machine owns run state and approvals; stage graphs own the LLM loops inside a stage |
| AI reasoning | Approved enterprise model endpoint with schema-constrained outputs | Requirement interpretation, ambiguity detection, candidate plans, DAX/spec proposals and explanations |
| Fabric data access | Fabric REST APIs, Spark/PySpark, SQL analytics endpoint | Workspace/Lakehouse discovery, metadata harvesting and profiling |
| Semantic model | TMDL generator, Power BI Authoring MCP, DAX execution and validators | Model authoring, object operations, testing and remediation |
| Report automation | PBIP/PBIR generator, report authoring skill or CLI, Power BI REST APIs | Report plan translation, report definition, validation, binding and publication |
| Persistence | Fabric SQL Database / Warehouse or equivalent control store; object storage for artifacts | Run state, contracts, metadata inventory, artifacts and validation evidence |
| Observability | Application Insights / Log Analytics / OpenTelemetry | Logs, metrics, traces, errors and cost telemetry |

## Component Design

### Rayfin Web UI
- Business-prompt editor
- Clarification conversation panel
- Workspace and Lakehouse selector
- Artifact comparison and preview
- Validation evidence and warning view
- Approval actions and run timeline

### Requirement Compiler
- Extract entities, KPIs, dimensions and constraints
- Detect missing business definitions
- Generate `BusinessContract.yaml`
- Maintain locked facts and open questions

### Metadata Harvester
- List approved source scope
- Extract schemas, tables and columns
- Run profile queries or notebooks
- Produce `MetadataInventory.json` and warnings

### Planning Engine
- Map entities to sources
- Score/select conformed tables
- Propose grain, relationships, measures, storage and RLS
- Generate `ExecutionPlan.yaml` and `ModelSpec.yaml`

### Semantic Model Builder
- Generate initial TMDL/DAX specification with LLM assistance
- Use deterministic serializers or MCP operations to create model objects
- Deploy to sandbox
- Invoke model validators and DAX tests

### Report Builder
- Generate `ReportPlan.json`
- Create PBIR/PBIP pages and visual bindings
- Render report for review
- Run schema, query and binding validators

### Validation and Repair Service
- Normalize validator errors
- Classify each failure as deterministic repair, LLM-assisted regeneration or user input
- Enforce retry limits and no-progress detection
- Record `ValidationReport.json`
- Runs the repair loop as a LangGraph stage graph. Run-state transitions stay with the orchestration API

### Deployment Service
- Resolve authorized target
- Create/update artifacts idempotently
- Poll asynchronous operations
- Run post-deployment smoke tests and record outcome
