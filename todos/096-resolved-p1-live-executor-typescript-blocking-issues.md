---
status: pending
priority: p1
issue_id: "096"
tags: [code-review, live-trading, typescript, type-safety, runtime-errors]
dependencies: []
---

# TypeScript blocking issues — syntax error, runtime undefined access, untyped API responses, N+1 queries

## Problem Statement

Four TypeScript issues in the plan that would cause compile errors or silent runtime failures:

1. `throw` expression in ternary is a TypeScript syntax error — plan Phase 4c won't compile
2. `pollOrderFill` returns `status: string` but `slStatus.fillPrice` is accessed in Phase 3f — runtime `undefined`
3. Raw `fetch().json()` is implicitly `any` — all TradeStation API response field accesses are untyped
4. `checkBracketFills` queries order status one-at-a-time in a loop — N+1 queries vs. TradeStation's batch GET /orders endpoint

## Findings

**TypeScript Reviewer (P1-1):** "`const accountToUse = isFutures ? token.futures_account_id ?? throw new Error(...)` — `throw` is a statement, not an expression. Deno will reject this."

**TypeScript Reviewer (P1-2):** "`pollOrderFill` returns `{ status: string }` but Phase 3f accesses `slStatus.fillPrice` — if the function only returns a status string, this is a runtime undefined access."

**TypeScript Reviewer (P1-4):** "`await response.json()` result type is `any`. Every field access downstream (`body.Orders[0].OrderID`, `body.Accounts[0].Equity`) is untyped and passes through the compiler silently even if the shape changes."

**Performance Oracle (P1-A):** "`checkBracketFills()` calls GET /orders one-at-a-time for each open position's SL and TP orders (N+1 pattern). TradeStation supports batch order status via `GET /brokerage/accounts/{id}/orders?orderIds=id1,id2,id3`."

## Proposed Solutions

### Fix 1 — throw expression:
```typescript
// Replace:
const accountToUse = isFutures ? token.futures_account_id ?? throw new Error(...) : token.account_id;

// With:
if (isFutures && !token.futures_account_id) {
  return { success: false, error: { type: 'broker_error', code: 'no_futures_account' } };
}
const accountToUse = isFutures ? token.futures_account_id! : token.account_id;
```

### Fix 2 — pollOrderFill return type:
```typescript
export type OrderStatus = 'FLL' | 'FPR' | 'CAN' | 'REJ' | 'OPN' | 'EXP';

export interface OrderFillResult {
  filledQuantity: number;
  fillPrice: number;
  status: OrderStatus;
}

export async function pollOrderFill(...): Promise<OrderFillResult>
// Also apply to getOrderStatus() return type
```

### Fix 3 — TradeStation API response interfaces:
```typescript
interface TSPlaceOrderResponse {
  Orders: Array<{ OrderID: string; Message: string; Error: string; }>;
}
interface TSOrderStatusResponse {
  Orders: Array<{ OrderID: string; Status: OrderStatus; FilledQuantity: number; AverageFillPrice: number; }>;
}
interface TSAccountBalanceResponse {
  Balances: Array<{ AccountID: string; Equity: number; BuyingPower: number; CashBalance: number; }>;
}
interface TSRefreshTokenResponse {
  access_token: string; expires_in: number; token_type: string; error?: string;
}
// Then: const body = await response.json() as TSPlaceOrderResponse;
```

### Fix 4 — Batch order status query:
```typescript
// Instead of N+1 per-order fetches:
const orderIds = openPositions.flatMap(p => [p.broker_sl_order_id, p.broker_tp_order_id].filter(Boolean));
const batchStatus = await getBatchOrderStatus(tsToken, accountId, orderIds);
// Then map results back to positions
```

## Technical Details

**Affected files:**
- `supabase/functions/_shared/tradestation-client.ts` — all four fixes
- `supabase/functions/live-trading-executor/index.ts` — batch order status in checkBracketFills, throw fix
- `docs/plans/2026-03-03-feat-live-trading-executor-tradestation-plan.md` — update Phase 2b, Phase 3f, Phase 4c

## Acceptance Criteria

- [ ] Phase 4c `throw` expression replaced with explicit guard clause
- [ ] `OrderStatus` type defined as string literal union (`'FLL' | 'FPR' | 'CAN' | 'REJ' | 'OPN' | 'EXP'`)
- [ ] `pollOrderFill` and `getOrderStatus` return typed `OrderFillResult`, not `{ status: string }`
- [ ] All four TradeStation API response interfaces defined and used in `response.json() as T` casts
- [ ] `checkBracketFills` uses batch `GET /orders?orderIds=...` instead of N+1 per-position requests
- [ ] `deno lint` passes on all new code with no `@ts-ignore` suppressions

## Work Log

- 2026-03-03: Finding created from TypeScript Reviewer (P1-1, P1-2, P1-4) and Performance Oracle (P1-A).
