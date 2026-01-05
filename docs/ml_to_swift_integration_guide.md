# ML to Swift Integration Guide

This guide documents how ML forecasts flow from the Python pipeline through Supabase Edge Functions to the SwiftUI client.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ML PIPELINE (Python)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ ARIMA-GARCH  │  │ Random Forest│  │ Gradient Boost│             │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         │                  │                  │                     │
│         └──────────────────┼──────────────────┘                     │
│                            ▼                                        │
│                    ┌──────────────┐                                 │
│                    │   Ensemble   │                                 │
│                    │   Combiner   │                                 │
│                    └──────┬───────┘                                 │
│                           │                                         │
│                           ▼                                         │
│                    ┌──────────────┐                                 │
│                    │  PostgreSQL  │                                 │
│                    │  (forecasts) │                                 │
│                    └──────────────┘                                 │
└─────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   SUPABASE EDGE FUNCTIONS                           │
│                                                                     │
│  GET /functions/v1/chart?symbol=AAPL&timeframe=d1                  │
│                                                                     │
│  Returns: { bars, mlSummary, indicators }                          │
└─────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     SWIFT CLIENT (macOS)                            │
│                                                                     │
│  APIClient → ChartViewModel → AdvancedChartView                    │
│                                                                     │
│  Renders: Candlesticks + Forecast Bands + Confidence Intervals     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Backend: Supabase Edge Function

### Chart Endpoint

Location: `backend/supabase/functions/chart/index.ts`

```typescript
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

serve(async (req) => {
  const url = new URL(req.url);
  const symbol = url.searchParams.get("symbol");
  const timeframe = url.searchParams.get("timeframe") || "d1";

  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
  );

  // Fetch OHLC bars
  const { data: bars } = await supabase
    .from("ohlc_bars")
    .select("ts, open, high, low, close, volume")
    .eq("symbol", symbol)
    .eq("timeframe", timeframe)
    .order("ts", { ascending: true })
    .limit(500);

  // Fetch ML forecasts
  const { data: forecasts } = await supabase
    .from("ml_forecasts")
    .select("*")
    .eq("symbol", symbol)
    .eq("timeframe", timeframe)
    .order("created_at", { ascending: false })
    .limit(1);

  const mlSummary = forecasts?.[0] ? buildMLSummary(forecasts[0]) : null;

  return new Response(
    JSON.stringify({
      symbol,
      assetType: "stock",
      timeframe,
      bars: bars || [],
      mlSummary,
    }),
    { headers: { "Content-Type": "application/json" } }
  );
});

function buildMLSummary(forecast: any): MLSummary {
  return {
    overallLabel: forecast.direction,
    confidence: forecast.confidence,
    horizons: [
      {
        horizon: `${forecast.horizon_days}d`,
        points: forecast.predictions.map((p: any) => ({
          ts: new Date(p.date).getTime() / 1000,
          value: p.mid_price,
          lower: p.lower_bound,
          upper: p.upper_bound,
        })),
      },
    ],
    srLevels: forecast.sr_levels,
    ensembleType: forecast.ensemble_type,
    modelAgreement: forecast.model_agreement,
  };
}
```

### Response Format

```json
{
  "symbol": "AAPL",
  "assetType": "stock",
  "timeframe": "d1",
  "bars": [
    {
      "ts": "2024-01-02T14:30:00Z",
      "open": 185.22,
      "high": 186.50,
      "low": 184.80,
      "close": 186.10,
      "volume": 45000000
    }
  ],
  "mlSummary": {
    "overallLabel": "bullish",
    "confidence": 0.82,
    "horizons": [
      {
        "horizon": "5d",
        "points": [
          {
            "ts": 1704326400,
            "value": 195.50,
            "lower": 192.00,
            "upper": 199.00
          },
          {
            "ts": 1704412800,
            "value": 196.25,
            "lower": 192.50,
            "upper": 200.00
          }
        ]
      }
    ],
    "srLevels": {
      "support": 188.50,
      "resistance": 201.25
    },
    "ensembleType": "RF+GB",
    "modelAgreement": 0.78
  }
}
```

---

## Swift Client: API Integration

### APIClient

Location: `client-macos/SwiftBoltML/Services/APIClient.swift`

