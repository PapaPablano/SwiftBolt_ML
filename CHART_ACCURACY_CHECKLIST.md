# Chart Data Accuracy Checklist

## Issue Report
**Symbol:** NVDA  
**Date:** November 1st, 2025  
**Reported Issue:** 15% swing that doesn't exist  
**Status:** ⚠️ Data is correct in database, likely a rendering issue

## Verification Results

### ✅ Database Data (Verified)
- **Source:** ohlc_bars_v2 table via chart-data-v2 API
- **Oct-Nov 2025:** 43 bars checked
- **Largest gap:** 2.6% (Oct 13 and Oct 15)
- **Nov 1st data:** Normal price movement, no anomalies
- **Provider:** All bars marked as 'polygon' with unadjusted prices

### ✅ Polygon API (Verified)
- **Direct API check:** Oct 30 - Nov 5, 2025
- **adjusted=false parameter:** Confirmed
- **Price continuity:** Normal (202-206 range, no splits)
- **No stock splits:** Checked via Polygon splits API

## Potential Issues to Debug

### 1. Swift Date/Timezone Parsing ⚠️
**Risk:** HIGH  
**Issue:** OHLCBar decoder might misalign timestamps

**Check:**
```swift
// In OHLCBar.swift - verify ISO8601 parsing
let formatter = ISO8601DateFormatter()
formatter.timeZone = TimeZone(secondsFromGMT: 0)!  // Must be UTC
```

**Test:**
- Print raw JSON timestamps from API
- Print parsed Date objects in Swift
- Compare: Does "2025-11-01T05:00:00Z" parse to correct day?

### 2. Chart Rendering Order 🔍
**Risk:** MEDIUM  
**Issue:** WebChartView might sort bars incorrectly

**Check:**
```swift
// In WebChartView.swift updateChartV2()
// Verify bars are sorted by timestamp before rendering
let sortedBars = data.layers.historical.data.sorted { $0.ts < $1.ts }
```

**Test:**
- Add logging before `bridge.setCandles()`
- Verify bar order matches database order

### 3. Duplicate Bars 🔍
**Risk:** MEDIUM  
**Issue:** Multiple bars for same date from different providers

**SQL Check:**
```sql
SELECT DATE(ts) as date, COUNT(*) as count, 
       STRING_AGG(DISTINCT provider, ', ') as providers,
       STRING_AGG(DISTINCT CAST(close AS TEXT), ', ') as closes
FROM ohlc_bars_v2 
WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'NVDA')
  AND timeframe = 'd1'
  AND ts >= '2025-10-30' AND ts < '2025-11-05'
GROUP BY DATE(ts)
HAVING COUNT(*) > 1;
```

### 4. JavaScript Chart Library 🔍
**Risk:** LOW  
**Issue:** Lightweight Charts misrendering data

**Check:**
```javascript
// In chart.js - verify data format
console.log('Setting candles:', candles.slice(0, 5));
// Ensure: {time: number, open: number, high: number, low: number, close: number}
```

### 5. Mixed Adjusted/Unadjusted Data 🔍
**Risk:** LOW (already verified)  
**Issue:** Some bars using adjusted prices

**Verification:**
- ✅ All Polygon backfill scripts use `adjusted: "false"`
- ✅ No `adjusted: "true"` in source code
- ✅ Database shows consistent provider='polygon'

## Action Plan

### Immediate Steps

1. **Add Debug Logging to Swift App**
   ```swift
   // In ChartViewModel.loadChart()
   if let dataV2 = chartDataV2 {
       print("📊 ChartDataV2 loaded:")
       print("  Historical bars: \(dataV2.layers.historical.count)")
       for (i, bar) in dataV2.layers.historical.data.prefix(5).enumerated() {
           print("  [\(i)] \(bar.ts) | O:\(bar.open) H:\(bar.high) L:\(bar.low) C:\(bar.close)")
       }
   }
   ```

2. **Add Debug Logging to WebChartView**
   ```swift
   // In updateChartV2()
   print("🎨 Rendering historical layer:")
   let bars = data.layers.historical.data
   for (i, bar) in bars.enumerated() where i < 5 || i >= bars.count - 5 {
       print("  [\(i)] \(bar.ts[:10]) | \(bar.close)")
   }
   ```

3. **Verify Chart.js Data**
   ```javascript
   // In chart.js setCandles()
   console.log('📊 setCandles called with', data.length, 'bars');
   console.log('First 3:', data.slice(0, 3));
   console.log('Last 3:', data.slice(-3));
   ```

4. **Run the App and Check Console**
   - Open Console.app
   - Filter for "SwiftBoltML"
   - Load NVDA chart
   - Look for the Nov 1st bar in logs
   - Compare timestamps and prices

### If Issue Persists

5. **Check for Intraday/Historical Overlap**
   ```sql
   -- Find any Tradier bars that might be mixing with Polygon
   SELECT ts, provider, open, high, low, close 
   FROM ohlc_bars_v2
   WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'NVDA')
     AND timeframe = 'd1'
     AND DATE(ts) = '2025-11-01'
   ORDER BY provider, ts;
   ```

6. **Verify Edge Function Logic**
   - Check `chart-data-v2/index.ts`
   - Ensure proper date filtering: `DATE(ts) < CURRENT_DATE` for historical
   - Ensure no UNION without deduplication

7. **Test with Different Symbol**
   - Load AAPL chart for same date range
   - If AAPL shows similar issue → rendering problem
   - If AAPL is fine → NVDA-specific data issue

## Expected Behavior

### Correct Data Flow
```
Polygon API (adjusted=false)
    ↓
deep_backfill_ohlc_v2.py
    ↓
ohlc_bars_v2 (provider='polygon', data_status='verified')
    ↓
chart-data-v2 Edge Function
    ↓
ChartDataV2Response (Swift)
    ↓
WebChartView → ChartBridge → chart.js
    ↓
Lightweight Charts (visual rendering)
```

### NVDA Nov 1st Expected Values
Based on database verification:
- **Date:** 2025-11-01
- **Open:** ~206.45
- **High:** ~207.97
- **Low:** ~202.07
- **Close:** ~202.49
- **Change from Oct 31:** ~-0.2% (normal)

## Resolution Checklist

- [ ] Add debug logging to Swift app
- [ ] Add debug logging to WebChartView
- [ ] Add debug logging to chart.js
- [ ] Run app and capture console output
- [ ] Verify bar order and timestamps
- [ ] Check for duplicate bars in database
- [ ] Test with different symbol (AAPL)
- [ ] Review Edge Function query logic
- [ ] Verify timezone handling in OHLCBar decoder

## Notes

- Database data is **verified correct** ✅
- No stock splits in Oct-Nov 2025 ✅
- All prices are unadjusted ✅
- Issue is likely in **Swift rendering or date parsing**
- Focus debugging on client-side (Swift app)
