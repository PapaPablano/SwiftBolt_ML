# Stock Analysis Platform — High‑Level Blueprint (Working Draft)

**Last Updated:** February 2026

## Implementation Status (Feb 2026)

- **Backend**: Supabase (Postgres + Edge Functions). Primary market data: **Alpaca**; news/events: Finnhub; supplemental: Polygon (Massive).
- **ML pipeline**: Unified forecast job (`unified_forecast_job.py`), daily horizons 1D/1W/1M, intraday 15m/1h. **2-model ensemble** (LSTM + ARIMA-GARCH) in canary; Gradient Boosting and Transformer disabled for production (Transformer permanently off; see ACTION_ITEMS.md).
- **Phase 7 canary**: 6-day validation (Jan 28–Feb 4) on AAPL, MSFT, SPY; walk-forward optimizer, divergence monitoring, `ensemble_validation_metrics`. GO/NO-GO decision after canary. See `1_27_Phase_7.1_Schedule.md`, `PHASE_7_CANARY_DEPLOYMENT_STATUS.md`.
- **Sentiment**: Backfill and `sentiment_scores` table exist; sentiment feature temporarily disabled (zero-variance fix) until `validate_sentiment_variance` passes. See `docs/technicalsummary.md`.
- **Orchestration**: GitHub Actions ML workflow; Transformer disabled; continue-on-error for populate_live_predictions; health checks documented.

## Mission

Make advanced technical analysis and machine‑learning insights accessible and digestible to the average trader.

## Scope of Supported Markets (Initial → Future)

* **Initial Production**: US Stocks, Futures, Options
* **Later Expansion**: Crypto assets

## Vision & Goals

* Deliver a unified platform combining traditional technical analysis with ML‑powered predictive analytics.
* Simplify complex analytics for novice traders while remaining powerful for advanced users.
* Provide a seamless workflow from data → insight → action.
* Maintain transparency and interpretability for all signals.
* Support extensibility for advanced custom strategies.

## Core Functional Modules

**Data Layer**: Ingest and store historical + real‑time OHLCV data across stocks, futures, and options. Normalize and validate data.

**Charting & Technical Analysis**: Interactive multi‑asset charts; indicators (SMA, EMA, MACD, RSI, Bollinger Bands, VWAP, etc.); pattern recognition; drawing tools.

**Screeners & Filters**: Multi‑asset scanners with technical conditions, volume conditions, volatility filters, and options‑specific filters (IV rank, OI, greeks planned for future).

**ML‑Powered Analytics**: Feature‑engineering pipeline, supervised models, time‑series forecasting models, probability‑based signals, model monitoring.

**Backtesting Engine**: Strategy simulation for indicator and ML‑based systems. Metrics: returns, drawdowns, volatility, Sharpe, win rate.

**Alerts & Notifications**: Triggered by technical criteria, ML signals, screener hits. Delivery via email/push/webhooks.

**User Interface**: Native macOS desktop app with customizable panels: charts, signals, screener results, option chains, and futures ladders, built using SwiftUI.

**Extensibility**: User‑defined indicators and strategies; plugin architecture for advanced users.

**Future Trading & Risk Layer**: Optional integration with broker APIs; position sizing tools; stop/limit modeling.

## Technology Stack (Current)

**Backend**: Supabase (Postgres + Edge Functions, TypeScript/Deno). Data: Alpaca (primary OHLC), Finnhub (news/quotes), Polygon/Massive (supplemental).

**ML Stack**: Python 3.11+; scikit-learn, pandas, statsmodels (ARIMA-GARCH); LSTM and ARIMA-GARCH in production ensemble; XGBoost/TabPFN for regime and experiments; Transformer disabled in workflow.

**Frontend**: Swift 5.9+ / SwiftUI macOS app; MVVM; async/await; HTTPS to Supabase Edge Functions; chart data and ML overlay via `/chart` and related endpoints.

**Infrastructure**: Docker (ML images); GitHub Actions (ML forecast, backfill, validation); scheduled ingestion and ML jobs; canary monitoring (divergence, RMSE).

## Architectural Risks & Trade‑offs

* Real‑time multi‑asset ingestion complexity.
* ML overfitting and regime changes.
* Balancing power features with simplicity.
* Scaling backtests and live data pipelines.

