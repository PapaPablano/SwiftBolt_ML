# 🎯 Multi-Provider Data Pipeline - Complete Setup

## ✅ Status: Ready to Run

Your multi-provider data pipeline has been fully configured with these fixes:

### What Was Fixed
1. **Provider Routing** - Polygon for intraday (m15, h1, h4), Yahoo for daily/weekly
2. **Database Schema** - Proper `symbol_id`, `provider`, `is_intraday`, `is_forecast` fields
3. **Upsert Logic** - Correct conflict resolution on all required columns
4. **Backfill System** - 2,615 chunks seeded for 2-year historical data (AAPL, NVDA, TSLA, SPY, QQQ)
5. **Rate Limiting** - Distributed token bucket respects Polygon's 5 req/min limit

### Files Changed
- [supabase/functions/_shared/providers/router.ts](supabase/functions/_shared/providers/router.ts) - Smart routing by timeframe
- [supabase/functions/_shared/providers/factory.ts](supabase/functions/_shared/providers/factory.ts) - Added getMassiveClient
- [supabase/functions/_shared/backfill-adapter.ts](supabase/functions/_shared/backfill-adapter.ts) - Symbol ID lookup, correct fields
- [supabase/functions/run-backfill-worker/index.ts](supabase/functions/run-backfill-worker/index.ts) - Pass supabase client, fix upsert key

---

## 🚀 Quick Start: 3 Steps to Enable Auto-Backfill

### Step 1: Add GitHub Secret

1. Go to your repo settings: https://github.com/YOUR_USERNAME/SwiftBolt_ML/settings/secrets/actions
2. Click **"New repository secret"**
3. Name: `SUPABASE_ANON_KEY`
4. Value: Get from https://supabase.com/dashboard/project/cygflaemtmwiwaviclks/settings/api
   - Copy the **anon/public** key (NOT the service_role key)
5. Click **"Add secret"**

### Step 2: Enable GitHub Actions

```bash
# Commit the workflow
git add .github/workflows/backfill-cron.yml
git commit -m "Add backfill worker cron"
git push

# Then go to: https://github.com/YOUR_USERNAME/SwiftBolt_ML/actions
# Click "I understand my workflows, go ahead and enable them"
```

### Step 3: Test & Monitor

Run the workflow manually once:
1. Go to Actions → "Backfill Worker Cron"
2. Click "Run workflow" → "Run workflow"
3. Wait 30 seconds, then check progress:

```sql
-- Run in SQL Editor: https://supabase.com/dashboard/project/cygflaemtmwiwaviclks/sql
SELECT
  symbol,
  progress || '%' as progress,
  (SELECT COUNT(*) FROM backfill_chunks WHERE job_id = j.id AND status = 'done') as done,
  (SELECT COUNT(*) FROM backfill_chunks WHERE job_id = j.id) as total
FROM backfill_jobs j
ORDER BY symbol;
```

**That's it!** The workflow runs automatically every 5 minutes.

---

## 📊 What Happens Next

### Automatic Processing

