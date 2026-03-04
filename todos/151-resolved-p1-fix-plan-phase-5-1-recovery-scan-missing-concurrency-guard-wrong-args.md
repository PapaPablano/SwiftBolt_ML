---
status: resolved
priority: p1
issue_id: "151"
tags: [plan-review, live-trading, state-machine, concurrency, financial-safety]
dependencies: []
---

# Fix Plan Phase 5.1: Recovery scan missing concurrency guard + wrong `closeLivePosition` argument count

## Problem Statement

Two related bugs in the Phase 5.1 `recoverStuckPositions` proposal:

1. **No concurrency guard**: Two concurrent Edge Function invocations can both detect the same stuck `pending_bracket` position and both call `closeLivePosition`, placing two market close orders for real money at the broker.

2. **Wrong argument signature**: The plan calls `closeLivePosition(supabase, pos, pos.current_price, "emergency_close")` but the actual function signature requires 7 arguments: `(supabase, accessToken, accountId, position, exitPrice, closeReason, tsSymbol)`.

## Findings

**Architecture Strategist (P1-3):**

The existing `closeLivePositionFromBracket` (called by `closeLivePosition`) uses optimistic locking with `.eq("status", "open")` — but the recovery scan targets positions with `status IN ('pending_entry', 'pending_bracket')`. The optimistic lock does not protect `pending_bracket` transitions. Two concurrent invocations can:
1. Both fetch the same `pending_bracket` position
2. Both call `closeLivePosition`
3. Both call `placeMarketOrder` at the broker
4. Position receives two closing market orders

The correct fix requires a transitional status. Before any broker call, the recovery scan must atomically transition the position to a new `closing_emergency` intermediate status, and only proceed if that update affected exactly one row.

**TypeScript Reviewer (P1-7):**

Actual `closeLivePosition` signature at line 1067 of `index.ts`:

```typescript
async function closeLivePosition(
  supabase: any,
  accessToken: string,
  accountId: string,
  position: LivePosition,
  exitPrice: number,
  closeReason: string,
  tsSymbol: string,
): Promise<ExecutionResult>
```

The plan's call passes 4 arguments; the function requires 7. This is a compile error that would fail at deploy.

## Proposed Solution

Add optimistic status transition before any broker call:

```typescript
// Claim the position atomically before doing anything
const { data: claimed } = await supabase
  .from("live_trading_positions")
  .update({ status: "closing_emergency" })
  .eq("id", pos.id)
  .in("status", ["pending_entry", "pending_bracket"])  // only claim from valid recovery states
  .select()
  .single();

if (!claimed) {
  // Another invocation already claimed this position — skip
  continue;
}

// Now safe to proceed with broker call
await closeLivePosition(
  supabase,
  token.access_token,
  pos.account_id,           // ← missing in plan's pseudocode
  claimed,
  claimed.current_price ?? claimed.entry_price,
  "emergency_close",
  claimed.symbol_id,        // ← missing in plan's pseudocode
);
```

Note: requires adding `"closing_emergency"` to the `status` CHECK constraint in migration `20260303110000_live_trading_tables.sql` (or the fix migration).

## Acceptance Criteria

- [x] `recoverStuckPositions` uses optimistic status transition before any broker call
- [x] `closeLivePosition` called with all 7 required arguments (supabase, token, accountId, position, price, reason, tsSymbol)
- [x] `"closing_emergency"` added to `status` CHECK enum OR inline cancellation logic avoids the need for it
- [x] Zero risk of double-close under concurrent invocations

## Work Log

- 2026-03-03: Finding from architecture-strategist (P1-3) and kieran-typescript-reviewer (P1-7) during plan review.
- 2026-03-03: Resolved — plan amended with corrected code snippets, acceptance criteria updated.

- 2026-03-03: RESOLVED. Plan amended to address all findings.
