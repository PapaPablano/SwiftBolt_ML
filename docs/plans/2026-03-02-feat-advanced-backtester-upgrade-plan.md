---
title: "feat: Advanced Backtester Upgrade"
type: feat
status: active
date: 2026-03-02
origin: docs/brainstorms/2026-03-02-advanced-backtester-upgrade-brainstorm.md
---

# feat: Advanced Backtester Upgrade

## Overview

Transform the functional-but-basic backtester into a quant-grade research tool. This is a Big Bang upgrade spanning the TS worker, Swift macOS client, and Supabase persistence layer. Fixes critical foundation bugs (crossover operators silently ignored, custom indicator periods not applied, 13+ indicators defined but not computed), then adds short selling, OR logic, statistical validation, advanced Swift Charts visuals, position sizing modes, and Supabase strategy persistence. (see brainstorm: docs/brainstorms/2026-03-02-advanced-backtester-upgrade-brainstorm.md)

## Problem Statement

The backtester is functional with real data but has serious gaps:

1. **Silent correctness bugs:** `cross_up`/`cross_down` operators pass through without evaluation (always true). Any MACD crossover strategy produces wrong results today.
2. **Custom parameters ignored:** Users can set RSI(9) in the UI but the worker always computes RSI(14). The `params` field is carried but never read.
3. **13+ phantom indicators:** MFI, Williams %R, Parabolic SAR, VWAP, KDJ, etc. are listed in the Swift UI but silently skipped by the worker.
4. **Long-only limitation:** No short selling despite `direction` field in trade output.
5. **No statistical rigor:** Raw metrics only — no confidence intervals, p-values, or IS/OOS validation.
6. **No advanced charts:** Only equity curve exists. No drawdown, heatmap, rolling metrics, or P&L distribution.
7. **No persistence:** Strategies are local mock data, lost on every session.
8. **Sharpe annualization bug:** Worker uses `sqrt(252)` regardless of timeframe (incorrect for intraday).

## Proposed Solution

Big Bang upgrade organized into 8 implementation tasks, shipped on one feature branch. Fix foundations first (indicator engine, crossovers, short selling), then add statistical validation, advanced visuals, and persistence.

## Technical Approach

### Design Decisions (from brainstorm)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Short selling model | Strategy-level direction enum (`long_only`, `short_only`, `long_short`) | Simpler than per-condition direction. No simultaneous positions. No margin. |
| OR logic model | Flat group-level OR: conditions within a group AND'd, groups OR'd | CNF-like. Avoids nested tree evaluator complexity. |
| Crossover detection | `cross_up` = `indicator[i] > value AND indicator[i-1] <= value` | Standard definition. First bar returns false. |
| Statistical tests | Bootstrap CI on Sharpe/drawdown/win_rate; t-test p-value on mean return vs. zero | Answers "did this strategy make money?" |
| IS/OOS methodology | Fixed 70/30 split by date, same strategy, no re-optimization | Simple evaluation, not parameter optimization. |
| Indicator registry | Keyed by `(name, params)` so RSI(7) and RSI(21) are independent | Correct semantics. Lazy computation. |
| Position sizing | `percent_of_equity` (default), `fixed_dollar`, `half_kelly` (min 10 trades) | Half Kelly to avoid aggressive sizing. |
| Persistence | Debounced auto-save (2s) + explicit "Save to Cloud" button | Balance between losing work and API noise. |
| Sharpe annualization | Timeframe-aware factor map: `{ d1: 252, h4: 1638, h1: 6552, m30: 6552, m15: 6552 }` | Fix existing bug. |
| Drawdown chart | Percentage drawdown from peak, negative area chart | Standard quant convention. |
| P&L histogram | Percentage return per trade, 20 bins | Most informative for strategy evaluation. |
| Rolling Sharpe window | 63 bars (~3 months daily) | Sufficient sample size for meaningful Sharpe. |
| Monthly heatmap partials | Show actual return, dim partial months | Avoid misleading extrapolation. |

### Implementation Phases

All phases ship together on one branch but are logically ordered for dependency management.

---

#### Phase 1: Worker Indicator Engine Redesign

**Goal:** Replace hardcoded indicator computation with an extensible registry that respects custom parameters.

##### Task 1.1: Build indicator registry (`strategy-backtest-worker/indicators.ts`)

