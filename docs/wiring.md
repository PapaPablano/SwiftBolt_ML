# Frontend Wiring Inspection (SwiftBolt ML)

Last updated: 2026-01-17

## Scope
This document summarizes current frontend wiring across charting/forecasting, options ranking, and ML dashboard views, plus a detailed list of fixes and suggested improvements.

---

## 1) App Routing & State Ownership

**Entry + routing**
- `ContentView` routes between `PredictionsView` and the stock detail split view. 
- Stock detail view: `ChartView` + tabbed panel (News / Options / Analysis).  

**Single source of truth**
- `AppViewModel` owns shared view models and syncs selection + indicator configs.

**Key files**
- `Views/ContentView.swift`
- `ViewModels/AppViewModel.swift`

---

## 2) Chart + Forecast Wiring

### 2.1 Symbol → Chart Load
- `AppViewModel.selectedSymbol` sets `ChartViewModel.selectedSymbol` → `loadChart()` via `didSet`.

### 2.2 Chart API paths
- **Primary (legacy)**: `APIClient.fetchChartRead()` (edge function `chart-read`) → `ChartResponse`.
- **Legacy REST**: `APIClient.fetchChart()` (endpoint `chart`).
- **V2 (layered)**: `APIClient.fetchChartV2()` returns `ChartDataV2Response` but **not currently called** in `ChartViewModel.loadChart()`.

### 2.3 Forecast UI (native & web)
- `ForecastHorizonsView` is rendered in **both** `ChartView` and `AnalysisView` when `mlSummary` exists.
- `ChartViewModel.selectedForecastHorizon` feeds chart overlays only when selected from the chart header card.
- `WebChartView` is ready for layered V2 data but only receives legacy `chartData` today.

---

## 3) Analysis Tab + Enhanced ML

- `AnalysisViewModel.loadEnhancedInsights()` calls `APIClient.fetchEnhancedPrediction()`.
- `ForecastExplainerView` and multi-timeframe consensus render from the response if available.
- Support/resistance data is fetched separately via `APIClient.fetchSupportResistance()`.

---

## 4) Predictions / ML Dashboard

- `PredictionsViewModel.loadDashboard()` hits `ml-dashboard`.
- Forecast accuracy tab fetches `action=horizon_accuracy`, `action=weights`, and `action=evaluations`.

---

## 5) Options Ranking Wiring

### 5.1 Ranker
- `OptionsRankerViewModel.loadRankings()` → `APIClient.fetchOptionsRankings()`.
- `OptionsRankerViewModel.triggerRankingJob()` → `APIClient.triggerRankingJob()`.
- Quotes refresh uses `APIClient.fetchOptionsQuotes()`.

### 5.2 Ranker views
- `OptionsRankerView` (all contracts + filters).
- `OptionsRankerExpiryView` (grouped by expiry).
- `OptionRankDetailView` (detail + strike analysis + metrics).

### 5.3 Options chain
- `OptionsChainViewModel.loadOptionsChain()` → `APIClient.fetchOptionsChain()`.

---

# Fixes (Detailed)

## A) WebChart V2 Forecast Layers Not Used
**Issue**: `ChartViewModel.loadChart()` never assigns `chartDataV2`, so `WebChartView` always falls back to `chartData` and never uses layered V2 forecast data.  
**Fix**:
1. In `ChartViewModel.loadChart()` when `useV2API == true`, call `fetchChartV2()` and set `chartDataV2`.
2. Keep `chartData` as legacy fallback, but ensure `chartDataV2` is populated to drive layered overlays in `WebChartView`.
3. Confirm `selectedForecastHorizon` updates are applied to V2 forecast bars in `WebChartView.applyForecastOverlay()`.

## B) Forecast Horizon Selection Not Shared Between Analysis + Chart
**Issue**: Analysis tab uses `ForecastHorizonsView` with local `selectedHorizon`, which does not update `ChartViewModel.selectedForecastHorizon`.  
**Fix**:
1. Bind `AnalysisView` horizon selector to `ChartViewModel.selectedForecastHorizon` (like `ChartView` does).
2. Ensure `ChartViewModel.rebuildSelectedForecastBars()` is called on horizon changes.

## C) GA Strategy + Recommendation Not Surfaced in UI
**Issue**: `OptionsRankerViewModel` loads GA strategy and recommendation but no UI uses them.  
**Fix**:
1. Add a GA summary card (strategy weights + recommendation) to `RankerHeader` or `RankedOptionsContent`.
2. Provide a toggle to enable GA filter and show how it affects ranking counts.

