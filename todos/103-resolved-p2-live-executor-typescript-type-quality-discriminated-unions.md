---
status: pending
priority: p2
issue_id: "103"
tags: [code-review, live-trading, typescript, type-safety]
dependencies: ["096"]
---

# TypeScript type quality — ExecutionError, BrokerToken, CircuitBreakerResult, IndicatorCache types

## Problem Statement

Several types in the plan are underspecified, leading to runtime errors that the compiler cannot catch:

1. `ExecutionError` codes are plain strings (`'position_size_cap'`), not a typed union — callers can't discriminate error types
2. `BrokerToken` interface is never defined — callers use implicit `any`
3. `CircuitBreakerResult.reason` is optional but accessed unconditionally — produces `"undefined"` in API responses
4. `IndicatorCache = Map<string, number>` — a typo in a key name is a silent cache miss at trade time
5. `normalizeSymbol` returns `multiplier: number` — a `0` result causes `Infinity` position size

These are distinct from the P1 blocking issues (todo #096) — these don't cause compile failures or immediate crashes but produce incorrect runtime behavior.

## Findings

**TypeScript Reviewer (P2-1):** "The plan's error discrimination section lists error codes as prose strings. The pseudocode returns a bare string: `return { success: false, error: 'position_size_cap' }`."

**TypeScript Reviewer (P2-5):** "`BrokerToken` interface is referenced but never defined anywhere in the plan."

**TypeScript Reviewer (P2-4):** "`CircuitBreakerResult.reason` is optional but code like `return errorResponse(circuitBreakerResult.reason, 403, origin)` passes a potentially undefined value."

**TypeScript Reviewer (P1-3):** "`IndicatorCache = Map<string, number>` — a typo in an indicator key name produces a silent undefined at trade time."

**TypeScript Reviewer (P2-2):** "`normalizeSymbol` returns `multiplier: number` — if implementation returns `0` for unknown symbol, `calculateQuantity` produces `Infinity` shares."

## Proposed Solutions

### Fix 1 — LiveExecutionError discriminated union:
```typescript
type LiveExecutionError =
  | { type: 'broker_auth_failed'; reason: string }
  | { type: 'broker_unavailable'; statusCode: number }
  | { type: 'order_rejected'; code: string }
  | { type: 'order_not_filled'; orderId: string }
  | { type: 'circuit_breaker'; rule: 'market_hours' | 'daily_loss' | 'max_positions' | 'position_size_cap' }
  | { type: 'position_locked'; reason: 'concurrent_close_detected' }
  | { type: 'database_error'; reason: string };
```

### Fix 2 — BrokerToken interface (export from tradestation-client.ts):
```typescript
export interface BrokerToken {
  id: string; user_id: string; provider: 'tradestation';
  access_token: string; refresh_token: string; expires_at: string;
  account_id: string; futures_account_id: string | null;
}
```

### Fix 3 — CircuitBreakerResult discriminated union:
```typescript
type CircuitBreakerResult =
  | { allowed: true }
  | { allowed: false; reason: string; rule: 'market_hours' | 'daily_loss' | 'max_positions' | 'position_size_cap' };
```

### Fix 4 — Typed IndicatorCache:
```typescript
export const INDICATOR_KEYS = ['RSI','MACD','EMA_20','EMA_50','Volume_MA','RSI_prev','MACD_prev'] as const;
export type IndicatorKey = typeof INDICATOR_KEYS[number];
export type IndicatorCache = Map<IndicatorKey, number>;
```

### Fix 5 — FuturesMultiplier literal type:
```typescript
export type FuturesMultiplier = 50 | 20 | 5 | 1000 | 100 | 5000;
export interface NormalizedSymbol { tsSymbol: string; isFutures: boolean; multiplier: FuturesMultiplier | 1; }
```

## Technical Details

**Affected files:**
- `supabase/functions/_shared/tradestation-client.ts` — BrokerToken, FuturesMultiplier, NormalizedSymbol
- `supabase/functions/_shared/condition-evaluator.ts` (or strategy-evaluator) — IndicatorKey, IndicatorCache
- `supabase/functions/live-trading-executor/index.ts` — LiveExecutionError, CircuitBreakerResult

## Acceptance Criteria

- [ ] `LiveExecutionError` is a discriminated union — no bare string error codes
- [ ] `BrokerToken` interface exported from `_shared/tradestation-client.ts` with `futures_account_id: string | null`
- [ ] `CircuitBreakerResult` discriminated union — `reason` is non-optional when `allowed: false`
- [ ] `IndicatorKey` typed literal union used as `IndicatorCache` key type
- [ ] `normalizeSymbol` returns `multiplier: FuturesMultiplier | 1` — never `0`
- [ ] `deno check` passes with no `any` warnings on the executor code

## Work Log

- 2026-03-03: Finding created from TypeScript Reviewer (P2-1, P2-2, P2-4, P2-5, P1-3).
