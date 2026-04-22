---
title: "refactor: Consolidate CI/CD from 13 workflows to 4 groups"
type: refactor
status: completed
date: 2026-04-21
origin: docs/brainstorms/2026-04-21-unified-backend-rationalization-brainstorm.md
---

# refactor: Consolidate CI/CD from 13 Workflows to 4 Groups

## Overview

Consolidate 13 active GitHub Actions workflows (plus 22 archived in `legacy/`) into 4 logical groups: (1) lint/test on PR, (2) deploy on merge to master, (3) ML pipeline (scheduled), (4) data ingestion (scheduled). Preserve the 3 required branch protection job names. Add self-documenting comment headers to each workflow.

## Problem Frame

The CI/CD surface has grown to 13 active workflows with overlapping triggers, unclear boundaries, and no documentation explaining what each workflow does. Two testing workflows (`api-contract-tests.yml` and `test-edge-functions.yml`) both trigger on `supabase/functions/**` changes. Seven scheduled workflows run intraday jobs at various intervals with no coordination. The `legacy/` directory contains 22 decommissioned workflows that create confusion about which files are active. (see origin: `docs/brainstorms/2026-04-21-unified-backend-rationalization-brainstorm.md`, Phase 3)

## Requirements Trace

- R9. Consolidate into 4 logical groups: lint/test, deploy, ML pipeline, data ingestion. Must audit legacy/ for still-active trigger references.
- R10. Each workflow must be self-documenting: comment block describing triggers, purpose, and affected components.
- R11. Deploy workflow must validate no breaking schema change before deploying (contract test gate). Depends on Phase 2 schemas from PR #34.

## Scope Boundaries

- **In scope:** Workflow consolidation, self-documenting headers, legacy cleanup, branch protection verification
- **Out of scope:** New CI functionality, changing what gets tested/deployed, modifying Edge Function code, adding new scheduled jobs
- **Non-goal:** Reducing CI run time — focus is on clarity and reduced surface area

### Deferred to Separate Tasks

- R11 contract test gate: depends on PR #34 (API registry + schemas) being merged. Add a placeholder step that will be activated when schemas are available.
- Phase 4 function consolidation: separate plan

## Prerequisites (from PR review findings)

Before starting this plan, the following P1/P2 fixes from prior PRs must be resolved:

**From PR #34 (API Registry — blocking):**
- **P1: CI workflow targets `main/develop` but default branch is `master`** — `api-contract-tests.yml` will never trigger. Must fix `branches:` to include `master` before merging test workflows into ci-lightweight.yml (Unit 1 of this plan absorbs that workflow).
- **P2: Registry grep uses substring match** — `grep -q "name: $func_name"` can false-positive. Fix to `grep -q "^  - name: $func_name$"`.
- **P2: user-refresh and data-health inline schemas removed with no replacement** — Add `user-refresh.schema.json` and `data-health.schema.json` to `_shared/schemas/` before merging test workflows.
- **P3: No reverse registry check** — Add a step that iterates registry entries and verifies each has a function directory.

**From PR #32 (Auth Fixes — non-blocking but should fix):**
- **P1: ga-strategy 401/503 responses missing CORS headers** — Use `errorResponse()` instead of raw `Response` in the gateway-key block.

## Context & Research

### Relevant Code and Patterns

**Active workflows (13):**

| File | Trigger | Purpose | Group |
|------|---------|---------|-------|
| `ci-lightweight.yml` | push/PR | Lint, pytest, Deno checks | 1: Lint/Test |
| `api-contract-tests.yml` | push/PR on supabase/** | Schema validation | 1: Lint/Test |
| `test-edge-functions.yml` | push/PR on supabase/** | Deno function tests | 1: Lint/Test |
| `deploy-supabase.yml` | workflow_run after CI | Deploy Edge Functions + migrations | 2: Deploy |
| `ml-validation.yml` | weekly + manual | Full ML test suite | 3: ML Pipeline |
| `ml-orchestration.yml` | daily 6AM UTC | Forecasting + model health | 3: ML Pipeline |
| `daily-data-refresh.yml` | daily 10AM UTC | EOD data ingestion | 4: Data Ingestion |
| `intraday-ingestion.yml` | */5 market hours | m15/h1 bar ingestion | 4: Data Ingestion |
| `intraday-forecast.yml` | */15 market hours | Intraday forecasts | 4: Data Ingestion |
| `intraday-data-watchdog.yml` | */30 market hours | Gap detection + recovery | 4: Data Ingestion |
| `hourly-canary-15m.yml` | hourly market hours | m15 canary validation | 4: Data Ingestion |
| `hourly-sr-recalc.yml` | hourly market hours | Support/resistance recalc | 4: Data Ingestion |
| `nightly-cleanup.yml` | daily 7AM UTC | Old job/log cleanup | 4: Data Ingestion |

