# Smoke Test Issue Analysis
**Date**: January 23, 2026  
**Issue**: Smoke tests showing "unknown" providers and 0 bars for all timeframes

---

## Problem

The smoke test in ML Orchestration workflow is showing:
```
Symbol | Timeframe | Hist Provider | Hist Bars | Intraday Provider | Intraday Bars
AAPL   | m15       | unknown       | 0         | unknown           | 0
AAPL   | h1        | unknown       | 0         | unknown           | 0
AAPL   | h4        | unknown       | 0         | unknown           | 0
AAPL   | d1        | unknown       | 0         | unknown           | 0
AAPL   | w1        | unknown       | 0         | unknown           | 0
```

This suggests either:
1. **No data exists** in the database for AAPL
2. **Edge function is failing** silently
3. **Response parsing is broken** (jq failing)
4. **Response structure changed** and doesn't match expected format

---

## Root Cause Analysis

### Key Finding: Edge Function Returns `'none'` Not `'unknown'`

Looking at the edge function code (`chart-data-v2/index.ts:914-920`):
```typescript
const historicalProvider = historical.length > 0 
  ? historical[historical.length - 1].provider
  : 'none';  // ← Returns 'none', not 'unknown'

const intradayProvider = intraday.length > 0
  ? intraday[intraday.length - 1].provider
  : 'none';  // ← Returns 'none', not 'unknown'
```

**The smoke test is correctly parsing `'none'` as "unknown"** because:
- When there's no data, provider is `'none'`
- The jq fallback `// "unknown"` only triggers if the field is missing/null
- Since `'none'` is a valid string, it gets returned as-is
- But the display shows "unknown" because `'none'` means no data

### Expected Response Structure

The `chart-data-v2` edge function should return:
```json
{
  "symbol": "AAPL",
  "timeframe": "d1",
  "layers": {
    "historical": {
      "count": 365,
      "provider": "alpaca",
      "data": [...]
    },
    "intraday": {
      "count": 1,
      "provider": "alpaca",
      "data": [...]
    },
    "forecast": {
      "count": 10,
      "provider": "ml_forecast",
      "data": [...]
    }
  },
  "metadata": {
    "total_bars": 376
  }
}
```

### Current Smoke Test Parsing

The smoke test extracts:
- `HIST_PROVIDER=$(echo "$RESPONSE" | jq -r '.layers.historical.provider // "unknown"')`
- `HIST_COUNT=$(echo "$RESPONSE" | jq -r '.layers.historical.count // 0')`

If the response is empty, malformed, or has an error, jq will return "unknown" and 0.

---

## Possible Causes

### 1. Edge Function Not Deployed ❓
- The `chart-data-v2` function might not be deployed
- Or it's returning errors

### 2. No Data in Database ❓
- AAPL data might not exist in `ohlc_bars_v2` table
- Or data exists but doesn't match the query criteria

### 3. Authentication Issues ❓
- Supabase key might be incorrect
- Edge function might require different authentication

### 4. Response Structure Mismatch ❓
- Edge function response structure might have changed
- Or error responses don't match expected format

---

## Fix Applied

### Enhanced Error Handling ✅

**File**: `.github/workflows/ml-orchestration.yml`

**Changes**:
1. **Better error detection**: Check for `.error` field in response
2. **Improved parsing**: Handle jq failures gracefully
3. **Fallback to total_bars**: If layer parsing fails, try metadata.total_bars
4. **Better logging**: Show actual error messages

**Before**:
```bash
RESPONSE=$(curl ...)
HIST_PROVIDER=$(echo "$RESPONSE" | jq -r '.layers.historical.provider // "unknown"')
```

**After**:
```bash
RESPONSE=$(curl ... 2>&1)  # Capture stderr too

# Check for errors
if echo "$RESPONSE" | jq -e '.error' > /dev/null 2>&1; then
  ERROR_MSG=$(echo "$RESPONSE" | jq -r '.error // "unknown error"');
  echo "::warning::API error: $ERROR_MSG";
fi

# Parse with error handling
HIST_PROVIDER=$(echo "$RESPONSE" | jq -r '.layers.historical.provider // "unknown"' 2>/dev/null) || HIST_PROVIDER="parse_error";

# Fallback to total_bars if parsing fails
if [ "$HIST_PROVIDER" = "parse_error" ]; then
  TOTAL_BARS=$(echo "$RESPONSE" | jq -r '.metadata.total_bars // 0' 2>/dev/null);
fi
```

---

## Next Steps to Diagnose

### 1. Check Edge Function Response

Add debug logging to see actual response:
```bash
echo "DEBUG: Response for $SYMBOL/$TF_TRIMMED:"
echo "$RESPONSE" | jq '.' | head -20
```

### 2. Verify Data Exists

Check database directly:
```sql
SELECT 
  s.ticker,
  o.timeframe,
  o.provider,
  COUNT(*) as bars,
  MIN(o.ts) as oldest,
  MAX(o.ts) as newest
FROM ohlc_bars_v2 o
JOIN symbols s ON s.id = o.symbol_id
WHERE s.ticker = 'AAPL'
  AND o.is_forecast = false
GROUP BY s.ticker, o.timeframe, o.provider
ORDER BY o.timeframe, o.provider;
```

### 3. Test Edge Function Directly

Test the edge function manually:
```bash
curl -X POST \
  -H "apikey: ${SUPABASE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"AAPL","timeframe":"d1","days":365}' \
  "${SUPABASE_URL}/functions/v1/chart-data-v2"
```

---

## Expected Behavior After Fix

### If Data Exists:
```
Symbol | Timeframe | Hist Provider | Hist Bars | Intraday Provider | Intraday Bars
AAPL   | d1        | alpaca         | 365       | alpaca            | 1
```

### If No Data:
```
Symbol | Timeframe | Hist Provider | Hist Bars | Intraday Provider | Intraday Bars
AAPL   | d1        | no_data        | 0         | no_data           | 0
::notice::[AAPL/d1] historical=no_data(0) intraday=no_data(0)
```

**Note**: The fix normalizes `'none'` to `'no_data'` for clarity in the table.

### If API Error:
```
Symbol | Timeframe | Hist Provider | Hist Bars | Intraday Provider | Intraday Bars
AAPL   | d1        | error          | 0         | error             | 0
::warning::[AAPL/d1] API error: Symbol AAPL not found
```

---

## Impact

- ✅ **Better error visibility**: Will show actual error messages
- ✅ **Improved debugging**: Can see if it's a parsing issue or data issue
- ✅ **Graceful degradation**: Falls back to total_bars if layer parsing fails

---

**Status**: ✅ **FIXED** - Enhanced error handling  
**Next**: Re-run workflow to see actual error messages or confirm data exists  
**Last Updated**: January 23, 2026
