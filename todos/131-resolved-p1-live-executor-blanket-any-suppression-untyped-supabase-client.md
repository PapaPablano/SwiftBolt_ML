---
status: pending
priority: p1
issue_id: "131"
tags: [code-review, live-trading, typescript, type-safety]
dependencies: []
---

# File-level `no-explicit-any` suppression masks type holes in real-money execution path

## Problem Statement

Both `live-trading-executor/index.ts` (line 12) and `_shared/tradestation-client.ts` (line 1) use the blanket directive:

```typescript
// deno-lint-ignore-file no-explicit-any
```

This silences every `any` in both files — including the `supabase: any` and `authSupabase: any` parameters appearing in at least 8 function signatures. Because the Supabase client parameters are `any`, all return types from `.from().select().eq()` chains become `any`, defeating discriminated union checking downstream. The compiler cannot catch misspelled method names (`.form()` vs `.from()`), wrong column names in `.eq()` calls, or shape mismatches in query results. In a 1400-line function that places real-money orders, this is unacceptable.

## Findings

**TypeScript reviewer P1-1.** The Supabase JS client exports a well-defined `SupabaseClient` type. A typed alias resolves this without touching every call site:

```typescript
import type { SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
type Db = SupabaseClient;

// Before:
async function checkDailyLossLimit(supabase: any, userId: string, ...

// After:
async function checkDailyLossLimit(supabase: Db, userId: string, ...
```

Removing the blanket suppress will also surface any remaining `any` usages that require explicit `// deno-lint-ignore no-explicit-any` suppressions with justifications — making the type holes visible rather than hidden.

## Proposed Solutions

**Option A (Recommended):** Import `SupabaseClient` from the Supabase Deno ESM URL, define a `type Db = SupabaseClient` alias at the top of each file, and replace all `supabase: any` / `authSupabase: any` parameters with `supabase: Db`. Remove the file-level suppression. Suppress only any remaining `any` usages individually with a justification comment. Effort: Medium.

**Option B:** Keep the blanket suppression but add an `// eslint-disable` comment explaining why it is necessary and tracking a follow-up. Effort: None — but defers the real fix indefinitely.

## Acceptance Criteria

- [ ] File-level `// deno-lint-ignore-file no-explicit-any` removed from both files
- [ ] `supabase` and `authSupabase` parameters typed as `SupabaseClient` (or an alias)
- [ ] Any remaining `any` usages are individually suppressed with justification comments
- [ ] `deno lint` passes without the file-level suppression
- [ ] No existing behavior changes — this is a type-only change
