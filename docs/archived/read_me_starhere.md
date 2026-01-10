# SwiftBolt ML — Backfill Automation (Start Here)

This mini-doc set is meant to help automate your historical OHLC backfill so you stop manually running scripts, while staying inside free-tier API constraints and respecting rate limits. The core idea is to run an incremental backfill on a schedule (every 6 hours) and store bars in Supabase, matching the approach described in `backfill_system.md`. 

## What you’re setting up

- A scheduled runner (GitHub Actions) that executes every 6 hours.
- A backfill entrypoint in your repo (Python or TS) that:
  - Fetches historical bars in chunks (intraday ~1 month per chunk; daily+ larger chunks).
  - Respects provider rate limits (e.g., strict limits on Polygon/Massive).
  - Upserts into `ohlc_bars` using a unique constraint to dedupe.
- Optional: manual trigger support for one-off backfills.

## Files in this “paste pack”

You asked for these docs:

1. README_START_HERE.md (this file)
2. QUICK_START_CHECKLIST.md
3. GITHUB_ACTIONS_SETUP.md
4. FREE_BACKFILL_AUTOMATION_GUIDE.md
5. COST_COMPARISON_AND_RECOMMENDATION.md
6. IMPLEMENTATION_SUMMARY.md

They’re designed to be pasted into your repo under `docs/` (recommended), except the workflow YAML which goes under `.github/workflows/`.

## Prereqs you should confirm

- You have a GitHub repo for SwiftBolt_ML.
- Supabase project exists and contains:
  - `symbols` table
  - `ohlc_bars` table
  - index on `(symbol_id, timeframe, ts)`
  - unique constraint preventing duplicate bars
- You have API keys for:
  - Finnhub (free tier)
  - Polygon/Massive (free tier)
  - Yahoo Finance usage (if applicable to any scripts)

## The minimal end state

After setup, you should be able to:

1. Trigger a manual backfill from GitHub Actions (“Run workflow”).
2. See logs for the run in GitHub Actions.
3. Verify new rows in `ohlc_bars` in Supabase.
4. Let the workflow run every 6 hours automatically.

## Recommended repo layout

- `.github/workflows/backfill-ohlc.yml`
- `backend/scripts/backfill_ohlc.py` (or a TypeScript/Deno entrypoint if you prefer)
- `docs/`:
  - `docs/README_START_HERE.md`
  - `docs/QUICK_START_CHECKLIST.md`
  - `docs/GITHUB_ACTIONS_SETUP.md`
  - `docs/FREE_BACKFILL_AUTOMATION_GUIDE.md`
  - `docs/COST_COMPARISON_AND_RECOMMENDATION.md`
  - `docs/IMPLEMENTATION_SUMMARY.md`

## What to do next

Go to File 2: `QUICK_START_CHECKLIST.md` and follow it top-to-bottom. It’s designed to get you from zero → “automated every 6 hours” in about 30 minutes.
