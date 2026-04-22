# Data Freshness Architecture

How OHLCV data flows from market data providers to clients, and how staleness is detected.

## Ingestion Paths

### m1 Bars (Real-Time)
- **Mechanism:** `pg_cron` triggers `ingest-live` Edge Function every 1 minute during market hours
- **Source:** Alpaca API (last 5-minute window of m1 bars)
- **Destination:** `ohlc_bars_v2` via UPSERT with `data_status: 'live'`
- **Max staleness:** ~2 minutes (1-minute cron + processing)
- **Used by:** Partial candle synthesis (m1 bars aggregated into higher timeframes client-side)

### m15/h1/d1 Bars (Near-Real-Time)
- **Mechanism:** GitHub Actions `intraday-ingestion.yml` runs Python scripts every 5 minutes during market hours (9AM-5PM ET)
- **Source:** Alpaca API via Python ML pipeline (`src/scripts/resolve_universe`)
- **Destination:** `ohlc_bars_v2` via Python ingestion scripts
- **Max staleness:** ~10 minutes (5-minute cron + processing)

### Daily/Weekly Bars (End-of-Day)
- **Mechanism:** Same GitHub Actions workflow, after-hours runs
- **Destination:** `ohlc_bars_v2` with `data_status: 'verified'` after market close

## Staleness Detection (Chart Endpoint)

The `chart` Edge Function (`supabase/functions/chart/index.ts`) computes staleness for every response:

1. Finds the most recent actual (non-forecast) bar's timestamp (`lastActualBarTs`)
2. Computes age: `ageMinutes = (now - lastActualBarTs) / 60_000`
3. Looks up the SLA for the requested timeframe from `FRESHNESS_SLA_MINUTES`
4. Sets `isStale = ageMinutes > slaMinutes`

### SLA Thresholds

| Timeframe | SLA (minutes) | Rationale |
|-----------|--------------|-----------|
| m15 | 10 | 2x the 5-minute GH Actions cron interval |
| m30 | 60 | 1 hour tolerance |
| h1 | 120 | 2 hours |
| h4 | 480 | 8 hours |
| d1 | 1440 | 24 hours |
| w1 | 10080 | 1 week |

Note: m1 is not a valid chart timeframe (`VALID_TIMEFRAMES` does not include it). m1 bars are consumed by the partial candle synthesis path, not served directly.

## Chart Response Freshness Fields

The `freshness` object in the chart response includes:

| Field | Type | Description |
|-------|------|-------------|
| `ageMinutes` | number/null | Minutes since most recent bar |
| `slaMinutes` | number | SLA threshold for this timeframe |
| `isWithinSla` | boolean | `ageMinutes <= slaMinutes` |
| `lastUpdated` | string/null | ISO 8601 timestamp of most recent bar |
| `isStale` | boolean | `ageMinutes > slaMinutes` |
| `ageSeconds` | number/null | Seconds since most recent bar |
| `slaSeconds` | number | SLA threshold in seconds |

## Database Schema

`ohlc_bars_v2` includes freshness-relevant columns:
- `fetched_at` (TIMESTAMP) — when data was fetched from the provider
- `updated_at` (TIMESTAMP) — auto-updated by trigger on any change
- `data_status` (VARCHAR) — `live`, `verified`, or `provisional`

Note: The `get_chart_data_v2` RPC does not return `fetched_at` or `updated_at`. The chart endpoint uses bar `ts` as the freshness timestamp.

## Stale Data Recovery

When data is stale (`ageMinutes > slaMinutes`), the chart endpoint triggers a background backfill job (if no active job exists for that symbol). The response is returned immediately with the stale data and `isStale: true` — the endpoint never blocks on a refresh.
