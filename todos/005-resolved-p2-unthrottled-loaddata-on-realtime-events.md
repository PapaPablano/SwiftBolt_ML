---
status: pending
priority: p2
issue_id: "005"
tags: [code-review, performance, realtime, debounce, supabase]
dependencies: ["003"]
---

# 005: Unthrottled loadData() call on every realtime event

## Problem Statement

Every `AnyAction` change event on the `paper_trading_positions` channel triggers a full `loadData()` call, which issues two concurrent Supabase queries. In active trading scenarios where many positions open/close in rapid succession, this creates a write storm: N events → N × 2 concurrent queries. A `Debouncer` actor already exists in the codebase at `client-macos/SwiftBoltML/Utilities/Debouncer.swift` and should be used here.

## Findings

**File:** `client-macos/SwiftBoltML/Services/PaperTradingService.swift` lines 139-143

```swift
Task { [weak self] in
    for await _ in changes {
        await self?.loadData()    // full refetch on EVERY event, no throttle
    }
}
```

During a burst of 10 position updates in 500ms:
- 10 × `fetchOpenPositions()` = 10 PostgREST queries
- 10 × `fetchTradeHistory()` = 10 more PostgREST queries
- 20 concurrent queries hit the Supabase connection pool
- First 9 fetches are immediately stale when the 10th arrives

Existing `Debouncer` at `client-macos/SwiftBoltML/Utilities/Debouncer.swift` implements exactly this pattern.

**Source:** performance-oracle agent (P0)

## Proposed Solutions

### Option A: Use existing Debouncer actor (Recommended)

```swift
private let reloadDebouncer = Debouncer(delay: 0.3)  // 300ms

// In subscription loop:
for await _ in changes {
    guard !Task.isCancelled else { break }
    await reloadDebouncer.debounce {
        await self?.loadData()
    }
}
```
- **Pros:** Reuses existing codebase pattern; 300ms delay coalesces bursts while still feeling live
- **Cons:** Requires reading Debouncer API to confirm usage
- **Effort:** Small | **Risk:** Very Low

### Option B: AsyncStream with collect-and-batch
Collect events over a 500ms window, then do one reload per batch.
- **Pros:** More sophisticated batching
- **Cons:** More complex; Debouncer is sufficient
- **Effort:** Medium | **Risk:** Low

### Option C: Optimistic local state update
Apply the change event payload directly to `openPositions` array without a full refetch. Only refetch when payload is ambiguous (`DELETE` or `UPDATE` with missing fields).
- **Pros:** Best UX latency; minimal network
- **Cons:** Requires parsing `AnyAction` payload (INSERT/UPDATE/DELETE) and updating local state correctly
- **Effort:** Large | **Risk:** Medium (state sync bugs)

## Recommended Action

Option A (Debouncer). This is a one-liner once the Task leak (todo #003) is also fixed.

## Technical Details

**Affected files:**
- `client-macos/SwiftBoltML/Services/PaperTradingService.swift`
- `client-macos/SwiftBoltML/Utilities/Debouncer.swift` (read to confirm API)

## Acceptance Criteria

- [ ] Realtime event handler uses `Debouncer` with ≤500ms delay
- [ ] Rapid burst of 10 events results in ≤2 `loadData()` calls
- [ ] UI still updates within 500ms of a position change
- [ ] No regression in subscription cancellation (depends on todo #003 fix)

## Work Log

- 2026-02-28: Identified by performance-oracle review agent in PR #23 code review

## Resources

- [PR #23](https://github.com/PapaPablano/SwiftBolt_ML/pull/23)
- `client-macos/SwiftBoltML/Utilities/Debouncer.swift`
