# M1 — Foundation

**Exit deliverable:** user can initiate and inspect a run. Shared shapes are in [CONTRACTS.md](CONTRACTS.md).

---

### T-101 — Run model, state machine and run store

**Depends on:** T-001 · **Spec:** FR-001, FR-021, §11 Workflow State Model, `RunManifest.json` (§10), NFR-003

#### Problem statement
The existing pipeline stages are disconnected scripts with no notion of a run. Nothing records which prompt a result belongs to, which stage it reached, or which state changes are allowed. Every later task needs a persistent run, with enforced state transitions, to attach its artifacts and gates to.

#### Functional requirements
1. Creating a run from a prompt gives it a unique `run_id` and state `CREATED` (FR-001).
2. State changes go through one transition function. It allows only the transitions in [CONTRACTS.md#run-states-and-transitions](CONTRACTS.md#run-states-and-transitions) and records every successful one in `history`.
3. Runs are persisted, survive process restarts, and can be listed and loaded.
4. Moving to `NEEDS_INPUT` stores `resume_state`. Leaving `NEEDS_INPUT` without naming a state returns to it.
5. A CLI exposes create, list, show and transition, for testing before the API exists.
6. A second store, `SqlRunStore`, keeps runs in a Fabric SQL Database behind the same `RunStore` interface. The `RUN_STORE` setting (`file` default, or `fabric_sql`) picks the store.

#### API contracts
- `app/workflow/states.py`: `class RunState(str, Enum)` with the 15 states, `ALLOWED: dict[RunState, set[RunState]]`, and `can_transition(a, b) -> bool`.
- `app/workflow/run.py`: pydantic `Run`, matching [CONTRACTS.md#run](CONTRACTS.md#run).
- `app/store/base.py`, with `class RunStore(Protocol)`:
  - `create(prompt, subject_area=None, desired_outputs=(), constraints=()) -> Run`
  - `get(run_id) -> Run`, which raises `RunNotFound`
  - `list(state: RunState | None = None, limit=50) -> list[Run]`, newest first
  - `save(run: Run) -> None`
  - `transition(run_id, to: RunState, reason: str, actor: str = "system") -> Run`, which raises `IllegalTransition(from_, to)`
- `app/store/file_store.py`: `FileRunStore(root: Path = PROJECT_ROOT / "runs")` writes `runs/<run_id>/RunManifest.json`.
- `app/store/sql_store.py`: `SqlRunStore(server, database)` keeps one row per run in `dbo.nexora_runs` (`run_id` PK, `state`, `created_at`, `updated_at`, `version`, `manifest` JSON). It creates the table on first use and uses a `version` check so two writers can't silently overwrite each other.
- `app/store/factory.py`: `get_run_store()` reads `RUN_STORE`, and for `fabric_sql` also `FABRIC_CONTROL_DB_SERVER` and `FABRIC_CONTROL_DB_NAME` from `.env`.
- CLI `python -m app.cli runs …`:
  - `create --prompt TEXT [--subject-area S] [--output O]… [--constraint C]…` prints the `run_id`.
  - `list [--state STATE]` prints a table of `run_id`, `state`, `created_at` and the first 40 characters of the prompt.
  - `show RUN_ID` prints the manifest JSON.
  - `transition RUN_ID STATE [--reason TEXT]`.
  - Exit `0` on success, `1` for a domain error (not found or illegal), `2` for bad arguments.

#### Constraints
- Writes are atomic: write `RunManifest.json.tmp`, then `os.replace` it.
- `runs/` is gitignored.
- The store is the only code that writes manifests. Other modules call the store.
- The file store is the default. The Fabric SQL store must target a writable Fabric *SQL Database*, never the read-only Lakehouse SQL endpoint, and only in the sandbox workspace. Its connection settings come from `.env`; never print them.
- This is the run layer of the hybrid orchestration ([CONTRACTS.md#stage-graphs](CONTRACTS.md#stage-graphs)). Don't use LangGraph here. `RunStore` stays the only source of truth for run state, even after stage graphs are added.

#### Edge cases and error handling
| Case | Expected behavior |
|---|---|
| Empty or whitespace-only prompt | `ValueError("Prompt cannot be empty")`, and the CLI exits `2`. |
| Prompt longer than 10,000 characters | Rejected with a message giving the limit. |
| Unknown `run_id` | `RunNotFound`. The CLI prints `Run not found: <id>` and exits `1`. |
| Illegal transition | `IllegalTransition`. The state and history are unchanged. |
| Transition to the current state | Treated as illegal, so no duplicate history entries are created. |
| Corrupt or partial `RunManifest.json` | `get` raises `RunCorrupt(run_id)`. `list` skips that run and logs a warning. |
| `runs/` folder missing | Created on first write. |
| `RUN_STORE` is not `file` or `fabric_sql` | `ValueError` naming the valid values, and the CLI exits `2`. |
| `RUN_STORE=fabric_sql` with a control-database setting blank | `ValueError: Missing required configuration: <name>`, and the CLI exits `2`. |
| Control database unreachable or permission denied | `StoreUnavailable`. The CLI prints the reason and exits `1`. |
| Another writer changes a run during a transition | The SQL store re-reads and re-validates, up to 3 times, then raises `StoreUnavailable`. |

#### Acceptance criteria
1. **Create.** Run `python -m app.cli runs create --prompt "Total sales by month"`. **Expected:** a UUID is printed, and `runs/<id>/RunManifest.json` exists with `"state": "CREATED"` and one history entry.
2. **Unique IDs.** Repeat AC-1 with the same prompt. **Expected:** a different `run_id`.
3. **Illegal transition blocked.** Run `python -m app.cli runs transition <id> DEPLOYING`. **Expected:** a message that `CREATED → DEPLOYING` is not allowed, exit `1`, and the state is still `CREATED`.
4. **Legal transition recorded.** Run `runs transition <id> NEEDS_CLARIFICATION --reason test`, then `runs show <id>`. **Expected:** the state is `NEEDS_CLARIFICATION`, and history has a second entry with your reason and a timestamp.
5. **Needs-input resume.** Run `runs transition <id> NEEDS_INPUT`, then `runs show <id>`. **Expected:** `resume_state` is `NEEDS_CLARIFICATION`.
6. **Persistence.** Close the terminal, open a new one, and run `runs show <id>`. **Expected:** the same state and history.
7. **Fabric SQL store, create and read.** Set `RUN_STORE=fabric_sql` and the two `FABRIC_CONTROL_DB_*` values, then run `runs create`, `runs list` and `runs show <id>`. **Expected:** the run appears in `runs list` and `show`, and `SELECT run_id, state FROM dbo.nexora_runs` in the database returns it.
8. **Fabric SQL store, same rules.** Repeat AC-3 to AC-5 with `RUN_STORE=fabric_sql`. **Expected:** the same results as the file store, and the `state` column in `dbo.nexora_runs` matches `runs show`.
9. **Fabric SQL store, persistence.** Open a new terminal and run `runs show <id>` again with `RUN_STORE=fabric_sql`. **Expected:** the same state and history. Runs created with the file store do not appear (the stores are separate).
10. **Missing setting.** With `RUN_STORE=fabric_sql`, blank `FABRIC_CONTROL_DB_NAME` and run `runs list`. **Expected:** `Missing required configuration: FABRIC_CONTROL_DB_NAME`, exit `2`, no traceback. Restore it afterwards.
11. **Unreachable database.** With `RUN_STORE=fabric_sql`, set `FABRIC_CONTROL_DB_SERVER=invalid.example.com` and run `runs list`. **Expected:** a readable "Cannot connect" message, exit `1`, no traceback. Restore it afterwards.
12. **Bad store name.** Run `$env:RUN_STORE="nope"; python -m app.cli runs list`. **Expected:** `Invalid RUN_STORE: 'nope'. Valid values: file, fabric_sql`, exit `2`.
7. **Corrupt file tolerated.** Copy a run folder, truncate its manifest to `{`, and run `runs list`. **Expected:** the other runs are listed and a warning names the corrupt run.

---

### T-102 — Orchestration API skeleton

**Depends on:** T-101 · **Spec:** FR-001, FR-021, §7 (API and orchestration layer), NFR-005

#### Problem statement
Runs can only be managed through a local CLI. Rayfin and the other services need an HTTP API that creates and inspects runs, with consistent errors and a "what happens next" hint.

#### Functional requirements
1. HTTP endpoints create, list and read runs, and list a run's artifacts.
2. Every run response includes `next_action`, derived from the state (FR-021).
3. Errors use the shared envelope ([CONTRACTS.md#error-envelope](CONTRACTS.md#error-envelope)).
4. Interactive API docs are available at `/docs`.

#### API contracts
App: `app/api/main.py`. Start it with `uvicorn app.api.main:app --reload --port 8000`.

| Method and path | Request | Response |
|---|---|---|
| `GET /health` | — | `200 {"status": "ok", "app": "Nexora", "version": "<git sha or 0.0.0>"}` |
| `POST /runs` | `{"prompt": str (1–10000 chars), "subject_area"?: str, "desired_outputs"?: [str], "constraints"?: [str]}` | `201` `RunDetail` |
| `GET /runs?state=&limit=50` | — | `200 {"items": [RunSummary], "total": int}` |
| `GET /runs/{run_id}` | — | `200` `RunDetail` |
| `GET /runs/{run_id}/artifacts` | — | `200 [{"name", "version", "path", "hash", "status", "updated_at"}]` |

- `RunSummary` is `{run_id, state, prompt_preview, created_at, created_by}`.
- `RunDetail` is the full `Run` plus `next_action: str` and `open_questions: []`, which stays empty until T-202.
- `next_action` by state:

| State | `next_action` |
|---|---|
| `CREATED` | Compile requirement |
| `NEEDS_CLARIFICATION` | Answer open questions |
| `REQUIREMENT_APPROVED` | Harvest metadata |
| `DATA_PROFILED` | Build plan |
| `PLAN_APPROVED` | Generate semantic model |
| `MODEL_GENERATING` | Validate and review model |
| `MODEL_FAILED` | Repair model |
| `MODEL_APPROVED` | Generate report |
| `REPORT_GENERATING` | Validate and review report |
| `REPORT_FAILED` | Repair report |
| `REPORT_APPROVED` | Deploy |
| `DEPLOYING` | Wait for deployment |
| `COMPLETED` | None |
| `NEEDS_INPUT` | Provide input |
| `ROLLED_BACK` | Investigate and redeploy |

#### Constraints
- Route handlers contain no business logic. They call `RunStore` and the domain services.
- There is no public endpoint for arbitrary state transitions. States change only through the domain endpoints added in later tasks.
- Pattern for those later endpoints: the handler calls a stage service. The service checks the state, runs the stage graph if the stage has one, runs the gate, and then transitions through `RunStore` ([CONTRACTS.md#stage-graphs](CONTRACTS.md#stage-graphs)).
- CORS allows `http://localhost:3000` (Rayfin, from T-104) only.
- No authentication yet. T-105 adds it, so run the API locally only.

#### Edge cases and error handling
| Case | Expected behavior |
|---|---|
| Empty prompt or missing `prompt` | `422 VALIDATION_ERROR`, with the field named. |
| Unknown `run_id` | `404 RUN_NOT_FOUND`. |
| `limit` above 200 or below 1 | `422`. |
| Invalid `state` filter | `422`, listing the valid states. |
| Unhandled exception | `500 INTERNAL_ERROR` with a generic message. Details go to the log only. |

#### Acceptance criteria
1. **Docs.** Start the API and open `http://localhost:8000/docs`. **Expected:** all five endpoints are listed.
2. **Create.** From Swagger, call `POST /runs` with `{"prompt": "Sales by product category"}`. **Expected:** `201`, a `run_id`, `state: "CREATED"` and `next_action: "Compile requirement"`.
3. **Read and list.** Call `GET /runs/{id}` and `GET /runs`. **Expected:** the new run appears in both.
4. **Validation.** Call `POST /runs` with `{"prompt": ""}`. **Expected:** `422` with the error envelope.
5. **Not found.** Call `GET /runs/00000000-0000-0000-0000-000000000000`. **Expected:** `404` with `code: "RUN_NOT_FOUND"`.
6. **Shared store.** Run `python -m app.cli runs list`. **Expected:** it shows the run created through the API.

---

### T-103 — Workspace and Lakehouse selection

**Depends on:** T-102 · **Spec:** FR-004, §14 (authorize by workspace and Lakehouse)

#### Problem statement
The Fabric workspace and Lakehouse are fixed in `.env`, so every run uses the same source. Users must be able to choose, per run, a workspace and Lakehouse they can access, and connectors must use that choice.

#### Functional requirements
1. List the Fabric workspaces visible to the caller's identity.
2. List the Lakehouses in a chosen workspace, including their SQL endpoint connection details.
3. Bind a run to a workspace, a Lakehouse and optionally schemas, after verifying that the identity can see them.
4. Connectors read the workspace, Lakehouse and SQL endpoint from the **run scope**. `.env` values are only a fallback for scripts that don't use a run.

#### API contracts
| Method and path | Request | Response |
|---|---|---|
| `GET /fabric/workspaces` | — | `200 [{"id", "display_name", "type"}]` |
| `GET /fabric/workspaces/{workspace_id}/lakehouses` | — | `200 [{"id", "display_name", "workspace_id", "sql_endpoint": {"server", "database"} \| null}]` |
| `PUT /runs/{run_id}/scope` | `{"workspace_id": str, "lakehouse_id": str, "schemas"?: [str]}` | `200` `RunDetail` |

- Upstream calls go to `GET https://api.fabric.microsoft.com/v1/workspaces` and `GET https://api.fabric.microsoft.com/v1/workspaces/{id}/lakehouses`, using a token for `FABRIC_SCOPE`.
- Connector factories: `FabricLakehouseConnector.for_scope(scope)` and `FabricSQLConnector.for_scope(scope)`.
- The `scope` object also stores `workspace_name`, `lakehouse_name` and `sql_endpoint` (see [CONTRACTS.md#run](CONTRACTS.md#run)). `RunDetail` gains `warnings: [str]`, used for the no-SQL-endpoint warning.
- `workspace_id` and `lakehouse_id` must be GUIDs, otherwise `422 VALIDATION_ERROR`. A workspace that doesn't exist is reported as `403 FORBIDDEN`, the same as one the identity can't see.

#### Constraints
- Until T-105, the identity is the local interactive credential from T-002.
- Follow `continuationToken` paging until all pages are read.
- The scope can be changed only before metadata is harvested: states `CREATED`, `NEEDS_CLARIFICATION`, and `REQUIREMENT_APPROVED` with no `MetadataInventory` artifact.

#### Edge cases and error handling
| Case | Expected behavior |
|---|---|
| Workspace or Lakehouse ID not visible to the identity | `403 FORBIDDEN`. The scope is not saved. |
| Lakehouse with no SQL endpoint yet | `sql_endpoint: null`. Setting it as the scope is allowed, with a warning in the response. |
| Fabric returns `429` | Retry after the `Retry-After` delay, up to 3 times, then return `429 RATE_LIMITED`. |
| Fabric unavailable or `5xx` | `502 UPSTREAM_ERROR` with the Fabric request ID. |
| Scope change after harvest | `409 SCOPE_LOCKED`. |
| `schemas` contains a schema that doesn't exist | `404 SCHEMA_NOT_FOUND`, naming the schema. |

#### Acceptance criteria
1. **Workspaces match the portal.** Call `GET /fabric/workspaces`. **Expected:** the same workspaces you see in the Fabric portal.
2. **Lakehouses match.** Call `GET /fabric/workspaces/{id}/lakehouses` for a known workspace. **Expected:** the same Lakehouses as the portal, with `sql_endpoint` filled in.
3. **Bind scope.** Call `PUT /runs/{id}/scope` with valid IDs and `"schemas": ["saleslt"]`, then `GET /runs/{id}`. **Expected:** `scope` is shown.
4. **Invalid ID refused.** Call `PUT /runs/{id}/scope` with a random GUID as `workspace_id`. **Expected:** `403`, and `GET /runs/{id}` still shows the previous scope.
5. **Bad schema.** Set `"schemas": ["does_not_exist"]`. **Expected:** `404 SCHEMA_NOT_FOUND`.

---

### T-104 — Rayfin UI shell

**Depends on:** T-103 · **Spec:** §8.1 Rayfin Web UI, FR-001, FR-004, FR-021, §7 (React / Next.js, Fluent UI)

#### Problem statement
Business users can't use Swagger. They need a web UI to submit a prompt, choose the data scope, and see where each run stands.

#### Functional requirements
1. A **New run** page has a prompt editor, optional subject area, desired outputs and constraints, and a workspace/Lakehouse selector.
2. A **Runs** page lists runs with their state and created time.
3. A **Run detail** page shows the prompt, scope, current state, next action, open questions and a state timeline (FR-021).

#### API contracts
App folder: `rayfin-ui/` (Next.js, TypeScript, Fluent UI v9). Start it with `npm run dev` on port 3000.

| Route | Calls |
|---|---|
| `/runs/new` | `GET /fabric/workspaces`, `GET /fabric/workspaces/{id}/lakehouses`, `POST /runs`, `PUT /runs/{id}/scope` |
| `/runs` | `GET /runs` |
| `/runs/[id]` | `GET /runs/{id}` |

Setting: `NEXT_PUBLIC_API_BASE_URL`, defaulting to `http://localhost:8000`, in `rayfin-ui/.env.local`, which is gitignored.

#### Constraints
- No business logic in the UI: it displays what the API returns, including `next_action`.
- The run detail page shows the current state, the next action and the blocker above the fold at 1366×768.
- Accessible: keyboard navigable, with labels on every input.

#### Edge cases and error handling
| Case | Expected behavior |
|---|---|
| API not reachable | An error banner with a retry button. The typed prompt is kept. |
| Workspace has no Lakehouses | The selector shows "No Lakehouses in this workspace", and submit is disabled. |
| No runs yet | An empty state with a "Create your first run" link. |
| `422` from the API | The field-level message is shown next to the input. |
| Slow API (over 1s) | A loading indicator is shown. Buttons are disabled while a request is in flight. |

#### Acceptance criteria
1. **Create through the UI.** Open `http://localhost:3000/runs/new`, enter a prompt, choose a workspace and Lakehouse, and submit. **Expected:** you land on `/runs/<id>`, with state `CREATED`, the selected scope and "Compile requirement" as the next action.
2. **Listed.** Open `/runs`. **Expected:** the new run is at the top.
3. **One-screen status.** On run detail at 1366×768. **Expected:** the state, next action and timeline are visible without scrolling.
4. **API down.** Stop the API and submit a new run. **Expected:** an error banner, and the prompt text is still in the editor.
5. **Validation shown.** Submit an empty prompt. **Expected:** an inline message on the prompt field.

---

### T-105 — Entra authentication

**Depends on:** T-104 · **Spec:** NFR-001, §14, FR-004, FR-018 (attributable actions)

#### Problem statement
The API is unauthenticated and acts with the developer's own credential, so anyone with network access could use it. FR-004 requires showing only the resources that **the signed-in user** can access, and FR-018 requires every action to be attributable to a user.

#### Functional requirements
1. Rayfin signs users in with Microsoft Entra ID (MSAL).
2. The API rejects requests without a valid bearer token.
3. The API calls Fabric **on behalf of** the signed-in user (OBO flow). Workspace and Lakehouse lists therefore reflect that user's access.
4. Runs record `created_by`, and history entries record `actor` as the user's UPN.

#### API contracts
- App registrations:
  - `rayfin-ui`: SPA, with redirect URI `http://localhost:3000`.
  - `nexora-api`: exposes the scope `api://<api-client-id>/access_as_user`, and has delegated Fabric permissions for OBO.
- API settings, added to `.env.example` with empty values: `ENTRA_TENANT_ID`, `ENTRA_API_CLIENT_ID`, `ENTRA_API_CLIENT_SECRET` (moved to Key Vault in T-705).
- UI settings: `NEXT_PUBLIC_ENTRA_TENANT_ID`, `NEXT_PUBLIC_ENTRA_CLIENT_ID`, `NEXT_PUBLIC_API_SCOPE`.
- Every endpoint except `GET /health` requires `Authorization: Bearer <token>`.
- The validated principal is `{oid, upn, name}`. FastAPI handlers receive it through `Depends(current_user)`.

#### Constraints
- Validate the token's signature (tenant JWKS, cached), issuer, audience (`ENTRA_API_CLIENT_ID`), expiry and the `access_as_user` scope.
- No bypass flag. The CLI keeps working because it calls the store directly, not the API.
- Never log tokens.

#### Edge cases and error handling
| Case | Expected behavior |
|---|---|
| No `Authorization` header | `401 UNAUTHENTICATED`. |
| Token expired | `401 TOKEN_EXPIRED`. The UI refreshes silently and retries once. |
| Token for the wrong audience or tenant | `401 UNAUTHENTICATED`. |
| OBO fails with `interaction_required` or consent missing | `403 CONSENT_REQUIRED`, with a message telling the user to consent. |
| User has no Fabric workspaces | `200 []`. The UI shows "You don't have access to any Fabric workspace". |

#### Acceptance criteria
1. **Sign-in required.** Open Rayfin in a private browser window. **Expected:** you're redirected to Microsoft sign-in.
2. **Attribution.** Sign in and create a run. **Expected:** run detail shows **Created by: \<your UPN\>**, and the first history entry's `actor` is your UPN.
3. **API rejects anonymous calls.** Run `curl -i http://localhost:8000/runs`. **Expected:** `401` with `UNAUTHENTICATED`.
4. **Health stays open.** Run `curl http://localhost:8000/health`. **Expected:** `200`.
5. **Per-user resources.** Sign in as a second test user with access to fewer workspaces. **Expected:** the workspace selector shows only that user's workspaces.
6. **M1 exit.** As an authenticated user, create a run with a scope and open its detail page. **Expected:** this works end to end without Swagger or the CLI.
