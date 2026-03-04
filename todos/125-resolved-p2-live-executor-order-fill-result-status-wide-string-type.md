---
status: pending
priority: p2
issue_id: "125"
tags: [code-review, live-trading, typescript, type-safety]
dependencies: []
---

# `OrderFillResult.status` typed as `string` — loses exhaustiveness checking on fill status handling

## Problem Statement

`OrderFillResult.status` in `tradestation-client.ts` (line 58) is typed as `string`. The executor switch at lines 299–310 uses hard-coded string literals `"FLL"`, `"Filled"`, `"FPR"`, `"Partial Fill"`, `"REJ"`, `"Rejected"`, `"CAN"`, `"Canceled"`. There is no type-level guarantee that the full set of cases is handled, and a typo in any case string silently falls through to the default without compiler warning. `LivePosition.status` (line 77 of the executor) has the same issue.

## Findings

TypeScript reviewer P2-2.

## Proposed Solutions

**Option A (Recommended):** Define a union type `OrderStatus = "FLL" | "Filled" | "FPR" | "Partial Fill" | "REJ" | "Rejected" | "CAN" | "Canceled" | "PENDING" | "UNKNOWN"` and use it for `OrderFillResult.status`. Similarly define a `PositionStatus` union for `LivePosition.status`. This gives compile-time exhaustiveness on all switch/if chains. Effort: Small.

## Acceptance Criteria

- [ ] `OrderFillResult.status` uses a union type covering all known TradeStation order status codes
- [ ] `LivePosition.status` uses the same union as the schema's CHECK constraint
- [ ] TypeScript compiler catches unhandled status cases or typos in status literals
