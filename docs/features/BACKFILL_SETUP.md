# Backfill Worker Setup Guide

Your multi-provider data pipeline is now configured! This guide shows you how to set up the automatic backfill cron job.

## ✅ What's Already Done

- [x] Database migrations applied
- [x] Edge functions deployed (`run-backfill-worker`, `trigger-backfill`)
- [x] Backfill jobs seeded (5 symbols × 523 chunks = 2,615 total)
- [x] Provider routing configured (Polygon for intraday, Yahoo for daily)

## 🚀 Option 1: GitHub Actions (Recommended - Free & Easy)

GitHub Actions can call your trigger endpoint every 5 minutes automatically.

### Setup Steps:

1. **Commit and push the workflow**:
   ```bash
   git add .github/workflows/backfill-cron.yml
   git commit -m "Add backfill worker cron via GitHub Actions"
   git push
   ```

2. **Enable Actions** (if not already enabled):
   - Go to: https://github.com/YOUR_USERNAME/SwiftBolt_ML/actions
   - Click "I understand my workflows, go ahead and enable them"

3. **Manually test**:
   - Go to Actions → Backfill Worker Cron → Run workflow
   - Click "Run workflow" to test immediately

4. **Monitor**:
   - The workflow runs every 5 minutes automatically
   - Each run triggers 4 chunks to be processed
   - Check progress in your database (see monitoring queries below)

**Pros**: Free, integrated with your repo, easy to set up
**Cons**: 5-minute minimum interval (vs 1-minute with cron-job.org)

---

## 🚀 Option 2: Cron-job.org (1-Minute Interval)

For faster processing, use cron-job.org's free tier.

### Setup Steps:

1. **Sign up**: Go to https://cron-job.org/en/signup/

2. **Create a cron job**:
   - Title: `SwiftBolt Backfill Worker`
   - URL: `https://cygflaemtmwiwaviclks.supabase.co/functions/v1/trigger-backfill`
   - Schedule: Every 1 minute
   - HTTP Method: POST
   - Request headers: `Content-Type: application/json`
   - Request body: `{}`

3. **Enable the job** and it will start running immediately

**Pros**: 1-minute interval (faster backfill), reliable
**Cons**: Requires external service signup

---

## 🚀 Option 3: EasyCron (Alternative)

Another free option with generous limits.

### Setup Steps:

1. **Sign up**: Go to https://www.easycron.com/

2. **Create a cron job**:
   - URL: `https://cygflaemtmwiwaviclks.supabase.co/functions/v1/trigger-backfill`
   - When: Every 1 minute
   - HTTP Method: POST
   - Enable: Yes

**Pros**: Simple UI, reliable
**Cons**: Another service to manage

---

## 🚀 Option 4: Manual Testing (Development)

For testing, you can trigger the backfill manually:

### Using curl:
```bash
curl -X POST "https://cygflaemtmwiwaviclks.supabase.co/functions/v1/trigger-backfill"
```

### Using your browser:
Just visit: https://cygflaemtmwiwaviclks.supabase.co/functions/v1/trigger-backfill

---

## 📊 Monitor Progress

Run these queries in your [Supabase SQL Editor](https://supabase.com/dashboard/project/cygflaemtmwiwaviclks/sql):

### Overall Status
```sql
SELECT
  symbol,
  status,
  progress,
  (SELECT COUNT(*) FROM backfill_chunks WHERE job_id = j.id AND status = 'done') as done,
  (SELECT COUNT(*) FROM backfill_chunks WHERE job_id = j.id AND status = 'pending') as pending,
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

### Bars Inserted
```sql
SELECT
  s.ticker,
  b.timeframe,
  b.provider,
  COUNT(*) as total_bars,
  MIN(b.ts)::date as earliest,
  MAX(b.ts)::date as latest,
  ROUND(EXTRACT(EPOCH FROM (MAX(b.ts) - MIN(b.ts))) / 86400) as days_coverage
FROM ohlc_bars_v2 b
JOIN symbols s ON s.id = b.symbol_id
WHERE b.provider = 'polygon' AND b.is_forecast = false
GROUP BY s.ticker, b.timeframe, b.provider
ORDER BY s.ticker, b.timeframe;
```

---

## 📈 Expected Timeline

| Interval | Chunks/Hour | Total Time (2,615 chunks) |
|----------|-------------|---------------------------|
| 1 minute | ~240        | ~11 hours                 |
| 5 minutes| ~48         | ~55 hours (2.3 days)      |

**Note**: Polygon's 5 req/min rate limit is the bottleneck. Each chunk uses ~1 API call.

---

## 🔍 Troubleshooting

### No chunks processing?

1. **Check the trigger is being called**:
   - GitHub Actions: Check workflow runs
   - Cron-job.org: Check execution history
   - Manual: Run `curl -X POST https://cygflaemtmwiwaviclks.supabase.co/functions/v1/trigger-backfill`

2. **Check for errors**:
   ```sql
   SELECT symbol, day, last_error, try_count
   FROM backfill_chunks
   WHERE status = 'error'
   ORDER BY updated_at DESC;
   ```

3. **View edge function logs**:
   - Go to: https://supabase.com/dashboard/project/cygflaemtmwiwaviclks/functions
   - Click on `run-backfill-worker` → Logs

### Rate limit errors?

This is expected - the distributed token bucket handles this automatically. Failed chunks will retry.

---

## ✅ Success Checklist

- [ ] Choose a cron option (GitHub Actions, cron-job.org, EasyCron)
- [ ] Set up the scheduled job
- [ ] Verify it's calling the trigger (check logs or curl manually)
- [ ] Monitor progress with SQL queries
- [ ] Wait ~11-55 hours for complete 2-year backfill

---

## 🎯 Next Steps

Once backfill completes:

1. **Test your charts** with 2 years of data
2. **Add more symbols** with `seed_intraday_backfill_2yr('MSFT', 'h1')`
3. **Enjoy unlimited historical intraday charting!** 🚀

---

## 📝 Notes

- The backfill runs **automatically in the background**
- Your app works normally while backfilling
- Data appears in charts as soon as it's inserted
- You can pause/resume anytime by disabling/enabling the cron
