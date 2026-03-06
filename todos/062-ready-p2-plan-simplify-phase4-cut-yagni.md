---
status: ready
priority: p2
issue_id: "062"
tags: [code-review, simplicity, yagni, plan-amendment]
dependencies: []
---

# 062 — Plan Phase 4 Over-Engineered: Cut YAGNI Components

## Problem Statement

Phase 4 proposes 5 new components, 2 new npm dependencies, and a 5-tab results interface. The Simplicity Reviewer identified that most of this is unnecessary for v1:

- `MonthlyBreakdown.tsx` — YAGNI (no user request)
- `ReturnsHeatmap.tsx` — YAGNI (decorative, equity curve shows same info)
- `DrawdownChart.tsx` — Defer to v2 (max DD number already in cards)
- CSV export — YAGNI
- 5-tab sub-interface — Over-designed
- `@tanstack/react-table` — Overkill for 8-column trade table
- `@uiwjs/react-heat-map` — Dependency for cut feature

## Findings

- **Simplicity Reviewer:** "~800 LOC not written, 2 dependencies not added, 4 components eliminated"
- **Performance Oracle:** "70KB bundle increase from 2 new deps; needs code splitting if kept"
- **Architecture Strategist:** "Phase 4 is the largest phase — could be split into 4a (core) + 4b (analytics)"

## Proposed Solutions

### Option A: Aggressive Simplification (Simplicity Reviewer Recommendation)
- Remove 20-row cap on existing table, add direction/closeReason columns
- Extract EquityCurveChart (pure refactor)
- No new npm dependencies
- No tabs, show cards + chart + table vertically
- **Pros:** ~60% LOC reduction, no new deps, dramatically less maintenance
- **Cons:** Less feature-rich results view
- **Effort:** Small (vs Large for original Phase 4)
- **Risk:** Low

### Option B: Moderate Simplification (Compromise)
- Keep TanStack Table for sortable/paginated trade table
- Keep DrawdownChart (genuinely useful)
- Cut: MonthlyBreakdown, ReturnsHeatmap, CSV export
- Cut: `@uiwjs/react-heat-map` dependency
- Reduce 5 tabs to 3: Overview | Trades | Drawdown
- **Pros:** Useful analytics without the decorative extras
- **Cons:** Still adds TanStack Table dependency
- **Effort:** Medium
- **Risk:** Low

### Option C: Keep Original Plan with Code Splitting
- Keep all 5 components as planned
- Add React.lazy code splitting + Vite manualChunks
- **Pros:** Full feature set
- **Cons:** Most scope, 2 new deps, most maintenance
- **Effort:** Large
- **Risk:** Medium (bundle size, maintenance)

## Technical Details

**Components to evaluate:**
- `frontend/src/App.tsx` (lines 340-380 — existing table capped at 20)
- `frontend/src/components/BacktestResultsPanel.tsx` (lines 287-323 — capped at 15)

## Acceptance Criteria

- [ ] Trade table shows ALL trades (not capped at 15-20)
- [ ] Direction and CloseReason columns visible
- [ ] Equity curve extracted to own component
- [ ] Chosen approach documented in plan

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-03-01 | Created from plan technical review | Simplicity + Performance reviewers aligned on cuts |
