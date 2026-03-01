---
status: resolved
priority: p1
issue_id: "027"
tags: [code-review, architecture, edge-functions, dead-code]
dependencies: []
---

# 027 — strategy/index.ts Is Node.js Dead Code Deployed to Deno Runtime

## Problem Statement
`supabase/functions/strategy/index.ts` uses Node.js/Express-style syntax (`export default async function handler(req, res)`) with `process.env` and `#!/usr/bin/env node`. Supabase Edge Functions run on Deno. This function cannot execute and silently fails at runtime while occupying a deployment slot.

## Findings
- `supabase/functions/strategy/index.ts`: `#!/usr/bin/env node` shebang
- Uses `process.env.SUPABASE_URL` (Deno uses `Deno.env.get()`)
- Uses Express-style `res.status(200).json()` response API
- Targets table `strategies` (different from active `strategy_user_strategies`)
- Active strategy CRUD function is `strategies/index.ts` (different function name)

## Proposed Solutions

### Option A: Delete the function (Recommended)
Remove `supabase/functions/strategy/` directory entirely.
- Effort: XSmall (10 minutes)
- Risk: None — it doesn't run anyway

### Option B: Convert to Deno
Rewrite in Deno patterns if the `strategies` table still holds distinct data.
- Effort: Medium
- Risk: Medium (unclear what data it served)

## Recommended Action
Option A. Confirm `strategies` table is empty/redundant vs `strategy_user_strategies`, then delete.

## Technical Details
- **Affected files:** `supabase/functions/strategy/` (entire directory)

## Acceptance Criteria
- [x] `supabase/functions/strategy/` directory deleted
- [x] `supabase/config.toml` entry removed if present (no `[functions.strategy]` section existed)
- [x] No frontend code references this endpoint (confirmed: no `/strategy` endpoint calls in frontend/src/)

## Work Log
- 2026-03-01: Identified by architecture-strategist review agent
- 2026-03-01: Resolved — deleted `supabase/functions/strategy/` directory (index.ts + README.md). Confirmed no `[functions.strategy]` entry in config.toml and no frontend references to the `/strategy` endpoint.
