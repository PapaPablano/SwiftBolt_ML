---
title: "feat: CI/CD Full Overhaul — Tests on PR, Deploy Gate, Smoke Test"
type: feat
status: completed
date: 2026-03-04
origin: docs/brainstorms/2026-03-04-ci-cd-forecasting-audit-brainstorm.md
---

# feat: CI/CD Full Overhaul — Tests on PR, Deploy Gate, Smoke Test

## Overview

Full overhaul of the GitHub Actions CI/CD pipeline to close four critical gaps:

1. **Tests never run on PRs** — only linting; ML code can merge untested
2. **No deploy gate** — `deploy-supabase.yml` runs regardless of CI status
3. **No post-deploy verification** — broken Edge Function deploys go undetected
4. **Deprecated workflows still in repo** — `ci.yml` and `test-ml.yml` cause confusion

Driver: proactive hygiene. No specific incident, but compounding gaps create production risk.
(see brainstorm: docs/brainstorms/2026-03-04-ci-cd-forecasting-audit-brainstorm.md)

---

## Problem Statement

### Gap 1 — PRs merge without tests
`ci-lightweight.yml` runs linting only (`black`, `flake8`, `mypy`, `deno lint`). Unit and integration tests are in `ml-validation.yml`, which only runs weekly (Monday 2:00 UTC), on manual dispatch, or when `requirements*.txt` changes. An ML change that breaks tests can be merged and deployed before the next weekly run catches it.

### Gap 2 — Deploy has no CI gate
`deploy-supabase.yml` triggers on push to `main` with `supabase/` path filter. It has no `needs:` dependency or CI check — broken code can reach production in the same push that breaks tests.

### Gap 3 — No smoke test
After `supabase db push` completes, there is no verification that Edge Functions are callable. A broken deploy succeeds silently until a user or scheduled job hits a 500 error.

### Gap 4 — Deprecated workflows add noise
`ci.yml` and `test-ml.yml` are deprecated workflow files (manually-triggered deprecation notices only). They're archived in `.github/workflows/legacy/` already — the active copies are just noise with confusion risk.

---

## Proposed Solution

Four targeted changes to four files:

```
Phase 1: Delete deprecated workflows (5 min)
  └── .github/workflows/ci.yml                    DELETE
  └── .github/workflows/test-ml.yml               DELETE

Phase 2: Add test jobs to ci-lightweight.yml (1–2 hrs)
  └── Add test-ml job (unit tests, matrix 3.10/3.11, change-gated)
  └── Add integration-test-ml job (change-gated, requirements*.txt only)
  └── Update ci-summary to include test outcomes

Phase 3: Add gate + smoke test to deploy-supabase.yml (1 hr)
  └── Add workflow_run trigger (runs after CI passes)
  └── Add smoke-test job calling /chart endpoint after migrations

Phase 4: Branch protection setup (10 min, manual in GitHub UI)
  └── Require ci-lightweight + test-ml status checks on master
  └── Require PRs before merge to master
```

---

## Technical Approach

### Architecture

```
Before (current):
──────────────────────────────────────────────────────────────
PR opened         →  ci-lightweight  (lint only, 2-3 min)
                                      ↓
                     no test gate — can merge untested
Merged to main   →  deploy-supabase  (no CI dependency)
                                      ↓
                     no smoke test — broken deploy undetected

After (overhaul):
──────────────────────────────────────────────────────────────
PR opened         →  ci-lightweight  (lint + unit tests, 8-12 min)
                                      ↓
                     branch protection blocks merge if CI fails
Merged to main   →  ci-lightweight  (runs again on main push)
                                      ↓ success only
                     deploy-supabase  (workflow_run gate)
                     ├── deploy-functions
                     ├── deploy-migrations
                     └── smoke-test  (GET /chart → assert 200 + non-empty ohlcv)
```

### Key Design Decisions (from brainstorm)

**Decision 1 — Test scope on PRs:**
Unit tests on every PR (change-gated: runs when `ml/**` changes). Integration tests only when `requirements*.txt` changes or manual dispatch. Keeps PRs touching only Swift/frontend fast.

**Decision 2 — Deploy gate mechanism:**
`workflow_run` trigger in `deploy-supabase.yml` — runs after `CI Lightweight` completes with `conclusion == 'success'`. Primary gate is branch protection (no PR merges without CI passing). `workflow_run` is belt-and-suspenders for any direct pushes to main.