```swift
actor APIClient {
    static let shared = APIClient()

    private let baseURL: URL
    private let decoder: JSONDecoder

    init() {
        baseURL = URL(string: Config.supabaseURL)!
        decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
    }

    func fetchChart(symbol: String, timeframe: String) async throws -> ChartResponse {
        var components = URLComponents(url: baseURL.appendingPathComponent("functions/v1/chart"), resolvingAgainstBaseURL: false)!
        components.queryItems = [
            URLQueryItem(name: "symbol", value: symbol),
            URLQueryItem(name: "timeframe", value: timeframe)
        ]

        var request = URLRequest(url: components.url!)
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              (200...299).contains(httpResponse.statusCode) else {
            throw APIError.invalidResponse
        }

        return try decoder.decode(ChartResponse.self, from: data)
    }
}
```

### Data Models

Location: `client-macos/SwiftBoltML/Models/ChartResponse.swift`

```swift
struct ChartResponse: Codable, Equatable {
    let symbol: String
    let assetType: String
    let timeframe: String
    let bars: [OHLCBar]
    let mlSummary: MLSummary?
}

struct MLSummary: Codable, Equatable {
    let overallLabel: String?
    let confidence: Double
    let horizons: [ForecastSeries]
    let srLevels: SRLevels?
    let ensembleType: String?
    let modelAgreement: Double?
}

struct ForecastSeries: Codable, Equatable {
    let horizon: String
    let points: [ForecastPoint]
}

struct ForecastPoint: Codable, Equatable {
    let ts: Int
    let value: Double
    let lower: Double
    let upper: Double

    // Flexible timestamp parsing (Int or ISO8601 string)
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)

        if let intValue = try? container.decode(Int.self, forKey: .ts) {
            ts = intValue
        } else if let stringValue = try? container.decode(String.self, forKey: .ts) {
            let formatter = ISO8601DateFormatter()
            if let date = formatter.date(from: stringValue) {
                ts = Int(date.timeIntervalSince1970)
            } else {
                throw DecodingError.dataCorruptedError(forKey: .ts, in: container, debugDescription: "Cannot parse ts")
            }
        } else {
            throw DecodingError.dataCorruptedError(forKey: .ts, in: container, debugDescription: "ts must be Int or String")
        }

        value = try container.decode(Double.self, forKey: .value)
        lower = try container.decode(Double.self, forKey: .lower)
        upper = try container.decode(Double.self, forKey: .upper)
    }
}
```

---

## ChartViewModel Integration

Location: `client-macos/SwiftBoltML/ViewModels/ChartViewModel.swift`

```swift
@MainActor
final class ChartViewModel: ObservableObject {
    @Published private(set) var chartData: ChartResponse?
    @Published private(set) var isLoading = false
    @Published var errorMessage: String?

    func loadChart() async {
        guard let symbol = selectedSymbol else { return }

        isLoading = true
        errorMessage = nil

        do {
            let response = try await APIClient.shared.fetchChart(
                symbol: symbol.ticker,
                timeframe: timeframe
            )
            chartData = response

            // Recalculate indicators with new data
            scheduleIndicatorRecalculation()
        } catch {
            errorMessage = error.localizedDescription
            chartData = nil
        }

        isLoading = false
    }
}
```

---

## Chart Rendering

Location: `client-macos/SwiftBoltML/Views/AdvancedChartView.swift`

### Forecast Overlay