## D) Ranking Freshness Status Depends on `run_at`
**Issue**: `OptionsRankerViewModel.updateRankingStatus()` depends on `OptionRank.runAt`. If backend doesn’t include it, status is always `.unknown`.  
**Fix**:
1. Ensure `run_at` is returned in `options-rankings` payload.
2. Add a fallback: if no `run_at`, use response timestamp or skip freshness badge.

## E) WebChart Forecast Confidence Badge Tied to Intraday Only
**Issue**: `WebChartView` adds confidence badge only for intraday timeframes.  
**Fix**:
1. Apply the badge for all timeframes if `mlSummary` exists (or explicitly document the constraint).

## F) Multi-Timeframe Forecast Charting (Missing Wiring)
**Issue**: Multi-timeframe forecast visualization (m15/h1/h4/d1/w1) is not surfaced as a unified experience. Current forecast plotting only reflects the active timeframe, and there is no wiring to load or compare forecast series across multiple timeframes.  
**Fix**:
1. Add a multi-timeframe forecast fetch path in `ChartViewModel` that requests all five timeframes in a single operation (m15/h1/h4/d1/w1) and stores them in a new `multiTimeframeForecasts` model.
2. Ensure the fetch path uses the same horizon selection semantics across timeframes (shared `selectedForecastHorizon`).
3. Add a multi-timeframe selector UI (preset stack) to display aligned forecast horizons side-by-side (mini grid or stacked panels).
4. Wire `ForecastHorizonsView` to accept an optional `timeframe` parameter and render a compact card for each timeframe when in multi-timeframe mode.

## G) Cross-Timeframe Trend Alignment Badge
**Issue**: No visual indicator when multiple timeframes agree or conflict on direction.  
**Fix**:
1. Add a computed `trendAlignment` model in `ChartViewModel` that summarizes agreement across timeframes (e.g., bullish/bearish/neutral alignment score).
2. Render a small badge in `ChartHeader` and in the forecast card header to show alignment status.
3. Use color-coded states (green aligned, yellow mixed, red conflicting) and show the contributing timeframes in a tooltip.

---

# Suggested Improvements

## 1) Unified Chart Data Fetching
- Introduce a single consolidated fetch path (e.g., `fetchConsolidatedChart`) and deprecate mixed `chart-read` vs `chart-data-v2` usage.
- Make `ChartViewModel` pick the endpoint based on `indicatorConfig.useWebChart` or a single feature flag.

## 2) Forecast UX Consistency
- Ensure `ForecastHorizonsView` selection always updates the same shared `selectedForecastHorizon` (in both Chart + Analysis).
- Add hover/tooltip with forecast confidence + time delta per horizon.

## 3) Options Ranker Feedback Loop
- Display ranking health signals (IC collapse, stability) if backend exposes them.
- Add “last refresh” timestamp near ranker header.

## 4) Health + Data Recency Surfacing
- Surface `dataQuality` and staleness report in `ChartHeader` or `AnalysisView` so users see stale data immediately.

## 5) Standardize Error/Empty States
- Consolidate error placeholders across Chart/Options/Predictions to a single reusable component.

## 6) Multi-Timeframe Forecast UX Enhancements
- Add a **multi-timeframe grid view** that shows weekly/daily/intraday forecasts together (drag-to-reorder optional).
- Provide a **timeframe stack preset selector** (e.g., Swing: w1/d1/h4, Day: d1/h1/m15) that automatically loads those series.
- Add a **trend alignment badge** and a short “alignment summary” line (e.g., “3/5 timeframes bullish”).
- Display **forecast delta vs current price** for each timeframe in a compact chip row.
- Optionally add a **confidence band overlay** per timeframe in the web chart for quick comparison.

## 7) Multi-Timeframe Control Surface
- Add a small control strip near the chart header that toggles single-timeframe vs multi-timeframe mode.
- Allow synchronized pan/zoom across mini charts to keep bars aligned in time when comparing timeframes.

---

# Appendix: Primary Wiring Files
- `ViewModels/AppViewModel.swift`
- `ViewModels/ChartViewModel.swift`
- `Views/ChartView.swift`
- `Views/WebChartView.swift`
- `Views/AdvancedChartView.swift`
- `Views/AnalysisView.swift`
- `ViewModels/AnalysisViewModel.swift`
- `Views/OptionsRankerView.swift`
- `ViewModels/OptionsRankerViewModel.swift`
- `Views/OptionsChainView.swift`
- `ViewModels/OptionsChainViewModel.swift`
- `Views/PredictionsView.swift`
- `ViewModels/PredictionsViewModel.swift`
- `Views/ForecastAccuracyTabView.swift`
- `Services/APIClient.swift`
