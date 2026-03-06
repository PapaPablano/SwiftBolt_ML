---
status: resolved
priority: p1
issue_id: "070"
tags: [code-review, swift, compilation-error]
dependencies: []
---

# saveStrategyToSupabase() is outside IntegratedStrategyBuilder struct — compilation error

## Problem Statement

`saveStrategyToSupabase()` is defined at brace depth 0, OUTSIDE the `IntegratedStrategyBuilder` struct body. The struct closes at line 195, but the function appears at line 199 with a dangling closing brace at line 206. The function references `strategyListVM` which is a `@State` property of the struct and is not in scope outside it.

This is a Swift compilation error. The code will not build.

## Findings

**File:** `client-macos/SwiftBoltML/Views/IntegratedStrategyBuilder.swift`

Verified via brace depth analysis:
```
195 [depth=0] }                    ← struct closes here
196 [depth=0]
197 [depth=0]     // MARK: - Supabase Helpers
198 [depth=0]
199 [depth=1]     private func saveStrategyToSupabase(_ strategy: Strategy) async {
200 [depth=1]         await strategyListVM.createStrategy(   ← strategyListVM NOT IN SCOPE
...
205 [depth=0]     }
206 [depth=-1] }                    ← dangling brace
```

## Proposed Solutions

### Option A: Move function inside the struct (Recommended)

Delete lines 195-206 and re-insert the function before the last `}` of the struct body:

```swift
// MARK: - Supabase Helpers

private func saveStrategyToSupabase(_ strategy: Strategy) async {
    await strategyListVM.createStrategy(
        name: strategy.name,
        entryConditions: strategy.entryConditions,
        exitConditions: strategy.exitConditions
    )
}
```

Place this inside the `IntegratedStrategyBuilder` body, before the closing `}`.

**Pros:** Minimal change, restores intended behavior. **Cons:** None.

### Option B: Convert to an extension on IntegratedStrategyBuilder

```swift
extension IntegratedStrategyBuilder {
    private func saveStrategyToSupabase(_ strategy: Strategy) async { ... }
}
```

**Pros:** Clean MARK organization. **Cons:** Extensions cannot access stored `@State` properties directly.

## Acceptance Criteria

- [ ] `saveStrategyToSupabase` compiles successfully as part of `IntegratedStrategyBuilder`
- [ ] `strategyListVM.createStrategy()` is accessible from within the function
- [ ] App builds without errors in Xcode

## Work Log

- 2026-03-02: Identified during PR #25 review by Pattern Recognition Specialist (verified via brace depth analysis)

## Resources

- PR: https://github.com/PapaPablano/SwiftBolt_ML/pull/25
- File: `client-macos/SwiftBoltML/Views/IntegratedStrategyBuilder.swift` lines 195-206