## Scope Control

To prevent scope creep and maintain a clear MVP path, features are categorized into:

### Core (MVP – must build)

* Single main chart with indicators
* Watchlist + basic status badges
* News feed for active symbol
* ML forecast overlay + ML report card
* Options ranker (simplified)
* 10-minute data refresh cycle
* Tabs: News / Options / Alerts / Forecasts

### Secondary (Build after MVP if capacity allows)

* Multi-indicator presets
* Custom indicator creation
* Watchlist scanner rules UI
* Expanded options analytics (IV rank, spreads, greeks tables)

### Won't Do (Too complex for now / revisit later)

* Real-time tick streaming
* Multi-chart layouts
* User-defined scripting engine
* Broker trade execution
* Multi-asset correlation maps

### Ideas for Later (Parked for future phases)

* Crypto integration
* Full backtesting engine
* Strategy builder UI
* Heatmaps and sector rotations
* Mobile companion app

## Backend & API Architecture

### 1. High-Level Design

* **Backend Platform**: Supabase (Postgres + Auth + Edge Functions).
* **External Data Providers**:

  * **Alpaca**: primary source for OHLC bars, corporate actions, market calendar, and news (used by Edge Functions and ML backfills).
  * **Finnhub**: quotes and news for stocks (supplemental).
  * **Polygon (Massive API)**: supplemental historical and options data.
* **Client**: macOS SwiftUI app communicates only with Supabase Edge Functions (never directly with providers) to keep API keys secure and centralize logic.
* **ML Engine**: Python pipeline (unified forecast job, evaluation jobs); runs via GitHub Actions or local/scheduled; writes to `ml_forecasts`, `ml_forecasts_intraday`, and `ensemble_validation_metrics` (Phase 7 canary).

Two core data flows:

1. **On-demand reads**: macOS app calls Edge Functions which aggregate from Postgres and external APIs.
2. **Scheduled ingestion + ML updates**: Supabase scheduled jobs/cron invoke ingestion and ML functions every ~10 minutes.

### 2. Data Flow Overview

**On-Demand Path (macOS UI → Edge Function)**

* User changes symbol or timeframe in app.
* App calls `GET /chart` Edge Function.
* Function:

  * Reads latest cached OHLC + forecasts from Postgres.
  * If data is stale or missing, pulls from Finnhub/Massive, updates Postgres, and returns merged response.

**Scheduled Path (Cron → Edge Functions)**

* Every 10 minutes:

  * Ingestion function pulls quotes/ohlc for:

    * Active watchlist symbols
    * Any symbols recently requested
  * Data stored in `ohlc_bars` (per timeframe) and `quotes` tables.
  * ML function reads recent data, produces new forecasts, writes into `ml_forecasts` and `options_ranks` tables.

### 3. Core Database Schema (Supabase Postgres)

Minimum tables for MVP:

* `symbols`

  * `id` (uuid, pk)
  * `ticker` (text, unique)
  * `asset_type` (enum: stock, future, option, crypto)
  * `description` (text)
  * `primary_source` (enum: finnhub, massive)

* `ohlc_bars`

  * `id` (bigint, pk)
  * `symbol_id` (fk → symbols.id)
  * `timeframe` (enum: m15, h1, h4, d1, w1)
  * `ts` (timestamptz)
  * `open`, `high`, `low`, `close` (numeric)
  * `volume` (numeric)
  * `provider` (enum: finnhub, massive)
  * Unique index on (`symbol_id`, `timeframe`, `ts`).

* `quotes`

  * `symbol_id` (fk → symbols.id)
  * `ts` (timestamptz)
  * `last`, `bid`, `ask` (numeric)
  * `day_high`, `day_low` (numeric)
  * `prev_close` (numeric)

* `ml_forecasts`

  * `id` (uuid, pk)
  * `symbol_id` (fk)
  * `horizon` (text, e.g. '1D', '1W')
  * `overall_label` (enum: bullish, neutral, bearish)
  * `confidence` (numeric)
  * `run_at` (timestamptz)
  * `points` (jsonb)  // array of forecast points with ts/value/lower/upper