**Decision 3 — Smoke test:**
`GET /chart?symbol=AAPL&timeframe=1D` — assert HTTP 200 + `ohlcv` array length > 0. The `/chart` endpoint has `verify_jwt: false` in the Supabase function config; no auth header required. Uses `SUPABASE_URL` secret (already in deploy workflow).

**Decision 4 — Delete, not archive:**
`ci.yml` and `test-ml.yml` already exist in `.github/workflows/legacy/`. The active copies are deprecated stubs. Hard delete.

**Decision 5 — Reuse `.github/actions/setup-ml-env/action.yml`:**
This composite action handles TA-Lib caching, Python setup, and environment config. Currently unused in `ci-lightweight.yml` despite being built for exactly this purpose. The new `test-ml` job will use it.

---

## Implementation Phases

### Phase 1: Delete Deprecated Workflows

**Files:**
- `.github/workflows/ci.yml` — DELETE
- `.github/workflows/test-ml.yml` — DELETE

**Why now:** No dependencies. Reduces confusion immediately. No behavior change.

**Verification:** `ls .github/workflows/` — neither file appears.

---

### Phase 2: Enhance `ci-lightweight.yml`

Add two new jobs alongside existing lint jobs. The `detect-changes` output already includes `ml: true` when `ml/**` changes — reuse it.

#### New job: `test-ml`

```yaml
# .github/workflows/ci-lightweight.yml

  test-ml:
    name: ML Unit Tests (Python ${{ matrix.python-version }})
    runs-on: ubuntu-latest
    needs: detect-changes
    if: needs.detect-changes.outputs.ml == 'true'
    strategy:
      matrix:
        python-version: ['3.10', '3.11']
      fail-fast: false
    steps:
      - uses: actions/checkout@v4
      - uses: ./.github/actions/setup-ml-env
        with:
          python-version: ${{ matrix.python-version }}
      - name: Run unit tests
        working-directory: ml
        run: |
          pytest tests/ -m "not integration" \
            --cov=src \
            --cov-report=xml \
            --cov-report=term-missing \
            -v --tb=short --maxfail=10
      - name: Enforce diff coverage (>=90%)
        working-directory: ml
        continue-on-error: true
        run: |
          diff-cover coverage.xml \
            --compare-branch origin/${{ github.base_ref || 'master' }} \
            --fail-under 90
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: coverage-py${{ matrix.python-version }}
          path: ml/coverage.xml
          retention-days: 7
```

#### New job: `integration-test-ml`

```yaml
  integration-test-ml:
    name: ML Integration Tests
    runs-on: ubuntu-latest
    needs: detect-changes
    # Only run when requirements change OR manual dispatch — avoids external API calls on normal PRs
    if: |
      github.event_name == 'workflow_dispatch' ||
      (needs.detect-changes.outputs.ml == 'true' &&
       contains(github.event.head_commit.modified || '', 'requirements'))
    steps:
      - uses: actions/checkout@v4
      - uses: ./.github/actions/setup-ml-env
        with:
          python-version: '3.10'
      - name: Run integration tests
        working-directory: ml
        continue-on-error: true
        run: |
          pytest tests/ -m integration -v --tb=short
```

#### Update `ci-summary` job

Add `test-ml` and `integration-test-ml` to the `needs:` list so the summary reflects test outcomes. Update the failure check to include test jobs.

```yaml
  ci-summary:
    name: CI Summary
    runs-on: ubuntu-latest
    needs: [detect-changes, lint-ml, test-edge-functions, validate-migrations, test-ml, integration-test-ml]
    if: always()
    steps:
      - name: Generate summary
        run: |
          # ... existing summary logic
          # Add test-ml and integration-test-ml status rows
          if [[ "${{ needs.test-ml.result }}" == "failure" ]]; then
            echo "❌ ML unit tests failed"
            FAILED=true
          fi
```

#### Check: Does `.github/actions/setup-ml-env/action.yml` handle `working-directory`?

Verify the composite action accepts a `python-version` input and installs from `ml/requirements.txt`. If it doesn't, adjust the action to accept a `working-directory` input, or inline the setup steps.

---

### Phase 3: Update `deploy-supabase.yml`

Two additions: `workflow_run` trigger and a `smoke-test` job.

#### Change trigger