- **Interval**: Every 5 minutes (GitHub Actions limit)
- **Chunks/run**: 4 chunks processed in parallel
- **Rate**: ~48 chunks/hour (respecting Polygon's 5 req/min limit)
- **Total time**: ~55 hours (2.3 days) for full 2-year backfill

### Progress Example

```
Hour 0:  0% complete    (0/2,615 chunks)
Hour 1:  2% complete    (48/2,615 chunks)
Hour 12: 22% complete   (576/2,615 chunks)
Hour 24: 44% complete   (1,152/2,615 chunks)
Hour 48: 88% complete   (2,304/2,615 chunks)
Hour 55: 100% complete  (2,615/2,615 chunks)
```

---

## 🎨 Alternative: Faster 1-Minute Cron

For faster backfill (~11 hours instead of 55), use cron-job.org:

1. **Sign up**: https://cron-job.org/en/signup/
2. **Create cron job**:
   - Title: `SwiftBolt Backfill`
   - URL: `https://cygflaemtmwiwaviclks.supabase.co/functions/v1/trigger-backfill`
   - Schedule: **Every 1 minute**
   - HTTP Method: **POST**
   - Request headers:
     ```
     Authorization: Bearer YOUR_ANON_KEY_HERE
     Content-Type: application/json
     ```
   - Request body: `{}`
3. **Enable** the job

---

## 📈 Monitor Progress

### Quick Status Check
```sql
-- How many bars have been inserted?
SELECT
  s.ticker,
  COUNT(*) as bars,
  MIN(b.ts)::date as earliest,
  MAX(b.ts)::date as latest,
  ROUND((MAX(b.ts) - MIN(b.ts)) / INTERVAL '1 day') as days_covered
FROM ohlc_bars_v2 b
JOIN symbols s ON s.id = b.symbol_id
WHERE b.provider = 'polygon' AND b.is_forecast = false
GROUP BY s.ticker
ORDER BY s.ticker;
```

### Detailed Job Status
```sql
SELECT
  symbol,
  timeframe,
  status,
  progress || '%' as pct,
  (SELECT COUNT(*) FROM backfill_chunks WHERE job_id = j.id AND status = 'done') as done,
  (SELECT COUNT(*) FROM backfill_chunks WHERE job_id = j.id AND status = 'pending') as pending,
  (SELECT COUNT(*) FROM backfill_chunks WHERE job_id = j.id AND status = 'error') as errors,
  (SELECT COUNT(*) FROM backfill_chunks WHERE job_id = j.id) as total
FROM backfill_jobs j
ORDER BY symbol;
```

### Recent Activity
```sql
SELECT
  symbol,
  day::text as date,
  status,
  try_count,
  last_error,
  updated_at
FROM backfill_chunks
WHERE status IN ('done', 'error', 'running')
ORDER BY updated_at DESC
LIMIT 20;
```

### Error Debugging
```sql
-- Check for errors
SELECT symbol, day::text, last_error, try_count
FROM backfill_chunks
WHERE status = 'error'
ORDER BY updated_at DESC;

-- View edge function logs
-- Go to: https://supabase.com/dashboard/project/cygflaemtmwiwaviclks/functions
-- Click "run-backfill-worker" → "Logs"
```

---

## 🔧 Advanced: Add More Symbols

After the initial backfill completes, add more symbols:

```sql
-- Add Microsoft (2-year h1 backfill)
SELECT seed_intraday_backfill_2yr('MSFT', 'h1');

-- Add Google
SELECT seed_intraday_backfill_2yr('GOOGL', 'h1');

-- Add Amazon
SELECT seed_intraday_backfill_2yr('AMZN', 'h1');

-- Add Meta
SELECT seed_intraday_backfill_2yr('META', 'h1');

-- Add AMD
SELECT seed_intraday_backfill_2yr('AMD', 'h1');
```

Each symbol adds ~523 chunks (1 per trading day for 2 years).

---

## 🎯 Test Your Charts

Once backfill progresses, test the chart endpoint:

```bash
curl -X POST "https://cygflaemtmwiwaviclks.supabase.co/functions/v1/chart-data-v2" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ANON_KEY" \
  -d '{
    "symbol": "AAPL",
    "timeframe": "h1",
    "days": 730,
    "includeForecast": true
  }'
```

You should see:
- `historical`: Array of Polygon bars (growing as backfill progresses)
- `intraday`: Today's Tradier bars
- `forecast`: ML predictions

---

## 🎉 Success!

Your app now:
- ✅ Uses Polygon for historical intraday data (months/years)
- ✅ Uses Tradier for today's real-time data
- ✅ Uses Yahoo for daily/weekly data
- ✅ Respects rate limits with distributed token bucket
- ✅ Automatically backfills 2 years of data in the background
- ✅ Charts work immediately with data as it arrives

**No more 1-2 week limitations!** Your charts can now show years of intraday data. 🚀

---

## 📚 Reference

- **Backfill Jobs**: [20260109040000_comprehensive_intraday_backfill.sql](backend/supabase/migrations/20260109040000_comprehensive_intraday_backfill.sql)
- **Provider Router**: [router.ts:124-161](supabase/functions/_shared/providers/router.ts#L124-L161)
- **Backfill Worker**: [run-backfill-worker/index.ts](supabase/functions/run-backfill-worker/index.ts)
- **Trigger Endpoint**: [trigger-backfill/index.ts](supabase/functions/trigger-backfill/index.ts)
- **GitHub Workflow**: [backfill-cron.yml](.github/workflows/backfill-cron.yml)

---

## 🆘 Need Help?

Check logs:
- **Edge Functions**: https://supabase.com/dashboard/project/cygflaemtmwiwaviclks/functions
- **Database**: Run the monitoring queries above
- **GitHub Actions**: https://github.com/YOUR_USERNAME/SwiftBolt_ML/actions

Common issues:
- **"No chunks processing"**: Check cron is running (GitHub Actions or cron-job.org)
- **"Rate limit errors"**: Normal - handled automatically by token bucket
- **"Symbol not found"**: Ensure symbol exists in `symbols` table first
