# Quick Start: Multi-Timeframe Data Integration

This guide gets you up and running with the enhanced Alpaca API integration and data quality monitoring system.

## Prerequisites

- Alpaca API credentials ([Get them here](https://app.alpaca.markets))
- Supabase project with proper secrets configured
- macOS 14+ for client app
- PostgreSQL access for validation scripts

## Step 1: Configure Secrets

### GitHub Actions Secrets

Add these secrets to your repository (Settings → Secrets → Actions):

```
ALPACA_API_KEY=your-alpaca-key-id
ALPACA_API_SECRET=your-alpaca-secret-key
DATABASE_URL=postgresql://user:pass@host:5432/db
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
```

### Local Environment

Create `/ml/.env`:

```bash
ALPACA_API_KEY=your-alpaca-key-id
ALPACA_API_SECRET=your-alpaca-secret-key
DATABASE_URL=postgresql://user:pass@host:5432/db
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key
```

## Step 2: Deploy Backend

```bash
cd backend

# Deploy the enhanced chart-data-v2 function
supabase functions deploy chart-data-v2

# Verify deployment
curl -X POST "https://your-project.supabase.co/functions/v1/chart-data-v2" \
  -H "Authorization: Bearer YOUR_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"AAPL","timeframe":"d1","days":60}'
```

## Step 3: Initial Data Backfill

```bash
# Make scripts executable
chmod +x scripts/*.sh

# Run comprehensive backfill (this may take 10-30 minutes)
./scripts/comprehensive_backfill.sh "AAPL,MSFT,NVDA,TSLA,META"

# Watch for:
# - ✅ Success messages for each symbol/timeframe
# - Bar counts (should see 250+ for d1, h4)
# - Any failures (will be logged)
```

## Step 4: Validate Data Quality

```bash
# Run validation script
./scripts/validate_data_quality.sh "AAPL,MSFT,NVDA,TSLA,META"

# Expected output:
# ✅ All symbols should have:
#    - m15: 1000+ bars, <4 hours old
#    - h1: 500+ bars, <24 hours old
#    - h4: 250+ bars, <48 hours old
#    - d1: 250+ bars, <72 hours old
#    - w1: 52+ bars, <1 week old
```

## Step 5: Build Frontend

```bash
# Open Xcode project
cd client-macos
open SwiftBoltML.xcodeproj

# In Xcode:
# 1. Select the SwiftBoltML scheme
# 2. Build (Cmd+B)
# 3. Run (Cmd+R)
```

## Step 6: Verify UI

1. **Launch the app**
2. **Select a symbol** (e.g., AAPL)
3. **Look for the Data Quality Badge** next to the ticker symbol:
   - ✅ Green checkmark = Fresh data (< 4 hours)
   - 🔵 Blue clock = Recent data (< 24 hours)
   - ⚠️ Orange warning = Stale data (> 24 hours)
4. **Click the badge** to see detailed metrics
5. **Switch timeframes** and verify badge updates

## Step 7: Enable Monitoring

### Verify GitHub Actions

```bash
# Check if workflows are enabled
gh workflow list

# Should see:
# - alpaca-intraday-cron.yml (runs every 15 min during market hours)
# - daily-data-refresh.yml (runs daily at 6:00 AM UTC)
# - data-quality-monitor.yml (runs every 6 hours)

# View recent runs
gh run list --workflow=data-quality-monitor.yml --limit 5
```

### Manual Workflow Triggers

```bash
# Trigger data quality check
gh workflow run data-quality-monitor.yml

# Trigger full backfill
gh workflow run daily-data-refresh.yml --field force_full_backfill=true

# Trigger intraday update
gh workflow run alpaca-intraday-cron.yml
```

## Troubleshooting

### Issue: Badge Shows Orange Warning (Stale Data)

**Solution 1: Manual Refresh**
```bash
# Run backfill for specific symbol
cd ml
python src/scripts/alpaca_backfill_ohlc_v2.py --symbol AAPL --timeframe d1 --force
```

**Solution 2: Trigger GitHub Action**
```bash
gh workflow run alpaca-intraday-cron.yml --field symbols=AAPL
```

### Issue: Insufficient Bars for ML

**Solution: Backfill More History**
```bash
# The comprehensive backfill script already requests adequate history
# If still insufficient, check Alpaca API limits
./scripts/comprehensive_backfill.sh "AAPL" true  # Force refresh
```

### Issue: Badge Not Showing

**Solution 1: Verify API Response**
```bash
# Test the API directly
curl -X POST "https://your-project.supabase.co/functions/v1/chart-data-v2" \
  -H "Authorization: Bearer YOUR_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"AAPL","timeframe":"d1","days":60}' | jq '.dataQuality'

# Should see dataQuality object
```

**Solution 2: Clear Caches**
- In app: Use the refresh button (🔄) in chart header
- Or use "Sync" button for full refresh

### Issue: GitHub Actions Not Running

**Check:**
1. Workflows are enabled in repo settings
2. Secrets are configured correctly
3. View workflow logs for errors:
   ```bash
   gh run view --log
   ```

## Daily Operations

### Morning Routine (Before Market Open)
```bash
# 1. Check data quality
./scripts/validate_data_quality.sh

# 2. If issues found, run backfill
./scripts/comprehensive_backfill.sh

# 3. Verify in app - check badge is green
```

### During Market Hours
- GitHub Actions automatically update intraday data every 15 minutes
- App shows live prices with green badge for fresh data

### After Market Close
- Daily refresh workflow runs automatically
- Data quality monitor validates at 6-hour intervals

## Monitoring Dashboard

### GitHub Actions Tab
View all workflow runs:
- Go to repository → Actions tab
- Filter by workflow name
- Check for failures (red X)

### Data Quality Reports
Download validation reports:
- Go to workflow run → Artifacts section
- Download `data-quality-report-XXX`
- Review for warnings or failures

### App UI
Visual monitoring:
- Badge color indicates freshness
- Click for detailed metrics
- Shows ML readiness status

## Next Steps

1. **Add More Symbols**
   ```bash
   ./scripts/comprehensive_backfill.sh "GOOGL,AMZN,NFLX,DIS"
   ```

2. **Schedule Regular Checks**
   - Set up calendar reminders to review data quality
   - Monitor GitHub Actions for failures

3. **Customize Monitoring**
   - Edit `.github/workflows/data-quality-monitor.yml`
   - Adjust frequency or add notifications

4. **Explore ML Features**
   - With 250+ bars, ML models have sufficient training data
   - Review forecast accuracy in app
   - Check options rankings for trade ideas

## Resources

- **Full Documentation:** `/docs/MULTI_TIMEFRAME_DATA_INTEGRATION.md`
- **Alpaca API Docs:** https://docs.alpaca.markets
- **Supabase Docs:** https://supabase.com/docs
- **GitHub Actions:** https://docs.github.com/actions

## Support

If you encounter issues:

1. **Check Logs**
   - GitHub Actions: View workflow run logs
   - Supabase: Functions → chart-data-v2 → Logs
   - App: View console output in Xcode

2. **Run Diagnostics**
   ```bash
   ./scripts/validate_data_quality.sh  # Detailed report
   ```

3. **Verify API**
   ```bash
   # Test Alpaca connection
   cd ml
   python -c "from src.scripts.alpaca_backfill_ohlc_v2 import *; print('API Key OK')"
   ```

## Success Indicators

✅ You're ready when:
- All validation checks pass (green)
- Badge shows fresh data in app
- Charts display without errors
- Options rankings load successfully
- GitHub Actions run without failures

🎉 **You're all set!** The system will now:
- Automatically update data every 15 minutes during market hours
- Validate quality every 6 hours
- Alert you to any issues
- Provide transparent data quality in the UI

---

**Quick Reference Commands:**

```bash
# Validate data quality
./scripts/validate_data_quality.sh "AAPL,MSFT,NVDA"

# Comprehensive backfill
./scripts/comprehensive_backfill.sh "AAPL,MSFT,NVDA"

# Check GitHub Actions
gh run list --limit 10

# Deploy edge function
cd backend && supabase functions deploy chart-data-v2

# Test API
curl -X POST "$SUPABASE_URL/functions/v1/chart-data-v2" \
  -H "Authorization: Bearer $SUPABASE_ANON_KEY" \
  -d '{"symbol":"AAPL","timeframe":"d1"}'
```
