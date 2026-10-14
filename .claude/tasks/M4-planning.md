# M4 — Planning

**Exit deliverable:** approved execution and model plan.

---

### T-401 — Entity-to-source mapping and conformed-table resolver

**Depends on:** T-304 · **Spec:** FR-009, §8.4, Business rule 5

**Build**
- Merge `requirement_data_matcher.py` (deterministic) and `semantic_mapper.py` (LLM candidates) into `app/planning/source_resolver.py`.
- Move the hardcoded `ALIASES` into a configurable glossary file, `config/glossary.yaml`.
- Add `config/conformed_sources.yaml`, listing the approved conformed schemas and tables.
- Score each candidate table per entity and KPI. Approved conformed tables score higher. Raw or non-conformed tables are only selectable with an exception.
- Output the **selected and rejected** sources, with a rationale for each.

**Manual test**
1. On the Net Revenue run, resolve sources. **Expected:**
   - Sales maps to `SalesLT_SalesOrderDetail` / `SalesOrderHeader`.
   - Product maps to `SalesLT_Product`.
   - Each has a rationale.
   - Rejected tables are listed with reasons.
2. Remove `SalesLT_Product` from `conformed_sources.yaml` and resolve again. **Expected:** it is either rejected, or selected but marked "requires exception approval".
3. Add a synonym to `glossary.yaml`, for example "item" meaning product, and use it in a prompt. **Expected:** it maps correctly with no code change.

**Done when:** table selection is explained and respects the conformed-source policy.

---

### T-402 — KPI feasibility and Data Gap

**Depends on:** T-401 · **Spec:** Business rule 8, §2.4 (no inventing KPIs), G1/G3 feasibility flags

**Build**
- For each approved KPI, check that every column needed by `formula_intent` maps to a selected source.
- If the data can't support a KPI, mark it **Not Feasible / Data Gap**, listing the missing data. Never produce a substitute calculation.
- A data gap moves the run to `NEEDS_INPUT`, with the options: narrow the scope, provide a source, or raise a data-engineering task.

**Manual test**
1. Approve a contract asking for "Customer Retention Rate", which needs customer activity history that `saleslt` doesn't have. Resolve sources.
2. **Expected:** the KPI is marked `Data Gap`, the missing inputs are listed, the state is `NEEDS_INPUT`, and **no** DAX or proxy measure is proposed.
3. Run the Net Revenue contract. **Expected:** feasible.

**Done when:** unsupported KPIs are stopped, not fabricated.

---

### T-403 — Bridge-table detection and proposal

**Depends on:** T-401 · **Spec:** FR-008, §15 Bridge-Table Design, Business rule 4

**Build**
- Detect many-to-many patterns from the relationship evidence (T-303).
- Handle each situation from §15:
  - **Existing mapping table:** propose it as the bridge, after validating duplicates and key coverage.
  - **Deterministic derivation rule exists:** propose a data-engineering artifact.
  - **Mapping depends on undocumented business judgement:** return `NEEDS_INPUT` and request the mapping rules.
- This task **proposes only**. Generation happens in T-506, after approval.

**Manual test**
1. Use a contract that needs Product × Promotion, against `nexora_test`. **Expected:** `bridge_product_promotion` is proposed as the bridge, with its duplicate and coverage evidence.
2. Use a contract that needs Product × Campaign, which has no mapping table. **Expected:** the run returns `NEEDS_INPUT`, the message asks for mapping rules, and **no bridge is guessed**. This is the "Unsupported bridge" scenario.

**Done when:** bridges are proposed only from evidence or approved rules.

---

### T-404 — ExecutionPlan and ModelSpec generation

**Depends on:** T-402, T-403 · **Spec:** FR-010, §8.4, `ExecutionPlan.yaml` and `ModelSpec.yaml` (§10), §2.3 (Direct Lake / Import)

**Build**
- Pydantic schemas plus YAML output.
- `ExecutionPlan.yaml` contains:
  - selected sources
  - dependencies
  - stages
  - gates
  - target (the sandbox)
  - required approvals
- `ModelSpec.yaml` contains:
  - tables with their roles (fact or dimension) and the fact grain
  - relationships, each with a reference to its evidence
  - storage mode (Direct Lake by default for Lakehouse Delta tables; Import as an option)
  - measures, one per feasible KPI, with formula intent only and no DAX yet
  - hierarchies (for example Date: Year → Quarter → Month)
  - formatting and display folders
  - RLS roles, **only** from the contract's `security` section
- Validators:
  - schema
  - reference checks: every relationship and measure points at an existing table and column
  - policy and feasibility rules

**Manual test**
1. Generate a plan for the Net Revenue run, then open both YAML files. **Expected:**
   - the fact grain is order line
   - the relationships are to Product, Customer and Date, each with evidence references
   - storage mode is Direct Lake
2. Hand-edit `ModelSpec.yaml` so a relationship references a nonexistent column, then run the validator. **Expected:** it fails, naming the bad reference.
3. On a contract with no security requirements, check the spec. **Expected:** no RLS roles. The system must not infer security policy (§14).

**Done when:** the plan and spec are complete, reference-valid and traceable to evidence.

---

### T-405 — Gate G3 and plan review UI

**Depends on:** T-404 · **Spec:** §12 G3, FR-010, FR-018, NFR-004

**Build**
- G3 automated checks:
  - grain defined
  - only approved sources, or ones with an approved exception
  - every join has evidence
  - dependencies complete
- **Plan review UI:** selected and rejected tables with rationale, a relationship diagram or list with evidence, the measures list, storage mode and RLS. Use the standard approval actions.
- A BI engineer approves. The run moves to `PLAN_APPROVED`.

**Manual test**
1. Open the plan in Rayfin. **Expected:** you can see why each table was chosen and why the others were rejected.
2. Click Edit and remove one relationship. **Expected:** G3 re-runs. If a measure depended on that relationship, it fails with a clear message.
3. Restore it and Accept. **Expected:** `PLAN_APPROVED`, with the approval recorded.

**Done when (M4 exit):** an approved execution and model plan exists.
