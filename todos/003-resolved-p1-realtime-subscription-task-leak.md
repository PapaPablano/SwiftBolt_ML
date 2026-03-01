---
status: pending
priority: p1
issue_id: "003"
tags: [code-review, performance, memory-leak, swift-concurrency, realtime]
dependencies: []
---

# 003: Untracked Task in subscribeToPositions() causes accumulating memory leak

## Problem Statement

`PaperTradingService.subscribeToPositions()` spawns a `Task { for await _ in changes { ... } }` with no handle stored. Each time the user navigates to Paper Trading and back, a new `Task` is spawned — the old one is never cancelled and continues listening, accumulating over the session lifetime. With enough navigation cycles, there are N redundant subscription loops all triggering `loadData()` concurrently. **BLOCKS MERGE** (P0 performance + P1 architecture finding).

## Findings

**File:** `client-macos/SwiftBoltML/Services/PaperTradingService.swift` lines 130-143

```swift
func subscribeToPositions() async {
    let channel = supabase.channel("paper_trading_positions")
    realtimeChannel = channel
    let changes = channel.postgresChange(AnyAction.self, ...)
    await channel.subscribe()
    Task { [weak self] in              // ← handle discarded, never cancelled
        for await _ in changes {
            await self?.loadData()
        }
    }
}
```

Additionally in `PaperTradingDashboardView.swift`, the view's `.onDisappear` calls `unsubscribe()` on the channel, but the orphaned `Task` is still iterating its now-closed `AsyncSequence` and may loop indefinitely or suppress proper cleanup.

**Source:** performance-oracle agent (P0), architecture-strategist agent (P1)

## Proposed Solutions

### Option A: Store Task handle and cancel on unsubscribe (Recommended)

```swift
private var subscriptionTask: Task<Void, Never>?

func subscribeToPositions() async {
    subscriptionTask?.cancel()  // cancel previous if re-entering
    let channel = supabase.channel("paper_trading_positions")
    realtimeChannel = channel
    let changes = channel.postgresChange(AnyAction.self, ...)
    await channel.subscribe()
    subscriptionTask = Task { [weak self] in
        for await _ in changes {
            guard !Task.isCancelled else { break }
            await self?.loadData()
        }
    }
}

func unsubscribe() async {
    subscriptionTask?.cancel()
    subscriptionTask = nil
    await realtimeChannel?.unsubscribe()
    realtimeChannel = nil
}
```
- **Pros:** Clean cancellation; no accumulation on re-navigation; mirrors existing Swift concurrency patterns
- **Effort:** Small | **Risk:** Very Low

### Option B: Use structured concurrency (task group in view)
Move subscription lifecycle into a `.task` modifier in the SwiftUI view — Swift automatically cancels the task when the view disappears.

```swift
// In PaperTradingDashboardView:
.task {
    await service.loadData()
    for await _ in service.positionChanges() {
        await service.loadData()
    }
}
// .onDisappear no longer needed — .task cancels automatically
```
- **Pros:** Structured concurrency; no manual cancel needed
- **Cons:** Requires refactoring service to return AsyncSequence; more invasive change
- **Effort:** Medium | **Risk:** Low

### Option C: Debounce + throttle as immediate patch
Not a fix for the leak — still need Option A or B. But should also add debouncing (see todo #005).
- **Effort:** Small (add to Option A) | **Risk:** Low

## Recommended Action

Option A as the immediate fix (small, targeted). Option B is the architecturally cleaner long-term goal.

## Technical Details

**Affected files:**
- `client-macos/SwiftBoltML/Services/PaperTradingService.swift` (subscribeToPositions + unsubscribe)
- `client-macos/SwiftBoltML/Views/PaperTradingDashboardView.swift` (onDisappear cleanup)

## Acceptance Criteria

- [ ] `subscriptionTask: Task<Void, Never>?` stored as property on `PaperTradingService`
- [ ] `subscribeToPositions()` cancels any existing task before creating a new one
- [ ] `unsubscribe()` cancels the task before setting to nil
- [ ] Navigate to Paper Trading 5 times and verify memory usage doesn't grow
- [ ] Realtime updates still trigger UI refresh after fix

## Work Log

- 2026-02-28: Identified by performance-oracle (P0) and architecture-strategist (P1) in PR #23 code review

## Resources

- [PR #23](https://github.com/PapaPablano/SwiftBolt_ML/pull/23)
- [Swift Task cancellation documentation](https://developer.apple.com/documentation/swift/task/cancel())
