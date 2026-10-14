# M2 — Requirement Control

**Exit deliverable:** approved requirement contract.

---

### T-201 — BusinessContract schema

**Depends on:** T-101 · **Spec:** `BusinessContract.yaml` (§10), FR-003, §8.2

**Build**
- Add `app/contracts/business_contract.py` with pydantic models. These replace `RequirementSpec` and become a superset of it:
  - `domain`, `grain`, `dimensions`, `filters`, `currency`, `exclusions`
  - `kpis[]`, each with `name`, `formula_intent`, `grain`, `filters`, `time_logic`, `exclusions`, `currency`, `expected_examples`, `status` (`draft` | `approved`)
  - `security[]`, containing the RLS requirements as stated by the business
  - `open_questions[]`, each with `id`, `text`, `blocking`, `answer`, `status`
  - `locked_facts[]`
- YAML save/load to `runs/<id>/BusinessContract.yaml`, and export the JSON Schema to `schemas/business_contract.schema.json`.
- CLI: `python -m app.cli contract validate <file.yaml>`.

**Manual test**
1. Write `samples/contract_valid.yaml` with one KPI, Net Revenue, filled in completely, and run `contract validate` on it. **Expected:** `VALID`.
2. Copy it, delete the KPI's `formula_intent`, and validate. **Expected:** `INVALID` with the field path in the message.
3. Load the valid file and save it again. **Expected:** the file contents are unchanged after the round trip.

**Done when:** contract validity can be checked from the command line.

---

### T-202 — Requirement Compiler with ambiguity detection

**Depends on:** T-201, T-102 · **Spec:** FR-002, §8.2, §1.1 principle 2, NFR-008, NFR-009

**Build**
- Evolve `app/llm/requirement_analyzer.py` into `app/compiler/requirement_compiler.py`. It takes a run prompt and returns a **draft** `BusinessContract`.
- Use schema-constrained output: pass the BusinessContract JSON Schema to the model's structured-output option, then validate with pydantic. Retry once on a validation failure.
- Ambiguity rules:
  - **Deterministic:** a business-critical term (configurable list, starting with Revenue, Margin, Retention, Same-Store Sales) without an explicit definition always creates a **blocking** question.
  - **LLM:** may add further questions, but cannot remove deterministic ones.
- Add `POST /runs/{id}/compile`. It moves the run to `NEEDS_CLARIFICATION` when any blocking question is open. Otherwise the run stays ready for G1.
- Send only the prompt and contract context to the LLM, no source data (NFR-008).

**Manual test**
1. Create a run with the prompt "Show revenue by month for 2024", then call `/compile`. **Expected:** state `NEEDS_CLARIFICATION`, and a blocking question asking how Revenue is defined (for example gross, net, or including tax).
2. Create a run with "Show Net Revenue by month for 2024. Net Revenue = SUM(LineTotal) excluding cancelled orders, USD." and compile it. **Expected:** no blocking question about Revenue, and the KPI `formula_intent` reflects the definition.
3. Compile the step 2 prompt twice. **Expected:** both contracts have the same structure: the same KPIs, dimensions and question set (NFR-009). Wording may vary.
4. Open `runs/<id>/BusinessContract.yaml`. **Expected:** it passes `contract validate`.

**Done when:** acceptance scenario **"Ambiguous Revenue"** stops at clarification.

---

### T-203 — Clarification loop

**Depends on:** T-202 · **Spec:** FR-002, FR-003, §8.2 (locked facts)

**Build**
- `POST /runs/{id}/questions/{qid}/answer`, with body `{answer}`. It stores the answer, adds it to `locked_facts`, recompiles, and keeps locked facts unchanged.
- When no blocking questions remain open, the run leaves `NEEDS_CLARIFICATION`.
- KPI definition edit endpoint: `PUT /runs/{id}/contract/kpis/{name}` (FR-003, edit).

**Manual test**
1. Use the run from T-202 step 1. Answer the Revenue question with "Net Revenue = SUM(LineTotal) excluding cancelled orders". **Expected:** the question status is `answered`, the KPI `formula_intent` is updated, and the answer appears in `locked_facts`.
2. Recompile. **Expected:** the locked fact is still present and the question is not asked again.
3. Check the run state. **Expected:** it is no longer `NEEDS_CLARIFICATION`.

**Done when:** a run can't progress while a blocking question is open, and answers persist across recompiles.

---

### T-204 — Approval service and Gate G1

**Depends on:** T-203, T-105 · **Spec:** FR-018, §12 G1, Business rules 1–2, §14 (record approvers)

**Build**
- `app/approvals/`: actions **Accept, Edit, Reject, Explain, Regenerate**. Each record holds artifact, artifact hash, action, user, timestamp and comment, appended to `runs/<id>/approvals.jsonl`.
- `app/gates/g1_requirement.py`, with these automated checks:
  - schema complete
  - no blocking questions open
  - every KPI has `formula_intent`, `grain` and `currency`
  - feasibility flags present
- `POST /runs/{id}/gates/G1/approve` runs the checks. If any fail it returns `409` with the failed checks. If they pass and the business owner Accepts, the run moves to `REQUIREMENT_APPROVED` and the contract is **locked**: edits return `409` unless the run is returned to requirement analysis.
- **Explain** returns the compiler's rationale for each KPI and question.

**Manual test**
1. On a run that still has a blocking question, call G1 approve. **Expected:** `409`, listing "blocking question open".
2. Resolve it, then approve with Accept. **Expected:** state `REQUIREMENT_APPROVED`, and `approvals.jsonl` has your UPN, a timestamp and the contract hash.
3. Try `PUT /runs/{id}/contract/kpis/Net Revenue`. **Expected:** `409`, contract locked.
4. On another run, call Reject with a comment. **Expected:** the run returns to clarification, and the rejection is recorded.
5. Call Explain. **Expected:** readable rationale for each KPI.

**Done when:** every approval is attributable, time-stamped and enforced by G1.

---

### T-205 — Clarification and contract review UI

**Depends on:** T-204 · **Spec:** §8.1 (clarification panel, approval actions), FR-002, FR-003, FR-018

**Build**
- **Run detail → Clarification panel:** shows open questions and lets the user answer them inline.
- **Contract review screen:** shows KPIs with formula intent, grain, filters, time logic, exclusions, currency and examples. It has the buttons Accept / Edit / Reject / Explain / Regenerate, and shows the G1 check results.

**Manual test**
1. In the UI, run the full **"Ambiguous Revenue"** acceptance scenario: submit "Show revenue by month for 2024", answer the question, review the contract and Accept.
2. **Expected:** the timeline shows `CREATED → NEEDS_CLARIFICATION → REQUIREMENT_APPROVED`, and the approval shows your name and time.
3. Try to approve while a question is open. **Expected:** the button is disabled, or the error lists the blocker.

**Done when (M2 exit):** a business user can produce an approved, locked BusinessContract in the UI.
