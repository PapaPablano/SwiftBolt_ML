# Polynomial S&R Debugging Guide

**Issue**: Indicator checkbox is checked but curves not showing on chart
**Status**: Diagnosing wiring issue

---

## Step-by-Step Debugging

### Step 1: Check Browser Console (F12)

Open DevTools → Console tab and look for these messages:

**Expected logs** (should see every 30 seconds):
```
[Chart] Updated S/R: Support 244.66, Resistance 277.27
```

**If you DON'T see this log**, the data isn't being passed to the chart.

**Common errors to look for**:
```
❌ "useIndicators is not defined"
   → Hook import issue in ChartWithIndicators.tsx

❌ "Cannot read property 'polynomial_support' of undefined"
   → srData is null/undefined

❌ "Cannot read property 'current' of undefined"
   → supportLineRef or resistanceLineRef not initialized

❌ "GET /api/support-resistance 404"
   → Backend endpoint not found or wrong URL
```

---

### Step 2: Check Network Tab (F12 → Network)

When you load the chart or switch symbols:

1. Open DevTools → Network tab
2. Switch to a different symbol (e.g., NVDA)
3. Look for request: `GET /api/support-resistance?symbol=NVDA&timeframe=...`

**What to check**:
- [ ] Request appears in Network tab
- [ ] Status is 200 (not 404 or 500)
- [ ] Response contains `polynomial_support` and `polynomial_resistance`
- [ ] Response has non-null `level` values

**If request doesn't appear**:
- useIndicators hook isn't running
- Check if ChartWithIndicators is rendering
- Check if useIndicators is imported correctly

**If response is 404**:
- Backend endpoint `/api/support-resistance` doesn't exist
- Check backend is running: `python -m uvicorn main:app --reload`

**If response is empty**:
- Insufficient pivot data for polynomial fit
- Check API response structure

---

### Step 3: Verify Component Chain

Check that components are properly wired:

```bash
# In frontend directory, check imports
grep -n "ChartWithIndicators" src/App.tsx
# Should show: import { ChartWithIndicators } from './components/ChartWithIndicators';

grep -n "useIndicators" src/components/ChartWithIndicators.tsx
# Should show: import { useIndicators } from '../hooks/useIndicators';

grep -n "TradingViewChart" src/components/ChartWithIndicators.tsx
# Should show: <TradingViewChart ... srData={data} />

grep -n "srData" src/components/TradingViewChart.tsx
# Should show both the prop and usage
```

---

### Step 4: Verify Hook is Fetching

Add this to browser console to test:

```javascript
// Check if useIndicators can be called
const { useIndicators } = await import('/src/hooks/useIndicators.js');
console.log('useIndicators loaded:', typeof useIndicators);

// Manual fetch test
fetch('http://localhost:8000/api/support-resistance?symbol=AAPL&timeframe=1h')
  .then(r => r.json())
  .then(data => {
    console.log('API Response:', data);
    console.log('Support:', data.polynomial_support?.level);
    console.log('Resistance:', data.polynomial_resistance?.level);
  })
  .catch(err => console.error('API Error:', err));
```

---

### Step 5: Check if srData is Being Passed

Add temporary console.log to `TradingViewChart.tsx`:

**In the component, add after line 42**:
```typescript
  console.log('[TradingViewChart] Received srData:', srData);
```

**In the useEffect after line 234**:
```typescript
  console.log('[S/R Effect] srData changed:', srData);
```

Then reload and check console. You should see:
```
[TradingViewChart] Received srData: {polynomial_support: {...}, ...}
[S/R Effect] srData changed: {polynomial_support: {...}, ...}
```

If you see `srData: null` or `srData: undefined`, the data isn't being passed.

---

### Step 6: Verify Line Series Are Created

Add console.log in TradingViewChart.tsx chart initialization (around line 134):

```typescript
console.log('[Chart] Support line series created:', supportLine);
console.log('[Chart] Resistance line series created:', resistanceLine);
```

You should see confirmation that both line series exist.

---

### Step 7: Check API Response Structure

Open Network tab, find `/api/support-resistance` request, click it, go to Response tab.

**Should look like this**:
```json
{
  "symbol": "AAPL",
  "current_price": 256.45,
  "polynomial_support": {
    "level": 244.66,
    "slope": 0.0234,
    "trend": "rising",
    "forecast": [245.10, 245.52, ...]
  },
  "polynomial_resistance": {
    "level": 277.27,
    "slope": -0.0156,
    "trend": "falling",
    "forecast": [277.19, 277.11, ...]
  },
  "nearest_support": 244.66,
  "nearest_resistance": 277.27,
  "support_distance_pct": 5.3,
  "resistance_distance_pct": 7.3,
  "bias": "bullish"
}
```

**If values are null**:
- Backend polynomial fitting failed
- Check ML logs for errors
- Might need more pivot points

---

## Possible Issues & Solutions

### Issue 1: API Endpoint Not Found

**Symptom**: Network tab shows `GET /api/support-resistance 404`

**Solution**:
```bash
# Check backend is running
curl http://localhost:8000/api/support-resistance?symbol=AAPL&timeframe=1h

# If 404, check backend router
grep -n "support-resistance" /Users/ericpeterson/SwiftBolt_ML/ml/api/routers/support_resistance.py
```

