# M6 — Report

**Exit deliverable:** approved report artifact.

---

### T-601 — Report planner

**Depends on:** T-507 · **Spec:** FR-013, §8.6, `ReportPlan.json` (§10), §9 (Report row)

**Build**
- Generate `runs/<id>/ReportPlan.json` from the approved contract and model. It contains:
  - business questions, taken from the contract
  - intended users
  - pages
  - visuals: type, plus fields and measures bound by object name
  - filters
  - drill paths, using the model hierarchies
  - interaction intent
- The LLM proposes the layout. Deterministic validation checks the plan schema and that **every referenced object exists in the approved model**.

**Manual test**
1. Generate a plan for the Net Revenue run. **Expected:** at least one page answers "Net Revenue by month", and each business question in the contract maps to a visual.
2. Hand-edit a visual to reference a measure that doesn't exist, then validate. **Expected:** fails, naming the missing object.

**Done when:** every contract question has a planned visual bound to real model objects.

---

### T-602 — PBIR generator and sandbox publish

**Depends on:** T-601 · **Spec:** FR-014, §8.6

**Build**
- Write a deterministic PBIR/PBIP generator from `ReportPlan.json`, producing pages, visuals and bindings to the approved semantic model. Version it per run under `runs/<id>/report/v<n>/`.
- Publish it to the sandbox through the Fabric reports item-definition API (create or update, idempotently).

**Manual test**
1. Generate and publish. Open the report in the sandbox workspace. **Expected:** the pages and visuals match the plan, and the visuals show data.
2. Click a month in a visual with a drill path. **Expected:** drill-down works as planned.
3. Publish again. **Expected:** the existing report is updated, not duplicated.

**Done when:** a report bound only to approved objects is visible in the sandbox.

---

### T-603 — Report validators and Gate G5

**Depends on:** T-602, T-505 · **Spec:** FR-015, FR-016, §12 G5, acceptance scenario "Report binding failure"

**Build**
- Validators:
  - PBIR schema
  - binding check: every field and measure exists in the approved model
  - query smoke test for each visual: run the equivalent DAX through `executeQueries`
  - rendered output: export the pages to PNG through the Power BI export API, for review
- Reuse the Validation and Repair service (T-505) at **page or visual granularity**.
- On failure, the state is `REPORT_FAILED`. If the root cause is in the model, return a **model defect** rather than patching the report.

**Manual test**
1. Validate the T-602 report. **Expected:** all checks pass, and page PNGs are saved in the run folder.
2. Edit one visual's PBIR so it binds to `[Net Revenue X]`, which doesn't exist, then validate and repair. **Expected:** only that visual is repaired, and the other page and visual files are unchanged in the diff. This is the **"Report binding failure"** scenario.
3. Break a measure in the **model** instead, then validate the report. **Expected:** the result is classified as a model defect and the run is routed back to the model stage.

**Done when:** report failures are fixed at the smallest scope, or routed to the right stage.

---

### T-604 — Report review and approval UI

**Depends on:** T-603 · **Spec:** §12 G5 (human decision), §2.2 (Project reviewer), FR-018

**Build**
- **Report review screen:**
  - the rendered page images
  - the business question each visual answers
  - binding and query results
  - **Regenerate** on a single page or visual
  - the standard approval actions
- The project reviewer and business user approve usability. The run moves to `REPORT_APPROVED`.

**Manual test**
1. Open the report review. **Expected:** each page image appears with the questions it answers.
2. Click Regenerate on one visual, with the comment "use a bar chart instead". **Expected:** only that visual changes, and validation re-runs.
3. Accept. **Expected:** `REPORT_APPROVED`, with the approval recorded.

**Done when (M6 exit):** an approved report artifact exists in the sandbox.