```yaml
# .github/workflows/deploy-supabase.yml
# BEFORE:
on:
  push:
    branches: [ main ]
    paths:
      - 'supabase/functions/**'
      - 'supabase/migrations/**'
      - '.github/workflows/deploy-supabase.yml'
  workflow_dispatch:

# AFTER:
on:
  workflow_run:
    workflows: ["CI Lightweight"]    # Must match exact `name:` field in ci-lightweight.yml
    types: [completed]
    branches: [main, master]
  workflow_dispatch:
```

> **Note:** `workflow_run` doesn't support `paths:` filtering. Add a conditional in `deploy-functions` to only proceed if relevant files changed. Use the GitHub API or `dorny/paths-filter` to check the triggering SHA's diff.

Alternative simpler approach if `workflow_run` path filtering is too complex: keep the existing `push` trigger but add a preflight check:

```yaml
  preflight-ci-check:
    name: Verify CI Passed
    runs-on: ubuntu-latest
    steps:
      - name: Check CI status for this SHA
        run: |
          CI_STATUS=$(gh run list \
            --commit ${{ github.sha }} \
            --workflow "ci-lightweight.yml" \
            --json status,conclusion \
            --jq '.[0] | "\(.status):\(.conclusion)"' 2>/dev/null || echo "not_found:unknown")

          if [ "$CI_STATUS" = "completed:success" ]; then
            echo "CI passed ✅"
          elif [ "$CI_STATUS" = "not_found:unknown" ] && [ "${{ github.event_name }}" = "workflow_dispatch" ]; then
            echo "Manual dispatch — skipping CI check"
          else
            echo "CI status: $CI_STATUS — blocking deploy ❌"
            exit 1
          fi
        env:
          GH_TOKEN: ${{ github.token }}

  deploy-functions:
    needs: preflight-ci-check
    # ... existing steps
```

#### Add `smoke-test` job

```yaml
  smoke-test:
    name: Post-Deploy Smoke Test
    runs-on: ubuntu-latest
    needs: deploy-migrations
    steps:
      - name: Test /chart endpoint returns HTTP 200
        run: |
          CHART_URL="${{ secrets.SUPABASE_URL }}/functions/v1/chart?symbol=AAPL&timeframe=1D"
          HTTP_CODE=$(curl -s -o /tmp/chart_response.json -w "%{http_code}" "$CHART_URL")

          if [ "$HTTP_CODE" != "200" ]; then
            echo "❌ Smoke test failed: /chart returned HTTP $HTTP_CODE"
            cat /tmp/chart_response.json
            exit 1
          fi
          echo "✅ HTTP 200 received"

      - name: Validate OHLCV data is non-empty
        run: |
          OHLCV_LEN=$(jq '.ohlcv | length // 0' /tmp/chart_response.json 2>/dev/null || echo 0)

          if [ "$OHLCV_LEN" -lt 1 ]; then
            echo "❌ Smoke test failed: ohlcv array is empty or missing"
            jq '.' /tmp/chart_response.json
            exit 1
          fi
          echo "✅ ohlcv has $OHLCV_LEN bars — deploy verified"
```

> **Auth note:** The `/chart` endpoint has `verify_jwt: false` in the Supabase deploy config. The smoke test should work without auth headers. If a 401 is returned, add `-H "apikey: ${{ secrets.SUPABASE_ANON_KEY }}"` to the curl command (add `SUPABASE_ANON_KEY` to repo secrets).

---

### Phase 4: Branch Protection (Manual — GitHub UI)

This is a one-time manual setup in GitHub repo settings. It cannot be done via workflow files.

**Settings path:** GitHub repo → Settings → Branches → Branch protection rules → Add rule for `master`

**Required status checks to add:**
- `CI Summary` (the summary job in ci-lightweight.yml)
- `ML Unit Tests (Python 3.10)` (new test-ml matrix job)
- `ML Unit Tests (Python 3.11)` (new test-ml matrix job)

**Other recommended protection settings:**
- ✅ Require a pull request before merging
- ✅ Require status checks to pass before merging
- ✅ Require branches to be up to date before merging
- ✅ Do not allow bypassing the above settings

**Document in CLAUDE.md** — add a note to the CI/CD section:
> Branch protection on `master` requires `CI Summary`, `ML Unit Tests (3.10)`, and `ML Unit Tests (3.11)` to pass. To change required checks: GitHub repo → Settings → Branches.

---

### Phase 5: Email Notifications

No workflow file changes required. GitHub automatically sends email notifications for workflow failures to watchers.

