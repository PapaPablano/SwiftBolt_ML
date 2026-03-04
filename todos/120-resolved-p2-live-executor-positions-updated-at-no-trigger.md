---
status: pending
priority: p2
issue_id: "120"
tags: [code-review, live-trading, database, schema, monitoring]
dependencies: []
---

# `live_trading_positions.updated_at` has no auto-update trigger — stale timestamps break monitoring

## Problem Statement

`live_trading_positions.updated_at` is defined as `DEFAULT NOW()` (migration line 71) which only sets the value on INSERT. Any subsequent UPDATE (status changes, fill price updates, bracket order ID assignment) leaves `updated_at` frozen at the INSERT timestamp. The existing `update_updated_at_column()` function in `001_core_schema.sql` handles this for other tables but was not wired to `live_trading_positions`. Monitoring queries for "positions not updated in 30 minutes" (potential executor hang detection) will return false positives with stale timestamps.

## Findings

Data Integrity Guardian P2-A. The paper trading tables have this trigger pattern — it was missing from live.

## Proposed Solutions

**Option A (Recommended):** Add to the migration: `CREATE TRIGGER live_positions_updated_at BEFORE UPDATE ON live_trading_positions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();`. The `update_updated_at_column()` function already exists. One-liner fix. Effort: Small.

## Acceptance Criteria

- [ ] `live_trading_positions.updated_at` is automatically refreshed on every UPDATE
- [ ] Monitoring queries for stale positions return accurate timestamps
- [ ] The trigger uses the existing `update_updated_at_column()` function
