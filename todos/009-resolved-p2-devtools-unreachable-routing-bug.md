---
status: pending
priority: p2
issue_id: "009"
tags: [code-review, architecture, routing, swift, swiftui]
dependencies: []
---

# 009: DevTools section is unreachable — falls to `default:` in ContentView switch

## Problem Statement

`ContentView.swift` has a `switch activeSection` that handles all `SidebarSection` cases. The `.devtools` case was present in the original codebase but is not handled explicitly — it falls to `default:` which renders `DetailView`. The `#if DEBUG` sidebar link for Dev Tools is present and navigable, but clicking it shows the stock detail view instead of `DevToolsView`. This is a routing bug introduced when the `strategyPlatform` cases were added.

## Findings

**File:** `client-macos/SwiftBoltML/Views/ContentView.swift` lines 34-54

```swift
switch activeSection {
case .predictions:
    PredictionsView()...
case .portfolio:
    Text("Portfolio")
case .multileg:
    MultiLegStrategyListView()...
case .tradestation:
    IntegratedStrategyBuilder()
case .strategyPlatform(.builder):
    StrategyBuilderWebView(...)
case .strategyPlatform(.paperTrading):
    PaperTradingDashboardView()
case .strategyPlatform(.backtesting):
    BacktestResultsWebView(...)
default:                        // ← .devtools and .stocks both fall here
    DetailView()...
}
```

`SidebarSection.devtools` exists and is shown in the `#if DEBUG` sidebar section, but has no case in the switch. The `.stocks` case also falls to `default:` (but `DetailView` is the correct view for stocks, so that's arguably intentional). `DevToolsView` presumably exists since the sidebar link existed before this PR.

**Source:** architecture-strategist agent (P2)

## Proposed Solutions

### Option A: Add explicit .devtools case (Recommended)

```swift
#if DEBUG
case .devtools:
    DevToolsView()
        .environmentObject(appViewModel)
#endif
```

If `DevToolsView` doesn't exist, create a minimal placeholder:
```swift
#if DEBUG
case .devtools:
    Text("Dev Tools").frame(maxWidth: .infinity, maxHeight: .infinity)
#endif
```
- **Pros:** Explicit routing; compiler catches future missing cases
- **Effort:** XSmall | **Risk:** Very Low

### Option B: Rename `default:` to explicit `case .stocks:` + add `.devtools:`
Make the switch exhaustive with explicit cases for every enum value. The compiler will then flag any future unhandled cases.
- **Pros:** Exhaustive switch; safer long-term
- **Cons:** Slightly more verbose
- **Effort:** Small | **Risk:** Very Low

## Recommended Action

Option B — make the switch fully exhaustive. This prevents future routing silently falling through to DetailView.

## Technical Details

**Affected files:**
- `client-macos/SwiftBoltML/Views/ContentView.swift` (switch statement ~lines 34-54)

**Check for DevToolsView:**
```bash
grep -r "DevToolsView" client-macos/
```

## Acceptance Criteria

- [ ] `.devtools` has an explicit case in the switch statement
- [ ] Dev Tools sidebar link in DEBUG mode navigates to correct view
- [ ] `switch activeSection` has no unhandled `SidebarSection` cases (exhaustive or explicit `default:` for `.stocks` only)
- [ ] All existing navigation (stocks, portfolio, etc.) still works

## Work Log

- 2026-02-28: Identified by architecture-strategist review agent in PR #23 code review

## Resources

- [PR #23](https://github.com/PapaPablano/SwiftBolt_ML/pull/23)
