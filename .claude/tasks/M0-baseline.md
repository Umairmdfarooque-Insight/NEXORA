# M0 — Baseline

Make the existing `app/` code reliable before building on it. Not a milestone in the spec; it's groundwork for M1.

---

### T-001 — Fix dependencies and configuration loading

**Depends on:** none · **Spec:** NFR-006

**Build**
- Add the missing packages to `requirements.txt`: `pydantic`, `pyodbc`, `pyyaml`, `fastapi`, `uvicorn`.
- In `app/config.py`, load `.env` once, from `PROJECT_ROOT / ".env"`. It currently calls `load_dotenv()` twice.
- Keep the clear `ValueError` for missing required settings.

**Manual test**
1. Create a fresh virtualenv and run `pip install -r requirements.txt`. **Expected:** installs without errors.
2. From the project root, run `python -c "import app.config; print(app.config.APP_NAME)"`. **Expected:** prints `Nexora`.
3. Temporarily rename `AZURE_OPENAI_API_KEY` in `.env` and repeat step 2. **Expected:** `ValueError: Missing required configuration: AZURE_OPENAI_API_KEY`. Restore the key afterwards.
4. Run the same command from a different working directory, using `python -c "import sys; sys.path.insert(0, r'<project>'); import app.config"`. **Expected:** it still finds `.env`.

**Done when:** a clean install runs every existing `app/test_*.py` script without `ImportError`.

---

### T-002 — Share one Azure credential across connectors

**Depends on:** T-001 · **Spec:** NFR-001

**Build**
- Create `app/auth.py`, exposing one shared credential. Use `InteractiveBrowserCredential` with the token cache enabled.
- Use it in both `FabricLakehouseConnector` and `FabricSQLConnector`, instead of each connector creating its own.

**Manual test**
1. Write a scratch script that calls `build_metadata_inventory(...)` and then `profile_product_ids(FabricSQLConnector())` in the same process.
2. Run it. **Expected:** the browser sign-in appears **once**, not twice.
3. Run it again within the hour. **Expected:** no sign-in prompt, or only an account picker.

**Done when:** one process needs at most one interactive sign-in.

---

### T-003 — Environment smoke-check command

**Depends on:** T-002 · **Spec:** NFR-007

**Build**
- Add `python -m app.tools.smoke`. It runs these checks and prints `PASS`/`FAIL` with the reason for each:
  1. LLM endpoint returns a response
  2. Lakehouse table listing works
  3. SQL endpoint connects and runs `SELECT 1`
- Exit code `0` only if all checks pass.

**Manual test**
1. Run `python -m app.tools.smoke`. **Expected:** three `PASS` lines and exit code 0.
2. Set `FABRIC_SQL_SERVER` to an invalid host and run it again. **Expected:** the SQL check shows `FAIL` with a readable error, the other two still `PASS`, and the exit code isn't 0.

**Done when:** a new developer can confirm their environment with one command.

---

### T-004 — Test fixtures in the sandbox Lakehouse

**Depends on:** T-003 · **Spec:** §6 Acceptance Scenarios, §15

Later tasks need data that deliberately breaks rules. Create it once, in a **sandbox** schema such as `nexora_test`. Never use production data for this.

**Build**
- Add a notebook or SQL script, `fixtures/create_test_tables.sql` or `.ipynb`, that creates:
  - `dim_product_dupes`: a product dimension with **duplicate** `ProductID` values (for the "Invalid relationship" scenario)
  - `dim_promotion` and `bridge_product_promotion`: a valid many-to-many mapping (for the "Many-to-many bridge" scenario)
  - `dim_campaign`: a table that relates many-to-many to product **with no mapping table** (for the "Unsupported bridge" scenario)
- Document each table's purpose in `fixtures/README.md`.

**Manual test**
1. Run the fixture script against the sandbox Lakehouse.
2. In the Fabric SQL endpoint, run `SELECT ProductID, COUNT(*) FROM nexora_test.dim_product_dupes GROUP BY ProductID HAVING COUNT(*) > 1`. **Expected:** at least one row.
3. Run `python -m app.test_metadata_inventory`, pointed at schema `nexora_test`. **Expected:** all four tables are listed with their columns.

**Done when:** the fixture tables exist and can be recreated by rerunning the script.
