# M7 — Operational Controls

**Exit deliverable:** repeatable end-to-end workflow. Shared shapes are in [CONTRACTS.md](CONTRACTS.md).

---

### T-701 — Impact analysis and stale marking

**Depends on:** T-604 · **Spec:** FR-020, §1.1 principle 8, Business rules 2 and 6, acceptance scenario "Upstream KPI change"

#### Problem statement
When an approved upstream artifact changes, for example a KPI definition, the artifacts built from it are silently out of date. The spec requires marking dependents stale, blocking progression while they're stale, and regenerating **only** what was affected.

#### Functional requirements
1. A run can be **returned** to an earlier stage (requirement analysis, planning or model). That unlocks the artifact for that stage, with the reason recorded.
2. After the changed artifact is approved again, compute the impact. Compare its old and new versions at **object level** (for example KPI → measure → visuals), using the `based_on` hashes and the dependency map below.
3. Mark the affected artifacts, and the objects within them, as `stale`. A stale artifact can't unlock dependent stages (rule 6).
4. Regenerate or revalidate only the stale objects.

#### API contracts
Dependency map:

| Upstream | Downstream |
|---|---|
| BusinessContract | SourceResolution, Feasibility, ExecutionPlan |
| MetadataInventory | SourceResolution |
| ModelSpec | SemanticModel (TMDL) |
| SemanticModel | ReportPlan |
| ReportPlan | Report (PBIR) |

Object level: a KPI maps to its measure (by `kpi` name), and a measure maps to the visuals that reference it.

| Method and path | Request | Response |
|---|---|---|
| `POST /runs/{id}/return` | `{"to": "REQUIREMENT_ANALYSIS" \| "PLANNING" \| "MODEL", "reason": str}` | `200 RunDetail`. The state becomes `CREATED`, `DATA_PROFILED` or `PLAN_APPROVED` respectively. |
| `GET /runs/{id}/impact` | — | `200 {"changed": [{"artifact", "objects": [..]}], "stale": [{"artifact", "objects": [..], "reason"}]}` |
| `POST /runs/{id}/regenerate-stale` | — | `200 {"regenerated": [...], "validation": [...], "run": RunDetail}` |

#### Constraints
- Returning a run never deletes earlier versions. They stay available for audit (T-703).
- Approvals tied to an old hash are invalidated when the artifact changes.
- Regeneration reuses the generators (T-404, T-502, T-503, T-602) with the T-505 scope guard. The objects outside the impact set stay byte-identical.

#### Edge cases and error handling
| Case | Expected behavior |
|---|---|
| A change with no object-level effect, such as rewording the objective | `stale: []`, and nothing is regenerated. |
| A KPI deleted | Its measure and visuals are marked for removal, and shown for review. They aren't silently dropped. |
| A return requested during `DEPLOYING` | `409 WRONG_STATE`. |
| Deploy attempted with stale artifacts | G6 fails (T-702). |

#### Acceptance criteria
1. **Return and change.** On a `REPORT_APPROVED` run, call `POST /runs/{id}/return` with `{"to": "REQUIREMENT_ANALYSIS", "reason": "Exclude tax"}`. Change the Net Revenue definition to also exclude tax, and re-approve G1.
2. **Impact listed.** Call `GET /runs/{id}/impact`. **Expected:** the Net Revenue measure, its TMDL table file and the visuals that use it are listed as `stale`. Unrelated measures and visuals aren't.
3. **Blocked.** Try to deploy. **Expected:** refused because of stale artifacts.
4. **Targeted regeneration.** Call `POST /runs/{id}/regenerate-stale`. **Expected:** only the stale objects change, which a diff of the model and report version folders confirms. Validation re-runs, and the reviews are required again. This is the "Upstream KPI change" scenario.

---

### T-702 — Promotion deployment, smoke tests and rollback

**Depends on:** T-701 · **Spec:** FR-019, §12 G6, §13 steps 4–7, §8.8, `RunManifest.json`

#### Problem statement
Approved artifacts are in the sandbox. Moving them to a higher environment must be gated, use exactly what was approved (verified by hash), be smoke-tested, and roll back cleanly on failure.

#### Functional requirements
1. Gate G6 checks:

   | ID | Check |
   |---|---|
   | G6.1 | The target workspace is authorized for the user and isn't the sandbox |
   | G6.2 | Gates G1–G5 have passed on the current hashes |
   | G6.3 | No stale artifacts |
   | G6.4 | Final release approval recorded (role `release_approver`) |

