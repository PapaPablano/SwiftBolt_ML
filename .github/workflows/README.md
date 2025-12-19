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