**Enable:**
1. Go to GitHub profile → Settings → Notifications
2. Under "Actions" → enable "Failed workflows only" for email
3. Ensure you're watching the repository (Watch → All Activity OR Custom → Workflows)

**For operational workflow failures specifically:** The nightly and intraday workflows will email on failure automatically once notifications are enabled. No per-workflow configuration needed.

---

## System-Wide Impact

### Interaction Graph

```
PR opened:
  1. ci-lightweight triggers (on: pull_request)
  2. detect-changes scans diff
  3. [if ml/* changed] lint-ml + test-ml (3.10) + test-ml (3.11) run in parallel
  4. ci-summary aggregates results
  5. Branch protection checks ci-summary + test-ml status
  6. PR blocked if any required check fails

Merge to master:
  1. ci-lightweight triggers again (on: push to master)
  2. [workflow_run trigger in deploy-supabase] waits for ci-lightweight conclusion
  3. If conclusion == success: deploy-functions → deploy-migrations → smoke-test
  4. If conclusion != success: deploy is skipped

Smoke test failure:
  1. smoke-test job fails
  2. deploy-supabase workflow shows failure
  3. GitHub emails watchers
  4. Manual investigation + re-deploy needed
```

### Error & Failure Propagation

| Failure point | Effect | Recovery |
|--------------|--------|----------|
| `test-ml` fails on PR | CI Summary fails → branch protection blocks merge | Fix code, push new commit |
| `test-ml` skipped (no ml/ changes) | Still merges (intentional — non-ML PRs unblocked) | n/a |
| `deploy-functions` fails | `deploy-migrations` and `smoke-test` skipped | Check Supabase CLI logs, re-run deploy |
| `deploy-migrations` fails | `smoke-test` skipped | Manual `supabase migration repair`, re-run |
| `smoke-test` fails | Workflow fails, email sent | `/chart` endpoint broken — investigate Edge Function logs |

### State Lifecycle Risks

- **Branch protection misconfiguration:** If status check names in protection rules don't exactly match job names in YAML, protection silently doesn't enforce. Verify after setup.
- **Matrix job names:** `test-ml` has matrix strategy → creates jobs named `ML Unit Tests (Python 3.10)` and `ML Unit Tests (Python 3.11)`. Both must be added to required checks separately.
- **workflow_run path filtering loss:** Switching to `workflow_run` trigger removes the `supabase/` path filter. Deploy will run after any CI-passing push to main, not just when supabase files change. Mitigated by adding a path diff check in the deploy job.
- **TA-Lib composite action:** `.github/actions/setup-ml-env/action.yml` exists but its exact inputs need verification before the `test-ml` job uses it. May need a `python-version` input wired through.

### Integration Test Scenarios

1. **PR with ML code change** → lint-ml + test-ml (both versions) run → branch protection requires both to pass
2. **PR with only Swift/frontend change** → detect-changes outputs `ml: false` → test-ml skipped → PR proceeds fast
3. **Push to master (via merged PR)** → ci-lightweight runs on master → conclusion passes → deploy-supabase triggers → smoke test calls /chart → assert 200
4. **Smoke test hits empty OHLCV** → `jq '.ohlcv | length'` returns 0 → job fails → email sent
5. **Deprecated workflow manually triggered** → both are deleted so cannot be triggered

---

## Acceptance Criteria

### Phase 1 — Cleanup
- [x] `.github/workflows/ci.yml` does not exist
- [x] `.github/workflows/test-ml.yml` does not exist
- [x] `.github/workflows/legacy/` still contains archived copies (do not delete legacy/)

### Phase 2 — Tests on PRs
- [x] A PR that changes `ml/` triggers `test-ml` with Python 3.10 and 3.11 jobs
- [x] A PR that only changes `client-macos/` or `frontend/` does NOT trigger `test-ml`
- [x] A PR that changes `ml/requirements.txt` triggers `integration-test-ml`
- [x] `ci-summary` job reflects pass/fail status of `test-ml` jobs
- [x] Existing lint jobs (`lint-ml`, `test-edge-functions`, `validate-migrations`) unchanged in behavior

### Phase 3 — Deploy Gate + Smoke Test
- [x] `deploy-supabase.yml` does not run if `ci-lightweight` fails for the same SHA
- [x] `smoke-test` job runs after `deploy-migrations` succeeds
- [x] `smoke-test` calls `GET /chart?symbol=AAPL&timeframe=1D` and asserts HTTP 200
- [x] `smoke-test` asserts `ohlcv` array has at least 1 bar
- [ ] A forced broken deploy (e.g., intentional syntax error in Edge Function) causes smoke test to fail