2. Before deploying, back up the target's existing definitions, if any.
3. Deploy the semantic model, then the report, using the **approved artifact hashes**. Refuse if the files on disk don't match.
4. Smoke tests:
   - the model refreshes
   - `EVALUATE ROW` on each measure returns a value
   - the report definition can be retrieved
5. On success, the run moves to `COMPLETED`. On failure, restore the backup (or delete newly created items) and move to `ROLLED_BACK`.

#### API contracts
- `POST /runs/{id}/deploy`, with `{"target_workspace_id": str}`, returns `202 {"deployment_id"}`. Progress is shown through `GET /runs/{id}`.
- `RunManifest.deployment`:
  ```json
  { "deployment_id": "…", "target_workspace_id": "…", "started_at": "…", "finished_at": "…",
    "items": [ { "type": "SemanticModel", "item_id": "…", "hash": "sha256:…", "operation": "updated" } ],
    "backup_path": "deploy/backup-<ts>/",
    "smoke_tests": [ { "id": "SMOKE.REFRESH", "status": "pass" } ],
    "outcome": "completed" }
  ```
  `outcome` is `completed` | `rolled_back` | `rollback_failed`.
- The promotion service is the only caller allowed past the T-501 sandbox guard.

#### Constraints
- Only one deployment per target workspace at a time, enforced by a lock file.
- The backup is taken through `getDefinition` and stored in the run folder.

#### Edge cases and error handling
| Case | Expected behavior |
|---|---|
| The target is the sandbox | G6.1 fails. |
| The model deploys but the report fails | Both are rolled back. |
| The rollback itself fails | `outcome: rollback_failed`, and state `NEEDS_INPUT` with a critical message for manual intervention. |
| A file on disk differs from the approved hash | `409 HASH_MISMATCH` before anything is deployed. |
| Another deployment to the same target is running | `409`: "target busy". |

#### Acceptance criteria
1. **Promote.** Approve the release as `release_approver`, then deploy to a test "higher" workspace. **Expected:** the model and report appear there, every smoke test passes, the state is `COMPLETED`, and `RunManifest.deployment` records the items and hashes.
2. **Unauthorized target.** Deploy to a workspace you can't access. **Expected:** G6.1 fails, and nothing is deployed.
3. **Rollback.** Force a smoke-test failure, for example by revoking the target's access to the source Lakehouse. **Expected:** state `ROLLED_BACK`, and the target shows the previous version, or nothing if it was new.
4. **Hash enforced.** Edit a TMDL file in the approved version folder and deploy. **Expected:** `409 HASH_MISMATCH`.

---

### T-703 — Audit trail and traceability view

**Depends on:** T-702 · **Spec:** FR-022, §14 (who approved), FR-021

#### Problem statement
A final report must be traceable to the prompt, the approved definitions, the source evidence and the validation results behind it (FR-022). Today that information is spread across many files in the run folder.

#### Functional requirements
1. Build an audit timeline for each run from the history, approvals, artifact versions, gate results, validation reports and deployments.
2. Trace any visual back through: visual → measure → DAX → approved KPI definition → source columns with their profile evidence → original prompt.
3. Show both in Rayfin.
4. Append events to a tamper-evident log, where each event holds the hash of the one before it.

#### API contracts
- `runs/<id>/events.jsonl`, one event per line: `{"seq", "at", "type", "actor", "artifact"?, "version"?, "hash"?, "summary", "prev_event_hash"}`.
- `GET /runs/{id}/audit?offset=0&limit=200` returns `200 {"events": [...], "total", "chain_valid": bool}`.
- `GET /runs/{id}/trace?visual_id=v1` returns `200 {"visual", "measure": {"name", "dax", "model_version"}, "kpi": {"definition", "contract_version", "approved_by", "approved_at"}, "sources": [{"table", "column", "profile_evidence"}], "prompt"}`.
- UI routes: `/runs/[id]/audit` and `/runs/[id]/trace/[visualId]`.

#### Constraints
- `events.jsonl` is append-only. `chain_valid` is checked by recomputing the hashes.
- Earlier artifact versions are never deleted, because the trace depends on them.

