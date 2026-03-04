---
status: resolved
priority: p2
issue_id: "188"
tags: [plan-review, live-trading, financial-safety, broker-integration, order-safety]
dependencies: []
---

# Fix Plan: `checkBracketFills` does not cancel the opposite bracket leg when one fills — orphaned order creates untracked position risk

## Problem Statement

When the SL fills, the TP order remains live at the broker. When the TP fills, the SL order remains live. `closeLivePositionFromBracket` closes the DB position record but does not call `cancelOrder` on the unfilled leg. If price reverses after an SL fill, the orphaned TP order could re-open a position at the broker with no corresponding DB record — an untracked live position with real financial exposure.

## Findings

**Spec-Flow Analyzer (GAP-P2-6):**

`checkBracketFills` at line 586 of `index.ts` detects which leg filled:
```typescript
if (orderStatuses.sl?.filled) {
  await closeLivePositionFromBracket(supabase, pos, slFillPrice, "SL_HIT");
  // ← TP order remains live at broker!
}
if (orderStatuses.tp?.filled) {
  await closeLivePositionFromBracket(supabase, pos, tpFillPrice, "TP_HIT");
  // ← SL order remains live at broker!
}
```

**Key question: Does TradeStation's `BRK` order type auto-cancel the opposite leg?**

The plan uses `BRK` (bracket) order type for bracket placement. If TradeStation's `BRK` group is implemented as OCO (One Cancels Other), the broker automatically cancels the opposite leg when one fills. In that case, this issue is a non-problem — the broker handles it.

If `BRK` is NOT OCO, the orphaned leg is a real risk:
- SL fills → position closed in DB → TP order still live
- Price reverses sharply → TP executes → new long position opened at broker
- DB has no record of this new position → `checkBracketFills` will not find it

**Test to determine TradeStation `BRK` behavior:**
1. Place a paper bracket order on SIM
2. Manually trigger the SL leg to fill
3. Check TradeStation order management — is the TP order automatically cancelled?

**If BRK is OCO (auto-cancel):** No code change needed; add a comment to `closeLivePositionFromBracket` noting that the broker handles OCO cancellation.

**If BRK is NOT OCO (manual cancel needed):**
```typescript
if (orderStatuses.sl?.filled) {
  await closeLivePositionFromBracket(supabase, pos, slFillPrice, "SL_HIT");
  // Cancel the unfilled TP leg
  if (pos.broker_tp_order_id) {
    const cancelled = await cancelOrder(accessToken, accountId, pos.broker_tp_order_id);
    if (!cancelled.ok) {
      console.error("cancel_opposite_leg_failed", {
        filledLeg: "SL", cancelledLeg: "TP", orderId: pos.broker_tp_order_id,
      });
    }
  }
}
```

## Proposed Solution

Amend the plan to explicitly address opposite-leg cancellation in `checkBracketFills`:
1. Document whether TradeStation `BRK` order type is OCO (auto-cancel) — verify with a SIM test
2. If not OCO: add explicit `cancelOrder` calls for the unfilled leg after each fill detection
3. Add `broker_tp_order_id` and `broker_sl_order_id` to the position model if not already stored (needed to cancel specific legs)

## Acceptance Criteria

- [x] Plan documents whether TradeStation `BRK` order type is OCO (confirmed via SIM test or API docs)
- [x] If not OCO: `cancelOrder` added for opposite leg in both SL-fill and TP-fill branches
- [x] Plan stores `broker_sl_order_id` and `broker_tp_order_id` in `live_trading_positions` so opposite-leg IDs are available at fill detection time
- [x] `cancelOrder` failure on opposite-leg cancel is logged as an alert (not silent)

## Work Log

- 2026-03-03: Finding from spec-flow-analyzer (GAP-P2-6) during plan review. Whether this is a real risk depends on TradeStation BRK OCO behavior — the plan must document this determination.

- 2026-03-03: RESOLVED. Plan amended to address all findings.
