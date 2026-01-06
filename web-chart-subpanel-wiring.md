
# SwiftBolt Web Chart – Sub‑Panel Tooltip Wiring

**Date:** 2026-01-06  
**Scope:** `chart.js` (RSI, MACD, Stochastic, Volume), optional SuperTrend enrichment in main panel  
**Goal:** When hovering over **sub‑panels**, show **panel‑specific** tooltips using the existing Enhanced Tooltip system.

---

## Summary

- Added a small helper `setupPanelCrosshair(panelName, chart, resolveValues)` that subscribes to each sub‑panel's crosshair and routes values to `window.enhancedTooltip`.
- Wired **RSI, MACD, Stochastic, and Volume** panels.
- Optionally enriched the **main** tooltip with **SuperTrend** line/trend, computed at the hovered time (no separate SuperTrend panel needed).

**Artifacts**  
- `chart.subpanels.patched.js`: drop‑in patched version with the wiring.  
- `subpanel_wiring.patch`: unified diff against your current file (or `chart.patched.js` if you already applied the previous step).

**Downloads**  
- `/mnt/data/chart.subpanels.patched.js`  
- `/mnt/data/subpanel_wiring.patch`

---

## What changed (conceptual)

### 1) New helper

```js
function setupPanelCrosshair(panelName, chart, resolveValues) {{
  if (!chart || !window.enhancedTooltip) return;
  if (!state.subPanelHandlers) state.subPanelHandlers = {{}};
  if (state.subPanelHandlers[panelName]) return;

  chart.subscribeCrosshairMove((param) => {{
    if (!param.time || !param.point || param.point.x < 0 || param.point.y < 0) {{
      window.enhancedTooltip.hide();
      return;
    }}
    const payload = resolveValues(param);
    if (!payload) {{ window.enhancedTooltip.hide(); return; }}
    window.enhancedTooltip.update(panelName, payload);
    window.enhancedTooltip.show(param.point.x + 12, param.point.y + 12);
  }});

  state.subPanelHandlers[panelName] = true;
}}
```

### 2) Panel‑specific resolvers

- **RSI** → reads `state.subSeries.rsi.line` and sends `{ rsi }`.  
- **MACD** → reads `state.subSeries.macd.line`, `.signal`, `.histogram` and sends `{ macdLine, signal, histogram }`.  
- **Stochastic** → reads `state.subSeries.stochastic.k` and `.d` and sends `{ kValue, dValue }`.  
- **Volume** → reads `state.subSeries.volume.histogram` and sends `{ volume, volumeMA }` (MA optional).  

### 3) Optional: SuperTrend in main tooltip

Inside the main crosshair handler, if `state.series.supertrend` is present, we compute the SuperTrend line at the hovered time and infer `trend = close >= stLine ? 1 : -1`. These fields can be used by the enhanced tooltip to render an extra section (if you choose to augment `buildMainTooltip`).

---

## Unified Diff (excerpt)

