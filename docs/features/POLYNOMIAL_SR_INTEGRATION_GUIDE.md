# Polynomial Support & Resistance: Frontend Integration Guide

## Overview

The polynomial regression S/R indicator has been fully integrated into the macOS web charts UI. The integration includes:

1. **API Data Fetching** - Hook to fetch S/R data from the backend
2. **Indicator Panel** - Analysis sidebar showing detailed S/R metrics
3. **Chart Rendering** - Polynomial curves displayed on the trading chart
4. **Full Wiring** - Complete integration with the existing forecast chart

---

## Files Created

### 1. `src/hooks/useIndicators.ts`
Custom React hook for fetching S/R indicator data from the API.

**Features:**
- Fetches `/api/support-resistance` endpoint
- Auto-refreshes every 30 seconds
- Provides loading/error states
- TypeScript types for S/R data structures

**Usage:**
```typescript
const { data, loading, error, refetch } = useIndicators(symbol, timeframe);
```

### 2. `src/components/IndicatorPanel.tsx`
Detailed analysis panel displaying polynomial S/R metrics.

**Displays:**
- Polynomial support level with slope and trend
- Polynomial resistance level with slope and trend
- Nearest support/resistance levels
- S/R bias (bullish/bearish/neutral)
- Multi-timeframe pivot levels
- Forecast data (next 5 bars)
- Last updated timestamp

**Features:**
- Expandable/collapsible sections
- Color-coded trend indicators
- Live slope values (price per bar)
- Touch-friendly interface

### 3. `src/components/ChartWithIndicators.tsx`
Layout component combining chart and indicator panel.

**Layout:**
- Desktop: 2-column layout (chart 2/3 width, panel 1/3 width)
- Mobile: Stacked layout (chart full width, panel below)

### 4. Updated `src/components/TradingViewChart.tsx`
Enhanced with polynomial S/R rendering capabilities.

