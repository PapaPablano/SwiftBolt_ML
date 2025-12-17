# Stock Analysis Platform — Implementation Checklist

This document turns the **Stock Analysis Blueprint** into an ordered, phase-based implementation plan. It is written so that an AI agent (or human lead) can:

* Work phase-by-phase.
* Check each item off only when completed and verified.
* Avoid scope creep by deferring non-MVP features to later phases.

Status notation:

* `[ ]` Not started
* `[-]` In progress / partially done
* `[x]` Completed & verified

---

## Phase 0 — Project Setup & Foundations

**Goal:** Create a clean, reproducible workspace and wire the project to the existing architecture blueprint.

### 0.1. Repo & Project Scaffolding

* [x] Create mono-repo or multi-repo structure (decide):

  * [x] `backend/` (Supabase / Edge Functions / ML jobs)
  * [x] `client-macos/` (SwiftUI app)
  * [x] `infra/` (optional: IaC, deployment templates)
* [x] Add the **Blueprint** and this **Implementation Checklist** to the repo (`docs/architecture.md`, `docs/implementation-checklist.md`).
* [x] Set up basic CONTRIBUTING and coding standards (Swift/TS/Python).

### 0.2. Supabase Project & Environments

* [x] Create Supabase project (dev environment).
* [x] Configure database connection and service role keys for backend.
* [ ] Define environment strategy:

  * [x] `dev` Supabase
  * [ ] `prod` Supabase (planned)
* [x] Document environment variables for:

  * [x] Supabase keys (service key, anon key)
  * [x] Finnhub API key (`FINNHUB_API_KEY`, `FINNHUB_BASE_URL`, `FINNHUB_MAX_RPS`, `FINNHUB_MAX_RPM`)
  * [x] Massive API key (`MASSIVE_API_KEY`, `MASSIVE_BASE_URL`, `MASSIVE_MAX_RPM`)
  * [x] Cache TTL overrides (`CACHE_TTL_QUOTE`, `CACHE_TTL_BARS`, `CACHE_TTL_NEWS`, etc.)

### 0.3. Core Tooling & CI Skeleton

* [x] Initialize Git and add `.gitignore` for Swift, Node, Python.
* [ ] Add basic CI skeleton (even if only lint/build):

  * [ ] Backend: TypeScript lint, Edge Function build check.
  * [ ] Client: Swift build (xcodebuild) for `Debug`.
  * [ ] ML: Python lint (ruff/flake8) and unit tests.
* [ ] Add pre-commit hooks or simple lint scripts.

---

## Phase 1 — Backend Core: Schema & Basic Data Path

**Goal:** Stand up Supabase schema and minimal Edge Functions so the macOS app can load real OHLC data and symbols.

### 1.1. Database Schema (Core Tables)

* [x] Create migration for `symbols` table.
* [x] Create migration for `ohlc_bars` table.
* [x] Create migration for `quotes` table.
* [x] Verify indexes (e.g., `symbol_id + timeframe + ts` for `ohlc_bars`).

### 1.2. Symbol Management

* [x] Implement basic seeding or loader for `symbols` from Finnhub/Massive.
  * [x] Created `backend/scripts/seed-symbols.ts` (Deno) with 20 sample symbols.
  * [x] Created `backend/scripts/seed-symbols.sql` (SQL) for direct DB seeding.
* [x] Add `GET /symbols/search` Edge Function:

  * [x] Input: `q` query string.
  * [x] Query `symbols` with `ILIKE`.
  * [x] Return JSON array of `{ ticker, assetType, description }`.
  * [x] Created shared utilities: `_shared/cors.ts`, `_shared/supabase-client.ts`.
* [x] Test: Search for `AAPL`, verify response.

### 1.3. OHLC Data Ingestion (On-Demand)

* [x] Implement a backend helper to fetch candles from Finnhub/Massive.
  * [x] Created `_shared/massive-client.ts` for Polygon.io API.
  * [x] Created `_shared/finnhub-client.ts` for future quote functionality.
  * [x] **Ensure calls go through provider router + rate limiter** (see `api_handling.md`) so quotas are respected.
    * [x] Implemented `DataProviderAbstraction` interface with unified types
    * [x] Implemented `TokenBucketRateLimiter` with dual buckets (per-second + per-minute)
    * [x] Implemented `MemoryCache` with TTL and tag-based invalidation
    * [x] Created `FinnhubClient` and `MassiveClient` implementing abstraction
    * [x] Created `ProviderRouter` with health tracking and automatic failover
    * [x] Updated `/chart` and `/news` Edge Functions to use ProviderRouter
