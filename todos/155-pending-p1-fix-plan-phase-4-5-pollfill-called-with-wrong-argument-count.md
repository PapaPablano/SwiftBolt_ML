---
status: pending
priority: p1
issue_id: "155"
tags: [plan-review, live-trading, typescript, financial-safety]
dependencies: []
---

# Fix Plan Phase 4.5/7.1: `pollOrderFill` called with 4 arguments but function only accepts 3

## Problem Statement

The fix plan's Phase 4.5 calls `pollOrderFill(token.access_token, accountId, closeOrderId, 5_000)` — passing 4 arguments. The actual `pollOrderFill` function in `index.ts` only accepts 3 parameters: `(accessToken, accountId, orderId)`. This is a compile error that would fail at Deno check time.

## Findings

**TypeScript Reviewer (P1-7):**

Actual `pollOrderFill` signature at `index.ts` line 282:

```typescript
async function pollOrderFill(
  accessToken: string,
  accountId: string,
  orderId: string,
): Promise<OrderFillResult>
```

No `timeoutMs` or `expectedQty` parameter exists. The plan passes `5_000` as a 4th argument, which TypeScript strict mode rejects.

The plan intends to use a shorter timeout for close orders (5s vs 15s for entry). This requires either:
1. Adding an optional `timeoutMs` parameter to `pollOrderFill` — but this function is also used on the entry path at line 832, so the signature change must be backward-compatible
2. Using the existing `POLL_TIMEOUT_MS` constant (15,000ms) for close orders as well

Additionally: the 5-second close order timeout may be insufficient for illiquid assets (options, thinly traded futures). A close order in a thin market can take 10–30 seconds. If `pollOrderFill` times out on the close, the plan falls back to `current_price` as the exit price — which is exactly the problem todo #140 is trying to fix. The plan should document this trade-off explicitly.

## Proposed Solution

Option A (recommended) — Add optional `timeoutMs` to `pollOrderFill`:

```typescript
async function pollOrderFill(
  accessToken: string,
  accountId: string,
  orderId: string,
  timeoutMs: number = POLL_TIMEOUT_MS,  // defaults to 15s
): Promise<OrderFillResult> {
  const deadline = Date.now() + timeoutMs;
  // ... existing poll loop
}
```

Then Phase 4.5 calls: `pollOrderFill(token.access_token, accountId, closeOrderId, 10_000)` — use 10s (not 5s) to give market close orders a reasonable window while still leaving ~30s for other work.

Option B — Reuse the existing 15s timeout constant for close orders too (simplest):

```typescript
closeFill = await pollOrderFill(token.access_token, accountId, closeOrderId);
// uses POLL_TIMEOUT_MS (15s) — identical to entry path
```

Acceptable for market orders, which typically fill in under 1 second.

## Acceptance Criteria

- [ ] `pollOrderFill` call in Phase 4.5 matches the actual function signature
- [ ] If timeout parameter is added, it is optional with a backward-compatible default
- [ ] The plan documents what happens when close fill poll times out (fallback to current_price, reconciliation needed)

## Work Log

- 2026-03-03: Finding from kieran-typescript-reviewer (P1-7) during plan review.
