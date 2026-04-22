# Edge Function Auth Matrix

Last updated: 2026-04-21

This document catalogs the authentication model for every Supabase Edge Function. It is a living document — update when functions are added or auth changes.

## How Auth Works in Supabase Edge Functions

- **`verify_jwt = true`** (default): Supabase gateway validates the JWT before the function executes. Requests with an invalid or missing JWT are rejected at the gateway level.
- **`verify_jwt = false`**: Supabase gateway passes all requests through. The function must implement its own auth (gateway-key, manual JWT check, or intentionally public).
- **Anon key**: All client requests include the Supabase anon key in the `apikey` header. This is for routing, not security.
- **SB_GATEWAY_KEY**: A shared secret for internal/cron callers. Enforced inside the function via `X-SB-Gateway-Key` header check.

## Functions with `verify_jwt = false` (explicit in config.toml)

| Function | Auth Mechanism | Caller Type | Rationale |
|----------|---------------|-------------|-----------|
| `chart` | Anon key (public) | Client (React, Swift) | Public read-only chart data. Anon key access by design. |
| `options-chain` | Anon key (public) | Client (React, Swift) | Public read-only options data. Anon key access by design. |
| `strategies` | Optional Bearer token | Client (React, Swift) | Auth is optional — authenticated users own strategies, anon gets user_id=null. Service-role client used. **Known limitation:** anon RLS allows any caller to mutate any null-user_id row. |
| `strategy-backtest` | Manual getUser() + 401 | Client (React, Swift) | Performs manual JWT validation inside function (lines 23-28). Returns 401 if no valid user. |
| `run-backfill-worker` | SB_GATEWAY_KEY | Cron (GH Actions) | Internal worker. Gateway-key enforced (lines 35-57). |
| `ga-strategy` | SB_GATEWAY_KEY | Cron (automation) | Internal optimization. Gateway-key enforced (added 2026-04-21). No GH Actions workflow currently passes the key — caller must be updated. |
| `strategy-backtest-worker` | SB_GATEWAY_KEY | Cron (GH Actions) | Internal worker. Gateway-key enforced. |
| `intraday-live-refresh` | SB_GATEWAY_KEY | Cron (pg_cron) | Internal data refresh. Gateway-key enforced. |
| `get-unified-validation` | JWT (verify_jwt=true) | Client (Swift) | Changed from false to true on 2026-04-21. Client-facing — APIClient.swift:1240 calls it. |

## Functions with `verify_jwt = true` (Supabase default)

All functions not listed in `supabase/config.toml` default to `verify_jwt = true`. JWT is validated by the Supabase gateway before the function executes.

| Function | Caller Type | Notes |
|----------|-------------|-------|
| `adjust-bars-for-splits` | Internal | Data maintenance |
| `apply-futures-migration` | Internal | One-time migration |
| `apply-h1-fix` | Internal | One-time fix |
| `backtest-strategy` | Client | Strategy backtesting |
| `data-health` | Client | Data quality monitoring |
| `ensure-coverage` | Internal | Data coverage check |
| `forecast-quality` | Client | Forecast quality metrics |
| `futures-chain` | Client | Futures chain data |
| `futures-continuous` | Client | Continuous futures data |
| `futures-roots` | Client | Futures root symbols |
| `get-multi-horizon-forecasts` | Client | ML forecast data |
| `greeks-surface` | Client | Options Greeks surface |
| `ingest-live` | Internal | Live data ingestion |
| `live-trading-executor` | Internal | Live trade execution |
| `log-validation-audit` | Internal | Validation logging |
| `market-status` | Client | Market hours/status |
| `multi-leg-close-leg` | Client | Multi-leg operations |
| `multi-leg-close-strategy` | Client | Multi-leg operations |
| `multi-leg-create` | Client | Multi-leg operations |
| `multi-leg-delete` | Client | Multi-leg operations |
| `multi-leg-detail` | Client | Multi-leg operations |
| `multi-leg-evaluate` | Client | Multi-leg operations |
| `multi-leg-list` | Client | Multi-leg operations |
| `multi-leg-templates` | Client | Multi-leg operations |
| `multi-leg-update` | Client | Multi-leg operations |
| `options-quotes` | Client | Options quote data |
| `paper-trading-executor` | Client | Paper trade execution |
| `portfolio-optimize` | Client | Portfolio optimization |
| `quotes` | Client | Real-time quotes |
| `seed-futures` | Internal | One-time seed |
| `stress-test` | Client | Stress test analysis |
| `symbol-backfill` | Internal | Data backfill |
| `symbols-search` | Client | Symbol search |
| `sync-corporate-actions` | Internal | Data sync |
| `sync-futures-bars` | Internal | Data sync |
| `sync-futures-data` | Internal | Data sync |
| `sync-market-calendar` | Internal | Data sync |
| `technical-indicators` | Client | Technical indicator data |
| `test-alpaca-futures` | Internal | Test utility |
| `test-polygon` | Internal | Test utility |
| `train-model` | Internal | ML model training |
| `trigger-backfill` | Internal | Backfill trigger |
| `trigger-ranking-job` | Internal | Ranking job trigger |
| `ts-strategies` | Client | TradeStation strategies |
| `user-refresh` | Client | User session refresh |
| `volatility-surface` | Client | Volatility surface data |
| `walk-forward-optimize` | Client | Walk-forward optimization |

## Security Notes

- **SB_GATEWAY_KEY** is a single shared secret across all gateway-key-protected functions. Compromise of any caller grants access to all protected functions. Key rotation is not yet implemented — tracked as future work.
- **Strategies anon RLS gap**: The `user_id IS NULL` RLS policy on `strategy_user_strategies` allows any anon caller to UPDATE/DELETE any null-user_id row. Anon data is intentionally ephemeral. Future fix: add `session_token` column for anon row scoping.
- **Internal functions with verify_jwt=true**: Functions like `ingest-live`, `train-model`, and `trigger-backfill` use JWT verification. Their callers must send a valid service-role JWT. If called from GitHub Actions, the workflow must use `SUPABASE_SERVICE_ROLE_KEY` as the Bearer token.
