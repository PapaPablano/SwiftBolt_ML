---
status: pending
priority: p3
issue_id: "011"
tags: [code-review, architecture, realtime, resilience, ux]
dependencies: ["003"]
---

# 011: Silent for-await loop exit — no reconnection or user notification

## Problem Statement

When the Supabase Realtime connection drops, the `for await _ in changes` loop in `PaperTradingService.subscribeToPositions()` exits silently. There is no reconnection attempt, no user-visible indicator (beyond the existing `SupabaseConnectivityBanner` for DNS failures), and no mechanism to distinguish "no changes" from "disconnected." The positions dashboard goes stale without the user knowing.

## Findings

**File:** `client-macos/SwiftBoltML/Services/PaperTradingService.swift` lines 139-143

```swift
Task { [weak self] in
    for await _ in changes {
        await self?.loadData()
    }
    // Loop exits silently — dropped connection, exhausted channel, anything
    // No log, no reconnect, no UI update
}
```

On a flaky network or after a Supabase deployment, the channel silently disconnects. The user sees stale data with no indication that live updates stopped.

**Source:** architecture-strategist agent (P2)

## Proposed Solutions

### Option A: Re-subscribe with exponential backoff after loop exit

```swift
private func startSubscriptionLoop() async {
    var delay: UInt64 = 1_000_000_000  // 1 second
    while !Task.isCancelled {
        let channel = supabase.channel("paper_trading_positions")
        realtimeChannel = channel
        let changes = channel.postgresChange(AnyAction.self, ...)
        await channel.subscribe()

        for await _ in changes {
            guard !Task.isCancelled else { return }
            await reloadDebouncer.debounce { [weak self] in
                await self?.loadData()
            }
        }

        // Loop exited — channel dropped
        await MainActor.run { self.isLive = false }
        if !Task.isCancelled {
            try? await Task.sleep(nanoseconds: delay)
            delay = min(delay * 2, 30_000_000_000)  // cap at 30s
        }
    }
}
```

Add `@Published var isLive = true` to surface reconnection state to the UI.
- **Pros:** Resilient to transient disconnections; user informed via `isLive` flag
- **Effort:** Medium | **Risk:** Low

### Option B: Poll as fallback
When the loop exits, fall back to polling `loadData()` every 5 seconds until reconnected.
- **Pros:** Simpler; guarantees data freshness even during realtime outage
- **Cons:** Higher Supabase query load; less elegant
- **Effort:** Small | **Risk:** Low

### Option C: Rely on existing SupabaseConnectivityBanner
The banner already covers DNS failures. Document that deeper realtime disconnections are not currently handled.
- **Pros:** No change needed
- **Cons:** Stale data silently; poor UX for active traders
- **Effort:** None | **Risk:** High (silent staleness)

## Recommended Action

Option A combined with an `isLive` indicator in `PaperTradingDashboardView` (small dot or text badge). Do this after the P1/P2 fixes are resolved.

## Technical Details

**Affected files:**
- `client-macos/SwiftBoltML/Services/PaperTradingService.swift`
- `client-macos/SwiftBoltML/Views/PaperTradingDashboardView.swift` (add `isLive` indicator)

**Depends on:** todo #003 (Task handle storage) — the reconnect loop needs the same `subscriptionTask` property.

## Acceptance Criteria

- [ ] Loop exit triggers reconnection attempt with backoff
- [ ] `PaperTradingService` exposes `@Published var isLive: Bool`
- [ ] `PaperTradingDashboardView` shows "reconnecting..." indicator when `isLive == false`
- [ ] After reconnection, `isLive` returns to `true` and data refreshes
- [ ] Manual `unsubscribe()` cleanly exits the loop without triggering reconnection

## Work Log

- 2026-02-28: Identified by architecture-strategist review agent in PR #23 code review

## Resources

- [PR #23](https://github.com/PapaPablano/SwiftBolt_ML/pull/23)
