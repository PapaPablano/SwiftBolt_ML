---
title: Fix Backtest Timeout Reliability
type: fix
status: completed
date: 2026-03-02
origin: docs/brainstorms/2026-03-02-backtest-timeout-fix-brainstorm.md
---

# Fix Backtest Timeout Reliability

## Overview

Custom strategy backtests time out at ~120 seconds and return no results. The root cause is a broken timeout chain: the frontend polls Supabase for 60s, gives up, falls back to a FastAPI path that can't handle custom strategies, waits another ~60s, then fails. Meanwhile the worker may have completed the backtest in the background.

This fix targets reliability by: (1) making the worker trigger awaitable with retry, (2) extending polling with progress feedback, (3) removing the broken fallback path, (4) adding cancel support, (5) cleaning up stale jobs, and (6) fixing the worker race condition where it claims the wrong job.

## Problem Statement / Motivation

Users building custom strategies via the condition builder cannot backtest over 1-3 year date ranges. They see a spinner for ~120s and get a generic error, even though the computation (250-750 daily bars with 9 indicators) should complete in seconds. The orchestration layer is the bottleneck, not the computation.

**Root causes (see brainstorm: docs/brainstorms/2026-03-02-backtest-timeout-fix-brainstorm.md):**
1. Fire-and-forget worker trigger silently drops errors (`fetch()` without `await`)
2. Frontend polling has a hard 60s limit with no user feedback
3. On timeout, frontend falls back to FastAPI which only handles preset strategies
4. Worker ignores `triggered_job_id` and claims oldest pending job (race condition, per todo #081)
5. No cancel, heartbeat, or stale job cleanup mechanisms

## Proposed Solution

Fix the existing queue/worker architecture rather than replacing it (see brainstorm: key decision #1). Six changes across 4 existing files + 1 new migration.

## Technical Considerations

**Edge Function timeout:** Supabase Edge Functions have a plan-dependent timeout (60s free, up to 400s Pro). Daily backtests (250-750 bars) should complete in <10s of compute. The bottleneck is orchestration overhead (cold starts, job claiming). If the Edge Function limit is <60s on this project, the worker may need to be moved to a different compute layer in a future iteration.

**Worker job loop:** Currently processes up to 3 jobs per invocation. After fixing to claim by `triggered_job_id`, reduce to 1 job per invocation to minimize Edge Function runtime and timeout risk.

**Anonymous user_id:** Pre-existing bug where `user_id = "anonymous"` (string) is inserted into a UUID column. Out of scope for this fix but noted as a related issue to address separately.

## System-Wide Impact

- **Interaction graph:** POST `backtest-strategy` → triggers `strategy-backtest-worker` → claims job → processes → updates DB → frontend polls GET `backtest-strategy` → reads result
- **Error propagation:** Worker errors update job `status='failed'` + `error_message`. Frontend poll reads this and surfaces it. New: trigger failures surface immediately via awaited fetch.
- **State lifecycle risks:** Stale jobs (worker dies mid-processing) now auto-cleaned after 5 minutes. Cancel sets terminal state to prevent zombie jobs.
- **API surface parity:** Only `backtest-strategy` Edge Function is the public API. `strategy-backtest` (legacy, auth-required) is not modified.

## Acceptance Criteria

### Phase 1: Fix Worker Trigger + Claim Logic (Backend)

- [x] **1a. Await worker trigger** in `supabase/functions/backtest-strategy/index.ts`
  - `await` the `fetch()` call to the worker (currently fire-and-forget at lines 200-212)
  - On trigger failure: return `{ job_id, status: 'pending', worker_triggered: false }` (job is already in DB)
  - Add 1 retry attempt if first trigger fails
  - Log trigger success/failure with response status

- [x] **1b. Fix worker to claim by `triggered_job_id`** in `supabase/functions/strategy-backtest-worker/index.ts`
  - Read `triggered_job_id` from request body (already sent but currently ignored, per todo #081)
  - If present: claim that specific job with `UPDATE ... SET status='running' WHERE id=$1 AND status='pending'`
  - If not present (legacy/manual trigger): fall back to `claim_pending_backtest_job()` RPC
  - Remove the `for (i < 3)` loop — process only the triggered job per invocation

- [x] **1c. Add heartbeat updates** in `supabase/functions/strategy-backtest-worker/index.ts`
  - Update `heartbeat_at` after: data fetch, indicator calculation, backtest loop completion
  - 3 heartbeat points per job execution

- [x] **1d. Add cancel checks** in `supabase/functions/strategy-backtest-worker/index.ts`
  - Before each major step (data fetch, indicator calc, backtest loop), re-read job status
  - If `status = 'cancelled'`, stop processing and return early (no error, no result)

### Phase 2: Cancel + Stale Cleanup (Backend)

- [x] **2a. Add PATCH handler** in `supabase/functions/backtest-strategy/index.ts`
  - Handle `PATCH /backtest-strategy` with `{ job_id, status: 'cancelled' }`
  - Auth: require valid user JWT, verify `user_id` matches job owner
  - State guard: only allow cancel from `status IN ('pending', 'running')`
  - Return 200 with updated job status, or 404/403/409 on error

- [x] **2b. Add stale job cleanup** on GET poll in `supabase/functions/backtest-strategy/index.ts`
  - Before returning poll result, update jobs where `status = 'running' AND COALESCE(heartbeat_at, started_at) < NOW() - INTERVAL '5 minutes'` → set `status = 'failed', error_message = 'Worker timed out'`
  - Scope cleanup to the polling user's jobs only (avoids cross-user side effects)
  - Rate-limit: only run cleanup once per GET request (it naturally is, since it's a single UPDATE)

### Phase 3: Frontend Polling + UX (Frontend)

- [x] **3a. Extend polling duration** in `frontend/src/lib/backtestService.ts`
  - Change from `40 × 1.5s = 60s` to `120 × 1.5s = 180s`
  - Add `'cancelled'` to terminal status check (currently only checks `'completed'` and `'failed'`)
  - Return a structured error object instead of `null` on timeout: `{ error: 'timeout', retryCount: N }`

- [x] **3b. Remove broken FastAPI fallback for custom strategies** in `frontend/src/lib/backtestService.ts`
  - Only fall back to FastAPI for preset strategies (id = '1', '2', '3')
  - For custom strategies (UUID id), surface timeout error directly
  - Keep FastAPI path for presets (it works correctly for those)

- [x] **3c. Add elapsed time counter** in `frontend/src/components/StrategyBacktestPanel.tsx`
  - Show "Running backtest... Xs" with incrementing counter during polling
  - Differentiate "Queued..." (job status = `pending`) vs "Computing..." (job status = `running`) if poll response includes status

- [x] **3d. Add cancel button** in `frontend/src/components/StrategyBacktestPanel.tsx`
  - Show "Cancel" button next to elapsed timer while `isRunning = true`
  - On click: PATCH `backtest-strategy` with `{ job_id, status: 'cancelled' }`
  - On cancel success: clear `isRunning`, show "Backtest cancelled" message

- [x] **3e. Timeout error with retry** in `frontend/src/components/StrategyBacktestPanel.tsx`
  - Track `retryCount` in component state (resets on new strategy or date range change)
  - First timeout: "Backtest timed out. This may be due to a cold start." + Retry button
  - Second timeout: "Try a shorter date range (e.g. 6 months)." + Retry button
  - Retry button calls `handleRunBacktest()` again (creates a new job)

### Phase 4: Database Migration

- [x] **4a. Add `heartbeat_at` column** via new migration `supabase/migrations/YYYYMMDDHHMMSS_add_backtest_heartbeat.sql`
  ```sql
  ALTER TABLE strategy_backtest_jobs ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMPTZ;

  -- Partial index for stale job detection
  CREATE INDEX IF NOT EXISTS idx_backtest_jobs_stale
    ON strategy_backtest_jobs(started_at)
    WHERE status = 'running';
  ```

## Job Status State Machine

```
pending ──→ running ──→ completed (terminal)
  │            │
  │            ├──→ failed (terminal: error or stale cleanup)
  │            │
  │            └──→ cancelled (terminal: user cancelled mid-run)
  │
  └──→ cancelled (terminal: user cancelled before worker claimed)
```

- Only `pending` and `running` can transition to `cancelled`
- `completed`, `failed`, `cancelled` are terminal — no further transitions
- Retry creates a NEW job (does not re-use failed/cancelled jobs)

## Files Modified

| File | Change | Lines Affected |
|------|--------|---------------|
| `supabase/functions/backtest-strategy/index.ts` | Await trigger, PATCH handler, stale cleanup | ~200-212 (trigger), new PATCH handler, GET handler |
| `supabase/functions/strategy-backtest-worker/index.ts` | Claim by ID, heartbeat, cancel checks, remove loop | ~38-53 (claim), ~632-639 (loop), new heartbeat/cancel logic |
| `frontend/src/lib/backtestService.ts` | Extend polling, handle cancelled, remove broken fallback | ~182-184 (loop), ~304-366 (fallback) |
| `frontend/src/components/StrategyBacktestPanel.tsx` | Cancel button, elapsed timer, retry UX | ~265-296 (run handler), ~599-615 (UI) |
| `supabase/migrations/YYYYMMDDHHMMSS_add_backtest_heartbeat.sql` | New: heartbeat_at column + index | New file |

## Success Metrics

- Custom strategy backtests complete reliably for 1-3 year daily date ranges
- Users see elapsed time feedback during backtest (no frozen spinner)
- Failed/timed-out backtests show actionable error with retry option
- Stale jobs auto-cleaned, no zombie jobs in `'running'` state indefinitely
- Cancel button stops processing within one heartbeat cycle

## Dependencies & Risks

- **Edge Function timeout:** If the project's Edge Function limit is <60s, daily backtests should still complete (computation is fast), but cold starts could push close to the limit. Monitor after deployment.
- **Migration safety:** `ALTER TABLE ADD COLUMN` with nullable column and `CREATE INDEX` are non-blocking in Postgres.
- **Backwards compatibility:** The PATCH handler is additive. The polling extension is backwards-compatible (just polls longer). The fallback removal changes behavior for custom strategy timeouts (from wrong results to clear error).

## Sources & References

- **Origin brainstorm:** [docs/brainstorms/2026-03-02-backtest-timeout-fix-brainstorm.md](docs/brainstorms/2026-03-02-backtest-timeout-fix-brainstorm.md) — Key decisions: fix trigger not architecture, 180s polling, remove broken fallback, add cancel + retry
- **Related todo (race condition):** `todos/081-resolved-p2-worker-ignores-triggered-job-id.md`
- **Related todo (key mismatch):** `todos/082-resolved-p2-initial-capital-key-mismatch-worker.md`
- **Edge Function timeout pattern:** `docs/plans/2026-03-01-feat-alpaca-data-pipeline-refresh-plan.md` — 58s timeout buffer pattern
- **Auth learnings:** `docs/BACKTEST_VISUALS_PAPER_TRADING_LEARNINGS.md` — JWT refresh gotcha, service role fallback anti-pattern