* `options_ranks`

  * `id` (uuid, pk)
  * `underlying_symbol_id` (fk → symbols.id)
  * `expiry` (date)
  * `strike` (numeric)
  * `side` (enum: call, put)
  * `ml_score` (numeric)
  * `implied_vol` (numeric)
  * `delta`, `gamma` (numeric)
  * `open_interest`, `volume` (integer)
  * `run_at` (timestamptz)

* `watchlists`

  * `id` (uuid, pk)
  * `user_id` (uuid)
  * `name` (text)

* `watchlist_items`

  * `watchlist_id` (fk → watchlists.id)
  * `symbol_id` (fk → symbols.id)
  * Composite primary key (`watchlist_id`, `symbol_id`).

* `scanner_alerts`

  * `id` (uuid, pk)
  * `symbol_id` (fk)
  * `triggered_at` (timestamptz)
  * `condition_label` (text)
  * `severity` (text)

* `news_items` (optional cache)

  * `id` (uuid, pk)
  * `symbol_id` (fk → symbols.id, nullable)
  * `title`, `source`, `url` (text)
  * `published_at` (timestamptz)

### 4. Edge Functions / API Endpoints (MVP)

All endpoints are implemented as Supabase Edge Functions and exposed via HTTPS. The macOS app only talks to these.

#### 4.1 Chart & ML

* **GET `/chart`**

  * Query params: `symbol`, `assetType`, `timeframe`.
  * Returns: OHLC bars, indicator series (optional), ML summary, forecast points.

#### 4.2 Options Ranker

* **GET `/options/rankings`**

  * Query params: `symbol`, optional `expiry`, optional `side`.
  * Returns: ranked option contracts with ML scores and key metrics.

#### 4.3 Watchlist Scanner

* **POST `/scanner/watchlist`**

  * Body: `{ "symbols": ["AAPL", "ES=F", ...] }`.
  * Returns: watchlist items with flags and alerts.

#### 4.4 News

* **GET `/news`**

  * Query params: `symbol` (optional for broad market news).
  * Returns: list of news items.

#### 4.5 Symbols & Search

* **GET `/symbols/search`**

  * Query params: `q` (partial ticker or name).
  * Returns: list of matching symbols.

### 5. Responsibilities

* **Finnhub**

  * Quick OHLC candles and quotes for stocks.
  * Symbol-aware news feed.

* **Massive API**

  * Options data and futures data (REST or WebSocket), aggregated into `options_ranks` and supplemental OHLC.

* **Supabase Postgres**

  * System of record for cached historical data, forecasts, rankings, watchlists, and alerts.

* **Supabase Edge Functions**

  * Authenticated API surface for mac app.
  * Orchestration layer calling Finnhub and Massive, applying business logic, and reading/writing Postgres.

## API Contracts (Draft)

The API contracts are designed from the macOS client perspective. All responses are JSON.

### `/chart` Response Shape (simplified)

```json
{
  "symbol": "AAPL",
  "assetType": "stock",
  "timeframe": "1D",
  "bars": [ /* OHLCBar[] */ ],
  "indicators": [ /* IndicatorSeries[] (optional MVP) */ ],
  "mlSummary": { /* MLSummary with overall_label, confidence, horizons, points */ }
}
```

### `/options/rankings` Response Shape

```json
{
  "symbol": "AAPL",
  "ranks": [ /* OptionContractRank[] */ ]
}
```

### `/scanner/watchlist` Response Shape

```json
{
  "watchlist": [ /* WatchlistItem[] with mlLabel + hasScannerAlert */ ],
  "alerts": [ /* ScannerAlert[] */ ]
}
```

### `/news` Response Shape

```json
{
  "symbol": "AAPL",
  "items": [ /* NewsItem[] */ ]
}
```

### `/symbols/search` Response Shape

```json
{
  "query": "AAP",
  "results": [ /* Symbol[] */ ]
}
```

These contracts are intentionally compact to keep the macOS app simple and to centralize data provider differences on the backend.

## ML Data Flow: Backend → API → Frontend

### 1. Backend ML Processing

* Scheduled Python job reads recent OHLC data from `ohlc_bars` for key symbols (watchlists + recently used) and a given timeframe (e.g., `1D`).
* Job computes features (technical indicators, returns, volatility, etc.) and runs the trained model (e.g., XGBoost/Prophet/NN) to produce:

  * A forecast path: future timestamps and predicted prices, optionally with lower/upper confidence bounds.
  * A classification label for each horizon (e.g., `Bullish`, `Neutral`, `Bearish`) and an overall confidence score.
