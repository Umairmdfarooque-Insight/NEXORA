# M0 — Baseline

Make the existing `app/` code reliable before building on it. M0 isn't a milestone in the spec; it's groundwork for M1. Shared shapes are in [CONTRACTS.md](CONTRACTS.md).

---

### T-001 — Fix dependencies and configuration loading

**Depends on:** none · **Spec:** NFR-006

#### Problem statement
A fresh install fails, because `requirements.txt` is missing `pydantic` and `pyodbc`, which the code imports. `app/config.py` calls `load_dotenv()` twice. The first call searches from the current working directory, so the settings that load depend on where the command is run from.

#### Functional requirements
1. `requirements.txt` lists every third-party package the code imports: `openai`, `python-dotenv`, `azure-identity`, `requests`, `pydantic`, `pyodbc`, `pyyaml`, `fastapi` and `uvicorn`.
2. `app/config.py` loads `.env` exactly once, from `PROJECT_ROOT / ".env"`.
3. Required settings are read through `get_required_setting()`. Optional settings return `None` when unset.
4. The values from the shell environment take precedence over `.env` values (`override=False`).

#### API contracts
Module `app.config`:

| Name | Type | Required | Default |
|---|---|---|---|
| `APP_NAME` | `str` | no | `"Nexora"` |
| `UI_APP_NAME` | `str` | no | `"Rayfin"` |
| `ENVIRONMENT` | `str` | no | `"development"` |
| `AZURE_OPENAI_ENDPOINT` | `str`, with the trailing `/` stripped | yes | — |
| `AZURE_OPENAI_DEPLOYMENT` | `str` | yes | — |
| `AZURE_OPENAI_API_KEY` | `str` | yes | — |
| `FABRIC_WORKSPACE_ID`, `FABRIC_LAKEHOUSE_ID`, `FABRIC_WORKSPACE_NAME`, `FABRIC_LAKEHOUSE_NAME`, `FABRIC_SQL_SERVER`, `FABRIC_SQL_DATABASE` | `str \| None` | no | `None` |

`get_required_setting(name: str) -> str` returns the stripped value. If the value is missing or blank, it raises `ValueError("Missing required configuration: <name>. Check your .env file.")`.

#### Constraints
- Python 3.12 on Windows.
- Never print or log setting values. Error messages may name a setting, but never include its value.
- Don't change any setting name, because existing code depends on them.

#### Edge cases and error handling
| Case | Expected behavior |
|---|---|
| `.env` file missing | The `ValueError` names the first missing required setting. |
| Value contains only whitespace | Treated as missing. |
| `AZURE_OPENAI_ENDPOINT` has a trailing `/` | Stripped. |
| Variable set in the shell and in `.env` | The shell value wins. |
| Command run from a different directory | `.env` is still found through `PROJECT_ROOT`. |

#### Acceptance criteria
1. **Clean install.** Create a new virtualenv and run `pip install -r requirements.txt`. **Expected:** installs with no errors.
2. **Defaults load.** From the project root, run `python -c "import app.config as c; print(c.APP_NAME)"`. **Expected:** prints `Nexora`.
3. **Missing setting.** Comment out `AZURE_OPENAI_API_KEY` in `.env` and repeat AC-2. **Expected:** `ValueError: Missing required configuration: AZURE_OPENAI_API_KEY. Check your .env file.` with no key value shown. Restore the line afterwards.
4. **Whitespace value.** Set `AZURE_OPENAI_DEPLOYMENT=   ` and repeat AC-2. **Expected:** the same error, naming `AZURE_OPENAI_DEPLOYMENT`. Restore it afterwards.
5. **Directory-independent.** Run `cd C:\` and then `python -c "import sys; sys.path.insert(0, r'<project>'); import app.config as c; print(c.ENVIRONMENT)"`. **Expected:** prints the value from `.env`.
6. **Imports work.** Run `python -c "import app.test_llm, app.test_fabric_sql, app.test_metadata_inventory"`. **Expected:** no `ImportError`.

---

### T-002 — Share one Azure credential across connectors

**Depends on:** T-001 · **Spec:** NFR-001

#### Problem statement
`FabricLakehouseConnector` and `FabricSQLConnector` each create their own `InteractiveBrowserCredential`. A process that uses both prompts the user to sign in twice, and no token is reused between runs.

#### Functional requirements
1. `app/auth.py` provides a single, process-wide credential.
2. Both connectors get their tokens from it.
3. Tokens are cached on disk, so a second run within the token lifetime doesn't need an interactive sign-in.

#### API contracts
Module `app.auth`:
- `STORAGE_SCOPE = "https://storage.azure.com/.default"`
- `SQL_SCOPE = "https://database.windows.net/.default"`
- `FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"`
- `get_credential() -> azure.core.credentials.TokenCredential` always returns the same instance.
- `get_token(scope: str) -> str` returns an access token string.

