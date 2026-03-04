---
status: pending
priority: p2
issue_id: "161"
tags: [plan-review, live-trading, typescript]
dependencies: []
---

# Fix Plan Phase 8.3: `OrderFillResult.status` uses `"FLP"` (wrong code) — should be `"FPR"` for partial fills

## Problem Statement

The Phase 8.3 `OrderFillResult` type proposal includes `"FLP"` as the status code for partial fills. The actual executor code (lines 302 and 849) handles partial fills using `"FPR"`. The `| string` tail in the union also defeats TypeScript's exhaustive narrowing, which eliminates the compile-time benefit of using a union type at all.

## Findings

**TypeScript Reviewer (P2-6):**

The plan's proposed type:

```typescript
status:
  | "FLL"   // Filled
  | "FLP"   // ← WRONG — plan says partial fill
  | "OPN"
  | "CAN"
  | "REJ"
  | "EXP"
  | string;
```

Actual code at `index.ts` lines 302 + 849:

```typescript
if (status === "FPR" || status === "Partial Fill") {  // "FPR" not "FLP"
```

Using `"FLP"` in the type means the partial fill branch in switch statements will never match if implemented following the type, silently falling through to poll timeout.

The `| string` tail makes the entire union equivalent to `string` for narrowing purposes — `switch (status)` will not produce an exhaustiveness warning. If the goal is to document known codes, the comment serves that purpose; the type itself should not use `| string` if exhaustiveness is desired.

## Proposed Solution

Fix the status code and handle the open-set problem correctly:

```typescript
// Known TradeStation order status codes (broker may return undocumented values)
type KnownOrderStatus =
  | "FLL"   // Fully filled
  | "FPR"   // Partial fill (NOT "FLP")
  | "OPN"   // Open/working
  | "CAN"   // Cancelled
  | "REJ"   // Rejected
  | "EXP"   // Expired
  // Broker also uses full English strings for some codes:
  | "Filled"
  | "Partial Fill"
  | "Canceled"
  | "Rejected";

export interface OrderFillResult {
  filledQuantity: number;
  fillPrice: number;
  status: KnownOrderStatus | string;  // | string: broker may send undocumented codes
}
```

Note: keeping `| string` is acceptable IF the intent is documentation, not exhaustive switching. The key fix is changing `"FLP"` to `"FPR"`.

## Acceptance Criteria

- [ ] `"FLP"` changed to `"FPR"` in the `OrderFillResult` status union
- [ ] Plan documents that `| string` is intentional (broker may send undocumented status codes)
- [ ] All existing partial fill checks in the executor use `"FPR"` consistently

## Work Log

- 2026-03-03: Finding from kieran-typescript-reviewer (P2-6) during plan review.
