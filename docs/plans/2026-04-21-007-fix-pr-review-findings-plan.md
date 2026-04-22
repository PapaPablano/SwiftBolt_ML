---
title: "fix: Resolve P1/P2 review findings across PRs 31-34"
type: fix
status: completed
date: 2026-04-21
---

# fix: Resolve P1/P2 Review Findings Across PRs 31-34

## Overview

Code reviews of PRs #31-34 surfaced 5 P1 issues and 7 P2 issues that should be fixed before the Phase 3-4 plans execute. This plan addresses all P1s and the most impactful P2s as targeted fixes on each PR's branch.

## Findings by PR

### PR #31 — Sidebar Redesign (`feat/macos-sidebar-redesign`)

| # | Sev | Issue | Fix |
|---|-----|-------|-----|
| 1 | P1 | `onDisappear` never fires on SidebarView in NavigationSplitView — timer cleanup is dead code | Remove `.onDisappear { marketService.stopMonitoring() }` — accept "always on" behavior since MarketStatusService should poll for the app's lifetime. Add comment explaining why. |
| 2 | P1 | PaperTradingService green dot empty until user visits Paper Trading — data not loaded eagerly | Add `.task { await paperTradingService.loadPositions() }` to ContentView so positions load at app startup, not on first navigation to Paper Trading. |
| 3 | P2 | `default:` on selectedDetailTab switch — should use explicit `case 2:` | Change `default:` to `case 2:` with a final `default: AnalysisView()` fallback. |
| 4 | P2 | ContentView at ~300 lines — extract sidebar enums | Move `ResearchSection`, `BuildSection`, `TradeSection`, `SidebarSection` to new `SidebarModels.swift` file. Add to Xcode project. |

### PR #32 — Auth Fixes (`fix/edge-function-auth-gaps`)

| # | Sev | Issue | Fix |
|---|-----|-------|-----|
| 5 | P1 | ga-strategy 401/503 responses missing CORS headers | Replace raw `new Response(JSON.stringify(...))` in gateway-key block with `errorResponse("Gateway key not configured", 503, origin)` and `errorResponse("Unauthorized", 401, origin)`. |
| 6 | P3 | AUTH_MATRIX says strategy-backtest-worker uses gateway-key but config.toml defaults to verify_jwt=true | Update AUTH_MATRIX.md to clarify: "verify_jwt=false in config.toml, SB_GATEWAY_KEY enforced in function" — verify config.toml entry exists. |

### PR #33 — Chart Freshness (`feat/chart-data-freshness`)

| # | Sev | Issue | Fix |
|---|-----|-------|-----|
| 7 | P1 | Duplicate `isStale` in `dataQuality` and `freshness` objects | Remove `isStale` from the dataQuality block (line ~1387) — let `freshness.isStale` be the single source. |
| 8 | P2 | `ageSeconds` uses unrounded minutes while `ageMinutes` is rounded | Compute `ageSeconds` from raw ms delta: `Math.round((Date.now() - new Date(lastActualBarTs).getTime()) / 1000)` |
| 9 | P2 | m15 SLA at 10min too tight (2-4min headroom) | Change `m15: 10` to `m15: 15` (3x the 5-minute cron) |

### PR #34 — API Registry (`feat/api-registry-contracts`)

| # | Sev | Issue | Fix |
|---|-----|-------|-----|
| 10 | **P1** | CI targets `main/develop` but default branch is `master` — contract tests never run | Change `branches: [main, develop]` to `branches: [main, master, develop]` in both push and pull_request triggers. |
| 11 | P2 | Registry grep uses substring match | Change to `grep -q "^  - name: ${func_name}$"` for exact matching. |
| 12 | P2 | user-refresh and data-health schemas removed with no replacement | Create `user-refresh.schema.json` and `data-health.schema.json` from the inline schemas that were removed. |
| 13 | P3 | No reverse registry check | Add CI step iterating registry names and verifying each has a function directory. |

## Implementation Units

- [x] **Unit 1: Fix PR #34 P1 — CI branch targeting** (CRITICAL — do first)

**Goal:** Make contract tests actually run on the default branch.

**Files:**
- Modify: `.github/workflows/api-contract-tests.yml`

**Approach:** Add `master` to both `push.branches` and `pull_request.branches` arrays. Also fix the grep substring match and add reverse registry check while in the file.

**Verification:** Push to PR #34 branch → CI workflow triggers on the PR.

---

- [x] **Unit 2: Fix PR #32 P1 — ga-strategy CORS on error responses**

**Goal:** Gateway-key 401/503 responses include proper CORS headers.

**Files:**
- Modify: `supabase/functions/ga-strategy/index.ts`

**Approach:** Replace raw `new Response()` calls in the gateway-key block with `errorResponse()` from `_shared/cors.ts`.

**Verification:** `curl` with wrong key returns 401 with `Access-Control-Allow-Origin` header.

---

- [x] **Unit 3: Fix PR #33 P1+P2 — freshness dedup + SLA + ageSeconds**

**Goal:** Single `isStale` source, correct ageSeconds computation, relaxed m15 SLA.

**Files:**
- Modify: `supabase/functions/chart/index.ts`

**Approach:** Remove `isStale` from dataQuality block. Fix ageSeconds to use raw ms. Change m15 SLA from 10 to 15.

**Verification:** Chart response has `isStale` only in `freshness` object. `ageSeconds` and `ageMinutes * 60` are consistent within 1 second.

---

- [x] **Unit 4: Fix PR #31 P1+P2 — sidebar lifecycle + enums extraction**

**Goal:** Fix dead onDisappear, eager PaperTradingService loading, extract sidebar enums.

**Files:**
- Modify: `client-macos/SwiftBoltML/Views/ContentView.swift`
- Create: `client-macos/SwiftBoltML/Views/SidebarModels.swift`
- Modify: `client-macos/SwiftBoltML.xcodeproj/project.pbxproj`

**Approach:** Remove dead `.onDisappear` + add comment. Add `.task` for eager position loading. Extract enums to SidebarModels.swift. Add new file to Xcode project via xcodeproj gem.

**Verification:** Build succeeds. Green dot appears on app launch if positions exist (without navigating to Paper Trading first).

---

- [x] **Unit 5: Fix PR #34 P2 — restore user-refresh and data-health schemas**

**Goal:** Restore contract test coverage for the two endpoints whose inline schemas were removed.

**Files:**
- Create: `supabase/functions/_shared/schemas/user-refresh.schema.json`
- Create: `supabase/functions/_shared/schemas/data-health.schema.json`
- Modify: `supabase/functions/registry.yaml` (update schema paths)

**Approach:** Recreate from the inline schemas that existed in the old api-contract-tests.yml (captured in git history of PR #34's diff).

**Verification:** `ajv compile` validates both schema files. Registry entries have schema paths filled in.

## Execution Order

1. **Unit 1** (PR #34 CI branch fix) — most critical, unblocks all contract testing
2. **Units 2-5** — parallel, each on its own PR branch

Each unit is a commit on the respective PR branch, then push to update the PR.
