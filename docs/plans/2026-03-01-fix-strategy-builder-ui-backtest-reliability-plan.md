---
title: "Fix: Strategy Builder UI & Backtest Reliability"
type: fix
status: completed
date: 2026-03-01
origin: docs/brainstorms/2026-03-01-backtest-visuals-paper-trading-pipeline-brainstorm.md
---

# Fix: Strategy Builder UI & Backtest Reliability

## Overview

The Strategy Builder and Backtesting system has a critical backend bug causing all user-facing symptoms: the worker is never triggered due to a gateway auth mismatch, forcing every backtest through a FastAPI fallback that ignores custom strategy configuration. This makes results appear identical, and the Swift app shows generic/no visuals.

## Root Cause (Confirmed)

**`backtest-strategy/index.ts` line 182** triggers the worker with `Authorization: Bearer ${serviceKey}`, but **`strategy-backtest-worker/index.ts` line 622** checks for `X-SB-Gateway-Key` header. The worker returns 401, the job is never processed, the frontend polls for 30s, times out, and falls back to FastAPI which ignores custom conditions.

**Fix the auth header = fix "identical results" + fix Swift visuals** (since the worker produces real trade data that flows through the bridge).

## Previously Completed (from prior session)

The following were already fixed and verified in the current codebase:
- [x] Task 1.2: Config reset bugs in `handleSaveStrategy`, `handleCreateStrategy`, `cancelForm` — all fixed
- [x] Task 2.1: Pending trades buffer in `WebChartView.swift` — implemented
- [x] Task 2.2: `EmbeddedBacktesting` → Swift chart bridge — wired
- [x] Task 5.1: `ConditionPickerIntegrated` popup sizing — increased to 800x560

---

## Phase 1: Fix Worker Trigger (Root Cause)

### Task 1: Fix Gateway Auth Header in Worker Trigger
- [x] In `backtest-strategy/index.ts` line 181-183: Add `X-SB-Gateway-Key` header to the worker trigger fetch
- [x] Keep the existing `Authorization: Bearer ${serviceKey}` for Supabase routing
- [x] Verify the worker processes jobs end-to-end after the fix

**Files:** `supabase/functions/backtest-strategy/index.ts`

### Task 2: Increase Frontend Poll Timeout
- [x] In `backtestService.ts`: Increase poll iterations from 20 to 40 (30s → 60s) to give the worker more time
- [x] Add console logging when timeout occurs and fallback is triggered
- [x] Consider showing a "still processing" message to the user during long polls

**Files:** `frontend/src/lib/backtestService.ts`

---

## Phase 2: Prevent Default Strategy Duplication

### Task 3: Guard Default Strategy IDs Before Backtest
- [x] In `backtestService.ts` → `ensureStrategyId()`: Skip Supabase save for default strategies (id='1','2','3') — route them through the preset FastAPI path instead
- [x] In `StrategyBacktestPanel.tsx`: When editing a default strategy, show "Save as Copy" instead of "Save" to create a new UUID strategy
- [x] Ensure `updateStrategyInSupabase` guard (`isStrategyIdUuid()` check on line 53) prevents accidental overwrites

**Files:** `frontend/src/lib/backtestService.ts`, `frontend/src/components/StrategyBacktestPanel.tsx`

---

## Phase 3: Error Handling

### Task 4: Add Backtest Error State and User Feedback
- [x] In `StrategyBacktestPanel.tsx`: Add `backtestError: string | null` state
- [x] Display error banner (red alert with message and retry button) when backtest fails
- [x] In `backtestService.ts`: Surface the structured error from `queueBacktestJob`/`pollBacktestJob` instead of returning null

**Files:** `frontend/src/components/StrategyBacktestPanel.tsx`, `frontend/src/lib/backtestService.ts`

---

## Phase 4: Server-Side Validation

### Task 5: Add SL/TP Validation in Backtest Edge Function
- [x] Import existing `validateSLTPBounds` from `_shared/validators.ts` into `backtest-strategy/index.ts`
- [x] Validate risk management values before inserting the job — return 400 on invalid values
- [x] Fix the `.or()` PostgREST filter injection: sanitize userId with UUID regex before use in filter

**Files:** `supabase/functions/backtest-strategy/index.ts`, `supabase/functions/_shared/validators.ts`

---

## Phase 5: Auth Token Threading

### Task 6: Pass User Session Token to Backtest Requests
- [x] In `StrategyBacktestPanel.tsx` → `handleRunBacktest`: Pass `session?.access_token` to `runBacktestViaAPI`
- [x] In `backtestService.ts` → `runBacktestViaAPI` / `runBacktestViaSupabase`: Accept optional token param and include as `Authorization: Bearer ${token}` header
- [x] Keep anon key as fallback for unauthenticated users

**Files:** `frontend/src/components/StrategyBacktestPanel.tsx`, `frontend/src/lib/backtestService.ts`

---

## Acceptance Criteria

- [x] Backtest results change when strategy conditions or SL/TP parameters change
- [x] Trade markers appear on macOS chart after backtest completion
- [x] Error messages display when backtest fails (not silent failure)
- [x] Default strategies don't create duplicates in Supabase on every run
- [x] Frontend builds without errors (`npm run build`)

## Success Metrics

- Backtest results visibly change when SL is changed from 2% to 10%
- Trade markers visible on macOS chart within 5 seconds of backtest completion
- Zero silent failures — all errors produce user-visible feedback

## Sources & References

- **Origin brainstorm:** [docs/brainstorms/2026-03-01-backtest-visuals-paper-trading-pipeline-brainstorm.md](docs/brainstorms/2026-03-01-backtest-visuals-paper-trading-pipeline-brainstorm.md)
- **Technical review:** Architecture, Security, Performance, Simplicity, TypeScript reviews identified gateway auth as root cause
- **Key finding:** `backtest-strategy/index.ts:182` sends `Authorization` but worker checks `X-SB-Gateway-Key`
