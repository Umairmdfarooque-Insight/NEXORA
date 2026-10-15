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

## M2 onward

Sections for T-201 and later are added when each task is implemented.

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

## Adding a task

When a task reaches `Awaiting manual test`:

1. Add a section under its milestone heading: `### T-xxx — Title`.
2. Rewrite each acceptance criterion from `.claude/tasks/<milestone>.md` as a numbered step with the **exact command, URL or payload** of the real implementation and its **Expected** result.
3. If a step needs a script, save it as `app/manual_tests/t<id>_<what>.py` (module with a `main()` and a docstring giving the expected result), list it in the table above, and call it with `python -m app.manual_tests.<name>`.
4. Mark each step 💻 (offline) or 🌐 (needs live Azure/Fabric or a browser).
5. Add a clean-up step if the test creates files or edits `.env`.
6. Keep earlier sections accurate: if a later task changes a command or behavior, update the affected steps in the same change.

Order of work for each task: `/implement-task` → run the steps here → `/implement-task done T-xxx` → `/commit-push` → PR → `/cleanup-branch`.
