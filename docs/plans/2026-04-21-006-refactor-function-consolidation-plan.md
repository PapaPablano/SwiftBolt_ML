---
title: "refactor: Consolidate Edge Functions and deprecate stale endpoints"
type: refactor
status: completed
date: 2026-04-21
origin: docs/brainstorms/2026-04-21-unified-backend-rationalization-brainstorm.md
---

# refactor: Consolidate Edge Functions and Deprecate Stale Endpoints

## Overview

Merge the 3 futures Edge Functions into a single `futures` function with query-param routing, migrate the `chart-read` pagination caller in the Swift client to the unified `chart` endpoint, and clean up legacy `chart-data-v2` references. Multi-leg functions (9 total) are NOT consolidated — they represent distinct REST operations.

## Problem Frame

The backend has related Edge Functions that share identical boilerplate (CORS setup, Supabase client init, auth handling) but are deployed and maintained separately. The `futures-chain`, `futures-continuous`, and `futures-roots` functions share >80% of their setup code. Meanwhile, `chart-read` has been deleted as a function but the Swift client still calls it at `APIClient.swift:672`, and `chart-data-v2` has legacy references that should be cleaned up. (see origin: `docs/brainstorms/2026-04-21-unified-backend-rationalization-brainstorm.md`, Phase 4)

## Requirements Trace

- R12. Consolidate related Edge Functions that share data dependencies into logical groups (futures-chain + futures-continuous + futures-roots → single futures function)
- R13. Both clients consume the same API surface — verified: only the Swift client calls futures endpoints; React frontend has no futures callers. Access parity is already satisfied.
- R14. Deprecate and remove chart-read and chart-data-v2. chart-read function is already deleted but APIClient.swift:672 still calls it. chart-data-v2 is fully retired with only legacy comments remaining.

## Scope Boundaries

- **In scope:** Futures function consolidation, chart-read Swift caller migration, chart-data-v2 reference cleanup, registry.yaml updates
- **Out of scope:** Multi-leg consolidation (9 distinct REST operations — not worth merging), new futures features, chart function pagination redesign beyond what's needed for chart-read migration
- **Non-goal:** Reducing total function count to a target number — consolidate only where it genuinely reduces maintenance cost

## Context & Research

## Prerequisites (from PR review findings)

Before starting this plan, the following P1/P2 fixes from prior PRs should be resolved:

**From PR #33 (Chart Freshness — affects Unit 4-5 chart changes):**
- **P1: Duplicate `isStale` in both `dataQuality` and `freshness` objects** — Deduplicate before adding cursor pagination to avoid shipping a third staleness indicator.
- **P2: `ageSeconds` rounding inconsistency** — Fix before adding more freshness fields.
- **P2: m15 SLA at 10min too tight** — Consider relaxing to 15min (3x cron) before chart changes.

**From PR #31 (Sidebar — affects Swift client work in Units 2, 5):**
- **P1: `onDisappear` never fires on SidebarView** — Remove dead cleanup code or switch to `.task`-based polling for MarketStatusService.
- **P1: PaperTradingService green dot may not populate until user visits Paper Trading** — Verify eager data loading.
- **P2: ContentView at 300-line limit** — Extract sidebar enums to SidebarModels.swift before adding more Swift client changes.

### Relevant Code and Patterns

