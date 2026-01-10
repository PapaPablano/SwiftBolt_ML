
```md
# GitHub Actions Setup — Automated Backfill (Every 6 Hours)

This guide wires up an automated backfill job so you stop manually running scripts, while staying within free-tier API constraints and using Supabase as the historical cache (as described in `backfill_system.md`).

## What this sets up

- A GitHub Actions workflow scheduled every 6 hours
- Secure secrets for Supabase + providers
- A manual “Run workflow” trigger for testing
- A validation checklist to confirm data is landing in `ohlc_bars`

---

## Repo prerequisites

Your repo should already have (or you should add):

- `.github/workflows/` directory
- A backfill runner:
  - Python: `backend/scripts/backfill_ohlc.py` (recommended)
  - or TS/Deno: Supabase Edge Function backfill endpoint
- A requirements file:
  - `backend/requirements.txt` or `backend/requirements-ml.txt`

---

## Step 1 — Add the workflow file

Create:

- `.github/workflows/backfill-ohlc.yml`

Use the workflow you pasted earlier and confirm the cron is set to every 6 hours:

```
schedule:
  - cron: "0 */6 * * *"
```

Commit and push:

```
git add .github/workflows/backfill-ohlc.yml
git commit -m "ci: scheduled backfill every 6 hours"
git push
```

---

## Step 2 — Configure secrets (required)

GitHub:
- Repo → Settings → Secrets and variables → Actions → New repository secret

Add:

1. `SUPABASE_URL`
   - Example: `https://YOUR_PROJECT.supabase.co`

2. `SUPABASE_SERVICE_KEY`
   - The `service_role` key from Supabase (treat as root credential)

3. `FINNHUB_API_KEY`
   - Finnhub free tier key

4. `MASSIVE_API_KEY`
   - Polygon/Massive free tier key

Important:
- Do not store secrets in `.env` committed to git.
- Do not print secrets in logs.
- If you have dev/prod, ensure the repo/environment maps correctly.

---

## Step 3 — Make sure the workflow command matches your repo

Your workflow likely runs something like:

```
cd backend
python -m scripts.backfill_ohlc --incremental
```

That requires:

- `backend/scripts/backfill_ohlc.py`
- `backend/scripts/__init__.py` (can be empty)

If you don’t want package-style execution, change the workflow to:

```
cd backend
python scripts/backfill_ohlc.py --incremental
```

### Requirements file path
If your repo uses `backend/requirements-ml.txt`, update the workflow:

```
pip install -r backend/requirements-ml.txt
```

---

## Step 4 — First run (manual test)

Before trusting the schedule, do a small test.

GitHub:
- Actions tab → “Automated OHLC Backfill” → Run workflow

Inputs:
- symbol: `AAPL`
- timeframe: `h1` (or `d1`)

What to look for in logs:
- No import/module errors
- No missing requirements file errors
- No Supabase auth errors
- Inserts happening (or dedupe happening if you re-run)

---

## Step 5 — Validate in Supabase

### Quick verification query
Run in Supabase SQL editor:

```
SELECT
  s.ticker,
  o.timeframe,
  COUNT(*) AS bar_count,
  MIN(o.ts) AS oldest_bar,
  MAX(o.ts) AS newest_bar
FROM ohlc_bars o
JOIN symbols s ON s.id = o.symbol_id
WHERE s.ticker = 'AAPL'
GROUP BY s.ticker, o.timeframe
ORDER BY o.timeframe;
```

Expected:
- `bar_count` is > 0
- `newest_bar` moves forward over time (or is already near “now”)

### Check for gaps / missing ranges (optional)
If you store intraday, check for large holes:

```
SELECT
  s.ticker,
  o.timeframe,
  MAX(o.ts) - MIN(o.ts) AS coverage_span,
  COUNT(*) AS bars
FROM ohlc_bars o
JOIN symbols s ON s.id = o.symbol_id
WHERE s.ticker = 'AAPL'
GROUP BY s.ticker, o.timeframe
ORDER BY o.timeframe;
```

---

## Rate limit / chunking expectations (sanity checks)

From your backfill design:
- Intraday windowing is roughly “1 month per request”
- A strict provider may require delays between chunks (example: 12 seconds to respect ~5 req/min)
- Dedup is handled by a unique constraint in the database

If you see 429s:
- Reduce the number of symbols per run
- Backfill fewer timeframes per run
- Increase sleep/delay between requests

---

## Common failures & fixes

### “No such file or directory: backend/requirements.txt”
Fix:
- Update workflow `pip install -r ...` path to the correct file.

### “No module named scripts.backfill_ohlc”
Fix:
- Add `backend/scripts/__init__.py`, OR
- Run the script by path (`python scripts/backfill_ohlc.py ...`).

### “401 Unauthorized” or “invalid JWT” calling Supabase
Fix:
- Confirm `SUPABASE_SERVICE_KEY` is the service role key (not anon).
- Confirm `SUPABASE_URL` matches your project.

### “Symbol not found in database”
Fix:
- Ensure `symbols` table contains the ticker you tested (seed it if needed).

### Provider 429 rate limiting
Fix:
- Add backoff and/or longer delay between provider calls.
- Run fewer symbols per job.
- Prefer incremental backfill (only missing ranges).

---

## Operational tips

- Keep the scheduled job incremental; reserve deep historical fills for a manual run.
- Add a “max symbols per run” limit if you expect watchlist growth.
- Keep logs short but structured (counts, oldest/newest timestamps, inserted vs skipped).
- If you later add “auto-trigger on watchlist add” (server-side), keep the scheduled job as a safety net.

---

## Next file

Reply “next” to get File 4/6: `FREE_BACKFILL_AUTOMATION_GUIDE.md`.
```