* [x] Implement initial on-demand ingestion function (internal helper):

  * [x] Given `symbol_id` + `timeframe`, pull and store OHLC bars.
  * [x] Upsert into `ohlc_bars` with proper uniqueness constraints.
* [x] Add `GET /chart` Edge Function (v1: **no ML yet**):

  * [x] Input: `symbol`, `assetType`, `timeframe`.
  * [x] Resolve `symbol` → `symbol_id`.
  * [x] Read `ohlc_bars`; if insufficient/stale, call ingestion helper.
  * [x] Return JSON with `bars` only.
* [x] Test: Call `/chart` for `AAPL` and verify candles.

### 1.4. News Endpoint (Optional Early Win)

* [x] Add `GET /news` Edge Function:

  * [x] Input: `symbol` (optional).
  * [x] Fetch latest news from Finnhub.
  * [x] Route via provider router + rate limiter (see `api_handling.md`).
  * [x] (Optional) Store in `news_items` cache.
  * [x] Return normalized JSON items.
* [x] Test: Call `/news?symbol=AAPL` and verify response.

### 1.5. Provider Migration to Live Ingestion

* [x] **Migrate from seed-based to provider-driven data architecture:**
  * [x] Implemented unified `DataProviderAbstraction` layer (see `docs/MIGRATION_SUMMARY.md`)
  * [x] Integrated rate limiting and caching across all provider calls
  * [x] Updated `/chart` and `/news` endpoints to use `ProviderRouter`
  * [ ] Build backfill ingestion helper for warming DB with historical OHLC
  * [ ] Remove direct seed script dependencies (keep DB seeding for bootstrap only)
  * [ ] Add provider-backed symbol discovery (populate `symbols` via provider APIs)

---

## Phase 2 — macOS Client Skeleton (SwiftUI)

**Goal:** Create the macOS app structure and wire it to the Phase 1 backend for basic chart + symbol search.

### 2.1. Project Setup

* [x] Create `client-macos` Xcode project (macOS app, SwiftUI lifecycle).
* [x] Define top-level folders:

  * [x] `Models/`
  * [x] `Services/`
  * [x] `ViewModels/`
  * [x] `Views/`
* [x] Add basic app entry: `SwiftBoltMLApp`.

### 2.2. Models & Networking

* [x] Implement `Symbol`, `OHLCBar`, and other core models matching `/chart` & `/symbols/search` payloads.
  * [x] Fixed camelCase vs snake_case key mapping for backend responses
  * [x] Fixed ISO8601 date parsing to handle both fractional seconds and timezone formats
* [x] Implement `ApiClient` or `NetworkClient` using `URLSession` + async/await.
* [x] Implement `MarketDataService` with:

  * [x] `fetchChart(symbol:assetType:timeframe:)`.
  * [x] `searchSymbols(query:)`.
  * [x] `fetchNews(symbol:)`.
* [x] Add simple error handling and logging for failed requests.
* [x] Backend calls use the unified ProviderRouter (rate limiter + caching handled server-side).

### 2.3. ViewModels

* [x] Implement `SymbolSearchViewModel`:

  * [x] Holds search query and results.
  * [x] Exposes symbol search functionality.
* [x] Implement `AppViewModel`:

  * [x] Holds `selectedSymbol`, `assetType`, `timeframe`.
  * [x] Coordinates chart and news data loading.
* [x] Implement `ChartViewModel` (v1):

  * [x] Holds `[OHLCBar]` and loading state.
  * [x] `loadChart()` calls `APIClient.fetchChart`.
  * [x] Supports multiple timeframes (m15, h1, h4, d1, w1).
* [x] Implement `NewsViewModel`:

  * [x] Holds news items and loading state.
  * [x] `loadNews()` calls `APIClient.fetchNews`.

### 2.4. Views (Skeleton Layout)

* [x] Implement `ContentView` (MainDashboardView) with:

  * [x] `SidebarView` with symbol search.
  * [x] `ChartView` rendering OHLC data.
  * [x] `NewsListView` displaying news items.
  * [x] Navigation split view layout.
* [x] Wire `AppViewModel` + `ChartViewModel` + `NewsViewModel` using `@StateObject`/`@EnvironmentObject`.
* [x] Confirm: Search symbol → select → triggers chart fetch → displays data ✅
  * [x] Tested with AAPL (70 bars loaded successfully)
  * [x] Tested symbol search with NVDA and CRWD (both found and clickable)
  * [x] News loading functional
  * [x] Fixed SwiftUI observation issues with nested ObservableObjects
  * [x] Implemented objectWillChange relay pattern for all view models
  * [x] Search results now properly display and are interactive
  * [x] Symbol selection triggers chart and news refresh correctly

