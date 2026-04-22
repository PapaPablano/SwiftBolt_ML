---
title: "feat: Hybrid ML pipeline — weekly training + live Kalman adjustment"
type: feat
status: active
date: 2026-04-22
origin: docs/brainstorms/2026-04-22-lightweight-ml-pipeline-brainstorm.md
---

# feat: Hybrid ML Pipeline — Weekly Training + Live Kalman Adjustment

## Overview

Replace the every-15-minute full-ensemble intraday forecast job with a hybrid architecture: full ensemble training runs weekly (or on-demand), and a lightweight Kalman filter adjustment layer runs inside `ingest-live` every minute to keep forecast points current as prices move. This eliminates 90%+ of GitHub Actions ML compute while maintaining forecast accuracy.

## Problem Frame

The current pipeline runs 5 models via GitHub Actions every 15 minutes (~96 runs/day/symbol). This is slow, expensive, and complex. Most runs produce nearly identical forecasts because market conditions don't change enough in 15-minute windows. The key insight: you don't need to re-run the full ensemble every 15 minutes — you need to adjust forecast target prices as actual prices move. (see origin: `docs/brainstorms/2026-04-22-lightweight-ml-pipeline-brainstorm.md`)

## Requirements Trace

- R1. Full ensemble training runs weekly or on-demand, not every 15 minutes
- R2. Training persists forecast points to `ml_forecasts` / `ml_forecasts_intraday`
- R3. Training triggerable via workflow_dispatch for major market events
- R4. Lightweight Kalman adjustment runs inside `ingest-live` every minute
- R5. Adjustment uses Kalman filter to shift forecast targets based on price movement
- R6. Adjusted forecasts written to same tables the chart endpoint reads
- R7. Full training replaces adjusted forecasts with fresh model predictions
- R8. Remove dead model code (Transformer, unused paths)
- R9. Reduce GH Actions ML workflows to weekly training + daily evaluation

## Scope Boundaries

- **In scope:** Kalman adjustment layer in ingest-live, training frequency change, dead code removal, workflow schedule changes
- **Out of scope:** New model architectures, changing chart endpoint response shape, client-side changes
- **Non-goal:** Real-time streaming (existing polling is sufficient)

### Deferred to Separate Tasks

- Model retraining after pipeline change (separate execution run)
- Per-symbol training frequency optimization (some symbols may need more frequent training)

## Key Technical Decisions

- **Kalman adjustment in TypeScript (ingest-live), not Python:** The adjustment is simple math (state update equation). Running it in the existing ingest-live Edge Function avoids a new infrastructure component. The Python Kalman implementation in `intraday_forecast_job.py` (`kalman_weight` config) serves as the reference.
- **Adjust short-term horizons only (15m, 1h, 4h):** Longer horizons (1D+) don't benefit from minute-by-minute adjustment ��� their signal is regime-level, not tick-level. Daily+ forecasts update only on weekly training.
- **Symbol universe stays watchlist-driven:** `resolve_symbol_list()` from `ml/src/scripts/universe_utils.py` sources from `watchlist_items` table. Same universe for both training and live adjustment.
- **Keep the full ensemble for training:** LSTM + ARIMA-GARCH (production ensemble) trains weekly. The Kalman layer adjusts cached predictions between training runs.

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not implementation specification.*

```
Current Pipeline:
  Every 15 min: [Alpaca bars] → [Feature eng] → [5 models] → [Ensemble] → [DB write]
  Cost: ~96 full inference runs/day/symbol

Proposed Pipeline:
  Weekly:      [Alpaca bars] → [Feature eng] → [2 models] → [Ensemble] → [DB write]
  Every 1 min: [Latest bar from ingest-live] → [Kalman adjust cached forecast] → [DB upsert]
  Cost: 1 training/week + simple math every minute

Kalman Adjustment (in ingest-live):
  1. Read latest forecast point from ml_forecasts_intraday for this symbol
  2. Read latest actual price from the m15 bar just ingested
  3. Compute adjustment: new_target = old_target + K * (actual_price - expected_price)
     where K is the Kalman gain (tunable, start with 0.15 matching existing kalman_weight)
  4. Upsert adjusted forecast point back to ml_forecasts_intraday
```

