---
status: pending
priority: p2
issue_id: "156"
tags: [plan-review, live-trading, typescript, reliability]
dependencies: []
---

# Fix Plan Phase 1.2: `SupabaseClient` imported from bare `@2` esm.sh URL causes version drift

## Problem Statement

The fix plan's Phase 1.2 imports `SupabaseClient` type from `"https://esm.sh/@supabase/supabase-js@2"` — a bare major-version specifier. The existing code imports `createClient` via the project's `deno.json` import map. Using a different specifier for the type vs the value creates two separate module identities in Deno, which can silently diverge across minor versions of `@supabase/supabase-js`.

## Findings

**TypeScript Reviewer (P2):**

The bare `@2` esm.sh URL will resolve to whatever esm.sh considers the latest `2.x` release at fetch time. The import map version and the esm.sh version can desync after a package update, producing subtle type mismatches (e.g., new optional fields in `PostgrestResponse` that the esm.sh type knows about but the import-map type does not, or vice versa).

The correct fix is to source the type from the same specifier already used in `deno.json`:

```typescript
// WRONG — introduces version drift risk
import type { SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";

// CORRECT — matches the specifier used for createClient
import type { SupabaseClient } from "@supabase/supabase-js";
```

If `@supabase/supabase-js` is not already mapped in `deno.json`, the plan should add it to the import map and import from the mapped specifier consistently across both files.

## Proposed Solution

Update Phase 1.2 in the plan to use the import map specifier:

```typescript
// In supabase/functions/live-trading-executor/index.ts
import type { SupabaseClient } from "@supabase/supabase-js";

// In supabase/functions/_shared/tradestation-client.ts
import type { SupabaseClient } from "@supabase/supabase-js";
```

And add to `deno.json` if not already mapped:

```json
{
  "imports": {
    "@supabase/supabase-js": "https://esm.sh/@supabase/supabase-js@2.x.y"
  }
}
```

## Acceptance Criteria

- [ ] `SupabaseClient` type import uses the same specifier as `createClient` (import map, not bare esm.sh)
- [ ] `deno check` passes with no type errors on both files
- [ ] No version drift between the type and value imports

## Work Log

- 2026-03-03: Finding from kieran-typescript-reviewer (P2-1) during plan review.