```swift
@ChartContentBuilder
private func forecastOverlay(_ mlSummary: MLSummary) -> some ChartContent {
    // Determine forecast color based on direction
    let forecastColor: Color = {
        switch (mlSummary.overallLabel ?? "").lowercased() {
        case "bullish": return ChartColors.forecastBullish
        case "bearish": return ChartColors.forecastBearish
        default: return ChartColors.forecastNeutral
        }
    }()

    // Calculate starting index (after last bar)
    let lastBarIndex = bars.count - 1
    let lastClose = bars.last?.close ?? 0

    // Connect from last bar to first forecast point
    if let firstHorizon = mlSummary.horizons.first,
       let firstPoint = firstHorizon.points.first {
        LineMark(x: .value("Index", lastBarIndex), y: .value("Price", lastClose))
            .foregroundStyle(forecastColor)
            .lineStyle(StrokeStyle(lineWidth: 2.5, dash: [6, 4]))

        LineMark(x: .value("Index", lastBarIndex + 1), y: .value("Price", firstPoint.value))
            .foregroundStyle(forecastColor)
            .lineStyle(StrokeStyle(lineWidth: 2.5, dash: [6, 4]))
    }

    // Render forecast points with confidence bands
    ForEach(mlSummary.horizons, id: \.horizon) { series in
        ForEach(Array(series.points.enumerated()), id: \.offset) { offset, point in
            let forecastIndex = lastBarIndex + offset + 1

            // Main prediction line
            LineMark(
                x: .value("Index", forecastIndex),
                y: .value("Forecast", point.value)
            )
            .foregroundStyle(forecastColor)
            .lineStyle(StrokeStyle(lineWidth: 2.5, dash: [6, 4]))

            // Confidence band fill
            AreaMark(
                x: .value("Index", forecastIndex),
                yStart: .value("Lower", point.lower),
                yEnd: .value("Upper", point.upper)
            )
            .foregroundStyle(forecastColor.opacity(0.15))

            // Upper bound line
            LineMark(
                x: .value("Index", forecastIndex),
                y: .value("Upper", point.upper)
            )
            .foregroundStyle(forecastColor.opacity(0.4))
            .lineStyle(StrokeStyle(lineWidth: 1.5, dash: [3, 3]))

            // Lower bound line
            LineMark(
                x: .value("Index", forecastIndex),
                y: .value("Lower", point.lower)
            )
            .foregroundStyle(forecastColor.opacity(0.4))
            .lineStyle(StrokeStyle(lineWidth: 1.5, dash: [3, 3]))
        }
    }

    // Endpoint marker
    if let lastHorizon = mlSummary.horizons.last,
       let lastPoint = lastHorizon.points.last {
        PointMark(
            x: .value("Index", lastBarIndex + lastHorizon.points.count),
            y: .value("Forecast", lastPoint.value)
        )
        .foregroundStyle(forecastColor)
        .symbolSize(60)
    }
}
```

### Extending Chart Domain for Forecasts

```swift
private var maxChartIndex: Int {
    var maxIndex = max(0, bars.count - 1)

    // Extend domain to include forecast points
    if let mlSummary = mlSummary {
        let lastBarIndex = bars.count - 1
        for horizon in mlSummary.horizons {
            let forecastEndIndex = lastBarIndex + horizon.points.count
            maxIndex = max(maxIndex, forecastEndIndex)
        }
    }

    return maxIndex
}

// Apply in Chart
Chart { ... }
    .chartXScale(domain: 0...maxChartIndex)
```

---

## ML Pipeline: Python

### Forecast Generation

Location: `ml/src/forecast_job_worker.py`

```python
from datetime import datetime, timedelta
import numpy as np
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor

class ForecastGenerator:
    def __init__(self, symbol: str, horizon_days: int = 5):
        self.symbol = symbol
        self.horizon_days = horizon_days

    def generate_forecast(self, historical_data: pd.DataFrame) -> dict:
        """Generate ensemble forecast with confidence intervals."""

        # Prepare features
        X, y = self._prepare_features(historical_data)

        # Train ensemble models
        rf_model = RandomForestRegressor(n_estimators=100)
        gb_model = GradientBoostingRegressor(n_estimators=100)

        rf_model.fit(X, y)
        gb_model.fit(X, y)

        # Generate predictions
        future_features = self._generate_future_features(historical_data)
        rf_pred = rf_model.predict(future_features)
        gb_pred = gb_model.predict(future_features)

        # Ensemble combination
        ensemble_pred = 0.6 * rf_pred + 0.4 * gb_pred

        # Calculate confidence intervals
        current_price = historical_data['close'].iloc[-1]
        tolerance = 0.01 if self.horizon_days <= 3 else 0.02

        predictions = []
        for i, pred in enumerate(ensemble_pred):
            date = datetime.now() + timedelta(days=i+1)
            predictions.append({
                'date': date.isoformat(),
                'mid_price': float(pred),
                'lower_bound': float(pred * (1 - tolerance)),
                'upper_bound': float(pred * (1 + tolerance)),
            })

        # Determine direction
        direction = 'bullish' if ensemble_pred[-1] > current_price else 'bearish'

        return {
            'symbol': self.symbol,
            'horizon_days': self.horizon_days,
            'direction': direction,
            'confidence': self._calculate_confidence(rf_pred, gb_pred),
            'predictions': predictions,
            'ensemble_type': 'RF+GB',
            'model_agreement': self._calculate_agreement(rf_pred, gb_pred),
        }

    def _calculate_confidence(self, rf_pred: np.ndarray, gb_pred: np.ndarray) -> float:
        """Calculate confidence based on model agreement and volatility."""
        agreement = 1 - np.std(rf_pred - gb_pred) / np.mean(np.abs(rf_pred))
        return min(0.95, max(0.5, agreement))

    def _calculate_agreement(self, rf_pred: np.ndarray, gb_pred: np.ndarray) -> float:
        """Calculate model agreement score (0-1)."""
        # Agreement based on same direction for each day
        rf_direction = np.sign(np.diff(rf_pred))
        gb_direction = np.sign(np.diff(gb_pred))
        return float(np.mean(rf_direction == gb_direction))
```

