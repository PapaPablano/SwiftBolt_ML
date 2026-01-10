# GitHub Actions Workflows

## backfill-ohlc.yml

Automated OHLC data backfill workflow that runs every 6 hours to keep historical stock data up-to-date.

### Schedule

Runs automatically at:
- 00:00 UTC (4:00 PM PST / 7:00 PM EST)
- 06:00 UTC (10:00 PM PST / 1:00 AM EST)
- 12:00 UTC (4:00 AM PST / 7:00 AM EST)
- 18:00 UTC (10:00 AM PST / 1:00 PM EST)

### Manual Trigger

You can also run this workflow manually from the GitHub Actions UI:

1. Go to **Actions** → **Automated OHLC Backfill**
2. Click **Run workflow**
3. Optionally specify:
   - **Symbol**: Single symbol to backfill (e.g., `AAPL`)
   - **Timeframe**: Timeframe to use (default: `d1`)
4. Leave both blank to backfill all watchlist symbols

### Required Secrets

Configure these in your GitHub repository settings (Settings → Secrets and variables → Actions):

- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY`: Supabase service role key (not anon key!)
- `FINNHUB_API_KEY`: Finnhub API key
- `MASSIVE_API_KEY`: Polygon.io API key

### How It Works

1. **Scheduled runs**: Backfills all watchlist symbols defined in `ml/src/scripts/backfill_ohlc.py`
2. **Manual runs**: Backfills specified symbol or all watchlist symbols
3. **Data source**: Fetches from Polygon.io via the `/chart` Edge Function
4. **Storage**: Upserts data into `ohlc_bars` table in Supabase
5. **Deduplication**: Uses upsert to avoid duplicate bars

### Monitoring

- Check the **Actions** tab to see workflow runs
- Each run provides a summary with success/failure counts
- Detailed logs show which symbols were processed
- Job summary shows configuration and results

### Troubleshooting

**Workflow fails with authentication error:**
- Verify all required secrets are set correctly
- Check that `SUPABASE_SERVICE_ROLE_KEY` is the service role key, not the anon key

**No data is being inserted:**
- Check Edge Function logs: `supabase functions logs chart`
- Verify Polygon.io API key has sufficient credits
- Ensure symbols exist in the `symbols` table

**Timeout errors:**
- The workflow has a 30-minute timeout
- If backfilling many symbols, consider breaking into smaller batches
- Check network connectivity to Supabase and Polygon.io

### Customization

To modify the schedule, edit the `cron` expression in `backfill-ohlc.yml`:

```yaml
schedule:
  - cron: "0 */6 * * *"  # Every 6 hours
```

Examples:
- `"0 0 * * *"` - Daily at midnight UTC
- `"0 */12 * * *"` - Every 12 hours
- `"0 0 * * 1-5"` - Daily at midnight UTC, Monday-Friday only

To add/remove symbols from the watchlist, edit `WATCHLIST_SYMBOLS` in `ml/src/scripts/backfill_ohlc.py`.

---

## daily-data-refresh.yml

**NEW:** Automated daily data refresh with gap detection and validation. Runs every morning to ensure all chart data is current and complete.

### Schedule

Runs automatically at:
- **6:00 AM UTC** (12:00 AM CST / 1:00 AM EST) every day

### Manual Trigger

Run manually from GitHub Actions UI:

1. Go to **Actions** → **Daily Data Refresh**
2. Click **Run workflow**
3. Options:
   - **Force full backfill**: Enable to run complete backfill with gap detection (slower but more thorough)
   - Leave unchecked for quick incremental update (default)

### Required Secrets

Configure these in GitHub repository settings:

- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY`: Supabase service role key
- `DATABASE_URL`: Direct Postgres connection string
- `ALPACA_API_KEY`: Alpaca API key
- `ALPACA_API_SECRET`: Alpaca API secret

### What It Does

**Incremental Mode (Default):**
1. Fetches latest bars for all timeframes (m15, h1, h4, d1, w1)
2. Updates only new data since last run
3. Validates data quality
4. Reports any gaps detected

**Full Backfill Mode (Manual trigger):**
1. Runs complete backfill with gap detection
2. Auto-retries any symbols/timeframes with issues
3. Validates final data quality
4. Ensures 100% coverage

### Features

- ✅ **Gap Detection**: Automatically finds missing data periods
- ✅ **Auto-Retry**: Fixes issues without manual intervention
- ✅ **Quality Validation**: Ensures data completeness
- ✅ **Artifact Upload**: Saves validation reports for review
- ✅ **Failure Notifications**: Alerts if critical gaps remain

### Monitoring

- Check **Actions** tab for daily run status
- Download validation report artifacts to see detailed coverage
- Workflow fails if critical gaps detected (requires attention)

### Validation Report

Each run generates a validation report showing:
- Bar counts per symbol/timeframe
- Coverage percentage (expected vs actual bars)
- Gap detection results
- Recommended retry commands if issues found

Example output:
```
✅ AAPL   m15  | Bars:  1055 | Coverage:  98.5% | Gaps:  0
✅ AAPL   h1   | Bars:  1047 | Coverage:  99.2% | Gaps:  0
✅ AAPL   h4   | Bars:   598 | Coverage:  97.8% | Gaps:  0
✅ AAPL   d1   | Bars:   501 | Coverage: 100.0% | Gaps:  0
✅ AAPL   w1   | Bars:   285 | Coverage: 100.0% | Gaps:  0
```

### Troubleshooting

**Workflow reports gaps detected:**
- Download the validation report artifact
- Review which symbols/timeframes have issues
- Run manual workflow with "Force full backfill" enabled

**Timeout errors:**
- 60-minute timeout per run
- If needed, reduce number of symbols in watchlist
- Or run incremental updates more frequently

**Authentication errors:**
- Verify all secrets are set correctly
- Ensure `ALPACA_API_KEY` and `ALPACA_API_SECRET` are valid
- Check Supabase credentials

### Best Practices

1. **Let it run daily**: Incremental mode is fast and keeps data fresh
2. **Monthly full backfill**: Run full backfill mode once a month for validation
3. **Monitor artifacts**: Check validation reports weekly
4. **Act on failures**: If workflow fails, investigate and fix gaps promptly
