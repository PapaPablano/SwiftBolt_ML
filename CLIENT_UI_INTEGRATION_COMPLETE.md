# Client UI Integration - Data Layer Separation

## Overview

The macOS client has been fully integrated with the new data layer separation architecture. The TradingView-style chart system now renders three distinct data layers with proper visual differentiation.

## Changes Made

### 1. New Data Models

**`ChartDataV2Response.swift`** - New response model for layered chart data
- `ChartDataV2Response` - Top-level response with symbol, timeframe, layers, and metadata
- `ChartLayers` - Contains three separate layer objects (historical, intraday, forecast)
- `LayerData` - Individual layer with count, provider, and data array
- `ChartMetadata` - Metadata with total bars, date range

**Extensions:**
- `allBars` - Combined historical + intraday data
- `allBarsWithForecast` - All three layers combined
- `hasIntraday` / `hasForecast` - Convenience flags

### 2. Updated OHLCBar Model

Added optional forecast-specific properties:
- `upperBand: Double?` - Upper confidence band
- `lowerBand: Double?` - Lower confidence band  
- `confidenceScore: Double?` - ML prediction confidence (0-1)

These fields are only populated for forecast layer data.

### 3. API Client Updates

**`APIClient.swift`** - Added `fetchChartV2()` method
```swift
func fetchChartV2(
    symbol: String, 
    days: Int = 60, 
    includeForecast: Bool = true, 
    forecastDays: Int = 10
) async throws -> ChartDataV2Response
```

Calls the `chart-data-v2` Edge Function endpoint with POST request.

### 4. ChartViewModel Updates

**New Properties:**
- `chartDataV2: ChartDataV2Response?` - Layered chart data
- `useV2API: Bool = true` - Toggle between V2 and legacy API

**Updated `loadChart()` method:**
- Checks `useV2API` flag
- Fetches from `chart-data-v2` endpoint when enabled
- Populates both `chartDataV2` and legacy `chartData` for compatibility
- Maintains backward compatibility with legacy endpoint

### 5. ChartBridge Updates

**New Methods:**

**`setIntradayOverlay(from: [OHLCBar])`**
- Renders intraday data as a highlighted overlay
- Uses blue color (#4a90e2) for visual distinction
- Line width: 2px for emphasis

**`setForecastLayer(from: [OHLCBar])`**
- Renders forecast data as dashed line
- Shows confidence bands (upper/lower)
- Purple color (#9c27b0) with semi-transparent bands
- Line style: 2 (dashed)

### 6. WebChartView Updates

**New `updateChartV2()` method:**
- Handles layered data rendering
- Sets historical candlesticks (solid, primary color)
- Adds intraday overlay if present (highlighted)
- Adds forecast layer if present (dashed with bands)
- Applies all configured indicators to combined data

**Updated data bindings:**
- Prioritizes `chartDataV2` over legacy `chartData`
- Falls back to legacy if V2 data unavailable
- Maintains backward compatibility

## Visual Rendering

### Historical Layer (Polygon)
- **Style:** Solid candlesticks
- **Color:** Primary theme color
- **Data:** All bars before today
- **Provider:** `polygon`

### Intraday Layer (Tradier)
- **Style:** Highlighted line overlay
- **Color:** Blue (#4a90e2)
- **Data:** Today's bars only
- **Provider:** `tradier`
- **Visibility:** Only shown when market is open or recently closed

### Forecast Layer (ML)
- **Style:** Dashed line with confidence bands
- **Color:** Purple (#9c27b0)
- **Data:** Future predictions (next 10 days)
- **Provider:** `ml_forecast`
- **Features:** 
  - Upper/lower confidence bands (semi-transparent)
  - Confidence score per prediction
  - Visual distinction from historical data

## Data Flow

```
User selects symbol
    ↓
ChartViewModel.loadChart()
    ↓
APIClient.fetchChartV2()
    ↓
chart-data-v2 Edge Function
    ↓
ChartDataV2Response (3 layers)
    ↓
WebChartView.updateChartV2()
    ↓
ChartBridge rendering:
    - setCandles() → Historical
    - setIntradayOverlay() → Intraday
    - setForecastLayer() → Forecast
    ↓
TradingView chart displays all layers
```

## Backward Compatibility

The integration maintains full backward compatibility:

1. **Legacy API still works** - Set `useV2API = false` to use old endpoint
2. **Legacy chartData populated** - V2 data is also converted to legacy format
3. **Existing indicators work** - All technical indicators use combined data
4. **No breaking changes** - Existing views continue to function

## Testing

To test the integration:

1. **Build and run** the macOS app
2. **Select a symbol** (e.g., AAPL)
3. **Verify three layers render:**
   - Historical bars (solid)
   - Intraday overlay (blue, if market open)
   - Forecast line (purple, dashed with bands)
4. **Check console logs:**
   ```
   [WebChartView] Updating chart with V2 layered data
   [WebChartView] - Historical: 5458 bars
   [WebChartView] - Intraday: 0 bars
   [WebChartView] - Forecast: 10 bars
   ```

## Configuration

Toggle between V2 and legacy API:

```swift
// In ChartViewModel
viewModel.useV2API = true  // Use new layered data (default)
viewModel.useV2API = false // Use legacy flat data
```

## Benefits

1. **Data Integrity** - Clear separation prevents mixing data sources
2. **Visual Clarity** - Users can distinguish historical, live, and predicted data
3. **Accuracy** - Each layer sourced from appropriate provider
4. **Transparency** - Confidence bands show prediction uncertainty
5. **Real-time Updates** - Intraday layer updates during market hours
6. **Future-proof** - Clean architecture for additional data sources

## Files Modified

- `client-macos/SwiftBoltML/Models/ChartDataV2Response.swift` (new)
- `client-macos/SwiftBoltML/Models/OHLCBar.swift`
- `client-macos/SwiftBoltML/Services/APIClient.swift`
- `client-macos/SwiftBoltML/Services/ChartBridge.swift`
- `client-macos/SwiftBoltML/ViewModels/ChartViewModel.swift`
- `client-macos/SwiftBoltML/Views/WebChartView.swift`

## Next Steps

1. **Deploy chart-data-v2 Edge Function** to Supabase
2. **Test with live market data** during trading hours
3. **Monitor intraday updates** every 15 minutes
4. **Verify forecast accuracy** over time
5. **Collect user feedback** on visual distinction

## Related Documentation

- `QUICK_START_DATA_SEPARATION.md` - Backend deployment guide
- `DATA_LAYER_SEPARATION_IMPLEMENTATION.md` - Full architecture details
- `dataintegrity.md` - Original problem analysis
