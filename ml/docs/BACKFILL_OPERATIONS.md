# OHLC Backfill Operations Guide

Production runbook for the automated OHLC backfill system.

---

## System Overview

**Purpose:** Automatically fetch and cache historical OHLC bars for watchlist symbols to support ML forecasting and options ranking.

**Components:**
- GitHub Actions workflow (`.github/workflows/backfill-ohlc.yml`)
- Python backfill script (`ml/src/scripts/backfill_ohlc.py`)
- Supabase `ohlc_bars` table
- Data provider: Polygon/Massive API (via `/chart` Edge Function)

**Schedule:** Every 6 hours (00:00, 06:00, 12:00, 18:00 UTC)

**Mode:** Incremental (only fetches new bars)

---

## Daily Operations

### Check Backfill Status

**Via GitHub Actions:**
1. Go to: `https://github.com/YOUR_USERNAME/SwiftBolt_ML/actions`
2. Find: "Automated OHLC Backfill"
3. Check latest run status (green = success, red = failure)

**Via SQL:**
```sql
-- Quick health check
SELECT
  s.ticker,
  MAX(o.ts) AS newest_bar,
  NOW()::date - MAX(o.ts)::date AS days_behind
FROM ohlc_bars o
JOIN symbols s ON s.id = o.symbol_id
WHERE o.timeframe = 'd1'
GROUP BY s.ticker
ORDER BY days_behind DESC;
```

**Expected:** All symbols should have `days_behind` ≤ 1.

---

## Manual Backfill Operations

### Backfill a Single Symbol

**Use case:** New symbol added to watchlist, or data gap detected.

**GitHub Actions:**
1. Go to Actions → "Automated OHLC Backfill"
2. Click "Run workflow"
3. Enter:
   - Symbol: `AAPL`
   - Timeframe: `d1`
4. Click "Run workflow"

**Local (for testing):**
```bash
cd ml
python src/scripts/backfill_ohlc.py --symbol AAPL --timeframe d1
```

### Backfill Multiple Symbols

**GitHub Actions:**
Not directly supported. Run multiple times or modify workflow.

**Local:**
```bash
cd ml
python src/scripts/backfill_ohlc.py --symbols AAPL NVDA TSLA --timeframe d1
```

### Full Backfill (Non-Incremental)

**Use case:** Rebuilding cache, or first-time setup.

**Local only (not in scheduled workflow):**
```bash
cd ml
# Without --incremental flag = full backfill
python src/scripts/backfill_ohlc.py --all --timeframe d1
```

**Warning:** This fetches ALL historical data and may hit rate limits.

---

## Troubleshooting

### Workflow Fails with "No module named config.settings"

**Cause:** Missing dependencies or incorrect Python path.

**Fix:**
1. Check `ml/requirements.txt` exists
2. Verify workflow installs from correct path:
   ```yaml
   pip install -r ml/requirements.txt
   ```

### Workflow Fails with "401 Unauthorized"

**Cause:** Invalid or missing Supabase secrets.

**Fix:**
1. Go to: GitHub repo → Settings → Secrets and variables → Actions
2. Verify these secrets exist:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
3. Values should match your Supabase project
4. Re-run workflow

### Workflow Fails with "Symbol not found in database"

**Cause:** Symbol doesn't exist in `symbols` table.

**Fix:**
```sql
-- Check if symbol exists
SELECT * FROM symbols WHERE ticker = 'AAPL';

-- If missing, insert it
INSERT INTO symbols (ticker, name, asset_type)
VALUES ('AAPL', 'Apple Inc.', 'stock')
ON CONFLICT (ticker) DO NOTHING;
```

### Provider 429 Rate Limit Errors

**Cause:** Too many API requests.

**Short-term fix:**
1. Reduce symbols per run (edit `WATCHLIST_SYMBOLS` in script)
2. Increase `RATE_LIMIT_DELAY` in `backfill_ohlc.py` (e.g., 5.0 seconds)

**Long-term fix:**
1. Split workflow into multiple smaller jobs
2. Run less frequently (every 12 hours)
3. Upgrade API plan (if needed)

### Data Gaps Detected

**Cause:** Missed scheduled runs, provider outage, or symbol was added mid-stream.

**Fix:**
```bash
# Manual full backfill for specific symbol
cd ml
python src/scripts/backfill_ohlc.py --symbol AAPL --timeframe d1
```