- [x] Create `IndicatorRegistry` class: `Map<string, (bars: Bar[], params: Record<string, number>) => Record<string, number[]>>`
- [x] Migrate existing indicators to registry functions with configurable periods:
  - `sma(period)`, `ema(period)`, `rsi(period)`, `macd(fast, slow, signal)`, `atr(period)`, `stochastic(period)`, `adx(period)`, `bollinger(period, stdDev)`, `cci(period)`, `obv()`, `supertrend(period, multiplier)`, `volume_ma(period)`
- [x] Each function receives `params` from the condition and falls back to defaults if not provided
- [x] Indicator results keyed by `(name, JSON.stringify(params))` for caching across conditions
- [x] Lazy computation: only compute indicators referenced by conditions
- [x] Add new indicators: `mfi(period)`, `williams_r(period)`, `momentum(period)`, `roc(period)`

##### Task 1.2: Fix crossover operators (`strategy-backtest-worker/index.ts`)

- [x] Add `cross_up` and `cross_down` to `evaluateConditions()`:
  ```
  cross_up: indicator[barIndex] > value AND indicator[barIndex - 1] <= value
  cross_down: indicator[barIndex] < value AND indicator[barIndex - 1] >= value
  ```
- [x] Return `false` for bar index 0 (no previous bar)

##### Task 1.3: Wire condition params to indicator computation

- [x] In `evaluateConditions()`, extract `params` from each condition
- [x] Pass params to registry lookup via `buildIndicatorCache` + `getIndicatorValue`
- [x] If indicator not found in registry, log warning and skip (existing behavior)
- [x] Normalize camelCase frontend params (fastPeriod→fast, stdDev→std_dev, etc.)

##### Task 1.4: Fix Sharpe annualization for intraday timeframes

- [x] Add timeframe to worker context (already available from job params)
- [x] Replace hardcoded `Math.sqrt(252)` with timeframe-aware `annualizationFactor(timeframe)` from indicators.ts

**Files:**
- NEW: `supabase/functions/strategy-backtest-worker/indicators.ts`
- MODIFY: `supabase/functions/strategy-backtest-worker/index.ts`

---

#### Phase 2: Short Selling & Position Sizing

**Goal:** Enable short positions and configurable position sizing modes.

##### Task 2.1: Add short selling to backtest loop

- [x] Add `direction` field to strategy config: `"long_only"` (default), `"short_only"`, `"long_short"`
- [x] Implement signed-shares model: `shares = +N` for long, `-N` for short
  - Entry: `cash -= shares * execPrice` (unified for both directions)
  - Exit: `cash += shares * exitPrice; shares = 0` (unified)
  - Equity: `cash + shares * currentPrice` (correct for both)
- [x] Invert SL/TP for shorts: SL triggers on price rise, TP triggers on price drop
- [x] Trade output records actual direction ("long"/"short")

##### Task 2.2: Add position sizing modes

- [x] Read `position_sizing`/`positionSizing` from strategy_config
- [x] `percent_of_equity`: shares = floor((equity * value/100) / execPrice)
- [x] `fixed_dollar`: shares = floor(value / execPrice)
- [x] `half_kelly`: activates after 10 trades, falls back to 2% before that
- [x] Extract SL/TP from strategy_config (riskManagement.stopLoss/takeProfit)

##### Task 2.3: Update strategy-translator.ts

- [ ] Add `direction` field to `WorkerCondition` and `NormalizedConfig`
- [ ] Add `position_sizing` to normalized config
- [ ] Map frontend/Swift config to worker format

**Files:**
- MODIFY: `supabase/functions/strategy-backtest-worker/index.ts`
- MODIFY: `supabase/functions/_shared/strategy-translator.ts`

---

#### Phase 3: OR Logic Between Conditions

**Goal:** Allow conditions to be grouped with OR logic (CNF model).

##### Task 3.1: Add condition group support to worker

- [x] Change condition structure from flat array to grouped:
  ```typescript
  interface ConditionGroup {
    conditions: WorkerCondition[];  // AND within group
    logicalOp: "AND" | "OR";       // how this group relates to next
  }
  ```
- [x] `evaluateConditionGroups()` logic:
  - Evaluate each group: all conditions in a group must be true (AND)
  - Groups connected by OR: at least one group must pass
  - Single flat array (no groups) treated as one AND group (backward compatible)
- [x] Backward compatibility: if conditions array contains raw conditions (no groups), wrap in a single AND group

##### Task 3.2: Update strategy-translator.ts for groups

- [x] Add `ConditionGroup` and `FrontendConditionGroup` types to translator
- [x] Add `normalizeToWorkerGroups()` — handles worker groups → frontend groups → flat worker → flat frontend with fallback chain
- [x] `StrategyConfigRaw` updated with `entry_condition_groups`, `exit_condition_groups`, `entryConditionGroups`, `exitConditionGroups`, `direction`, `positionSizing`

