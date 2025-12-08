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
  * [ ] Finnhub API key
  * [ ] Massive API key

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

* [ ] Implement a backend helper to fetch candles from Finnhub/Massive.
* [ ] Implement initial on-demand ingestion function (internal helper):

  * [ ] Given `symbol_id` + `timeframe`, pull and store OHLC bars.
  * [ ] Upsert into `ohlc_bars` with proper uniqueness constraints.
* [ ] Add `GET /chart` Edge Function (v1: **no ML yet**):

  * [ ] Input: `symbol`, `assetType`, `timeframe`.
  * [ ] Resolve `symbol` → `symbol_id`.
  * [ ] Read `ohlc_bars`; if insufficient/stale, call ingestion helper.
  * [ ] Return JSON with `bars` only.
* [ ] Test: Call `/chart` for `AAPL` and verify candles.

### 1.4. News Endpoint (Optional Early Win)

* [ ] Add `GET /news` Edge Function:

  * [ ] Input: `symbol` (optional).
  * [ ] Fetch latest news from Finnhub.
  * [ ] (Optional) Store in `news_items` cache.
  * [ ] Return normalized JSON items.
* [ ] Test: Call `/news?symbol=AAPL` and verify response.

---

## Phase 2 — macOS Client Skeleton (SwiftUI)

**Goal:** Create the macOS app structure and wire it to the Phase 1 backend for basic chart + symbol search.

### 2.1. Project Setup

* [ ] Create `client-macos` Xcode project (macOS app, SwiftUI lifecycle).
* [ ] Define top-level folders:

  * [ ] `Models/`
  * [ ] `Services/`
  * [ ] `ViewModels/`
  * [ ] `Views/`
* [ ] Add basic app entry: `StockAnalysisApp`.

### 2.2. Models & Networking

* [ ] Implement `Symbol`, `OHLCBar`, and other core models matching `/chart` & `/symbols/search` payloads.
* [ ] Implement `ApiClient` or `NetworkClient` using `URLSession` + async/await.
* [ ] Implement `MarketDataService` with:

  * [ ] `fetchChart(symbol:assetType:timeframe:)`.
  * [ ] `searchSymbols(query:)`.
* [ ] Add simple error handling and logging for failed requests.

### 2.3. ViewModels

* [ ] Implement `SymbolViewModel`:

  * [ ] Holds `symbol`, `assetType`, `timeframe`.
  * [ ] Exposes symbol search and selection.
* [ ] Implement `ChartViewModel` (v1):

  * [ ] Holds `[OHLCBar]`.
  * [ ] `load()` calls `MarketDataService.fetchChart`.
  * [ ] Integrates with a 10-minute refresh trigger (can be stubbed first).

### 2.4. Views (Skeleton Layout)

* [ ] Implement `MainDashboardView` with:

  * [ ] Placeholder `TopControlBarView`.
  * [ ] `ChartAreaView` with dummy chart placeholder.
  * [ ] `RightSidebarView` placeholder.
* [ ] Wire `SymbolViewModel` + `ChartViewModel` into `MainDashboardView` using `@StateObject`.
* [ ] Confirm: Search symbol → select → triggers chart fetch → displays data (even if chart is basic for now).

---

## Phase 3 — Charting & Basic Technicals

**Goal:** Replace placeholder chart with real price chart and basic indicators.

### 3.1. Chart Rendering

* [ ] Select charting approach (native SwiftUI drawing vs 3rd-party).
* [ ] Implement `PriceChartView`:

  * [ ] Render candlesticks from `[OHLCBar]`.
  * [ ] Support x-axis as time, y-axis as price.
  * [ ] Add crosshair + basic tooltip (if feasible).

### 3.2. Indicators (Client or Backend)

* [ ] Decide location for indicator computation:

  * [ ] Start with **client-side** for simple indicators (SMA, EMA, RSI) *or*
  * [ ] Add indicator arrays in `/chart` response.
* [ ] Implement minimal indicator set for MVP:

  * [ ] SMA/EMA overlays.
  * [ ] RSI as a panel indicator.
* [ ] Implement `IndicatorPanelView` for 1–2 panel indicators.
* [ ] Wire indicator visibility controls into `TopControlBarView` (even if minimal toggles).

### 3.3. Watchlist (Static / Local)

* [ ] Implement local-only `WatchlistViewModel`.
* [ ] Implement `WatchlistView` in the right sidebar.
* [ ] Allow add/remove symbols to/from watchlist (persist to local storage initially).

---

## Phase 4 — Backend ML Pipeline & Forecast Storage