#### Edge cases and error handling
| Case | Expected behavior |
|---|---|
| A referenced version file is missing | The trace shows an explicit gap ("version 2 missing"). It doesn't fail silently. |
| The event log was edited | `chain_valid: false`, and the first broken `seq` is shown. |
| A long-running run with many events | Paged results. |
| A visual ID that doesn't exist | `404`. |

#### Acceptance criteria
1. **Timeline.** Open `/runs/[id]/audit` for a `COMPLETED` run. **Expected:** every stage, with who approved it and when, and the artifact hashes.
2. **Trace.** Open the trace for `v1`. **Expected:** you reach the original prompt through the measure, its DAX, the approved KPI and the source columns with their evidence, without leaving Rayfin.
3. **Tamper detection.** Edit one line of a copy of `events.jsonl`, pointing the run at it in a test, and load the audit. **Expected:** `chain_valid: false`, with the broken `seq`.

---

### T-704 — Observability

**Depends on:** T-702 · **Spec:** NFR-007, §7 (Observability layer)

#### Problem statement
There's no way to tell how long each stage took, how many retries happened, or what model calls cost for a run. NFR-007 requires a correlation ID, stage durations, errors, retry counts, validation outcomes and model-call cost.

#### Functional requirements
1. Use `run_id` as the correlation ID on every log line, trace span and outbound HTTP call.
2. Record a span per stage, with its duration, outcome and attempt number.
3. Record metrics: stage duration, error count, retry count, validation pass or fail, LLM input and output tokens, and LLM cost.
4. Export to Application Insights, or to the console in local development.

#### API contracts
- Settings: `OTEL_EXPORTER` (`console` | `azuremonitor`) and `APPLICATIONINSIGHTS_CONNECTION_STRING`.
- Span names: `stage.<name>`, for example `stage.compile` or `stage.model.validate`. Attributes: `run_id`, `stage`, `attempt` and `outcome`.
- Metrics:

  | Metric | Unit |
  |---|---|
  | `nexora.stage.duration` | ms |
  | `nexora.errors` | count |
  | `nexora.retries` | count |
  | `nexora.validation.passed` | 0 or 1 |
  | `nexora.llm.tokens.input` | count |
  | `nexora.llm.tokens.output` | count |
  | `nexora.llm.cost` | USD |

- Pricing config `config/model_pricing.yaml`: `{ "<deployment>": { "input_per_1k": float, "output_per_1k": float } }`. You fill in the values.
- Logs are JSON lines: `{"ts", "level", "run_id", "stage", "msg", …}`.

#### Constraints
- Never log prompts, LLM responses, tokens or secrets in full. Log their length and a hash.
- Telemetry failure must not break a run.

#### Edge cases and error handling
| Case | Expected behavior |
|---|---|
| The exporter is unreachable | The run continues, and one warning is logged per process. |
| Pricing is missing for a deployment | `cost` is not recorded, and a warning names the deployment. |
| Work outside a run, such as `/health` | No `run_id` attribute, and nothing fails. |

#### Acceptance criteria
1. **Correlated logs.** With `OTEL_EXPORTER=console`, complete a compile and harvest. **Expected:** every log line and span includes the `run_id`, with a duration for each stage.
2. **App Insights.** With `azuremonitor`, query `traces | where customDimensions.run_id == "<id>"`. **Expected:** every stage is present, along with the retry count from any repair and the LLM token and cost metrics.
3. **No prompt leakage.** Search the logs for a phrase from the prompt. **Expected:** not found. Only the length and hash appear.

---

### T-705 — Security hardening

**Depends on:** T-704 · **Spec:** NFR-001, NFR-002, NFR-008, §14

#### Problem statement
Secrets are still in `.env`. Run access isn't scoped to authorized users, and nothing enforces that only metadata and profile summaries reach the LLM. §14 requires Key Vault, managed identity, scoping and data minimization.

#### Functional requirements
1. Load secrets from Azure Key Vault, including the Azure OpenAI key and the API client secret. Keep `.env` for non-secret settings only.
2. Use managed identity for service-to-service calls where supported, and `DefaultAzureCredential` for local development.
3. **Run authorization:** a user can read or act on a run only if they created it, or have access to its scope workspace. Workspace access is checked through Fabric and cached for 5 minutes.
4. Scope caches by tenant and workspace.
5. **LLM payload guard:** every outbound LLM payload is checked against an allowlist of shapes (prompt, contract, metadata names and types, profile summaries). Payloads with row-like data are rejected. The size and shape of every payload are logged.