##### Task 3.3: Update Swift UI for OR grouping

- [ ] Add "OR" divider button between condition groups in `ConditionsCardWeb`
- [ ] Visual separation: groups in rounded boxes, "OR" pill between them
- [ ] Each group can have multiple AND conditions
- [ ] "Add condition" adds to current group, "Add OR group" creates a new group
- [ ] Update `buildStrategyConfig()` to serialize groups

**Files:**
- MODIFY: `supabase/functions/strategy-backtest-worker/index.ts`
- MODIFY: `supabase/functions/_shared/strategy-translator.ts`
- MODIFY: `client-macos/SwiftBoltML/Views/StrategyBuilderWebStyle.swift`

---

#### Phase 4: Statistical Validation

**Goal:** Add confidence intervals, p-values, and IS/OOS split to worker output.

##### Task 4.1: Implement bootstrap confidence intervals

- [x] After backtest completes, run bootstrap on trade returns (1000 iterations):
  - Resample trade P&L array with replacement
  - Compute Sharpe, max drawdown, win rate for each sample
  - Report 2.5th and 97.5th percentiles as 95% CI
- [x] Compute p-value: two-tailed t-test on daily returns vs. zero mean (incomplete beta function implementation)
- [x] Add `validation` object to response with confidence_intervals, p_value, bootstrap_iterations, sample_size, in_sample, out_of_sample
- [x] Skip validation if fewer than 10 trades (insufficient sample)

##### Task 4.2: Implement IS/OOS split

- [x] Split equity curve at 70% mark by bar index (temporal correctness)
- [x] Compute IS and OOS metrics using split equity and filtered trades
- [x] Both sections returned as `in_sample` and `out_of_sample` within `validation`

##### Task 4.3: Compute monthly returns and rolling metrics

- [x] Aggregate equity curve into monthly returns: `{ year, month, return_pct, is_partial }`
- [x] Compute rolling Sharpe over 63-bar window: `{ date, sharpe_63, win_rate_63 }`
- [x] Compute drawdown series: `{ date, drawdown_pct }` (negative values, 0 at peaks)
- [x] All three arrays returned from worker and forwarded by frontend `backtestService.ts`

**Files:**
- MODIFY: `supabase/functions/strategy-backtest-worker/index.ts`
- NEW: `supabase/functions/strategy-backtest-worker/validation.ts`

---

#### Phase 5: Swift Model & API Updates

**Goal:** Update Swift models to decode new worker fields; update APIClient; add trade metadata.

##### Task 5.1: Update BacktestingModels.swift

- [ ] Add to `BacktestResultPayload`:
  ```swift
  let validation: BacktestValidation?
  let monthlyReturns: [MonthlyReturn]?
  let rollingMetrics: [RollingMetric]?
  let drawdownSeries: [DrawdownPoint]?
  ```
- [ ] New structs:
  ```swift
  struct BacktestValidation: Decodable {
    let confidenceIntervals: ConfidenceIntervals?
    let pValue: Double?
    let inSample: SplitMetrics?
    let outOfSample: SplitMetrics?
    let sampleSize: Int?
    let bootstrapIterations: Int?
  }
  struct ConfidenceIntervals: Decodable { ... }
  struct SplitMetrics: Decodable { ... }
  struct MonthlyReturn: Decodable { let year: Int; let month: Int; let returnPct: Double }
  struct RollingMetric: Decodable { let date: String; let sharpe63: Double?; let winRate63: Double? }
  struct DrawdownPoint: Decodable { let date: String; let drawdownPct: Double }
  ```
- [ ] All new fields use `decodeIfPresent` for backward compatibility

##### Task 5.2: Update Trade model

- [ ] Add `direction`, `closeReason`, `quantity`, `returnPct` to `Trade` struct in StrategyBuilderWebStyle.swift
- [ ] Update `BacktestResult.from()` to map these fields from `BacktestResultTrade`
- [ ] Update `TradesTableWeb` to display direction (arrow icon), close reason, and return %

##### Task 5.3: Update BacktestResult

- [ ] Add `validation`, `monthlyReturns`, `rollingMetrics`, `drawdownSeries` to `BacktestResult`
- [ ] Update `BacktestResult.from()` factory to pass through new data

##### Task 5.4: Add direction and position sizing to Swift UI

