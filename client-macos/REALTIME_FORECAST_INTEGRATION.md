# Real-time Forecast Integration Guide

## ✅ What's Been Added

Your SwiftBoltML macOS app now has real-time forecast support integrated! Here's what was added:

### New Files Created

1. **`Models/RealtimeForecastModels.swift`**
   - Models matching the new FastAPI `/api/v1/chart-data/{symbol}/{horizon}` endpoint
   - Conversion methods to integrate with existing chart system

2. **`Services/RealtimeForecastService.swift`**
   - API client extension for fetching real-time chart data
   - WebSocket service for live forecast updates
   - Health check for FastAPI backend availability

3. **`ViewModels/ChartViewModel+RealtimeForecasts.swift`**
   - Extension to ChartViewModel with real-time methods
   - WebSocket connection management
   - Live forecast update handling

4. **`Views/RealtimeForecastToggle.swift`**
   - UI toggle component for switching to real-time mode
   - Connection status indicator
   - API health checker

---

## 🚀 How to Use

### Step 1: Add Files to Xcode Project

1. Open `SwiftBoltML.xcodeproj` in Xcode
2. **Add new files to project:**
   - Right-click on `Models` folder → Add Files
     - Select `RealtimeForecastModels.swift`
   - Right-click on `Services` folder → Add Files
     - Select `RealtimeForecastService.swift`
   - Right-click on `ViewModels` folder → Add Files
     - Select `ChartViewModel+RealtimeForecasts.swift`
   - Right-click on `Views` folder → Add Files
     - Select `RealtimeForecastToggle.swift`

### Step 2: Update ChartView

Add the real-time toggle to your chart view. Open `Views/ChartView.swift` or `Views/AdvancedChartView.swift` and add:

```swift
import SwiftUI

struct YourChartView: View {
    @ObservedObject var viewModel: ChartViewModel
    
    var body: some View {
        VStack(spacing: 0) {
            // Add the real-time toggle at the top
            RealtimeForecastToggle(viewModel: viewModel)
                .padding()
            
            // Your existing chart view
            // ... rest of your chart code
        }
    }
}
```

### Step 3: Start FastAPI Backend

Make sure your FastAPI backend is running:

```bash
cd /Users/ericpeterson/SwiftBolt_ML/ml
uvicorn api.main:app --reload
```

The API will be available at `http://localhost:8000`

### Step 4: Test the Integration

1. **Run the macOS app** in Xcode (⌘R)
2. **Navigate to chart view** with a symbol selected (e.g., AAPL)
3. **Click "Check"** button to verify FastAPI is running
4. **Toggle "Real-time Forecasts"** to ON
5. **Watch forecasts appear** as markers on the chart!

---

## 🎯 Features

### Real-time Chart Data
- Fetches OHLC bars + forecasts from FastAPI endpoint
- Displays forecast targets as chart markers
- Shows latest forecast as a price line
- Supports all timeframes: 15m, 1h, 4h, 8h, 1D, 5D, 10D, 20D

### Live WebSocket Updates
- Automatically connects to WebSocket for live updates
- Receives new forecasts as they're generated
- Shows connection status indicator (green = live, gray = offline)
- Automatically adds new forecast markers to chart

### Health Monitoring
- "Check" button verifies FastAPI backend availability
- Shows helpful error messages if backend not running
- Automatically reverts toggle if API unavailable

---

## 🔧 API Endpoints Used

### REST API
```
GET http://localhost:8000/api/v1/chart-data/{symbol}/{horizon}?days_back=30
```

**Response:**
```json
{
  "symbol": "AAPL",
  "horizon": "1h",
  "bars": [{"time": 1769547600, "open": 257.6, ...}, ...],
  "forecasts": [{"time": 1769551222, "price": 263.51, "confidence": 0.6, "direction": "bullish"}, ...],
  "latest_price": 257.6,
  "latest_forecast": {...},
  "timestamp": 1769554297
}
```

### WebSocket API
```
ws://localhost:8000/api/v1/ws/live-forecasts/{symbol}/{horizon}
```

