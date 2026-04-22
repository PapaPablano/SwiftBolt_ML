---
title: "Stale chart data: pg_cron vault secret mismatch + missing ingest-live job"
date: 2026-04-22
category: integration-issues
module: data ingestion
problem_type: integration_issue
component: database
symptoms:
  - Chart data stale across all timeframes during market hours
  - ingest-live pg_cron job missing entirely (migration never applied)
  - Four pg_cron jobs returning 401 due to null auth headers
  - GitHub Actions ingestion ran only 1 time in 40+ minutes despite */5 cron
root_cause: config_error
resolution_type: migration
severity: critical
tags:
  - pg-cron
  - vault-secrets
  - ingest-live
  - edge-functions
  - auth-401
  - stale-data
  - github-actions-cron
related_components:
  - background_job
---

# Stale Chart Data: pg_cron Vault Secret Mismatch + Missing ingest-live Job

## Problem

Chart data was stale across all timeframes during market hours. No OHLCV bars were being written to `ohlc_bars_v2` via the reliable pg_cron path, leaving GitHub Actions (which runs unreliably at sub-10-minute intervals) as the sole ingestion mechanism.

## Symptoms

- Chart data frozen across all timeframes (m15, h1, d1) during market hours
- No visible errors in the application UI — charts simply showed old candles
- Edge Function logs: `POST ingest-live → 401` and `POST run-backfill-worker → 401` every minute
- `cron.job_run_details` showed status "succeeded" for all jobs — **misleading**, because `net.http_post` returns success regardless of HTTP status code
- GitHub Actions `schedule-intraday-ingestion.yml` showed only 1 run in 40+ minutes despite `*/5` cron schedule

## What Didn't Work

- **Reducing GitHub Actions cron from 15min to 5min** — GitHub Actions deprioritizes scheduled workflows on repos with low recent commit activity. Even `*/5` cannot be trusted as a real-time data pipeline. (session history)
- **Deploying updated ingest-live code** — The Edge Function was correctly deployed with m15 bar support, but pg_cron never called it because the cron job didn't exist. Code changes are useless without the triggering infrastructure.

## Solution

**1. Fix vault secret name across all 6 broken pg_cron jobs:**

The vault secret was named `service_role`, but 4 cron jobs referenced `service_role_key`. Fix via SQL:

```sql
-- Example: fix backfill-worker vault reference
SELECT cron.unschedule('backfill-worker-every-minute');
SELECT cron.schedule(
  'backfill-worker-every-minute',
  '* * * * *',
  $$
    SELECT net.http_post(
      url := 'https://<project>.supabase.co/functions/v1/run-backfill-worker',
      headers := jsonb_build_object(
        'Content-Type', 'application/json',
        'X-SB-Gateway-Key', (SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = 'service_role')
      ),
      body := '{}',
      timeout_milliseconds := 29000
    );
  $$
);
```

**2. Create the missing ingest-live cron job:**

The migration `20260305000003_ingest_live_cron.sql` used `current_setting('app.supabase_url')` and `current_setting('app.sb_gateway_key')` — both were NULL. Created the job manually with hardcoded URL and vault-based auth:

```sql
SELECT cron.schedule(
  'ingest-live',
  '* 13-20 * * 1-5',
  $$
    SELECT net.http_post(
      url := 'https://<project>.supabase.co/functions/v1/ingest-live',
      headers := jsonb_build_object(
        'Content-Type', 'application/json',
        'X-SB-Gateway-Key', (SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = 'service_role')
      ),
      body := '{}'::jsonb,
      timeout_milliseconds := 29000
    );
  $$
);
```

**3. Add m15 bar ingestion to ingest-live:**

Extended `supabase/functions/ingest-live/index.ts` with a second pass (m15 bars) and third pass (Kalman forecast adjustment) after the existing m1 bar ingestion.

## Why This Works

- **Vault-based auth** reads the secret at runtime from `vault.decrypted_secrets`, bypassing `current_setting()` which requires explicit per-environment configuration that was never done
- **Correct vault name** (`service_role` not `service_role_key`) produces a valid JWT that Edge Functions accept via gateway-key comparison
- **pg_cron** fires reliably every minute during market hours — unlike GitHub Actions which is best-effort for scheduled workflows

## Prevention

- **Always verify pg_cron jobs exist after migrations:** `SELECT jobname, schedule, active FROM cron.job ORDER BY jobname;` — a migration file in git does not guarantee the job was created
- **Audit vault secret names against all pg_cron jobs:** `SELECT jobname, command FROM cron.job WHERE command LIKE '%vault%';` — check every vault reference matches actual secret names
- **Never trust `cron.job_run_details` status alone:** `net.http_post` returns success even on 401/500. Cross-reference with Edge Function logs: `mcp__plugin_supabase_supabase__get_logs` with `service: "edge-function"`
- **Prefer pg_cron over GitHub Actions** for any ingestion interval under 10 minutes — GitHub Actions cron is not reliable for low-activity repos
- **Avoid `current_setting()` in cron migrations** — use `vault.decrypted_secrets` directly, or verify settings exist before migration runs
- **Add this verification query to deploy checklists:**
  ```sql
  SELECT j.jobname,
    CASE WHEN jrd.status = 'succeeded' AND jrd.return_message = '1 row' THEN 'cron_ok'
         ELSE 'CHECK_LOGS' END as cron_status
  FROM cron.job j
  LEFT JOIN LATERAL (
    SELECT status, return_message FROM cron.job_run_details
    WHERE jobid = j.jobid ORDER BY start_time DESC LIMIT 1
  ) jrd ON true
  ORDER BY j.jobname;
  ```

## Related

- [Live partial candle synthesis timeframe coordination](../integration-issues/live-partial-candle-synthesis-timeframe-coordination.md) — covers the broader ingest-live → chart data flow; this doc covers the auth/infra failure that prevented it from running
- [AUTH_MATRIX.md](../../AUTH_MATRIX.md) — documents all Edge Function auth models including SB_GATEWAY_KEY rotation procedure
- GitHub Issue #9 — "Data Quality Issues Detected"
