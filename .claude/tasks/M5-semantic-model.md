# M5 — Semantic Model

**Exit deliverable:** approved semantic model.

---

### T-501 — Sandbox deployment client

**Depends on:** T-105 · **Spec:** FR-019, §8.8, §13 steps 1 and 7, NFR-003 (idempotency)

**Build**
- Add a `SANDBOX_WORKSPACE_ID` setting. All generation targets go to the sandbox only.
- `app/deploy/fabric_items.py`:
  - create or update a semantic model from a TMDL definition through the Fabric item-definition APIs (`POST /v1/workspaces/{ws}/semanticModels`, then `.../updateDefinition` for later versions)
  - poll long-running operations until they finish
- Idempotent: if a model with the same name exists, update it instead of creating a duplicate.

**Manual test**
1. Hand-write a minimal TMDL model: one table over `SalesLT_Product` and one measure, `Product Count = COUNTROWS(...)`. Deploy it to the sandbox.
2. **Expected:** the model appears in the sandbox workspace in the Fabric portal and opens in the web model view.
3. Change the measure name and deploy again. **Expected:** the **same** model is updated, and the workspace doesn't show a second copy.
4. Set a production workspace ID as the target. **Expected:** refused, because only the sandbox is allowed before promotion.

**Done when:** sandbox create and update are reliable and repeatable.

---

### T-502 — TMDL generator

**Depends on:** T-405, T-501 · **Spec:** FR-011, §8.5, §9 (TMDL row: deterministic serialization)

**Build**
- A deterministic serializer from `ModelSpec.yaml` to a TMDL folder. It covers the database and model files, one file per table, relationships, the Direct Lake expression or partitions, hierarchies, formatting and display folders.
- Versioned per run: `runs/<id>/model/v<n>/`.
- No LLM involvement. The same ModelSpec always produces byte-identical TMDL (NFR-009).

**Manual test**
1. Generate TMDL for the approved Net Revenue plan. **Expected:** the files match the ModelSpec tables and relationships.
2. Generate it again and diff the two versions. **Expected:** identical.
3. Deploy to the sandbox (T-501) and open the model view. **Expected:** the tables, relationships (with correct cardinality and direction) and the Date hierarchy are visible.

**Done when:** the approved plan becomes a deployable model structure without an LLM.

---

### T-503 — DAX measure generation

**Depends on:** T-502 · **Spec:** FR-011, §9 (KPI logic row), Business rules 1–2

**Build**
- For each feasible KPI, the LLM proposes DAX from:
  - the approved `formula_intent`, grain, filters, time logic and exclusions
  - the ModelSpec object names
- Insert the measures into TMDL, with a description that quotes the approved definition, plus format string and display folder.
- The LLM output is a **candidate**. It isn't trusted until T-504 validates it.

**Manual test**
1. Generate the measures for Net Revenue. **Expected:** the DAX references only existing tables and columns, and implements the "excluding cancelled orders" rule.
2. Deploy to the sandbox. In the Power BI web model view, run a quick DAX query, `EVALUATE ROW("NR", [Net Revenue])`. **Expected:** returns a number.
3. Hand-calculate the same figure in the SQL endpoint. **Expected:** it matches. T-504 automates this check.

**Done when:** each approved KPI has a candidate DAX measure in the model.

---

### T-504 — Model validators and Gate G4

**Depends on:** T-503 · **Spec:** FR-012, §12 G4, `ValidationReport.json` (§10), §8.7

**Build**
- Validators, each writing checks, evidence, severity and errors to `runs/<id>/ValidationReport.json`:
  - **Reference check:** every measure and relationship references existing objects.
  - **Relationship tests:** rerun uniqueness and orphan checks on the deployed model's sources.
  - **DAX execution:** run each measure through the Power BI `executeQueries` REST API.
  - **Reconciliation:** compare each measure's total, and one sliced value, with an equivalent SQL query, within a stated tolerance.
  - **RLS checks:** roles exist and filter expressions are valid. Test them with an effective identity where possible.
- A failed G4 means state `MODEL_FAILED`, and the report stage cannot start.

