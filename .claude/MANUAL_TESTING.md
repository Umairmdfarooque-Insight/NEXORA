# Manual testing guide

How to test each Nexora task by hand. A task is `Done` only after its checks here pass (`/implement-task done T-xxx`).

**This file is updated every time a task is implemented.** `/implement-task` adds or refreshes the task's section here at hand-over (see [Adding a task](#adding-a-task)). Acceptance criteria are defined in `.claude/tasks/`; this file holds the exact commands.

## Before you start

- Windows, PowerShell, Python 3.12. Run everything from the **project root**: `cd C:\Users\umdfaroo\Downloads\Nexora_V1\Nexora_V1`. Python only finds the `app` package from there.
- Activate the virtualenv: `.venv\Scripts\activate`. If it fails with `No Python at ...`, recreate it: `py -3.12 -m venv .venv`, then `pip install -r requirements.txt`.
- `.env` must exist (copy `.env.example`) with real values. Never paste its values into chat or commit it.
- If a test tells you to edit `.env` (comment out a line, blank a value), **restore it afterwards**.
- Tests marked 🌐 need a live Azure/Fabric sign-in (browser). Tests marked 💻 run offline.

---

## M0 — Baseline

### T-001 — Fix dependencies and configuration loading

1. 💻 **Clean install.** `Remove-Item -Recurse -Force .venv; py -3.12 -m venv .venv; .venv\Scripts\activate; pip install -r requirements.txt`. **Expected:** no errors.
2. 💻 **Defaults load.** `python -c "import app.config as c; print(c.APP_NAME)"`. **Expected:** `Nexora`.
3. 💻 **Missing setting.** In `.env`, put `#` at the very start of the `AZURE_OPENAI_API_KEY` line (or leave its value empty), then repeat step 2. **Expected:** `ValueError: Missing required configuration: AZURE_OPENAI_API_KEY. Check your .env file.` with no key shown. **Restore the line.** (Setting the value to `#` does *not* count, since `#` is a valid value.)
4. 💻 **Whitespace value.** Set `AZURE_OPENAI_DEPLOYMENT=   ` and repeat step 2. **Expected:** the same error, naming `AZURE_OPENAI_DEPLOYMENT`. **Restore it.**
5. 💻 **Directory-independent.** `cd C:\` then `python -c "import sys; sys.path.insert(0, r'C:\Users\umdfaroo\Downloads\Nexora_V1\Nexora_V1'); import app.config as c; print(c.ENVIRONMENT)"`. **Expected:** the `ENVIRONMENT` value from `.env`. Then `cd` back to the project root.
6. 💻 **Imports work.** From the project root: `python -c "import app.test_llm, app.test_fabric_sql, app.test_metadata_inventory"`. **Expected:** no output and no error.

### T-002 — Share one Azure credential across connectors

1. 🌐 **One sign-in per process.** `python -m app.manual_tests.t002_check`. **Expected:** the browser sign-in appears **once**, then the table count and `Connected successfully.` print.
2. 🌐 **Cache reused.** Run the same command again within an hour. **Expected:** no sign-in prompt (an account picker is acceptable). If it still prompts, delete `%LOCALAPPDATA%\.IdentityService\nexora_auth_record.json` and retry from step 1.
3. 💻 **Same instance.** `python -c "from app.auth import get_credential as g; print(g() is g())"`. **Expected:** `True`.

### T-003 — Environment smoke-check command

1. 🌐 **All pass.** `python -m app.tools.smoke`, then `echo $LASTEXITCODE`. **Expected:** three `PASS` lines (`llm`, `lakehouse`, `sql`) and `0`. A first-time browser sign-in counts against the 30-second limit per check; run again if it times out.
2. 🌐 **One failure is isolated.** `$env:FABRIC_SQL_SERVER="invalid.example.com"; python -m app.tools.smoke; echo $LASTEXITCODE`. **Expected:** `FAIL sql` with a readable reason, `llm` and `lakehouse` still `PASS`, exit `1`. Then `Remove-Item Env:FABRIC_SQL_SERVER`.
3. 🌐 **Single check.** `python -m app.tools.smoke --only llm --json`. **Expected:** JSON containing only the `llm` check.
4. 💻 **Bad option.** `python -m app.tools.smoke --only foo; echo $LASTEXITCODE`. **Expected:** `Invalid --only value: 'foo'. Valid checks: llm, lakehouse, sql` and exit `2`.

### T-004 — Test fixtures in the sandbox Lakehouse

Run the SQL checks in the Lakehouse **SQL endpoint** of the sandbox.

1. 🌐 **Tables exist.** Import `fixtures/create_test_tables.ipynb` into the sandbox workspace, attach the sandbox Lakehouse (schemas enabled, with `saleslt`) as the default, and run all cells. **Expected:** the last cell prints `All fixture checks passed.` and five tables appear under `nexora_test`.
2. 🌐 **Duplicates present.** `SELECT ProductID, COUNT(*) c FROM nexora_test.dim_product_dupes GROUP BY ProductID HAVING COUNT(*) > 1`. **Expected:** at least 3 rows (4 with the shipped notebook).
3. 🌐 **Bridge is unique.** `SELECT ProductID, PromotionID, COUNT(*) FROM nexora_test.bridge_product_promotion GROUP BY ProductID, PromotionID HAVING COUNT(*) > 1`. **Expected:** 0 rows.
4. 🌐 **Keys join to real data.** `SELECT COUNT(*) FROM nexora_test.bridge_product_promotion b LEFT JOIN saleslt.SalesLT_Product p ON b.ProductID = p.ProductID WHERE p.ProductID IS NULL`. **Expected:** `0`.
5. 🌐 **Date coverage.** `SELECT COUNT(*) FROM saleslt.SalesLT_SalesOrderHeader h LEFT JOIN nexora_test.dim_date d ON CAST(h.OrderDate AS date) = d.Date WHERE d.Date IS NULL`. **Expected:** `0`.
6. 🌐 **Rerunnable.** Run the notebook again, then repeat steps 2 and 3. **Expected:** the same results and unchanged row counts.
7. 🌐 **Visible to the harvester.** `python -m app.test_metadata_inventory nexora_test`. **Expected:** all five tables listed with their columns.

---

## M1 — Foundation

### T-101 — Run model, state machine and run store

Steps 1–7 and 11, 13 and 14 run offline with the file store (`RUN_STORE=file`, the default). Replace `<id>` with the `run_id` printed by step 1. Steps 8–10 and 12 need a writable Fabric SQL Database in the sandbox workspace; fill `FABRIC_CONTROL_DB_SERVER` and `FABRIC_CONTROL_DB_NAME` in `.env` first.

1. 💻 **Create.** `python -m app.cli runs create --prompt "Total sales by month"`. **Expected:** a UUID is printed, and `runs\<id>\RunManifest.json` exists with `"state": "CREATED"` and one history entry.
2. 💻 **Unique IDs.** Repeat step 1. **Expected:** a different `run_id`.
3. 💻 **Illegal transition blocked.** `python -m app.cli runs transition <id> DEPLOYING; echo $LASTEXITCODE`. **Expected:** `CREATED → DEPLOYING is not allowed`, exit `1`, and `runs show <id>` still shows `CREATED`.
4. 💻 **Legal transition recorded.** `python -m app.cli runs transition <id> NEEDS_CLARIFICATION --reason test`, then `python -m app.cli runs show <id>`. **Expected:** state `NEEDS_CLARIFICATION`, and a second history entry with reason `test` and a timestamp.
5. 💻 **Needs-input resume.** `python -m app.cli runs transition <id> NEEDS_INPUT`, then `runs show <id>`. **Expected:** `resume_state` is `NEEDS_CLARIFICATION`. Then `python -m app.cli runs transition <id> RESUME`. **Expected:** the state is `NEEDS_CLARIFICATION` again and `resume_state` is `null`.
6. 💻 **Persistence.** Close the terminal, open a new one (activate the venv), and run `python -m app.cli runs show <id>`. **Expected:** the same state and history.
7. 💻 **Offline checks.** `python -m app.manual_tests.t101_offline_checks`. **Expected:** only `PASS` lines and `All checks passed.` (the SQL store runs against an in-memory SQLite stand-in, so this checks its logic, not Fabric access).
8. 🌐 **Fabric SQL store, create and read.** In `.env` set `RUN_STORE=fabric_sql`. Run `python -m app.cli runs create --prompt "Total sales by month"`, then `runs list` and `runs show <id>`. **Expected:** a UUID, the run listed, and its manifest shown. In the database, `SELECT run_id, state FROM dbo.nexora_runs` returns the same run.
9. 🌐 **Fabric SQL store, same rules.** With `RUN_STORE=fabric_sql`, repeat steps 3, 4 and 5 on the new run. **Expected:** the same results as the file store, and the `state` column in `dbo.nexora_runs` matches `runs show`.
10. 🌐 **Fabric SQL store, persistence.** Open a new terminal and run `runs show <id>`. **Expected:** the same state and history. Runs from the file store are not listed.
11. 💻 **Missing setting.** With `RUN_STORE=fabric_sql`, blank `FABRIC_CONTROL_DB_NAME` and run `python -m app.cli runs list; echo $LASTEXITCODE`. **Expected:** `Missing required configuration: FABRIC_CONTROL_DB_NAME`, exit `2`. **Restore it.**
12. 🌐 **Unreachable database.** With `RUN_STORE=fabric_sql`, set `FABRIC_CONTROL_DB_SERVER=invalid.example.com` and run `runs list; echo $LASTEXITCODE`. **Expected:** a readable "Cannot connect" message, exit `1`, no traceback. **Restore it.**
13. 💻 **Bad store name.** `$env:RUN_STORE="nope"; python -m app.cli runs list; echo $LASTEXITCODE`, then `Remove-Item Env:RUN_STORE`. **Expected:** `Invalid RUN_STORE: 'nope'. Valid values: file, fabric_sql`, exit `2`.
14. 💻 **Clean up.** Set `RUN_STORE=file` in `.env` and delete the `runs\` folder. Optionally remove test rows with `DELETE FROM dbo.nexora_runs` in the sandbox database.

### T-102 — Orchestration API skeleton

> **Since T-105 every call except `/health` needs a bearer token.** In Swagger click **Authorize** and paste one; with curl add `-H "Authorization: Bearer <token>"`. See "Getting a token for curl or Swagger" in the T-105 section. Without a token you get HTTP 401.

Start the API in one terminal (leave it running): `uvicorn app.api.main:app --reload --port 8000`. It uses the store from `RUN_STORE` (default `file`). In a second terminal use the commands below, or the Swagger page at <http://localhost:8000/docs>. In PowerShell use `curl.exe` (plain `curl` is an alias for something else).

1. 💻 **Health.** `curl.exe http://localhost:8000/health`. **Expected:** `{"status":"ok","app":"Nexora","version":"<git sha or 0.0.0>"}`.
2. 💻 **Create.** `curl.exe -X POST http://localhost:8000/runs -H "Content-Type: application/json" -d "{\"prompt\":\"Total sales by month\"}"`. **Expected:** HTTP 201 with the full run: `"state":"CREATED"`, `"next_action":"Compile requirement"`, `"open_questions":[]`, and one history entry.
3. 💻 **List.** `curl.exe http://localhost:8000/runs`. **Expected:** `{"items":[...],"total":N}` where each item has `run_id`, `state`, `prompt_preview`, `created_at` and `created_by`, newest first.
4. 💻 **Read.** `curl.exe http://localhost:8000/runs/<run_id>`. **Expected:** the same run as step 2.
5. 💻 **Artifacts.** `curl.exe http://localhost:8000/runs/<run_id>/artifacts`. **Expected:** `[]` for a new run.
6. 💻 **Next action follows state.** `python -m app.cli runs transition <run_id> NEEDS_CLARIFICATION`, then repeat step 4. **Expected:** `"next_action":"Answer open questions"`. (With `RUN_STORE=file` the CLI and API share the same `runs\` folder.)
7. 💻 **Validation errors.** `curl.exe -i -X POST http://localhost:8000/runs -H "Content-Type: application/json" -d "{\"prompt\":\"   \"}"`. **Expected:** HTTP 422 and `{"error":{"code":"VALIDATION_ERROR","message":"Invalid prompt: ...","details":{...}}}`. Repeat with `-d "{}"` (same result), and with `http://localhost:8000/runs?limit=201`, `?limit=0` and `?state=BOGUS` (422 each; the `state` message lists the valid states).
8. 💻 **Unknown run.** `curl.exe -i http://localhost:8000/runs/00000000-0000-4000-8000-000000000000`. **Expected:** HTTP 404 and `"code":"RUN_NOT_FOUND"`.
9. 💻 **No transition endpoint.** Open <http://localhost:8000/docs>. **Expected:** the page loads, and the only endpoints are `GET /health`, `POST /runs`, `GET /runs`, `GET /runs/{run_id}` and `GET /runs/{run_id}/artifacts`. Nothing changes a run's state.
10. 💻 **CORS.** `curl.exe -i http://localhost:8000/health -H "Origin: http://localhost:3000"`. **Expected:** the response has `access-control-allow-origin: http://localhost:3000`. With `-H "Origin: http://evil.example.com"` the header is absent.
11. 💻 **Persistence across restarts.** Stop uvicorn (Ctrl+C), start it again, and repeat step 4. **Expected:** the same run.
12. 💻 **Unhandled error stays generic.** Covered by the offline checks (step 13); there is no safe way to trigger a 500 by hand.
13. 💻 **Offline checks.** `python -m app.manual_tests.t102_offline_checks`. **Expected:** only `PASS` lines and `All checks passed.` (one "Unhandled error" traceback in the log is expected).
14. 🌐 **Fabric SQL store behind the API (optional).** Stop uvicorn, set `RUN_STORE=fabric_sql` with the `FABRIC_CONTROL_DB_*` values, start it again, and repeat steps 2–4. **Expected:** the same results, and the run appears in `dbo.nexora_runs`. If the database is unreachable the API returns 502 `UPSTREAM_ERROR` with a generic message. **Restore `RUN_STORE=file` afterwards.**
15. 💻 **Clean up.** Stop uvicorn, set `RUN_STORE=file` in `.env`, and delete the `runs\` folder.

---

### T-103 — Workspace and Lakehouse selection

> **Since T-105 every call except `/health` needs a bearer token.** In Swagger click **Authorize** and paste one; with curl add `-H "Authorization: Bearer <token>"`. See "Getting a token for curl or Swagger" in the T-105 section. Without a token you get HTTP 401.

Start the API in one terminal (leave it running): `uvicorn app.api.main:app --reload --port 8000`. The first call that reaches Fabric opens a browser sign-in in that terminal's process. Use `curl.exe` (not `curl`) in PowerShell, or the Swagger page at <http://localhost:8000/docs>. Create a run first: `curl.exe -X POST http://localhost:8000/runs -H "Content-Type: application/json" -d "{\"prompt\":\"Total sales by month\"}"`, and note its `run_id`. Use the sandbox workspace.

1. 🌐 **Workspaces match the portal.** `curl.exe http://localhost:8000/fabric/workspaces`. **Expected:** a list of `{"id","display_name","type"}` that matches the workspaces you see in the Fabric portal. Note the sandbox workspace `id`.
2. 🌐 **Lakehouses match.** `curl.exe http://localhost:8000/fabric/workspaces/<workspace_id>/lakehouses`. **Expected:** the same Lakehouses as the portal, each with `sql_endpoint` `{"server","database"}` filled in (`null` only for a Lakehouse whose SQL endpoint isn't ready). Note the `id` of the sales Lakehouse.
3. 🌐 **Bind scope.** `curl.exe -X PUT http://localhost:8000/runs/<run_id>/scope -H "Content-Type: application/json" -d "{\"workspace_id\":\"<workspace_id>\",\"lakehouse_id\":\"<lakehouse_id>\",\"schemas\":[\"saleslt\"]}"`, then `curl.exe http://localhost:8000/runs/<run_id>`. **Expected:** HTTP 200, and `scope` shows both IDs, `lakehouse_name`, `workspace_name`, `schemas: ["saleslt"]` and the `sql_endpoint`. The state stays `CREATED`.
4. 🌐 **Invalid ID refused.** Repeat step 3 with `"workspace_id":"99999999-9999-4999-8999-999999999999"`, then `GET /runs/<run_id>`. **Expected:** HTTP 403 and `"code":"FORBIDDEN"`; `scope` is unchanged from step 3. Repeat with a random `lakehouse_id` for the right workspace: also 403.
5. 🌐 **Bad schema.** Repeat step 3 with `"schemas":["does_not_exist"]`. **Expected:** HTTP 404, `"code":"SCHEMA_NOT_FOUND"`, and the message names `does_not_exist`. `scope` is unchanged.
6. 💻 **Bad input.** Repeat step 3 with `"workspace_id":"abc"`. **Expected:** HTTP 422 `VALIDATION_ERROR`. Use an unknown run ID in the URL: HTTP 404 `RUN_NOT_FOUND`.
7. 🌐 **Scope locks.** `python -m app.cli runs transition <run_id> REQUIREMENT_APPROVED`, then repeat step 3. **Expected:** HTTP 200 (no metadata inventory exists yet). Then `python -m app.cli runs transition <run_id> DATA_PROFILED` and repeat step 3. **Expected:** HTTP 409 `SCOPE_LOCKED`.
8. 🌐 **Connectors use the scope.** With the scope from step 3 (run this before step 7 if you want to keep the run in `CREATED`; the scope is stored either way), run `python -m app.manual_tests.t103_connectors_check <run_id>`. **Expected:** the Lakehouse's catalog name and its schema list (including `saleslt`), then `Connected successfully.` for the scope's SQL endpoint.
9. 💻 **`.env` fallback still works.** `python -m app.tools.smoke --only lakehouse`. **Expected:** `PASS lakehouse` (scripts without a run still use the `.env` values).
10. 💻 **Offline checks.** `python -m app.manual_tests.t103_offline_checks`. **Expected:** only `PASS` lines and `All checks passed.` (one logged "Fabric error" line is expected). This covers paging, 429 retries, 5xx, timeouts, the locking rules and the connector factories with a fake Fabric.
11. 💻 **Clean up.** Stop uvicorn and delete the `runs\` folder.

---

### T-104 — Rayfin UI shell

> **Since T-105 the UI signs you in first.** Set the `NEXT_PUBLIC_ENTRA_*` values (see the T-105 setup) before these steps; the pages open after you sign in with Microsoft.

Needs Node.js 20 or later (checked with 24) and two terminals. Run the API from the project root, and the UI from `rayfin-ui\`. Steps 1 and 10 need the live Fabric sign-in; the rest work with no Fabric access (the workspace list just stays empty).

**One-time setup:** `cd rayfin-ui; npm install` (the UI reads `NEXT_PUBLIC_API_BASE_URL`, default `http://localhost:8000`; to change it, copy `.env.local.example` to `.env.local`).

**Start:** terminal 1: `.venv\Scripts\activate; uvicorn app.api.main:app --port 8000`. Terminal 2: `cd rayfin-ui; npm run dev`, then open <http://localhost:3000>. If the page shows HTTP 426 or a blank error, another program is holding port 3000 (on one machine `AMAgent.exe` did); stop it, because the API only allows the origin `http://localhost:3000`.

1. 🌐 **Create through the UI.** Open <http://localhost:3000/runs/new>, type a prompt (for example `Total sales by month`), choose your sandbox workspace and Lakehouse, and click **Create run**. **Expected:** you land on `/runs/<id>` showing state `CREATED`, the chosen workspace, Lakehouse and SQL endpoint under "Data scope", and "Compile requirement" as the next action.
2. 💻 **Create without a data scope.** On `/runs/new`, enter a prompt and leave the workspace empty, then submit. **Expected:** you land on the run page with "No data scope selected yet."
3. 💻 **Listed.** Open <http://localhost:3000/runs>. **Expected:** the new run is at the top, with its state badge, created time and prompt text. The run id links to the detail page.
4. 💻 **One-screen status.** Open a run's detail page with the browser window at 1366×768 (in Edge or Chrome: F12, device toolbar, set 1366×768; or just use a 1366×768 screen). **Expected:** the state, next action, open questions, prompt, scope and timeline are visible without scrolling.
5. 💻 **API down.** Stop the API (Ctrl+C in terminal 1). On `/runs/new` type a prompt and click **Create run**. **Expected:** a red banner "Couldn't create the run." saying it can't reach the API, with a **Retry** button; the prompt text is still in the editor. Start the API again and click **Retry**: you land on the new run.
6. 💻 **Validation shown.** On `/runs/new`, leave the prompt empty and click **Create run**. **Expected:** an inline message under the prompt field (`Invalid`-style text from the API, such as "String should have at least 1 character"). No run is created.
7. 💻 **Empty state.** Stop the API, delete the `runs\` folder (or set `RUN_STORE` to an empty store), start the API, and open `/runs`. **Expected:** "No runs yet." and a "Create your first run" link.
8. 💻 **Error banner with retry on the list.** Stop the API and reload `/runs`. **Expected:** a banner "Couldn't load runs." with **Retry**. Start the API and click **Retry**: the list appears.
9. 💻 **Run not found.** Open <http://localhost:3000/runs/does-not-exist>. **Expected:** "Run not found: does-not-exist" and a link back to the runs list.
10. 🌐 **No Lakehouses.** Pick a workspace that has no Lakehouse (if you have one). **Expected:** the Lakehouse field shows "No Lakehouses in this workspace" and **Create run** is disabled.
11. 💻 **Keyboard and labels.** On `/runs/new`, press Tab through the page. **Expected:** focus moves in order through the nav links, prompt, subject area, outputs, constraints, workspace, Lakehouse and the button, each with a visible focus ring and a label.
12. 💻 **Unit tests and build.** `cd rayfin-ui; npm test; npm run typecheck; npm run build`. **Expected:** 5 passing tests, no type errors, and a successful build listing `/runs`, `/runs/new` and `/runs/[id]`.
13. 💻 **Clean up.** Stop both servers (Ctrl+C) and delete the `runs\` folder.

---

### T-105 — Entra authentication

**One-time Entra setup** (an admin or app owner does this in the Azure portal, Microsoft Entra ID, *App registrations*). Use a tenant where you can test with at least two users.

1. **`nexora-api` registration.**
   - *New registration*, single tenant, no redirect URI. Note the **Application (client) ID** and **Directory (tenant) ID**.
   - *Expose an API*: set the Application ID URI to `api://<api-client-id>`, then *Add a scope* named `access_as_user` (who can consent: Admins and users).
   - *Certificates & secrets*: create a client secret and copy its **value** now.
   - *API permissions* → *Add a permission* → *Delegated*: **Power BI Service** (this is Fabric): `Workspace.Read.All` and `Lakehouse.Read.All` (or `Item.Read.All`); and **Azure Storage**: `user_impersonation`. Grant admin consent if you can.
2. **`rayfin-ui` registration.**
   - *New registration*, single tenant. Note its **Application (client) ID**.
   - *Authentication* → *Add a platform* → **Single-page application**, redirect URI `http://localhost:3000`.
   - *API permissions* → *My APIs* → `nexora-api` → delegated `access_as_user`.
3. **Let users consent once.** Easiest: on `nexora-api` → *Manifest*, add the `rayfin-ui` client ID to `knownClientApplications`, or grant admin consent for both apps. Without it, users get the `CONSENT_REQUIRED` message in step 8.
4. **Fill in the settings** (names are in `.env.example` and `rayfin-ui/.env.local.example`; never paste the values into chat or commit them):
   - `.env`: `ENTRA_TENANT_ID`, `ENTRA_API_CLIENT_ID` (the `nexora-api` client ID), `ENTRA_API_CLIENT_SECRET`.
   - `rayfin-ui/.env.local`: `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`, `NEXT_PUBLIC_ENTRA_TENANT_ID`, `NEXT_PUBLIC_ENTRA_CLIENT_ID` (the `rayfin-ui` client ID), `NEXT_PUBLIC_API_SCOPE=api://<api-client-id>/access_as_user`.
5. **Install and start.** `pip install -r requirements.txt` (adds `PyJWT[crypto]` and `msal`). Terminal 1: `.venv\Scripts\activate; uvicorn app.api.main:app --port 8000`. Terminal 2: `cd rayfin-ui; npm install; npm run dev` (restart it after editing `.env.local`).

**Getting a token for curl or Swagger** (needed for the T-102 and T-103 steps from now on): sign in to <http://localhost:3000>, open the browser dev tools (F12) → *Network*, click any request to `localhost:8000`, and copy the part of the `Authorization` request header after `Bearer `. It is valid for about an hour. In Swagger (<http://localhost:8000/docs>) click **Authorize** and paste it; for curl use `-H "Authorization: Bearer <token>"`. Treat it like a password.

1. 🌐 **Sign-in required.** Open <http://localhost:3000> in a private (InPrivate/Incognito) window. **Expected:** you are redirected to the Microsoft sign-in page, and after signing in you land on `/runs`. The header shows your name and **Sign out**.
2. 🌐 **Attribution.** Create a run on `/runs/new`. **Expected:** the run detail page shows **Created by: \<your UPN\>**. Then `python -m app.cli runs show <run_id>`: `created_by` holds your `oid`, `upn` and `name`, and the first `history` entry's `actor` is your UPN.
3. 💻 **API rejects anonymous calls.** `curl.exe -i http://localhost:8000/runs`. **Expected:** HTTP 401 and `"code":"UNAUTHENTICATED"`, with a `www-authenticate: Bearer` header. Also `curl.exe -i -X POST http://localhost:8000/runs -H "Content-Type: application/json" -d "{\"prompt\":\"x\"}"` (401) and `curl.exe -i http://localhost:8000/runs -H "Authorization: Bearer abc.def.ghi"` (401, "The access token is not valid").
4. 💻 **Health stays open.** `curl.exe http://localhost:8000/health`. **Expected:** HTTP 200 with no token.
5. 🌐 **Valid token works.** `curl.exe -i http://localhost:8000/runs -H "Authorization: Bearer <token>"`. **Expected:** HTTP 200 with the run list.
6. 🌐 **Per-user resources.** Sign in (private window) as a second test user who can see fewer Fabric workspaces. **Expected:** the workspace dropdown on `/runs/new` lists only that user's workspaces. A user with none sees "You don't have access to any Fabric workspace".
7. 🌐 **M1 exit.** As an authenticated user, create a run with a workspace and Lakehouse, and open its detail page. **Expected:** it works end to end without Swagger or the CLI, and the page shows the scope and "Created by".
8. 🌐 **Consent (optional).** Sign in as a user who hasn't consented and has no admin consent behind the app, then pick a workspace. **Expected:** a red banner with the `CONSENT_REQUIRED` message telling the user to consent, not a crash.
9. 💻 **Fails closed when not configured.** In `.env` blank `ENTRA_TENANT_ID`, restart the API, and run `curl.exe -i http://localhost:8000/runs -H "Authorization: Bearer abc.def.ghi"`. **Expected:** HTTP 500, `"code":"CONFIG_ERROR"`, naming `ENTRA_TENANT_ID`; `/health` is still 200. **Restore the value.** In `rayfin-ui/.env.local` blank `NEXT_PUBLIC_ENTRA_CLIENT_ID`, restart the UI, and open the site. **Expected:** "Sign-in is not configured" naming the setting, with no way to use the app. **Restore it.**
10. 💻 **CLI still works.** `python -m app.cli runs list`. **Expected:** the runs are listed with no sign-in (the CLI calls the store directly).
11. 💻 **Offline checks.** `python -m app.manual_tests.t105_offline_checks`, then `cd rayfin-ui; npm test; npm run typecheck; npm run build`. **Expected:** `All checks passed.`, 11 passing tests, no type errors and a successful build. These cover token validation (expiry, audience, issuer, tenant, scope, forged tokens), OBO errors, attribution, the auth gate on every endpoint, and the silent refresh-and-retry in the UI client.
12. 💻 **Clean up.** Stop both servers, and delete the `runs\` folder if it was only test data.

---

## M2 — Requirement control

### T-201 — BusinessContract schema

1. 💻 **Valid sample.** `python -m app.cli contract validate samples/contract_valid.yaml; echo $LASTEXITCODE`. **Expected:** `VALID` and `0`.
2. 💻 **Missing field.** `Copy-Item samples\contract_valid.yaml $env:TEMP\c2.yaml`, open the copy, set `status: approved` on the first line that says `status: draft` (the contract's own status, near the top), and delete the KPI's `formula_intent:` line. Run `python -m app.cli contract validate $env:TEMP\c2.yaml; echo $LASTEXITCODE`. **Expected:** `INVALID`, a line starting `kpis.0.formula_intent:` and exit `1`. Put the line back and the file is `VALID` again.
3. 💻 **Blocking question prevents approval.** In the copy (contract `status: approved`, `formula_intent` restored), replace `open_questions: []` with:
   ```yaml
   open_questions:
   - id: Q1
     text: How is Revenue defined?
     blocking: true
     source: rule
     status: open
   ```
   **Expected:** `INVALID` with a line naming `open_questions.0` and `Q1`. Change `status: open` to `status: answered` and it is `VALID`. With contract `status: draft` the open question is allowed.
4. 💻 **Round trip.** `python -c "from app.contracts import business_contract as b; print(b.save(b.load('samples/contract_valid.yaml'), r'$env:TEMPt.yaml'))"` then `fc.exe /b samples\contract_valid.yaml $env:TEMPt.yaml`. **Expected:** a `sha256:…` line, then `FC: no differences encountered`.
5. 💻 **Schema export.** `python -m app.cli contract schema --output $env:TEMP\schema.json`, then `python -c "import json,os; d=json.load(open(os.environ['TEMP']+'/schema.json')); print('kpis' in d['properties'])"`. **Expected:** `True`. (`python -m app.cli contract schema` prints the same JSON; with PowerShell's `>` the file would be UTF-16, which is why `--output` exists.) Compare with the committed file: `python -m app.manual_tests.t201_offline_checks` reports it as current.
6. 💻 **Edge cases.** Make a copy each time. (a) Rename `kpis:` to `kpi:`. **Expected:** `kpi: extra field not permitted`. (b) Add `- name: net revenue` right under `kpis:`. **Expected:** a `kpis.1.name` line that also names `kpis.0.name`. (c) Set `schema_version: 2`. **Expected:** `unsupported schema_version 2`. (d) Empty the file. **Expected:** `empty document`. (e) Break the YAML, for example a lone `[` line. **Expected:** a message with `line` and `column`. (f) A path that doesn't exist. **Expected:** `File not found: …`, exit `2`.
7. 💻 **Offline checks.** `python -m app.manual_tests.t201_offline_checks`. **Expected:** `All checks passed.` (38 checks covering all of the above, determinism, UTF-8/LF output, hash and the committed schema file).
8. 💻 **Clean up.** `Remove-Item $env:TEMP\c2.yaml, $env:TEMPt.yaml, $env:TEMP\schema.json -ErrorAction SilentlyContinue`.

---

### T-202 — Requirement Compiler with ambiguity detection

**Before you start:** `pip install -r requirements.txt` (adds `langgraph`). Do the T-105 setup so you have a token (see "Getting a token for curl or Swagger"). Start the API in the terminal you will watch for the log line in step 7: `uvicorn app.api.main:app --port 8000`. In Swagger (<http://localhost:8000/docs>) click **Authorize** and paste the token. The compile steps call the real Azure OpenAI deployment and take a few seconds.

To create a run without the UI, use `POST /runs` in Swagger with `{"prompt": "…"}` and copy the `run_id`.

1. 🌐 **Ambiguous Revenue stops.** Create a run with the prompt `Show revenue by month for 2024`, then `POST /runs/{run_id}/compile`. **Expected:** HTTP 200, `run.state` is `NEEDS_CLARIFICATION`, `blocking_questions` is `1`, and `run.open_questions` has `{"id": "RULE-REVENUE", "text": "How is Revenue defined?", "blocking": true, "source": "rule", …}`. The contract has KPI `Revenue` with `formula_intent: null` and dimension `Month`. In the UI (<http://localhost:3000/runs/{run_id}>) the run shows the question with "(blocking)" and the next action "Answer open questions". Other questions the model adds are fine, as long as none repeats the Revenue question.
2. 🌐 **Explicit definition passes.** Create a run with `Show Net Revenue by month for 2024. Net Revenue = SUM(LineTotal) excluding cancelled orders, in USD.` and compile it. **Expected:** `run.state` is `CREATED`, `blocking_questions` is `0`, no Revenue question, and the KPI `formula_intent` mentions `LineTotal` and the exclusion of cancelled orders.
3. 🌐 **Repeatable structure.** Create two new runs with the step 2 prompt and compile both. **Expected:** the same KPI names, dimensions and set of question texts in both contracts (the wording of `rationale` or `formula_intent` may differ).
4. 💻 **Valid file.** `python -m app.cli contract validate runs\<run_id>\BusinessContract.yaml`. **Expected:** `VALID`.
5. 🌐 **Versioning.** Compile the step 1 run a second time. **Expected:** `runs\<run_id>\contracts\` holds `BusinessContract.v1.yaml` and `BusinessContract.v2.yaml`, `runs\<run_id>\BusinessContract.yaml` equals v2, and `GET /runs/{run_id}/artifacts` lists `BusinessContract` with `version: 2`, `status: draft` and a `sha256:` hash.
6. 🌐 **Wrong state.** Create a run, then `python -m app.cli runs transition <run_id> REQUIREMENT_APPROVED`, then `POST /runs/{run_id}/compile`. **Expected:** HTTP 409 with `"code": "WRONG_STATE"` naming the state, and no `contracts\` folder in that run.
7. 🌐 **Graph boundary.** For the step 1 run, `python -m app.cli runs show <run_id>`. **Expected:** `history` has exactly two entries (`null → CREATED` and `CREATED → NEEDS_CLARIFICATION`), even after the second compile in step 5. In the terminal running uvicorn, each compile logged a line like `INFO: app.graphs.base: stage=compile run_id=<run_id> node_path=llm_compile -> validate_schema -> apply_critical_terms -> apply_locked_facts`.
8. 🌐 **Bad config stops the API.** Stop the API. Rename `config\critical_terms.yaml` to `critical_terms.bak` and start it again. **Expected:** startup fails with `Configuration file critical_terms.yaml is missing`. Rename the file back and restart.
9. 💻 **Offline checks.** `python -m app.manual_tests.t202_offline_checks`. **Expected:** `All checks passed.` (80 checks with a fake LLM: the rules, the retry and the 2-attempt limit, `LLM_INVALID_OUTPUT` with the raw output saved under `logs\`, timeout and content-filter errors, versioning, locked facts, state changes and the log line).
10. 💻 **Clean up.** Stop the API. Delete the test runs' folders under `runs\` if they were only test data.

**Not run by Claude:** the API steps (1–3, 5–8), which need your Entra token. Claude did run the real model once through `compile_requirement` and the stage service in a temporary folder with both step 1 and step 2 prompts, and got the results described above.

---

### T-203 — Clarification loop

**Before you start:** same setup as T-202 (token in Swagger, API running with `uvicorn app.api.main:app --port 8000`). Create a run with `{"prompt": "Show revenue by month for 2024"}` and compile it (`POST /runs/{run_id}/compile`). The answers recompile through the real model, so each takes a few seconds.

1. 🌐 **Answer closes the question.** `POST /runs/{run_id}/questions/RULE-REVENUE/answer` with `{"answer": "Net Revenue = SUM(LineTotal) excluding cancelled orders"}`. **Expected:** HTTP 200 with `run` and `contract`. In the contract, `RULE-REVENUE` has `status: answered` and the `answer`, `locked_facts` has `{"id": "LF-RULE-REVENUE", "source_question_id": "RULE-REVENUE", …}`, and the Revenue KPI's `formula_intent` is the answer text. (The question id is `RULE-REVENUE`, since the rule question is the one that asks how Revenue is defined.)
2. 🌐 **State advances.** `GET /runs/{run_id}`. **Expected:** `state` is `CREATED`, `next_action` is `Compile requirement`, and `open_questions` lists only non-blocking questions, if any. `python -m app.cli runs show <run_id>` shows a `NEEDS_CLARIFICATION → CREATED` entry by your UPN.
3. 🌐 **Locked fact survives.** `POST /runs/{run_id}/compile`. **Expected:** `locked_facts` is unchanged, `RULE-REVENUE` is still answered (not asked again) and the KPI keeps the definition.
4. 🌐 **Dismiss rules.** Create and compile a second run with the same prompt, then `POST /runs/{run_id}/questions/RULE-REVENUE/dismiss` with `{"reason": "skip"}`. **Expected:** `409`, code `QUESTION_CONFLICT`, "blocking questions must be answered". On a run where the model added a non-blocking question (`Q1`), dismiss it with `{"reason": "Out of scope"}`. **Expected:** `200`, the question has `status: dismissed` and the reason, and it no longer appears in `open_questions`. If the model raised no non-blocking question, step 9 covers this with a fake model.
5. 🌐 **Concurrent edit.** Copy `hash` of `BusinessContract` from `GET /runs/{run_id}/artifacts`. `PUT /runs/{run_id}/contract/kpis/Net%20Revenue` (use the KPI's name in the contract; case does not matter) with `{"currency": "EUR", "expected_hash": "sha256:old"}`. **Expected:** `409`, code `STALE_VERSION`. Repeat with the real hash. **Expected:** `200`, only `currency` changed, and a new version file in `runs\<run_id>\contracts\`. Repeat with the first hash again. **Expected:** `409 STALE_VERSION`.
6. 🌐 **Edge cases.** An unknown `qid` or KPI name gives `404 NOT_FOUND`; `{"answer": ""}` gives `422`; re-answering `RULE-REVENUE` gives `200` and replaces the locked fact (the old answer remains in the earlier `contracts\BusinessContract.v<n>.yaml`).
7. 💻 **Edit after approval.** In `runs\<run_id>\BusinessContract.yaml` set `status: approved` (only possible with no blocking question open), then repeat the step 5 request with the current hash. **Expected:** `409 CONTRACT_LOCKED`. Restore the file or discard the run.
8. 💻 **Valid file.** `python -m app.cli contract validate runs\<run_id>\BusinessContract.yaml`. **Expected:** `VALID`.
9. 💻 **Offline checks.** `python -m app.manual_tests.t203_offline_checks`. **Expected:** `All checks passed.` (fake LLM: answer, locked fact, state change, locked fact surviving a recompile and a contradicting model, dismiss rules, re-answer, stale and locked edits, 404/409/422 cases).
10. 💻 **Clean up.** Stop the API and delete the test runs' folders under `runs\` if they were only test data.

**Not run by Claude:** the live steps (1–6), which need your Entra token and the real model.

---

### T-204 — Approval service and Gate G1

**Before you start:** same setup as T-202 and T-203 (token in Swagger, API running with `uvicorn app.api.main:app --port 8000`). Open `config\roles.yaml` and put **your own UPN** (the `upn` of your Entra sign-in; it is the `upn` in `created_by` of a run you create) in the `business_owner` list in place of `user@contoso.com`. The file is committed as-is, so don't commit your real UPN unless you mean to publish it. Roles are read on every request, so no restart is needed after editing.

Create a run with `{"prompt": "Show revenue by month for 2024"}` and compile it (`POST /runs/{run_id}/compile`). Every approval call needs `expected_hash`: copy `hash` of `BusinessContract` from `GET /runs/{run_id}/artifacts` (it changes after each action).

1. 🌐 **Gate blocks.** `POST /runs/{run_id}/approvals` with `{"artifact": "BusinessContract", "action": "ACCEPT", "expected_hash": "<hash>"}` while the Revenue question is open. **Expected:** HTTP 409, code `GATE_FAILED`, `details.failed_checks` containing `G1.2` (and `G1.3`, since the KPI has no definition yet), and `details.gate_result` with each check. The run is still `NEEDS_CLARIFICATION`, there is no `approvals.jsonl`, and `runs\<run_id>\gates\` holds a `G1-*.json` file. `POST /runs/{run_id}/gates/G1/check` returns the same checks as a `GateResult` with `"passed": false`.
2. 🌐 **Approve.** Answer the question: `POST /runs/{run_id}/questions/RULE-REVENUE/answer` with `{"answer": "Net Revenue = SUM(LineTotal) excluding cancelled orders"}`. Check that `POST /runs/{run_id}/gates/G1/check` gives `"passed": true` (G1.5 is a `warning`: "not yet assessed"). Then `ACCEPT` with the new hash and `"comment": "Looks right"`. **Expected:** HTTP 200 with `approval`, `run` and `gate_result`. `run.state` is `REQUIREMENT_APPROVED`, `runs\<run_id>\BusinessContract.yaml` has `status: approved`, and `runs\<run_id>\approvals.jsonl` has one line with your UPN, an `at` timestamp, `artifact_hash` equal to the artifact hash in `GET /runs/{run_id}/artifacts`, `action: ACCEPT`, `role: business_owner` and a `gate_result_ref`. `GET /runs/{run_id}/approvals` lists it. `python -m app.cli contract validate runs\<run_id>\BusinessContract.yaml` prints `VALID`.
3. 🌐 **Locked.** `PUT /runs/{run_id}/contract/kpis/Net%20Revenue` with `{"currency": "EUR", "expected_hash": "<hash>"}` (use the KPI's name from the contract). **Expected:** HTTP 409, code `CONTRACT_LOCKED`. Also: `ACCEPT` again gives `409 ALREADY_APPROVED`, and `REJECT`, `EDIT` and `REGENERATE` give `409 CONTRACT_LOCKED`. `EXPLAIN` still works.
4. 🌐 **Role enforced.** In `config\roles.yaml` remove your UPN from `business_owner` (use `[someone.else@contoso.com]`). Create, compile and answer a second run, then `ACCEPT` it. **Expected:** HTTP 403, code `FORBIDDEN`, and the run is unchanged. `REJECT` also gives 403; `EXPLAIN` still works. **Restore your UPN** in the file afterwards.
5. 🌐 **Reject.** On a draft run with no blocking question (the second run, after restoring your role), `REJECT` with `"comment": "Exclude tax as well"`. **Expected:** HTTP 200, `run.state` is `NEEDS_CLARIFICATION`, `run.open_questions` has `{"id": "REV-1", "text": "Exclude tax as well", "blocking": true, "source": "reviewer", …}`, and `approvals.jsonl` ends with a `REJECT` record carrying the comment. `REJECT` with no comment gives `422`. Compile the run again: `REV-1` is still open. Answer it with `POST /runs/{run_id}/questions/REV-1/answer` and the run returns to `CREATED`.
6. 🌐 **Explain.** `EXPLAIN` on any draft run. **Expected:** HTTP 200 with `explanation.kpis` and `explanation.questions`, each with a readable `rationale` (for example "Net Revenue is defined as: …" or "has no definition yet"), an `EXPLAIN` record in `approvals.jsonl`, and the run state unchanged.
7. 🌐 **Edit, regenerate and stale hash.** `EDIT` with `"edits": {"kpis": {"Net Revenue": {"currency": "EUR"}}}` changes the KPI and writes an `EDIT` record. `REGENERATE` with `"comment": "Use fiscal months"` recompiles (a few seconds) keeping the locked facts and writes a `REGENERATE` record. Any action with an old `expected_hash` gives `409 STALE_VERSION`.
8. 💻 **Bad config.** Rename `config\roles.yaml` to `roles.bak` and start the API. **Expected:** startup fails with `Configuration file roles.yaml is missing`. Rename it back.
9. 💻 **Offline checks.** `python -m app.manual_tests.t204_offline_checks`. **Expected:** `All checks passed.` (fake LLM and a temporary roles file: G1 checks, accept, locking, roles, reject, explain, edit, regenerate, and the 403/404/409/422 cases).
10. 💻 **Clean up.** Restore `config\roles.yaml` (`git checkout config/roles.yaml`), stop the API and delete the test runs' folders under `runs\`.

**Not run by Claude:** the live steps (1–7), which need your Entra token and the real model.

---

### T-205 — Clarification and contract review UI

**Before you start:** do the T-204 setup: your own UPN in the `business_owner` list of `config\roles.yaml` (restore it afterwards). Start the API in one terminal (`uvicorn app.api.main:app --reload --port 8000`) and the UI in another (`cd rayfin-ui; npm install; npm run dev`), then open <http://localhost:3000> and sign in. Compile and answer steps call the real model and take a few seconds; Regenerate can take up to a minute.

1. 🌐 **Ambiguous Revenue end to end.** **New run** with the prompt `Show revenue by month for 2024`, then on the run page click **Compile**. **Expected:** a progress indicator ("Compiling the requirement…") shows and the buttons are disabled while it runs. Afterwards the clarification panel lists a **Blocking** question "How is Revenue defined?", the next action is "Answer open questions" and the state is `NEEDS_CLARIFICATION`. Type `Net Revenue = SUM(LineTotal) excluding cancelled orders` in **Your answer** and click **Submit answer**. **Expected:** the question disappears, the state becomes `CREATED` (reload the page to confirm). Click **Contract review**, then **Accept**. **Expected:** the state timeline on the run page shows `CREATED → NEEDS_CLARIFICATION → CREATED → REQUIREMENT_APPROVED`, and **Approval history** on the contract page shows an `ACCEPT` entry with your UPN and the time.
2. 🌐 **Blocked approval is explained.** Create and compile another run with the same prompt, but don't answer. Open **Contract review**. **Expected:** **Accept** is disabled with the note "Accept is unavailable: Gate G1 failed: G1.2, G1.3." (or similar), and the G1 checklist shows `G1.2` (and `G1.3`) with a red **Fail**, `G1.5` with an amber **Warning**, and the others **Pass**. If your UPN isn't in `business_owner`, Accept and Reject are hidden instead, with a note naming the role.
3. 🌐 **Explain.** On a draft contract click **Explain**. **Expected:** an "Explanation" box appears under each KPI (for example "Net Revenue is defined as: …" or "has no definition yet") and next to each question, and **Approval history** gains an `EXPLAIN` entry. The state doesn't change.
4. 🌐 **Stale version.** Open the contract page of a draft run in two browser tabs. In tab 1 click **Edit** on a KPI, change **Currency** and **Save**. In tab 2 (not reloaded) click **Regenerate**, **Explain** or **Accept**. **Expected:** tab 2 shows the warning "The contract changed. Reload to see the latest version. Nothing was changed.", with a **Reload** button, and no approval record is added. After **Reload** the new currency shows.
5. 🌐 **M2 exit.** Using only Rayfin, produce an approved contract (step 1). **Expected:** the contract page shows "Approved and locked", the Edit, Accept, Reject and Regenerate controls are gone (Explain remains), and `python -m app.cli contract validate runs\<run_id>\BusinessContract.yaml` prints `VALID` with `status: approved` in the file.
6. 🌐 **Other behaviour.** (a) With the API stopped, type an answer and click **Submit answer**. **Expected:** an error banner "Couldn't send your answer. What you typed is kept." with **Retry**, and the typed text is still in the box. Start the API and click **Retry**: the answer goes through. (b) Dismiss a non-blocking question with a reason. **Expected:** it disappears from the open list. (c) **Reject** is disabled until the comment box has text; with `Exclude tax as well` the run returns to `NEEDS_CLARIFICATION` and shows a blocking question with that text. (d) A very long answer or rationale shows **Show more / Show less**.
7. 💻 **Display-rule tests.** `cd rayfin-ui; npm test`. **Expected:** `fail 0` and no failing test (`pass 18` after T-205; later tasks add tests, T-304 brings it to 29), including the Accept rules, the stale message and long-text collapsing. `npm run typecheck` and `npm run build` also finish without errors.
8. 💻 **API checks.** `python -m app.manual_tests.t205_offline_checks`. **Expected:** `All checks passed.` (`contract` and `artifacts` in the run detail, `GET /me` with roles).
9. 💻 **Clean up.** Restore `config\roles.yaml` (`git checkout config/roles.yaml`), stop the API and UI, and delete the test runs' folders under `runs\`.

**Not run by Claude:** the browser steps (1–6), which need your Entra sign-in and the real model. Claude ran steps 7 and 8.

---

## M3 — Data understanding

### T-301 — Metadata Harvester per run

**Before you start:** same setup as T-204 and T-205 (token in Swagger, API running with `uvicorn app.api.main:app --port 8000`, your UPN in `business_owner` of `config\roles.yaml`; restore it afterwards). You need two runs that are `REQUIREMENT_APPROVED` (create, compile, answer and Accept as in T-204/T-205). Bind run A: `PUT /runs/{run_id}/scope` with your workspace and Lakehouse ids and `{"schemas": ["saleslt"]}`. Bind run B the same way with `"schemas": []`.

1. 🌐 **Harvest.** `POST /runs/{run_A}/harvest` (no body). **Expected:** HTTP 200 with `summary` (`tables`, `columns`, `errors`) and `artifact` (`name: MetadataInventory`, `version: 1`, a `sha256:` hash). `runs\<run_A>\MetadataInventory.json` lists every `saleslt` table, the `summary` counts equal the table, column and error totals in the file, and `GET /runs/{run_A}/inventory` returns the same content. The run state is still `REQUIREMENT_APPROVED`.
2. 🌐 **Matches the portal.** Pick three tables from the file and compare their columns, types and nullability with the Lakehouse explorer in Fabric. **Expected:** identical.
3. 🌐 **Not hardcoded.** `POST /runs/{run_B}/harvest` with `{"schemas": ["nexora_test"]}`. **Expected:** the five fixture tables from T-004, and `scope.schemas` in the file is `["nexora_test"]`. Run B's own scope is not changed.
4. 🌐 **Wrong state.** Create a run (state `CREATED`), bind a scope and `POST /runs/{id}/harvest`. **Expected:** HTTP 409, code `WRONG_STATE`. Also try `{"schemas": ["no_such_schema"]}` on run A. **Expected:** HTTP 404, code `SCHEMA_NOT_FOUND`, and the inventory file is unchanged.
5. 🌐 **Versioning.** `POST /runs/{run_A}/harvest` again. **Expected:** the response `artifact.version` and the file's `version` are `2`, `GET /runs/{run_A}/artifacts` shows `MetadataInventory` at version 2 with a new hash, and `runs\<run_A>\inventories\` holds `MetadataInventory.v1.json` and `.v2.json`.
6. 🌐 **Scope lock.** `PUT /runs/{run_A}/scope` after the harvest. **Expected:** HTTP 409, code `SCOPE_LOCKED`.
7. 💻 **Offline checks.** `python -m app.manual_tests.t301_offline_checks`. **Expected:** `All checks passed.` (fake Lakehouse: table paging, per-table errors, `NO_COLUMNS`, Unicode names, 520 tables with progress logs, versioning, schema override, wrong state, missing scope, re-harvest from `DATA_PROFILED`, 0 tables warning, listing failures).
8. 💻 **Clean up.** Restore `config\roles.yaml` (`git checkout config/roles.yaml`), stop the API and delete the test runs' folders under `runs\`.

**Not run by Claude:** the live steps (1–6), which need your Entra token and the real Lakehouse. Claude ran step 7.

---

### T-302 — Generic data profiler

**Before you start:** same setup as T-301 (token in Swagger, API running, your UPN in `business_owner`; restore it afterwards), with run A harvested (`POST /runs/{run_A}/harvest`, scope `saleslt`) and run B harvested with `{"schemas": ["nexora_test"]}`. The contract's entities decide which tables are profiled automatically, so give run A the prompt `Show total sales by product`; add `{"tables": [...]}` to profile others. The profiler queries the SQL endpoint **as you** (on-behalf-of), so the API's app registration needs the Azure SQL Database `user_impersonation` permission with consent. If the call returns `403 CONSENT_REQUIRED`, ask your admin to grant it. Run the SQL checks below in the Lakehouse SQL endpoint in Fabric.

1. 🌐 **Row count matches.** `POST /runs/{run_A}/profile` with `{"tables": ["saleslt.SalesLT_Product"]}`. **Expected:** HTTP 200 with `{"profiled": n, "warnings": n, "errors": 0}`. In the SQL endpoint run `SELECT COUNT(*) FROM saleslt.SalesLT_Product`; `GET /runs/{run_A}/inventory` shows the same number as `row_count` in that table's `profile`.
2. 🌐 **Unique key.** In the same profile, `columns.ProductID`. **Expected:** `is_unique: true` and `distinct_count` equal to `row_count`.
3. 🌐 **Duplicates detected.** `POST /runs/{run_B}/profile` with `{"tables": ["nexora_test.dim_product_dupes"]}`. **Expected:** `columns.ProductID.is_unique: false`, the table `status: warning`, and a warning "ProductID is not unique (n duplicate values)". Run `SELECT ProductID, COUNT(*) c FROM nexora_test.dim_product_dupes GROUP BY ProductID HAVING COUNT(*) > 1`: the number of rows equals `n` (at least 3, as T-004 AC-2).
4. 🌐 **Date coverage.** Pick a date column of a profiled table (for example `ModifiedDate` of `SalesLT_Product`) and run `SELECT MIN(ModifiedDate), MAX(ModifiedDate) FROM saleslt.SalesLT_Product`. **Expected:** equal to `min` and `max` of that column in the profile (UTC, ISO format), and `freshness.max_value` equals the `max` of the freshness column.
5. 🌐 **No raw strings.** Pick a known product name from the SQL endpoint (`SELECT TOP 1 Name FROM saleslt.SalesLT_Product`) and search `runs\<run_A>\MetadataInventory.json` for it (`Select-String -Path runs\<run_A>\MetadataInventory.json -Pattern "<name>"`). **Expected:** no match. String columns have counts only, no `min` or `max`.
6. 🌐 **Edge cases.** `{"tables": ["saleslt.NoSuchTable"]}` gives `404 NOT_FOUND`; profiling before any harvest gives `404 NOT_FOUND`; profiling a `CREATED` run gives `409 WRONG_STATE`. Re-harvest run A (`POST /runs/{run_A}/harvest`): **Expected:** the inventory is version 2 and every `profile` is `null` again.
7. 💻 **Offline checks.** `python -m app.manual_tests.t302_offline_checks`. **Expected:** `All checks passed.` (a fake SQL endpoint over in-memory tables: counts, uniqueness, duplicate count, min and max, freshness, empty and all-null cases, removed and timed-out tables, binary columns, the 10M-row approximate path, no string values stored, SELECT-only SQL, and the 404/409/422/400 cases).
8. 💻 **Clean up.** Restore `config\roles.yaml` (`git checkout config/roles.yaml`), stop the API and delete the test runs' folders under `runs\`.

**Not run by Claude:** the live steps (1–6), which need your Entra token, SQL consent and the real Lakehouse. Claude ran step 7.

---

### T-303 — Relationship evidence

**Before you start:** same setup as T-302 (token in Swagger, API running, your UPN in `business_owner`, SQL consent; restore `config\roles.yaml` afterwards). Use run A (harvested for `saleslt`) and run B (harvested for `saleslt` and `nexora_test`, so it includes `dim_product_dupes`). Missing profiles are computed automatically. The model's suggestions need the real model; the analysis itself needs only the SQL endpoint. Run the SQL checks in the Lakehouse SQL endpoint in Fabric.

1. 🌐 **Real join measured.** `POST /runs/{run_A}/relationships/analyze` (no body). **Expected:** HTTP 200 with `{"candidates": n, "high": n, "medium": n, "low": n, "rejected": n, "warnings": []}`. `GET /runs/{run_A}/relationships` contains an entry from `saleslt.SalesLT_SalesOrderDetail.ProductID` to `saleslt.SalesLT_Product.ProductID` with `cardinality: many_to_one`, `confidence: high` and `source: heuristic`. Run `python -m app.test_product_mapping`: its `Detail rows` and `Matched detail rows` give the orphan rate, `(detail_rows - matched_rows) / detail_rows * 100`, which equals `orphan_rate`. `evidence.queries` shows the SQL that ran.
2. 🌐 **Bad join is low confidence.** `POST /runs/{run_A}/relationships/analyze` with `{"candidates": [{"from": {"table": "saleslt.SalesLT_SalesOrderDetail", "column": "ProductID"}, "to": {"table": "saleslt.SalesLT_Customer", "column": "CustomerID"}}]}`. **Expected:** that entry has `source: user`, `confidence: low` and a small `overlap_pct` (compare with `SELECT COUNT(DISTINCT d.ProductID), COUNT(DISTINCT c.CustomerID) FROM saleslt.SalesLT_SalesOrderDetail d JOIN saleslt.SalesLT_Customer c ON d.ProductID = c.CustomerID`). A pair of different types, such as `SalesLT_Product.Name` to `SalesLT_Customer.CustomerID`, gives `type_compatible: false`, `confidence: low` and no queries.
3. 🌐 **Invalid relationship evidence.** `POST /runs/{run_B}/relationships/analyze`, then look for entries whose `to.table` is `nexora_test.dim_product_dupes`. **Expected:** `cardinality: many_to_many`, `confidence: low` and a note "The target column is not unique, so this can't be many-to-one". `SELECT ProductID, COUNT(*) c FROM nexora_test.dim_product_dupes GROUP BY ProductID HAVING COUNT(*) > 1` returns at least 3 rows, so the target really isn't unique.
4. 🌐 **Hallucinated column rejected.** The model may or may not invent one, so inject it: this needs the offline check (step 6), which feeds the analysis a model answer with `Product.NoSuchColumn`. **Expected:** `status: rejected`, `rejected_reason: "column not in inventory"`. By hand you can still check a user candidate with a column that doesn't exist (`"column": "NoSuchColumn"`): it is rejected the same way.
5. 🌐 **Stored and cleared.** Open `runs\<run_A>\MetadataInventory.json`: `relationship_evidence` holds the same entries and the profiles of the tables used. `POST /runs/{run_A}/harvest` again. **Expected:** `GET /runs/{run_A}/relationships` is `[]`.
6. 💻 **Offline checks.** `python -m app.manual_tests.t303_offline_checks`. **Expected:** `All checks passed.` (fake SQL endpoint and model: heuristics, LLM and user candidates, the unique/duplicate/null/orphan/overlap numbers, high/medium/low, one_to_one/many_to_one/many_to_many, rejections for hallucinated table and column, self-relationship and missing profile, type mismatch with no join query, names-and-types-only model payload, model failure degrading to a warning, replaced evidence, cleared on re-harvest, and the 404/409/422/400 cases).
7. 💻 **Clean up.** Restore `config\roles.yaml` (`git checkout config/roles.yaml`), stop the API and delete the test runs' folders under `runs\`.

**Not run by Claude:** the live steps (1–5), which need your Entra token, SQL consent, the real model and the real Lakehouse. Claude ran step 6.

---

### T-304 — Gate G2 and inventory UI

**Before you start:** same setup as T-302 and T-303 (token in Swagger, API running with `uvicorn app.api.main:app --reload --port 8000`, SQL consent). Open `config\roles.yaml` and put **your own UPN** in the `data_engineer` list in place of `user@contoso.com` (restore it afterwards; it is the only role needed here). Start the UI (`cd rayfin-ui; npm install; npm run dev`) and sign in at <http://localhost:3000>. You need runs that are `REQUIREMENT_APPROVED` (create, compile, answer and Accept the contract as in T-205). Give run A the prompt `Show total sales by product` (its entities should include Products), bind it to `saleslt` and scope run B to `saleslt` and `nexora_test`. The tables the gate looks at are the ones whose names match the contract's entities (for example `Products` matches `SalesLT_Product` and `dim_product_dupes`).

1. 🌐 **Pass on conformed data.** Open `http://localhost:3000/runs/<run_A>/inventory`. Click **Harvest**, then **Profile candidates**. **Expected:** the **Gate G2 checklist** shows `G2.1`, `G2.2`, `G2.3` and `G2.5` as **Pass** (`G2.4` is **Pass** or an amber **Warning**), and the Accept note is gone. Click **Accept**. **Expected:** the summary shows the state `DATA_PROFILED` and the badge **Accepted**; `runs\<run_A>\approvals.jsonl` ends with an `ACCEPT` record for `MetadataInventory` with your UPN, role `data_engineer` and a `gate_result_ref`; `runs\<run_A>\gates\` holds `G2-*.json`. Via Swagger the same is `POST /runs/{run_A}/gates/G2/check` then `POST /runs/{run_A}/approvals` with `{"artifact": "MetadataInventory", "action": "ACCEPT", "expected_hash": "<hash of MetadataInventory from GET /runs/{run_A}/artifacts>"}`.
2. 🌐 **Exception required.** In `config\conformed_sources.yaml` delete the line `saleslt.SalesLT_Customer` (restore it afterwards), make sure the contract of run B has the entity `Customers`, harvest and profile run B, and click **Reload**. **Expected:** `G2.5` is **Fail** and names `saleslt.SalesLT_Customer`, **Accept** is disabled with "Gate G2 failed: G2.5.", and **Source exceptions** shows "saleslt.SalesLT_Customer is not a conformed source". If the contract has no `Customers` entity, use another table that matches a contract entity and remove that table from the file instead.
3. 🌐 **Exception approved.** In **Source exceptions** type a rationale and click **Approve exception**. **Expected:** `G2.5` turns **Pass**, the exception is listed under "Approved exceptions" with your UPN and time, `GET /runs/{run_B}/approvals` has a record with `artifact: "Exception:saleslt.SalesLT_Customer"` and the rationale as `comment`, and **Accept** is available. With your UPN removed from `data_engineer` (use `[someone.else@contoso.com]`), the same call is `403 FORBIDDEN` and the UI says a data_engineer must approve it. An exception for a table that matches no contract entity, `POST /runs/{run_B}/exceptions` with `{"table": "saleslt.SalesLT_SalesOrderHeader", "rationale": "x"}` (any harvested table that matches no contract entity), gives `422`.
4. 🌐 **Evidence visible.** On run B click **Analyze relationships**, find `nexora_test.dim_product_dupes` in **Tables** (use the search box) and click **Show columns**. **Expected:** the warning "ProductID is not unique (n duplicate values)"; click **Show evidence**. **Expected:** the ProductID numbers (rows, nulls, distinct, values appearing more than once) and the SQL that ran, for example the `GROUP BY [ProductID] HAVING COUNT(*) > 1` query. In **Relationship evidence**, **Show SQL** on any entry shows its queries, and entries into `dim_product_dupes` show `many_to_many` with the "not unique" note.
5. 🌐 **Data gap.** On a run in `REQUIREMENT_APPROVED`, type "Warehouse stock data is not in the Lakehouse" under **Raise a data gap** and click **Raise data gap**. **Expected:** the state becomes `NEEDS_INPUT` ("Returns to REQUIREMENT_APPROVED when input is provided" on the run page), and the run page shows a **Data gap** message with the description. `GET /runs/{run_id}` has it under `data_gaps`.
6. 🌐 **Search and paging.** On the inventory page, type `product` in **Search tables**. **Expected:** only matching tables are listed, with "n of m tables". If a harvest has more than 50 tables, **Previous** and **Next** page through them.
7. 🌐 **Re-harvest after Accept.** On run A click **Re-harvest**. **Expected:** the state returns to `REQUIREMENT_APPROVED`, the inventory is version 2 and a **Draft**, profiles are gone, and `G2.3` fails until you profile again.
8. 🌐 **M3 exit.** Using only Rayfin: Harvest, Profile candidates, Analyze relationships, then Accept. **Expected:** an accepted inventory exists for the run (`MetadataInventory.json`, status `approved`) and every table, column profile, warning and relationship is reviewable on the Inventory page.
9. 💻 **Offline checks.** `python -m app.manual_tests.t304_offline_checks`. **Expected:** `All checks passed.` (G2.1-G2.5 incl. a candidate that failed to harvest or profile, no candidates, exceptions and roles, Accept with a stale hash and wrong state, re-harvest, data gaps, and the 404/409/422/500 cases).
10. 💻 **Display-rule tests.** `cd rayfin-ui; npm test`. **Expected:** `fail 0` (`pass 29` when T-304 was done; later tasks add tests, so it is higher now). `npm run typecheck` and `npm run build` also finish without errors, and the build lists `/runs/[id]/inventory`.
11. 💻 **Clean up.** Restore `config\roles.yaml` and `config\conformed_sources.yaml` (`git checkout config/roles.yaml config/conformed_sources.yaml`), stop the API and UI, and delete the test runs' folders under `runs\`.

**Not run by Claude:** the live and browser steps (1–8), which need your Entra sign-in, SQL consent and the real Lakehouse. Claude ran steps 9 and 10.

---

## M4 — Planning

### T-401 — Entity-to-source mapping and conformed-table resolver

**Before you start:** same setup as T-302 to T-304 (token in Swagger, API running with `uvicorn app.api.main:app --reload --port 8000`, SQL consent, the real model). Open `config\roles.yaml` and put **your own UPN** in `data_engineer` (restore it afterwards). You need runs in state `DATA_PROFILED` (create, compile and Accept the contract, bind a scope, harvest, profile and Accept the inventory as in T-205 and T-304). Run A: prompt `Show net revenue by product and customer`, scope `saleslt`; its contract needs the entities Sales, Product and Customer and a Net Revenue KPI. Run B: the same, scoped to `saleslt` and `nexora_test`.

1. 🌐 **Correct selection.** `POST /runs/{run_A}/plan/sources` (no body). **Expected:** HTTP 200. `entities` has Sales selected as `saleslt.SalesLT_SalesOrderDetail`, Product as `saleslt.SalesLT_Product` and Customer as `saleslt.SalesLT_Customer`; each has a `score`, `conformed: true`, `exception_id: null` and a `rationale` (for example "Glossary match 'product'; conformed; key ProductID unique"). `kpi_fields` for Net Revenue maps the line amount to `SalesLT_SalesOrderDetail.LineTotal` (`role: measure`) and the order status to a `SalesLT_SalesOrderHeader` column (`role: filter`). The file is `runs\<run_A>\SourceResolution.json`, the state is still `DATA_PROFILED`, and `GET /runs/{run_A}/artifacts` lists `SourceResolution` v1 as `draft`.
2. 🌐 **Rejections explained.** `POST /runs/{run_B}/plan/sources` (if run B has no profile of the dupes table yet, call `POST /runs/{run_B}/profile` first with `{"tables": ["nexora_test.dim_product_dupes"]}`). **Expected:** under Product, `rejected` holds `nexora_test.dim_product_dupes` with a lower score, `requires_exception: true` and a reason such as "Not conformed and no approved exception; key ProductID not unique".
3. 🌐 **Conformed policy.** In `config\conformed_sources.yaml` delete the line `saleslt.SalesLT_Product` (restore it afterwards) and call `POST /runs/{run_A}/plan/sources` again. **Expected:** Product has `selected: null`, a `reason` saying a data_engineer must approve an exception, and `SalesLT_Product` in `rejected` with `requires_exception: true`. An exception can only be approved while the run is `REQUIREMENT_APPROVED`: on another run, call `POST /runs/{id}/exceptions` with `{"table": "saleslt.SalesLT_Product", "rationale": "pilot"}` before accepting the inventory. Its resolution then selects the table with `conformed: false` and the exception's `exception_id`.
4. 🌐 **Glossary without code.** In `config\glossary.yaml` remove `item` from the `product` list, create a run whose contract entity is `Items` and call `/plan/sources`. **Expected:** `Items` has `selected: null` and the reason "No table in the inventory matches 'Items'". Add `item` back and call it again. **Expected:** `Items` maps to `saleslt.SalesLT_Product` (`SourceResolution` is version 2), with no code change. Break the file (a term whose value is not a list) and call it. **Expected:** `500 CONFIG_ERROR` naming `glossary.yaml` and the line.
5. 🌐 **Deterministic.** Call `/plan/sources` twice on the same run. **Expected:** the version stays 1 and `SourceResolution.json` is byte for byte the same (the model's first answer is kept in `runs\<run>\source_suggestions.json` and reused for an unchanged request).
6. 💻 **Offline checks.** `python -m app.manual_tests.t401_offline_checks`. **Expected:** `All checks passed.` (glossary loading and errors, scoring and tie-breaks, selection of Sales, Product and Customer, rationale and key evidence, rejected tables with reasons, the conformed policy and approved exceptions, KPI field mapping with hallucinated tables, columns and roles discarded, a names-and-types-only model payload, an identical file on a second call, a glossary edit making a new version, and the 404/409/500/502 cases).
7. 💻 **Clean up.** Restore `config\roles.yaml`, `config\conformed_sources.yaml` and `config\glossary.yaml` (`git checkout config/roles.yaml config/conformed_sources.yaml config/glossary.yaml`), stop the API and delete the test runs' folders under `runs\`.

**Not run by Claude:** the live steps (1–5), which need your Entra token, SQL consent, the real model and the real Lakehouse. Claude ran step 6.

---

### T-402 — KPI feasibility and Data Gap

**Before you start:** same setup as T-401 (token in Swagger, API running, SQL consent, the real model). Run A needs the Net Revenue KPI (as in T-401). Run B has the same contract plus a second KPI, `Customer Retention Rate by quarter` (formula intent "customers active in two consecutive quarters over those active in the first", time logic "by quarter"); `saleslt` can't support it. Both runs are `DATA_PROFILED` and have called `POST /runs/{id}/plan/sources`.

1. 🌐 **Unsupported KPI stopped.** `POST /runs/{run_B}/plan/feasibility`. **Expected:** HTTP 200. `Customer Retention Rate` is `data_gap` with `missing` entries (for example "customer activity per period" and a quarter/date need, each with a reason) and `options: ["drop_kpi", "provide_source", "data_engineering_task"]`. `run.state` is `NEEDS_INPUT` with `resume_state: DATA_PROFILED`, and `run.data_gaps` has an entry for the KPI. Search `runs\<run_B>` for `DAX`, `EVALUATE` and `proxy` (for example `Select-String -Path runs\<run_B>\* -Pattern 'dax|proxy' -Recurse`). **Expected:** no matches.
2. 🌐 **Supported KPI passes.** `POST /runs/{run_A}/plan/feasibility`. **Expected:** `Net Revenue` is `feasible`, `missing: []`, and every `needed` entry has `mapped` set to a column such as `saleslt.SalesLT_SalesOrderDetail.LineTotal`. The state stays `DATA_PROFILED`. `runs\<run_A>\Feasibility.json` exists and `GET /runs/{run_A}/artifacts` lists `Feasibility`.
3. 🌐 **Deterministic override.** Open `runs\<run_A>\SourceResolution.json` and delete the field entry whose `column` is `LineTotal` from `kpi_fields`, then call `POST /runs/{run_A}/plan/feasibility` again. **Expected:** Net Revenue is `data_gap`, `missing` names the line amount ("… is not a column mapped in the source resolution"), `Feasibility.json` is version 2 and the state is `NEEDS_INPUT`. (Restore the file by calling `POST /runs/{run_A}/plan/sources`, after `python -m app.cli runs transition <run_A> DATA_PROFILED`.)
4. 🌐 **Repeatable.** On a feasible run call the endpoint twice. **Expected:** the version stays 1 and `Feasibility.json` is byte for byte the same.
5. 💻 **Offline checks.** `python -m app.manual_tests.t402_offline_checks`. **Expected:** `All checks passed.` (feasible and data-gap KPIs, the deterministic override, a model claiming a column the inventory lacks, one missing exclusion making a gap, time logic with and without a date column, needs the source resolution couldn't map, all KPIs gaps, NEEDS_INPUT and the data gap list, no DAX in the run folder, the one retry and 502 on unusable output, and the 404/409 cases).
6. 💻 **Clean up.** Stop the API and delete the test runs' folders under `runs\`.

**Not run by Claude:** the live steps (1–4), which need your Entra token, SQL consent, the real model and the real Lakehouse. Claude ran step 5.

---

### T-403 — Bridge-table detection and proposal

**Before you start:** same setup as T-401 (token in Swagger, API running, SQL consent, `config\roles.yaml` with **your own UPN** in `bi_engineer`; restore it afterwards). The `nexora_test` fixtures must exist (`fixtures\README.md`), and `config\conformed_sources.yaml` lists `nexora_test.dim_promotion`, `bridge_product_promotion` and `dim_campaign`. Run A: contract entities `Sales`, `Product` and `Promotion` (a prompt such as "sales by promotion and product"), scope `saleslt` and `nexora_test`. Run B: entities `Product` and `Campaign`, the same scope. For each run: harvest, `POST /runs/{id}/profile`, `POST /runs/{id}/relationships/analyze`, Accept the inventory, then `POST /runs/{id}/plan/sources`.

1. 🌐 **Existing mapping proposed.** `POST /runs/{run_A}/plan/bridges`. **Expected:** HTTP 200 with one proposal: `id: "B1"`, `entities: ["Product", "Promotion"]`, `situation: "existing_table"`, `table: "nexora_test.bridge_product_promotion"`, `status: "proposed"`, `evidence.duplicate_pairs: 0` and `coverage_a_pct` (Product, well under 100) and `coverage_b_pct: 100.0` (Promotion). `evidence.queries` shows the aggregate SQL. Compare in the SQL endpoint: `SELECT COUNT(DISTINCT p.ProductID) * 100.0 / (SELECT COUNT(DISTINCT ProductID) FROM saleslt.SalesLT_Product) FROM saleslt.SalesLT_Product p JOIN nexora_test.bridge_product_promotion b ON b.ProductID = p.ProductID`. The state is still `DATA_PROFILED`, and `runs\<run_A>\BridgeProposals.json` exists.
2. 🌐 **No guess.** `POST /runs/{run_B}/plan/bridges`. **Expected:** one proposal with `situation: "needs_rules"`, `table: null`, `derivation_rule: null` and an issue "mapping rules required: …". The run state is `NEEDS_INPUT` and `GET /runs/{run_B}` shows a data gap "Mapping rules are required for Product and Campaign …". `dim_campaign` has no mapping table on purpose.
3. 🌐 **Can't approve without rules.** `POST /runs/{run_B}/approvals` with `{"artifact": "BridgeProposal:B1", "action": "ACCEPT", "expected_hash": "<hash of BridgeProposals from GET /runs/{run_B}/artifacts>"}`. **Expected:** `409 MAPPING_RULES_REQUIRED` ("mapping rules required for Product and Campaign"); the proposal stays `proposed`.
4. 🌐 **Approve a real bridge.** The same call on run A with `BridgeProposal:B1` (and, after a first try with a wrong hash, **Expected:** `409 STALE_VERSION`). **Expected:** HTTP 200, `runs\<run_A>\approvals.jsonl` ends with an `ACCEPT` record for `BridgeProposal:B1` with your UPN and role `bi_engineer`, the proposal's status is `approved` and `BridgeProposals` is version 2 with status `approved`. A second approval is `409 ALREADY_APPROVED`.
5. 🌐 **Derivation rule.** Add to `config\derivation_rules.yaml`: `rules:` then `- id: DR1`, `entities: [Product, Campaign]`, `description: Campaign applies to the products of its category`, `approved_by: <you>` (restore it afterwards), and call `/plan/bridges` on a fresh run like B. **Expected:** `situation: "derivation_rule"`, `derivation_rule: "DR1"`, no table, and the state stays `DATA_PROFILED`.
6. 🌐 **No false alarm.** On a run with entities `Sales`, `Product` and `Customer` (scope `saleslt`), call `/plan/bridges`. **Expected:** `[]` and the state unchanged.
7. 💻 **Offline checks.** `python -m app.manual_tests.t403_offline_checks`. **Expected:** `All checks passed.` (rule file errors, an existing mapping table with duplicates and coverage, several mapping tables, a derivation rule, a deduplication rule, `needs_rules` and `NEEDS_INPUT`, an isolated entity, a normal star with no proposals, a many-to-many nobody needs, approvals by both roles, the 403/404/409/422 cases, and 400/404/500 preconditions).
8. 💻 **Clean up.** Restore `config\roles.yaml` and `config\derivation_rules.yaml` (`git checkout config/roles.yaml config/derivation_rules.yaml`), stop the API and delete the test runs' folders under `runs\`.

**Not run by Claude:** the live steps (1–6), which need your Entra token, SQL consent and the real Lakehouse with the `nexora_test` fixtures. Claude ran step 7.

---

### T-404 — ExecutionPlan and ModelSpec generation

**Before you start:** same setup as T-401 to T-403 (token in Swagger, API running, SQL consent). Run A: the Net Revenue KPI plus a monthly KPI such as `Monthly Revenue` (formula intent "sum of line totals", time logic "by month"), entities `Sales`, `Product` and `Customer`, scope `saleslt` and `nexora_test`. Do harvest and profile, then `POST /runs/{id}/relationships/analyze` with the joins the plan needs as user candidates (the model may propose some already): `{"candidates": [{"from": {"table": "saleslt.SalesLT_SalesOrderDetail", "column": "SalesOrderID"}, "to": {"table": "saleslt.SalesLT_SalesOrderHeader", "column": "SalesOrderID"}}, {"from": {"table": "saleslt.SalesLT_SalesOrderHeader", "column": "OrderDate"}, "to": {"table": "nexora_test.dim_date", "column": "Date"}}]}`. Then Accept the inventory, call `POST /runs/{id}/plan/sources` and `POST /runs/{id}/plan/feasibility`. Run B: the same with scope `saleslt` only (no date table).

1. 🌐 **Plan generated.** `POST /runs/{run_A}/plan`. **Expected:** HTTP 200 with `execution_plan`, `model_spec` and `validation`. `runs\<run_A>\ModelSpec.yaml` and `ExecutionPlan.yaml` exist. `ModelSpec` has a `Sales` table with `role: fact`, `grain: order line` and source `SalesLT_SalesOrderDetail`. Its relationships go from Sales to Product and to the order header, and from the header to Customer and Date. Each has an `evidence_ref`: an id from `relationship_evidence` in `MetadataInventory.json` with `high` or `medium` confidence. `storage_mode` is `DirectLake`, `Date` has a `Calendar` hierarchy (Year, Quarter, Month), and `Net Revenue` is a measure with `dax: null`. `validation.passed` is `true`. The state is still `DATA_PROFILED`, and `GET /runs/{run_A}/artifacts` lists `ModelSpec` and `ExecutionPlan`.
2. 🌐 **Bad reference caught.** In `runs\<run_A>\ModelSpec.yaml` change the `to:` column of the `Sales_Product` relationship to `NoSuchColumn`, then run `python -m app.cli plan validate runs\<run_A>`. **Expected:** `INVALID` and a line `PLAN.1: relationships[Sales_Product].to.column: Product.NoSuchColumn`, exit code 1. `GET /runs/{run_A}/plan` shows the same failure under `validation`. Undo the edit, or call `POST /runs/{run_A}/plan` to regenerate: the command prints `VALID` and exits 0.
3. 🌐 **No inferred security.** Check `roles` in `ModelSpec.yaml` of run A, whose contract has no security requirements. **Expected:** `roles: []`. On a run whose contract has a security requirement (for example "Sales reps see only their region") the plan has one role `RLS1` with that description and `table_filters: []`.
4. 🌐 **Missing date handled.** `POST /runs/{run_B}/plan` (scope without `dim_date`). **Expected:** `execution_plan.data_engineering_actions` has one `create_date_table` action (`blocking: true`, `owner: null`). `ModelSpec` has no table with `role: date` and no table without a `source`, so no calculated table. `validation.passed` is `true`.
5. 🌐 **Evidence required.** In `ModelSpec.yaml` of run A set a relationship's `evidence_ref` to the id of a `low` entry of `relationship_evidence`, and run `python -m app.cli plan validate runs\<run_A>`. **Expected:** `PLAN.2: relationships[<name>]: evidence R<n> is low and there is no override with a rationale`. Adding `override_rationale: Confirmed with the data owner` to that relationship makes it `VALID`.
6. 💻 **Offline checks.** `python -m app.manual_tests.t404_offline_checks`. **Expected:** `All checks passed.` (the plan for a normal star, hierarchy, hidden keys, evidence refs, determinism, the CLI as a command, every validation check failing with its path, RLS from the contract only, the date-table action, a bridge in the plan, only feasible KPIs, `NO_FEASIBLE_KPIS`, and the 404/409/500 cases).
7. 💻 **Clean up.** Stop the API and delete the test runs' folders under `runs\`.

**Not run by Claude:** the live steps (1–5), which need your Entra token, SQL consent, the real model and the real Lakehouse. Claude ran step 6.

---

### T-405 — Gate G3 and plan review UI

**Before you start:** same setup as T-404 (token in Swagger, API running with `uvicorn app.api.main:app --reload --port 8000`, SQL consent), plus the UI (`cd rayfin-ui; npm install; npm run dev`, sign in at <http://localhost:3000>). Open `config\roles.yaml` and put **your own UPN** in `bi_engineer` (restore it afterwards). Use run A of T-404, which has a generated plan (Net Revenue and a monthly KPI, entities Sales, Product and Customer, scope `saleslt` and `nexora_test`, the order header and date relationships analyzed). Open <http://localhost:3000/runs/{run_A}/plan>. In this model the date joins through the order header, so the relationship names are `Sales_Product`, `Sales_SalesLT_SalesOrderHeader`, `SalesLT_SalesOrderHeader_Customer` and `SalesLT_SalesOrderHeader_Date`; read the real names on the screen.

1. 🌐 **Rationale visible.** Look at **Tables**. **Expected:** every table shows its role, source and a line "Why: …" (for example "Product: Glossary match 'product'; conformed; key ProductID unique (score 0.9)"). **Rejected alternatives** lists the tables that were not chosen with their reason (for example `nexora_test.dim_product_dupes`: "Not conformed and no approved exception; key ProductID not unique"). **Relationships** shows each relationship's evidence ("R3, high confidence, many to one, 100% overlap, 0% orphans") and **Show SQL**. **Measures**, **Storage mode**, **Row-level security** and **Data-engineering actions** are listed too.
2. 🌐 **Edit re-validates.** On the `SalesLT_SalesOrderHeader_Date` relationship click **Remove**. **Expected:** the page reloads as the next plan version, the **Gate G3 checklist** shows `G3.6` as **Fail** with "measures[Monthly Revenue]: needs Date related to Sales, but no relationship path connects them", and **Accept** says "Accept is unavailable: Gate G3 failed: G3.6." **History** has an `EDIT` entry "remove_relationship SalesLT_SalesOrderHeader_Date". Via Swagger the same is `PATCH /runs/{run_A}/plan` with `{"expected_hash": "<hash of ExecutionPlan from GET /runs/{run_A}/artifacts>", "ops": [{"op": "remove_relationship", "name": "SalesLT_SalesOrderHeader_Date"}]}`, which returns `gate_result.passed: false`. An unknown op such as `{"op": "explode"}` is `422` and its message lists the four valid ops.
3. 🌐 **Approve.** Click **Regenerate plan** (or use the relationship's override or remove the Monthly Revenue measure instead), so that G3 passes again, then click **Accept**. **Expected:** the summary shows the state `PLAN_APPROVED` and the badge **Approved**; `runs\<run_A>\approvals.jsonl` ends with an `ACCEPT` record for `ExecutionPlan` whose `artifact_hash` equals the `ExecutionPlan` hash in `GET /runs/{run_A}/artifacts`, with role `bi_engineer` and a `gate_result_ref` `gates/G3-…`. **Reject** (with a comment) on the approved plan reopens it: state `DATA_PROFILED`, badge **Draft**.
4. 🌐 **Role enforced.** In `config\roles.yaml` remove your UPN from `bi_engineer` (use `[someone.else@contoso.com]`), reload the page. **Expected:** **Accept** says "Only a bi_engineer can accept or reject the plan." Via Swagger, `POST /runs/{run_A}/approvals` with `{"artifact": "ExecutionPlan", "action": "ACCEPT", "expected_hash": "<hash>"}` is `403 FORBIDDEN` and the state doesn't change.
5. 🌐 **Blocking action.** On run B (scope `saleslt` only, a KPI with time logic), generate the plan. **Expected:** **Data-engineering actions** shows "DE1 … Blocking, Owner: unassigned" (create a date table), and `G3.5` is **Fail** with the action and its owner, so **Accept** is unavailable.
6. 🌐 **M4 exit.** Using Rayfin only: Resolve sources, Check feasibility, Generate plan, review, and Accept. **Expected:** an approved plan exists (`ModelSpec.yaml` and `ExecutionPlan.yaml`, status `approved`, run state `PLAN_APPROVED`) and its tables, rationale, relationships, evidence and measures are reviewable on the Plan review screen.
7. 💻 **Offline checks.** `python -m app.manual_tests.t405_offline_checks`. **Expected:** `All checks passed.` (G3.1-G3.7 each passing and failing, the four edit operations, atomic and invalid edits, stale hashes, versions kept, EDIT records, Accept with G3 and roles, `GATE_FAILED`, reject and reopen, approving again, and the 404/409/422/500 cases).
8. 💻 **Display-rule tests.** `cd rayfin-ui; npm test`. **Expected:** `pass 42`, `fail 0`. `npm run typecheck` and `npm run build` also finish without errors, and the build lists `/runs/[id]/plan`.
9. 💻 **Clean up.** Restore `config\roles.yaml` (`git checkout config/roles.yaml`), stop the API and UI, and delete the test runs' folders under `runs\`.

**Not run by Claude:** the live and browser steps (1–6), which need your Entra sign-in, SQL consent, the real model and the real Lakehouse. Claude ran steps 7 and 8.

---

## M5 — Semantic model

### T-501 — Sandbox deployment client

**Before you start:** put the sandbox workspace's ID in `SANDBOX_WORKSPACE_ID` in `.env` (a workspace you may write to, never a production one). Create this folder, indenting with tabs:

```
tmp\Nexora_Smoke\definition.pbism                  {"version": "4.0", "settings": {}}
tmp\Nexora_Smoke\definition\database.tmdl          database Nexora_Smoke
                                                   	compatibilityLevel: 1604
tmp\Nexora_Smoke\definition\model.tmdl             model Model
                                                   	culture: en-US
                                                   ref table Product
tmp\Nexora_Smoke\definition\tables\Product.tmdl    table Product
                                                   	column ProductID
                                                   		dataType: int64
                                                   		sourceColumn: ProductID
                                                   		summarizeBy: none
                                                   	measure 'Product Count' = COUNTROWS('Product')
                                                   	partition Product = m
                                                   		mode: import
                                                   		source = let Source = #table({"ProductID"}, {{1}, {2}}) in Source
```

The table holds two literal rows, so no Lakehouse connection is needed. If Fabric rejects the files, adjust them to Microsoft's current TMDL documentation. The error you see is also what step 4 tests.

1. 🌐 **Create.** `python -m app.cli deploy model tmp\Nexora_Smoke --name Nexora_Smoke`. **Expected:** `item_id: <guid>` and `operation: created`, exit code 0. The model `Nexora_Smoke` appears in the sandbox workspace and opens in the web model view.
2. 🌐 **Update, not duplicate.** Rename the measure in `Product.tmdl` (for example to `Products`) and run the same command again. **Expected:** the same `item_id` and `operation: updated`. The workspace still has exactly one `Nexora_Smoke`, showing the new measure name.
3. 🌐 **Guard.** `python -m app.cli deploy model tmp\Nexora_Smoke --name Nexora_Smoke --workspace-id 99999999-9999-4999-8999-999999999999; echo $LASTEXITCODE`. **Expected:** `TARGET_NOT_ALLOWED: Deployment is only allowed to the configured sandbox workspace`, exit code 1, and nothing created anywhere (no Fabric call is made).
4. 🌐 **Failure surfaced.** Put a syntax error in `Product.tmdl` (for example delete the `=` of the measure) and deploy. **Expected:** `UPSTREAM_ERROR: ...` with Fabric's message, `Fabric request ID: <id>` and Fabric's error JSON, exit code 1. Fix the file afterwards.
5. 💻 **Offline checks.** `python -m app.manual_tests.t501_offline_checks`. **Expected:** `All checks passed.` (the definition parts, create, update without a duplicate, polling with `Retry-After`, a failed operation, a rejected definition, `429` retries, a name used by another type, the timeout, the target guard, the setting fallback and the CLI).
6. 💻 **Clean up.** Delete `Nexora_Smoke` from the sandbox workspace and the `tmp\Nexora_Smoke` folder.

**Not run by Claude:** the live steps (1–4), which need your sign-in and the sandbox workspace. Claude ran step 5.

---

### T-502 — TMDL generator

**Before you start:** you need a run in `PLAN_APPROVED`, so the setup is the same as T-405 (API running with `uvicorn app.api.main:app --reload --port 8000`, token in Swagger, your UPN under `bi_engineer` in `config\roles.yaml`, restored afterwards). Use run A of T-404/T-405 (scope `saleslt` and `nexora_test`, plan generated and accepted). Its Lakehouse must have a SQL endpoint. `SANDBOX_WORKSPACE_ID` must be set for step 3.

1. 🌐 **Generated.** `POST /runs/{run_A}/model/generate` in Swagger. **Expected:** HTTP 200 with `version: 1`, `files` and `run.state: MODEL_GENERATING`. `runs\<run_A>\model\v1\` has `definition.pbism` and `definition\` with `database.tmdl`, `model.tmdl`, `relationships.tmdl`, `expressions.tmdl` and one file under `tables\` per ModelSpec table. `GET /runs/{run_A}/artifacts` lists `TMDLModel` (version 1, draft). A second call is `409 WRONG_STATE`.
2. 🌐 **Deterministic.** `python -m app.cli model generate runs\<run_A>`, then `git diff --no-index runs\<run_A>\model\v1 runs\<run_A>\model\v2`. **Expected:** the command prints `v2: <n> files in ...` and `git diff` prints nothing. The run state is still `MODEL_GENERATING`.
3. 🌐 **Deployable.** `python -m app.cli deploy model runs\<run_A>\model\v1 --name Nexora_<run>` (use the first 8 characters of the run id). **Expected:** `operation: created`. In the web model view of the sandbox workspace the tables, the relationships (many-to-one, single direction, unless the ModelSpec says otherwise) and the Calendar hierarchy of the date table are visible. Measures show only after T-503 (their `dax` is still null). If Fabric rejects the files, Fabric's error is printed: report it with the file, because the generator is what to fix.
4. 🌐 **No LLM.** In `.env` set `AZURE_OPENAI_ENDPOINT` to `https://invalid.invalid` (restore it afterwards) and run `python -m app.cli model generate runs\<run_A>`. **Expected:** it still prints `v3: ...`, because the generator never calls the model.
5. 🌐 **Edited spec refused.** Add a blank line at the end of `runs\<run_A>\ModelSpec.yaml` and change a table name in it, then run `python -m app.cli model generate runs\<run_A>`. **Expected:** `The model spec changed since you loaded it...` (the file no longer matches the approved hash), exit code 1, and no new `v` folder. Undo the edit by hand, or reject the plan and regenerate it. A spec that fails a PLAN check is refused with `INVALID` and the failing path, which the offline checks cover.
6. 💻 **Offline checks.** `python -m app.manual_tests.t502_offline_checks`. **Expected:** `All checks passed.` (the file layout, quoting, tabs and LF, Direct Lake and Import partitions, the hierarchy, relationships, null DAX left out, byte-identical output in any object order, refusals that write nothing, the endpoint with its 404/409/400/422 cases, `MODEL_FAILED` for repair, and the CLI).
7. 💻 **Clean up.** Delete the model from the sandbox workspace, restore `config\roles.yaml` and `.env`, stop the API, and delete the test runs' folders under `runs\`.

**Not run by Claude:** the live steps (1–5), which need your Entra token, the real run and the sandbox workspace. Claude ran step 6.

---

### T-503 — DAX measure generation

**Before you start:** run A of T-502, in state `MODEL_GENERATING` with `model1` generated (Net Revenue with the exclusion of cancelled orders, a monthly KPI with time logic, scope with `nexora_test.dim_date`). The API must reach the real model (`.env` set up, as for the compile step). The KPI definitions are what the model gets: make sure the Net Revenue KPI's exclusions state the status value to exclude (for example "Cancelled orders have Status = 6", answered through the clarification loop), because the model never sees data and the pre-check rejects a number the definition doesn't state.

1. 🌐 **Measures added.** `POST /runs/{run_A}/model/measures` in Swagger. **Expected:** HTTP 200, `version: 2`, and Net Revenue `accepted` with `dax`. Its DAX uses only objects of the ModelSpec and applies the exclusion of cancelled orders. `runs\<run_A>\ModelSpec.yaml` is version 2 with that `dax` and a `description` starting `Approved: <the formula intent>` followed by `Exclusions: ...`. `runs\<run_A>\model2\definition	ables\<fact table>.tmdl` has the `measure` and a `///` description, and `model1` is unchanged. A second call returns the same measures and `version: 2` without calling the model. The run is still `MODEL_GENERATING`. A measure may come back `rejected` with a reason: report which one and why.
2. 🌐 **Deployed and computes.** `python -m app.cli deploy model runs\<run_A>\model2 --name Nexora_<run>`. In the web model view of the sandbox workspace, run the DAX query `EVALUATE ROW("NR", [Net Revenue])`. **Expected:** a number.
3. 🌐 **Matches SQL.** In the Lakehouse SQL endpoint run the equivalent query, for example `SELECT SUM(d.LineTotal) FROM saleslt.SalesLT_SalesOrderDetail d JOIN saleslt.SalesLT_SalesOrderHeader h ON h.SalesOrderID = d.SalesOrderID WHERE h.Status <> 6`. **Expected:** the same value as step 2. (T-504 automates this.)
4. 💻 **Bad reference rejected.** Not repeatable live: editing a ModelSpec column by hand makes the next call `409 STALE_VERSION`, because the file no longer matches the approved hash. The offline checks cover it: a proposal that uses `Sales[Nope]` gets one retry carrying "unknown column 'Nope' ...", and if the retry fails too the measure is `rejected` with a reason naming `Sales[Nope]`, while the other measures are still processed.
5. 💻 **Offline checks.** `python -m app.manual_tests.t503_offline_checks`. **Expected:** `All checks passed.` (reading DAX references, every rejection rule, the 2-attempt graph path, `date table required`, the endpoint with accepted and rejected measures, the replay without a model call, the TMDL and ModelSpec versions, and the 404/409 cases).
6. 💻 **Clean up.** Delete the model from the sandbox workspace, stop the API, and delete the test runs' folders under `runs\`.

**Not run by Claude:** the live steps (1–3), which need your Entra token, the real model and the sandbox workspace. Claude ran steps 4 and 5 (offline).

---

### T-504 — Model validators and Gate G4

**Before you start:** the T-503 setup (run A in `MODEL_GENERATING` with the measures added and `model\v2` generated), plus `SANDBOX_WORKSPACE_ID` in `.env`, the API's Entra app registration granted the Power BI delegated permission `Dataset.ReadWrite.All` with consent (otherwise `403 CONSENT_REQUIRED`), and SQL consent as before. Validation has no role gate, so `config\roles.yaml` needs no change.

1. 🌐 **Passing model.** `POST /runs/{run_A}/model/validate` in Swagger. **Expected:** HTTP 200, `report.passed: true`, the run still `MODEL_GENERATING`. `runs\<run_A>\ValidationReport.json` has one run with `G4.REF`, one `G4.REL` per relationship, `G4.DAX` and `G4.RECON` per measure, and `G4.RLS` ("no roles defined" for a contract without security). The `G4.RECON` evidence for Net Revenue shows `dax_query`, `dax_value`, `sql_query` and `sql_value` side by side, plus a `slice` with its label and both values. The model `Nexora_<run>` exists in the sandbox workspace. Read the reference SQL and confirm it is a sensible independent calculation. A second call appends attempt 2 and reuses the saved SQL.
2. 🌐 **Broken measure fails.** Open `runs\<run_A>\model\v2\definition\tables\<fact table>.tmdl` and change `Sales[LineTotal]` in the Net Revenue measure to `Sales[LineTotalX]`, then validate again (use a fresh run in `MODEL_GENERATING` if run A is `MODEL_FAILED`). **Expected:** `G4.REF` fails with "column 'LineTotalX' not found in table 'Sales'", `G4.DAX` fails with the engine's error (or `DEPLOY_FAILED` with Fabric's error), a `FILES_CHANGED` warning is present, and the run is `MODEL_FAILED`. The task's wording edits the ModelSpec and regenerates, but the ModelSpec is locked to its approved hash, so the deployed files are edited instead. To continue after a failure, run `python -m app.cli runs transition <run_A> MODEL_GENERATING` (the repair service of T-505 will do this).
3. 🌐 **Invalid relationship.** Use a run whose plan has `nexora_test.dim_product_dupes` as the product dimension, with the Sales to Product relationship under an override: `PATCH /runs/{run}/plan` with `{"expected_hash": "<ExecutionPlan hash>", "ops": [{"op": "override_relationship", "name": "<the Sales to Product relationship>", "rationale": "Test of the duplicate-key check"}]}` (the conformed list and an approved exception must allow the dupes table). Accept the plan, generate the model and measures, then validate. **Expected:** `G4.REL` fails for that relationship with "N duplicate key value(s) on the 'one' side", `evidence.to_duplicate_keys` and the queries, and the run is `MODEL_FAILED`.
4. 💻 **Report blocked.** `python -m app.cli runs transition <run_A> REPORT_GENERATING` while the run is `MODEL_FAILED`. **Expected:** `ILLEGAL_TRANSITION`. The `409 WRONG_STATE` from the report-planning endpoint arrives with T-601, which isn't built yet; the offline checks assert the state machine.
5. 🌐 **Tolerance.** On a new run, before approving the contract, set a wrong example with `PUT /runs/{id}/contract/kpis/Net%20Revenue` and `{"expected_hash": "<contract hash>", "expected_examples": [{"description": "Total net revenue", "value": 1}]}`; take the run through plan, model, measures and validate. **Expected:** `G4.RECON` for Net Revenue fails, with `evidence.expected_example.value: 1`, `dax_value`, the difference and "differs from the business example 1" in the message.
6. 💻 **Offline checks.** `python -m app.manual_tests.t504_offline_checks`. **Expected:** `All checks passed.` (the tolerance, the reference-SQL guard, the Power BI client, every G4 check passing and failing, skipped checks, the report and artifact, the move to `MODEL_FAILED`, replay of the saved SQL, and the 404/409/500 cases).
7. 💻 **Clean up.** Delete the `Nexora_<run>` models from the sandbox workspace, restore any edited files, stop the API, and delete the test runs' folders under `runs\`.

**Not run by Claude:** the live steps (1-3, 5), which need your Entra token and Power BI consent, the real model, the sandbox workspace and the Lakehouse. Claude ran steps 4 and 6 (offline).

---

### T-505 — Validation and Repair service

**Before you start:** the T-504 setup (API running, `SANDBOX_WORKSPACE_ID`, Power BI consent). Each step below uses a fresh run in `MODEL_GENERATING` with the measures added and `model\v2` generated, validated with `POST /runs/{id}/model/validate`. Repair calls the real model for DAX, so `.env` must reach it.

1. 🌐 **Targeted repair.** In `runs\<id>\model\v2\definition\tables\<fact table>.tmdl` change `Sales[LineTotal]` in the Net Revenue measure to `Sales[LineTotalX]` and validate: **Expected:** the run is `MODEL_FAILED`. Then `POST /runs/{id}/model/repair`. **Expected:** HTTP 200, `outcome: passed`, one attempt, `final_state: MODEL_GENERATING`. `git diff --no-index runs\<id>\model\v2 runs\<id>\model\v3` shows only the fact table's file (the typo was in the deployed files, so the repair restores the measure from the ModelSpec after the model re-checks it); `ValidationReport.json` shows the failed run, then a run with `repair_attempt: 1` that passed.
2. 🌐 **Escalation.** Make the model read a source column that doesn't exist: in the Lakehouse (or in `runs\<id>\model\v2` for a column of a Direct Lake table) rename a column that a measure uses, then validate. **Expected:** a failing `G4.DAX` check whose message names the column (for example "The refresh failed: Column 'LineTotal' not found ..."). `POST /runs/{id}/model/repair` then returns `outcome: user_input_only`, no attempts, `final_state: NEEDS_INPUT`, and a `message` naming the column. No model call is made. `python -m app.cli runs show <id>` shows `resume_state: MODEL_FAILED`. Restore the column afterwards.
3. 🌐 **Retry limit.** Set `reconciliation.relative_tolerance` and `absolute_tolerance` to `0` in `config\validation.yaml` (restore afterwards) so that a rounding difference fails `G4.RECON`, then validate and repair. **Expected:** at most 3 attempts (or an earlier `no_progress` stop, if the model returns the measure unchanged), then `NEEDS_INPUT` with a message listing what remains.
4. 🌐 **Audit.** Open `runs\<id>\ValidationReport.json` after step 1 or 3. **Expected:** one run per validation and per repair attempt, each with `attempt`, `repair_attempt`, `artifact_version` and a `fingerprint` per check.
5. 🌐 **Graph boundary.** After step 3 run `python -m app.cli runs show <id>`. **Expected:** `history` has one entry for the repair call (`MODEL_FAILED -> NEEDS_INPUT`), not one per attempt; the attempts appear only in `ValidationReport.json` and in the `attempts` of the response.
6. 💻 **Offline checks.** `python -m app.manual_tests.t505_offline_checks`. **Expected:** `All checks passed.` (fingerprints, the policy, every outcome, the scope guard dropping an attempt, the deterministic fix, the artifacts and the single transition, and the 404/409/422 cases).
7. 💻 **Clean up.** Restore `config\validation.yaml`, delete the models from the sandbox workspace, stop the API, and delete the test runs' folders under `runs\`.

**Not run by Claude:** the live steps (1-5), which need your Entra token and Power BI consent, the real model, the sandbox workspace and the Lakehouse. Claude ran step 6.

---

### T-506 — Bridge-table generation

**Before you start:** run A of T-505 with the T-403 data: a run on scope `saleslt` and `nexora_test` with entities including Product and Promotion, the relationships of the bridge analyzed (`POST /runs/{id}/relationships/analyze` with `nexora_test.bridge_product_promotion.ProductID` to `saleslt.SalesLT_Product.ProductID` and `PromotionID` to `nexora_test.dim_promotion.PromotionID` as user candidates), bridge proposal `B1` (Product x Promotion, `existing_table`) approved (`POST /runs/{id}/approvals` with `{"artifact": "BridgeProposal:B1", "action": "ACCEPT", "expected_hash": "<BridgeProposals hash>"}`), the plan accepted, the model generated with measures, and validated once (`POST /runs/{id}/model/validate` passing: that is the baseline for the totals). The run's Lakehouse must be in the sandbox workspace (`SANDBOX_WORKSPACE_ID`).

1. 🌐 **Bridge generated.** `POST /runs/{run_A}/model/bridges/B1/generate`. **Expected:** HTTP 200, a `version` one higher than the validated one, `validation.passed: true`, and the checks `G4.BRIDGE.UNIQUE`, two `G4.BRIDGE.ORPHANS` and `G4.BRIDGE.TOTALS` all `pass`. `runs\<run_A>\ModelSpec.yaml` has `bridge_product_promotion` with `role: bridge` and two `many_to_one` relationships from it (to Product with `cross_filter: both`, to Promotion `single`). In the web model view of the deployed model (`Nexora_<run>`) the bridge and its two relationships are visible.
2. 🌐 **No double counting.** On the previous model version (`runs\<run_A>\model\v<n>`, deployed with `python -m app.cli deploy model ... --name Nexora_before`) and on the new one, run `EVALUATE ROW("All", [Net Revenue])` in the web model view, and compare both with the SQL total (`SELECT SUM(d.LineTotal) FROM saleslt.SalesLT_SalesOrderDetail d JOIN saleslt.SalesLT_SalesOrderHeader h ON h.SalesOrderID = d.SalesOrderID WHERE h.Status <> 6`). **Expected:** all three values match, and the `G4.BRIDGE.TOTALS` evidence shows `total_before` and `total_with_bridge` equal.
3. 🌐 **Per-promotion values.** In the web model view run `EVALUATE SUMMARIZECOLUMNS('Promotion'[PromotionName], "NR", [Net Revenue])` and compare each row with a hand-written SQL join through the bridge (`... JOIN nexora_test.bridge_product_promotion b ON b.ProductID = d.ProductID JOIN nexora_test.dim_promotion p ON p.PromotionID = b.PromotionID ... GROUP BY p.PromotionName`). **Expected:** the values match (a product in two promotions counts in both, so the rows add up to more than the grand total).
4. 🌐 **Duplicates fail.** In the sandbox Lakehouse insert a duplicate pair into `nexora_test.bridge_product_promotion` with a Spark notebook cell (`spark.sql("INSERT INTO nexora_test.bridge_product_promotion SELECT * FROM nexora_test.bridge_product_promotion LIMIT 1")`), then `POST /runs/{run_A}/model/validate`. **Expected:** `G4.BRIDGE.UNIQUE` fails showing the pair and its count, and the run is `MODEL_FAILED`. Remove the duplicate row afterwards by rerunning `fixtures\create_test_tables.ipynb`.
5. 🌐 **Notebook path (optional).** Add a rule to `config\derivation_rules.yaml` (restore it afterwards) for entities Product and Region, run T-403 for a run that has a Region entity with no mapping table, approve the proposal, then generate it. **Expected:** `runs\<id>\bridges\B1.ipynb` exists, a notebook `Nexora_<run>_B1` is in the sandbox workspace and ran, `nexora_generated.bridge_b1_product_region` exists in the Lakehouse, and the model references it. Read the SQL in the notebook: it is the model's draft and should match the rule.
6. 💻 **Offline checks.** `python -m app.manual_tests.t506_offline_checks`. **Expected:** `All checks passed.` (the notebook and the items client for notebooks and jobs, the model changes and filter directions, every G4.BRIDGE check passing and failing, deduplication under a rule, a derived bridge, the SQL guard, a failing notebook, the sandbox rule, and the 404/409/422/403/502 cases).
7. 💻 **Clean up.** Delete the models and notebooks from the sandbox workspace and the `nexora_generated` tables, restore `config\derivation_rules.yaml`, stop the API, and delete the test runs' folders under `runs\`.

**Not run by Claude:** the live steps (1-5), which need your Entra token and Power BI consent, the real model, the sandbox workspace and Lakehouse. Claude ran step 6.

---

## Next tasks

Sections for T-507 and later are added when each task is implemented.

## Helper scripts

Any script a manual test needs is committed under `app/manual_tests/` (one file per task, named `t<id>_<what>.py`) so every developer runs the same code. Run them as modules from the project root: `python -m app.manual_tests.<name>`. Never keep them as untracked files in the project root or in a personal scratch folder.

| Script | Task | Purpose |
|---|---|---|
| `app/manual_tests/t002_check.py` | T-002 | One sign-in for the Lakehouse and SQL connectors |
| `app/manual_tests/t101_offline_checks.py` | T-101 | Offline checks of the state table, file store and SQL store logic |
| `app/manual_tests/t102_offline_checks.py` | T-102 | In-process checks of the API endpoints, error envelope and CORS |
| `app/manual_tests/t103_offline_checks.py` | T-103 | Fake-Fabric checks of the Fabric client, scope binding and scope locking |
| `app/manual_tests/t103_connectors_check.py` | T-103 | Live check that scope-based connectors reach the Lakehouse and its SQL endpoint |
| `app/manual_tests/t105_offline_checks.py` | T-105 | Throwaway-key JWT checks of token validation, OBO, attribution and the auth gate |
| `app/manual_tests/t201_offline_checks.py` | T-201 | Checks of BusinessContract validation, round trip, CLI and schema export |
| `app/manual_tests/t202_offline_checks.py` | T-202 | Fake-LLM checks of the compile graph, ambiguity rules, versioning and the /compile endpoint |
| `app/manual_tests/t203_offline_checks.py` | T-203 | Fake-LLM checks of answering, dismissing, locked facts and KPI edits |
| `app/manual_tests/t204_offline_checks.py` | T-204 | Fake-LLM checks of Gate G1, the approval actions, locking, roles and the approvals log |
| `app/manual_tests/t205_offline_checks.py` | T-205 | Checks of `contract` and `artifacts` in the run detail and `GET /me` |
| `app/manual_tests/t301_offline_checks.py` | T-301 | Fake-Lakehouse checks of the harvester, versioning and the harvest/inventory endpoints |
| `app/manual_tests/t302_offline_checks.py` | T-302 | Fake-SQL-endpoint checks of the data profiler and the profile endpoint |
| `app/manual_tests/t303_offline_checks.py` | T-303 | Fake-SQL-and-LLM checks of relationship candidates, evidence, rejections and the endpoints |
| `app/manual_tests/t304_offline_checks.py` | T-304 | Checks of Gate G2, exceptions, Accept of the inventory and data gaps |
| `app/manual_tests/t401_offline_checks.py` | T-401 | Fake-LLM checks of the glossary, source scoring, the conformed policy and `plan/sources` |
| `app/manual_tests/t402_offline_checks.py` | T-402 | Fake-LLM checks of KPI feasibility, data gaps and `plan/feasibility` |
| `app/manual_tests/t403_offline_checks.py` | T-403 | Fake-SQL checks of bridge detection, mapping-table evidence, derivation rules, approvals and `plan/bridges` |
| `app/manual_tests/t404_offline_checks.py` | T-404 | Checks of ModelSpec and ExecutionPlan generation, plan validation, the `plan` endpoints and `cli plan validate` |
| `app/manual_tests/t405_offline_checks.py` | T-405 | Checks of Gate G3, plan edits, Accept and Reject of the ExecutionPlan |
| `app/manual_tests/t501_offline_checks.py` | T-501 | Fake-Fabric checks of the deployment client, the sandbox guard and `cli deploy model` |
| `app/manual_tests/t502_offline_checks.py` | T-502 | Checks of the TMDL generator, `model/generate` and `cli model generate` |
| `app/manual_tests/t503_offline_checks.py` | T-503 | Fake-LLM checks of the DAX pre-check, the `dax_measure` graph and `model/measures` |
| `app/manual_tests/t504_offline_checks.py` | T-504 | Fake-Fabric, Power BI, SQL and LLM checks of the G4 checks, the report and `model/validate` |
| `app/manual_tests/t505_offline_checks.py` | T-505 | Fake-service checks of the repair policy, the `repair` graph, the scope guard and `model/repair` |
| `app/manual_tests/t506_offline_checks.py` | T-506 | Fake-service checks of bridge generation, the notebook, G4.BRIDGE.* and `model/bridges/{id}/generate` |

## Adding a task

When a task reaches `Awaiting manual test`:

1. Add a section under its milestone heading: `### T-xxx — Title`.
2. Rewrite each acceptance criterion from `.claude/tasks/<milestone>.md` as a numbered step with the **exact command, URL or payload** of the real implementation and its **Expected** result.
3. If a step needs a script, save it as `app/manual_tests/t<id>_<what>.py` (module with a `main()` and a docstring giving the expected result), list it in the table above, and call it with `python -m app.manual_tests.<name>`.
4. Mark each step 💻 (offline) or 🌐 (needs live Azure/Fabric or a browser).
5. Add a clean-up step if the test creates files or edits `.env`.
6. Keep earlier sections accurate: if a later task changes a command or behavior, update the affected steps in the same change.

Order of work for each task: `/implement-task` → run the steps here → `/implement-task done T-xxx` → `/commit-push` → PR → `/cleanup-branch`.
