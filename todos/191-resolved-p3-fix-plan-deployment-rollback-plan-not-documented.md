---
status: resolved
priority: p3
issue_id: "191"
tags: [plan-review, live-trading, deployment, documentation, migration]
dependencies: []
---

# Fix Plan: Deployment rollback plan not documented — partial-deploy states not analyzed

## Problem Statement

The plan's Migration Ordering section specifies the sequence: apply migration 1 → apply migration 2 → deploy function. It does not specify a rollback path for each step failure. While the specific partial-deploy scenarios for PR #28 are mostly safe, this reasoning is not documented — leaving deployment teams to reason through it themselves under pressure during an actual incident. The Phase 1.3 partial-deploy scenario (UUID→TEXT migration applied, new function not yet deployed) deserves explicit documentation.

## Findings

**Spec-Flow Analyzer (GAP-P3-2):**

**Migration 2 succeeds, function deployment fails:**
- `increment_rate_limit` RPC now exists → old function's fail-open fallback branch is no longer needed (RPC exists, so it works better than before) — safe
- `live_positions_updated_at` trigger now exists → fires on every UPDATE regardless of function version — harmless
- FK changed from CASCADE to RESTRICT on `live_trading_positions` → safe for any running function version
- **Conclusion:** Old function continues working normally with the new schema — safe partial state

**Migration 1 (Phase 1.3: UUID→TEXT) succeeds, function not deployed:**
- `symbol_id` column changed from UUID to TEXT
- Old function inserts UUID values → PostgreSQL performs implicit cast UUID→TEXT → succeeds (UUID strings are valid TEXT)
- New UNIQUE index on (user_id, symbol_id TEXT) is recreated — existing UUID values remain valid TEXT
- **Conclusion:** Safe partial state if no raw symbol strings (e.g. "AAPL") have been written yet

**CORS change partial state:**
If `_shared/cors.ts` is updated but function deployment fails, the old functions are still running the old CORS utility code — no impact.

**What is NOT safe — Phase 1.3 rollback after non-UUID data:**
If new function deploys successfully AND writes raw symbol strings (e.g. "AAPL") to `symbol_id`, and then the team wants to roll back to the old function (UUID column), the migration is a one-way door. Rolling back requires:
1. Delete all rows with non-UUID `symbol_id` values
2. `ALTER COLUMN symbol_id TYPE UUID USING symbol_id::uuid` — fails if any non-UUID strings exist
This rollback risk is documented in todo #164 but not in the plan's deployment section.

**Recommended addition:**

Add a "Rollback Plan" subsection to Migration Ordering:

```markdown
### Rollback Plan

For each step, the system state if the NEXT step fails:

| Step | Failure | State | Safe to operate? |
|------|---------|-------|-----------------|
| Migration 1 deployed | Function deploy fails | symbol_id is TEXT, old function inserts UUIDs as TEXT | ✅ Yes |
| Migration 2 deployed | Function deploy fails | increment_rate_limit RPC exists, FK is RESTRICT | ✅ Yes |
| Function deployed | Need to roll back function | If Migration 1 wrote non-UUID symbol_id values, old function + UUID column rollback is NOT possible without data deletion | ⚠️ One-way door |

See todo #164 for Phase 1.3 rollback constraints.
```

## Proposed Solution

Add a "Rollback Plan" subsection to the Migration Ordering section documenting partial-deploy states and their safety. Flag Phase 1.3 as a one-way door once non-UUID data is written.

## Acceptance Criteria

- [x] Plan includes a "Rollback Plan" table for each migration step's failure scenario
- [x] Phase 1.3 one-way door documented (consistent with todo #164)
- [x] Each partial-deploy state is assessed as safe or unsafe to continue operating in
- [x] If any state is unsafe, a recovery procedure is documented

## Work Log

- 2026-03-03: Finding from spec-flow-analyzer (GAP-P3-2) during plan review. The specific partial-deploy states for PR #28 are mostly safe, but this reasoning should be documented rather than left to deployment teams to re-derive.

- 2026-03-03: RESOLVED. Plan amended to address all findings.
