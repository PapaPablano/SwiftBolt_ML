
```md
## Implementation templates

This section provides copy/paste templates and “contracts” that keep the system reliable under free-tier constraints.

---

## Template: GitHub Actions workflow (6-hour schedule)

This is the canonical template (Linux runner, 6-hour cron). It assumes a Python entrypoint in `backend/`.

```
name: Automated OHLC Backfill

on:
  schedule:
    - cron: "0 */6 * * *"
  workflow_dispatch:
    inputs:
      symbol:
        description: "Optional (AAPL). Blank = all."
        required: false
        type: string
      timeframe:
        description: "Optional (h1). Blank = all."
        required: false
        type: string

jobs:
  backfill:
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          pip install -r backend/requirements.txt

      - name: Backfill (scheduled)
        if: github.event_name == 'schedule'
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
          FINNHUB_API_KEY: ${{ secrets.FINNHUB_API_KEY }}
          MASSIVE_API_KEY: ${{ secrets.MASSIVE_API_KEY }}
        run: |
          cd backend
          python -m scripts.backfill_ohlc --incremental

      - name: Backfill (manual)
        if: github.event_name == 'workflow_dispatch'
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
          FINNHUB_API_KEY: ${{ secrets.FINNHUB_API_KEY }}
          MASSIVE_API_KEY: ${{ secrets.MASSIVE_API_KEY }}
        run: |
          cd backend

          SYMBOL="${{ github.event.inputs.symbol }}"
          TIMEFRAME="${{ github.event.inputs.timeframe }}"

          ARGS="--incremental"
          if [ -n "$SYMBOL" ]; then ARGS="$ARGS --symbol=$SYMBOL"; fi
          if [ -n "$TIMEFRAME" ]; then ARGS="$ARGS --timeframe=$TIMEFRAME"; fi

          python -m scripts.backfill_ohlc $ARGS
```

Notes:
- Use Ubuntu (Linux) runners to minimize cost/minutes.
- If your repo is private, GitHub Free includes 2,000 minutes/month for GitHub-hosted runners. [web:33]
- Public repos have free Actions usage on standard runners. [web:33]

---

## Backfill runner contract (minimum expectations)

Regardless of language, your backfill runner should:

1. Be idempotent
- Safe to re-run (dedupe at DB layer).
- Avoid inserting duplicates; rely on unique constraint.

2. Support incremental runs
- Only fetch missing date ranges by default.

3. Implement chunking rules
- Intraday: chunk roughly 1 month per request.
- Daily+: chunk larger ranges (e.g., 6 months).
- Respect your documented “delay between chunks” approach for strict providers. 

4. Emit structured logging
- symbol, timeframe
- date range
- provider used
- inserted_count, skipped_count
- elapsed time
- number of requests made

5. Exit codes matter
- non-zero exit on “hard failure” so GitHub Actions shows red.

---

## If you outgrow a single run: split workloads

### Pattern 1: Split by symbol groups
- Workflow A: symbols 1–50
- Workflow B: symbols 51–100

### Pattern 2: Split by timeframe cost
- Run intraday timeframes less frequently or with fewer symbols.
- Run daily/weekly more broadly (they’re cheaper).

### Pattern 3: “Queue then work”
- Scheduler enqueues small jobs
- Worker processes jobs slowly across runs

This is the cleanest way to scale without rate-limit spikes.

---

## Supabase scheduling (pg_cron + pg_net) example

Supabase supports `pg_cron` and `pg_net` so Postgres can call an Edge Function on a schedule. [web:27]

This is useful if you want to avoid GitHub Actions.

High-level steps:
1) Store function URL + key in Vault.
2) Create a `cron.schedule(...)` job that calls `net.http_post(...)`.

Example (from Supabase docs, adjust names and keys):

```
-- Store project URL + publishable key in Vault
select vault.create_secret('https://PROJECT_REF.supabase.co', 'project_url');
select vault.create_secret('YOUR_SUPABASE_PUBLISHABLE_KEY', 'publishable_key');

-- Call an Edge Function every minute (example cadence)
select
  cron.schedule(
    'invoke-function-every-minute',
    '* * * * *',
    $$
    select
      net.http_post(
        url := (select decrypted_secret from vault.decrypted_secrets where name = 'project_url')
               || '/functions/v1/function-name',
        headers := jsonb_build_object(
          'Content-type', 'application/json',
          'Authorization', 'Bearer ' || (select decrypted_secret from vault.decrypted_secrets where name = 'publishable_key')
        ),
        body := concat('{"time": "', now(), '"}')::jsonb
      ) as request_id;
    $$
  );
``` 

To adapt this to backfill:
- Replace `function-name` with your backfill function route.
- Use a token that authorizes the call (Vault is recommended). [web:27]
- Schedule every 6 hours with cron: `0 */6 * * *`

---

## External HTTP cron (cron-job.org) secure trigger pattern

cron-job.org can trigger a URL periodically for free. [web:9]

Recommended security:
- Use a dedicated secret token header, e.g. `X-Backfill-Token: <random>`
- Validate that header in your endpoint.
- Rate-limit or queue work inside your endpoint.

Avoid:
- Exposing an unprotected backfill endpoint.

---

## Monitoring checklist (minimum)

Use your existing monitoring query ideas (bars per symbol/timeframe, oldest/newest). Your backfill doc already includes a “Count bars per symbol/timeframe” query. [file:1]

Add one more table if you want clear ops:
- `job_runs`:
  - job_name
  - started_at
  - finished_at
  - status
  - inserted_count
  - error_message

This is optional but makes failures obvious.

---

## Final recommendation (practical)

Start with GitHub Actions:
- It matches the “scheduled nightly backfill job” idea you documented, and running every 6 hours just tightens freshness. [file:1]
- It is fast to test and easy to debug.

Only move to Supabase scheduling or an external HTTP cron if:
- You can’t use GitHub Actions, or
- You prefer keeping all scheduling inside Supabase. [web:27]
```
