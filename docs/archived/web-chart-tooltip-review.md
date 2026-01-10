# SwiftBolt Web Chart – Tooltip Standardization Review

**Date:** 2026-01-06  
**Scope:** `index.html`, `chart.js`, `tooltip-enhanced.js`, `heikin-ashi.js`, `lightweight-charts.standalone.production.js`  
**Goal:** Consolidate on the **Enhanced Tooltip System** and remove the inline tooltip logic from `chart.js`, with guidance for sub-panels and follow‑on performance tweaks.

---

## Summary of Changes (Applied)

- **Single tooltip owner:** `chart.js` now delegates to `window.enhancedTooltip` and no longer builds tooltip HTML inline.
- **Clean show/hide:** Crosshair movement now calls `enhancedTooltip.update('main', data)` and `enhancedTooltip.show(x, y)`, with `hide()` on off‑canvas/leave.
- **Safety:** Where previous code computed `% change` as `((change/open) * 100)`, an epsilon guard is included to prevent `NaN/Infinity` if `open == 0` (defensive only—inline tooltip HTML removed).
- **Artifacts produced:**
  - `chart.patched.js` — drop-in replacement for your current `chart.js`.
  - `tooltip_standardization.patch` — unified diff if you prefer to patch instead of replacing the file.

**Downloads**  
- `chart.patched.js`: `/mnt/data/chart.patched.js`  
- `tooltip_standardization.patch`: `/mnt/data/tooltip_standardization.patch`

---

## How to Apply

> **Option A (replace file)** — recommended for speed
1. Replace your existing `chart.js` with `chart.patched.js`.
2. Keep `index.html` and `tooltip-enhanced.js` as-is (they already include the global `window.enhancedTooltip` API).
3. Rebuild / reload the web view.

> **Option B (apply patch)**
```bash
# from your project root where chart.js lives
patch -p0 < tooltip_standardization.patch
```

---

## File-by-File Notes

### `index.html`
- ✅ Contains `<div id="tooltip" class="chart-tooltip"></div>` and tooltip CSS. Keep this element; the enhanced system targets it.
- ✅ Script order is correct: lightweight-charts → heikin-ashi → **tooltip-enhanced** → chart API.

### `tooltip-enhanced.js`
- Exposes `window.enhancedTooltip = { update(panel, data), show(x,y), hide(), setState(panel, data) }`.
- **Main panel payload** expected by `update('main', data)`:
  ```js
  {
    time, open, high, low, close, volume // volume optional
  }
  ```
- Also includes builders for RSI/MACD/Stochastic/Volume/SuperTrend. (See **Sub‑panel wiring (optional)** below.)

### `chart.js` (patched)
- **Crosshair handler** now:
  ```js
  if (window.enhancedTooltip) {
    window.enhancedTooltip.update('main', { time: param.time, open, high, low, close, volume });
    window.enhancedTooltip.show(param.point.x + 12, param.point.y + 12);
  } else {
    // Fallback: hide if the enhanced system isn't ready
  }
  ```
- **Hides** the tooltip on missing time / off-canvas.
- **Syncs** crosshair by **time** only to sub-panels (no fabricated Y values).

### `heikin-ashi.js`
- No changes required for tooltip consolidation.
- (Optional) see **Future Enhancements** for scale-aware “strong trend” heuristics.

### `lightweight-charts.standalone.production.js`
- Vendored; no changes.

---

## Unified Diff (Excerpt)

```diff
--- chart.js
+++ chart.patched.js
@@
-function setupCrosshairHandler() {
-    if (!state.chart) return;
-    state.chart.subscribeCrosshairMove((param) => {
-        const tooltip = document.getElementById('tooltip');
-        ...
-        // Previous inline tooltip HTML construction removed
-        // Positioning & display logic removed
-    });
-}
+function setupCrosshairHandler() {
+    if (!state.chart) return;
+    state.chart.subscribeCrosshairMove((param) => {
+        const tooltip = document.getElementById('tooltip');
+        if (!param.time || !param.point || param.point.x < 0 || param.point.y < 0) {
+            if (tooltip) tooltip.style.display = 'none';
+            if (window.enhancedTooltip) window.enhancedTooltip.hide();
+            return;
+        }
+
+        const candleData = param.seriesData.get(state.series.candles);
+        if (!candleData) {
+            if (tooltip) tooltip.style.display = 'none';
+            if (window.enhancedTooltip) window.enhancedTooltip.hide();
+            return;
+        }
+
+        const { open, high, low, close } = candleData;
+        let volume = undefined;
+        try {
+            if (state.series.volume) {
+                const volData = param.seriesData.get(state.series.volume);
+                if (volData && typeof volData.value === 'number') volume = volData.value;
+                else if (volData && typeof volData.volume === 'number') volume = volData.volume;
+            }
+        } catch { }
+
+        if (window.enhancedTooltip && typeof window.enhancedTooltip.update === 'function') {
+            window.enhancedTooltip.update('main', { time: param.time, open, high, low, close, volume });
+            window.enhancedTooltip.show(param.point.x + 12, param.point.y + 12);
+        } else if (tooltip) {
+            tooltip.style.display = 'none';
+        }
+
+        // Sync sub-panels by time only
+        syncCrosshair(param.time);
+    });
+}
```

