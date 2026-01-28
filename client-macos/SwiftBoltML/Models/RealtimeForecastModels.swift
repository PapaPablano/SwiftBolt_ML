//
//  RealtimeForecastModels.swift
//  SwiftBoltML
//
//  Models for Real-time Forecast Chart API
//  Connects to /api/v1/chart-data/{symbol}/{horizon}
//

import Foundation

// MARK: - Real-time Forecast Chart Data

/// Complete chart data bundle from real-time API
struct RealtimeChartData: Codable {
    let symbol: String
    let horizon: String
    let bars: [OHLCBarRealtime]
    let forecasts: [ForecastOverlayData]
    let latestPrice: Double
    let latestForecast: ForecastOverlayData?
    let timestamp: Int
    
    enum CodingKeys: String, CodingKey {
        case symbol, horizon, bars, forecasts, timestamp
        case latestPrice = "latest_price"
        case latestForecast = "latest_forecast"
    }
}

/// OHLC bar in real-time format
struct OHLCBarRealtime: Codable {
    let time: Int  // Unix timestamp
    let open: Double
    let high: Double
    let low: Double
    let close: Double
    let volume: Double?
    
    /// Convert to LightweightCandle for chart display
    func toLightweightCandle() -> LightweightCandle {
        return LightweightCandle(
            time: time,
            open: open,
            high: high,
            low: low,
            close: close
        )
    }
}

/// Forecast overlay data
struct ForecastOverlayData: Codable {
    let time: Int  // Unix timestamp
    let price: Double
    let confidence: Double
    let direction: String  // "bullish", "bearish", "neutral"
    
    /// Convert to chart marker
    func toChartMarker() -> ChartMarker {
        let shape: String
        let color: String
        let type: String

        switch direction.lowercased() {
        case "bullish":
            shape = "arrowUp"
            color = "#26a69a"  // Green
            type = "buy"
        case "bearish":
            shape = "arrowDown"
            color = "#ef5350"  // Red
            type = "sell"
        default:
            shape = "circle"
            color = "#888888"  // Gray
            type = "sell"
        }

        return ChartMarker(
            time: time,
            type: type,
            text: String(format: "%.2f (%.0f%%)", price, confidence * 100),
            color: color,
            position: "aboveBar",
            shape: shape
        )
    }
    
    /// Convert to price line
    func toPriceLine() -> (price: Double, color: String, label: String) {
        let color: String
        switch direction.lowercased() {
        case "bullish":
            color = "#26a69a"
        case "bearish":
            color = "#ef5350"
        default:
            color = "#888888"
        }
        
        let label = String(format: "Target: $%.2f", price)
        return (price, color, label)
    }
}

// MARK: - WebSocket Update Models

/// WebSocket message for real-time forecast updates
struct RealtimeForecastUpdate: Codable {
    let type: String  // "new_forecast", "price_update", "connection_confirmed"
    let symbol: String
    let horizon: String
    let data: ForecastOverlayData?
    let timestamp: Int
    let message: String?
}