## Phased Delivery

### Phase 1: Add Kalman adjustment to ingest-live (ship first)
Units 1-2. This can run alongside the existing intraday forecast job — both write to the same table via UPSERT. The adjustment improves freshness immediately.

### Phase 2: Reduce training frequency + cleanup
Units 3-5. Once the Kalman adjustment is proven in production, reduce the intraday job to weekly and clean up dead code.

## Implementation Units

- [x] **Unit 1: Add Kalman forecast adjustment to ingest-live**

**Goal:** After writing m1+m15 bars, adjust cached intraday forecast points based on price movement.

**Requirements:** R4, R5, R6

**Dependencies:** None (additive to existing ingest-live)

**Files:**
- Modify: `supabase/functions/ingest-live/index.ts`

**Approach:**
- After the m15 upsert pass (added earlier this session), add a third pass: "forecast adjustment"
- For each symbol in the batch, read the latest `ml_forecasts_intraday` row for horizons 15m, 1h, 4h
- Compare the forecast's `target_price` with the actual latest close price from the m15 bar just written
- Apply Kalman adjustment: `adjusted_target = target_price + gain * (actual_close - forecast_close_at_generation)`
- Upsert the adjusted forecast back with `data_status: 'adjusted'`
- Use a conservative gain (0.15) matching the existing `kalman_weight` in HORIZON_CONFIG
- Respect the 25-second deadline — skip adjustment if m1+m15 passes consumed too much time

**Patterns to follow:**
- Existing m15 upsert pass structure in ingest-live (batch loop, deadline check, error handling)
- `kalman_weight: 0.15` from `ml/src/intraday_forecast_job.py` HORIZON_CONFIG

**Test scenarios:**
- Happy path: Forecast target adjusts toward actual price when price moves away from prediction
- Happy path: Adjustment is proportional to gain * deviation (0.15 * price_diff)
- Edge case: No forecast exists for symbol → skip adjustment, no error
- Edge case: Forecast expired (expires_at < now) → skip, don't adjust stale forecasts
- Edge case: Deadline hit during m15 pass → skip forecast adjustment entirely
- Error path: ml_forecasts_intraday query fails → log warning, continue with next symbol

**Verification:**
- ingest-live logs show "forecast adjustment" pass with upsert counts
- ml_forecasts_intraday rows show `data_status: 'adjusted'` for active forecasts
- Chart endpoint serves adjusted forecasts (no change needed — reads from same table)

---

- [x] **Unit 2: Deploy and validate Kalman adjustment**

**Goal:** Deploy updated ingest-live and validate adjustments are flowing through to the chart.

**Requirements:** R4, R6

**Dependencies:** Unit 1

**Files:**
- No code changes — deployment and monitoring

**Approach:**
- Deploy ingest-live via `npx supabase functions deploy ingest-live`
- Monitor pg_cron run details for ingest-live success
- Check edge function logs for forecast adjustment messages
- Query ml_forecasts_intraday for `data_status = 'adjusted'` rows
- Verify chart endpoint returns forecasts with recent `updated_at`

**Test expectation:** none — operational deployment and validation.

**Verification:**
- ingest-live runs every minute without 401s or deadline hits
- Adjusted forecasts visible in chart response within 2 minutes

---

- [x] **Unit 3: Change intraday forecast schedule from every-15-min to weekly**

**Goal:** Reduce the expensive full-ensemble intraday forecast job from every 15 minutes to weekly.

**Requirements:** R1, R9

**Dependencies:** Unit 2 (Kalman adjustment proven in production)

**Files:**
- Modify: `.github/workflows/schedule-intraday-forecast.yml`

**Approach:**
- Change the cron schedule from `5,20,35,50 13-22 * * 1-5` (every 15 min on weekdays) to `0 4 * * 1` (Monday 4 AM UTC, after market close)
- Keep `workflow_dispatch` for on-demand triggering (R3)
- Update the workflow header comment to reflect the new schedule
- The job itself doesn't change — it runs the same Python ensemble, just less often

**Test scenarios:**
- Happy path: Workflow triggers at the new weekly schedule
- Happy path: workflow_dispatch still allows manual triggering
- Edge case: If weekly run fails, forecasts are still served (Kalman-adjusted from last training)

