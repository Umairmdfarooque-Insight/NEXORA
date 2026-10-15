# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Nexora is the AI engine behind a UI called "Rayfin" (`APP_NAME` / `UI_APP_NAME` in `app/config.py`). It takes a business requirement in plain English and works out which tables and columns in a Microsoft Fabric Lakehouse can satisfy it. The sample data is AdventureWorks-style (`saleslt` schema).

## Spec and design docs

The target product is defined in `.claude/spec/` (requirements FR/NFR, business rules, acceptance scenarios) and `.claude/technical-documentation/` (architecture, artifact contracts, run states, gates G1–G6, milestones, open decisions). Both are transcribed from `Nexora_Specification_and_Technical_Design.docx` (v0.1 draft). Read them before adding a new pipeline stage.

The code is an early slice of the design and does not yet produce its artifacts. Mapping of current code to the design:
- `requirement_analyzer.py` → the old prototype of the Requirement Compiler. The real one is `app/compiler/` (T-202): it produces `BusinessContract.yaml`. The approval loop comes with T-203/T-204.
- `metadata_inventory.py`, `data_profiler.py`, `semantic_mapper.py`, `relationship_validator.py` → Metadata Harvester and relationship evidence (M3, FR-005–FR-007).
- Not started: the Rayfin UI and run store (M1), planning (M4), TMDL/DAX (M5), reports (M6), retries, deployment and audit (M7).

Manual test steps for every finished task are in `.claude/MANUAL_TESTING.md`; `/implement-task` updates it at each hand-over.

The human workflow (dev session `T-xxx` plus review session `T-xxx_test`, task branch, PR, cleanup) is described in `.claude/DEVELOPMENT_WORKFLOW.md`. In a `_test` session, review and help test only; don't implement the task. Use `/review-task [T-xxx]` (`.claude/skills/review-task/SKILL.md`) for the review. The build order is in `.claude/tasks/` (T-001 … T-706, grouped by milestone M0–M7). Each task has six sections (problem statement, functional requirements, API contracts, constraints, edge cases and error handling, acceptance criteria). Its acceptance criteria must pass a manual test before the next task starts. Shared shapes and error codes are in `.claude/tasks/CONTRACTS.md`; implement against them exactly. `.claude/tasks/README.md` lists the defaults assumed for the spec's open decisions, such as FastAPI, hybrid orchestration and a file-based run store. Orchestration is decided as **hybrid**: the run state machine and `RunStore` own run state, approvals and audit, and LangGraph stage graphs run only the LLM loops inside a stage (rules in `.claude/tasks/CONTRACTS.md#stage-graphs`). Use `/implement-task <milestone file | task ID>` (`.claude/skills/implement-task/SKILL.md`) to work on a task. It enforces the dependency order and keeps the README status column up to date. Use `/commit-push [branch | "note"]` (`.claude/skills/commit-push/SKILL.md`) to commit with a generated message and push. The repo is public, so that skill blocks secrets and binaries. After a branch's PR is merged, `/cleanup-branch [branch]` updates local `main` from the remote and deletes the branch, after a caution message and confirmation.

Rules from the spec that constrain all new code:
- The LLM proposes; deterministic validators decide progression.
- No silent assumptions for KPI definitions.
- Return "Not Feasible / Data Gap" instead of fabricating a calculation.
- A LangGraph stage graph never changes run state or writes `RunManifest.json`. Its loops are bounded, and it routes only on validator output.

## Commands

Windows; a virtualenv lives in `.venv` (Python 3.12). A `.venv` copied from another machine fails with "No Python at ..."; recreate it with `py -3.12 -m venv .venv`.

```
.venv\Scripts\activate
pip install -r requirements.txt           # lists every third-party package the code imports
python -m app.test_requirement_analyzer   # run one script
python -m app.tools.smoke [--only llm,lakehouse,sql] [--json]   # check LLM, Lakehouse and SQL access; exit 0/1/2
python -m app.cli runs create --prompt "..."   # also: list, show RUN_ID, transition RUN_ID STATE (exit 0/1/2)
python -m app.cli contract validate FILE   # VALID/INVALID (exit 0/1); also: contract schema [--output FILE]
uvicorn app.api.main:app --reload --port 8000   # orchestration API; Swagger at /docs
cd rayfin-ui; npm install; npm run dev          # Rayfin UI on http://localhost:3000 (also: npm test, npm run typecheck, npm run build)
```