- [ ] Add direction picker to `BacktestWebStyle`: Segmented control (Long Only / Short Only / Long & Short)
- [ ] Add position sizing mode picker: percent_of_equity / fixed_dollar / half_kelly with value input
- [ ] Update `buildStrategyConfig()` to include `direction` and `position_sizing`

##### Task 5.5: Add cancel backtest button

- [ ] Add "Cancel" button visible during polling
- [ ] Call existing PATCH endpoint on `backtest-strategy` Edge Function
- [ ] Stop polling loop on cancellation

**Files:**
- MODIFY: `client-macos/SwiftBoltML/Models/BacktestingModels.swift`
- MODIFY: `client-macos/SwiftBoltML/Views/StrategyBuilderWebStyle.swift`
- MODIFY: `client-macos/SwiftBoltML/Services/APIClient.swift`

---

#### Phase 6: Advanced Swift Charts Visuals

**Goal:** Add 4 new chart views: monthly heatmap, rolling Sharpe, drawdown, P&L histogram.

##### Task 6.1: Monthly return heatmap

- [ ] New `MonthlyHeatmapChart` view using Swift Charts `RectangleMark`
- [ ] X-axis: months (Jan-Dec), Y-axis: years
- [ ] Color scale: deep red (-10%+) → light red → gray (0%) → light green → deep green (+10%+)
- [ ] Partial months dimmed with reduced opacity
- [ ] Tooltip on hover showing exact return %
- [ ] Computed client-side from `monthlyReturns` array (or from equity curve if not available)

##### Task 6.2: Rolling Sharpe chart

- [ ] New `RollingSharpeChart` view using Swift Charts `LineMark`
- [ ] Plot rolling Sharpe over time with a horizontal reference line at 0 and 1.0
- [ ] Color: green above 1.0, yellow 0-1.0, red below 0
- [ ] Secondary line for rolling win rate (right Y-axis)
- [ ] Computed from `rollingMetrics` array

##### Task 6.3: Drawdown chart

- [ ] New `DrawdownChart` view using Swift Charts `AreaMark`
- [ ] Always negative (0 at peaks, negative during drawdowns)
- [ ] Red fill, darker at deeper drawdowns
- [ ] Max drawdown line annotated with date and depth
- [ ] Computed from `drawdownSeries` array (or from equity curve client-side)

##### Task 6.4: P&L distribution histogram

- [ ] New `PnLHistogramChart` view using Swift Charts `BarMark`
- [ ] Bin trade returns into 20 buckets
- [ ] Green bars for positive bins, red for negative
- [ ] Vertical line at mean return
- [ ] Show count per bin
- [ ] Computed client-side from trades array

##### Task 6.5: Statistical validation card

- [ ] New `ValidationCardWeb` view showing:
  - Sharpe CI: "1.2 [0.8, 2.1] (95% CI)"
  - p-value with significance indicator (green if < 0.05)
  - IS vs OOS comparison: side-by-side metrics with delta
  - Sample size and bootstrap iterations
- [ ] Show "Insufficient data" if < 10 trades

##### Task 6.6: Integrate into BacktestResultsWeb

- [ ] Add tabbed sections or scrollable layout:
  1. Summary metrics grid (existing)
  2. Equity curve (existing)
  3. Statistical validation card (new)
  4. Monthly heatmap (new)
  5. Rolling metrics (new)
  6. Drawdown chart (new)
  7. P&L distribution (new)
  8. Trade history table (existing)

**Files:**
- NEW: `client-macos/SwiftBoltML/Views/BacktestCharts/MonthlyHeatmapChart.swift`
- NEW: `client-macos/SwiftBoltML/Views/BacktestCharts/RollingSharpeChart.swift`
- NEW: `client-macos/SwiftBoltML/Views/BacktestCharts/DrawdownChart.swift`
- NEW: `client-macos/SwiftBoltML/Views/BacktestCharts/PnLHistogramChart.swift`
- NEW: `client-macos/SwiftBoltML/Views/BacktestCharts/ValidationCardWeb.swift`
- MODIFY: `client-macos/SwiftBoltML/Views/StrategyBuilderWebStyle.swift`

---

#### Phase 7: Supabase Strategy Persistence

**Goal:** Sync strategies with `strategy_user_strategies` table across sessions.

##### Task 7.1: Make Strategy model Codable and Supabase-compatible

