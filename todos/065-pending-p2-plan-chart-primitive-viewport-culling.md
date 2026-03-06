---
status: pending
priority: p2
issue_id: "065"
tags: [code-review, performance, tradingview, chart]
dependencies: []
---

# 065 — Chart Trade Primitives Need Viewport Culling + Object Pooling

## Problem Statement

The plan's `TradeRegionPrimitive` creates one `TradeRegionPaneView` per trade in `updateAllViews()`, which TradingView calls on every frame during zoom/scroll/crosshair movement. With 100 trades, this means 300+ Canvas draw calls per frame and 100 object allocations per frame (GC pressure). Without viewport culling, panning a chart with 50+ trades will drop below 30fps.

## Findings

- **Performance Oracle:** "This is the difference between 60fps and <20fps on charts with 50+ trades"
- **Performance Oracle:** Viewport culling reduces active renderers to 5-15 regardless of total trade count

## Proposed Solutions

### Option A: Viewport Culling + Object Pooling (Recommended)
- In renderer's `draw()`, skip trades outside visible time range
- In `updateAllViews()`, reuse existing view objects instead of re-allocating
- For >20 visible trades, reduce opacity progressively
- **Pros:** 60fps maintained at any trade count
- **Cons:** Slightly more complex primitive implementation
- **Effort:** Small (add ~20 lines to primitive)
- **Risk:** Low

## Technical Details

**Affected files:**
- `frontend/src/components/chart/TradeRegionPrimitive.ts` (proposed)

**Key pattern:**
```typescript
// Viewport culling in renderer
draw(target: CanvasRenderingTarget2D): void {
  const visibleRange = this._source.chart.timeScale().getVisibleLogicalRange();
  if (!visibleRange) return;
  if (this._trade.exitLogical < visibleRange.from ||
      this._trade.entryLogical > visibleRange.to) return;
  // ... actual drawing
}
```

## Acceptance Criteria

- [ ] Chart maintains 60fps with 100+ trades during pan/zoom
- [ ] Only visible trades render Canvas operations
- [ ] View objects pooled (no per-frame allocation)
- [ ] Opacity reduces when >20 trades visible

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-03-01 | Created from plan technical review | Performance Oracle analysis |