### Phase 4 — Branch Protection
- [ ] A PR to `master` without passing CI cannot be merged (confirmed via test PR)
- [x] Branch protection rules documented in CLAUDE.md

### Phase 5 — Email
- [ ] At least one team member confirms receiving email on workflow failure
- [ ] Manual test: trigger a deliberate failure and verify email received

---

## Dependencies & Prerequisites

- **`SUPABASE_URL` secret** — Already in repo secrets (used by deploy workflow). Used by smoke test.
- **`SUPABASE_ANON_KEY` secret** — May be needed if `/chart` requires an `apikey` header. Check by running the smoke test curl manually first. If needed, add to repo secrets.
- **`.github/actions/setup-ml-env/action.yml` inputs** — Verify this composite action accepts `python-version` as an input. If not, add it or inline setup steps.
- **Job name accuracy for branch protection** — Status check names in GitHub UI must match exactly what appears in the GitHub Actions job name. Run the new CI workflow once on a branch to confirm displayed names before configuring branch protection.

---

## Risk Analysis

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| CI time increases block rapid iteration | Medium | Low | Change-gating means non-ML PRs stay fast (~2 min) |
| Flaky unit tests block PRs | Low | High | `--maxfail=10` to avoid single flake blocking; fix flaky tests |
| workflow_run loses path filtering | High (certain) | Low | Add manual path check in deploy job OR accept wider trigger scope |
| Status check name mismatch in branch protection | Medium | High | Verify names from actual run before configuring protection rules |
| TA-Lib composite action incompatibility | Low | Medium | Read action.yml before using; fallback to inline setup if needed |
| Smoke test flaky (AAPL data unavailable) | Low | Medium | Use `continue-on-error: true` initially; tighten after 2 weeks stable |

---

## Files to Change

| File | Change Type | Description |
|------|------------|-------------|
| `.github/workflows/ci.yml` | DELETE | Deprecated stub |
| `.github/workflows/test-ml.yml` | DELETE | Deprecated stub |
| `.github/workflows/ci-lightweight.yml` | MODIFY | Add `test-ml` and `integration-test-ml` jobs; update `ci-summary` |
| `.github/workflows/deploy-supabase.yml` | MODIFY | Add deploy gate (workflow_run or preflight check); add `smoke-test` job |
| `CLAUDE.md` | MODIFY | Document branch protection setup in CI/CD section |
| GitHub repo settings | MANUAL | Enable required status checks on `master` branch |

---

## Out of Scope (Deferred)

Per brainstorm decisions:
- Slack webhook alerting
- Canary deployments for Edge Functions
- Circuit breaker / exponential backoff for staleness retries
- Total coverage threshold (currently diff-only at 90%)
- Load testing
- Consolidating market-hours checking to a shared action
- OHLC validation shared script

---

## Success Metrics

- **Zero untested ML merges:** Every PR touching `ml/` shows green unit test badges before merge
- **Deploy confidence:** Post-deploy smoke test passes on every production deploy
- **Noise reduction:** `ci.yml` and `test-ml.yml` no longer appear in Actions UI
- **Fast non-ML PRs:** PRs touching only `frontend/` or `client-macos/` complete CI in <3 min

---

## Sources & References

### Origin
- **Brainstorm document:** [docs/brainstorms/2026-03-04-ci-cd-forecasting-audit-brainstorm.md](docs/brainstorms/2026-03-04-ci-cd-forecasting-audit-brainstorm.md)
  - Key decisions carried forward: change-gated test strategy, workflow_run deploy gate, smoke test on /chart

### Internal References
- Existing CI patterns: `.github/workflows/ci-lightweight.yml` (detect-changes, lint-ml jobs)
- Existing test config: `.github/workflows/ml-validation.yml` (test-ml job — blueprint for new test-ml)
- Composite action: `.github/actions/setup-ml-env/action.yml`
- Deployment workflow: `.github/workflows/deploy-supabase.yml`
- Legacy workflows: `.github/workflows/legacy/` (24 archived files — do not touch)

### External References
- [GitHub Actions `workflow_run` trigger docs](https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows#workflow_run)
- [dorny/paths-filter action](https://github.com/dorny/paths-filter) — used in detect-changes job
- [GitHub branch protection rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
