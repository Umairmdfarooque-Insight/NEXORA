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

## M1 onward

Sections for T-101 and later are added when each task is implemented.

## Helper scripts

Any script a manual test needs is committed under `app/manual_tests/` (one file per task, named `t<id>_<what>.py`) so every developer runs the same code. Run them as modules from the project root: `python -m app.manual_tests.<name>`. Never keep them as untracked files in the project root or in a personal scratch folder.

| Script | Task | Purpose |
|---|---|---|
| `app/manual_tests/t002_check.py` | T-002 | One sign-in for the Lakehouse and SQL connectors |

## Adding a task

When a task reaches `Awaiting manual test`:

1. Add a section under its milestone heading: `### T-xxx — Title`.
2. Rewrite each acceptance criterion from `.claude/tasks/<milestone>.md` as a numbered step with the **exact command, URL or payload** of the real implementation and its **Expected** result.
3. If a step needs a script, save it as `app/manual_tests/t<id>_<what>.py` (module with a `main()` and a docstring giving the expected result), list it in the table above, and call it with `python -m app.manual_tests.<name>`.
4. Mark each step 💻 (offline) or 🌐 (needs live Azure/Fabric or a browser).
5. Add a clean-up step if the test creates files or edits `.env`.
6. Keep earlier sections accurate: if a later task changes a command or behavior, update the affected steps in the same change.

Order of work for each task: `/implement-task` → run the steps here → `/implement-task done T-xxx` → `/commit-push` → PR → `/cleanup-branch`.
