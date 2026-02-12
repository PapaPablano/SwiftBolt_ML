# PostgreSQL Best Practices Implementation Plan

**Date:** February 12, 2026  
**Source:** Supabase Postgres Best Practices Rule + Project Audit  
**Reference:** `.cursor/rules/supabase-postgres-best-practices.mdc`, `docs/audits/SQL_PERFORMANCE_AUDIT.md`

---

## Executive Summary

This plan consolidates all recommendations from the PostgreSQL best practices audit of SwiftBolt ML. Implement in phases by priority. Each phase includes specific tasks, file locations, and SQL/code examples.

---

## Phase 1: Query Performance (CRITICAL)

### 1.1 BRIN Indexes for Time-Series Tables

**Objective:** Add BRIN indexes on large time-series tables (10-100x smaller than B-tree).

**Migration:** `supabase/migrations/20260212000000_add_brin_indexes_timeseries.sql`

| Table | Column | Index Name |
|-------|--------|------------|
| ohlc_bars_v2 | ts | idx_ohlc_v2_ts_brin |
| ohlc_bars_h4_alpaca | ts | idx_ohlc_h4_ts_brin |
| indicator_values | ts | idx_indicator_values_ts_brin |
| options_price_history | snapshot_at | idx_options_price_history_snapshot_brin |
| ml_forecasts_intraday | created_at | idx_ml_forecasts_intraday_created_brin |

Use `CREATE INDEX CONCURRENTLY` to avoid table locks during deployment.

### 1.2 Fix N+1 in data-health Edge Function

**Objective:** Replace per-symbol/timeframe loop with single batched RPC.

**Migration:** `supabase/migrations/20260212010000_get_latest_bars_batch_rpc.sql`

```sql
CREATE OR REPLACE FUNCTION get_latest_bars_batch(
  symbol_ids UUID[],
  timeframes TEXT[]
)
RETURNS TABLE (
  symbol_id UUID,
  timeframe TEXT,
  latest_ts TIMESTAMPTZ
) AS $$
  WITH ranked_bars AS (
    SELECT 
      symbol_id,
      timeframe,
      ts,
      ROW_NUMBER() OVER (
        PARTITION BY symbol_id, timeframe 
        ORDER BY ts DESC
      ) as rn
    FROM ohlc_bars_v2
    WHERE 
      symbol_id = ANY(symbol_ids)
      AND timeframe = ANY(timeframes)
      AND is_forecast = false
  )
  SELECT symbol_id, timeframe, ts as latest_ts
  FROM ranked_bars
  WHERE rn = 1;
$$ LANGUAGE SQL STABLE;
```

**Refactor:** `supabase/functions/data-health/index.ts` — replace loop with `supabase.rpc('get_latest_bars_batch', { symbol_ids, timeframes })`.

### 1.3 Composite Index for Multi-Leg Alerts

**Objective:** Optimize `strategy_id IN (...) AND resolved_at IS NULL` query.

**Migration:** Same as 1.2 or separate — `idx_multi_leg_alerts_unresolved` on `options_multi_leg_alerts(strategy_id, severity) WHERE resolved_at IS NULL`.

---

## Phase 2: Connection Management (CRITICAL)

### 2.1 Use Supabase Connection Pooler

- **`ml/config/settings.py`:** Add `database_pooler_url: str | None = None` (maps to `SUPABASE_DB_POOLER_URL`).
- **Docs:** Use pooler URL (port 6543) for direct Postgres connections; REST API via Supabase client uses pooler by default.
- **Reference:** [Supabase Connection Pooling](https://supabase.com/docs/guides/database/connecting-to-postgres#connection-pooler)

---

## Phase 3: Security & RLS (CRITICAL)

### 3.1 FORCE ROW LEVEL SECURITY

**Migration:** `supabase/migrations/20260212020000_force_rls_multi_tenant.sql`

For user-scoped tables:
- `options_strategies`
- `options_legs`
- `options_multi_leg_alerts`
- `options_strategy_metrics`
- `multi_leg_journal`
- `user_alert_preferences`

```sql
ALTER TABLE options_strategies FORCE ROW LEVEL SECURITY;
-- repeat for each table
```

---

## Phase 4: Schema Design (HIGH)

### 4.1 Primary Key Guidelines

For **new tables**:
- Single DB: `bigint generated always as identity primary key`
- Distributed/exposed IDs: UUIDv7 or ULID
- Avoid `gen_random_uuid()` for large-table PKs (causes index fragmentation)

---

## Phase 5: Data Access Patterns (MEDIUM)

### 5.1 Cursor-Based Pagination

**Files:**
- `ml/src/data/supabase_db.py` — `fetch_ohlc_bars` (lines 145–173)
- `ml/scripts/hourly_canary_summary.py` — `_fetch_forecasts` (lines 110–127)
- `ml/scripts/kalman_health_aggregator.py` — pagination loop (lines 51–67)

**Pattern:** Replace `offset += PAGE_SIZE` with cursor key (e.g. `ts < last_ts` or `created_at > last_created_at`). Cursor pagination is O(1); OFFSET scans all skipped rows.

### 5.2 Batch Inserts

Keep existing batch patterns (chunks of 500 for backfills). Document in this plan that bulk inserts should use 100–500 rows per statement.

---

## Phase 6: Monitoring & Diagnostics

### 6.1 EXPLAIN ANALYZE

Run periodically on hot queries:
```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT * FROM ohlc_bars_v2 
WHERE symbol_id = '...' AND timeframe = 'd1' AND is_forecast = false
ORDER BY ts DESC LIMIT 500;
```

Look for: Seq Scan on large tables, Rows Removed by Filter, Buffers read >> hit.

---

## Implementation Order

| Order | Phase | Effort | Impact |
|-------|-------|--------|--------|
| 1 | 1.1 BRIN indexes | Low | High |
| 2 | 1.2 N+1 fix | Medium | High |
| 3 | 5.1 Cursor pagination | Medium | Medium |
| 4 | 1.3 Multi-leg index | Low | Medium |
| 5 | 2.1 Pooler | Low | Medium |
| 6 | 3.1 FORCE RLS | Low | High |
| 7 | 4.1 Guidelines | Low | Long-term |
| 8 | 6.1 Monitoring | Low | Medium |

---

## Deliverables Checklist

- [x] Plan document (`ml/docs/POSTGRES_BEST_PRACTICES_IMPLEMENTATION_PLAN.md`)
- [x] Migration: BRIN indexes (`20260212000000_add_brin_indexes_timeseries.sql`)
- [x] Migration: get_latest_bars_batch RPC + multi-leg index (`20260212010000_get_latest_bars_batch_and_indexes.sql`)
- [x] Migration: FORCE RLS (`20260212020000_force_rls_multi_tenant.sql`)
- [x] Refactor: data-health index.ts (N+1 → batch RPC)
- [x] Refactor: supabase_db.py pagination (cursor-based)
- [x] Refactor: hourly_canary_summary.py pagination (cursor-based)
- [x] Refactor: kalman_health_aggregator.py pagination (cursor-based)
- [x] Config: database_pooler_url in settings + effective_database_url
- [x] Docs: DATABASE_CONNECTION.md