* For each symbol + horizon (e.g., `1D`, `1W`), the job writes a row into `ml_forecasts` with:

  * `symbol_id`, `horizon`, `overall_label`, `confidence`, `run_at`
  * `points` (jsonb array; see **Canonical Forecast Point Schema** below).

#### Canonical Forecast Point Schema (points JSONB)

Both `ml_forecasts.points` and `ml_forecasts_intraday.points` store an array of **ForecastPoint** objects. One canonical shape serves daily/weekly and intraday (15m/1h/4h_trading) so the lab, ML job, Edge Functions, and SwiftUI share the same contract.

**Required (blueprint minimal; backward compatible):**

| Field       | Type   | Description |
|------------|--------|-------------|
| `ts`       | string | ISO 8601 timestamp (e.g. `2026-02-07T15:30:00Z`) for this forecast step. |
| `value`    | number | Primary plot value; typically equals `ohlc.close`. Used by `/chart` for the forecast line. |

**Optional (roll out in phases; no migration needed):** The lab and recommended persistence typically include `timeframe`, `step`, and `ohlc` for each point so Edge/UI can consume without reshaping.

| Field         | Type   | Description |
|---------------|--------|-------------|
| `lower`       | number | Lower confidence/interval bound for band. |
| `upper`       | number | Upper confidence/interval bound for band. |
| `timeframe`   | string | Bar timeframe: `m15`, `h1`, `4h_trading`, `d1`, `w1`. |
| `step`        | number | 1-based step index in the horizon (e.g. 1 … 5 for 5-day). |
| `ohlc`        | object | `{ open, high, low, close, volume? }` when forecast is OHLC. |
| `indicators`  | object | Recomputed indicators at this step: `rsi_14`, `macd`, `macd_signal`, `macd_hist`, `bb_upper`, `bb_mid`, `bb_lower`, `kdj_k`, `kdj_d`, `kdj_j`, `j_minus_d`, `j_above_d` (optional). |
| `confidence`  | number | Step-level confidence 0–1 (ensemble or model-specific). |
| `components` | object | Per-component point forecast, e.g. `{ "xgboost": 187.9, "arima": 186.9 }` for ensembles. |
| `weights`    | object | Per-component weight at this step, e.g. `{ "xgboost": 0.6, "arima": 0.4 }`. |

**Example (full; all optional fields present):**

```json
{
  "ts": "2026-02-07T15:30:00Z",
  "timeframe": "m15",
  "step": 1,
  "value": 187.52,
  "lower": 185.10,
  "upper": 190.00,
  "ohlc": { "open": 187.4, "high": 188.0, "low": 186.9, "close": 187.52, "volume": 0 },
  "indicators": {
    "rsi_14": 52.1,
    "macd": 0.12,
    "macd_signal": 0.09,
    "macd_hist": 0.03,
    "bb_upper": 191.2,
    "bb_mid": 187.8,
    "bb_lower": 184.4,
    "kdj_k": 61.0,
    "kdj_d": 58.5,
    "kdj_j": 66.0,
    "j_minus_d": 7.5,
    "j_above_d": 1
  },
  "confidence": 0.73,
  "components": { "xgboost": 187.9, "arima": 186.9 },
  "weights": { "xgboost": 0.6, "arima": 0.4 }
}
```

**Example (minimal; blueprint contract only):**

```json
{ "ts": "2026-02-07T21:00:00Z", "value": 187.52 }
```

**Mapping from lab / forecaster:**

- **OHLCStep** (lab `BaseForecaster.predict()` output) has `open`, `high`, `low`, `close`, `volume` and optional indicator keys. Convert to ForecastPoint by: `value = ohlc.close` (or primary series), `ts` from base timestamp + step offset, `ohlc` = step dict subset, `indicators` = step dict subset of indicator keys. Non-ensemble models omit `confidence`, `components`, `weights`; ensemble jobs add them when available.
- **Timeframe** in points: use `m15`, `h1`, `4h_trading`, `d1`, `w1` so intraday and daily/weekly are consistent; Edge/UI can filter or label by `timeframe`.
- **API/timeframe vocabulary:** Bars and chart API use `m15`, `h1`, `h4`, `d1`, `w1` (same as `ohlc_bars.timeframe`). The lab uses `4h_trading` for 4-hour trading session; it is equivalent to `h4`. Edge/backend accept both and normalize to `h4` in responses so the client sees one token end-to-end.
- **Implementation and pipeline order (lab + production L1):** see [FORECAST_PIPELINE_MASTER_PLAN.md](FORECAST_PIPELINE_MASTER_PLAN.md).

