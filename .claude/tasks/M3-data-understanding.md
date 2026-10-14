# M3 — Data Understanding

**Exit deliverable:** validated metadata inventory.

The existing code (`metadata_inventory.py`, `data_profiler.py`, `semantic_mapper.py`, `relationship_validator.py`, `test_product_mapping.py`) is the starting point. These tasks generalize it, removing the hardcoded `saleslt` table names, and attach it to a run.

---

### T-301 — Metadata Harvester per run

**Depends on:** T-204, T-103 · **Spec:** FR-005, §8.3, `MetadataInventory.json` (§10)

**Build**
- `POST /runs/{id}/harvest`, which requires state `REQUIREMENT_APPROVED`. It harvests the run's scoped Lakehouse: one or more schemas, tables, columns, data types, and descriptions where available.
- Output `runs/<id>/MetadataInventory.json`, with per-table errors recorded rather than aborting the run.
- Remove all hardcoded schema and table names from the harvester.

**Manual test**
1. On an approved run scoped to the sample Lakehouse, call `/harvest`. **Expected:** `MetadataInventory.json` lists every `saleslt` table with its columns and types.
2. Compare three random tables against the Lakehouse explorer in the Fabric portal. **Expected:** same column names and types.
3. Call `/harvest` on a run in `CREATED` state. **Expected:** `409`.
4. Scope a run to the `nexora_test` schema (T-004) and harvest it. **Expected:** the four fixture tables appear, which shows nothing is hardcoded.

**Done when:** inventory is produced for any selected scope.

---

### T-302 — Generic data profiler

**Depends on:** T-301 · **Spec:** FR-006, NFR-008, §14 (minimum data to the model)

**Build**
- Replace `profile_product_ids` with a generic profiler. For each **candidate** table, meaning tables matched to contract entities, so the whole Lakehouse isn't profiled, compute:
  - row count
  - nulls and distinct count for each column
  - key uniqueness for likely key columns
  - min/max of date columns (date coverage)
  - freshness: max date, or last-modified time
- Every result has `status` (`ok` | `warning` | `error`), `evidence` (the numbers and the query used) and `warnings`.
- Queries are read-only, with identifiers safely quoted (`[schema].[table]`).
- Only these summaries can ever be sent to an LLM, never raw rows.

**Manual test**
1. Harvest and profile a run. Open the profile for `SalesLT_Product`. **Expected:** the row count matches `SELECT COUNT(*) FROM saleslt.SalesLT_Product` run by hand in the SQL endpoint.
2. Check `ProductID`. **Expected:** key uniqueness `true`, with distinct count equal to row count.
3. Profile `nexora_test.dim_product_dupes`. **Expected:** `ProductID` uniqueness `false`, status `warning`, and the duplicate count in the evidence.
4. Check a date column's min/max against a hand-written `SELECT MIN(), MAX()`. **Expected:** the values match.

**Done when:** profile numbers match hand-run SQL and include evidence.

---

### T-303 — Relationship evidence

**Depends on:** T-302 · **Spec:** FR-007, §9 (Relationships row), Business rule 7

**Build**
- Generate candidate relationships from:
  - deterministic naming heuristics (`XxxID` ↔ `Xxx.XxxID`)
  - the LLM semantic mapper (`semantic_mapper.py`), whose output stays labelled as **candidates** only
- For each candidate, compute:
  - type compatibility
  - value overlap %
  - cardinality (1:1, 1:\*, \*:\*)
  - orphan rate
  - confidence (high, medium or low, with the thresholds stated in the output)
- Generalize `relationship_validator.py` and the query in `test_product_mapping.py`. Store the results in the inventory under `relationship_evidence`.

**Manual test**
1. For `SalesLT_SalesOrderDetail.ProductID → SalesLT_Product.ProductID`, compare the orphan rate with the output of `python -m app.test_product_mapping`. **Expected:** matching numbers, cardinality `*:1` and confidence `high`.
2. Find an LLM-suggested candidate with no real overlap, or force one by joining `ProductID` to `CustomerID`. **Expected:** confidence `low`, with the overlap % shown.
3. Check `nexora_test.dim_product_dupes`. **Expected:** relationships to it are flagged \*:\* or as failing uniqueness. This is the **"Invalid relationship"** evidence.

**Done when:** every proposed relationship carries evidence and confidence.

---

### T-304 — Gate G2 and inventory UI

**Depends on:** T-303, T-205 · **Spec:** §12 G2, FR-005–FR-007, NFR-004, Business rule 5

**Build**
- G2 automated checks:
  - sources accessible
  - metadata complete for the candidate tables
  - key/profile warnings summarized
  - raw or non-conformed sources flagged as needing **exception approval**
- If the checks pass, the run moves to `DATA_PROFILED`. Exceptions need an explicit reviewer Accept, with a rationale.
- **Inventory UI:** tables, column profiles, warnings, and relationship evidence (overlap, orphans, cardinality, confidence). Each warning links to its evidence query.
- Failure actions: re-harvest, narrow the scope, or raise a **data gap**.

**Manual test**
1. On a run against `saleslt`, run G2. **Expected:** `DATA_PROFILED`, and the UI shows profiles and relationships with evidence.
2. On a run scoped to include `nexora_test.dim_product_dupes`, run G2. **Expected:** a warning is shown. If the table is a candidate, G2 requires a reviewer decision before progressing.
3. Click a warning. **Expected:** you can see the query and the numbers behind it.

**Done when (M3 exit):** a validated metadata inventory exists for the run and is reviewable in Rayfin.
