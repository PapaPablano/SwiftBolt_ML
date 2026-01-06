# WebChart Phase 1 - Testing Guide
**Build Succeeded - Ready for Testing**

---

## ✅ Pre-Test Checklist

- [x] Build succeeded without errors
- [x] All files added to Xcode project
- [x] WebChartControlsView integrated into ChartView
- [x] Timestamp bug fixed (seconds instead of milliseconds)
- [x] Volume profile calculator implemented

---

## 🧪 Test Scenarios

### Test 1: Heikin-Ashi Toggle

**Steps:**
1. Launch the app
2. Select a symbol (e.g., AAPL)
3. Ensure "Use WebChart" is enabled in settings
4. Locate the "Chart Options" panel above the chart
5. Toggle "Heikin-Ashi Candles" ON

**Expected Results:**
- ✅ Candles transform to Heikin-Ashi format
- ✅ Colors change to lime green (bullish) and bright red (bearish)
- ✅ Candles appear smoother/less noisy than standard
- ✅ Chart remains responsive (60 FPS)
- ✅ Console shows: `[ChartJS] Heikin-Ashi toggled: true`

**Toggle OFF:**
- ✅ Candles revert to standard OHLC
- ✅ Colors return to original green/red
- ✅ Console shows: `[ChartJS] Heikin-Ashi toggled: false`

**Verification:**
```
Check browser console (Web Inspector):
- Look for "[HA] Heikin-Ashi enabled" message
- Verify no JavaScript errors
- Check candle data transformation
```

---

### Test 2: Volume Profile Display

**Steps:**
1. With a symbol loaded (e.g., NVDA)
2. Toggle "Volume Profile" ON
3. Observe the chart

**Expected Results:**
- ✅ Console shows: `[ChartViewModel] Volume profile calculated: X levels, POC at $Y`
- ✅ Info box appears showing "X price levels"
- ✅ POC price displayed (e.g., "POC: $150.25")
- ✅ Histogram appears on right side of chart (if visible)
- ✅ POC level highlighted in red/orange

**Verification:**
```swift
// Check in Xcode debugger:
po viewModel.volumeProfile.count
// Should show number of price levels (typically 50-200)

po viewModel.volumeProfile.first(where: { $0["pointOfControl"] as? Bool == true })
// Should show POC data
```

**Toggle OFF:**
- ✅ Info box disappears
- ✅ Histogram removed from chart

---

### Test 3: Chart Rendering After Timestamp Fix

**Steps:**
1. Load any symbol with historical data
2. Check x-axis labels
3. Hover over candles to see tooltip

**Expected Results:**
- ✅ X-axis shows proper dates (e.g., "Jan 5", "Jan 6")
- ✅ NO large numbers like "60000" on x-axis
- ✅ Tooltip shows correct timestamp
- ✅ Candles align chronologically
- ✅ No gaps or overlaps in data

**Console Verification:**
```
[ChartBridge] Candles: 100 bars
[ChartBridge] First: 2026-01-01 O:150.0 H:151.0 L:149.0 C:150.5
[ChartBridge] Last: 2026-01-06 O:155.0 H:156.0 L:154.0 C:155.5
```

---

### Test 4: Combined Features

**Steps:**
1. Enable Heikin-Ashi
2. Enable Volume Profile
3. Switch between different symbols
4. Change timeframes (15m, 1h, 1d)

**Expected Results:**
- ✅ Both features work simultaneously
- ✅ HA state persists across symbol changes
- ✅ Volume profile recalculates for new symbol
- ✅ No performance degradation
- ✅ Chart remains responsive

---

### Test 5: Performance Testing

**Steps:**
1. Load a symbol with 1000+ bars (e.g., AAPL on 1D timeframe)
2. Enable Heikin-Ashi
3. Enable Volume Profile
4. Pan and zoom the chart
5. Toggle HA on/off rapidly

**Expected Results:**
- ✅ Chart maintains 60 FPS during pan/zoom
- ✅ HA calculation completes in <10ms
- ✅ Volume profile calculation completes in <50ms
- ✅ Memory usage stays under 50MB
- ✅ No UI freezing or lag

**Performance Monitoring:**
```
Check Xcode Instruments:
- CPU usage should stay under 30%
- Memory should not leak
- Frame rate should stay at 60 FPS
```

---

### Test 6: Edge Cases

#### 6.1 Empty Data
**Steps:**
1. Toggle HA with no symbol loaded

**Expected:**
- ✅ No crash
- ✅ Console: `[ChartJS] No candle data to transform`

#### 6.2 Single Bar
**Steps:**
1. Load symbol with only 1 bar
2. Toggle HA

**Expected:**
- ✅ HA calculates correctly
- ✅ No division by zero errors

#### 6.3 Zero Volume
**Steps:**
1. Load data with zero volume bars
2. Enable Volume Profile

**Expected:**
- ✅ Handles gracefully
- ✅ Skips zero-volume bars
- ✅ No NaN or Infinity values

