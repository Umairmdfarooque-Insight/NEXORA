# Shared Contracts

These are data shapes and conventions used by more than one task. Tasks reference them as `CONTRACTS.md#<section>` instead of repeating them. If a task changes a shared shape, update this file in the same branch.

Conventions:
- Timestamps are ISO 8601 in UTC (`2026-10-14T09:30:00Z`).
- IDs are UUID v4 strings unless stated otherwise.
- JSON keys use `snake_case`.
- Every persisted artifact has `schema_version` (integer, starting at `1`).
- **Hash** means SHA-256 of the artifact's canonical form: JSON with sorted keys and no insignificant whitespace, or YAML dumped with sorted keys. It is written as `sha256:<hex>`.

---

## Run

Persisted as `runs/<run_id>/RunManifest.json` (the spec's `RunManifest.json`, §10).

```json
{
  "schema_version": 1,
  "run_id": "6f1c…",
  "prompt": "Show Net Revenue by month for 2024",
  "subject_area": "Sales",
  "desired_outputs": ["semantic model", "report"],
  "constraints": ["Use conformed tables only"],
  "state": "CREATED",
  "resume_state": null,
  "scope": { "workspace_id": "…", "lakehouse_id": "…", "schemas": ["saleslt"] },
  "created_by": { "oid": "…", "upn": "user@contoso.com", "name": "User Name" },
  "created_at": "…",
  "updated_at": "…",
  "history": [
    { "from": null, "to": "CREATED", "at": "…", "reason": "Run created", "actor": "user@contoso.com" }
  ],
  "artifacts": {
    "BusinessContract": { "path": "BusinessContract.yaml", "version": 2, "hash": "sha256:…", "status": "approved", "based_on": {}, "updated_at": "…" }
  },
  "deployment": null
}
```

- `scope` and `created_by` are `null` until T-103 and T-105 set them.
- `resume_state` is set only while the state is `NEEDS_INPUT`. It records the state to return to.
- Artifact `status` is one of `draft` | `approved` | `failed` | `stale` | `needs_input` | `data_gap`.
- `based_on` maps the name of each upstream artifact to the hash it was built from. T-701 uses it.

## Run states and transitions

These are the states from spec §11. Only these transitions are allowed. Anything else returns `ILLEGAL_TRANSITION`.

| From | Allowed to |
|---|---|
| `CREATED` | `NEEDS_CLARIFICATION`, `REQUIREMENT_APPROVED` |
| `NEEDS_CLARIFICATION` | `CREATED` (no blocking question left; draft ready for G1) |
| `REQUIREMENT_APPROVED` | `DATA_PROFILED`, `CREATED` (returned to requirement analysis) |
| `DATA_PROFILED` | `PLAN_APPROVED`, `REQUIREMENT_APPROVED` (re-harvest), `CREATED` |
| `PLAN_APPROVED` | `MODEL_GENERATING`, `DATA_PROFILED` (plan reopened), `CREATED` |
| `MODEL_GENERATING` | `MODEL_FAILED`, `MODEL_APPROVED` |
| `MODEL_FAILED` | `MODEL_GENERATING` (repair) |
| `MODEL_APPROVED` | `REPORT_GENERATING`, `CREATED`, `PLAN_APPROVED` |
| `REPORT_GENERATING` | `REPORT_FAILED`, `REPORT_APPROVED` |
| `REPORT_FAILED` | `REPORT_GENERATING` (repair), `MODEL_GENERATING` (model defect) |
| `REPORT_APPROVED` | `DEPLOYING`, `CREATED`, `PLAN_APPROVED`, `MODEL_GENERATING` |
| `DEPLOYING` | `COMPLETED`, `ROLLED_BACK`, `NEEDS_INPUT` |
| `ROLLED_BACK` | `DEPLOYING` |
| `COMPLETED` | — (terminal) |
| any state except `COMPLETED` | `NEEDS_INPUT` |
| `NEEDS_INPUT` | the stored `resume_state`, or `CREATED` |

`CREATED` doubles as "requirement draft without blocking questions". The spec has no separate state for it.

## Stage graphs

Orchestration is **hybrid**, with two layers:

| Layer | Built with | Owns |
|---|---|---|
| Run layer | The state machine and `RunStore` (T-101) | Run state, the transitions above, approvals, `history` and the audit trail. Waiting for a person (clarification, approval, `NEEDS_INPUT`) is always a run state. |
| Stage layer | A LangGraph `StateGraph` per stage | The LLM loop inside one stage call: propose, validate, retry or repair, then return a result |

A stage service (called from an API endpoint) checks the run state, invokes the stage graph, runs the gate on the result, and then makes the transition through `RunStore`.

Rules for every stage graph:
1. **No run-state writes.** A graph never calls `RunStore.transition` or `RunStore.save`, and never writes `RunManifest.json`. Nodes may write new versioned artifact files and append to `ValidationReport.json`. The stage service registers the artifact in the manifest after the graph returns.
2. **Deterministic routing.** Conditional edges route only on validator output (pass or fail, error codes, fingerprints, attempt counts), never on free LLM text.
3. **Bounded loops.** Every cycle has an `attempt` counter in the graph state, checked by a conditional edge against the task's limit. `run_graph` also passes a `recursion_limit`. A `GraphRecursionError` is a bug and returns `500 INTERNAL_ERROR`.
4. **Short-lived.** A graph finishes within the call that started it. No `interrupt()` and no persistent checkpointer. Graphs are compiled without a checkpointer. After a person responds, the next API call starts a new graph invocation from the run's artifacts.
5. **Shared LLM client.** LLM nodes call `app/llm/client.py`, so the T-705 payload guard and T-704 metrics apply. Don't use LangChain chat-model classes. The only new dependency is `langgraph`.
6. **No external tracing.** LangSmith tracing (`LANGSMITH_TRACING`, `LANGCHAIN_TRACING_V2`) stays off, because prompts and metadata must not leave the tenant (NFR-008). Tracing goes through T-704.
7. **Testable.** The LLM call is passed into `build_<name>_graph(llm=…)`, so a test can swap in a fake and check the node path without Azure.

Layout:
- `app/graphs/base.py`: `run_graph(graph, state: dict, *, run_id: str, stage: str, recursion_limit: int = 25) -> dict`. It invokes the graph with `config={"recursion_limit": …, "metadata": {"run_id": …, "stage": …}}`, records the node path, and converts `GraphRecursionError` to `INTERNAL_ERROR`. T-202 adds it.
- `app/graphs/<name>.py`: `build_<name>_graph(llm=…) -> CompiledStateGraph`, with the graph state as a `TypedDict`.

| Graph | Task | Nodes and loop | Bound |
|---|---|---|---|
| `compile` | T-202, reused by T-203 | `llm_compile → validate_schema → (retry llm_compile with errors) → apply_critical_terms → apply_locked_facts` | 2 LLM attempts |
| `dax_measure` | T-503 | `propose_dax → precheck_references → (retry propose_dax with errors)`, one invocation per measure | 2 attempts per measure |
| `repair` | T-505, reused by T-603 | `classify → deterministic_fix → llm_fix → scope_guard → validate → check_progress → (loop to classify, or stop)` | `max_attempts` from `config/repair_policy.yaml`. Also stops when there's no progress or only `user_input` errors remain |

Use plain functions, not a graph, for stages with no loop (for example T-301, T-302 and T-303).

## Error envelope

Every API error uses this body:

```json
{ "error": { "code": "ILLEGAL_TRANSITION", "message": "CREATED → DEPLOYING is not allowed", "details": { "from": "CREATED", "to": "DEPLOYING" } } }
```

| HTTP | Code | Used for |
|---|---|---|
| 400 | `BAD_REQUEST` | Malformed request that isn't a validation error |
| 401 | `UNAUTHENTICATED`, `TOKEN_EXPIRED` | Missing or invalid token |
| 403 | `FORBIDDEN`, `CONSENT_REQUIRED`, `TARGET_NOT_ALLOWED` | Authenticated but not allowed |
| 404 | `RUN_NOT_FOUND`, `NOT_FOUND`, `SCHEMA_NOT_FOUND` | Unknown resource |
| 409 | `ILLEGAL_TRANSITION`, `WRONG_STATE`, `GATE_FAILED`, `CONTRACT_LOCKED`, `STALE_VERSION`, `SCOPE_LOCKED`, `ALREADY_APPROVED`, `HASH_MISMATCH` | Conflicts with the current state |
| 422 | `VALIDATION_ERROR`, `PROMPT_REJECTED`, `PAYLOAD_REJECTED` | Invalid input, or an LLM payload blocked by the guard (T-705) |
| 429 | `RATE_LIMITED` | Upstream throttling the caller should retry |
| 502 | `UPSTREAM_ERROR`, `LLM_INVALID_OUTPUT` | Fabric, Power BI or the LLM returned an error or unusable output |
| 504 | `UPSTREAM_TIMEOUT` | An upstream call timed out |
| 500 | `INTERNAL_ERROR`, `CONFIG_ERROR` | A bug or missing configuration. The message must not include secrets. |

## Roles

Taken from spec §2.2. During development they are mapped in `config/roles.yaml`, which T-204 introduces:

```yaml
roles:
  business_owner:    [user@contoso.com]
  bi_engineer:       [user@contoso.com]
  security_reviewer: [user@contoso.com]
  project_reviewer:  [user@contoso.com]
  data_engineer:     [user@contoso.com]
  release_approver:  [user@contoso.com]
```

## Approval record

Appended to `runs/<run_id>/approvals.jsonl`, one JSON object per line. The file is append-only.

```json
{
  "approval_id": "…",
  "run_id": "…",
  "artifact": "BusinessContract",
  "artifact_version": 2,
  "artifact_hash": "sha256:…",
  "target": null,
  "action": "ACCEPT",
  "role": "business_owner",
  "user": { "oid": "…", "upn": "user@contoso.com" },
  "at": "…",
  "comment": "Looks right",
  "gate_result_ref": "gates/G1-…json"
}
```

- `action` is one of `ACCEPT` | `EDIT` | `REJECT` | `EXPLAIN` | `REGENERATE` (FR-018).
- `target` optionally narrows the action to one object, for example `{ "page": "Overview", "visual": "v3" }`.

## Gate result

Saved as `runs/<run_id>/gates/<gate>-<timestamp>.json`.

```json
{
  "gate": "G1",
  "artifact": "BusinessContract",
  "artifact_hash": "sha256:…",
  "passed": false,
  "checked_at": "…",
  "checks": [
    { "id": "G1.2", "description": "No blocking question open", "status": "fail", "evidence": { "open_blocking": ["Q1"] } }
  ]
}
```

Check `status` is `pass` | `fail` | `warning`. A gate passes only when no check has the status `fail`.

## Validation report

Saved as `runs/<run_id>/ValidationReport.json` (spec §10). Each new validation run appends to `runs`.

```json
{
  "schema_version": 1,
  "run_id": "…",
  "runs": [
    {
      "artifact": "SemanticModel",
      "artifact_version": 3,
      "artifact_hash": "sha256:…",
      "attempt": 1,
      "started_at": "…",
      "passed": false,
      "checks": [
        {
          "id": "G4.DAX",
          "object": "measure:Net Revenue",
          "status": "fail",
          "severity": "error",
          "code": "DAX_REFERENCE",
          "message": "Column 'LineTotalX' not found",
          "evidence": { "query": "EVALUATE ROW(\"v\", [Net Revenue])", "response": "…" },
          "fingerprint": "sha256:…",
          "classification": "llm"
        }
      ]
    }
  ]
}
```

- `severity` is `error` | `warning` | `info`.
- `classification` is `deterministic` | `llm` | `user_input`. T-505 sets it.

## Object references

Model objects are referenced like this in plans, specs and reports:
- `{ "table": "Sales", "column": "OrderDate" }`
- `{ "measure": "Net Revenue" }`
- `{ "hierarchy": "Date", "table": "Date" }`