**Branch protection required job names** (from AGENTS.md):
- `CI Summary` — aggregate from ci-lightweight.yml
- `ML Unit Tests (Python 3.10)` — matrix job in ci-lightweight.yml
- `ML Unit Tests (Python 3.11)` — matrix job in ci-lightweight.yml

**Workflow chain:** `deploy-supabase.yml` uses `workflow_run` triggered by "CI - Lightweight (Code Quality)" succeeding on main/master. The workflow name string must match exactly.

**Legacy directory:** `.github/workflows/legacy/` contains 22 `.yml` files. None are active (no `on:` triggers reference them). Safe to archive or delete.

### Institutional Learnings

- **Status check names** (AGENTS.md): "Status check names must exactly match job `name:` fields in the YAML. Run CI once on a branch to confirm displayed names before adding to branch protection."

## Key Technical Decisions

- **Merge testing workflows into ci-lightweight.yml:** `api-contract-tests.yml` and `test-edge-functions.yml` both trigger on `supabase/functions/**` changes. Merge their steps into ci-lightweight.yml's existing conditional component detection. This reduces 3 → 1 PR-triggered workflow.
- **Keep scheduled workflows separate but grouped:** The 7 scheduled workflows have different cron intervals (5min, 15min, 30min, hourly, daily). Merging them into one file with multiple jobs is possible but makes failure isolation harder. Instead, add self-documenting headers and standardize naming to `schedule-*.yml` prefix.
- **Preserve all 3 branch protection job names exactly:** `CI Summary`, `ML Unit Tests (Python 3.10)`, `ML Unit Tests (Python 3.11)` must not be renamed. The workflow name "CI - Lightweight (Code Quality)" must not change (deploy-supabase.yml triggers on it).
- **Delete legacy/ directory:** All 22 files are decommissioned. Remove the directory entirely rather than leaving dead files.
- **R11 contract test gate as placeholder:** Add a commented-out step in the deploy workflow that will be activated when PR #34's schemas are merged. This prevents the deploy workflow from needing a second touch later.

## Open Questions

### Resolved During Planning

- **Are any legacy workflows still active?** No — none have `on:` triggers that reference them, and the `workflow_run` chain only references "CI - Lightweight (Code Quality)".
- **Which workflows have overlapping triggers?** `api-contract-tests.yml` and `test-edge-functions.yml` both trigger on `supabase/functions/**` for push/PR. `ci-lightweight.yml` also detects Edge Function changes.
- **Can scheduled workflows be merged?** Technically yes, but different cron intervals make a single-file approach unwieldy. Better to standardize naming and add headers.

### Deferred to Implementation

- Exact step ordering within the merged ci-lightweight.yml — depends on reading existing step dependencies
- Whether `hourly-canary-15m.yml` and `intraday-forecast.yml` can be deduplicated (both run at 15-minute-adjacent intervals) — needs deeper analysis of what each does

## Implementation Units

- [x] **Unit 1: Merge testing workflows into ci-lightweight.yml**

**Goal:** Merge `api-contract-tests.yml` and `test-edge-functions.yml` into `ci-lightweight.yml`, reducing 3 PR-triggered workflows to 1.

**Requirements:** R9

**Dependencies:** None

**Files:**
- Modify: `.github/workflows/ci-lightweight.yml`
- Delete: `.github/workflows/api-contract-tests.yml`
- Delete: `.github/workflows/test-edge-functions.yml`

