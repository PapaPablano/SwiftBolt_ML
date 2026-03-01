---
status: pending
priority: p3
issue_id: "015"
tags: [code-review, architecture, swift, access-control]
dependencies: []
---

# 015: SupabaseService and its client are unnecessarily public

## Problem Statement

`SupabaseService` is declared `public class` with `public static let shared` and `public let client`. The macOS app is a single target with no framework dependencies — nothing outside the app module needs `public` access. Overly broad visibility allows any future module, Swift package, or plugin added to the project to obtain a fully-authenticated `SupabaseClient` directly. `internal` is the correct access level for app-target singletons.

## Findings

**File:** `client-macos/SwiftBoltML/Services/SupabaseService.swift` lines ~1-12

```swift
public class SupabaseService {
    public static let shared = SupabaseService()
    public let client: SupabaseClient
    ...
}
```

**Source:** security-sentinel agent (P5-LOW), architecture-strategist agent (P2)

## Proposed Solutions

### Option A: Change to internal / final (Recommended)

```swift
final class SupabaseService {
    static let shared = SupabaseService()
    private(set) var client: SupabaseClient
    ...
}
```
- `final` prevents subclassing (appropriate for a singleton)
- `private(set)` on `client` prevents external mutation; readable within the app
- Remove `public` from all declarations (defaults to `internal`)
- **Effort:** XSmall | **Risk:** Very Low

## Recommended Action

Option A. Low-risk cleanup that improves the access control baseline.

## Technical Details

**Affected files:**
- `client-macos/SwiftBoltML/Services/SupabaseService.swift`

**Verify callers:** Check that no test target or other module references `SupabaseService.shared` via a `@testable import` — if so, keep `internal` (which is accessible via `@testable`).

## Acceptance Criteria

- [ ] `SupabaseService` class visibility changed from `public` to `internal` (implicit)
- [ ] `static let shared` access level changed to `internal`
- [ ] `client` property changed to `private(set) var` (or `let`)
- [ ] App builds and connects to Supabase after change
- [ ] No compilation errors in other files that use `SupabaseService.shared.client`

## Work Log

- 2026-02-28: Identified by security-sentinel (P5) and architecture-strategist (P2) review agents in PR #23 code review