### 2. API: Serving Forecasts via `/chart`

* The Supabase Edge Function `GET /chart` is the main integration point for the macOS client.
* For a request `GET /chart?symbol=AAPL&assetType=stock&timeframe=1D`, the function:

  * Resolves `symbol` → `symbol_id`.
  * Queries `ohlc_bars` for recent bars at the requested timeframe.
  * Fetches the latest `ml_forecasts` row(s) for that `symbol_id` and desired horizon(s).
  * Assembles a single JSON payload containing:

    * `bars`: OHLC array for the chart candles.
    * `mlSummary`: forecast horizons, points, and labels (omitted or null for free users).
* The client never calls the ML job directly; it only consumes precomputed forecasts via `/chart`.

### 3. Front-End Consumption & Plotting (SwiftUI)

* The macOS app calls `MarketDataService.fetchChart(...)` which:

  * Performs an HTTP request to `/chart`.
  * Decodes the response into Swift models: `OHLCBar[]` and `MLSummary` (containing `ForecastSeries` and `ForecastPoint` structs).
* `ChartViewModel` stores:

  * `bars` for candle plotting.
  * `mlSummary` for forecast overlay + ML report card.
* `PriceChartView` receives:

  * `bars` → rendered as candlesticks.
  * `forecastPoints` (from `mlSummary.horizons[..].points`) → rendered as a forecast line and optional band above/after current time.
* `MLReportCardView` reads `mlSummary.overallLabel` and `confidence` to display a simple, color-coded summary (Green = Bullish, Gray = Neutral, Red = Bearish) with horizon chips (e.g., `Next 1D`, `Next 1W`).
* No ML computation occurs on the client; it only plots and explains the data produced by the backend.

## Roadmap

**Phase 1 (MVP)**: Multi‑asset data ingestion, charts, basic indicators, screeners, dashboard. ✅

**Phase 2**: ML feature pipeline, baseline predictive models, ML signal UI. ✅

**Phase 3**: Alerts, notification engine, saved strategies. (Partial)

**Phase 4**: Extensibility layer, API for custom strategies, option analytics (IV, greeks). (Partial; options ranker deployed)

**Phase 5**: Crypto expansion, potential broker integration, risk‑management systems. (Later)

**Phase 7 (Feb 2026)**: 2-model ensemble canary (LSTM + ARIMA-GARCH) on AAPL, MSFT, SPY; walk-forward validation; divergence monitoring; GO/NO-GO after 6-day canary. In progress.

## Guiding Principles

Clarity; transparency; modularity; performance; user‑centric design.

---

## Backlog (To Be Prioritized)

* Asset‑class normalization rules
* Option chain data source selection
* Futures tick‑size and multiplier table
* ML model evaluation framework
* UI layout draft
* Backtesting engine spec

## Open Questions

* Data provider selection for futures and options
* Latency requirements for real‑time feeds
* MVP indicator set
* ML model update frequency

## Term-Structure & Forward-Vol (Options Ranker)

### Goal (5-min ranker)
Add term-structure and forward-vol features that:
- Work with a 2-expiry snapshot per symbol (near + ~30D).
- Are numerically stable (no complex vols, no throws).
- Support dual scoring via StrategyIntent: long_premium vs short_premium.

### Decisions (recommended)
- **Ranker modes:** Apply the feature bundle across **all** modes (ENTRY, EXIT, MONITOR). Mode controls how features influence scoring (weights/gating), not whether they exist.
- **Backend scope:** Python batch job computes forward-vol, VRP, skew, and (later) GEX/DEX. Edge/TS remains a data fetch layer: returns chains (`persist=0`) plus cached expiries; no term-structure/forward-vol math in TS.
- **Strategy intent:** Keep StrategyIntent explicit (`long_premium` | `short_premium`) with env default `RANKER_STRATEGY_INTENT`, overridable per run/request.