- [ ] Add `Codable` conformance to `Strategy`, `StrategyCondition`
- [ ] Use server-generated UUID (from Supabase) instead of client-side `UUID()`
- [ ] Map Swift properties to Supabase column names:
  - `id` → `id`
  - `name` → `name`
  - `description` → `description`
  - `entryConditions`, `exitConditions`, `stopLoss`, `takeProfit`, `positionSizing`, `direction` → `config` JSONB
  - `isActive` → `is_active`
- [ ] Add `userId: String?` field populated from auth

##### Task 7.2: Add strategy CRUD to APIClient

- [ ] `fetchStrategies() async throws -> [Strategy]` — GET from `strategy_user_strategies` where `user_id` matches
- [ ] `createStrategy(_ strategy: Strategy) async throws -> Strategy` — INSERT, return with server ID
- [ ] `updateStrategy(_ strategy: Strategy) async throws` — UPDATE by ID
- [ ] `deleteStrategy(id: String) async throws` — DELETE by ID
- [ ] All calls authenticated with JWT from SupabaseService

##### Task 7.3: Update StrategyBuilderViewModel for persistence

- [ ] Make `@MainActor` for thread safety
- [ ] On init: fetch strategies from Supabase, fall back to local mock if auth fails
- [ ] Debounced auto-save: 2-second delay after last edit
- [ ] Explicit "Save to Cloud" button in header bar
- [ ] Handle offline: queue changes, sync when connected
- [ ] Replace `loadMockStrategies()` with Supabase fetch

##### Task 7.4: Add OR condition groups to Strategy model

- [ ] Update `Strategy.entryConditions` and `exitConditions` from `[StrategyCondition]` to `[ConditionGroup]`
- [ ] `ConditionGroup` has `conditions: [StrategyCondition]` and `logicalOp: String` ("AND" default)
- [ ] Backward compatible: single conditions wrapped in a group

**Files:**
- MODIFY: `client-macos/SwiftBoltML/Views/StrategyBuilderWebStyle.swift`
- MODIFY: `client-macos/SwiftBoltML/Services/APIClient.swift`

---

#### Phase 8: Integration & Polish

##### Task 8.1: Add Xcode build phase entries for new files

- [ ] Add all new Swift files to project.pbxproj (PBXBuildFile, PBXFileReference, Sources)
- [ ] Create `BacktestCharts` group in Xcode project

##### Task 8.2: Deploy Edge Functions

- [ ] Deploy updated `strategy-backtest-worker`
- [ ] Deploy updated `backtest-strategy` (if changed)
- [ ] Verify with test backtest: custom RSI strategy with short selling

##### Task 8.3: End-to-end verification

- [ ] Run backtest with custom RSI(9) < 30 entry, RSI(9) > 70 exit
- [ ] Verify crossover strategy: MACD crosses_above 0
- [ ] Verify short selling: Short-only strategy
- [ ] Verify OR logic: (RSI < 30 OR Price > SMA) entry
- [ ] Verify statistical validation appears in results
- [ ] Verify all 4 new charts render
- [ ] Verify strategy persistence across app restart

---

## System-Wide Impact

### Interaction Graph

1. Swift UI edit → `buildStrategyConfig()` → `APIClient.queueBacktestJob()` → `backtest-strategy` Edge Function → INSERT `strategy_backtest_jobs` → worker triggered
2. Worker `runBacktest()` → `IndicatorRegistry.compute()` → `evaluateConditions()` with groups → trade loop with direction → `computeValidation()` → INSERT `strategy_backtest_results` → UPDATE job status
3. Swift polls `getBacktestJobStatus()` → `BacktestResult.from()` → renders `BacktestResultsWeb` with charts

### Error & Failure Propagation

- Unknown indicator → warning logged, condition skipped (existing behavior, acceptable)
- Bootstrap with < 10 trades → skip validation, return null (not an error)
- Supabase persistence failure → show error toast, keep local changes, retry on next edit
- Worker crash between result insert and job update → stale cleanup marks job failed after 5 min (existing, Gap 37 from analysis — acceptable for now)

### State Lifecycle Risks

- **Strategy identity transition:** When local Strategy gets a server ID, all references must update. Mitigated by using server ID as source of truth after first save.
- **Concurrent edits:** No conflict resolution in V1. Last write wins. Acceptable for single-user tool.

### API Surface Parity

- Worker response shape changes (additive only — new optional fields)
- Swift models use `decodeIfPresent` for all new fields → backward compatible
- Frontend `BacktestResultsPanel.tsx` would benefit from the same validation data but is out of scope for this plan (Swift-only)

### Integration Test Scenarios

