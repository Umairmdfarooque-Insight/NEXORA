---
name: review-task
description: Review the code of a Nexora task branch (for use in a T-xxx_test session). Checks the changes against the task's Build list and Done-when, the spec rules, correctness, security and codebase conventions, then reports verified findings and a fix list to paste into the development session. Review only - does not modify code.
argument-hint: "[T-101]  (default: task from the current branch name)"
---

# Review a Nexora task

Argument: `$ARGUMENTS`

This review runs in a **separate session** from the one that wrote the code, so it isn't anchored on the developer's reasoning. Judge the code as it is. Don't assume the implementation is right because it exists.

**Review only.** Don't edit, create or delete project files, and don't commit, switch branches or stash. Fixes are made in the development session (`T-xxx`) using the fix list from step 6. If the user explicitly asks you to fix something here, remind them of the workflow first, and only then proceed.

## 1. Identify the task and the changes

- **Task ID:** from the argument, or else from the current branch (`git branch --show-current`, format `task/T-xxx-…`). If neither gives a task ID, ask which task to review.
- If the current branch is `main`, stop. Task work lives on task branches.
- Read:
  - `.claude/CLAUDE.md`
  - the task's full section in `.claude/tasks/M*-*.md`, including Depends on, Spec, Build, Manual test and Done when
  - the spec sections the task cites, in `.claude/spec/` and `.claude/technical-documentation/`
- Collect **all** changes on the branch, committed and uncommitted:
  ```
  git fetch origin
  git diff --stat $(git merge-base origin/main HEAD)
  git diff $(git merge-base origin/main HEAD)
  git status --short -uall            # untracked files are part of the change too
  ```
- Read each changed or new file **in full**, not just the hunks, plus the existing code it calls or replaces.

## 2. Check the task conformance

For every bullet in the task's **Build** list, decide its status and the evidence for it:

| Status | Meaning |
|---|---|
| ✅ Done | Implemented as specified, with `file:line` evidence |
| ⚠️ Partial | Some of it is missing or deviates. Say exactly what. |
| ❌ Missing | Not implemented |

Also check:
- **Scope creep:** code that belongs to a later task. Name the task, for example "this is T-302 work".
- **Done when:** is the condition actually reachable with this code?
- **Manual-test readiness:** could each manual-test step run as written? The commands, endpoints, file paths and CLI names must exist and match the implementation.

## 3. Review the code

| Area | What to look for |
|---|---|
| Spec rules | LLM output treated as a candidate, with deterministic code validating and controlling state. No silent assumptions for KPI definitions. A Data Gap returned instead of a fabricated calculation. No raw rows sent to the LLM (NFR-008). Generation and deployment only to the sandbox. The workflow state machine not bypassed. |
| Correctness | Logic errors, wrong edge-case handling (empty, None, duplicates), state transitions that skip `RunStore`, errors swallowed silently, results that are non-deterministic where NFR-009 requires repeatability |
| Security | Secrets in code, logs or committed files. `.env` values read or printed. SQL built by string concatenation with untrusted input, or identifiers not quoted. Missing auth or authorization checks on API endpoints (after T-105). |
| Conventions | Absolute imports (`from app.…`). Settings read through `app/config.py`. Existing modules and connectors reused instead of duplicated. Naming and comment density matching the surrounding code. New dependencies added to `requirements.txt`. New settings added to `.env.example` with empty values. |
| Hygiene | Leftover debug prints, dead code, hardcoded `saleslt` names or IDs where the task asked for them to be generalized, or files that shouldn't be committed (`runs/`, `.venv/`, `__pycache__/`) |

## 4. Verify before reporting

- **Prove each finding** by reading the exact code path. Where possible, also run an offline check that shows the problem.
- Drop anything you can't verify, or label it **Plausible** with the reason.
- Run the checks that don't need Azure, Fabric or a browser sign-in, and report their real output:
  - `python -m compileall -q app`
  - importing every changed module
  - `--help` for any new CLI command
  - any deterministic generator or validator the task added, run on sample input
- Never claim a live Azure or Fabric step passed unless you ran it and saw the result.

## 5. Severity

- **Blocker:** the task's Done-when can't be met, a spec rule is violated, there's a security problem, or a manual-test step can't work as written.
- **Major:** a bug in a realistic scenario, or a Build item that is Partial or Missing.
- **Minor:** a convention break, readability issue or small cleanup.

## 6. Report

Reply in this structure:

1. **Verdict:** ✅ **Ready for manual test**, or ❌ **Needs changes**. Any Blocker or Major finding means Needs changes. Add one line on why.
2. **Scope reviewed:** the branch, the base commit, and the number of files changed.
3. **Build checklist:** the table from step 2.
4. **Findings**, most severe first. Each has:
   - Severity, then `file:line`, then a one-line title
   - **What happens:** concrete input or state, and the wrong result or crash
   - **Suggested fix:** one or two sentences, without writing the patch
   - Verified, or Plausible
5. **Checks run:** each command with pass or fail and the key output.
6. **Fix list for the dev session:** one fenced block the user can paste straight into the `T-xxx` session:
   ```
   Review of T-xxx found these issues. Fix them on the current branch, then hand back the manual test:
   1. [Blocker] app/...py:42 — ...
   2. [Major] ...
   ```
   Leave this out if there are no findings.
7. **Next:**
   - If Ready, offer to walk the user through the task's manual-test steps one at a time, checking each result against its **Expected** value.
   - If Needs changes, tell the user to paste the fix list into the `T-xxx` session, and then run `/review-task` again, preferably in a fresh `_test` session.