### Mode behavior (how features affect scores)
- **ENTRY:** Use VRP + term structure primarily inside **Value** (cheap/expensive vol by intent) and as a confidence multiplier (e.g., penalize low-confidence forward-vol). Earnings-jump isolation (when bracketed): boost “sell premium” when event move is large and IV elevated; boost “buy premium” when VRP negative and term structure implies near-term vol cheap.
- **EXIT:** Use VRP + term structure mainly for **risk/decay context** (e.g., short premium + term structure flips to backwardation → tighten exits; long premium + IV collapsing post-event → prioritize profit protection). Earnings module matters most here (IV crush / post-event regime detection).
- **MONITOR:** Use them as **screening context**: fast ranking stability + better comparability across symbols.

### Backend scope (what lives where)
- **Python:** Forward-vol, earnings-jump, MenthorQ math. Iterate quickly; keep logic in one place.
- **Edge/TS:** `/options-chain` retrieval (twice per symbol with `expiration=` + `persist=0`); expiry cache reads/writes (daily refresh job; not in the 5-min loop).

### Time convention (single source of truth)
- Use Unix seconds end-to-end for expiries in the pipeline and cache.
- Convert to years inside ML modules using ACT/365:
  - SECONDS_PER_YEAR = 365 * 24 * 60 * 60
  - T_years = max(0, (exp_ts - now_ts) / SECONDS_PER_YEAR)

### Edge contract (5-min loop)
For each symbol, fetch two chains via Edge (and do NOT persist full chains):
- /options-chain?underlying=SYMBOL&expiration=NEAR_TS&persist=0
- /options-chain?underlying=SYMBOL&expiration=FAR_TS&persist=0

### Supabase: options_expiration_cache (migration)
File: supabase/migrations/20260206000000_options_expiration_cache.sql

```sql
-- Per-symbol cached expiries for 5-min ranker (Unix seconds)
create table if not exists public.options_expiration_cache (
  symbol           text primary key,
  expirations_ts   bigint[] not null default '{}',
  expiry_near_ts   bigint not null,
  expiry_far_ts    bigint not null,
  source           text not null default 'tradier',
  updated_at       timestamptz not null default now(),

  constraint options_expiry_near_positive check (expiry_near_ts > 0),
  constraint options_expiry_far_positive  check (expiry_far_ts > 0),
  constraint options_expiry_order_ok      check (expiry_far_ts >= expiry_near_ts)
);

comment on table public.options_expiration_cache is
  'Per-symbol option expirations cache for 5-min ranker. Stores Unix seconds for direct Edge /options-chain expiration param.';

create index if not exists idx_options_expiration_cache_updated_at
  on public.options_expiration_cache(updated_at);

alter table public.options_expiration_cache enable row level security;
```

### Daily refresh job (outline)
Run once per day (and on symbol-add). Do NOT run inside the 5-min loop.

Inputs:
- symbols: list[str] (ranker universe, ~100)

Steps:
1) For each symbol:
   - Call Tradier get_expirations(symbol) once (returns YYYY-MM-DD strings).
   - Apply selection rule:
     - expiry_near: first expiry >= ref_date
     - expiry_far: first expiry with DTE in [28,45], else closest to 30D; ensure expiry_far != expiry_near if possible.
2) Convert chosen dates to Unix seconds (canonical: midnight UTC).
3) Upsert row:
   - (symbol, expirations_ts[], expiry_near_ts, expiry_far_ts, updated_at)

Fallback:
- If <2 expiries, set both near/far to the only available expiry or mark stale and skip symbol in 5-min job.

### New ML modules / edits (Option A)
- New: ml/src/models/forward_vol.py
  - Build ATM IV per expiry directly from chain (no SVI required for 5-min loop).
  - Forward vol:
    sigma_f = sqrt( max(0, (T2*s2^2 - T1*s1^2) / (T2 - T1)) )
    If raw numerator < 0, clamp to 0 and set low_confidence=True.
  - Term-structure regime naming:
    - contango: front IV < back IV (upward slope, "short cheap")
    - backwardation: front IV > back IV (downward slope, "short rich")

