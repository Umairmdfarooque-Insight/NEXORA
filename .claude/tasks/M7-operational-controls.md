# M7 — Operational Controls

**Exit deliverable:** repeatable end-to-end workflow.

---

### T-701 — Impact analysis and stale marking

**Depends on:** T-604 · **Spec:** FR-020, §1.1 principle 8, Business rules 2 and 6, acceptance scenario "Upstream KPI change"

**Build**
- An artifact dependency graph: BusinessContract → MetadataInventory → ExecutionPlan/ModelSpec → TMDL → ReportPlan → PBIR. Each node stores the hash of the upstream version it was built from.
- **Return to requirement analysis:** when an approved upstream artifact changes, mark every dependent artifact `STALE` and list them. A stale artifact can't unlock later stages (rule 6).
- Revalidate or regenerate only the affected objects. For example, a changed KPI affects one measure and the visuals that use it.

**Manual test**
1. On a `REPORT_APPROVED` run, return it to requirement analysis and change Net Revenue to also exclude tax. Re-approve G1.
2. **Expected:**
   - the UI lists the affected artifacts: ModelSpec measure, TMDL measure file, and the visuals using Net Revenue
   - they are marked `STALE`
   - deployment is blocked
3. Run regeneration. **Expected:** only the affected measure and visuals change. The relationships and unrelated visuals are unchanged in the diff.

**Done when:** the **"Upstream KPI change"** scenario passes.

---

### T-702 — Promotion deployment, smoke tests and rollback

**Depends on:** T-701 · **Spec:** FR-019, §12 G6, §13 steps 4–7, §8.8, `RunManifest.json`

**Build**
- G6 checks:
  - target workspace authorized for the user
  - all previous gates passed
  - no stale artifacts
  - final release approval recorded
- Promotion deploys the **approved artifact hashes**. A different hash means a different artifact, so it is refused.
- Post-deployment smoke tests: model refresh or query, and the report loads.
- On success, the state is `COMPLETED`. On failure, restore the last approved state, set the state to `ROLLED_BACK`, and record why.

**Manual test**
1. Promote an approved run to a test "higher" workspace. **Expected:** the model and report appear there, the smoke tests pass, and the state is `COMPLETED`, with the deployment outcome in `RunManifest.json`.
2. Promote to a workspace you have no rights to. **Expected:** refused at G6, before any deployment.
3. Force a smoke-test failure, for example by pointing the model at a missing table in the target. **Expected:** state `ROLLED_BACK`, and the target either keeps the previous approved version or contains nothing partial.
4. Edit a TMDL file after approval and try to promote. **Expected:** refused because of a hash mismatch.

**Done when:** only approved, unchanged artifacts reach a higher environment, and failures roll back.

---

### T-703 — Audit trail and traceability view

**Depends on:** T-702 · **Spec:** FR-022, §14 (who approved), FR-021

**Build**
- **Audit view per run:**
  - the prompt
  - contract versions and their approvals
  - inventory and evidence
  - plan, model and report versions, with hashes
  - validation reports and retries
  - the deployment outcome
- **Trace from report:** select a visual, and see its measure, the measure's DAX, the approved KPI definition, the source columns with profile evidence, and the original prompt.

**Manual test**
1. Open a `COMPLETED` run's audit view. **Expected:** every stage appears with who approved it and when.
2. Pick a visual and trace it. **Expected:** you can reach the original prompt through the measure, the contract and the source evidence, without leaving Rayfin.

**Done when:** the final report can be traced back to its requirement and source evidence.

---

### T-704 — Observability

**Depends on:** T-702 · **Spec:** NFR-007, §7 (Observability layer)

**Build**
- A correlation ID equal to the run ID on every log line, trace and outbound call.
- Capture, for each run:
  - stage durations
  - error counts
  - retry counts
  - validation outcomes
  - LLM token usage and cost
- OpenTelemetry export to Application Insights, with a console exporter for local development.

**Manual test**
1. Complete a run locally with the console exporter. **Expected:** every log line includes the run ID, and there is a timing entry for each stage.
2. Query Application Insights for that run ID. **Expected:** all stages are present, plus the retry counts from any repair and the total LLM tokens and cost.

**Done when:** any run's cost, duration and failures can be found by run ID.

---

### T-705 — Security hardening

**Depends on:** T-704 · **Spec:** NFR-001, NFR-002, NFR-008, §14

**Build**
- Move secrets, including the Azure OpenAI key, from `.env` into **Key Vault**. Use managed identity for service-to-service calls where supported.
- Scope runs and artifacts to authorized users and workspaces. A user can read only runs in workspaces they can access.
- Apply tenant and workspace scoping to metadata caches.
- Data-minimization guard: log the size and shape of every LLM payload, and reject any payload that contains raw row data rather than profile summaries.

**Manual test**
1. Remove `AZURE_OPENAI_API_KEY` from `.env` and run a compile. **Expected:** it works, with the key retrieved from Key Vault.
2. As user B, call `GET /runs/{id}` for a run belonging to user A in a workspace user B can't access. **Expected:** `403`.
3. Review the LLM payload log for a full run. **Expected:** it contains only metadata and profile summaries, with no source rows.

**Done when:** secrets, data access and model payloads follow §14.

---

### T-706 — End-to-end vertical slice acceptance

**Depends on:** T-705 · **Spec:** [Definition of Done](../spec/acceptance-scenarios.md#definition-of-done-for-the-initial-vertical-slice), [acceptance scenarios](../spec/acceptance-scenarios.md), [review checklist](../spec/acceptance-scenarios.md#recommended-review-checklist)

**Build**
- Write no new features. Fix only the defects this run finds.

**Manual test**
1. Starting from a fresh Sales prompt in Rayfin, work through **every** item in the Definition of Done checklist and tick each one with evidence. Evidence can be a run ID, a screenshot or a file path.
2. Run all seven acceptance scenarios and record pass or fail with the run ID:

   | Scenario | Proven earlier in | Result |
   |---|---|---|
   | Simple Sales KPI | T-706 run | |
   | Ambiguous Revenue | T-205 | |
   | Invalid relationship | T-504 | |
   | Many-to-many bridge | T-506 | |
   | Unsupported bridge | T-403 | |
   | Report binding failure | T-603 | |
   | Upstream KPI change | T-701 | |

3. Walk through the review checklist with the business, BI and security reviewers.
4. Update the [status tracker](../technical-documentation/roadmap-risks-decisions.md#project-status-tracking).

**Done when (M7 exit):** every Definition-of-Done item and every acceptance scenario passes, so the workflow is repeatable end to end.