#### 6.4 Rapid Symbol Switching
**Steps:**
1. Enable HA and Volume Profile
2. Rapidly switch between symbols (AAPL → NVDA → TSLA → MSFT)

**Expected:**
- ✅ Features persist across switches
- ✅ Volume profile recalculates each time
- ✅ No memory leaks
- ✅ No stale data displayed

---

## 🐛 Troubleshooting

### Issue: HA toggle doesn't work
**Debug Steps:**
1. Open Web Inspector (Right-click chart → Inspect Element)
2. Check Console tab for errors
3. Verify `window.chartApi.toggleHeikinAshi` exists
4. Check `state.originalBars.length > 0`

**Fix:**
```javascript
// In browser console:
console.log(window.chartApi);
console.log(state.originalBars.length);
```

### Issue: Volume Profile not showing
**Debug Steps:**
1. Check Xcode console for calculation message
2. Verify `viewModel.volumeProfile` is not empty
3. Check that bars have volume data

**Fix:**
```swift
// In Xcode debugger:
po viewModel.chartDataV2?.allBars.first?.volume
// Should be > 0
```

### Issue: Chart shows wrong dates
**Debug Steps:**
1. Check that timestamp fix was applied
2. Verify `timeIntervalSince1970` (NOT `* 1000`)
3. Check browser console for candle data

**Fix:**
```
Verify in ChartBridge.swift line 289:
time: Int(bar.ts.timeIntervalSince1970)  // NO * 1000
```

---

## 📊 Success Metrics

After testing, verify these metrics:

### Functionality (100% Pass Required)
- [ ] Heikin-Ashi toggle works correctly
- [ ] Volume Profile displays and calculates
- [ ] Chart x-axis shows proper dates
- [ ] Tooltips display correct information
- [ ] Features persist across symbol changes

### Performance (Target Metrics)
- [ ] Chart renders at 60 FPS
- [ ] HA calculation: <10ms for 1000 bars
- [ ] Volume profile: <50ms for 1000 bars
- [ ] Memory usage: <50MB
- [ ] No UI freezing or lag

### User Experience
- [ ] Controls are intuitive and easy to find
- [ ] Toggle switches respond immediately
- [ ] Visual feedback is clear (colors, labels)
- [ ] No confusing error messages
- [ ] Professional appearance

---

## 📝 Test Results Template

```
Date: ___________
Tester: ___________
Build: ___________

Test 1 - Heikin-Ashi Toggle:        [ PASS / FAIL ]
Test 2 - Volume Profile:             [ PASS / FAIL ]
Test 3 - Chart Rendering:            [ PASS / FAIL ]
Test 4 - Combined Features:          [ PASS / FAIL ]
Test 5 - Performance:                [ PASS / FAIL ]
Test 6 - Edge Cases:                 [ PASS / FAIL ]

Notes:
_________________________________________________
_________________________________________________
_________________________________________________

Issues Found:
_________________________________________________
_________________________________________________
_________________________________________________

Overall Status: [ READY FOR PRODUCTION / NEEDS FIXES ]
```

---

## 🚀 Next Steps After Testing

### If All Tests Pass:
1. ✅ Mark Phase 1 as complete
2. ✅ Deploy to production
3. ✅ Monitor user feedback
4. ✅ Begin Phase 2 planning (Greeks, Win-Rate, Multi-Timeframe)

### If Issues Found:
1. Document specific failures
2. Create bug tickets
3. Prioritize fixes
4. Re-test after fixes
5. Repeat until all tests pass

---

## 💡 Quick Test Commands

### Enable Web Inspector (macOS):
```
In app:
1. Right-click on chart
2. Select "Inspect Element"
3. Go to Console tab
4. Watch for log messages
```

### Xcode Console Filters:
```
Filter by:
[ChartBridge]     - Bridge operations
[ChartJS]         - JavaScript events
[ChartViewModel]  - ViewModel calculations
[WebChartView]    - View updates
```

### Quick Verification:
```swift
// In Xcode debugger (lldb):
po viewModel.useHeikinAshi
po viewModel.showVolumeProfile
po viewModel.volumeProfile.count
po viewModel.chartDataV2?.allBars.count
```

---

## ✨ Expected User Experience

**Before Phase 1:**
- Standard candlestick chart
- Basic indicators
- Static display

**After Phase 1:**
- ✅ Heikin-Ashi for clearer trends
- ✅ Volume Profile showing support/resistance
- ✅ Enhanced tooltips with detailed info
- ✅ Professional trading interface
- ✅ Improved decision-making tools

---

## 🎯 Testing Priority

**Critical (Must Pass):**
1. Heikin-Ashi toggle functionality
2. Chart renders with correct dates
3. No crashes or errors

**High (Should Pass):**
1. Volume Profile calculation
2. Performance metrics
3. Combined features work

**Medium (Nice to Have):**
1. Edge case handling
2. Rapid switching
3. Memory optimization

---

**Ready to test!** Start with Test 1 (Heikin-Ashi) and work through the scenarios.