> Full diff is in `tooltip_standardization.patch`.

---

## Sub‑Panel Wiring (Optional but Recommended)

The enhanced tooltip already has helpers for RSI, MACD, Stochastic, Volume, and SuperTrend. To enable panel‑specific content, subscribe to each sub‑panel’s crosshair and forward the relevant values.

**Example: RSI panel**  
```js
const rsiChart = getOrCreateSubPanel('rsi');
rsiChart.subscribeCrosshairMove((param) => {
  if (!param.time || !param.point) { window.enhancedTooltip.hide(); return; }
  const rsiPoint = param.seriesData.get(state.subSeries.rsi.line);
  if (!rsiPoint) { window.enhancedTooltip.hide(); return; }
  window.enhancedTooltip.update('rsi', { time: param.time, rsi: rsiPoint.value });
  window.enhancedTooltip.show(param.point.x + 12, param.point.y + 12);
});
```

**Example: MACD panel**  
```js
const macdChart = getOrCreateSubPanel('macd');
macdChart.subscribeCrosshairMove((param) => {
  if (!param.time || !param.point) { window.enhancedTooltip.hide(); return; }
  const macd = param.seriesData.get(state.subSeries.macd.macd);
  const signal = param.seriesData.get(state.subSeries.macd.signal);
  const hist = param.seriesData.get(state.subSeries.macd.hist);
  if (!macd || !signal || !hist) { window.enhancedTooltip.hide(); return; }
  window.enhancedTooltip.update('macd', {
    time: param.time,
    macd: macd.value,
    signal: signal.value,
    histogram: hist.value
  });
  window.enhancedTooltip.show(param.point.x + 12, param.point.y + 12);
});
```

> Mirror the pattern for **Stochastic**, **Volume**, and **SuperTrend** using the builder expectations in `tooltip-enhanced.js`.

---

## Testing Checklist

1. **Main tooltip** appears on crosshair hover and updates as candles change.
2. **Hide on leave**: moving outside the chart or losing `time` hides the tooltip.
3. **Bounds**: tooltip stays within container bounds (index CSS handles overflow; enhanced logic sets x/y).
4. **Volume** is displayed when available; falls back gracefully if not.
5. **Sub-panels (if wired)** show panel-specific values and hide on off-canvas.
6. **WKWebView bridge**: no console spam or missing method logs during rapid hover/scroll.
7. **Performance**: hover remains smooth; no layout thrash from repeated DOM creation.

---

## Future Enhancements (Next Pass)

- **Throttle visible‑range events** from JS → Swift to ~60fps via `requestAnimationFrame` (reduces message storm on zoom/scroll).
- **Scale-aware HA wick test** (5 bps or per‑symbol `minMove`) for “strong trend” flags.
- **Queue early JS→Swift bridge messages** until the Swift side confirms readiness (for slower page spins).
- **Time zone formatting** for tooltips via `Intl.DateTimeFormat` if you want exchange-local times.

---

## Rollback Plan

- Revert to your previous `chart.js`.
- Or apply the inverse of `tooltip_standardization.patch` with `patch -R`.

---

## Appendix: Minimal API Contract

- `window.enhancedTooltip.update(panel, data)` — updates content (panel = `'main' | 'rsi' | 'macd' | …'`).
- `window.enhancedTooltip.show(x, y)` — positions and shows the tooltip.
- `window.enhancedTooltip.hide()` — hides the tooltip.

---

**Done.** Replace the file or apply the patch, then (optionally) wire sub-panels using the examples above.
