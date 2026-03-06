---
status: resolved
priority: p2
issue_id: "075"
tags: [code-review, swift, strategy, crud]
dependencies: [071]
---

# Update and delete strategy not wired — creates duplicates on save, no way to delete

## Problem Statement

Two CRUD operations exist in the service layer but have no UI path:

1. **Save always creates, never updates**: `saveStrategyToSupabase()` always calls `createStrategy()`. When a user edits and re-saves an existing strategy, a duplicate is created instead of the original being updated.
2. **Delete has no UI trigger**: `StrategyListViewModel.deleteStrategy()` with optimistic removal + rollback is implemented but unreachable from the UI.

## Findings

**File:** `client-macos/SwiftBoltML/Views/IntegratedStrategyBuilder.swift` line 199-205

```swift
private func saveStrategyToSupabase(_ strategy: Strategy) async {
    await strategyListVM.createStrategy(   // ← always creates, never updates
        name: strategy.name,
        entryConditions: strategy.entryConditions,
        exitConditions: strategy.exitConditions
    )
}
```

`StrategyService.updateStrategy()` and `StrategyListViewModel.updateStrategy()` exist but are never called.

**File:** `client-macos/SwiftBoltML/ViewModels/StrategyListViewModel.swift` lines 117-138

```swift
func deleteStrategy(id: UUID) async { ... }  // ← never called from UI
```

## Proposed Solutions

### Option A: Track Supabase ID on selectedStrategy (Recommended)

Add an optional `supabaseId: UUID?` to the `Strategy` model. When loading from Supabase (todo 071), populate it. In `saveStrategyToSupabase`, check if the ID exists and call update vs create:

```swift
private func saveStrategyToSupabase(_ strategy: Strategy) async {
    if let id = strategy.supabaseId {
        await strategyListVM.updateStrategy(id: id, name: strategy.name,
            entryConditions: strategy.entryConditions,
            exitConditions: strategy.exitConditions)
    } else {
        await strategyListVM.createStrategy(...)
    }
}
```

For delete: add a context menu to the strategy picker:
```swift
Button(role: .destructive) {
    Task { await strategyListVM.deleteStrategy(id: supabaseStrategy.id) }
} label: { Label("Delete", systemImage: "trash") }
```

**Pros:** Correct CRUD semantics, uses existing service layer. **Cons:** Requires `Strategy` model change.

### Option B: Separate "New" vs "Edit" flows

Don't modify `Strategy` model — always create new, but add an explicit "Update" button in the editor toolbar that calls update, and a "Delete" button.

**Pros:** No model changes. **Cons:** Two save paths confuse users.

## Acceptance Criteria

- [ ] Saving an existing Supabase strategy updates it rather than creating a duplicate
- [ ] Users can delete a strategy from the list (context menu or button)
- [ ] Delete uses optimistic removal with rollback from `StrategyListViewModel.deleteStrategy()`
- [ ] New strategies still create correctly

## Work Log

- 2026-03-02: Identified during PR #25 review by Agent-Native reviewer

## Resources

- PR: https://github.com/PapaPablano/SwiftBolt_ML/pull/25
- File: `client-macos/SwiftBoltML/Views/IntegratedStrategyBuilder.swift` line 199
- File: `client-macos/SwiftBoltML/ViewModels/StrategyListViewModel.swift` line 117
