# Alpaca Intraday Workflow Review

## Issues Identified in Current Workflow

### 1. **Critical Issues**
- **Missing `rsi_14` column**: Fixed with migration `20260117110000_add_missing_indicator_columns.sql`
- **Duplicate schedules**: Both `alpaca-intraday-cron.yml` and `intraday-ingestion.yml` run on the same schedule
- **No secret validation**: Workflow fails without clear error messages if secrets are missing

### 2. **Reliability Issues**
- **No retry logic**: Single API failures cause the entire workflow to fail
- **No timeout handling**: Operations can hang indefinitely
- **Poor error reporting**: Failed steps don't provide detailed error context
- **Rate limit handling**: No special handling for Alpaca rate limits (200 req/min)

### 3. **Data Flow Issues**
- **Market state logic**: Complex nested conditions make debugging difficult
- **Manual override behavior**: Inconsistent behavior between manual and scheduled runs
- **Data freshness reporting**: No clear indication of how stale the data is

### 4. **Performance Issues**
- **Sequential processing**: Timeframes processed one after another
- **No parallelization**: Could process multiple symbols/timeframes concurrently
- **Large symbol sets**: No limits on processing size, can cause timeouts

## Recommended Solutions

### 1. **Immediate Fixes Applied**
```yaml
# Added validation job to check secrets before running
- name: Validate Environment
  if [ -z "$ALPACA_API_KEY" ]; then
    echo "::error::ALPACA_API_KEY is not configured"
    exit 1
  fi
```

### 2. **Retry Logic Implementation**
```bash
retries=0
max_retries=3
while [ $retries -lt $max_retries ]; do
  if $cmd; then
    success=true
    break
  else
    retries=$((retries + 1))
    sleep 5  # Wait before retry
  fi
done
```

### 3. **Better Error Handling**
- Added database connection test
- Detailed error reporting in step summaries
- Graceful degradation for non-critical failures

### 4. **Data Freshness Reporting**
```python
# Calculate and display data age
from datetime import datetime, timezone
now = datetime.now(timezone.utc)
age_hours = (now - latest).total_seconds() / 3600
```

## Migration Strategy

### Option 1: Disable Duplicate Workflow
1. Disable schedule in `alpaca-intraday-cron.yml`
2. Use only `intraday-ingestion.yml`
3. Add missing features to `intraday-ingestion.yml`

### Option 2: Consolidate and Replace
1. Replace `alpaca-intraday-cron.yml` with `alpaca-intraday-cron-fixed.yml`
2. Disable `intraday-ingestion.yml`
3. Use the enhanced workflow with all fixes

### Option 3: Merge Best Features
1. Take retry logic from fixed version
2. Add to `intraday-ingestion.yml`
3. Deprecate old workflow completely

## Endpoint Validation

### Required Scripts Check
✅ `src/scripts/alpaca_backfill_ohlc_v2.py` - Exists and functional
✅ `src/scripts/get_watchlist_symbols.py` - Exists and functional
✅ `src/intraday_forecast_job.py` - Exists and functional
✅ `src/data/supabase_db.py` - Has `fetch_ohlc_bars()` method

### Database Tables Check
✅ `ohlc_bars_v2` - Main data table
✅ `indicator_values` - Now includes `rsi_14` column
✅ `symbols` - Symbol metadata
✅ `watchlist_items` - Watchlist management

### API Endpoints Check
✅ Alpaca Data API v2 - `https://data.alpaca.markets/v2`
✅ Supabase REST API - For data storage
✅ Supabase RPC - For custom functions

## Performance Recommendations

1. **Add Parallel Processing**
```yaml
strategy:
  matrix:
    timeframe: [m15, h1, h4]
  max-parallel: 3
```

2. **Implement Caching**
- Cache watchlist symbols for 1 hour
- Cache market hours check
- Cache API responses where appropriate

3. **Optimize Data Queries**
- Use batch inserts for indicators
- Limit historical data fetches
- Add database indexes for common queries

## Security Considerations

1. **Secret Management**
✅ All secrets properly referenced
✅ No hardcoded values
⚠️ Add secret rotation strategy

2. **Access Control**
✅ Using service role key for backend operations
✅ Row Level Security enabled on tables
⚠️ Consider adding IP restrictions

## Monitoring and Alerting

1. **Add Health Checks**
```yaml
- name: Health Check
  run: |
    curl -f "${SUPABASE_URL}/rest/v1/" || exit 1
```

2. **Error Notifications**
- Slack/webhook integration for failures
- Email alerts for consecutive failures
- Dashboard for monitoring success rates

3. **Metrics Collection**
- Track API usage per run
- Monitor data freshness
- Record processing times

## Next Steps

1. **Immediate**: Apply the fixed workflow or migrate to intraday-ingestion.yml
2. **Short Term**: Add monitoring and alerting
3. **Long Term**: Consider moving to a more robust scheduling system (e.g., Kubernetes CronJobs)

## Files Changed

- `supabase/migrations/20260117110000_add_missing_indicator_columns.sql` - Added missing columns
- `.github/workflows/alpaca-intraday-cron.yml` - Re-enabled schedule
- `.github/workflows/alpaca-intraday-cron-fixed.yml` - Enhanced version with all fixes
- `docs/ALPACA_INTRADAY_WORKFLOW_REVIEW.md` - This documentation
