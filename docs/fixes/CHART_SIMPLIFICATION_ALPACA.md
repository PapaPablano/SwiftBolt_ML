# Chart Data Fetching Simplification for Alpaca

## Summary

Simplified chart data fetching to treat all timeframes (15m, 1h, 4h, 1D, 1W) uniformly with Alpaca API. Removed unnecessary "intraday" vs "historical" distinctions since Alpaca uses the same API for all timeframes.

## Key Changes

### 1. Added Alpaca Format Mapping (`Timeframe.swift`)

Added `alpacaFormat` property to convert internal timeframe tokens to Alpaca's expected format:

```swift
var alpacaFormat: String {
    switch self {
    case .m15: return "15Min"   // Alpaca expects "15Min"
    case .h1:  return "1Hour"   // Alpaca expects "1Hour"
    case .h4:  return "4Hour"   // Alpaca expects "4Hour"
    case .d1:  return "1Day"    // Alpaca expects "1Day"
    case .w1:  return "1Week"   // Alpaca expects "1Week"
    }
}
```

**Usage**: When calling Alpaca API directly, use `timeframe.alpacaFormat` instead of `timeframe.apiToken`.

### 2. Simplified `fetchChartV2` (`APIClient.swift`)

**Before**: Special handling for "intraday" timeframes (m15, h1, h4) with conditional cache-busting and headers.

**After**: Uniform handling for all timeframes:
- Cache-buster enabled for ALL requests (not just intraday)
- Same cache policy for all timeframes (`.reloadIgnoringLocalCacheData`)
- Same headers for all timeframes (`no-cache`, unique `X-Request-ID`)

**Rationale**: Alpaca treats all timeframes the same way - you just change the `timeframe` parameter. No need for special "intraday" logic.

### 3. Simplified `buildBars` (`ChartViewModel.swift`)

**Before**: Complex switch statement with different logic for intraday vs daily/weekly timeframes.

**After**: Simple merge and sort for all timeframes:

```swift
// Merge all bars and sort by timestamp (works for all timeframes)
let allBars = (historical + intraday).sorted(by: { $0.ts < $1.ts })
```

**Rationale**: With Alpaca, both layers contain the same type of data, just from different time ranges. Simply merge and sort.

## What This Fixes

### Issue: 15m and 1h Charts Not Loading

**Root Cause**: The backend edge function `chart-data-v2` likely expects Alpaca format strings but was receiving internal tokens:
- ❌ Sending: `"m15"`, `"h1"` (internal format)
- ✅ Should send: `"15Min"`, `"1Hour"` (Alpaca format)

### Solution Path

The Swift client now has the `alpacaFormat` property ready. The backend edge function should:

1. Accept internal tokens (`m15`, `h1`, etc.) from the client
2. Convert to Alpaca format before calling Alpaca API
3. Return unified data in both `historical` and `intraday` layers

## Backend Requirements

The `chart-data-v2` edge function should:

```typescript
// Map internal tokens to Alpaca format
const timeframeMap = {
  'm15': '15Min',
  'h1': '1Hour',
  'h4': '4Hour',
  'd1': '1Day',
  'w1': '1Week'
};

const alpacaTimeframe = timeframeMap[timeframe] || timeframe;

// Call Alpaca with correct format
const response = await fetch(`https://data.alpaca.markets/v2/stocks/${symbol}/bars?timeframe=${alpacaTimeframe}&limit=1000`, {
  headers: {
    'APCA-API-KEY-ID': apiKey,
    'APCA-API-SECRET-KEY': secretKey
  }
});
```

## Testing

To verify the fix works:

1. **Check logs**: Look for `"📊 Fetching chart: symbol=AAPL, timeframe=m15"` in console
2. **Verify data**: Switch to 15m/1h timeframe and confirm bars appear
3. **Check timestamps**: Newest bar should be recent (within last 15min/1hr)
4. **Compare timeframes**: All timeframes should load with same speed/reliability

## Benefits

1. **Simpler code**: Removed ~30 lines of conditional logic
2. **Consistent behavior**: All timeframes treated uniformly
3. **Better caching**: Cache-busting works for all timeframes
4. **Easier debugging**: Single code path for all timeframes
5. **Future-proof**: Easy to add new timeframes (5m, 30m, etc.)

## Migration Notes

- ✅ Client-side changes complete
- ⚠️ Backend edge function may need update to use Alpaca format
- ✅ No breaking changes to API contract
- ✅ Backward compatible with existing data

## Related Files

- `@/Users/ericpeterson/SwiftBolt_ML/client-macos/SwiftBoltML/Models/Timeframe.swift`
- `@/Users/ericpeterson/SwiftBolt_ML/client-macos/SwiftBoltML/Services/APIClient.swift`
- `@/Users/ericpeterson/SwiftBolt_ML/client-macos/SwiftBoltML/ViewModels/ChartViewModel.swift`