**Manual test**
1. Validate the T-503 model. **Expected:** all checks `pass`, and the reconciliation shows the DAX and SQL values side by side.
2. Hand-edit the measure to `SUM(SalesLT_SalesOrderDetail.LineTotalX)` and validate. **Expected:** the DAX execution and reference checks fail with the error text, and the state is `MODEL_FAILED`.
3. Build a model that uses `nexora_test.dim_product_dupes` as a dimension and validate it. **Expected:** the relationship test fails with duplicate-key evidence. This is the **"Invalid relationship"** scenario.
4. Try to start report generation while the model is `MODEL_FAILED`. **Expected:** `409`.

**Done when:** an invalid model cannot progress, and each failure includes evidence.

---

### T-505 — Validation and Repair service

**Depends on:** T-504 · **Spec:** FR-016, FR-017, §8.7, §9 (Regeneration row), NFR-003

**Build**
- Normalize validator errors into a common structure: artifact, object, error code, message, evidence.
- Classify each failure:
  - **deterministic repair**, for example a wrong format string
  - **LLM-assisted regeneration** of only the failing object, for example one measure
  - **user input** required
- Targeted regeneration: only the failed or impacted objects change. Every other TMDL file stays byte-identical.
- Retry limit of 3 per object. No-progress detection: the same error fingerprint twice in a row moves the run to `NEEDS_INPUT`.

**Manual test**
1. Inject a typo into one measure, then run validation and repair. **Expected:** the measure is regenerated and revalidated, and validation passes. Diff the `v<n>` and `v<n+1>` folders: **only** that measure's file changed. This matches the Definition of Done item on intentional model failure.
2. Make the failure unfixable, for example a contract KPI that references a column which no longer exists. **Expected:** at most 3 attempts or a no-progress stop, then state `NEEDS_INPUT` with a message for the user.
3. Check `ValidationReport.json`. **Expected:** each attempt is recorded with its retry count.

**Done when:** failures are repaired with the smallest possible change, or escalated.

---

### T-506 — Bridge-table generation

**Depends on:** T-505, T-403 · **Spec:** FR-008, §15, Business rule 4, acceptance scenario "Many-to-many bridge"

**Build**
- For an **approved** bridge proposal:
  - Existing mapping table: add it to the model, with two one-to-many relationships.
  - Approved derivation rule: generate the data-engineering artifact (for example a view or notebook) in the sandbox, validate it, then reference it.
- Validate mapping uniqueness, duplicates and filter behavior (no double counting).
- Duplicates are removed only under an approved deterministic rule. Otherwise validation fails.

**Manual test**
1. Approve the Product × Promotion bridge from T-403, then generate and validate. **Expected:** `bridge_product_promotion` is in the model with two 1:\* relationships, and validation passes.
2. Run a DAX query for sales by promotion, and compare it with a hand-written SQL query. **Expected:** the totals match, with no double counting.
3. Insert a duplicate row into the bridge table and revalidate. **Expected:** fails with duplicate evidence.

**Done when:** acceptance scenario **"Many-to-many bridge"** passes.

---

### T-507 — Model review and approval UI

**Depends on:** T-506 · **Spec:** §12 G4 (human decision), §2.2 approval scopes, FR-018

**Build**
- **Model review screen:**
  - tables and relationships
  - each measure's DAX next to its approved KPI definition
  - reconciliation results
  - RLS roles
  - the full ValidationReport
- Approval scopes:
  - **BI engineer:** technical correctness (DAX, relationships, performance)
  - **Business owner:** business fidelity, confirming the measure implements the approved definition without redefining it (rule 2)
  - **Security reviewer:** RLS
- When all required approvals are recorded and G4 passes, the run moves to `MODEL_APPROVED`.

**Manual test**
1. Open the model review. **Expected:** the Net Revenue DAX appears next to "SUM(LineTotal) excluding cancelled orders", with the reconciled values.
2. Approve as the BI engineer only. **Expected:** the state is still awaiting business and security approval.
3. Complete the remaining approvals. **Expected:** `MODEL_APPROVED`, with three attributable approval records.

**Done when (M5 exit):** an approved semantic model exists in the sandbox.
