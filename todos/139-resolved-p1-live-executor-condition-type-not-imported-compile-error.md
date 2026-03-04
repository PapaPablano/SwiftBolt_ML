---
status: pending
priority: p1
issue_id: "139"
tags: [code-review, live-trading, typescript, type-safety]
dependencies: []
---

# `Condition` type referenced in `executeStrategy` but never imported

## Problem Statement

`/Users/ericpeterson/SwiftBolt_ML/supabase/functions/live-trading-executor/index.ts` lines 54–55 reference `Condition[]` as the type for `config.entry_conditions` and `config.exit_conditions`, but `Condition` is never imported anywhere in the file. In Deno/TypeScript this is a compile-time type error. The `Condition` type is defined in `_shared/condition-evaluator.ts` and should either be imported from there, or the parameter should be typed as `unknown[]` if the executor only passes conditions through to `evaluateStrategySignals` without inspecting their shape.

## Findings

**Code Simplicity Reviewer (P3-9):** "`Condition` type is used but never imported or defined in `index.ts`. In Deno/TypeScript this would produce a compile error unless `Condition` is globally declared elsewhere."

## Proposed Solutions

**Option A (Recommended):** Import `Condition` from the shared evaluator:
```typescript
import type { Condition } from "../_shared/condition-evaluator.ts";
```

**Option B:** Replace with `unknown[]` if the executor never inspects condition shape:
```typescript
entry_conditions: unknown[];
exit_conditions: unknown[];
```

**Option C:** Define a minimal inline type that matches what the executor needs.

## Acceptance Criteria

- [ ] `Condition` type resolves without error when running `deno check`
- [ ] `deno lint` passes on `live-trading-executor/index.ts`
- [ ] No behavior change — type-only fix

## Work Log

- 2026-03-03: Finding from code-simplicity-reviewer.
