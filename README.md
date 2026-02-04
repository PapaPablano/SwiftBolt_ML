# SwiftBolt ML

SwiftBolt ML is an end-to-end market intelligence platform that unifies intraday/historical market data ingestion, automated Supabase orchestration, Python ML forecasting, and a macOS SwiftUI workstation for equities and options research.

## Project Scope

- **Data ingestion & normalization:** Supabase Edge Functions coordinate Alpaca and Polygon (Massive) feeds, corporate action reconciliation, intraday backfills, and coverage monitoring.
- **Market intelligence layer:** Supabase Postgres models store calendars, corporate actions, OHLC/IV histories, options chains, and orchestrator telemetry for downstream consumers.
- **Forecasting & analytics:** Python pipelines generate ensemble forecasts, ranking evaluations, and health reports that feed both dashboards and the desktop client.
- **macOS research workstation:** The SwiftUI client renders ML overlays, options analytics, and alerting tools tailored for discretionary traders.


## Tech Stack

- **Client**: Swift 5.9+, SwiftUI, macOS 14+
- **Backend**: Supabase Edge Functions (TypeScript/Deno)
- **Database**: PostgreSQL (Supabase)
- **ML**: Python 3.11+, scikit-learn, pandas
- **Data Providers**: Alpaca (primary market data), Finnhub (news/events), Polygon (Massive API)

## Project Structure

```
SwiftBolt_ML/
├── backend/          # Supabase Edge Functions
├── client-macos/     # SwiftUI macOS app
├── ml/               # Python ML pipeline
├── infra/            # Docker, deployment configs
├── docs/             # Architecture documentation
├── CLAUDE.md         # Claude Code instructions
└── README.md
```

## Getting Started

### Prerequisites

- macOS 14+
- Xcode 15+
- Node.js 18+
- Python 3.11+
- Supabase CLI

### Environment Setup

1. Copy environment template:
   ```bash
   cp .env.example .env
   ```

2. Fill in your API keys in `.env`

### Backend Development

```bash
cd backend
npm install
npx supabase start
npx supabase functions serve
```

### ML Pipeline

```bash
cd ml
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

**Recent Updates (Jan–Feb 2026)**:
- **ML consolidation**: Unified forecast processor (`unified_forecast_job.py`), split evaluation jobs (daily/intraday), Redis feature caching (4–6x improvement). See `CONSOLIDATION_COMPLETE_SUMMARY.md`.
- **Phase 7 canary (Feb 2026)**: 2-model ensemble (LSTM + ARIMA-GARCH) in 6-day canary on AAPL, MSFT, SPY; walk-forward validation and divergence monitoring. Transformer disabled in production workflow. See `1_27_Phase_7.1_Schedule.md` and `PHASE_7_CANARY_DEPLOYMENT_STATUS.md`.
- **Sentiment**: Temporarily disabled in features (zero-variance fix); backfill and `validate_sentiment_variance` before re-enable. See `docs/technicalsummary.md`.

**Running Forecasts**:
```bash
# Generate daily forecasts (1D, 1W, 1M)
python ml/src/unified_forecast_job.py

# Generate intraday forecasts (15m, 1h)
python ml/src/intraday_forecast_job.py

# Evaluate daily forecasts
python ml/src/evaluation_job_daily.py

# Evaluate intraday forecasts
python ml/src/evaluation_job_intraday.py
```

### macOS Client

Open `client-macos/SwiftBolt.xcodeproj` in Xcode and run.

## Documentation

### Architecture & Design
- [Master Blueprint](docs/master_blueprint.md) - Vision, scope, backend/API design
- [Architecture](docs/ARCHITECTURE.md) - System diagram, components, data flow
- [Implementation Checklist](docs/blueprint_checklist.md) - Phase-based progress tracker

### Phase 7 & ML (Feb 2026)
- [Phase 7.1 Schedule](1_27_Phase_7.1_Schedule.md) - Canary plan, GO/NO-GO criteria
- [Phase 7 Canary Status](PHASE_7_CANARY_DEPLOYMENT_STATUS.md) - Deployment readiness, 2-model ensemble

### ML Pipeline Consolidation (Jan 2026)
- [Consolidation Summary](CONSOLIDATION_COMPLETE_SUMMARY.md) - Complete overview of Phases 1-4
- [Implementation Plan](CONSOLIDATION_IMPLEMENTATION_PLAN.md) - Detailed consolidation roadmap
- [Dependency Analysis](DEPENDENCY_ANALYSIS.md) - Original dependency mapping
- [Test Suite](tests/audit_tests/README_PHASE3.md) - Testing documentation
- [Legacy Scripts](ml/src/_legacy/README.md) - Archived code reference

## License

Proprietary - All rights reserved
