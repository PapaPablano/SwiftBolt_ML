---
status: resolved
priority: p1
issue_id: "149"
tags: [plan-review, live-trading, order-safety, financial-safety]
dependencies: []
---

# Fix Plan Phase 4.2: Double-cancel on non-23505 DB errors due to catch nesting

## Problem Statement

The fix plan's Phase 4.2 code snippet contains a logical flaw where `cancelOrder` is called twice for non-23505 DB insert errors. The catch block fires on the deliberately re-thrown `insertError`, causing a second cancel attempt on the same `entryOrderId`. This must be corrected in the plan before implementation.

## Findings

**Architecture Strategist + TypeScript Reviewer (P1):**

The proposed code structure:

```typescript
try {
  const { error: insertError } = await supabase.from(...).insert({...});
  if (insertError) {
    if (insertError.code === "23505") {
      await cancelOrder(token, accountId, entryOrderId);  // [A]
    } else {
      await cancelOrder(token, accountId, entryOrderId);  // [B]
      throw insertError;                                   // [C] → falls to catch
    }
  }
} catch (e) {
  await cancelOrder(token, accountId, entryOrderId);       // [D] fires again!
  throw e;
}
```

On non-23505 DB errors: path [B] fires (first cancel), then [C] throws `insertError`, which is caught by the outer catch, which fires path [D] (second cancel on same order ID). Two broker cancel calls for one order.

When Phase 4.1's `cancelOrder` response check is also implemented, the second cancel returns a 404 from TradeStation (order already cancelled), which will log a spurious `cancelOrder failed (404)` error, masking the real DB error.

## Proposed Solutions

**Recommended Fix — Use a flag to prevent double-cancel:**

```typescript
let cancelCalled = false;
const cancelOnce = async () => {
  if (!cancelCalled) {
    cancelCalled = true;
    const cancelled = await cancelOrder(token.access_token, accountId, entryOrderId);
    if (!cancelled.ok) {
      console.error(`[live-executor] cancelOrder failed (${cancelled.status})`);
    }
  }
};

const { error: insertError } = await supabase.from("live_trading_positions").insert({...});
if (insertError) {
  await cancelOnce();
  if (insertError.code !== "23505") {
    throw insertError;
  }
  // 23505 = duplicate position already exists, normal race condition
}
```

This eliminates the double-cancel by moving the cancel before the conditional throw, outside any try/catch that would catch the rethrow.

**Alternative — Secondary error handling for cancel failure (recommended addition):**

```typescript
try {
  await cancelOrder(token.access_token, accountId, entryOrderId);
} catch (cancelErr) {
  console.error("[live-executor] CRITICAL: cancelOrder threw — position may be untracked", cancelErr);
  // Alert ops — market order remains live with no DB record
}
```

## Acceptance Criteria

- [x] Phase 4.2 code snippet updated in the plan so cancelOrder is called exactly once per error path
- [x] Secondary error handling added if cancelOrder itself throws
- [x] 23505 duplicate case still calls cancelOrder (existing position wins)
- [x] Non-23505 errors still propagate after cancel

## Work Log

- 2026-03-03: Finding from architecture-strategist (P1-1) and kieran-typescript-reviewer (P1-2) during plan review.
- 2026-03-03: Resolved — plan amended with corrected code snippets, acceptance criteria updated.

- 2026-03-03: RESOLVED. Plan amended to address all findings.
