# AGENTS.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## What This Project Is

SwiftBolt ML is an end-to-end market intelligence platform: intraday/historical data ingestion via Supabase Edge Functions, Python ML forecasting pipelines (ensemble of LSTM + ARIMA-GARCH, with XGBoost and TabPFN), and a macOS SwiftUI research workstation for equities and options. Alpaca is the primary market data provider; Supabase Postgres is the database.

## Architecture Overview

**Data flow:** Alpaca → Supabase Edge Functions (ingest/normalize) → Postgres → Python ML pipeline (feature eng → train → infer → evaluate) → Postgres → Edge Functions (GET /chart) → SwiftUI client

The SwiftUI client never calls data vendors directly — all market data and forecasts go through Supabase Edge Functions (the only public API surface).

### Key subsystems

- **`ml/`** — Python ML pipeline. Entry point: `ml/config/settings.py` (pydantic-settings singleton). Core jobs: `ml/src/unified_forecast_job.py` (daily 1D/5D/10D/20D), `ml/src/intraday_forecast_job.py` (15m/1h), `ml/src/evaluation_job_daily.py`, `ml/src/evaluation_job_intraday.py`. Models live in `ml/src/models/` (XGBoost, ARIMA-GARCH, LSTM, TabPFN, ensemble). Features in `ml/src/features/`. Data access in `ml/src/data/supabase_db.py`.
- **`supabase/functions/`** — TypeScript/Deno Edge Functions. Each function has its own directory with an `index.ts`. Shared code in `supabase/functions/_shared/` (Supabase client, CORS, rate limiter, data validation, provider adapters). The `chart` function implements the main GET /chart contract.
- **`supabase/migrations/`** — Postgres migration files. Naming convention: `YYYYMMDDHHMMSS_description.sql`.
- **`client-macos/`** — SwiftUI macOS app. Xcode project at `client-macos/SwiftBoltML.xcodeproj`. Uses async/await, Combine, actors for thread safety.
- **`frontend/`** — React + TradingView Lightweight Charts dashboard (Vite + TypeScript + Tailwind).
- **`backend/`** — Wrapper around Supabase Edge Functions with deployment scripts.

### ML pipeline architecture

The forecast pipeline follows a strict temporal discipline:
1. **Ingest** — Fetch OHLCV from Alpaca, store in `ohlc_bars_v2`
2. **Feature engineering** — Technical indicators, support/resistance, regime features, volatility analysis. Cached via `ml/src/features/feature_cache.py` (Redis optional, DB fallback)
3. **Inference** — Ensemble forecasts with weight precedence: intraday-calibrated → symbol-specific → defaults. Weights managed by `IntradayDailyFeedback` in `ml/src/intraday_daily_feedback.py`
4. **Evaluation** — Walk-forward validation only (no random splits). See `ml/src/evaluation/walk_forward_cv.py`. Lookahead bias guards in `ml/src/features/lookahead_checks.py`

**Current production ensemble:** LSTM + ARIMA-GARCH (2-model). Transformer disabled. TabPFN used in ensemble but not as sole model for trending assets (trend extrapolation limitations).

### Key Postgres tables

- `ohlc_bars_v2` — OHLCV cache (indexed on `symbol_id, timeframe, ts DESC`)
- `ml_forecasts` — Multi-horizon forecasts (upsert per `symbol_id + horizon`)
- `forecast_validation_metrics` / `ensemble_validation_metrics` — Walk-forward and canary results

## Build, Lint, and Test Commands

### Python ML pipeline (`ml/` directory)

```bash
# Setup
cd ml && python -m venv .venv && source .venv/bin/activate
pip install -e .                    # editable install from pyproject.toml
pip install -e ".[dev]"             # includes pytest, black, mypy, etc.

# Run forecasts
python ml/src/unified_forecast_job.py       # daily (1D, 5D, 10D, 20D)
python ml/src/intraday_forecast_job.py      # intraday (15m, 1h)
python ml/src/evaluation_job_daily.py       # evaluate daily forecasts
python ml/src/evaluation_job_intraday.py    # evaluate intraday forecasts

# Tests (from repo root)
pytest ml/tests/ -m "not integration" -v    # unit tests only
pytest ml/tests/ -v                         # all tests
pytest ml/tests/path/to/test_file.py::TestClass::test_method -v  # single test

# Linting & formatting
cd ml
black src tests                             # format (line-length 100)
black --check src tests                     # check only
isort src tests                             # sort imports
flake8 src tests --max-line-length=120 --extend-ignore=E203,W503
mypy src --ignore-missing-imports
```

