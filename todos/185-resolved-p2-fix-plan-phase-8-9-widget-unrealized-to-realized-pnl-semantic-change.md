---
status: resolved
priority: p2
issue_id: "185"
tags: [plan-review, live-trading, frontend, ux, api-design]
dependencies: []
---

# Fix Plan Phase 8.9: `LiveTradingStatusWidget` switches from unrealized to realized P&L — UX regression not acknowledged

## Problem Statement

Phase 8.9 changes `LiveTradingStatusWidget` to read P&L from the `summary` endpoint (today's realized P&L after Phase 7.3 date-bounding). The current widget computes *unrealized* P&L from open positions. These are fundamentally different numbers. A user in two profitable open trades with no closed trades today will see "$0 today" after Phase 8.9, down from showing live unrealized gains. The plan does not acknowledge this semantic change or update the widget label.

## Findings

**Spec-Flow Analyzer (GAP-P2-3):**

Current `LiveTradingStatusWidget` (lines 30–39) calculates:
```typescript
const unrealizedPnl = openPositions.reduce(
  (sum, pos) => sum + (pos.current_price - pos.entry_price) * pos.quantity, 0
);
```

After Phase 8.9, this is replaced by `summary.total_pnl` — today's *realized* P&L from closed trades.

**Semantic difference:**
- **Unrealized P&L**: reflects current market exposure, changes with price movements, shows the value of open positions
- **Realized P&L**: reflects completed trade outcomes, only changes when trades close, does not show current market exposure

**UX regression:**
A user with two profitable open positions and no closed trades today will see:
- **Before Phase 8.9**: positive unrealized P&L (showing live gains)
- **After Phase 8.9**: $0 or null (no closed trades = no realized P&L)

This will be confusing. The user may think something is broken.

**Options:**

1. **Show both**: Add a second row to the widget — "Open P&L" (unrealized from positions) and "Today's P&L" (realized from summary). This requires the existing positions fetch to remain alongside the new summary fetch.

2. **Keep unrealized only**: Revert Phase 8.9 and instead fix the unrealized P&L calculation to use `current_price` correctly (currently computed locally without server-side price updates).

3. **Show realized only with clear label**: Keep Phase 8.9 but explicitly label it "Today's Realized P&L" and add a secondary display showing "X positions open" with no P&L number — make it clear realized is shown.

**Recommended**: Option 1 (show both) or Option 3 (clear label). Option 2 loses the realized P&L visibility that Phase 8.9 was trying to add.

## Proposed Solution

Amend Phase 8.9 in the plan to explicitly acknowledge the semantic change from unrealized to realized P&L and choose one of the three display options. Update the widget label to clearly distinguish realized vs. unrealized, or show both.

## Acceptance Criteria

- [x] Plan explicitly documents the semantic change: Phase 8.9 replaces unrealized P&L display with realized P&L
- [x] Widget label updated to distinguish realized P&L from unrealized P&L
- [x] Either: both values shown, OR clear labeling, OR documented rationale for showing only realized
- [x] UX regression acknowledged: users with open positions and no closed trades should not see a confusingly empty or $0 P&L figure

## Work Log

- 2026-03-03: Finding from spec-flow-analyzer (GAP-P2-3) during plan review. Unrealized and realized P&L are fundamentally different user-facing metrics; the switch should be deliberate, not accidental.

- 2026-03-03: RESOLVED. Plan amended to address all findings.