- Extend: ml/src/models/earnings_analyzer.py
  - Add isolate_earnings_jump(...) using bracketing expiries (E1 before, E2 after earnings) + variance subtraction.
  - Keep current heuristic regime scoring as fallback.

- Extend: ml/src/models/options_momentum_ranker.py
  - Add StrategyIntent enum: long_premium | short_premium
  - Default StrategyIntent from env: RANKER_STRATEGY_INTENT
  - Dual-intent mapping inside Value/Greeks (keep 40/35/25):
    - IV rank: long uses (100 - iv_rank), short uses (iv_rank)
    - VRP: positive favors short_premium, negative favors long_premium
    - Term structure: backwardation favors long_premium, contango favors short_premium

- Extend: ml/src/options_ranking_job.py
  - Fetch two expiries via Edge (persist=0), merge, compute feature bundle, pass into ranker kwargs.
  - Persist only filtered feature snapshots (avoid writing full chains each cycle).

### Defaults and config
- `RANKER_STRATEGY_INTENT` default: `long_premium`.
- `TERMSTRUCT_LOW_CONFIDENCE_PENALTY`: subtract X points or multiply Value score by 0.9 when forward-vol is clamped/dirty so it doesn’t dominate ranks.
- GEX/DEX: context-only initially (or behind a flag) because with only 2 expiries you’ll be computing partial-surface exposures.

### Env vars
- RANKER_STRATEGY_INTENT: long_premium | short_premium (default: long_premium)
- (Optional) TERMSTRUCT_MIN_OI / TERMSTRUCT_MIN_VOL for ATM IV liquidity filters
- (Optional) TERMSTRUCT_LOW_CONFIDENCE_PENALTY for clamped forward-vol

### Clarifications needed (options ranker)
- **UI:** Should the app show two separate ranked lists (“Long premium” and “Short premium”) every refresh, or will the UI toggle intent and re-rank on demand?

---

This document is iteratively updated as we refine the architecture and define the build sequence. Last substantive update: February 2026 (Phase 7 canary, Alpaca primary, 2-model ensemble).

## Front-End UX Blueprint (Main Dashboard)

### 1. Primary Use Cases

* **Quick Market Read**: See latest price action, key indicators, and sentiment for a selected symbol across stocks, futures, and options.
* **Technicals-First Analysis**: Power users customize indicators and timeframes to match their process (scalping, day trading, swing, position).
* **Watchlist Monitoring**: Track a curated list of tickers and get visual cues when something demands attention.
* **News & Event Awareness**: Surface relevant headlines and upcoming events that might affect symbols on the chart or in the watchlist.
* **Options & ML Insights (Upgraded)**: View ranked options strikes, ML-based forecasts, and scanner results that flag favorable setups.

### 2. Main Dashboard Layout (Desktop)

Based on the sketch (page 1 of the uploaded design), the main dashboard is a **three-zone layout**: top control bar, central chart stack, right insights column. fileciteturn0file0

1. **Top Control Bar**

   * Ticker input/search (e.g., `AAPL`), with asset-type tagging (Stock / Future / Option / Crypto-later).
   * Timeframe selector: `15M`, `1H`, `4H`, `D`, `W` (extensible to custom presets).
   * Indicator preset dropdown: select saved indicator profiles (e.g., "Scalping", "Swing", "VWAP + Volume").
   * Optional controls: layout selector (single vs multi-chart), compare ticker, theme toggle.

2. **Central Chart Stack**

   * **Price Chart Panel** (top, dominant area)

     * Candlestick/ohlc chart with overlays (MA, EMA, VWAP, Bollinger, etc.).
     * Dynamic y-axis on the right; current price clearly highlighted.
     * Crosshair with tooltip showing OHLC, volume, indicator values.
   * **Indicator Panels** (stacked below price chart)

     * Slot 1: selected oscillator/indicator (e.g., RSI, MACD).
     * Slot 2: second indicator (e.g., Stochastic, ATR, Volume profile).
     * Each slot is configurable via an indicator picker dialog.
     * For advanced users, allow additional slots or split-pane mode later.

