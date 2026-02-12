# Hourly Canary Blockers and Fixes

## Summary

Two blockers prevent the hourly canary from producing full rows:
1. **Realized bars** – ingestion stopped after 2026-01-16; no new `ohlc_bars_v2` rows for recent dates.
2. **Forecasts** – MSFT was missing from `intraday_symbols`; SPY first forecast at 15:47Z, after 09:30 CST target (15:30Z).

## 1) Realized Bars (Highest Priority)

### Root cause
`ohlc_bars_v2` has a trigger `validate_ohlc_v2_write()` (migration `20260117161834`) that enforces:

- **Historical** (`is_intraday=false`, `is_forecast=false`): `bar_date >= today` → RAISE EXCEPTION
- **Intraday** (`is_intraday=true`): `bar_date <> today` → RAISE EXCEPTION
- **Forecast** (`is_forecast=true`): `ts <= now()` → RAISE EXCEPTION

`today` is `(now() at time zone 'utc')::date`. If ingestion runs late at night, uses UTC timestamps, or replays bars for “today” after midnight UTC, inserts can fail.

### Data flow
- **Intraday ingestion** (`.github/workflows/intraday-ingestion.yml`): runs `alpaca_backfill_ohlc_v2.py` with `m15,h1` during market hours
- **Alpaca backfill** sets `is_intraday = (bar_date == today) and timeframe in ["m15","h1","h4"]`
- **Trigger**: no provider-specific rules; uses `is_intraday` / `is_forecast` / `bar_date` vs `today`

### Action items
1. **Check ingestion logs** for insert/upsert errors from `validate_ohlc_v2_write`
2. **Use Supabase Postgres logs** to see trigger exceptions (RAISE EXCEPTION)
3. **Validate canary loop**: Run canary on a date when *both* (a) realized bars exist and (b) forecasts with `created_at <= target_utc` exist. For 2026-01-16, realized bars exist but `ml_forecasts_intraday` has no rows from that date (forecasts are created live when the job runs). To validate:
   - Run intraday forecast job during market hours, then immediately run canary for that date
   - Or backfill historical forecasts for 2026-01-16 (if such a path exists)

### Timestamp semantics
- **Actual column type** (verified via `information_schema.columns`): `timestamp with time zone` (timestamptz)
- The original migration `20260105000000_ohlc_bars_v2.sql` defined `ts TIMESTAMP NOT NULL`; migration `20260117161834` altered it to `timestamptz`
- Alpaca bars are on `:00`, `:15`, `:30`, `:45` (15m boundaries)
- Canary targets 09:30–14:30 CST = 15:30–20:30 UTC; these align with bar timestamps
- Ensure all writers use UTC for `ts` consistently

## 2) MSFT Missing Forecasts

### Root cause
`settings.intraday_symbols` did not include MSFT or SPY, so the intraday forecast job never produced forecasts for them.

### Fix applied
Added **MSFT** and **SPY** to `ml/config/settings.py` `intraday_symbols`:
```python
intraday_symbols: list[str] = [
    "AAPL",
    "MSFT",
    "SPY",
    "NVDA",
    ...
]
```

### Post-write verification
The intraday forecast job now logs forecast counts by symbol after each run:
```
Post-write verification: 9 forecasts in last 15m for 15m (by symbol: {'AAPL': 3, 'MSFT': 3, 'SPY': 3})
```

### MSFT failure: insufficient OHLC coverage (category a)
Traceback/root cause:
```
Fetched 29 bars for MSFT (m15) via provider=polygon
Insufficient m15 bars for MSFT: 29 (need 60). Proceeding with fallback.
```
- Alpaca returns 0 bars for MSFT m15; polygon fallback returns 29
- 29 < 60 (min_bars) and 29 < 30 (hard return) → job returns False
- **Fix**: Treat as data-coverage problem first. Backfill MSFT m15 via Alpaca (or ensure MSFT is in the watchlist for intraday ingestion) before tuning model thresholds.

## 3) SPY Missing Forecast at 15:30Z (09:30 CST)

### Root cause
The earliest SPY forecast on 2026-02-11 was at `created_at` 15:47:10 UTC. The canary requires `created_at <= target_utc`, so target 15:30 UTC correctly has no qualifying forecast.

### Fix (operational)
1. **Schedule intraday forecast job before 09:30 CST (15:30 UTC)**
2. Or **drop the 09:30 target** from canary unless you run a pre-open forecast pass (e.g. 08:30–09:25 CST)

### Current schedule
- Intraday forecast: `5,20,35,50 13-22 * * 1-5` (5 min after each ingestion run)
- 13:00 UTC = 8:00 AM ET; first run is before 09:30 CST if market opens 9:30 ET

## 4) Schema Note (Optional)

`ohlc_bars_v2.ts` is already `timestamptz`. The trigger uses `DATE(NEW.ts)` vs `CURRENT_DATE`; both are in UTC. If clients send “UTC-looking” values that are actually local time, you can get day-boundary issues. Consider documenting that all ts must be in UTC.

## 5) Validation Commands

```bash
# Canary with intraday (after ingestion + forecast run)
python -m ml.scripts.hourly_canary_summary \
  --symbols SPY,AAPL,MSFT \
  --date-cst 2026-01-16 \
  --forecast-source intraday \
  --out ml/validation_results/hourly_canary_summary.csv

# Include rows with missing realized (for debugging)
python -m ml.scripts.hourly_canary_summary \
  --symbols SPY,AAPL,MSFT \
  --date-cst 2026-02-11 \
  --forecast-source intraday \
  --include-missing-realized \
  --out ml/validation_results/hourly_canary_summary.csv

# Run canary on known-good date (2026-01-16 has bars)
python -m ml.scripts.hourly_canary_summary --symbols SPY,AAPL --date-cst 2026-01-16 --forecast-source intraday --out ml/validation_results/hourly_canary_summary.csv
```