- Test data for the acceptance scenarios lives in schema `nexora_test` of the sandbox Lakehouse. It is created by the Spark notebook `fixtures/create_test_tables.ipynb` (see `fixtures/README.md`), not by Python in `app/`. `python -m app.test_metadata_inventory [schema]` lists a schema's tables (default `saleslt`).
- There is no build, lint, or pytest setup. The `app/test_*.py` files are **manual scripts** with a `main()`. Each exercises one pipeline stage against live Azure/Fabric.
- Run them as modules from the project root (`python -m app.test_x`). Imports are absolute (`from app.config import ...`), so running the file directly will fail.
- Running anything needs a `.env` (copy `.env.example`). `app/config.py` loads `PROJECT_ROOT/.env` once (shell variables win over `.env`, so the working directory doesn't matter) and calls `get_required_setting` at import time for `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT` and `AZURE_OPENAI_API_KEY`, so importing `app.config` raises `ValueError` if any is missing. That includes the connector modules. The Fabric settings (`FABRIC_*`) are optional: `get_optional_setting` returns `None` when they are unset or blank.
- Fabric access goes through `app/auth.py`: one process-wide `InteractiveBrowserCredential` with an on-disk token cache (`TokenCachePersistenceOptions(name="nexora")`), plus a saved sign-in record (`%LOCALAPPDATA%\.IdentityService\nexora_auth_record.json`, account identifiers only, no tokens), so a process signs in once and later runs read the cache silently. Delete that file to force a fresh sign-in. Connectors call `get_token(STORAGE_SCOPE | SQL_SCOPE | FABRIC_SCOPE)`; never create a credential elsewhere. `fabric_sql_connector` also needs the ODBC Driver 18 for SQL Server installed.

## Runs

`app/workflow/` holds the run states (`states.py`) and the `Run` model with the single `apply_transition` function (`run.py`). `app/store/` holds the `RunStore` interface (`base.py`), the default `FileRunStore` (`runs/<run_id>/RunManifest.json`, gitignored) and `SqlRunStore` (table `dbo.nexora_runs` in a writable Fabric SQL Database). `RUN_STORE=file|fabric_sql` picks the store through `get_run_store()`; `fabric_sql` also needs `FABRIC_CONTROL_DB_SERVER` and `FABRIC_CONTROL_DB_NAME`. Only the store writes manifests.

`app/api/` is the FastAPI orchestration API (`main.py` app, CORS for `http://localhost:3000`; `runs.py` routes; `schemas.py`; `errors.py` maps exceptions to the shared error envelope; `deps.py` supplies the store). Handlers hold no business logic and there is no public state-transition endpoint. `app/workflow/next_action.py` maps each state to its `next_action`. Every endpoint except `/health` needs an Entra bearer token (`api/security.py` validates signature, issuer, audience, expiry, tenant and the `access_as_user` scope; `current_user` yields `{oid, upn, name}`). There is no bypass: without `ENTRA_TENANT_ID` and `ENTRA_API_CLIENT_ID` protected endpoints return `500 CONFIG_ERROR`. Fabric and OneLake are called on behalf of the user (`api/obo.py`, MSAL OBO; needs `ENTRA_API_CLIENT_SECRET`), so lists reflect that user's access. Runs record `created_by` and the history actor as the user's UPN. The CLI calls the store directly and needs no token.

Fabric access for runs: `connectors/fabric_api.py` (`FabricApiClient`) lists workspaces and Lakehouses (paging, 429 retry, typed errors); `workflow/scope.py` (`bind_scope`) verifies and saves a run's `scope` (`PUT /runs/{id}/scope`, locked once metadata is harvested). Connectors take the scope through `FabricLakehouseConnector.for_scope(scope)` and `FabricSQLConnector.for_scope(scope)`; with no scope they fall back to the `FABRIC_*` values in `.env`.

`rayfin-ui/` is the Rayfin web UI: Next.js (app router), TypeScript and Fluent UI v9. Pages: `/runs` (list), `/runs/new` (prompt, scope and options form), `/runs/[id]` (state, next action, open questions, scope, timeline). All data comes from the API through `src/lib/api.ts` (`NEXT_PUBLIC_API_BASE_URL`, default `http://localhost:8000`, set in the gitignored `rayfin-ui/.env.local`); the UI holds no business logic. The UI signs in with MSAL (`src/lib/auth.ts`, `src/components/AuthProvider.tsx`) before any page renders and sends the token as a bearer header (`src/lib/api.ts` refreshes it silently once on `TOKEN_EXPIRED`). Settings: `NEXT_PUBLIC_ENTRA_TENANT_ID`, `NEXT_PUBLIC_ENTRA_CLIENT_ID`, `NEXT_PUBLIC_API_SCOPE`. The API's CORS allows only `http://localhost:3000`, so the UI must run on that port.

## Business contract

`app/contracts/business_contract.py` defines `BusinessContract` (pydantic, `extra="forbid"`) and its parts (`Kpi`, `OpenQuestion`, `LockedFact`, `Feasibility`). `load`/`save` read and write `BusinessContract.yaml` deterministically (fixed key order, UTF-8, LF; `save` returns the `sha256:` hash). The approval rules (no open blocking question; every KPI has `formula_intent`, `grain` and `currency`; unique KPI names and ids) live in the model, not in prompts. `schemas/business_contract.schema.json` is the committed JSON Schema (regenerate with `contract schema --output`); `samples/contract_valid.yaml` is the reference sample. 

### Requirement Compiler (T-202)

`POST /runs/{id}/compile` (`workflow/compile_stage.py`, `compile_run`) is allowed in `CREATED` and `NEEDS_CLARIFICATION` only (`409 WRONG_STATE` otherwise). It runs the `compile` LangGraph (`graphs/compile.py`, run through `graphs/base.py:run_graph`): `llm_compile → validate_schema → (one retry with the errors) → apply_critical_terms → apply_locked_facts`. The LLM call (`llm/structured.py`, Responses API, strict JSON Schema, 60 s) gets only the prompt, subject area, outputs, constraints and the previous contract. `config/critical_terms.yaml` lists the business-critical terms; one used without a definition always gets a blocking `RULE-<TERM>` question (`compiler/critical_terms.py`), and no KPI gives `RULE-METRIC`. The service writes `runs/<id>/BusinessContract.yaml` and `contracts/BusinessContract.v<n>.yaml`, registers the artifact and moves the state (`NEEDS_CLARIFICATION` while a blocking question is open, else `CREATED`). The graph itself never touches run state. Tests inject a fake LLM through `build_compile_graph(llm=…)` or the `get_llm` dependency.

## Architecture

A staged discovery pipeline. There is no orchestrator or entry point yet; the `test_*.py` scripts wire the stages together by hand. Data flows between stages as plain dicts or the `RequirementSpec` pydantic model:

1. `llm/requirement_analyzer.py` — `analyze_requirement()` returns a `RequirementSpec` (objective, entities, metrics, dimensions, filters, security requirements, assumptions, clarification questions).
2. `connectors/fabric_lakehouse.py` + `discovery/metadata_inventory.py` — `build_metadata_inventory()` returns `{schema_name, tables: [{table_name, columns: [{name, data_type}]}], errors}`. It reads the OneLake table REST API with a bearer token for `storage.azure.com`.
3. `discovery/requirement_data_matcher.py` — deterministic matching of requirement terms to inventory columns, driven by the `ALIASES` dict and name normalization.
4. `discovery/semantic_mapper.py` — LLM-suggested mappings and join relationships, given the requirement and the inventory.
5. `discovery/relationship_validator.py` — checks the suggested relationships against the inventory. With `run_data_checks=True` and a connector, it also checks them against real data.
6. `connectors/fabric_sql_connector.py` — a separate read-only path to the Fabric SQL endpoint (pyodbc; passes a `database.windows.net` access token via `attrs_before={1256: ...}`). Used by `discovery/data_profiler.py` and the data checks in step 5.

Design rule stated in the code: **inventory metadata is the source of truth** for which tables and columns exist. LLM output is only a candidate until validated, so don't let LLM-suggested names bypass the validator.

### LLM access

`llm/client.py` builds one shared `OpenAI` client pointed at Azure's v1 endpoint (`{AZURE_OPENAI_ENDPOINT}/openai/v1/`). It uses the Responses API (`client.responses.create`) with `model=AZURE_OPENAI_DEPLOYMENT`. Prompts name the assistant "Nexora"; `ask_rayfin()` is the generic helper. The analyzer and mapper ask for JSON and validate it (pydantic for the analyzer).

## Gotchas

- Table and column names are hardcoded in several places for the sample data (`saleslt.SalesLT_Product`, `saleslt.synthetic_sales_daily`, the `ALIASES` dict, `data_profiler.py`). Generalizing means touching all of them.
- `.env` holds real credentials and is gitignored (`.env.example` lists the variable names).