---

## Phase 3 — Charting & Basic Technicals

**Goal:** Replace placeholder chart with real price chart and basic indicators.

### 3.1. Chart Rendering

* [x] Select charting approach (native SwiftUI drawing vs 3rd-party).
  * [x] Selected native SwiftUI Charts framework with custom drawing
* [x] Implement `PriceChartView`:

  * [x] Render candlesticks from `[OHLCBar]`.
  * [x] Support x-axis as time, y-axis as price.
  * [x] Add crosshair + basic tooltip (if feasible).
  * [x] Created `AdvancedChartView` with interactive crosshair and tooltip overlay

### 3.2. Indicators (Client or Backend)

* [x] Decide location for indicator computation:

  * [x] Start with **client-side** for simple indicators (SMA, EMA, RSI)
  * [x] Created `TechnicalIndicators.swift` utility class
* [x] Implement minimal indicator set for MVP:

  * [x] SMA/EMA overlays (SMA 20/50/200, EMA 9/21).
  * [x] RSI as a panel indicator.
  * [x] Volume bars visualization
  * [x] VWAP and Bollinger Bands calculations (available for future use)
* [x] Implement `IndicatorPanelView` for 1–2 panel indicators.
  * [x] Created multi-panel layout with price chart, RSI panel, and volume bars
* [x] Wire indicator visibility controls into `TopControlBarView` (even if minimal toggles).
  * [x] Added `IndicatorToggleMenu` in ChartView with toggles for all indicators

### 3.3. Watchlist (Static / Local)

* [x] Implement local-only `WatchlistViewModel`.
  * [x] Created with UserDefaults persistence
  * [x] Supports add, remove, toggle, and isWatched operations
* [x] Implement `WatchlistView` in the right sidebar.
  * [x] Created with empty state, symbol rows, and selection highlighting
  * [x] Integrated into ContentView sidebar between search and navigation
* [x] Allow add/remove symbols to/from watchlist (persist to local storage initially).
  * [x] Star button in search results to add to watchlist
  * [x] Remove button in watchlist view (appears on hover)

---

## Phase 4 — Backend ML Pipeline & Forecast Storage

**Goal:** Build the backend ML pipeline that produces forecasts and stores them for `/chart` to consume.

### 4.1. ML Job Skeleton

* [x] Create `ml/` folder with Python environment.
* [x] Define data access layer to Supabase Postgres:

  * [x] Use Supabase REST API (service role) to query `ohlc_bars` via `src/data/supabase_db.py`.
* [x] Write script to:

  * [x] Load recent OHLC data for a set of symbols.
  * [x] Build features (basic indicators + returns) in `src/features/technical_indicators.py`.

### 4.2. Baseline Model & Forecast Generation

* [x] Choose and implement a **baseline** forecast model (Random Forest classifier).
* [x] For each symbol:

  * [x] Produce forecast points for horizon (e.g., `1D` / `1W`).
  * [x] Compute a simple label (bullish/neutral/bearish) and confidence.
* [x] Implement write-back to `ml_forecasts`:

  * [x] Insert or upsert `symbol_id`, `horizon`, `overall_label`, `confidence`, `run_at`, `points` via `SupabaseDatabase.upsert_forecast()`.

### 4.3. Scheduling & Ops

* [ ] Configure a 10-minute schedule to run the ML scoring job (cron/scheduler).
* [x] Add logging and basic error alerts (Python logging configured).
* [x] Confirm forecasts exist in `ml_forecasts` for test symbols (AAPL forecasts verified).

---

## Phase 5 — Integrating ML with `/chart` and SwiftUI

**Goal:** Pipe forecasts into the `/chart` API and render them as overlay + report card in the macOS app.

### 5.1. Backend: `/chart` with ML

* [x] Update `/chart` Edge Function to:

  * [x] Query `ml_forecasts` for latest row(s) for `symbol_id`.
  * [x] Transform DB row(s) into `mlSummary` JSON structure:

    * Overall label + confidence.
    * `horizons[]` each with series of forecast points.
  * [x] Gracefully return null `mlSummary` when forecasts unavailable (plan gating deferred).
* [x] Verified `/chart` returns `mlSummary` for symbols with forecasts (tested with AAPL).

### 5.2. Client: Models & ViewModel

* [x] Add `ForecastPoint`, `ForecastSeries`, and `MLSummary` Swift models in `ChartResponse.swift`.
* [x] Extend `ChartResponse` to include optional `mlSummary` field.
* [x] Update `MarketDataService.fetchChart` to decode `mlSummary` (automatic via Codable).
* [x] Update `ChartViewModel` to store `mlSummary` and pass to views:

  * [x] `forecastSeries` for chart overlay.
  * [x] `overallLabel` and `confidence` for report card.

