# GitHub Actions Setup Guide

This guide walks you through setting up GitHub Actions for the SwiftBolt ML project.

## Prerequisites

- Repository pushed to GitHub
- Access to repository settings (admin/maintainer role)
- Supabase project credentials
- API keys for Finnhub and Polygon.io

## Step 1: Configure Repository Secrets

1. Go to your GitHub repository
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add the following secrets:

### Required Secrets

| Secret Name | Description | Where to Find |
|-------------|-------------|---------------|
| `SUPABASE_URL` | Your Supabase project URL | Supabase Dashboard → Settings → API → Project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role key (NOT anon key) | Supabase Dashboard → Settings → API → Service Role Key |
| `FINNHUB_API_KEY` | Finnhub API key | Finnhub.io → Dashboard → API Keys |
| `MASSIVE_API_KEY` | Polygon.io API key | Polygon.io → Dashboard → API Keys |

**Important**: Use the **service role key**, not the anon key, for `SUPABASE_SERVICE_ROLE_KEY`. The service role key bypasses RLS and is needed for backfill operations.

## Step 2: Verify Workflow Files

Ensure these files exist in your repository:

```
.github/
├── workflows/
│   ├── backfill-ohlc.yml    # Main workflow
│   └── README.md             # Workflow documentation
└── SETUP.md                  # This file
```

## Step 3: Enable GitHub Actions

1. Go to your repository's **Actions** tab
2. If prompted, click **I understand my workflows, go ahead and enable them**
3. You should see "Automated OHLC Backfill" in the workflows list

## Step 4: Test the Workflow

### Manual Test Run

1. Go to **Actions** → **Automated OHLC Backfill**
2. Click **Run workflow** (dropdown on the right)
3. Leave inputs blank to test with all watchlist symbols
4. Click **Run workflow** (button)
5. Watch the workflow run in real-time

### Verify Results

1. Check the workflow logs for success/failure messages
2. Verify data in Supabase:
   ```sql
   SELECT symbol_id, timeframe, COUNT(*) as bar_count
   FROM ohlc_bars
   GROUP BY symbol_id, timeframe
   ORDER BY symbol_id;
   ```

## Step 5: Monitor Scheduled Runs

The workflow automatically runs every 6 hours at:
- 00:00 UTC (4:00 PM PST)
- 06:00 UTC (10:00 PM PST)
- 12:00 UTC (4:00 AM PST)
- 18:00 UTC (10:00 AM PST)

Check the **Actions** tab to see past runs and their results.

## Troubleshooting

### "Error: No secrets found"

**Solution**: Verify all four required secrets are set in repository settings.

### "Authentication failed"

**Solution**:
- Double-check `SUPABASE_SERVICE_ROLE_KEY` is the service role key
- Verify `SUPABASE_URL` matches your project URL exactly
- Check that the service role key hasn't expired

### "Failed to fetch chart data"

**Solution**:
- Verify `MASSIVE_API_KEY` (Polygon.io) is valid
- Check Polygon.io dashboard for rate limits or quota issues
- Ensure the `/chart` Edge Function is deployed: `supabase functions list`

### "No bars returned for symbol"

**Solution**:
- Verify the symbol exists in the `symbols` table
- Check if Polygon.io has data for that symbol
- Test the symbol manually: `curl https://YOUR_URL/functions/v1/chart?symbol=AAPL`

### Workflow doesn't run on schedule

**Solution**:
- GitHub Actions may delay scheduled workflows by up to 15 minutes during high load
- Verify the workflow is enabled in the Actions tab
- Check that the repository isn't archived or disabled

## Security Best Practices

1. **Never commit secrets to the repository**
   - Always use GitHub Secrets for sensitive data
   - Add `.env` files to `.gitignore`

2. **Rotate API keys periodically**
   - Update secrets when rotating keys
   - Monitor API usage for unauthorized access

3. **Use service role key carefully**
   - Only use in trusted, server-side contexts
   - Never expose in client-side code
   - Limit workflow permissions if possible

4. **Review workflow logs**
   - Check for suspicious activity
   - Monitor for failed authentication attempts
   - Verify expected data volumes

## Next Steps

- Review `.github/workflows/README.md` for detailed workflow documentation
- Customize the watchlist in `ml/src/scripts/backfill_ohlc.py`
- Adjust the schedule in `backfill-ohlc.yml` if needed
- Set up notifications for workflow failures (Settings → Notifications)

## Support

For issues:
1. Check workflow logs in the Actions tab
2. Review Supabase function logs: `supabase functions logs chart`
3. Verify database state with SQL queries
4. Check this repository's Issues page for known problems