**Verification:**
- GitHub Actions shows the new cron schedule
- No intraday forecast runs except weekly and manual

---

- [ ] **Unit 4: Remove dead model code**

**Goal:** Remove unused model paths to reduce maintenance surface.

**Requirements:** R8

**Dependencies:** None (parallel with Unit 3)

**Files:**
- Audit: `ml/src/models/` — identify which models are imported but never instantiated in active code paths
- Potentially remove or mark as deprecated: Transformer model, unused XGBoost paths

**Approach:**
- Grep for imports and instantiation of each model in `unified_forecast_job.py` and `intraday_forecast_job.py`
- If a model is never instantiated in either job's active code path, it's dead code
- Remove dead model files or add clear deprecation comments
- Do NOT remove EnsembleForecaster, ArimaGarchForecaster, LSTMForecaster, BaselineForecaster — these are active

**Execution note:** Read each model file and trace its usage before removing. Some models may be used in evaluation or GA training paths.

**Test scenarios:**
- Happy path: All remaining model imports resolve correctly
- Happy path: `pytest ml/tests/ -m "not integration"` passes after removal
- Edge case: Model referenced only in tests — keep the test, remove only the dead production path

**Verification:**
- No unused model imports in active job files
- All tests pass

---

- [ ] **Unit 5: Update DATA_FRESHNESS.md and docs**

**Goal:** Document the new pipeline architecture.

**Requirements:** R1, R4

**Dependencies:** Units 1-4

**Files:**
- Modify: `docs/DATA_FRESHNESS.md`

**Approach:**
- Update the "Ingestion Paths" section to describe the Kalman adjustment layer
- Add a "Forecast Pipeline" section explaining: weekly training, minute-by-minute adjustment, data_status values (live/adjusted/verified)
- Update SLA expectations for forecast freshness

**Test expectation:** none — documentation only.

**Verification:**
- DATA_FRESHNESS.md describes the hybrid architecture

## System-Wide Impact

- **Interaction graph:** ingest-live gains a third pass (forecast adjustment) after m1 and m15 upserts. The chart endpoint reads from ml_forecasts_intraday which now gets both full-training writes (weekly) and Kalman adjustments (every minute). No chart endpoint changes needed.
- **Error propagation:** Kalman adjustment failures must not block m1/m15 ingestion. Each pass is independent — if adjustment fails, bars still flow.
- **State lifecycle risks:** Adjusted forecasts are overwritten by the next full training run (R7). If training fails, adjusted forecasts continue to be served — they drift but don't disappear.
- **Unchanged invariants:** Chart endpoint response shape, Swift client, React frontend — all unchanged. The only difference is forecast points are fresher.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Kalman gain too aggressive — forecasts chase noise | Start conservative (0.15), matching existing kalman_weight. Can tune later. |
| ingest-live 25s deadline leaves no time for adjustment | m1+m15 typically complete in 5-10s for a small watchlist. 15s buffer should suffice. |
| Weekly training misses fast regime changes | workflow_dispatch allows on-demand retrain. Daily evaluation job detects degradation. |
| Adjusted forecasts drift too far between training runs | Monitor drift metrics. If > 2% deviation from last training, trigger automatic retrain. |

## Operational / Rollout Notes

- Phase 1 (Kalman adjustment) ships first and runs alongside existing 15-minute job
- Monitor for 1 week to validate adjustment quality before reducing to weekly training (Phase 2)
- Keep `schedule-intraday-forecast.yml` workflow_dispatch enabled for emergency retrains

## Sources & References

- **Origin document:** [docs/brainstorms/2026-04-22-lightweight-ml-pipeline-brainstorm.md](docs/brainstorms/2026-04-22-lightweight-ml-pipeline-brainstorm.md)
- Existing Kalman config: `ml/src/intraday_forecast_job.py` HORIZON_CONFIG `kalman_weight: 0.15`
- ingest-live (current): `supabase/functions/ingest-live/index.ts`
- Symbol universe: `ml/src/scripts/universe_utils.py`
- Forecast tables: `ml_forecasts`, `ml_forecasts_intraday`
