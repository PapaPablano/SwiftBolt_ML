---
status: pending
priority: p2
issue_id: "101"
tags: [code-review, live-trading, security, rls, database]
dependencies: []
---

# Column-level security gaps on UPDATE policies — financial fields overwritable

## Problem Statement

Two UPDATE policies lack column-level restrictions:

1. `broker_tokens UPDATE USING (auth.uid() = user_id)` — allows overwriting `account_id`, `futures_account_id`, `access_token`, `refresh_token`. An attacker with a hijacked session can redirect live orders to a different account or inject a forged refresh token.

2. `live_trading_positions UPDATE USING (auth.uid() = user_id)` — allows overwriting `broker_order_id`, `entry_price`, `quantity`, `stop_loss_price`, `take_profit_price`. A frontend bug or compromise could manipulate position records to inflate P&L or defeat bracket monitoring.

## Findings

**Security Sentinel (SEC-06 P2):** "This policy allows any authenticated user to UPDATE their own broker_tokens row, including account_id and futures_account_id. An attacker who hijacks a session token... can overwrite account_id with a different account number, causing live orders to be routed to a different account."

**Security Sentinel (SEC-07 P2):** "A malicious or compromised frontend client could... overwrite broker_sl_order_id with a fake order ID, causing the bracket fill monitoring to fail silently."

## Proposed Solutions

**For broker_tokens:** Only `access_token`, `refresh_token`, `expires_at` should be updatable via the token refresh flow. `account_id`, `futures_account_id`, and `provider` should be immutable after initial INSERT.

Options:
- Add column-level privileges: `REVOKE UPDATE (account_id, futures_account_id, provider) ON broker_tokens FROM authenticated`
- Or use a `SECURITY DEFINER` function for all token updates, revoking direct UPDATE from authenticated role

**For live_trading_positions:** Only `current_price`, `updated_at`, and `status` (via the transition trigger) should be user-updatable. All financial fields should be immutable after INSERT.

Options:
- `WITH CHECK` constraints on the UPDATE policy
- Or revoke direct UPDATE entirely, route all updates through `SECURITY DEFINER` functions

## Technical Details

**Migration changes:**
```sql
-- broker_tokens: restrict to token refresh columns only
CREATE POLICY "broker_tokens_user_update" ON broker_tokens
  FOR UPDATE
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);
-- Plus column-level revoke:
REVOKE UPDATE (account_id, futures_account_id, provider, user_id) ON broker_tokens FROM authenticated;

-- live_trading_positions: restrict to price/status updates only
CREATE POLICY "live_positions_user_update" ON live_trading_positions
  FOR UPDATE
  USING (auth.uid() = user_id)
  WITH CHECK (
    auth.uid() = user_id
    -- financial fields unchanged:
    AND entry_price = OLD.entry_price
    AND quantity = OLD.quantity
    AND stop_loss_price = OLD.stop_loss_price
    AND take_profit_price = OLD.take_profit_price
    AND broker_order_id = OLD.broker_order_id
  );
```

## Acceptance Criteria

- [ ] `broker_tokens`: `account_id`, `futures_account_id`, `provider` cannot be updated by authenticated role
- [ ] `live_trading_positions`: `entry_price`, `quantity`, `stop_loss_price`, `take_profit_price`, `broker_order_id` cannot be updated after insert via RLS
- [ ] Status transition trigger (from todo #100) enforces valid state machine regardless of column-level policies

## Work Log

- 2026-03-03: Finding created from Security Sentinel (SEC-06, SEC-07).
