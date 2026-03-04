---
status: pending
priority: p2
issue_id: "172"
tags: [plan-review, live-trading, order-safety, financial-safety, typescript]
dependencies: []
---

# Fix Plan Phase 4.2: `cancelOrder` response not checked in insert-error recovery path — silent open position risk

## Problem Statement

The Phase 4.1 code uses `if (!cancelled.ok)` to detect `cancelOrder` failures after a TOCTOU conflict. The Phase 4.2 insert-error recovery path also calls `cancelOrder` (when a non-23505 DB error occurs after the entry order has been placed), but the plan does not apply the same `!cancelled.ok` check. If `cancelOrder` fails silently in the Phase 4.2 path, the entry order remains open at the broker with no corresponding position record in the database — an untracked open position with live financial exposure.

## Findings

**Security Sentinel (P2-Finding 5.2):**

Phase 4.1 pattern (applied correctly):
```typescript
// TOCTOU conflict path — correctly checks response:
const cancelled = await cancelOrder(accessToken, accountId, entryOrderId);
if (!cancelled.ok) {
  console.error("cancel_failed_toctou", { entryOrderId, status: cancelled.status });
  // alert/escalate
}
```

Phase 4.2 insert-error recovery (plan omits the check):
```typescript
// Non-23505 DB insert error — cancelOrder called but response NOT checked:
catch (insertError) {
  if (insertError.code !== "23505") {
    await cancelOrder(accessToken, accountId, entryOrderId);  // ← no !.ok check
    throw insertError;
  }
}
```

**Risk:** If `cancelOrder` returns a non-ok response (e.g., 404 because the order already partially filled, or 500 from TradeStation), the function throws `insertError` and returns. The caller has no record of the order. The position is now:
- **Open at TradeStation** (entry order executed or partially executed)
- **Missing from `live_trading_positions`** (DB insert failed)
- **Never recovered** (recovery scan only looks for positions in the DB)

This is the same risk as the Phase 4.1 TOCTOU path — but the Phase 4.1 `!cancelled.ok` check was added specifically to catch it there, and was not carried over to Phase 4.2.

Note: This is related to but distinct from todo #149 (which addresses the double-cancel catch nesting bug). #149 fixes the duplicate call; this issue requires the response check be added to the single correct cancel call.

## Proposed Solution

Apply the same `!cancelled.ok` pattern from Phase 4.1 to the Phase 4.2 insert-error recovery:

```typescript
catch (insertError) {
  if (insertError.code !== "23505") {
    const cancelled = await cancelOrder(accessToken, accountId, entryOrderId);
    if (!cancelled.ok) {
      // Position may be open at broker with no DB record — critical alert
      console.error("cancel_failed_insert_recovery", {
        entryOrderId,
        insertError: insertError.message,
        cancelStatus: cancelled.status,
      });
      // The recovery scan won't find this — it only queries live_trading_positions.
      // Manual intervention required. Consider writing a "phantom position" record
      // to an alert table for operator visibility.
    }
    throw insertError;
  }
}
```

Optionally: write a record to a `live_trading_alerts` table when `!cancelled.ok` so that the recovery scan or an operator can detect the orphaned order.

## Acceptance Criteria

- [ ] Phase 4.2 insert-error recovery applies `!cancelled.ok` check to the `cancelOrder` call
- [ ] Plan documents what operators should do when `cancelOrder` fails in this path (since the recovery scan cannot detect the order)
- [ ] Plan notes that this is a different issue from the double-cancel bug in todo #149

## Work Log

- 2026-03-03: Finding from security-sentinel (P2-Finding 5.2) during plan review. Related to #149 (double-cancel nesting) but the specific `!cancelled.ok` response-check gap in the insert-recovery path was not captured in any existing todo.