1. **Custom period indicator:** RSI(7) strategy → worker computes RSI with period 7 → results differ from RSI(14)
2. **Crossover detection:** MACD crosses_above 0 → entry only on actual crossover bars, not on all bars where MACD > 0
3. **Short selling P&L:** Short entry at $100, exit at $90 → P&L = +$10/share (not -$10)
4. **OR group evaluation:** Group A fails, Group B passes → entry triggers
5. **IS/OOS split:** 1-year backtest → IS uses first 70% of bars, OOS uses last 30%, both return valid metrics

---

## Acceptance Criteria

### Functional Requirements

- [ ] All ~35 indicators compute with configurable periods from condition params
- [ ] `cross_up` and `cross_down` operators correctly detect threshold crossings
- [ ] Short selling works: short entry, inverted SL/TP, correct P&L
- [ ] OR logic: condition groups with AND within, OR between
- [ ] Position sizing: percent_of_equity, fixed_dollar, half_kelly all functional
- [ ] Statistical validation: 95% CI on Sharpe/drawdown/win_rate, p-value, IS/OOS split
- [ ] Monthly heatmap chart renders with color-coded returns
- [ ] Rolling Sharpe chart renders with reference lines
- [ ] Drawdown chart renders as negative area
- [ ] P&L histogram renders with green/red bins
- [ ] Validation card shows CI, p-value, IS vs OOS comparison
- [ ] Strategies persist to Supabase, survive app restart
- [ ] Cancel button stops running backtest
- [ ] Trade table shows direction, close reason, return %
- [ ] Sharpe ratio correctly annualized for all timeframes

### Non-Functional Requirements

- [ ] Worker backtest completes within 120s for 1-year daily data
- [ ] Bootstrap validation adds < 5s to total computation time
- [ ] All new Swift Charts render in < 500ms for 1000 data points
- [ ] Supabase strategy CRUD operations complete in < 2s

### Quality Gates

- [ ] Xcode BUILD SUCCEEDED with zero warnings in modified files
- [ ] Edge Function deploys without errors
- [ ] End-to-end backtest with custom strategy returns correct results

---

## Dependencies & Prerequisites

- Supabase `strategy_user_strategies` table exists (confirmed — created in PR #22)
- Swift app has authenticated Supabase session (confirmed — `SupabaseService.shared`)
- Worker heartbeat and cancellation support (confirmed — added in PR #26)

## Risk Analysis & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Bootstrap adds too much latency | Medium | Medium | Cap at 500 iterations if > 100 trades; skip if > 500 trades |
| Edge Function memory exceeded for large intraday backtests | Medium | High | Limit intraday to 1 year (15m), 2 years (1h) at job creation |
| OR logic UI too complex | Low | Medium | Start with simple "Add OR Group" button, no nesting |
| Kelly criterion produces extreme sizing early | Low | High | Half Kelly, minimum 10 trades before activation |

## Future Considerations

- Monte Carlo simulation of trade sequences (shuffle trade order, estimate tail risk)
- Regime-aware testing (segment by bull/bear/sideways markets)
- Multi-timeframe conditions (daily RSI + hourly MACD)
- Multi-asset portfolio backtesting
- Walk-forward parameter optimization
- Strategy comparison (side-by-side results)
- `ml_signal` indicator integration with ML pipeline

## Sources & References

### Origin

- **Brainstorm document:** [docs/brainstorms/2026-03-02-advanced-backtester-upgrade-brainstorm.md](docs/brainstorms/2026-03-02-advanced-backtester-upgrade-brainstorm.md) — Key decisions: indicator registry pattern, Big Bang approach, short selling support, flat OR groups, bootstrap CI + t-test p-value, Supabase persistence with debounced auto-save.

### Internal References

- Worker: `supabase/functions/strategy-backtest-worker/index.ts`
- Strategy translator: `supabase/functions/_shared/strategy-translator.ts`
- Swift models: `client-macos/SwiftBoltML/Models/BacktestingModels.swift`
- Swift UI: `client-macos/SwiftBoltML/Views/StrategyBuilderWebStyle.swift`
- API client: `client-macos/SwiftBoltML/Services/APIClient.swift`
- Historical bugs: `docs/BACKTESTING_INSTITUTIONAL_LEARNINGS.md`
- Resolved todos: `todos/079-084` (parameter bypass, strategy rejection, race conditions, capital mismatch, hardcoded timeframe, condition loss)

### Related Work

- PR #22: Strategy platform implementation (foundation)
- PR #23: P1/P2 fixes
- PR #26: Backtest timeout reliability fix