**Goal:** Build the backend ML pipeline that produces forecasts and stores them for `/chart` to consume.

### 4.1. ML Job Skeleton

* [ ] Create `ml/` folder with Python environment.
* [ ] Define data access layer to Supabase Postgres:

  * [ ] Use `postgres` URL (service role) to query `ohlc_bars`.
* [ ] Write script to:

  * [ ] Load recent OHLC data for a set of symbols.
  * [ ] Build features (basic indicators + returns).

### 4.2. Baseline Model & Forecast Generation

* [ ] Choose and implement a **baseline** forecast model (e.g., simple regression / Prophet / AR model) — keep it simple at first.
* [ ] For each symbol:

  * [ ] Produce forecast points for horizon (e.g., `1D` / `1W`).
  * [ ] Compute a simple label (Bullish/Neutral/Bearish) and confidence.
* [ ] Implement write-back to `ml_forecasts`:

  * [ ] Insert or upsert `symbol_id`, `horizon`, `overall_label`, `confidence`, `run_at`, `points`.

### 4.3. Scheduling & Ops

* [ ] Configure a 10-minute schedule to run the ML scoring job.
* [ ] Add logging and basic error alerts (e.g., job статус table or log stream).
* [ ] Confirm forecasts exist in `ml_forecasts` for test symbols.

---

## Phase 5 — Integrating ML with `/chart` and SwiftUI

**Goal:** Pipe forecasts into the `/chart` API and render them as overlay + report card in the macOS app.

### 5.1. Backend: `/chart` with ML

* [ ] Update `/chart` Edge Function to:

  * [ ] Query `ml_forecasts` for latest row(s) for `symbol_id`.
  * [ ] Transform DB row(s) into `mlSummary` JSON structure:

    * Overall label + confidence.
    * `horizons[]` each with series of forecast points.
  * [ ] Omit or null `mlSummary` for free users (based on `user_plans`).
* [ ] Add tests for `/chart` to ensure `mlSummary` is present and well-formed for upgraded users.

### 5.2. Client: Models & ViewModel

* [ ] Add `MLTrendLabel`, `ForecastPoint`, `ForecastSeries`, and `MLSummary` Swift models.
* [ ] Extend `ChartResponse` to include `mlSummary`.
* [ ] Update `MarketDataService.fetchChart` to decode `mlSummary`.
* [ ] Update `ChartViewModel` to store `mlSummary` and expose:

  * [ ] `forecastSeries` for chart overlay.
  * [ ] `overallLabel` and `confidence` for report card.

### 5.3. Client: Chart & Report Card UI

* [ ] Update `PriceChartView` to draw:

  * [ ] Candle series from `bars`.
  * [ ] Forecast line series using future `ForecastPoint.value`.
  * [ ] Optional band using `lower`/`upper`.
* [ ] Implement `MLReportCardView`:

  * [ ] Green / Gray / Red label based on `overallLabel`.
  * [ ] Confidence as percentage.
  * [ ] Horizon chips for each forecast series.
* [ ] Wire `MLReportCardView` into `ChartAreaView`.

---

## Phase 6 — Options Ranker & Scanner (Post-MVP)

**Goal:** Add ranked options and basic scanner support, gated to upgraded plan.

### 6.1. Options Data & `options_ranks`

* [ ] Ingest options chain & metrics from Massive API.
* [ ] Create or finalize `options_ranks` schema.
* [ ] Implement ML scoring/ranking for options in Python job.

### 6.2. `/options/rankings` Endpoint

* [ ] Implement Edge Function for `GET /options/rankings`.
* [ ] Apply plan gating (only upgraded users receive real data).

### 6.3. Client Integration

* [ ] Implement `OptionsRankerService` and models.
* [ ] Implement `OptionsRankerTabView` UI.

### 6.4. Watchlist Scanner

* [ ] Implement `scanner_alerts` logic and table.
* [ ] Implement `/scanner/watchlist` Edge Function.
* [ ] Wire `ScannerService` + `AlertsTabView` + watchlist badges.

---

## Phase 7 — Hardening, Observability & Polish

**Goal:** Make the system robust enough for real usage.

### 7.1. Error Handling & Degradation

* [ ] Define how `/chart` behaves when external providers fail:

  * [ ] Return last-known data with `stale: true` flag.
* [ ] Ensure client shows appropriate UI for stale/failed data.

### 7.2. Monitoring & Logging

* [ ] Centralize logging for Edge Functions.
* [ ] Add basic metrics (errors, latency, job success/failure).

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
