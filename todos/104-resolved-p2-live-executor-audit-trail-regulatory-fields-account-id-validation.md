---
status: pending
priority: p2
issue_id: "104"
tags: [code-review, live-trading, compliance, audit-trail, security]
dependencies: []
---

# Audit trail missing regulatory fields + account_id has no format validation (SSRF risk)

## Problem Statement

Two related issues:

1. `live_trading_trades` is missing columns required for financial audit trails: `order_submitted_at` (distinct from fill time), `execution_venue`, `order_type`, `order_source`. Without these, post-incident reconstruction and regulatory compliance are impossible.

2. `account_id` and `futures_account_id` are stored as unconstrained `TEXT` in `broker_tokens`. These values are used in TradeStation API URL path construction. An attacker who can write to their own `broker_tokens` row can set `account_id` to a path-traversal string or another user's account number, causing API requests to hit unintended endpoints (SSRF / IDOR).

## Findings

**Security Sentinel (SEC-12 P2):** "For equity and futures trading, FINRA Rule 4511 and SEC Rule 17a-4 require broker-dealer audit trails to include: order submission time (distinct from fill time), the execution venue, the order type (market/limit/bracket), the source of the order."

**Security Sentinel (SEC-09 P2):** "account_id and futures_account_id are stored as unconstrained TEXT. If an attacker can write to their own broker_tokens row, they could set account_id to a path-traversal string. TradeStation account IDs are uppercase alphanumeric — add a CHECK constraint."

## Proposed Solutions

### Fix 1 — Add regulatory columns to live_trading_trades:
```sql
-- Add to CREATE TABLE live_trading_trades:
order_submitted_at  TIMESTAMPTZ NOT NULL,  -- when order was sent to TradeStation
execution_venue     TEXT NOT NULL DEFAULT 'tradestation',
order_type          TEXT NOT NULL DEFAULT 'market' CHECK (order_type IN ('market', 'limit', 'bracket')),
order_source        TEXT NOT NULL DEFAULT 'algorithm',  -- 'algorithm' or 'manual'
broker_fill_price   DECIMAL(12,4),  -- actual fill price from TradeStation (may differ from recorded price)
```

### Fix 2 — account_id format validation:
```sql
-- In broker_tokens definition:
account_id TEXT NOT NULL CHECK (account_id ~ '^[A-Z0-9]{4,15}$'),
futures_account_id TEXT CHECK (futures_account_id ~ '^[A-Z0-9]{4,15}$'),
```

And in `tradestation-client.ts`:
```typescript
function buildAccountUrl(accountId: string, path: string): string {
  if (!/^[A-Z0-9]{4,15}$/.test(accountId)) throw new Error('Invalid account ID format');
  return `${TS_BASE_URL}/brokerage/accounts/${encodeURIComponent(accountId)}${path}`;
}
```

## Technical Details

**Affected files:**
- `supabase/migrations/20260303110000_live_trading_tables.sql` — add regulatory columns + account_id CHECK
- `supabase/migrations/20260303100000_broker_tokens.sql` — add account_id format CHECK
- `supabase/functions/_shared/tradestation-client.ts` — URL builder with format validation

## Acceptance Criteria

- [ ] `order_submitted_at`, `execution_venue`, `order_type`, `order_source` added to `live_trading_trades`
- [ ] `broker_fill_price` column added (may differ from computed `exit_price`)
- [ ] `account_id` and `futures_account_id` have CHECK constraint enforcing `[A-Z0-9]{4,15}` format
- [ ] URL builder in `tradestation-client.ts` validates account ID format before use
- [ ] `order_submitted_at` populated with the time the API call is made (before awaiting fill)

## Work Log

- 2026-03-03: Finding created from Security Sentinel (SEC-12, SEC-09).