### 5.3. Client: Chart & Report Card UI

* [x] Update `AdvancedChartView` to draw:

  * [x] Candle series from `bars`.
  * [x] Forecast line series using `ForecastPoint.value` with dashed style.
  * [x] Confidence bands using `lower`/`upper` bounds with shaded area.
* [x] Implement `MLReportCard`:

  * [x] Green / Orange / Red label based on `overallLabel` (bullish/neutral/bearish).
  * [x] Confidence as percentage bar with color matching.
  * [x] Horizon chips for each forecast series.
  * [x] Brain icon header with purple accent.
* [x] Wire `MLReportCard` into `ChartView` above the chart when `mlSummary` available.

---

## Phase 6 — Options Ranker & Scanner (Post-MVP)

**Goal:** Add ranked options and basic scanner support, gated to upgraded plan.

### 6.1. Options Data & `options_ranks`

* [x] Options chain data available via `/options-chain` Edge Function (Yahoo Finance).
* [x] Enhanced `options_ranks` schema with ML scoring columns.
  * [x] Added contract_symbol, theta, vega, rho, bid/ask/mark, last_price
  * [x] Created indexes for performant queries (ml_score DESC, run_at, underlying+score)
* [x] Implemented ML scoring/ranking for options in Python:
  * [x] Created `OptionsRanker` class with multi-factor scoring model
  * [x] Scoring factors: moneyness, IV rank, liquidity, delta/theta, momentum
  * [x] Weighted composite ml_score (0-1 range)
  * [x] Created `options_ranking_job.py` for batch processing

### 6.2. `/options/rankings` Endpoint

* [x] Implemented Edge Function `GET /options-rankings`:
  * [x] Query params: symbol, expiry (optional), side (optional), limit (default 50)
  * [x] Returns ML-ranked contracts sorted by ml_score descending
  * [x] Deployed to Supabase production
* [ ] Apply plan gating (deferred - currently open for MVP testing).

### 6.3. Client Integration

* [x] Implemented Swift models:
  * [x] `OptionsRankingResponse` with `OptionRank` struct
  * [x] ML score helpers (color coding, percentage, labels)
  * [x] Expiry date parsing and DTE calculation
* [x] Implement API client methods for `/options-rankings` and `/scanner-watchlist`.
* [x] Integrate ranking display into `OptionsChainView` with dedicated ranker tab.
  * [x] Created `OptionsRankerViewModel` for state management
  * [x] Created `OptionsRankerView` with ML score filtering and sorting
  * [x] Added tabbed interface in `OptionsChainView` (ML Ranker / Full Chain)
  * [x] Implemented rich UI with score badges, filters, and contract details

### 6.4. Watchlist Scanner

* [x] Enhanced `scanner_alerts` table:
  * [x] Added condition_type, details (JSONB), is_read, expires_at
  * [x] Created indexes for efficient queries
* [x] Implemented Edge Function `POST /scanner-watchlist`:
  * [x] Accepts array of symbols from user's watchlist
  * [x] Fetches ML forecasts for each symbol
  * [x] Aggregates alerts (last 7 days) with unread counts
  * [x] Returns watchlist items with price data and alert badges
  * [x] Deployed to Supabase production
* [x] Implemented Swift models:
  * [x] `ScannerWatchlistResponse` with `WatchlistItem` and `ScannerAlert`
  * [x] Alert severity and condition type enums
  * [x] Color helpers for badges and icons
  * [x] `AnyCodable` for flexible JSON details
* [x] Implement scanner integration in Swift client.
  * [x] Created `AnalysisViewModel` for alert management
  * [x] Created comprehensive `AnalysisView` with three sections:
    * [x] Active Alerts section with severity-based filtering
    * [x] ML Forecast Breakdown with horizon details
    * [x] Technical Summary with RSI, volume, and MA analysis
  * [x] Integrated `AnalysisView` into main tab navigation

### 6.5. Enhanced ML Report Card

* [x] Redesigned `MLReportCard` for improved UX:
  * [x] Compact horizontal layout (default collapsed state)
  * [x] Inline metrics showing forecast and confidence at a glance
  * [x] Expandable details on click with smooth animation
  * [x] Confidence breakdown showing contributing factors
  * [x] Horizon detail rows with target prices and ranges
  * [x] Color-coded status indicators throughout

### 6.6. Job Queue System for Rankings