**Approach:**
- Read all 3 workflows to understand their steps and conditional triggers.
- Add the testing steps from `api-contract-tests.yml` (registry validation, schema validation from PR #34) and `test-edge-functions.yml` (Deno test runner) as new jobs or steps in `ci-lightweight.yml`, conditioned on `supabase/functions/**` path changes.
- Preserve all existing job `name:` fields exactly — especially `CI Summary`, `ML Unit Tests (Python 3.10)`, `ML Unit Tests (Python 3.11)`.
- Preserve the workflow `name:` "CI - Lightweight (Code Quality)" exactly — `deploy-supabase.yml` triggers on it.

**Execution note:** Before deleting the old workflows, verify the merged workflow passes on a test branch. Branch protection checks are fragile — a missing job name silently stops enforcing.

**Patterns to follow:**
- Existing conditional component detection in ci-lightweight.yml (it already detects which components changed)

**Test scenarios:**
- Happy path: PR touching `supabase/functions/` triggers lint + Edge Function tests + contract validation in one workflow run
- Happy path: PR touching only `ml/` triggers ML tests but NOT Edge Function tests
- Happy path: PR touching only `frontend/` triggers lint but NOT ML or Edge Function tests
- Edge case: PR touching both `ml/` and `supabase/functions/` triggers all relevant jobs
- Error path: Malformed Edge Function file fails Deno lint — CI reports failure with clear job name
- Integration: `CI Summary` job name still appears in GitHub status checks after merge
- Integration: `deploy-supabase.yml` still triggers on workflow_run after the merge (workflow name unchanged)

**Verification:**
- `CI Summary`, `ML Unit Tests (Python 3.10)`, `ML Unit Tests (Python 3.11)` appear as status checks on a test PR
- `deploy-supabase.yml` trigger still fires on main push (verify `workflow_run` works with the merged workflow)
- Old workflow files deleted from `.github/workflows/`

---

- [x] **Unit 2: Add self-documenting headers to all workflows**

**Goal:** Add standardized comment headers to every active workflow explaining triggers, purpose, and affected components.

**Requirements:** R10

**Dependencies:** Unit 1 (work on the post-merge file set)

**Files:**
- Modify: `.github/workflows/ci-lightweight.yml` (updated from Unit 1)
- Modify: `.github/workflows/deploy-supabase.yml`
- Modify: `.github/workflows/ml-validation.yml`
- Modify: `.github/workflows/ml-orchestration.yml`
- Modify: `.github/workflows/daily-data-refresh.yml`
- Modify: `.github/workflows/intraday-ingestion.yml`
- Modify: `.github/workflows/intraday-forecast.yml`
- Modify: `.github/workflows/intraday-data-watchdog.yml`
- Modify: `.github/workflows/hourly-canary-15m.yml`
- Modify: `.github/workflows/hourly-sr-recalc.yml`
- Modify: `.github/workflows/nightly-cleanup.yml`

**Approach:**
- Add a standardized comment block at the top of each workflow:
  ```
  # =============================================================================
  # GROUP: [1: Lint/Test | 2: Deploy | 3: ML Pipeline | 4: Data Ingestion]
  # PURPOSE: [1-2 sentence description]
  # TRIGGERS: [push/PR/schedule/workflow_run + conditions]
  # COMPONENTS: [which directories/subsystems this affects]
  # SECRETS: [which secrets are used]
  # =============================================================================
  ```
- Use the mapping table from Context & Research to fill in the values.
- Some workflows (like `intraday-ingestion.yml`) already have partial headers — standardize them to match the format.

**Test expectation:** none — pure comment/documentation change with no behavioral impact.

**Verification:**
- Every `.yml` file in `.github/workflows/` (excluding `legacy/`) has the standardized header
- Headers accurately describe the workflow's group, purpose, triggers, components, and secrets

---

- [x] **Unit 3: Rename scheduled workflows with group prefix**

**Goal:** Rename scheduled workflow files to use a `schedule-` prefix for visual grouping in the directory listing.

**Requirements:** R9

**Dependencies:** Unit 2 (headers added first so the rename carries the documentation)

**Files:**
- Rename: `intraday-ingestion.yml` → `schedule-intraday-ingestion.yml`
- Rename: `intraday-forecast.yml` → `schedule-intraday-forecast.yml`
- Rename: `intraday-data-watchdog.yml` → `schedule-intraday-watchdog.yml`
- Rename: `hourly-canary-15m.yml` → `schedule-hourly-canary.yml`
- Rename: `hourly-sr-recalc.yml` → `schedule-hourly-sr-recalc.yml`
- Rename: `daily-data-refresh.yml` → `schedule-daily-data-refresh.yml`
- Rename: `nightly-cleanup.yml` → `schedule-nightly-cleanup.yml`
- Rename: `ml-orchestration.yml` → `schedule-ml-orchestration.yml`

**Approach:**
- Use `git mv` for each file to preserve history.
- Verify no `workflow_run` triggers reference any of these filenames (only `ci-lightweight.yml` is referenced by `deploy-supabase.yml`).
- Update any internal cross-references (comments, documentation).
- The `name:` field inside each YAML stays the same — only filenames change.

**Test expectation:** none — file rename with no behavioral change. GitHub Actions uses the filename for workflow identity in some contexts but not for `workflow_run` matching (which uses `name:`).

**Verification:**
- All scheduled workflows have `schedule-` prefix
- `ls .github/workflows/schedule-*` shows 8 files
- All scheduled cron jobs continue to fire on their original schedules

---

- [x] **Unit 4: Delete legacy/ directory**

**Goal:** Remove the 22 decommissioned workflow files in `.github/workflows/legacy/`.

**Requirements:** R9

**Dependencies:** Unit 1 (confirm no active workflow references legacy files)

**Files:**
- Delete: `.github/workflows/legacy/` (entire directory, 22 files)

**Approach:**
- Verify no active workflow imports from or references the legacy directory (grep for `legacy/` in all active `.yml` files).
- Remove the directory with `git rm -r`.
- These files are already in git history — they can be recovered if needed.

**Test expectation:** none — deletion of unused files.

**Verification:**
- `.github/workflows/legacy/` directory no longer exists
- All active workflows continue to function (no broken references)

---

- [x] **Unit 5: Add contract test gate placeholder to deploy workflow**

**Goal:** Add a placeholder step in `deploy-supabase.yml` for the schema contract test gate (R11), ready to activate when PR #34 schemas merge.

**Requirements:** R11

**Dependencies:** Unit 1 (testing merged into ci-lightweight), PR #34 (API registry + schemas — external dependency)

**Files:**
- Modify: `.github/workflows/deploy-supabase.yml`

**Approach:**
- Add a commented-out job step that would run `ajv validate` against the `_shared/schemas/` files before deploying. Include a clear `# TODO: Activate when PR #34 (API registry + schemas) is merged` comment.
- When PR #34 merges, this step can be uncommented to enforce schema validation as a deploy gate.
- The existing post-deploy smoke test (GET /chart) remains unchanged.

**Test expectation:** none — commented-out placeholder with no behavioral change.

**Verification:**
- `deploy-supabase.yml` contains the placeholder step with clear activation instructions
- Existing deploy pipeline (supabase link, deploy, smoke test) is unchanged

## System-Wide Impact

- **Interaction graph:** `deploy-supabase.yml` triggers via `workflow_run` on "CI - Lightweight (Code Quality)" — the workflow `name:` must not change. Branch protection requires 3 specific job names — these must be preserved.
- **Error propagation:** Merging test workflows into ci-lightweight means a Deno lint failure and a Python test failure both appear in the same workflow run. They should be separate jobs so failures are isolated and clearly labeled.
- **State lifecycle risks:** Renaming workflow files may cause GitHub to treat them as new workflows (losing run history). The `name:` field stays the same, so the workflow identity in the GitHub UI should persist.
- **Unchanged invariants:** All cron schedules remain identical. All test suites run the same checks. Deploy pipeline remains unchanged. Branch protection enforces the same 3 job names.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Renamed/merged workflow breaks branch protection | Verify job names on a test branch before merging. AGENTS.md rule: "Run CI once on a branch to confirm displayed names." |
| deploy-supabase.yml workflow_run stops firing | Preserve "CI - Lightweight (Code Quality)" as the exact workflow `name:` field. Test on a branch. |
| Scheduled workflow rename loses run history | GitHub tracks by `name:` not filename for history. Filenames affect only the file listing. |
| Legacy workflow deletion removes something still needed | Grep for references first. Git history preserves everything. |
| R11 contract gate activation forgotten after PR #34 merges | Clear TODO comment with PR number. Follow up after merge. |

## Sources & References

- **Origin document:** [docs/brainstorms/2026-04-21-unified-backend-rationalization-brainstorm.md](docs/brainstorms/2026-04-21-unified-backend-rationalization-brainstorm.md) — Phase 3 (R9-R11)
- Branch protection rules: AGENTS.md CI/CD section
- Active workflows: `.github/workflows/*.yml` (13 files)
- Legacy workflows: `.github/workflows/legacy/` (22 files)
- Deploy chain: `deploy-supabase.yml` → `workflow_run` on ci-lightweight
- API schemas (R11 dependency): PR #34 (`feat/api-registry-contracts`)
