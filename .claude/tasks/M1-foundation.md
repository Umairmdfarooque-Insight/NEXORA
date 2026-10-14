# M1 — Foundation

**Exit deliverable:** user can initiate and inspect a run.

---

### T-101 — Run model, state machine and run store

**Depends on:** T-001 · **Spec:** FR-001, FR-021, §11 Workflow State Model, `RunManifest.json` (§10), NFR-003

**Build**
- `app/workflow/states.py`: the 15 states from §11, and an explicit table of allowed transitions. Example: `CREATED → NEEDS_CLARIFICATION | REQUIREMENT_APPROVED`, and any state can go to `NEEDS_INPUT`.
- `app/workflow/run.py`: a `Run` model with run ID (UUID), prompt, subject area, desired outputs, constraints, state, created_at and history of transitions.
- `app/store/`: a `RunStore` interface plus a `FileRunStore` that writes `runs/<run_id>/RunManifest.json`. Add `runs/` to `.gitignore`.
- A transition function that rejects disallowed transitions with a clear error and records each allowed one (from, to, timestamp, reason).
- CLI: `python -m app.cli runs create --prompt "..."`, `runs list`, `runs show <id>`, `runs transition <id> <STATE>`.

**Manual test**
1. Run `python -m app.cli runs create --prompt "Total sales by month"`. **Expected:** prints a new run ID, and `runs/<id>/RunManifest.json` exists with state `CREATED`.
2. Run it again with the same prompt. **Expected:** a **different** run ID (FR-001: each prompt creates a uniquely identified run).
3. Run `runs transition <id> DEPLOYING`. **Expected:** an error saying `CREATED → DEPLOYING` is not allowed, and the state is unchanged.
4. Run `runs transition <id> NEEDS_CLARIFICATION`, then `runs show <id>`. **Expected:** the state and a history entry with a timestamp.
5. Delete the Python process and run `runs show <id>`. **Expected:** the state persists.

**Done when:** illegal transitions are impossible and every transition is recorded.

---

### T-102 — Orchestration API skeleton

**Depends on:** T-101 · **Spec:** FR-001, FR-021, §7 (API and orchestration layer), NFR-005

**Build**
- `app/api/main.py` (FastAPI), with these endpoints:
  - `POST /runs`, with body `{prompt, subject_area?, desired_outputs?, constraints?}`, returns the created run.
  - `GET /runs` and `GET /runs/{id}`, which return the state, history, open questions (empty for now) and `next_action`.
  - `GET /runs/{id}/artifacts`, which lists the artifact files in the run folder.
- Start it with `uvicorn app.api.main:app --reload`.
- Errors return JSON: `404` for an unknown run, `409` for an illegal transition, `422` for invalid input.

**Manual test**
1. Start the API and open `http://localhost:8000/docs`. **Expected:** Swagger lists all the endpoints.
2. Call `POST /runs` with `{"prompt": "Sales by product category"}`. **Expected:** `201`, a run ID and state `CREATED`.
3. Call `GET /runs/{id}`. **Expected:** the same run, with a `next_action` such as "Compile requirement".
4. Call `POST /runs` with `{"prompt": ""}`. **Expected:** `422`.
5. Call `GET /runs/does-not-exist`. **Expected:** `404`.

**Done when:** runs can be created and inspected through the API alone.

---

### T-103 — Workspace and Lakehouse selection

**Depends on:** T-102 · **Spec:** FR-004, §14 (authorize by workspace and Lakehouse)

**Build**
- Add these endpoints, using the Fabric REST API with the signed-in identity:
  - `GET /fabric/workspaces`, which calls `GET https://api.fabric.microsoft.com/v1/workspaces`.
  - `GET /fabric/workspaces/{id}/lakehouses`, which calls `GET .../v1/workspaces/{id}/lakehouses`.
- `PUT /runs/{id}/scope`, with body `{workspace_id, lakehouse_id}`. It verifies that the identity can see both IDs, then stores them in `RunManifest.json`.
- Connectors read the workspace and Lakehouse from the **run scope**. `.env` `FABRIC_*` values become defaults only.

**Manual test**
1. Call `GET /fabric/workspaces`. **Expected:** only the workspaces you can access in the Fabric portal. Compare against the portal list.
2. Pick a workspace and call `GET /fabric/workspaces/{id}/lakehouses`. **Expected:** matches the Lakehouses shown in that workspace.
3. Call `PUT /runs/{id}/scope` with valid IDs, then `GET /runs/{id}`. **Expected:** the scope is shown.
4. Call `PUT /runs/{id}/scope` with a random GUID. **Expected:** `403` or `404`, and the scope is not saved.

**Done when:** a run can be bound to a workspace and Lakehouse the user can access, and to no others.

---

### T-104 — Rayfin UI shell

**Depends on:** T-103 · **Spec:** §8.1 Rayfin Web UI, FR-001, FR-004, FR-021, §7 (React / Next.js, Fluent UI)

**Build**
- A `rayfin-ui/` Next.js app using Fluent UI, which calls the API, with:
  - **New run** page: business-prompt editor plus optional subject area, desired outputs and constraints, and a workspace/Lakehouse selector.
  - **Runs** page: list of runs with state and created time.
  - **Run detail** page: current stage, a state timeline from the history, open questions and the next action (FR-021).

**Manual test**
1. Run `npm run dev` and open `http://localhost:3000`.
2. Create a run with a prompt, a workspace and a Lakehouse. **Expected:** you're redirected to run detail, showing state `CREATED` and the selected scope.
3. Go to Runs. **Expected:** the new run is listed.
4. On run detail, check that the current state and the next action are visible without scrolling (FR-021: one screen shows current state and blocker).

**Done when:** a user can start and inspect a run without using Swagger.

---

### T-105 — Entra authentication

**Depends on:** T-104 · **Spec:** NFR-001, §14, FR-018 (attributable actions)

**Build**
- Register Entra app(s) for the UI and the API.
- In the UI, add MSAL sign-in. The API validates bearer tokens on every endpoint.
- The API calls Fabric **on behalf of** the signed-in user (OBO flow), so FR-004 shows that user's resources, not the service's.
- Every run records `created_by` (user object ID and UPN).

**Manual test**
1. Open the UI in a private window. **Expected:** you're redirected to Microsoft sign-in.
2. Sign in and create a run. **Expected:** run detail shows **Created by** with your UPN.
3. Call `GET /runs` from Swagger or curl **without** a token. **Expected:** `401`.
4. Sign in as a second test user who has access to fewer workspaces. **Expected:** the workspace selector shows only that user's workspaces.

**Done when (M1 exit):** an authenticated user can initiate and inspect a run, scoped to resources they can access.