---

### Issue 2: Hook Not Being Called

**Symptom**: Console shows no logs, Network tab shows no API calls

**Solution**:
1. Check ChartWithIndicators.tsx is rendering
2. Verify useIndicators is imported
3. Add console.log at top of useIndicators function:
```typescript
console.log('[useIndicators] Fetching:', symbol, timeframe);
```

---

### Issue 3: Data Not Reaching Chart

**Symptom**: API returns data (200 OK), but chart shows no curves

**Solution**:
1. Check srData prop is passed to TradingViewChart
2. Verify supportLineRef and resistanceLineRef are created
3. Check useEffect watches srData changes:
```typescript
useEffect(() => {
  console.log('[S/R Effect] Updating with srData:', srData);
  // ... update logic
}, [srData]); // ← dependency array is critical
```

---

### Issue 4: Curves Not Rendering Despite Data

**Symptom**: Console shows data exists, but no curves on chart

**Solution**:
1. Check line series are added to chart
2. Verify `setData()` is being called with valid data
3. Check timestamp format in line data:
```typescript
const supportData = [
  {
    time: Math.floor(Date.now() / 1000), // Should be Unix timestamp
    value: srData.polynomial_support.level, // Should be number
  },
];
```

---

### Issue 5: Lines Created But Not Visible

**Symptom**: No console errors, but curves don't show

**Solution**:
1. Check if lines are behind candlesticks (z-index)
2. Check line colors are visible (blue #2962ff, red #f23645)
3. Check price scale - values might be outside visible range
4. Try temporary hack to verify lines work:
```typescript
// In useEffect, add dummy data
supportLineRef.current?.setData([
  { time: Math.floor(Date.now() / 1000) - 3600, value: 240 },
  { time: Math.floor(Date.now() / 1000), value: 280 },
]);
```

---

## Quick Test Script

Run this in browser console to test entire data flow:

```javascript
console.log('=== Polynomial S&R Wiring Test ===');

// Test 1: Check API
console.log('Test 1: API Connection');
fetch('http://localhost:8000/api/support-resistance?symbol=AAPL&timeframe=1h')
  .then(r => {
    console.log('  Status:', r.status);
    return r.json();
  })
  .then(data => {
    console.log('  ✓ API Response received');
    console.log('  Support:', data.polynomial_support?.level);
    console.log('  Resistance:', data.polynomial_resistance?.level);
  })
  .catch(err => console.error('  ✗ API Error:', err.message));

// Test 2: Check component rendering
console.log('\nTest 2: Component Rendering');
const app = document.querySelector('div[class*="grid"]');
console.log('  App mounted:', !!app);
console.log('  Chart visible:', !!document.querySelector('div[class*="lwc-canvas"]'));

// Test 3: Check for console errors
console.log('\nTest 3: Console Errors');
console.log('  Check console for errors above ↑');
```

---

## File Checklist

Verify all files exist and have content:

```bash
cd /Users/ericpeterson/SwiftBolt_ML/frontend

# Check files exist
test -f src/hooks/useIndicators.ts && echo "✓ useIndicators.ts" || echo "✗ MISSING"
test -f src/components/IndicatorPanel.tsx && echo "✓ IndicatorPanel.tsx" || echo "✗ MISSING"
test -f src/components/ChartWithIndicators.tsx && echo "✓ ChartWithIndicators.tsx" || echo "✗ MISSING"

# Check imports
grep -q "srData" src/components/TradingViewChart.tsx && echo "✓ TradingViewChart has srData" || echo "✗ MISSING srData prop"
grep -q "useIndicators" src/components/ChartWithIndicators.tsx && echo "✓ ChartWithIndicators imports useIndicators" || echo "✗ MISSING import"
grep -q "ChartWithIndicators" src/App.tsx && echo "✓ App imports ChartWithIndicators" || echo "✗ MISSING import"
```

---

## Next Steps

1. **Open F12 Console** and look for the log: `[Chart] Updated S/R: Support ...`
2. **Open F12 Network** and look for: `GET /api/support-resistance`
3. **Check Response** from that API call for polynomial data
4. **Add debugging logs** if neither appears
5. **Report findings** with:
   - What you see in Console tab
   - What API requests appear in Network tab
   - Whether API response has polynomial data

---

## Most Likely Issues

Based on the fact that the indicator checkbox exists but curves don't show:

1. **75% Chance**: API endpoint not running or returning null polynomial data
   - Check: `curl http://localhost:8000/api/support-resistance?symbol=AAPL&timeframe=1h`

2. **15% Chance**: useIndicators hook not being called
   - Check: Are you seeing API calls in Network tab every 30 seconds?

3. **10% Chance**: Data not being passed to chart component
   - Check: Is `srData` prop appearing in TradingViewChart console logs?

---

## Get Help

When reporting the issue, provide:
1. Screenshot of F12 Console (with any errors visible)
2. Screenshot of F12 Network tab showing `/api/support-resistance` request
3. Response JSON from that API call
4. What you see on the chart (nothing, or partial rendering?)

This will help identify exactly where the wiring broke.
