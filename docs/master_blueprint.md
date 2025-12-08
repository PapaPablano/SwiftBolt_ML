# Stock Analysis Platform — High‑Level Blueprint (Working Draft)

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

## Technology Stack (Draft)

**Backend**: Python for ingestion/ML; Postgres or TimescaleDB; FastAPI for API layer; WebSockets for live feeds.

**ML Stack**: scikit‑learn, XGBoost, Prophet or neural nets for time-series forecasting.

**Frontend**: Swift + SwiftUI macOS app; financial charting component; MVVM architecture using ObservableObject/State and async/await for networking; server interactions via HTTPS APIs refreshed on a 10-minute cadence.

**Infrastructure**: Docker; CI/CD; nightly data refresh; scheduled ML retraining.

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

  * **Finnhub**: quotes, OHLC candles, and news for stocks (and later forex/crypto).
  * **Massive API**: high-quality historical and real-time data for stocks, options, indices, currencies, and futures.
* **Client**: macOS SwiftUI app communicates only with Supabase Edge Functions (never directly with Finnhub/Massive) to keep API keys secure and centralize logic.
* **ML Engine**: runs server-side (could be a separate service or scheduled function) and writes forecast outputs into `ml_forecasts` table in Postgres.

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
  * `points` (jsonb array of `{ timestamp, value, lower?, upper? }`).

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

**Phase 1 (MVP)**: Multi‑asset data ingestion, charts, basic indicators, screeners, dashboard.

**Phase 2**: ML feature pipeline, baseline predictive models, ML signal UI.

**Phase 3**: Alerts, notification engine, saved strategies.

**Phase 4**: Extensibility layer, API for custom strategies, option analytics (IV, greeks).

**Phase 5**: Crypto expansion, potential broker integration, risk‑management systems.

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

---

This document will be iteratively updated as we refine the architecture and define the build sequence.

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