**New Features:**
- Accepts `srData` prop for indicator data
- Renders polynomial support line (blue, #2962ff)
- Renders polynomial resistance line (red, #f23645)
- Updated legend with S/R line indicators
- Real-time S/R line updates

### 5. Updated `src/App.tsx`
Integrated new ChartWithIndicators component.

---

## How It Works

### Data Flow

```
Frontend (App.tsx)
  ↓
ChartWithIndicators
  ├─ useIndicators hook
  │   ├─ Fetches /api/support-resistance endpoint
  │   └─ Returns SupportResistanceData
  │
  ├─ TradingViewChart (receives srData)
  │   └─ Renders polynomial S/R curves on chart
  │
  └─ IndicatorPanel (receives srData)
      └─ Displays detailed metrics
```

### Component Hierarchy

```
App
└─ ChartWithIndicators
   ├─ TradingViewChart
   │  └─ Lightweight Charts
   │     ├─ Candlesticks
   │     ├─ Forecast line
   │     ├─ Confidence band
   │     ├─ Support line (from srData)
   │     └─ Resistance line (from srData)
   │
   └─ IndicatorPanel
      ├─ Polynomial S/R Section
      │  ├─ Support metrics
      │  └─ Resistance metrics
      │
      ├─ Summary Section
      │  ├─ Current price
      │  ├─ Nearest support/resistance
      │  └─ S/R bias
      │
      └─ Pivot Levels Section
         └─ Multi-timeframe pivots
```

---

## UI Appearance

### Analysis Panel (Right Sidebar)

```
┌─────────────────────────────────┐
│ 📊 Analysis                     │
├─────────────────────────────────┤
│ 📈 Polynomial Regression S/R    │ [✓ Expanded]
├─────────────────────────────────┤
│ Support (Polynomial)            │
│ │ Price Level: $244.66          │
│ │ Slope (Price/Bar): +0.0234    │
│ │ Trend: rising                 │
│                                 │
│ Resistance (Polynomial)         │
│ │ Price Level: $277.27          │
│ │ Slope (Price/Bar): -0.0156    │
│ │ Trend: falling                │
├─────────────────────────────────┤
│ 🎯 Support & Resistance         │ [✓ Expanded]
├─────────────────────────────────┤
│ Price    │ Support  │ Resistance│
│ $256.45  │ $244.66  │  $277.27  │
│          │ 5.3% ↓   │  7.3% ↑   │
│                                 │
│ S/R Bias: Bullish (0.72)        │
├─────────────────────────────────┤
│ ⭐ Pivot Levels (3)             │ [✓ Expanded]
├─────────────────────────────────┤
│ Period 5 Bar                    │
│ Low: $243.45  High: $277.79     │
│                                 │
│ Period 25 Bar                   │
│ Low: $246.28  High: $275.34     │
│                                 │
│ ... (more pivots)               │
└─────────────────────────────────┘
```

### Chart with S/R Lines

```
High
  |     ┌─── Resistance (red line)
  |     │
  |   ┌─┼─┬─┐
  |   │ │ │ │ (candlesticks)
  |───┼─┤─┼─┤─── Support (blue line)
  |   │ │ │ │
  | ──┼─┴─┼─┴──
  |   └─────────
Low
    Time →

Legend:
🟦 Polynomial Support (blue, slope: +0.0234)
🟥 Polynomial Resistance (red, slope: -0.0156)
🟩 Price Up  🟪 Price Down
🟦 Forecast  🔷 Confidence Band
```

---

## Styling & Colors

### Polynomial S/R
- **Support**: #2962ff (TradingView Blue)
  - Light variant: #42a5f5
  - Status background: bg-blue-900/20

- **Resistance**: #f23645 (TradingView Red)
  - Light variant: #ef5350
  - Status background: bg-red-900/20

### Trend Indicators
- **Rising**: Text green-400, bg-green-900/30
- **Falling**: Text red-400, bg-red-900/30
- **Flat**: Text gray-400, bg-gray-800

### Bias Indicator
- **Bullish**: Green (text-green-400, border-green-700/30)
- **Bearish**: Red (text-red-400, border-red-700/30)
- **Neutral**: Gray (text-gray-400, border-gray-700/30)

---

## API Endpoint

The frontend calls the backend S/R indicator endpoint:

```
GET /api/support-resistance?symbol={symbol}&timeframe={timeframe}
```

**Response Structure:**
```json
{
  "symbol": "AAPL",
  "current_price": 256.45,
  "last_updated": "2026-01-28T14:30:00Z",
  "nearest_support": 244.66,
  "nearest_resistance": 277.27,
  "support_distance_pct": 5.3,
  "resistance_distance_pct": 7.3,
  "bias": "bullish",
  "polynomial_support": {
    "level": 244.66,
    "slope": 0.0234,
    "trend": "rising",
    "forecast": [245.10, 245.52, 245.95, ...]
  },
  "polynomial_resistance": {
    "level": 277.27,
    "slope": -0.0156,
    "trend": "falling",
    "forecast": [277.19, 277.11, 277.02, ...]
  },
  "pivot_levels": [
    {
      "period": 5,
      "level_high": 277.79,
      "level_low": 243.45
    },
    ...
  ]
}
```

---

## Usage Instructions

### For Users

1. **View Polynomial S/R**:
   - Open SwiftBolt charts
   - S/R indicator loads automatically in the Analysis panel
   - Polynomial curves appear on the chart as blue (support) and red (resistance) lines

2. **Interpret the Data**:
   - **Level**: Current polynomial S/R value
   - **Slope**: Price change per bar (positive = rising, negative = falling)
   - **Trend**: Visual classification (rising/falling/flat)
   - **Forecast**: Projected S/R values for next 5 bars

3. **Analyze S/R Bias**:
   - **Bullish**: Support is closer (price closer to support than resistance)
   - **Bearish**: Resistance is closer (price closer to resistance than support)
   - **Neutral**: Equal distance to both levels

### For Developers

1. **Fetch Data Manually**:
```typescript
import { useIndicators } from './hooks/useIndicators';

const MyComponent = ({ symbol, timeframe }) => {
  const { data, loading, error } = useIndicators(symbol, timeframe);

  return (
    <div>
      {loading && <p>Loading...</p>}
      {error && <p>Error: {error}</p>}
      {data && (
        <>
          <p>Support: ${data.polynomial_support?.level}</p>
          <p>Resistance: ${data.polynomial_resistance?.level}</p>
        </>
      )}
    </div>
  );
};
```

2. **Add S/R to Custom Chart**:
```typescript
import { useIndicators } from './hooks/useIndicators';

const CustomChart = ({ symbol, timeframe }) => {
  const { data } = useIndicators(symbol, timeframe);

  // Use data.polynomial_support and data.polynomial_resistance
  // to render on your chart
};
```

3. **Customize Update Frequency**:
Edit `src/hooks/useIndicators.ts` line 62:
```typescript
// Change from 30000ms (30s) to your preferred interval
const interval = setInterval(fetchIndicators, 30000);
```

---

## Customization

### Change S/R Colors

Edit `src/components/TradingViewChart.tsx` lines 131-157:

```typescript
// Support line color
const supportLine = chart.addLineSeries({
  color: '#2962ff',  // Change this color
  // ...
});

// Resistance line color
const resistanceLine = chart.addLineSeries({
  color: '#f23645',  // Change this color
  // ...
});
```

### Change Panel Layout

Edit `src/components/ChartWithIndicators.tsx`:

```typescript
// For full-width panel (mobile-style):
<div className="grid grid-cols-1 gap-6">
  <div>... Chart ...</div>
  <div>... Panel ...</div>
</div>

// For side-by-side (current desktop style):
<div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
  <div className="lg:col-span-2">... Chart ...</div>
  <div className="lg:col-span-1">... Panel ...</div>
</div>
```

### Add More Indicators

Extend `src/hooks/useIndicators.ts` to fetch additional data from the backend, then add a new section to `src/components/IndicatorPanel.tsx`.

---

## Troubleshooting

### "No data available" in panel

**Cause**: API endpoint not responding or invalid symbol/timeframe

**Solution**:
1. Check backend is running: `python -m uvicorn main:app --reload`
2. Verify symbol exists: `curl http://localhost:8000/api/support-resistance?symbol=AAPL&timeframe=1h`
3. Check browser console for error messages

### S/R lines not showing on chart

**Cause**: Polynomial data not available (insufficient pivots)

**Solution**:
- Indicator requires at least 4 pivot points
- Try a longer timeframe (1D instead of 15m)
- Wait for more bars to be available

### Panel not updating

**Cause**: Update interval too slow or data hasn't changed

**Solution**:
- Manual refresh: Check browser console logs
- Change update interval in useIndicators hook (default 30s)
- Check API for fresh data: `curl http://localhost:8000/api/support-resistance?symbol=AAPL&timeframe=1h`

### Styling issues

**Cause**: Tailwind CSS not processing new components

**Solution**:
1. Rebuild frontend: `npm run build`
2. Clear browser cache: Cmd+Shift+Delete (Chrome)
3. Check Tailwind includes new files in `tailwind.config.js`

---

## Performance Considerations

### API Call Frequency
- Default: 30-second refresh interval
- Adjust in `src/hooks/useIndicators.ts` line 62
- Balances real-time accuracy vs. API load

### Chart Rendering
- Polynomial curves rendered as simple line series
- No performance impact on existing forecast rendering
- Lightweight-charts optimizes line rendering automatically

### Memory Usage
- IndicatorPanel data stored in hook state
- Chart component has references to line series
- No memory leaks (cleanup in useEffect return)

---

## Next Steps

### Enhancements You Can Add

1. **Interactive Controls**:
   - Toggle S/R curves on/off
   - Adjust polynomial degree (linear/quadratic/cubic)
   - Change lookback window

2. **Alerts & Notifications**:
   - Alert when price crosses S/R levels
   - Notify when slope changes direction

3. **Historical Analysis**:
   - Compare S/R across timeframes
   - Track S/R accuracy over time

4. **Export**:
   - Export S/R metrics as CSV
   - Generate PDF reports with charts

### Backend Enhancements

- Add more indicator data to `/api/support-resistance` response
- Implement WebSocket for real-time S/R updates
- Add forecasting confidence scores

---

## Support

For questions or issues:

1. Check logs in browser console (F12)
2. Check backend API: `curl http://localhost:8000/api/support-resistance?symbol=AAPL&timeframe=1h`
3. Verify all frontend files were created correctly
4. Ensure backend `/ml/api/routers/support_resistance.py` is running

---

## Summary

The polynomial S/R indicator is now fully integrated into your web charts UI with:

✅ **Data Fetching** - Automatic API calls every 30 seconds
✅ **Chart Rendering** - Blue support & red resistance curves on main chart
✅ **Analysis Panel** - Detailed S/R metrics with slopes and trends
✅ **Mobile Responsive** - Works on desktop, tablet, and mobile
✅ **TypeScript Types** - Full type safety for S/R data

The indicator is ready for production use and matches the TradingView aesthetic exactly.