```diff
--- chart.patched.js
+++ chart.subpanels.patched.js
@@
+// --- Sub-panel tooltip wiring helper ---
+function setupPanelCrosshair(panelName, chart, resolveValues) {{
+  if (!chart || !window.enhancedTooltip) return;
+  if (!state.subPanelHandlers) state.subPanelHandlers = {{}};
+  if (state.subPanelHandlers[panelName]) return;
+  chart.subscribeCrosshairMove((param) => {{
+    if (!param.time || !param.point || param.point.x < 0 || param.point.y < 0) {{
+      window.enhancedTooltip.hide();
+      return;
+    }}
+    try {{
+      const payload = resolveValues(param);
+      if (!payload) {{ window.enhancedTooltip.hide(); return; }}
+      window.enhancedTooltip.update(panelName, payload);
+      window.enhancedTooltip.show(param.point.x + 12, param.point.y + 12);
+    }} catch (e) {{
+      console.warn('[ChartJS] sub-panel tooltip error for', panelName, e);
+      window.enhancedTooltip.hide();
+    }}
+  }});
+  state.subPanelHandlers[panelName] = true;
+}}
@@
 setRSI: function(data) {{
   const chart = getOrCreateSubPanel('rsi');
   ...
+  // Wire enhanced tooltip for RSI panel
+  setupPanelCrosshair('rsi', chart, (param) => {{
+    const p = param.seriesData.get(state.subSeries.rsi && state.subSeries.rsi.line);
+    if (!p || typeof p.value !== 'number') return null;
+    return {{ rsi: p.value }};
+  }});
   console.log('[ChartJS] RSI set:', data.length);
 }},
@@
 setMACD: function(line, signal, histogram) {{
   const chart = getOrCreateSubPanel('macd');
   ...
+  setupPanelCrosshair('macd', chart, (param) => {{
+    const macd = state.subSeries.macd; if (!macd) return null;
+    const m = param.seriesData.get(macd.line);
+    const s = param.seriesData.get(macd.signal);
+    const h = param.seriesData.get(macd.histogram);
+    if (!m || !s || !h) return null;
+    return {{ macdLine: m.value, signal: s.value, histogram: h.value }};
+  }});
   console.log('[ChartJS] MACD set:', line.length);
 }},
@@
 setStochastic: function(kData, dData) {{
   const chart = getOrCreateSubPanel('stochastic');
   ...
+  setupPanelCrosshair('stochastic', chart, (param) => {{
+    const st = state.subSeries.stochastic; if (!st) return null;
+    const k = param.seriesData.get(st.k);
+    const d = param.seriesData.get(st.d);
+    if (!k || !d) return null;
+    return {{ kValue: k.value, dValue: d.value }};
+  }});
   console.log('[ChartJS] Stochastic set:', kData.length);
 }},
@@
 setVolume: function(data) {{
   const chart = getOrCreateSubPanel('volume');
   ...
+  setupPanelCrosshair('volume', chart, (param) => {{
+    const v = state.subSeries.volume && param.seriesData.get(state.subSeries.volume.histogram);
+    if (!v) return null;
+    return {{ volume: v.value, volumeMA: undefined }};
+  }});
   console.log('[ChartJS] Volume set:', data.length);
 }},
@@
 function setupCrosshairHandler() {{
   ...
   const {{ open, high, low, close }} = candleData;
+  /* SUPER_TREND_MAIN_UI */
+  let stLine, stTrend;
+  try {{
+    if (state.series && state.series.supertrend) {{
+      const stPoint = param.seriesData.get(state.series.supertrend);
+      if (stPoint && typeof stPoint.value === 'number') {{
+        stLine = stPoint.value;
+        stTrend = (typeof close === 'number' && typeof stLine === 'number' && close >= stLine) ? 1 : -1;
+      }}
+    }}
+  }} catch {{}} 
   ...
 }}
```

> Full diff is in `subpanel_wiring.patch`.

---

## How to Apply

**Option A** — replace your file with the patched version  
Copy `chart.subpanels.patched.js` over your current `chart.js`.

**Option B** — apply the patch  
```bash
# from your project root (where chart.js lives)
patch -p0 < subpanel_wiring.patch
```

---

## Testing Checklist

- Hover **RSI** panel → tooltip shows RSI value and status bands.  
- Hover **MACD** panel → tooltip shows MACD/Signal/Histogram + momentum.  
- Hover **Stochastic** panel → tooltip shows %K/%D + cross signal.  
- Hover **Volume** panel → tooltip shows volume; MA line (if you later add it) will auto‑appear.  
- Move mouse outside sub‑panels or off canvas → tooltip hides.  
- Main chart hover still shows the **main** tooltip content.  
- (Optional) If you extend `buildMainTooltip` to render SuperTrend data when present, verify the extra row appears and reads correctly.

---

## Optional: show SuperTrend inside the main tooltip

To display SuperTrend alongside O/H/L/C in the **main** tooltip, you have two tiny edits:

1. **`chart.js`** — already computes `stLine` and `stTrend` in the main handler. Update the `enhancedTooltip.update('main', ...)` call to include them:
   ```js
   window.enhancedTooltip.update('main', {{ time: param.time, open, high, low, close, volume, stLine, trend: stTrend }});
   ```

2. **`tooltip-enhanced.js`** — append to `buildMainTooltip(data)` (after the volume row):
   ```js
   if (typeof data.stLine === 'number') {{
     const trendText = data.trend === 1 ? 'Uptrend' : 'Downtrend';
     content += `
       <div class="tooltip-row">
         <span class="label">SuperTrend:</span>
         <span class="value">${{data.stLine.toFixed(2)}} (${{trendText}})</span>
       </div>`;
   }}
   ```

This keeps a single tooltip while enriching it where it makes sense.

---

**Done.** Apply the patch or drop in the patched file, and you’ll have panel‑aware tooltips wired up.
