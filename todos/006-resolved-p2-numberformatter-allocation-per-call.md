---
status: pending
priority: p2
issue_id: "006"
tags: [code-review, performance, swift, memory]
dependencies: []
---

# 006: NumberFormatter allocated on every formatCurrency() call

## Problem Statement

`formatCurrency()` in `PaperTradingDashboardView.swift` allocates a new `NumberFormatter` on every call. With 8 metric cards + N position rows + N trade history rows visible simultaneously, this creates hundreds of allocations per render pass. `NumberFormatter` is an expensive object to create (it reads locale tables) and should be a file-level or class-level constant.

## Findings

**File:** `client-macos/SwiftBoltML/Views/PaperTradingDashboardView.swift` (formatCurrency function)

```swift
// Current pattern (approximately):
func formatCurrency(_ value: Double) -> String {
    let formatter = NumberFormatter()   // ← new instance every call
    formatter.numberStyle = .currency
    formatter.maximumFractionDigits = 2
    return formatter.string(from: NSNumber(value: value)) ?? "$0.00"
}
```

Called from:
- `MetricsGridView`: 8 cards (totalPnl, openPnl, winRate, etc.)
- `PositionRowView`: once per open position
- `TradeRowView`: once per trade history row

On a view with 10 positions + 20 trades + 8 metrics = 38 formatter allocations per render.

**Additional finding (code-simplicity-reviewer):** `formatCurrency` uses `NumberFormatter` with `.currency` style, while `formatPrice` (also in the same file) uses `String(format: "$%.2f", value)`. `NumberFormatter` with `.currency` style formats negative values using locale-specific notation — e.g., `($123.45)` with parentheses instead of `$-123.45` on some locales. For a P&L display, this can produce confusing output. Both functions should use the same approach.

**Source:** performance-oracle agent (P1), code-simplicity-reviewer agent

## Proposed Solutions

### Option A: File-level private constant (Recommended)

```swift
// At file scope, above any struct/class:
private let currencyFormatter: NumberFormatter = {
    let f = NumberFormatter()
    f.numberStyle = .currency
    f.maximumFractionDigits = 2
    return f
}()
```

Then `formatCurrency` simply calls `currencyFormatter.string(...)`.
- **Pros:** Zero allocation cost; thread-safe (NumberFormatter is not thread-safe but @MainActor guarantees single-thread access); idiomatic Swift
- **Cons:** None
- **Effort:** XSmall | **Risk:** Very Low

### Option B: Static property on a helper struct
Create `Formatters.currency` as a static — cleaner if multiple formatters are needed.
- **Pros:** Groupable; reusable across files
- **Cons:** Slight over-engineering for one formatter
- **Effort:** Small | **Risk:** Very Low

### Option C: SwiftUI `.formatted()` API (iOS 15+/macOS 12+)
```swift
value.formatted(.currency(code: "USD"))
```
- **Pros:** No custom formatter needed; locale-aware; more declarative
- **Cons:** Less control over fraction digits; macOS 12+ requirement
- **Effort:** Small | **Risk:** Low

## Recommended Action

Option A (file-level constant) for immediate fix; Option C is worth considering for a future SwiftUI modernization pass.

## Technical Details

**Affected files:**
- `client-macos/SwiftBoltML/Views/PaperTradingDashboardView.swift`

## Acceptance Criteria

- [ ] `NumberFormatter` created exactly once (file-level or static, not per-call)
- [ ] `formatCurrency()` uses the shared instance
- [ ] P&L display still correct for positive, negative, and zero values
- [ ] No regression for non-USD locales if locale-aware formatting is kept

## Work Log

- 2026-02-28: Identified by performance-oracle review agent in PR #23 code review

## Resources

- [PR #23](https://github.com/PapaPablano/SwiftBolt_ML/pull/23)
