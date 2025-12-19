
```md
# 30-Minute Quick Start — Automated Backfill (Every 6 Hours)

Goal: automate historical OHLC backfill so you don’t manually run scripts, while respecting free-tier provider limits and using Supabase as the cache, consistent with the approach in `backfill_system.md`. 

## What you’ll end with

- A GitHub Actions workflow that runs every 6 hours.
- Secure secrets stored in GitHub Actions secrets.
- A backfill entrypoint you can run locally AND via GitHub Actions.
- A quick SQL check to confirm bars are inserting and deduping correctly.

---

## Step 0 — Decide your backfill entrypoint (2 minutes)

Pick ONE:

A) Python script entrypoint (common if you already have ML scripts)
- Run command in workflow: `python -m scripts.backfill_ohlc --incremental`

B) Supabase Edge Function entrypoint (TypeScript/Deno)
- Run command in workflow: `curl -X POST https://.../functions/v1/backfill ...`

This checklist assumes **A (Python)** because it’s easiest to schedule, cheapest, and you already have Python in the project.

---

## Step 1 — Add the workflow file (5 minutes)

Create this file in your repo:

- `.github/workflows/backfill-ohlc.yml`

Use the YAML you already pasted earlier (every 6 hours). Confirm the cron line:

- `cron: "0 */6 * * *"`

Commit and push:

```
git add .github/workflows/backfill-ohlc.yml
git commit -m "ci: add scheduled backfill workflow"
git push
```

---

## Step 2 — Add GitHub secrets (5 minutes)

In GitHub:
- Repo → Settings → Secrets and variables → Actions → New repository secret

Add:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY` (service_role)
- `FINNHUB_API_KEY`
- `MASSIVE_API_KEY`

Notes:
- Never commit these keys.
- If you have a prod and dev Supabase, do this in the repo that maps to the environment you’re scheduling.

---

## Step 3 — Ensure the backfill command actually runs (10 minutes)

### 3.1 Confirm requirements install path
Your workflow currently has:

```
pip install -r backend/requirements.txt
```

If your repo uses a different file (e.g. `backend/requirements-ml.txt`), change the workflow accordingly.

### 3.2 Ensure the Python module exists
If you use:

```
python -m scripts.backfill_ohlc --incremental
```

Then in `backend/` you need:

- `backend/scripts/backfill_ohlc.py`
- `backend/scripts/__init__.py` (can be empty)

If you don’t want packages, change the workflow to:

```
python scripts/backfill_ohlc.py --incremental
```

### 3.3 Ensure it respects the limits described in backfill_system.md
The runtime logic should follow your documented plan:

- Intraday: fetch ~1 month per chunk
- Daily+: fetch ~6 months per chunk
- Delay between chunks: ~12 seconds to respect strict free tier limits (Polygon/Massive)
- Dedup via unique constraint on `(symbol_id, timeframe, ts)`

---

## Step 4 — Run a manual workflow test (5 minutes)

GitHub → Actions → “Automated OHLC Backfill” → Run workflow

Use inputs for a small test:
- symbol: `AAPL`
- timeframe: `h1`

Confirm:
- Workflow completes without errors
- Logs show inserts
- No repeated 429 rate limit spam

---

## Step 5 — Verify in Supabase (3 minutes)

Run a quick check (adjust names if your schema differs):

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

You should see increasing `bar_count` and a reasonable `newest_bar`.

---

## Step 6 — Let the schedule run (no effort)

Once the manual run passes:
- Do nothing.
- It will run automatically every 6 hours.

---

## If it fails (common fixes)

- “No such file requirements.txt”
  - Update workflow to correct requirements file path.
- “No module named scripts.backfill_ohlc”
  - Add `scripts/__init__.py` or switch to script path execution.
- “401/403 from Supabase”
  - Confirm `SUPABASE_SERVICE_KEY` is service_role and stored as secret.
- Provider 429 rate limits
  - Reduce symbols per run, reduce timeframes per run, increase inter-chunk delay.

