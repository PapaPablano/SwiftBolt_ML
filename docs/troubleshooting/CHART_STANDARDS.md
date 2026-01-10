# Chart Display Standards - SwiftBolt ML
**Last Updated:** January 10, 2026  
**Status:** ✅ Standardized and Enforced

---

## 📊 Your Established Chart Goals

### **Default Zoom & Visible Range**
- **Initial Load:** Always show **100 most recent bars** (regardless of timeframe)
- **Auto-reset:** When bar count changes, reset to 100 most recent bars
- **Maximum Cache:** Up to 1000 bars available from backend
- **Minimum Visible:** 10 bars (zoom limit)

### **Time Scale Configuration**
```javascript
timeScale: {
    borderColor: '#333',
    timeVisible: true,
    secondsVisible: false,
    rightOffset: 30,           // Edge spacing on right side
    barSpacing: 12,            // Space between bars (default visibility)
    minBarSpacing: 4,          // Minimum compression limit
    fixLeftEdge: false,        // Allow panning left
    fixRightEdge: false,       // Allow panning right
    uniformDistribution: true  // Equal spacing (ignore time gaps)
}
```

### **Price Scaling**
- **Y-axis:** Dynamically adjusts to **visible bars only**
- **Includes:** Indicator values (SMA, EMA, Bollinger Bands) in range calculation
- **Padding:** 5% above and below for visual clarity
- **Scale Margins:** `{ top: 0.1, bottom: 0.1 }` (10% top/bottom)

---

## 🎯 Standardization Summary

### **What Was Fixed (Jan 10, 2026)**

#### ❌ **Before:** Inconsistent Default Zoom
```javascript
// OLD: Varied by timeframe (60-100 bars)
if (avgBarInterval < 60 * 30) {
    targetVisibleBars = 100;  // 15-minute
} else if (avgBarInterval < 60 * 90) {
    targetVisibleBars = 80;   // 1-hour
} else {
    targetVisibleBars = 60;   // 4-hour, daily
}
```

#### ✅ **After:** Consistent 100 Bars
```javascript
// NEW: Always 100 bars on initial load
const targetVisibleBars = 100;
```

**Rationale:** Provides predictable, consistent user experience across all timeframes (15m, 1h, 4h, 1D).

---

## 📁 Files Implementing These Standards

### **JavaScript (Web Charts)**
1. **`client-macos/SwiftBoltML/Resources/WebChart/chart.js`**
   - Lines 128-137: Time scale configuration
   - Lines 525-527: Default zoom (100 bars)
   - Lines 530-534: Visible range calculation

### **Swift (Native Charts)**
2. **`client-macos/SwiftBoltML/Views/AdvancedChartView.swift`**
   - Default visible range: 100 bars
   - Pan/zoom controls
   - Reset to latest functionality

3. **`client-macos/SwiftBoltML/Views/WebChartView.swift`**
   - Coordinator tracks visible range
   - Syncs with JavaScript chart state

4. **`client-macos/SwiftBoltML/Services/ChartBridge.swift`**
   - `setVisibleRange(from:to:)` command
   - `visibleRangeChange` event handling

---

## 🔄 User Controls

### **Zoom Controls**
- **Zoom In:** Halves visible bars (e.g., 100 → 50 → 25)
- **Zoom Out:** Doubles visible bars (e.g., 100 → 200 → 400)
- **Limits:** Min 10 bars, Max all available bars
- **Disabled:** When at limits

### **Pan Controls**
- **Pan Left:** Move backward 25% of visible range
- **Pan Right:** Move forward 25% of visible range
- **Disabled:** When at data boundaries

### **Reset Control**
- **"Latest" Button:** Returns to most recent 100 bars
- **Auto-reset:** Triggered when new data loads

---

## 🎨 Visual Consistency

### **Candlestick Colors**
- **Bullish:** `#33d97a` (green)
- **Bearish:** `#ff4d4d` (red)

### **Heikin-Ashi Colors** (when enabled)
- **Bullish:** `#32CD32` (lime green)
- **Bearish:** `#FF6B6B` (bright red)

### **Grid & Background**
- **Background:** `#1e1e1e` (dark)
- **Grid Lines:** `#2a2a2a` (subtle)
- **Text:** `#888888` (gray)
- **Crosshair:** `#555555` (medium gray)

---

## 📏 Performance Targets

### **Rendering**
- **Frame Rate:** 60 FPS for pan/zoom
- **Initial Render:** <100ms with 100 bars
- **Memory Usage:** <50MB for historical + indicator data

### **Calculations**
- **Heikin-Ashi:** <10ms for 1000 bars
- **Volume Profile:** <50ms for 1000 bars
- **Indicator Updates:** <100ms latency on new bar

### **Data Updates**
- **Live Bar Animation:** 500ms smooth transition
- **Cache TTL:** 15 minutes for chart endpoint
- **Maximum Bars:** 1000 bars cached per symbol/timeframe

---

## 🧪 Verification Checklist

### **Default Zoom**
- [ ] 15-minute timeframe loads with 100 bars
- [ ] 1-hour timeframe loads with 100 bars
- [ ] 4-hour timeframe loads with 100 bars
- [ ] Daily timeframe loads with 100 bars
- [ ] All timeframes show consistent initial zoom

### **Time Scale**
- [ ] `rightOffset: 30` provides adequate edge spacing
- [ ] `barSpacing: 12` shows clear bar separation
- [ ] `minBarSpacing: 4` prevents over-compression
- [ ] `uniformDistribution: true` maintains equal spacing

### **Price Scaling**
- [ ] Y-axis adjusts to visible bars only
- [ ] Indicator overlays included in range
- [ ] 5% padding above/below visible range
- [ ] No clipping of price extremes

### **User Controls**
- [ ] Zoom in/out works correctly
- [ ] Pan left/right respects boundaries
- [ ] Reset returns to 100 most recent bars
- [ ] Controls disabled at appropriate limits

---

## 🔧 Troubleshooting

### **Issue: Chart shows wrong number of bars**
**Solution:**
1. Check console for "Visible range set" message
2. Should show: `showing 100 bars (detected: Xm/Xh/Xd timeframe)`
3. Verify `targetVisibleBars = 100` in chart.js line 527

### **Issue: Bars too compressed or too spread out**
**Solution:**
1. Verify `barSpacing: 12` in chart.js line 133
2. Check `minBarSpacing: 4` in chart.js line 134
3. Ensure `uniformDistribution: true` in chart.js line 137

### **Issue: Price scale doesn't fit visible data**
**Solution:**
1. Check `scaleMargins: { top: 0.1, bottom: 0.1 }` in chart.js line 126
2. Verify dynamic range calculation includes indicators
3. Ensure 5% padding is applied above/below

---

## 📚 Related Documentation

- **Implementation:** `WEBCHART_PHASE1_IMPLEMENTATION.md`
- **Quick Start:** `WEBCHART_QUICKSTART.md`
- **Testing:** `WEBCHART_TESTING_GUIDE.md`
- **Deployment:** `docs/DEPLOYMENT_VERIFICATION.md`
- **Architecture:** `docs/charting_architecture_guide.md`

---

## ✅ Summary

**All chart displays now follow these standards:**
1. ✅ **100 bars** on initial load (all timeframes)
2. ✅ **Consistent time scale** settings (rightOffset: 30, barSpacing: 12)
3. ✅ **Dynamic price scaling** with 5% padding
4. ✅ **Synchronized** pan/zoom across all panels
5. ✅ **Predictable** user controls and reset behavior

**Files Updated:** `chart.js` (lines 525-527)  
**Status:** Ready for testing and deployment
