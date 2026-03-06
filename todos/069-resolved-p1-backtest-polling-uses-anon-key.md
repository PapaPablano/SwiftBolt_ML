---
status: resolved
priority: p1
issue_id: "069"
tags: [code-review, auth, backtest, swift]
dependencies: []
---

# BacktestService.fetchJobStatus() uses anon key instead of user JWT

## Problem Statement

`BacktestService.fetchJobStatus()` hardcodes `Config.supabaseAnonKey` as the Bearer token when polling for backtest job status. Since `submitBacktest()` tags the job with the real `user_id`, the server's `.eq("user_id", userId)` filter resolves as "anonymous" on polls and returns no rows — **authenticated users' backtests will always time out**.

This was identified independently by Security, Performance Oracle, and Agent-Native reviewers.

## Findings

**File:** `client-macos/SwiftBoltML/Services/BacktestService.swift`

```swift
// Lines 113-116 — WRONG: always uses anon key
request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
```

Contrast with `submitBacktest()` which correctly uses the session JWT. The server-side handler at `supabase/functions/backtest-strategy/index.ts` queries:

```typescript
.eq("id", jobId)
.eq("user_id", userId)   // userId resolved from JWT — "anonymous" when anon key used
```

## Proposed Solutions

### Option A: Mirror submitBacktest() auth pattern (Recommended)
Add session lookup and fall back to anon key if unauthenticated:

```swift
request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
if let session = try? await SupabaseService.shared.client.auth.session {
    request.setValue("Bearer \(session.accessToken)", forHTTPHeaderField: "Authorization")
} else {
    request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
}
```

**Pros:** Matches existing pattern in `submitBacktest()`, minimal change. **Cons:** None.

### Option B: Pass jobId as a known-good value and don't filter by user_id on server
Remove the `user_id` filter from the server-side GET handler.

**Pros:** Simpler server code. **Cons:** Any user can poll any job by guessing a UUID; security regression.

### Option C: Extract shared `addAuthHeaders()` helper into BacktestService
Refactor both methods to share a common auth header helper.

**Pros:** DRY. **Cons:** Slightly more refactoring scope.

## Acceptance Criteria

- [ ] `fetchJobStatus()` sends the user's JWT when a session is available
- [ ] Falls back to anon key when no session (for anonymous poll use case)
- [ ] Pattern matches `submitBacktest()` auth logic
- [ ] Authenticated users' backtests complete successfully without timeout

## Work Log

- 2026-03-02: Identified during PR #25 review by Security Sentinel, Performance Oracle, Agent-Native reviewer

## Resources

- PR: https://github.com/PapaPablano/SwiftBolt_ML/pull/25
- File: `client-macos/SwiftBoltML/Services/BacktestService.swift` line 113
