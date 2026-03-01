---
status: pending
priority: p3
issue_id: "014"
tags: [code-review, security, logging, swift, cleanup]
dependencies: []
---

# 014: Debug print statements run in release builds and log ticker data to stdout

## Problem Statement

`ContentView.swift` contains `print("[DEBUG] ...")` statements outside `#if DEBUG` guards that log the selected symbol ticker to stdout on every symbol change. These execute in release builds and are readable via Console.app or `log stream` by any process with the same user context. While tickers are low-sensitivity, it establishes a pattern of leaking runtime state in production builds.

## Findings

**File:** `client-macos/SwiftBoltML/Views/ContentView.swift` lines 64-71

```swift
.onChange(of: appViewModel.selectedSymbol) { oldValue, newValue in
    print("[DEBUG] ========================================")
    print("[DEBUG] ContentView detected selectedSymbol change")
    print("[DEBUG] - Old: \(oldValue?.ticker ?? "nil")")
    print("[DEBUG] - New: \(newValue?.ticker ?? "nil")")
    print("[DEBUG] ========================================")
    ...
}
```

These are outside `#if DEBUG` unlike the `onAppear` block just below (lines 72-79), which correctly uses `#if DEBUG`.

**Source:** security-sentinel agent (P6-LOW)

## Proposed Solutions

### Option A: Wrap in #if DEBUG (Recommended)

```swift
.onChange(of: appViewModel.selectedSymbol) { oldValue, newValue in
    #if DEBUG
    print("[DEBUG] ContentView selectedSymbol: \(oldValue?.ticker ?? "nil") → \(newValue?.ticker ?? "nil")")
    #endif
    DispatchQueue.main.async { activeSection = .stocks }
}
```
- **Effort:** XSmall | **Risk:** Very Low

### Option B: Replace with os_log using .private data class

```swift
private let logger = Logger(subsystem: "com.swiftbolt.ml", category: "ContentView")
// ...
logger.debug("selectedSymbol changed: \(oldValue?.ticker ?? "nil", privacy: .private) → \(newValue?.ticker ?? "nil", privacy: .private)")
```
- **Pros:** Consistent with codebase Logger usage; privacy-tagged; still available in release with `log stream`
- **Effort:** XSmall | **Risk:** Very Low

## Recommended Action

Option A (wrap in #if DEBUG) as quick fix. The codebase already has the `onAppear` block correctly guarded below — these just need the same treatment.

## Technical Details

**Affected files:**
- `client-macos/SwiftBoltML/Views/ContentView.swift` lines 64-71

## Acceptance Criteria

- [ ] `print` statements wrapped in `#if DEBUG` or replaced with private-tagged `Logger` calls
- [ ] No ticker data logged to stdout in release builds

## Work Log

- 2026-02-28: Identified by security-sentinel review agent in PR #23 code review