#### Constraints
- Use `InteractiveBrowserCredential` with `TokenCachePersistenceOptions(name="nexora")`.
- Don't write any token to logs or files outside the MSAL cache.
- The connectors' public methods keep their current signatures.

#### Edge cases and error handling
| Case | Expected behavior |
|---|---|
| User closes the browser sign-in | `ClientAuthenticationError` is raised with a readable message, not a stack of nested errors. |
| Encrypted persistent cache unavailable on this machine | Fall back to an in-memory cache and log one warning. |
| Token expired during a long run | Refreshed silently by the credential. |

#### Acceptance criteria
1. **One sign-in per process.** Write a scratch script that calls `build_metadata_inventory(FabricLakehouseConnector(), "saleslt")` and then `profile_product_ids(FabricSQLConnector())`. Run it. **Expected:** the browser sign-in appears **once**.
2. **Cache reused.** Run the same script again within an hour. **Expected:** no sign-in prompt, or an account picker only.
3. **Same instance.** Run `python -c "from app.auth import get_credential as g; print(g() is g())"`. **Expected:** `True`.

---

### T-003 — Environment smoke-check command

**Depends on:** T-002 · **Spec:** NFR-007

#### Problem statement
There is no quick way to tell whether a machine's configuration, the LLM endpoint, the Lakehouse and the SQL endpoint all work. Developers find out only when a test script fails part-way.

#### Functional requirements
1. One command runs three independent checks: **llm** (the model returns a reply), **lakehouse** (tables can be listed) and **sql** (`SELECT 1` runs).
2. Each check reports `PASS` or `FAIL`, with its duration and a short reason.
3. One failing check doesn't stop the others.
4. Optional JSON output for scripting.

#### API contracts
CLI: `python -m app.tools.smoke [--only llm,lakehouse,sql] [--json]`

Text output:
```
PASS  llm        Azure OpenAI replied (1.2s)
PASS  lakehouse  12 tables in saleslt (0.8s)
FAIL  sql        OperationalError: Login timeout expired (30.0s)
```

JSON output (`--json`):
```json
{ "passed": false, "checks": [ { "name": "sql", "status": "fail", "duration_ms": 30000, "detail": "OperationalError: Login timeout expired" } ] }
```

Exit codes: `0` when all checks pass, `1` when any check fails, `2` for a configuration error or an invalid `--only` value.

#### Constraints
- Read-only. The LLM check uses a prompt of at most 20 tokens.
- 30-second timeout per check.
- No setting values or tokens in the output.

#### Edge cases and error handling
| Case | Expected behavior |
|---|---|
| A required setting is missing | Exit `2`, naming the setting. |
| A check times out | `FAIL … timed out after 30s`. The other checks still run. |
| Unknown name in `--only` | Exit `2`, listing the valid names. |
| `FABRIC_LAKEHOUSE_NAME` unset | The lakehouse check fails, naming the missing setting. |

#### Acceptance criteria
1. **All pass.** Run `python -m app.tools.smoke`. **Expected:** three `PASS` lines, then `echo $LASTEXITCODE` (PowerShell) prints `0`.
2. **One failure is isolated.** Set `FABRIC_SQL_SERVER=invalid.example.com` and run it again. **Expected:** `FAIL sql` with a readable reason, `llm` and `lakehouse` still `PASS`, and exit code `1`.
3. **Single check.** Run `python -m app.tools.smoke --only llm --json`. **Expected:** JSON containing only the `llm` check.
4. **Bad option.** Run `python -m app.tools.smoke --only foo`. **Expected:** exit `2`, listing `llm, lakehouse, sql`.

---

### T-004 — Test fixtures in the sandbox Lakehouse

**Depends on:** T-003 · **Spec:** §6 Acceptance Scenarios, §15