3. **Right Insights Column**

   * **Top: Watchlist Card**

     * List of tickers with: last price, % change, basic sentiment badge (bullish/neutral/bearish), and ML signal badge for upgraded users.
     * Clicking a ticker updates the main chart + indicator stack.
     * Star/checkbox to add/remove from primary watchlist.
   * **Bottom: Tabbed Insights Card**
     Tabs:

     * **News**: Recent headlines for active symbol + global market movers.
     * **Options Ranker (Upgraded)**: Ranked call/put strikes with ML score, IV, delta, volume/OI; quick filters for expiries.
     * **Alerts / Scanner**: Shows conditions that have fired (e.g., "RSI crossed 30", "MACD bull cross", "Option ML score > threshold").
     * **Forecasts (Upgraded)**: Short-term and mid-term price forecasts with confidence bands and explanation snippets.

### 3. User Tiers & Gating

* **Core (Free)**

  * Full charting, basic indicators, custom layouts.
  * Watchlist, news, manual alerts based on technicals.
* **Upgraded**

  * ML-powered **Options Ranker** with ranked contracts for current symbol.
  * **Forecasts panel** with price paths, probability ranges, and scenario labels.
  * **ML Scanner** that monitors the user’s watchlist and flags when a symbol becomes favorable.

UI behavior:

* ML-only features appear as disabled/teaser state for non-upgraded users with clear value messaging.

### 4. Core Front-End Components (SwiftUI-level)

High-level component breakdown:

* `MainDashboardView`: shell providing header (top control bar), main content (chart + indicators), and right sidebar (watchlist + insights).
* `TopControlBarView`: ticker search, timeframe selector, indicator preset selector, refresh control.
* `ChartAreaView`:

  * `PriceChartView` (integrated with a charting library / custom drawing and fed OHLCV + forecast series).
  * `IndicatorPanelView` (reusable; accepts indicator config and underlying data).
* `RightSidebarView`:

  * `WatchlistView`
  * `InsightsTabsView` with `NewsTabView`, `OptionsRankerTabView`, `AlertsTabView`, `ForecastsTabView`.

Core ViewModels / State Objects:

* `SymbolViewModel` — active symbol, asset type, resolved metadata.
* `ChartViewModel` — OHLCV + overlays + ML forecast series, updated on a ~10-minute cadence.
* `IndicatorsViewModel` — selected indicators, parameters, presets per user.
* `WatchlistViewModel` — CRUD for watchlist, watchlist-level scanner state.
* `InsightsViewModel` — news feed, options rankings, ML forecast “report card” data.

Service layer (used by ViewModels):

* `MarketDataService` — fetches quotes and OHLCV.
* `MLForecastService` — fetches forecast paths + bullish/neutral/bearish labels.
* `OptionsRankerService` — fetches ranked option contracts.
* `NewsService` — fetches symbol-aware news.
* `ScannerService` — evaluates and returns scanner/alert hits.

State flows through MVVM: views observe ViewModels via `@StateObject` / `@ObservedObject`, ViewModels call services with async/await, and publish updates back to the UI.

### 5. Interaction Flows

* **Change Ticker**: User selects a ticker from watchlist or search → chart data reloads → indicators recompute → options/news/ML panels refetch.
* **Change Timeframe**: Updates chart resolution and any timeframe-dependent indicators; ML forecasts may show horizon-specific views.
* **Manage Indicators**: Clicking indicator slot opens selector → user chooses indicator + params → config saved to profile/preset.
* **Set Alert/Scanner Rule**: From chart or watchlist item → opens rule builder (e.g., "RSI < 30", "ML score > 0.8") → saved to backend, visual badge on symbol.
* **Review Options Ranker** (Upgraded): User opens Options tab → sees ranked calls/puts with scores, can filter by expiry/side → click-through opens full chain view (future).

### 6. Responsive Design Notes

* **Desktop-first** layout, as sketched, is the primary target.
* **Tablet**: stack right column below chart, maintain tabs for insights.
* **Mobile**: single-column; top controls collapse into a sticky header; chart, then watchlist, then a carousel of insights (News, Options, Alerts, Forecasts).

### 7. Next Front-End Decisions

* Choose charting library and state-management approach.
* Define the exact MVP indicator set and which are overlays vs sub-panels.
* Decide how aggressively to expose ML in the core dashboard vs a dedicated "ML Insights" view.
