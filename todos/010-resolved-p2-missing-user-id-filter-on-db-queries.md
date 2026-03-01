---
status: pending
priority: p2
issue_id: "010"
tags: [code-review, security, supabase, rls, data-scoping]
dependencies: []
---

# 010: No user_id filter on PaperTradingService database queries

## Problem Statement

`fetchOpenPositions()` and `fetchTradeHistory()` in `PaperTradingService.swift` do not include a `user_id` filter in the query. Data security entirely depends on RLS policies being correctly configured. If RLS is absent or misconfigured on either table, all users' positions and trades would be silently loaded. The absence of a client-side user filter also means a future RLS misconfiguration would not be caught at the app layer. The realtime channel subscription also lacks a user-scoped filter.

## Findings

**File:** `client-macos/SwiftBoltML/Services/PaperTradingService.swift` lines 153-172

```swift
private func fetchOpenPositions() async throws -> [PaperPosition] {
    let response: [PaperPosition] = try await supabase
        .from("paper_trading_positions")
        .select("*")
        .eq("status", value: "open")   // only status filter — no user_id
        .order("entry_time", ascending: false)
        .execute().value
    return response
}

private func fetchTradeHistory() async throws -> [PaperTrade] {
    let response: [PaperTrade] = try await supabase
        .from("paper_trading_trades")
        .select("*")          // no user_id filter
        .order("exit_time", ascending: false)
        .limit(100)
        .execute().value
    return response
}
```

Similarly, the realtime channel at line 131-137 has no filter — change events for other users' rows also trigger `loadData()`.

**Source:** security-sentinel agent (P4-MEDIUM)

## Proposed Solutions

### Option A: Add explicit user_id filter (Recommended)

```swift
guard let userId = supabase.auth.currentUser?.id else {
    throw PaperTradingError.notAuthenticated
}

// In fetchOpenPositions:
.eq("user_id", value: userId.uuidString)
.eq("status", value: "open")

// In fetchTradeHistory:
.eq("user_id", value: userId.uuidString)

// In subscribeToPositions channel:
let changes = channel.postgresChange(
    AnyAction.self,
    schema: "public",
    table: "paper_trading_positions",
    filter: "user_id=eq.\(userId.uuidString)"
)
```
- **Pros:** Defense-in-depth independent of RLS; explicit intent; prevents silent data leaks if RLS misconfigures
- **Effort:** Small | **Risk:** Very Low

### Option B: Verify RLS only, no client filter
Confirm `user_id = auth.uid()` policies exist on both tables via `get_advisors` and document the decision to rely on RLS.
- **Pros:** Less code; standard Supabase pattern
- **Cons:** No app-layer protection; fragile to RLS policy changes
- **Effort:** XSmall (verification only) | **Risk:** Medium

## Recommended Action

Option A. Defense-in-depth is worth the 2 lines per query.

## Technical Details

**Affected files:**
- `client-macos/SwiftBoltML/Services/PaperTradingService.swift` (fetchOpenPositions, fetchTradeHistory, subscribeToPositions)

**Prerequisite:** Verify that `paper_trading_positions` and `paper_trading_trades` have RLS policies in Supabase. The schema was created in PR #22 — check `supabase/migrations/` for the RLS definitions.

## Acceptance Criteria

- [ ] `fetchOpenPositions()` includes `.eq("user_id", ...)` filter
- [ ] `fetchTradeHistory()` includes `.eq("user_id", ...)` filter
- [ ] Realtime channel subscription includes `filter: "user_id=eq.{userId}"`
- [ ] App handles `supabase.auth.currentUser == nil` gracefully (not authenticated)
- [ ] Positions from other test users are not visible in the dashboard

## Work Log

- 2026-02-28: Identified by security-sentinel review agent in PR #23 code review

## Resources

- [PR #23](https://github.com/PapaPablano/SwiftBolt_ML/pull/23)
- [Supabase RLS documentation](https://supabase.com/docs/guides/auth/row-level-security)
