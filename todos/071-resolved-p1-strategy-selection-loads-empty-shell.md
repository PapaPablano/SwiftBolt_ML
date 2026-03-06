---
status: resolved
priority: p1
issue_id: "071"
tags: [code-review, swift, strategy, persistence]
dependencies: []
---

# Strategy selection loads empty shell — saved conditions not retrieved

## Problem Statement

When a user selects a saved strategy from the list, `IntegratedStrategyBuilder` creates a new `Strategy(name: supabaseStrategy.name)` with **empty entry and exit conditions**. `StrategyService.getStrategy(id:)` exists and returns the full config, but it is never called. Strategy persistence is effectively write-only — users cannot load conditions for editing or backtesting.

Identified by Agent-Native reviewer and Simplicity reviewer.

## Findings

**File:** `client-macos/SwiftBoltML/Views/IntegratedStrategyBuilder.swift` lines 110-113

```swift
ForEach(strategyListVM.strategies) { supabaseStrategy in
    Button(supabaseStrategy.name) {
        // Load full strategy from local model for now
        selectedStrategy = Strategy(name: supabaseStrategy.name)  // ← empty conditions!
    }
}
```

`StrategyService.getStrategy(id:)` returns the full `SupabaseStrategy` with encoded conditions.
`fromSupabaseCondition()` exists to convert `SupabaseCondition` → `StrategyCondition`.

Neither is called.

**Impact:** Running a backtest on a "loaded" strategy immediately hits the empty-conditions validation warning and produces a meaningless result.

## Proposed Solutions

### Option A: Fetch full strategy on selection (Recommended)

```swift
Button(supabaseStrategy.name) {
    Task {
        do {
            let full = try await StrategyService.shared.getStrategy(id: supabaseStrategy.id)
            selectedStrategy = Strategy(
                name: full.name,
                entryConditions: full.config.entryConditions.compactMap { fromSupabaseCondition($0) },
                exitConditions: full.config.exitConditions.compactMap { fromSupabaseCondition($0) }
            )
        } catch {
            // Show inline error or log
        }
    }
}
```

**Pros:** Correct behavior, uses existing `getStrategy` and `fromSupabaseCondition` infrastructure. **Cons:** Async — need loading state indicator.

### Option B: Include full conditions in the list endpoint

Modify `StrategyService.listStrategies()` to decode conditions alongside the name.

**Pros:** Single network call. **Cons:** More data transferred for list view, wider server-side change.

### Option C: Keep as-is and add a "Load" button

Keep empty shell for the list, add an explicit "Load Full Strategy" button in the editor.

**Pros:** Simpler immediate fix. **Cons:** Poor UX — the user doesn't know conditions are missing.

## Acceptance Criteria

- [ ] Selecting a strategy from the list loads its entry and exit conditions
- [ ] Conditions are correctly converted from Supabase format via `fromSupabaseCondition()`
- [ ] Loading state shown while fetching (spinner or disabled state)
- [ ] Error state shown if fetch fails
- [ ] Running a backtest on a loaded strategy uses the saved conditions

## Work Log

- 2026-03-02: Identified during PR #25 review by Agent-Native reviewer (verified in source)

## Resources

- PR: https://github.com/PapaPablano/SwiftBolt_ML/pull/25
- File: `client-macos/SwiftBoltML/Views/IntegratedStrategyBuilder.swift` line 111
- Service method: `client-macos/SwiftBoltML/Services/StrategyService.swift` `getStrategy(id:)`
- Mapper: `client-macos/SwiftBoltML/Services/StrategyService.swift` `fromSupabaseCondition()`