#### API contracts
- Settings: `KEY_VAULT_URL`. Secret names: `azure-openai-api-key` and `entra-api-client-secret`.
- `app/security/llm_guard.py`: `check_payload(payload: dict) -> None`, which raises `PayloadRejected(reason)`.
- Authorization is applied as a FastAPI dependency on every `/runs/{id}/…` route. A failure returns `403 FORBIDDEN`.

#### Constraints
- No secret values in `.env.example`, logs or errors.
- Fail fast at startup if Key Vault is configured but unreachable.
- The guard runs in the shared LLM client, so no code path can skip it.

#### Edge cases and error handling
| Case | Expected behavior |
|---|---|
| Key Vault unreachable at startup | The process exits with a clear message naming `KEY_VAULT_URL`. The secret is never printed. |
| A secret is rotated | When the LLM returns `401`, the secret is re-read from Key Vault and the call retried once. |
| A user is removed from a workspace | They lose access to its runs within 5 minutes, when the cache expires. |
| A payload is rejected by the guard | The stage fails with `422 PAYLOAD_REJECTED`, the reason is logged, and nothing is sent. |

#### Acceptance criteria
1. **Secrets from Key Vault.** Remove `AZURE_OPENAI_API_KEY` from `.env`, set `KEY_VAULT_URL`, and compile a run. **Expected:** it works.
2. **Run isolation.** As user B, with no access to user A's workspace, call `GET /runs/<A's run>`. **Expected:** `403`.
3. **Guard blocks rows.** In a test, call the LLM client with a payload that contains a list of 10 row dictionaries. **Expected:** `PayloadRejected`, and no request is sent. Confirm in the logs.
4. **Payload log.** Review the payload log for a full run. **Expected:** only allowed shapes, with their sizes.

---

### T-706 — End-to-end vertical slice acceptance

**Depends on:** T-705 · **Spec:** [Definition of Done](../spec/acceptance-scenarios.md#definition-of-done-for-the-initial-vertical-slice), [acceptance scenarios](../spec/acceptance-scenarios.md), [review checklist](../spec/acceptance-scenarios.md#recommended-review-checklist)

#### Problem statement
Each task was tested on its own. The initial vertical slice is done only when one real Sales prompt goes from Rayfin all the way to a deployed, traceable report, and every acceptance scenario passes on the integrated system.

#### Functional requirements
1. Run one complete Sales run in Rayfin, from prompt to `COMPLETED`.
2. Re-run all seven acceptance scenarios on the integrated system.
3. Walk through the review checklist with the business, BI and security reviewers.
4. Fix only the defects found. **No new features** in this task.

#### API contracts
No new contracts. Record the evidence in `.claude/tasks/T-706-evidence.md`, listing the run IDs, screenshots or their paths, and file paths.

#### Constraints
- Use the sandbox, and a test "higher" workspace for promotion. Never use production.
- Each defect fix goes into its own commit, referencing the scenario it fixes.

#### Edge cases and error handling
| Case | Expected behavior |
|---|---|
| A scenario fails | Record it, fix it on this branch, and re-run **every** scenario, not just that one. |
| A fix needs a new feature | Stop. Add a new task to the plan instead. |

#### Acceptance criteria
1. **Definition of Done.** Every item in the [Definition of Done](../spec/acceptance-scenarios.md#definition-of-done-for-the-initial-vertical-slice) is ticked, with evidence.
2. **Scenarios.** Every row passes on the integrated system:

   | Scenario | First proven in | Result | Run ID |
   |---|---|---|---|
   | Simple Sales KPI | T-706 | | |
   | Ambiguous Revenue | T-205 | | |
   | Invalid relationship | T-504 | | |
   | Many-to-many bridge | T-506 | | |
   | Unsupported bridge | T-403 | | |
   | Report binding failure | T-603 | | |
   | Upstream KPI change | T-701 | | |

3. **Review checklist.** Every [review checklist](../spec/acceptance-scenarios.md#recommended-review-checklist) question is answered "yes" by the responsible reviewer.
4. **Status tracker.** The [status tracker](../technical-documentation/roadmap-risks-decisions.md#project-status-tracking) is updated, with every workstream `Done`.
5. **M7 exit.** **Expected:** the workflow is repeatable end to end.