### Storing Forecasts

```python
async def store_forecast(supabase, forecast: dict):
    """Store forecast in PostgreSQL via Supabase."""
    await supabase.table('ml_forecasts').insert({
        'symbol': forecast['symbol'],
        'timeframe': 'd1',
        'horizon_days': forecast['horizon_days'],
        'direction': forecast['direction'],
        'confidence': forecast['confidence'],
        'predictions': forecast['predictions'],
        'ensemble_type': forecast['ensemble_type'],
        'model_agreement': forecast['model_agreement'],
        'created_at': datetime.now().isoformat(),
    })
```

---

## Database Schema

### ml_forecasts Table

```sql
CREATE TABLE ml_forecasts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL DEFAULT 'd1',
    horizon_days INTEGER NOT NULL,
    direction TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    predictions JSONB NOT NULL,
    ensemble_type TEXT,
    model_agreement DOUBLE PRECISION,
    sr_levels JSONB,
    training_stats JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);

CREATE INDEX idx_ml_forecasts_symbol_timeframe ON ml_forecasts(symbol, timeframe);
CREATE INDEX idx_ml_forecasts_created_at ON ml_forecasts(created_at DESC);
```

---

## Error Handling

### API Client Errors

```swift
enum APIError: LocalizedError {
    case invalidResponse
    case decodingFailed(String)
    case networkError(Error)
    case serverError(Int)

    var errorDescription: String? {
        switch self {
        case .invalidResponse: return "Invalid server response"
        case .decodingFailed(let details): return "Failed to decode: \(details)"
        case .networkError(let error): return "Network error: \(error.localizedDescription)"
        case .serverError(let code): return "Server error: \(code)"
        }
    }
}
```

### Graceful Degradation

```swift
// In ChartView
if let chartData = chartViewModel.chartData {
    if let mlSummary = chartData.mlSummary {
        // Show full chart with forecasts
        AdvancedChartView(bars: chartData.bars, mlSummary: mlSummary, ...)
    } else {
        // Show chart without forecasts (ML unavailable)
        AdvancedChartView(bars: chartData.bars, mlSummary: nil, ...)
    }
}
```

---

## Testing

### Mock Forecast Data

```swift
extension MLSummary {
    static var mock: MLSummary {
        MLSummary(
            overallLabel: "bullish",
            confidence: 0.82,
            horizons: [
                ForecastSeries(
                    horizon: "5d",
                    points: (1...5).map { day in
                        ForecastPoint(
                            ts: Int(Date().timeIntervalSince1970) + (day * 86400),
                            value: 195.0 + Double(day) * 0.5,
                            lower: 193.0 + Double(day) * 0.3,
                            upper: 197.0 + Double(day) * 0.7
                        )
                    }
                )
            ],
            srLevels: SRLevels(support: 188.50, resistance: 201.25),
            ensembleType: "RF+GB",
            modelAgreement: 0.78
        )
    }
}
```

---

## Future Enhancements

1. **WebSocket Live Updates**: Stream real-time price updates
2. **Forecast Accuracy Tracking**: Compare predictions to actual prices
3. **Multi-Horizon Display**: Show 1d, 3d, 5d, 10d forecasts simultaneously
4. **Confidence Cone**: Widening confidence bands over time
5. **What-If Analysis**: User-adjustable scenario modeling
