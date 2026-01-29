# Options Ranker Fresher Data via Docker/FastAPI

## Summary

Options data for the Options Momentum Ranker can be served from the **Docker/FastAPI** backend for fresher chain and quotes. The macOS app tries FastAPI first for options-chain and options-quotes, then falls back to Supabase Edge if FastAPI is unavailable.

## Why Data Was Stale

1. **Rankings (STALE 5d ago)**  
   Rankings come from the **database** (`options_ranks`), filled by the ML ranking job. If that job hasn’t run for a symbol recently, the “last run” time is old and the UI shows STALE.  
   **Fix:** Run the ranking job more often (cron/scheduler) or trigger it from the app so `options_ranks` is updated regularly.

2. **Quotes (Stale 4h/5h on contracts)**  
   Bid/ask were coming from Supabase Edge `options-quotes`, which uses Alpaca/Yahoo. When the client didn’t refresh quotes often or the Edge cache was old, quotes looked stale.  
   **Fix:** Use FastAPI with **Tradier** for options chain and quotes so the app gets live data when the backend is running.

## What’s Implemented

### FastAPI (Docker) backend

- **GET /api/v1/options-chain?underlying=AAPL&expiration=...**  
  Fetches live options chain: **Alpaca first** (when `ALPACA_API_KEY` / `ALPACA_API_SECRET` are set), then **Tradier** as fallback. Same response shape as the Supabase `options-chain` Edge Function.

- **POST /api/v1/options-quotes**  
  Body: `{ "symbol": "AAPL", "contracts": ["AAPL250117C00250000", ...] }`. Returns live quotes from Alpaca (primary) or Tradier (fallback). Same response shape as the Supabase `options-quotes` Edge Function.

- **GET /api/v1/options-rankings?symbol=AAPL&mode=monitor&...**  
  Returns options rankings from Supabase (same data as Edge `options-rankings`). Powers the Options Ranker list and the **detail view** (Ranking Modes, Momentum Framework Breakdown, GA Strategy Alignment). Requires Supabase configured in FastAPI env.

**Requirements:** At least one of:
- **Alpaca** (already used for stock data): set `ALPACA_API_KEY` and `ALPACA_API_SECRET` in the FastAPI/Docker environment.
- **Tradier**: set `TRADIER_API_KEY` in the FastAPI/Docker environment.

If neither is set, these endpoints return 503 and the client falls back to Edge.

### macOS client

- **Options chain:** `fetchOptionsChain` calls FastAPI `/api/v1/options-chain` first; on failure (e.g. FastAPI down or 503), it uses the Supabase `options-chain` Edge Function.
- **Options quotes:** `fetchOptionsQuotes` calls FastAPI `/api/v1/options-quotes` first; on failure, it uses the Supabase `options-quotes` Edge Function.
- **Rankings:** `fetchOptionsRankings` tries FastAPI `/api/v1/options-rankings` first (reads Supabase `options_ranks`), then Edge. The detail panel (Ranking Modes, Momentum Framework, GA Strategy) uses this same rankings data. Fresher “Stale: 5d” requires running the ML ranking job more often or triggering it from the app.

### Data flow (fresher path)

```
macOS App
  → GET  Config.fastAPIURL/api/v1/options-chain?underlying=AAPL
  → POST Config.fastAPIURL/api/v1/options-quotes  (symbol + contracts)
  ← FastAPI: Alpaca first, then Tradier (same credentials you already use)

If FastAPI fails (not running / 503):
  → Supabase Edge options-chain / options-quotes (Yahoo/Alpaca)
```

## How to Get Fresher Data

1. **Run FastAPI with Alpaca and/or Tradier**  
   - Start the backend: `docker-compose up -d` in `ml/` (or run the FastAPI app).  
   - Set **Alpaca** (same as stock data): `ALPACA_API_KEY` and `ALPACA_API_SECRET`. Options chain/quotes will use Alpaca first.  
   - Optionally set **Tradier**: `TRADIER_API_KEY` as fallback when Alpaca isn’t configured or returns no data.  
   - Ensure the macOS app’s FastAPI URL (e.g. `FASTAPI_URL` in Info.plist) points at that backend (e.g. `http://localhost:8000`).

2. **Refresh quotes in the app**  
   The ranker’s “Sync LIVE” / quote refresh will then pull from FastAPI/Tradier when the backend is up, so bid/ask stay current.

3. **Fresher rankings**  
   - Trigger the ranking job from the app if your build supports it, or  
   - Run the ML options ranking job on a schedule (e.g. cron) so `options_ranks` is updated regularly.  
   Rankings themselves are not yet served from FastAPI; they remain from the DB via Edge.

## Files Touched

| Area | File | Change |
|------|------|--------|
| FastAPI | `ml/api/routers/options.py` | options-chain (GET), options-quotes (POST), options-rankings (GET) — Alpaca/Tradier for chain/quotes; Supabase for rankings. |
| FastAPI | `ml/api/main.py` | Registered options router. |
| Client | `client-macos/SwiftBoltML/Services/APIClient.swift` | `fetchOptionsChain`, `fetchOptionsQuotes`, and `fetchOptionsRankings` try FastAPI first, then Edge. |

## Quick test (FastAPI + Tradier)

```bash
# In ml/ with ALPACA_API_KEY/ALPACA_API_SECRET (and optionally TRADIER_API_KEY) set
docker-compose up -d
curl "http://localhost:8000/api/v1/options-chain?underlying=AAPL" | head -c 500
curl -X POST "http://localhost:8000/api/v1/options-quotes" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"AAPL","contracts":["AAPL250117C00250000"]}'
```

Then open the Options tab in the macOS app and refresh; with FastAPI running and Alpaca (or Tradier) configured, chain and quotes should come from the backend and appear fresher.
