---
status: resolved
priority: p2
issue_id: "182"
tags: [plan-review, live-trading, financial-accuracy, typescript, api-design]
dependencies: []
---

# Fix Plan Phase 4.5: `closeLivePosition` fill price integration ambiguity — poll result vs. function parameter

## Problem Statement

Phase 4.5 adds `pollOrderFill` for the manual close path to get the actual fill price. The plan's pseudocode shows polling happening inside `closeLivePosition`, but `closeLivePosition` in the current executor receives `exitPrice` as a parameter from the outer handler (set to `pos.current_price ?? pos.entry_price` before polling). The plan does not specify whether the poll moves inside the function (requiring a signature change) or stays in the handler (requiring the handler to pass the fill price down before calling). Without clarifying this, implementers may poll correctly but still write the pre-poll estimated price to the trade record.

## Findings

**Spec-Flow Analyzer (GAP-P1-5):**

Current code at line 1305 of `index.ts` (manual close handler):
```typescript
const latestPrice = pos.current_price ?? pos.entry_price;
// ...
await closeLivePosition(supabase, accessToken, accountId, position, "MANUAL_CLOSE", latestPrice);
//                                                                                   ^^^^^^^^^^^
// exitPrice is set BEFORE polling — pre-poll estimated price
```

The plan's Phase 4.5 pseudocode:
```typescript
const closeFill = await pollOrderFill(token.access_token, accountId, closeOrderId);
exitPrice = closeFill.fillPrice;  // <- updates local variable
```

If `pollOrderFill` is called inside `closeLivePosition` (after the function already received `exitPrice` as a parameter), the function ignores the parameter and uses the fill price correctly. But if `pollOrderFill` is called in the handler (before calling `closeLivePosition`), then `closeLivePosition` must be called with the fill price, not the pre-poll estimated price.

The plan is ambiguous on which boundary the poll belongs to. Either approach works, but the plan must specify one:

**Option A — Poll inside `closeLivePosition`:**
```typescript
async function closeLivePosition(
  supabase, accessToken, accountId, position, reason
  // ← NO exitPrice parameter; function polls internally
): Promise<void> {
  const closeOrder = await placeMarketOrder(...);
  const fill = await pollOrderFill(accessToken, accountId, closeOrder.orderId);
  await closeLivePositionFromBracket(supabase, position, fill.fillPrice, reason);
}
```

**Option B — Poll in the handler, pass fill price down:**
```typescript
// In the handler:
const closeOrder = await placeMarketOrder(...);
const fill = await pollOrderFill(token.access_token, accountId, closeOrder.orderId);
await closeLivePosition(supabase, token.access_token, accountId, position, "MANUAL_CLOSE", fill.fillPrice);
//                                                                                          ^^^^^^^^^^^^^^
// Pass actual fill price — handler is responsible for polling
```

Option A is cleaner (encapsulation); Option B requires a signature change at all call sites.

## Proposed Solution

Amend Phase 4.5 in the plan to explicitly specify which option is used, and show the complete function signature. The plan's pseudocode should show either: (a) `closeLivePosition` without `exitPrice` parameter (Option A), or (b) the handler passing `fill.fillPrice` as the `exitPrice` argument (Option B).

## Acceptance Criteria

- [x] Plan specifies whether `pollOrderFill` is called inside `closeLivePosition` or in the handler
- [x] Plan shows the complete updated `closeLivePosition` signature
- [x] If Option B, plan shows all call sites updated to pass the fill price
- [x] The trade record's `exit_price` is confirmed to be the actual fill price, not `pos.current_price`

## Work Log

- 2026-03-03: Finding from spec-flow-analyzer (GAP-P1-5) during plan review. Ambiguity in Phase 4.5 integration could result in correct polling but still writing the estimated price to trade records.

- 2026-03-03: RESOLVED. Plan amended to address all findings.
