# 🚀 Quick Start: Backfill Setup

Your multi-provider pipeline is ready! Just set up the cron job to start the automatic 2-year backfill.

## ✅ What's Done

- Database migrations applied ✓
- Edge functions deployed ✓
- 2,615 chunks seeded (5 symbols × 523 days) ✓
- Polygon routing configured ✓

## 🎯 One-Time Setup (Choose One Option)

### Option 1: GitHub Actions (5-minute interval, free)

1. **Enable the workflow** (already committed):
   ```bash
   git add .github/workflows/backfill-cron.yml
   git commit -m "Add backfill cron"
   git push
   ```

2. **Go to Actions** and enable workflows:
   https://github.com/YOUR_USERNAME/SwiftBolt_ML/actions

3. **Run once manually** to test:
   - Click "Backfill Worker Cron"
   - Click "Run workflow"

**Done!** It runs every 5 minutes automatically.

---

### Option 2: Cron-job.org (1-minute interval, faster)

1. **Sign up**: https://cron-job.org/en/signup/

2. **Create job**:
   - URL: `https://cygflaemtmwiwaviclks.supabase.co/functions/v1/trigger-backfill`
   - Schedule: Every 1 minute
   - Method: POST
   - Add header: `Authorization: Bearer YOUR_ANON_KEY`
     - Get anon key from: https://supabase.com/dashboard/project/cygflaemtmwiwaviclks/settings/api
   - Body: `{}`

**Done!** Backfill starts immediately.

---

### Option 3: Manual Testing

Test manually anytime:

```bash
# Get your anon key from: https://supabase.com/dashboard/project/cygflaemtmwiwaviclks/settings/api
export SUPABASE_ANON_KEY="your-anon-key-here"

curl -X POST "https://cygflaemtmwiwaviclks.supabase.co/functions/v1/trigger-backfill" \
  -H "Authorization: Bearer $SUPABASE_ANON_KEY"
```

---

## 📊 Monitor Progress

```sql
-- Overall status (run in SQL Editor)
SELECT
  symbol,
  progress,
  (SELECT COUNT(*) FROM backfill_chunks WHERE job_id = j.id AND status = 'done') as done,
  (SELECT COUNT(*) FROM backfill_chunks WHERE job_id = j.id) as total
FROM backfill_jobs j;

-- Check bars inserted
SELECT
  s.ticker,
  COUNT(*) as bars,
  MIN(b.ts)::date as earliest,
  MAX(b.ts)::date as latest
FROM ohlc_bars_v2 b
JOIN symbols s ON s.id = b.symbol_id
WHERE b.provider = 'polygon'
GROUP BY s.ticker;
```

---

## ⏱️ Timeline

- **With 1-min cron**: ~11 hours for full 2-year backfill
- **With 5-min cron**: ~55 hours (2.3 days)

The backfill runs automatically in the background while you use the app!

---

## 🎉 That's It!

Your system now automatically backfills 2 years of Polygon intraday data. Charts will show historical data as soon as it's inserted.

**Questions?** Check logs in:
- https://supabase.com/dashboard/project/cygflaemtmwiwaviclks/functions

**Add more symbols**:
```sql
SELECT seed_intraday_backfill_2yr('MSFT', 'h1');
```
