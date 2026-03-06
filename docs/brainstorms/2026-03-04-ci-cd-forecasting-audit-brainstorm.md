# Brainstorm: CI/CD and Forecasting Pipeline Audit & Overhaul

**Date:** 2026-03-04
**Status:** Ready for planning
**Approach:** Full CI/CD overhaul
**Driver:** Proactive hygiene — no specific incident

---

## What We're Building

A full audit and overhaul of the GitHub Actions CI/CD pipeline and ML forecasting workflow to achieve:

1. **Tests on every PR** — unit + integration tests gate all PRs (change-gated for speed)
2. **Required status checks** — branch protection prevents merging without passing CI
3. **Deploy gate** — `deploy-supabase.yml` only runs after CI passes
4. **Post-deploy smoke test** — automatically call `/chart` after every deployment
5. **Delete deprecated workflows** — remove `ci.yml`, `test-ml.yml` (legacy/confused state)
6. **GitHub email notifications** — built-in email on workflow failure for all operational jobs
7. **Full test matrix** — both Python 3.10 and 3.11 on every PR

---

## Current State

### Workflows (8 active, ~22 archived)

| Workflow | Purpose | Issues |
|----------|---------|--------|
| `ci-lightweight.yml` | Lint on PR (no tests) | Missing: tests, deploy gate |
| `ml-validation.yml` | Tests + security (weekly) | Not gated on PR |
| `deploy-supabase.yml` | Deploy to production | No CI gate, no smoke test |
| `ml-orchestration.yml` | Nightly ensemble forecast | OK |
| `intraday-forecast.yml` | 15m/1h forecasts | OK |
| `intraday-ingestion.yml` | Live OHLC fetch | OK |
| `daily-data-refresh.yml` | Historical backfill | OK |
| `intraday-data-watchdog.yml` | Staleness safety net | OK |
| `ci.yml` | **DEPRECATED** — delete | Confusion risk |
| `test-ml.yml` | **DEPRECATED** — delete | Confusion risk |

### Key Gaps
- PRs only run linting — ML code can merge untested
- `deploy-supabase.yml` has no gate requiring CI to pass first
- No post-deploy verification that functions are callable
- Deprecated workflows still in repo create confusion

---

## Why This Approach

**Full overhaul** (vs. targeted fixes) because:
- The gaps compound each other: untested code + ungated deploy = production risk
- Branch protection + required checks is a one-time setup that prevents whole classes of future problems
- The test infrastructure (`ml-validation.yml`) already exists — we're plugging it into the PR flow, not building from scratch
- Python 3.10/3.11 matrix is already in `ml-validation.yml` — reuse it on PRs

---

## Key Decisions

### 1. Test Strategy on PRs
**Decision:** Run unit tests on every PR, integration tests only when `ml/` or `requirements*.txt` changes.
**Rationale:** Unit tests are fast (~3-5 min). Integration tests hit external APIs — gate them on relevant changes. Full matrix (3.10 + 3.11) for unit; single version for integration.

### 2. Deploy Gate Mechanism
**Decision:** Add `needs: [ci]` to `deploy-supabase.yml` and require the new CI job to pass.
**Rationale:** Simplest way to block bad code from reaching production. If CI is skipped (no ML changes), deploy still proceeds.

### 3. Post-Deploy Smoke Test
**Decision:** After deploying Edge Functions, call `GET /chart?symbol=AAPL&timeframe=1D` and assert HTTP 200 + non-empty OHLCV array.
**Rationale:** Catches broken Edge Function deploys immediately. Simple, deterministic, no flakiness.

### 4. Branch Protection
**Decision:** Enable required status checks on `master` for: `ci-lightweight`, new `ci-tests` job.
**Rationale:** Enforces that PRs can't merge without passing tests. Done via GitHub repo settings (out of band from workflow files).

### 5. Email Notifications
**Decision:** Use GitHub's built-in workflow notification settings (not Slack) — email on failure for all 5 operational workflows (`ml-orchestration`, `intraday-forecast`, `intraday-ingestion`, `daily-data-refresh`, `deploy-supabase`).
**Rationale:** No Slack webhook setup needed. GitHub emails are automatic when you watch a repo's workflow runs.
**Implementation:** Add `on.workflow_dispatch` + ensure `workflow_run` triggers are set correctly. Per-job `if: failure()` notify steps may be needed for granularity.

### 6. Deprecated Workflow Deletion
**Decision:** Hard delete `ci.yml` and `test-ml.yml` (not archive).
**Rationale:** They're already archived in `.github/workflows/legacy/`. The active copies just add noise.

---

## Proposed CI Redesign

```
ci-lightweight.yml (existing — keep, add tests)
  ├── Detect changed components (ml/, supabase/functions/, migrations/)
  ├── If ml/ changed:
  │   ├── Black + isort + flake8 + mypy
  │   ├── Unit tests (Python 3.10 + 3.11)
  │   └── Integration tests (if requirements*.txt changed OR manual)
  ├── If supabase/functions/ changed:
  │   ├── deno lint + fmt
  │   └── Edge Function unit tests
  └── If migrations/ changed:
      └── Migration naming validation

deploy-supabase.yml (add gate + smoke test)
  ├── needs: [ci-lightweight]  ← NEW gate
  ├── Deploy Edge Functions
  ├── Apply migrations
  └── Smoke test: GET /chart?symbol=AAPL&timeframe=1D → assert 200  ← NEW
```

---

## Scope

### In Scope
- [ ] Modify `ci-lightweight.yml` to run unit + integration tests on PR
- [ ] Add `needs: [ci-lightweight]` gate to `deploy-supabase.yml`
- [ ] Add post-deploy smoke test job to `deploy-supabase.yml`
- [ ] Delete `ci.yml` and `test-ml.yml`
- [ ] Document branch protection setup (README or CLAUDE.md note)
- [ ] Email notification: confirm GitHub notification settings cover operational failures

### Out of Scope (defer)
- Slack webhook alerting
- Canary deployments for Edge Functions
- Circuit breaker / exponential backoff for staleness retries
- Total coverage threshold (currently diff-only at 90%)
- Load testing

---

## Resolved Questions

**Q: Should tests run on every PR or only on file changes?**
A: Change-gated: unit tests run if `ml/` changes; integration tests run if `requirements*.txt` changes or manual dispatch. This keeps PRs touching only Swift/frontend files fast.

**Q: Slack or email alerting?**
A: GitHub built-in email only for now. Add Slack later if needed.

**Q: Targeted fix vs. full overhaul?**
A: Full overhaul — required status checks prevent whole classes of future problems.

---

## Open Questions

None — all major decisions resolved.

---

## Files to Touch

| File | Change |
|------|--------|
| `.github/workflows/ci-lightweight.yml` | Add unit + integration test jobs (change-gated) |
| `.github/workflows/deploy-supabase.yml` | Add `needs: [ci]` gate + smoke test job |
| `.github/workflows/ci.yml` | **Delete** |
| `.github/workflows/test-ml.yml` | **Delete** |
| GitHub repo settings | Enable required status checks on `master` (manual step) |

---

## Risks

- **CI time increase:** Adding full test matrix (3.10 + 3.11) on every PR adds ~5-10 min. Acceptable given the safety gain.
- **Flaky integration tests blocking PRs:** Gate integration tests on `requirements*.txt` changes only to reduce this risk.
- **Branch protection lockout:** If CI is broken, no one can merge. Mitigate by testing CI changes on a branch first.