**Messages:**
```json
{
  "type": "new_forecast",
  "symbol": "AAPL",
  "horizon": "1h",
  "data": {
    "time": 1769551222,
    "price": 263.51,
    "confidence": 0.6,
    "direction": "bullish"
  },
  "timestamp": 1769554297
}
```

---

## 🎨 Chart Visualization

### Forecast Markers
- **Bullish**: Green up arrow ↑
- **Bearish**: Red down arrow ↓
- **Neutral**: Gray circle ●

Markers show:
- Target price (e.g., "$263.51")
- Confidence level (e.g., "60%")

### Price Lines
- Horizontal line at forecast target price
- Color matches direction (green/red/gray)
- Label shows "Target: $XXX.XX"

---

## 🔄 Switching Between Modes

### Standard Mode (Default)
- Uses existing Supabase/Edge Function API
- Fetches from `chart_data_v2` function
- Shows historical ML forecasts

### Real-time Mode (New)
- Uses FastAPI backend on localhost:8000
- Fetches from `/api/v1/chart-data` endpoint
- Shows live ML forecasts with WebSocket updates

**Toggle between modes** anytime without restarting the app!

---

## 📊 Supported Timeframes

| Timeframe | Horizon | Update Frequency |
|-----------|---------|------------------|
| 15 min    | 15m     | Every 15 minutes |
| 1 hour    | 1h      | Every hour       |
| 4 hour    | 4h      | Every 4 hours    |
| 8 hour    | 8h      | Every 8 hours    |
| Daily     | 1D      | Daily            |
| 5 Day     | 5D      | Daily            |
| 10 Day    | 10D     | Daily            |
| 20 Day    | 20D     | Daily            |

---

## 🐛 Troubleshooting

### "Real-time API not available"
**Solution:**
```bash
# Start FastAPI backend
cd /Users/ericpeterson/SwiftBolt_ML/ml
uvicorn api.main:app --reload

# Verify it's running
curl http://localhost:8000/api/v1/health/realtime-charts
```

### "WebSocket not connecting"
**Possible causes:**
1. FastAPI not running → Start it
2. Port 8000 blocked → Check firewall
3. Symbol/horizon mismatch → Verify symbol is valid

**Check logs:**
- Look for `[RealtimeChart]` and `[RealtimeForecastWebSocket]` prefixes in Xcode console

### "No forecasts showing"
**Possible causes:**
1. No recent forecasts in database
2. Symbol not in ml_forecasts_intraday table
3. Wrong timeframe selected

**Solution:**
```bash
# Trigger a forecast manually
curl -X POST http://localhost:8000/api/v1/trigger-forecast-update/AAPL/1h
```

---

## 🎯 Next Steps

### Optional Enhancements

1. **Add Settings Panel**
   - Configure WebSocket auto-reconnect
   - Adjust forecast marker styles
   - Set custom colors

2. **Forecast Notifications**
   - macOS notifications for new high-confidence forecasts
   - Sound alerts for significant price targets

3. **Historical Comparison**
   - Overlay past forecast accuracy
   - Show forecast vs. actual price paths

4. **Multi-Symbol Dashboard**
   - Real-time forecasts for watchlist
   - Grid view with live updates

---

## 📚 Code Examples

### Manually Trigger Real-time Load

```swift
Task {
    await viewModel.loadRealtimeChart()
}
```

### Start/Stop WebSocket

```swift
// Start
viewModel.startRealtimeForecastUpdates()

// Stop
viewModel.stopRealtimeForecastUpdates()

// Check connection
if viewModel.isRealtimeConnected {
    print("WebSocket is live!")
}
```

### Check API Health

```swift
Task {
    let healthy = await APIClient.shared.checkRealtimeAPIHealth()
    print("API Status: \(healthy ? "Healthy" : "Offline")")
}
```

---

## ✅ Integration Complete!

Your SwiftBoltML macOS app now supports **real-time ML forecasts** with live WebSocket updates!

**Enjoy your enhanced trading dashboard! 🚀📈**