### Supabase Edge Functions

```bash
# Local dev
npx supabase start                          # start local Supabase
npx supabase functions serve                # serve Edge Functions locally

# Or use convenience script
./scripts/start-backend.sh [start|stop|restart|logs|status]

# Lint & format
deno lint supabase/functions/
deno fmt supabase/functions/
deno fmt --check supabase/functions/

# Deploy
npx supabase functions deploy
npx supabase functions deploy <function-name>  # single function
```

### Frontend (React dashboard)

```bash
cd frontend
npm install
npm run dev       # Vite dev server
npm run build     # tsc && vite build
npm run lint      # eslint
```

### macOS Client

Open `client-macos/SwiftBoltML.xcodeproj` in Xcode and build/run (macOS 14+, Xcode 15+).

### Docker

```bash
docker compose up --build    # ML backend API on port 8000
```

## CI/CD

- **`ci-lightweight.yml`** — Runs on every push/PR. Detects changed components (ml/edge functions/migrations) and runs only relevant checks: Black, isort, flake8, mypy for ML; deno lint/fmt/check for Edge Functions; migration naming validation.
- **`ml-validation.yml`** — Comprehensive ML tests. Runs weekly (Monday 2:00 UTC), on demand, or when `requirements*.txt` changes. Runs pytest with coverage on Python 3.10 and 3.11. Enforces diff coverage >=90%.
- **`deploy-supabase.yml`** — Deploys Edge Functions and migrations.

## Code Conventions

- **Python:** Black formatter (line-length 100), isort (profile "black"), type hints on all signatures, async/await for I/O, guard clauses for early returns. Config via pydantic-settings (`ml/config/settings.py`).
- **Edge Functions:** Each function in its own `supabase/functions/<name>/index.ts`. Shared utilities in `_shared/`. Cache-first reads (return cached data, refresh if stale).
- **Swift:** Modern concurrency (async/await, actors), SwiftUI + Combine, `MARK:` comments for organization, `os_log` for logging.
- **SQL:** Lowercase snake_case identifiers, parameterized queries, BRIN indexes for time-series tables, cursor-based pagination (not OFFSET).

## Critical Rules

- **Never leak future data:** All ML validation must be walk-forward (time-ordered). The `STRICT_LOOKAHEAD_CHECK` env flag enables synthetic lookahead guards. See `ml/src/features/lookahead_checks.py`.
- **Client talks only to Edge Functions** — never directly to Alpaca, Finnhub, or other vendors.
- **Single GET /chart contract** — Don't fragment the chart read path into multiple endpoints. The chart Edge Function returns OHLCV + indicators + forecasts + accuracy badges in one round trip.
- **Read files before editing** — Always read a file before proposing changes.
- **One markdown doc per session** — Consolidate documentation into a single file per session rather than creating multiple .md files.
- **Sentiment features are currently disabled** (zero-variance fix pending). Do not re-enable without running `validate_sentiment_variance`.
- **Forecast weight precedence:** intraday-calibrated (fresh) → intraday-calibrated (stale, with warning) → symbol-specific from DB → defaults. Managed by `IntradayDailyFeedback`.

## Environment Variables

Copy `.env.example` to `.env`. Key variables: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `ALPACA_API_KEY`, `ALPACA_API_SECRET`, `FINNHUB_API_KEY`. Optional: `REDIS_FEATURE_CACHE=true` with Redis config for feature caching. ML config flags: `USE_UNIFIED_FORECAST=true`, `USE_SEPARATE_EVALUATIONS=true`, `STRICT_LOOKAHEAD_CHECK=0|1`.