- `supabase/functions/futures-chain/index.ts` (201 lines) — GET with `root` + `asOf` params
- `supabase/functions/futures-continuous/index.ts` (186 lines) — GET with `root` + `depth` params
- `supabase/functions/futures-roots/index.ts` (100 lines) — GET with `sector` param
- `client-macos/SwiftBoltML/Services/APIClient.swift:672` — `fetchChartReadPage()` calls the deleted `chart-read` function with `before` (cursor) and `pageSize` params
- `supabase/functions/chart/index.ts` — Unified chart endpoint. Currently uses `days`/`start`/`end` params, not cursor-based pagination.
- `supabase/functions/registry.yaml` — Machine-readable function catalog (from PR #34)

### Institutional Learnings

- **API contract rule** (CLAUDE.md): "Any breaking change to a function's response requires a PR review of all affected callers, a caller-update PR merged before the function change."
- **chart-read migration note** (APIClient.swift:672): "update separately when the unified chart function gains cursor-based pagination support"

## Key Technical Decisions

- **Futures: query-param routing, not URL-path routing:** The consolidated `futures` function will use a `type` query parameter (`?type=chain`, `?type=continuous`, `?type=roots`) to route requests. This preserves backward compatibility — old URLs can redirect via the function detecting the absence of `type` param and inferring from other params (e.g., `root` + `asOf` → chain, `sector` → roots).
- **Futures: keep old function directories as redirects temporarily:** Deploy the consolidated `futures` function first, then update each old function to redirect to `futures?type=X`. Remove old functions only after verifying no callers remain. Per CLAUDE.md, caller-update PR must merge before function deletion.
- **chart-read: add cursor pagination to chart function:** Rather than a separate migration effort, add a `before` parameter to the existing `chart` function that enables cursor-based backward pagination. This lets `fetchChartReadPage()` switch from `chart-read` to `chart` with minimal changes.
- **Multi-leg: no consolidation:** 9 functions represent distinct operations (create, list, detail, update, delete, close-leg, close-strategy, evaluate, templates). Merging them into one REST-routed function would create a 1000+ line monolith with mixed concerns. Not worth it.

## Open Questions

### Resolved During Planning

- **Which functions are consolidation candidates?** Only futures (3→1). Multi-leg (9 functions) are distinct REST operations — not worth merging.
- **Does chart-data-v2 still exist?** No — function directory deleted. Only legacy comments remain in Swift client code.
- **Which clients call futures endpoints?** Only Swift client (APIClient.swift:600 `fetchFuturesChain()`). React frontend has no futures callers.

### Deferred to Implementation

- Exact query-param routing logic for the consolidated futures function — depends on reading all 3 functions' param handling
- Whether the old futures-chain/continuous/roots functions should redirect (302) or proxy (pass-through) during the transition period
- Exact `before` cursor implementation in the chart function — depends on how `get_chart_data_v2` RPC handles cursor-based queries

## Implementation Units

- [x] **Unit 1: Create consolidated futures function**

**Goal:** Merge futures-chain, futures-continuous, and futures-roots into a single `futures` function with query-param routing.

**Requirements:** R12

**Dependencies:** None

**Files:**
- Create: `supabase/functions/futures/index.ts`
- Test: `supabase/functions/futures/index_test.ts`
- Reference: `supabase/functions/futures-chain/index.ts`, `futures-continuous/index.ts`, `futures-roots/index.ts`

**Approach:**
- Read all 3 existing functions to understand their full logic.
- Create `supabase/functions/futures/index.ts` with a `type` query parameter router:
  - `?type=chain&root=GC&asOf=...` → chain logic
  - `?type=continuous&root=GC&depth=...` → continuous logic
  - `?type=roots&sector=...` → roots logic
- Extract shared setup (CORS, Supabase client, auth) to the top of the function.
- Auto-detect type when `type` param is absent: if `sector` is present → roots, if `asOf` is present → chain, if `depth` is present → continuous. This provides backward compatibility for callers using old param patterns.
- Add to `supabase/config.toml` if auth settings are needed (all 3 originals use JWT default).

**Patterns to follow:**
- Existing multi-route Edge Functions (e.g., `strategies/index.ts` routes by HTTP method)
- Shared CORS/auth pattern from `_shared/cors.ts`

**Test scenarios:**
- Happy path: `?type=chain&root=GC&asOf=2026-04-01` → returns chain data
- Happy path: `?type=continuous&root=ES&depth=2` → returns continuous data
- Happy path: `?type=roots&sector=indices` → returns roots list
- Happy path: Auto-detect — `?root=GC&asOf=2026-04-01` (no type param) → infers chain
- Edge case: Unknown type param → 400 error with valid types listed
- Edge case: Missing required params for chain (no root) → 400 error
- Error path: Supabase query fails → 500 with error message
- Integration: Swift client `fetchFuturesChain()` works against new endpoint after URL update

**Verification:**
- All 3 query types return identical data to their standalone predecessors
- Auto-detection routes correctly when `type` param is absent

---

- [x] **Unit 2: Update Swift client to call consolidated futures endpoint**

**Goal:** Migrate `fetchFuturesChain()` in APIClient.swift from `futures-chain` to `futures?type=chain`.

**Requirements:** R12, R13

**Dependencies:** Unit 1 (consolidated function deployed)

**Files:**
- Modify: `client-macos/SwiftBoltML/Services/APIClient.swift`

**Approach:**
- Find `fetchFuturesChain()` (around line 600) and update the `functionURL("futures-chain")` call to `functionURL("futures")` with `type=chain` query parameter.
- Search for any other futures endpoint calls (`futures-continuous`, `futures-roots`) in the Swift client and update them similarly.
- Per CLAUDE.md: this caller-update PR must merge before the old function directories are deleted.

**Patterns to follow:**
- Existing `functionURL()` pattern in APIClient.swift

**Test scenarios:**
- Happy path: `fetchFuturesChain()` returns the same data as before against the new endpoint
- Edge case: If futures-continuous or futures-roots are also called, those are updated too

**Verification:**
- No references to `futures-chain`, `futures-continuous`, or `futures-roots` as endpoint names in APIClient.swift
- Futures chain data loads correctly in the macOS app

---

- [x] **Unit 3: Add redirect stubs to old futures functions**

**Goal:** Replace the old futures-chain, futures-continuous, futures-roots functions with redirect stubs pointing to the consolidated `futures` endpoint.

**Requirements:** R12

**Dependencies:** Unit 2 (callers updated first per CLAUDE.md)

**Files:**
- Modify: `supabase/functions/futures-chain/index.ts` (replace with redirect)
- Modify: `supabase/functions/futures-continuous/index.ts` (replace with redirect)
- Modify: `supabase/functions/futures-roots/index.ts` (replace with redirect)

**Approach:**
- Replace each function body with a lightweight redirect that constructs the `futures?type=X` URL from the incoming request params and returns a 301 redirect.
- Keep the functions deployed during a transition period so any undiscovered callers don't break silently.
- Add a deprecation log line so monitoring can detect if redirects are being hit.
- After a monitoring period (1-2 weeks), delete the old function directories entirely.

**Test scenarios:**
- Happy path: `GET /futures-chain?root=GC` → 301 redirect to `/futures?type=chain&root=GC`
- Happy path: `GET /futures-roots?sector=indices` → 301 redirect to `/futures?type=roots&sector=indices`
- Edge case: OPTIONS preflight → CORS response (no redirect)

**Verification:**
- Old endpoints redirect correctly to consolidated function
- Deprecation log entries appear in Supabase function logs

---

- [x] **Unit 4: Add cursor pagination to chart function for chart-read migration**

**Goal:** Add a `before` query parameter to the chart endpoint to enable backward cursor-based pagination, allowing the Swift `fetchChartReadPage()` to migrate off the deleted `chart-read` function.

**Requirements:** R14

**Dependencies:** None (parallel with Units 1-3)

**Files:**
- Modify: `supabase/functions/chart/index.ts`
- Test: `supabase/functions/chart/index_test.ts`

**Approach:**
- Add an optional `before` query parameter (ISO 8601 timestamp or unix timestamp) to the chart endpoint.
- When `before` is present, modify the OHLCV query to filter `ts < before` and order by `ts DESC` with `limit` set to the `pageSize` param (default 400).
- This is additive — the existing `days`/`start`/`end` params continue to work. `before` is a new, optional pagination mode.
- Ensure the response shape is identical whether `before` is used or not.

**Execution note:** Read `fetchChartReadPage()` in APIClient.swift first to understand exactly what params and response shape it expects, then match that contract.

**Patterns to follow:**
- Existing chart endpoint query construction (the `get_chart_data_v2` RPC call and fallback direct query)
- CLAUDE.md cursor-based pagination convention: "cursor-based pagination (not OFFSET)"

**Test scenarios:**
- Happy path: `GET /chart?symbol=AAPL&timeframe=d1&before=2026-01-01T00:00:00Z&pageSize=100` → returns 100 bars before the cursor
- Happy path: `GET /chart?symbol=AAPL&timeframe=d1&days=180` → existing behavior unchanged
- Edge case: `before` timestamp is in the future → returns latest bars (same as no `before`)
- Edge case: `before` timestamp is before any data → returns empty bars array
- Edge case: `pageSize` not provided with `before` → defaults to 400
- Error path: Invalid `before` format → 400 error
- Integration: `fetchChartReadPage()` works against chart endpoint after URL update

**Verification:**
- Chart endpoint accepts `before` param and returns paginated results
- Existing chart behavior (days/start/end) is unchanged
- Response shape with `before` matches what `fetchChartReadPage()` expects

---

- [x] **Unit 5: Migrate fetchChartReadPage to unified chart endpoint**

**Goal:** Update `fetchChartReadPage()` in APIClient.swift to call `chart` instead of the deleted `chart-read`.

**Requirements:** R14

**Dependencies:** Unit 4 (cursor pagination available in chart)

**Files:**
- Modify: `client-macos/SwiftBoltML/Services/APIClient.swift`

**Approach:**
- Update `fetchChartReadPage()` (line ~672) to use `functionURL("chart")` instead of `functionURL("chart-read")`.
- Add the `before` parameter to the query string (already passed as a param in the current implementation).
- Remove the `// update separately when the unified chart function gains cursor-based pagination support` comment.
- Verify no other references to `chart-read` exist in the codebase.

**Patterns to follow:**
- Existing chart endpoint calls in APIClient.swift

**Test scenarios:**
- Happy path: Historical chart scrolling (backward pagination) works in the macOS app
- Edge case: First page load (no `before` param) still works
- Integration: Full scroll-back flow loads progressively older bars

**Verification:**
- Zero references to `chart-read` in the entire codebase (grep confirms)
- Historical chart pagination works in the app

---

- [x] **Unit 6: Clean up chart-data-v2 legacy references**

**Goal:** Remove all legacy comments and dead code referencing `chart-data-v2`.

**Requirements:** R14

**Dependencies:** None (parallel)

**Files:**
- Modify: `client-macos/SwiftBoltML/Services/APIClient.swift` (remove legacy comments)
- Possibly modify: any other files referencing `chart-data-v2`

**Approach:**
- Grep the entire codebase for `chart-data-v2` and remove all references (comments, dead code, type aliases).
- The function directory is already deleted — this is purely comment/reference cleanup.

**Test expectation:** none — comment removal with no behavioral change.

**Verification:**
- Zero references to `chart-data-v2` in the entire codebase

---

- [x] **Unit 7: Update registry.yaml and AUTH_MATRIX.md**

**Goal:** Update the API registry to reflect the consolidation (add `futures`, mark old functions as deprecated, remove chart-read/chart-data-v2).

**Requirements:** R12, R14

**Dependencies:** Units 1-6

**Files:**
- Modify: `supabase/functions/registry.yaml`

**Approach:**
- Add `futures` entry with `method: GET`, `auth: jwt`, `consumers: client`, and schema path.
- Mark `futures-chain`, `futures-continuous`, `futures-roots` entries as `deprecated: true` (or remove after redirect stubs are deleted).
- Remove `chart-read` and `chart-data-v2` entries if they exist.

**Test expectation:** none — registry data update with no behavioral change.

**Verification:**
- Registry reflects the consolidated function landscape
- CI registry validation passes (no missing function directories)

## System-Wide Impact

- **Interaction graph:** Swift client's `fetchFuturesChain()` changes target URL. The `fetchChartReadPage()` function changes from a dead endpoint to the live chart endpoint. Both changes require the server-side function to be deployed before the client update ships.
- **Error propagation:** Old futures endpoints redirect (301) during transition — any caller following redirects continues to work. Callers that don't follow redirects get a 301 instead of data, which is a visible failure.
- **API surface parity:** Only the Swift client calls futures endpoints — React has no futures callers. No cross-client parity concern.
- **Unchanged invariants:** Chart endpoint's existing behavior (days/start/end params) is not modified. Multi-leg functions are not touched. All other Edge Functions are unchanged.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Undiscovered callers of old futures endpoints | Redirect stubs (Unit 3) catch them. Monitor logs for redirect hits before deleting. |
| chart cursor pagination changes chart response shape | Use same response shape with `before` as without — additive param only. |
| fetchChartReadPage expects different response shape than chart | Read the function first (Execution note in Unit 4). Match the expected contract. |
| Old function deletion breaks deploy pipeline | Delete only after monitoring period confirms zero redirect hits. |

## Sources & References

- **Origin document:** [docs/brainstorms/2026-04-21-unified-backend-rationalization-brainstorm.md](docs/brainstorms/2026-04-21-unified-backend-rationalization-brainstorm.md) — Phase 4 (R12-R14)
- CLAUDE.md API contract rules (caller-update PR before function change)
- Futures functions: `supabase/functions/futures-{chain,continuous,roots}/index.ts`
- Chart-read caller: `client-macos/SwiftBoltML/Services/APIClient.swift:672`
- Registry: `supabase/functions/registry.yaml` (PR #34)