---

## Configuration Changes

### Add New Symbol to Watchlist

**Edit:** `ml/src/scripts/backfill_ohlc.py`

```python
WATCHLIST_SYMBOLS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META",
    "SPY", "QQQ", "CRWD", "PLTR", "AMD", "NFLX", "DIS",
    "SNOW"  # Add new symbol here
]
```

**Then:**
1. Commit and push change
2. Next scheduled run will include new symbol
3. Or manually trigger workflow for immediate backfill

### Change Schedule Frequency

**Edit:** `.github/workflows/backfill-ohlc.yml`

```yaml
schedule:
  - cron: "0 */12 * * *"  # Every 12 hours instead of 6
```

**Cron examples:**
- Every 6 hours: `"0 */6 * * *"`
- Every 12 hours: `"0 */12 * * *"`
- Daily at midnight: `"0 0 * * *"`
- Twice daily (6am, 6pm UTC): `"0 6,18 * * *"`

### Adjust Rate Limiting

**Edit:** `ml/src/scripts/backfill_ohlc.py`

```python
# Increase delay between symbols
RATE_LIMIT_DELAY = 5.0  # Was 2.0

# Increase delay between chunks
CHUNK_DELAY = 20.0      # Was 12.0
```

**When to adjust:**
- Getting 429 errors → increase delays
- Workflow too slow → decrease delays (carefully)

---

## Monitoring Best Practices

### Weekly Health Check

Run these queries weekly:

```sql
-- 1. Coverage check
SELECT COUNT(DISTINCT symbol_id) FROM ohlc_bars WHERE timeframe = 'd1';

-- 2. Freshness check
SELECT
  s.ticker,
  MAX(o.ts) AS newest_bar,
  NOW()::date - MAX(o.ts)::date AS days_behind
FROM ohlc_bars o
JOIN symbols s ON s.id = o.symbol_id
WHERE o.timeframe = 'd1'
GROUP BY s.ticker
HAVING NOW()::date - MAX(o.ts)::date > 1
ORDER BY days_behind DESC;

-- 3. Gap detection
-- (See BACKFILL_VALIDATION.md for full query)
```

### GitHub Actions Monitoring

**Set up notifications:**
1. GitHub repo → Settings → Notifications
2. Enable "Actions workflow failures"
3. Get email alerts when workflows fail

---

## Scaling Considerations

### When to Split Workloads

**Trigger:** Workflow runtime > 20 minutes or rate limit errors.

**Options:**

1. **Split by symbol groups:**
   - Workflow A: Symbols A-M
   - Workflow B: Symbols N-Z

2. **Split by timeframe:**
   - Workflow A: Daily bars (runs 4x/day)
   - Workflow B: Hourly bars (runs 2x/day)

3. **Use job queue pattern:**
   - Store backfill jobs in `backfill_queue` table
   - Worker processes queue gradually

---

## Rollback Procedure

### If Automated Backfill Breaks

**Immediate:**
1. Disable workflow:
   - Edit `.github/workflows/backfill-ohlc.yml`
   - Comment out `schedule:` section
   - Commit and push

**Recovery:**
1. Fix the issue (see Troubleshooting)
2. Test manually:
   ```bash
   cd ml
   python src/scripts/backfill_ohlc.py --symbol AAPL --timeframe d1 --incremental
   ```
3. Re-enable schedule in workflow
4. Monitor next scheduled run

---

## Security Notes

- **Never commit** API keys or secrets to git
- Use GitHub Secrets for all credentials
- Rotate API keys if exposed
- Use service role key (not anon key) for backfill
- Audit Supabase RLS policies if data visibility changes

---

## Support & Escalation

**Self-service:**
1. Check GitHub Actions logs
2. Review this runbook
3. Check Supabase logs (Dashboard → Edge Functions)

**Common issues:**
- See Troubleshooting section above
- See `BACKFILL_VALIDATION.md` for SQL queries

**When to escalate:**
- Persistent data corruption
- Unresolvable API quota issues
- Security concerns

---

## Related Documentation

- `BACKFILL_VALIDATION.md` - SQL queries for monitoring
- `FREE_BACKFILL_AUTOMATION_GUIDE.md` - Implementation templates
- `GITHUB_ACTIONS_SETUP.md` - Initial setup guide
- `docs/master_blueprint.md` - Overall architecture