#### Problem statement
The acceptance scenarios need data that deliberately breaks rules: duplicate dimension keys, a many-to-many relationship with a mapping table, and one without a mapping table. The `saleslt` sample has none of these, so the scenarios can't be tested. `saleslt` also has no date table, and Direct Lake models can't create one as a calculated table. The monthly KPIs in the scenarios therefore need a physical date table.

#### Functional requirements
1. A Spark notebook creates the fixture tables in schema `nexora_test` of the **sandbox** Lakehouse.
2. The tables use `ProductID` values that exist in `saleslt.SalesLT_Product`, so they can join to the real data.
3. Rerunning the notebook recreates the tables with the same content.
4. `fixtures/README.md` documents each table and the scenario it supports.

#### API contracts
Files: `fixtures/create_test_tables.ipynb` (PySpark) and `fixtures/README.md`.

| Table | Columns | Required property | Used by |
|---|---|---|---|
| `nexora_test.dim_product_dupes` | `ProductID int, Name string, Category string` | At least 3 `ProductID` values appear more than once | "Invalid relationship" (T-302, T-303, T-504) |
| `nexora_test.dim_promotion` | `PromotionID int, PromotionName string, StartDate date, EndDate date` | 3–5 promotions with unique IDs | "Many-to-many bridge" (T-403, T-506) |
| `nexora_test.bridge_product_promotion` | `ProductID int, PromotionID int` | Unique `(ProductID, PromotionID)` pairs. Some products have more than one promotion, and some promotions cover more than one product. | "Many-to-many bridge" |
| `nexora_test.dim_campaign` | `CampaignID int, CampaignName string, ProductCategory string` | Relates to many products **only** through free-text category. No mapping table exists. | "Unsupported bridge" (T-403) |
| `nexora_test.dim_date` | `Date date, Year int, Quarter string, MonthNumber int, MonthName string` | One row per day, covering every `OrderDate` in `saleslt.SalesLT_SalesOrderHeader`. `Date` is unique. | Monthly KPIs and the Calendar hierarchy (T-404, T-502, T-601) |

#### Constraints
- **The Lakehouse SQL endpoint is read-only.** Tables must be written with Spark (`saveAsTable`, mode `overwrite`), not SQL `CREATE TABLE`.
- Write only to the sandbox Lakehouse and the `nexora_test` schema. Never write to `saleslt`.
- Use small, synthetic data: 100 rows or fewer per table (except `dim_date`), and no real customer data.

#### Edge cases and error handling
| Case | Expected behavior |
|---|---|
| Schema `nexora_test` doesn't exist | The notebook creates it first. |
| Lakehouse doesn't have schemas enabled | The notebook stops with a clear message, because schema-enabled Lakehouses are required. |
| Notebook rerun | The tables are overwritten, with no duplicate rows. |

#### Acceptance criteria
1. **Tables exist.** Run the notebook in the sandbox Lakehouse. **Expected:** the five tables appear under `nexora_test` in the Lakehouse explorer.
2. **Duplicates present.** In the SQL endpoint, run `SELECT ProductID, COUNT(*) c FROM nexora_test.dim_product_dupes GROUP BY ProductID HAVING COUNT(*) > 1`. **Expected:** at least 3 rows.
3. **Bridge is unique.** Run `SELECT ProductID, PromotionID, COUNT(*) FROM nexora_test.bridge_product_promotion GROUP BY ProductID, PromotionID HAVING COUNT(*) > 1`. **Expected:** 0 rows.
4. **Keys join to real data.** Run `SELECT COUNT(*) FROM nexora_test.bridge_product_promotion b LEFT JOIN saleslt.SalesLT_Product p ON b.ProductID = p.ProductID WHERE p.ProductID IS NULL`. **Expected:** `0`.
5. **Date coverage.** Run `SELECT COUNT(*) FROM saleslt.SalesLT_SalesOrderHeader h LEFT JOIN nexora_test.dim_date d ON CAST(h.OrderDate AS date) = d.Date WHERE d.Date IS NULL`. **Expected:** `0`.
6. **Rerunnable.** Run the notebook again, then repeat AC-2 and AC-3. **Expected:** the same results, and the row counts are unchanged.
7. **Visible to the harvester.** Point `app/test_metadata_inventory.py` at schema `nexora_test` and run it. **Expected:** all five tables are listed with their columns.
