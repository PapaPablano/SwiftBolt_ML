---
title: "fix: Remaining deferred items from session audit"
type: fix
status: active
date: 2026-04-22
---

# fix: Remaining Deferred Items

## Overview

Address the 6 remaining deferred items from the full-stack audit and backend rationalization session: missing JSON schemas, gateway key rotation prep, anon RLS mutation gap, Swift forecast hybrid fetch, and two P3 visual issues.

## Requirements Trace

- D1. Create `user-refresh.schema.json` and `data-health.schema.json` in `_shared/schemas/` and update `registry.yaml`
- D2. Document SB_GATEWAY_KEY rotation procedure and scope per-function keys as future work
- D3. Add `session_token` column to `strategy_user_strategies` for anon row scoping, or restrict anon mutations to INSERT-only
- D4. Add defensive guard in `rebuildSelectedForecastBars` to prevent hybrid fetch-cycle mixing
- D5. Return `dataStatus: "no_data"` instead of `"fresh"` when zero bars exist in chart response
- D6. Expand degenerate HorizonRangeBand range when all forecasts converge

## Scope Boundaries

- **In scope:** All 6 items, each as a small independent fix
- **Out of scope:** Full gateway key rotation implementation (only document the procedure), full RLS redesign
- **Non-goal:** Changing existing API behavior beyond the specific fixes

## Implementation Units

- [ ] **Unit 1: Restore user-refresh and data-health schemas (D1)**

**Goal:** Restore contract test coverage for 2 endpoints removed during CI consolidation.

**Requirements:** D1

**Dependencies:** None

**Files:**
- Create: `supabase/functions/_shared/schemas/user-refresh.schema.json`
- Create: `supabase/functions/_shared/schemas/data-health.schema.json`
- Modify: `supabase/functions/registry.yaml`

**Approach:** Recreate from git history of the old `api-contract-tests.yml` inline schemas (commit before PR #34 removed them). Update registry.yaml schema paths from `null` to the new file paths.

**Test scenarios:**
- Happy path: `ajv compile --spec=draft7` validates both schema files
- Happy path: Registry entries have non-null schema paths

**Verification:** CI schema validation step passes with 7 total schema files (5 existing + 2 new)

---

- [ ] **Unit 2: Document SB_GATEWAY_KEY rotation procedure (D2)**

**Goal:** Document how to rotate the shared gateway key without downtime.

**Requirements:** D2

**Dependencies:** None

**Files:**
- Modify: `docs/AUTH_MATRIX.md`

**Approach:** Add a "Key Rotation" section to AUTH_MATRIX.md describing: (1) generate new key, (2) update Supabase Edge Function secrets, (3) update vault secret, (4) verify cron jobs succeed. Note the blast radius (7+ functions share one key) and recommend per-function keys as future improvement.

**Test expectation:** none — documentation only.

**Verification:** AUTH_MATRIX.md contains rotation procedure section.

---

- [ ] **Unit 3: Restrict anon strategy mutations (D3)**

**Goal:** Prevent anonymous callers from mutating other anonymous users' strategies.

**Requirements:** D3

**Dependencies:** None

**Files:**
- Create: `supabase/migrations/YYYYMMDDHHMMSS_restrict_anon_strategy_mutations.sql`

**Approach:** The simplest fix: restrict the UPDATE and DELETE RLS policies on `strategy_user_strategies` to authenticated users only. Anonymous strategies become write-once (INSERT allowed, UPDATE/DELETE require auth). This is the correct semantic — anon strategies are demo/scratch data, not user-owned state.

**Test scenarios:**
- Happy path: Authenticated user can UPDATE their own strategy
- Happy path: Anonymous user can INSERT a new strategy
- Error path: Anonymous user cannot UPDATE any strategy (including their own anon row)
- Error path: Anonymous user cannot DELETE any strategy

**Verification:** RLS policies verified via SQL test queries

---

- [ ] **Unit 4: Guard rebuildSelectedForecastBars against hybrid mixing (D4)**

**Goal:** Prevent creating a chartDataV2 with bars from one fetch and mlSummary from another.

**Requirements:** D4

**Dependencies:** None

**Files:**
- Modify: `client-macos/SwiftBoltML/ViewModels/ChartViewModel.swift`

**Approach:** In `rebuildSelectedForecastBars`, add a fetch-cycle identifier. Stamp each `chartDataV2` write with a monotonic counter incremented on each `loadChart` call. Before merging layers and mlSummary, verify both come from the same fetch cycle. If mismatched, skip the rebuild and wait for the next consistent load.

**Test scenarios:**
- Happy path: Bars and mlSummary from same fetch cycle — rebuild proceeds
- Edge case: Symbol switch mid-fetch — fetch cycle mismatch → rebuild skipped

**Verification:** Build succeeds. No stale forecast overlay after rapid symbol switching.

---

- [ ] **Unit 5: Return "no_data" status for zero-bar symbols (D5)**

**Goal:** Distinguish "fresh data" from "no data exists" in the chart response.

**Requirements:** D5

**Dependencies:** None

**Files:**
- Modify: `supabase/functions/chart/index.ts`

**Approach:** After computing `dataStatus`, add: if `paginatedActualBars.length === 0`, override `dataStatus = "no_data"`. This is additive — existing "fresh"/"stale"/"updating" values remain for symbols with bars.

**Test scenarios:**
- Happy path: Symbol with bars → `dataStatus: "fresh"` or `"stale"` (unchanged)
- Edge case: Symbol with zero bars → `dataStatus: "no_data"`
- Edge case: Symbol with only forecast bars (no actual) → `dataStatus: "no_data"`

**Verification:** Chart request for a non-existent symbol returns `dataStatus: "no_data"`, not `"fresh"`.

---

- [ ] **Unit 6: Fix HorizonRangeBand degenerate range (D6)**

**Goal:** Prevent all bands collapsing to center when forecasts converge.

**Requirements:** D6

**Dependencies:** None

**Files:**
- Modify: `client-macos/SwiftBoltML/Views/ForecastHorizonsView.swift`

**Approach:** In the `normalized()` function (around line 561), when `scaleRange` is degenerate (min == max), expand range to `value ± (value * 0.01)` instead of returning 0.5 for all values. This produces a narrow but visible spread around the converged price.

**Test scenarios:**
- Happy path: Multiple horizons with different prices — bands spread normally
- Edge case: All horizons converge to same price — bands show narrow range, not collapsed center

**Verification:** Build succeeds. Single-horizon view shows visible band, not a flat line at 50%.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| D3 RLS change breaks anonymous strategy creation | Only restrict UPDATE/DELETE, not INSERT. Test INSERT still works. |
| D5 "no_data" status breaks client expectations | Additive value — clients checking for "fresh"/"stale" won't match "no_data", which is correct behavior. |

## Sources & References

- Deferred items from session audit (2026-04-21/22)
- AUTH_MATRIX.md (PR #32)
- RLS migration: `supabase/migrations/20260222150000_allow_anon_strategies.sql`
- Chart endpoint: `supabase/functions/chart/index.ts`
- ForecastHorizonsView: `client-macos/SwiftBoltML/Views/ForecastHorizonsView.swift`
