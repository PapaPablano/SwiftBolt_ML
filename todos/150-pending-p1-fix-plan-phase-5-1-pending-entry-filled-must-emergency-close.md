---
status: pending
priority: p1
issue_id: "150"
tags: [plan-review, live-trading, state-machine, financial-safety]
dependencies: []
---

# Fix Plan Phase 5.1: `pending_entry` + filled recovery must emergency-close, not advance to `open`

## Problem Statement

The fix plan's Phase 5.1 recovery scan advances a filled `pending_entry` position directly to `status='open'` when brackets were never placed. An `open` position without `broker_sl_order_id`/`broker_tp_order_id` is completely unprotected — it has no SL or TP orders at the broker. The main cycle's `checkBracketFills` silently skips it every cycle. This puts real capital at risk with no automated exit protection.

## Findings

**Architecture Strategist (P1-2):**

The plan's `pending_entry` + filled branch (Phase 5.1, lines ~336–342):

```typescript
// WRONG — plan advances to open without bracket protection
await supabase.from("live_trading_positions")
  .update({ status: "open", entry_price: fill.fillPrice })
  .eq("id", pos.id).eq("status", "pending_entry");
console.error(`[live-executor] ALERT: Position ${pos.id} recovered from pending_entry — no brackets placed`);
```

The `pending_bracket` branch in the same section correctly calls `closeLivePosition`. A filled `pending_entry` that never reached bracket placement is in the SAME dangerous state as `pending_bracket` — live capital with no automated protection. The only difference is what happened in the past (bracket placement started vs not started). The correct recovery action is identical: emergency close immediately.

## Proposed Solution

Change the `pending_entry` + filled branch to emergency-close, identical to `pending_bracket`:

```typescript
// CORRECT
if (pos.status === "pending_entry" && orderStatus.filledQuantity > 0) {
  // Entry filled but brackets were never placed — emergency close
  // Same action as pending_bracket: cannot leave capital exposed
  console.error(
    `[live-executor] CRITICAL: Position ${pos.id} filled in pending_entry but no brackets placed. Emergency closing.`
  );
  await closeLivePosition(
    supabase,
    token.access_token,
    pos.account_id,
    pos,
    pos.current_price ?? pos.entry_price,
    "emergency_close",
    pos.symbol_id,
  );
} else if (pos.status === "pending_entry" && orderStatus.filledQuantity === 0) {
  // Entry never filled — cancel the order and set cancelled
  await cancelOrder(token.access_token, pos.account_id, pos.broker_order_id!);
  await supabase.from("live_trading_positions")
    .update({ status: "cancelled" })
    .eq("id", pos.id).eq("status", "pending_entry");
}
```

Note: `pos.current_price` will be `null` for stuck `pending_entry` positions (price is only updated in the main cycle after brackets are confirmed). The fallback to `entry_price` is intentional and must be documented — the trade record will show `entry_price === exit_price` and P&L of approximately zero (minus slippage). Manual reconciliation is required for these emergency closes.

## Acceptance Criteria

- [ ] Phase 5.1 `pending_entry` + filled branch changed to `closeLivePosition`, not `update({status: 'open'})`
- [ ] Comment explains that current_price fallback to entry_price is expected and P&L needs reconciliation
- [ ] `pending_entry` + unfilled branch (order cancelled/rejected) still cancels the position
- [ ] Behavior is symmetric with the `pending_bracket` branch

## Work Log

- 2026-03-03: Finding from architecture-strategist (P1-2) during plan review.