* [x] Implemented database-backed job queue:
  * [x] Created `ranking_jobs` table with status tracking (pending/running/completed/failed)
  * [x] Added priority queue support with retry logic
  * [x] Created database functions: `get_next_ranking_job()`, `complete_ranking_job()`, `fail_ranking_job()`
  * [x] Implemented atomic job locking with `FOR UPDATE SKIP LOCKED`
* [x] Created `trigger-ranking-job` Edge Function:
  * [x] Queues ranking jobs in database instead of direct execution
  * [x] Prevents duplicate jobs within 5-minute window
  * [x] Returns job ID and estimated completion time
  * [x] Calculates queue position for user feedback
* [x] Created Python job worker (`ml/src/ranking_job_worker.py`):
  * [x] Polls queue for pending jobs
  * [x] Executes `options_ranking_job.py` as subprocess
  * [x] Handles job completion and failure with retry logic
  * [x] Supports watch mode for continuous processing (--watch flag)
  * [x] Tested end-to-end with MSFT, CRWD, AAPL
* [x] Updated Swift client:
  * [x] Added `triggerRankingJob()` API method
  * [x] Updated `OptionsRankerViewModel` to use real job queue
  * [x] Added loading state with estimated wait time
  * [x] Auto-refresh rankings after job completion

### 6.7. Multi-Expiry Comparison View

* [x] Fixed OHLC data persistence:
  * [x] Created `backfill_ohlc.py` script for historical data
  * [x] Fixed `/chart` Edge Function to auto-persist fetched data
  * [x] Fixed database constraint error (provider enum)
  * [x] Tested with CRWD, NVDA (70 bars persisted per symbol)
* [x] Enhanced symbol database:
  * [x] Added missing popular symbols (PLTR, AMD, NFLX, DIS)
  * [x] Verified symbol search functionality
* [x] Implemented multi-expiry comparison UI:
  * [x] Created `OptionsRankerExpiryView.swift`
  * [x] Grouped rankings by expiration date with pinned headers
  * [x] Shows top 10 contracts per expiration
  * [x] Compact display with ML score, strike, side, mark, IV, delta, volume
  * [x] Added segmented control to toggle between "All Contracts" and "By Expiry" views
  * [x] Maintained filter compatibility (side, min score) in both views
  * [x] Added file to Xcode project (project.pbxproj updated)

### 6.8. Documentation

* [x] Created comprehensive documentation:
  * [x] `FIXES_SUMMARY.md` - Detailed guide for multi-expiry view and symbol fixes
  * [x] `RANKING_JOB_SYSTEM.md` - Complete architecture of job queue system
  * [x] `OPTIONS_RANKER_SETUP.md` - Setup and testing guide
  * [x] `QUICKSTART_RANKING_JOBS.md` - Quick reference for job system
  * [x] `XCODE_PROJECT_UPDATED.md` - Confirmation of Xcode project changes

---

## Phase 7 — Hardening, Observability & Polish

**Goal:** Make the system robust enough for real usage.

### 7.1. Error Handling & Degradation

* [ ] Define how `/chart` behaves when external providers fail:

  * [ ] Return last-known data with `stale: true` flag.
* [ ] Ensure client shows appropriate UI for stale/failed data.

### 7.2. Monitoring & Logging

* [ ] Centralize logging for Edge Functions.
* [ ] Add basic metrics (errors, latency, job success/failure) plus per-provider usage and 429 rate-limit events (see `api_handling.md`).

### 7.3. Performance & UX Polish

* [ ] Verify 10-minute cadence is stable.
* [ ] Optimize heavy queries (indexes, limit ranges).
* [ ] Tighten layout and usability on macOS.

---

## Agent Instructions (How an AI Oversees This Checklist)

An AI agent guiding implementation should:

1. **Respect Phases:**

   * Do not start work in a later phase until all prerequisites in earlier phases have `[x]` or an explicit, documented reason to skip.

2. **Enforce MVP Scope:**

   * Only implement items labeled `[Core (MVP)]` in early passes.
   * Move any new ideas to a separate "Ideas for Later" list instead of expanding active phases.

3. **Verify Each Task:**

   * For each checklist item:

     * Confirm code exists.
     * Confirm basic tests or manual checks pass.
     * Only then change `[ ]` → `[x]`.

4. **Keep Docs In Sync:**

   * When behavior or APIs change, update:

     * Blueprint (architecture).
     * This implementation checklist.

5. **Flag Ambiguities:**

   * If a task is ambiguous (e.g., "optimize performance"), the agent should:

     * Suggest a more precise sub-checklist.
     * Ask for clarification before marking complete.

This turns the blueprint into an executable plan that an AI or human can follow step-by-step, ensuring that nothing critical is skipped and that scope remains under control.
