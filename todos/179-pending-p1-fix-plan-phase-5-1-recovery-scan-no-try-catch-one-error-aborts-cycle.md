---
status: pending
priority: p1
issue_id: "179"
tags: [plan-review, live-trading, reliability, error-handling, financial-safety]
dependencies: []
---

# Fix Plan Phase 5.1: `recoverStuckPositions` has no try/catch — one error aborts the entire execution cycle

## Problem Statement

The plan adds `recoverStuckPositions` at the top of `executeLiveTradingCycle` but shows no `try/catch` wrapping it. If `recoverStuckPositions` throws (DB timeout, network error, `getOrderStatus` 404), the entire execution cycle aborts — no strategies run for that bar. Additionally, there is no per-position try/catch inside the recovery loop, so a single failing position prevents recovery of all subsequent positions in the same scan.

## Findings

**Spec-Flow Analyzer (GAP-P1-1):**

The plan's Phase 4.4 adds try/catch around `checkBracketFills` — the same pattern must be applied to `recoverStuckPositions`:

```typescript
// Phase 4.4 pattern (correct):
try {
  await checkBracketFills(supabase, token.access_token, accountId);
} catch (err) {
  console.error("bracket_fill_check_failed", { error: err.message });
  // continue — don't abort the cycle
}

// Phase 5.1 — plan shows NO try/catch:
await recoverStuckPositions(supabase, token.access_token, accountId);  // ← can abort cycle
```

**Second issue — no per-position try/catch inside the recovery loop:**

Inside `recoverStuckPositions`, the loop calls `getOrderStatus` and `cancelOrder`/`closeLivePosition` per position. `getOrderStatus` in `_shared/tradestation-client.ts` throws on non-200 responses (e.g. 404 if the order aged out of TradeStation's history window — common for orders placed days ago). Without a per-position catch, one bad position aborts recovery for all subsequent positions.

**Third issue — `getOrderStatus` will throw 404 for orders aged out of TradeStation history:**

TradeStation's order history API returns 404 for orders older than its retention window. A position stuck for more than ~24 hours could have an order ID that no longer exists in the broker API. The recovery scan must handle this case gracefully, not crash the loop.

**Correct pattern:**

```typescript
// At the call site in executeLiveTradingCycle:
try {
  await recoverStuckPositions(supabase, token.access_token, accountId);
} catch (err) {
  console.error("recovery_scan_failed", { error: err.message });
  // continue — recovery failure must not abort strategy execution
}

// Inside recoverStuckPositions, per-position loop:
for (const pos of stuckPositions) {
  try {
    // ... getOrderStatus, cancelOrder, closeLivePosition
  } catch (err) {
    console.error("recovery_position_failed", { positionId: pos.id, error: err.message });
    // continue to next position
  }
}
```

## Proposed Solution

Amend Phase 5.1 in the plan to add:
1. Top-level try/catch around the `recoverStuckPositions` call in `executeLiveTradingCycle`
2. Per-position try/catch inside the recovery loop body
3. A note that `getOrderStatus` 404 (order aged out) should be treated as "unknown state — emergency close" rather than a crash

## Acceptance Criteria

- [ ] `recoverStuckPositions` call in `executeLiveTradingCycle` is wrapped in try/catch that logs and continues (does not rethrow)
- [ ] Per-position loop body inside `recoverStuckPositions` has individual try/catch
- [ ] Plan documents how `getOrderStatus` 404 is handled (treat as order-not-found → emergency close)
- [ ] Pattern matches Phase 4.4's `checkBracketFills` try/catch pattern

## Work Log

- 2026-03-03: Finding from spec-flow-analyzer (GAP-P1-1) during plan review. Companion to #151 (wrong args, no concurrency guard) — this issue is specifically the missing error containment.
