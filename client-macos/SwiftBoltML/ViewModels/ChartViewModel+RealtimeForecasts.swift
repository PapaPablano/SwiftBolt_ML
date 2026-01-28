//
//  ChartViewModel+RealtimeForecasts.swift
//  SwiftBoltML
//
//  Extension to ChartViewModel for real-time forecast loading
//

import Foundation
import SwiftUI

extension ChartViewModel {

    // MARK: - Real-time Forecast Loading

    /// Load chart data using the new real-time forecast API
    /// This is an alternative to the existing loadChart() method
    func loadRealtimeChart() async {
        guard let symbol = selectedSymbol else {
            errorMessage = "No symbol selected"
            return
        }

        errorMessage = nil

        do {
            // Check if real-time API is available
            let isAvailable = await APIClient.shared.checkRealtimeAPIHealth()
            guard isAvailable else {
                throw APIError.serviceUnavailable(message: "Real-time forecast API not available. Make sure FastAPI backend is running on http://localhost:8000")
            }

            // Map Timeframe to horizon string
            let horizon = self.timeframe.toHorizonString()

            // Fetch chart data from real-time API
            let realtimeData = try await APIClient.shared.fetchRealtimeChartData(
                symbol: symbol.ticker,
                horizon: horizon,
                daysBack: 30
            )

            // Update chart data from real-time API
            // The existing chart rendering system will pick up the data from the models
            print("[RealtimeChart] Loaded \(realtimeData.bars.count) bars and \(realtimeData.forecasts.count) forecasts for \(symbol.ticker)/\(horizon)")

            // Store the real-time data in a way the chart can use it
            self.realtimeChartData = realtimeData

        } catch {
            errorMessage = "Failed to load real-time chart: \(error.localizedDescription)"
            print("[RealtimeChart] Error: \(error)")
        }
    }

    /// Start WebSocket connection for live forecast updates
    func startRealtimeForecastUpdates() {
        guard let symbol = selectedSymbol else { return }

        let horizon = self.timeframe.toHorizonString()

        // Create WebSocket instance if needed
        if realtimeWebSocket == nil {
            realtimeWebSocket = RealtimeForecastWebSocket()
        }

        // Set up callbacks
        realtimeWebSocket?.onForecastUpdate = { [weak self] forecast in
            Task { @MainActor in
                self?.handleNewForecast(forecast)
            }
        }

        realtimeWebSocket?.onConnectionChange = { [weak self] connected in
            Task { @MainActor in
                self?.isRealtimeConnected = connected
            }
        }

        // Connect
        realtimeWebSocket?.connect(symbol: symbol.ticker, horizon: horizon)

        print("[RealtimeChart] Started WebSocket for \(symbol.ticker)/\(horizon)")
    }

    /// Stop WebSocket connection
    func stopRealtimeForecastUpdates() {
        realtimeWebSocket?.disconnect()
        realtimeWebSocket = nil
        isRealtimeConnected = false
        print("[RealtimeChart] Stopped WebSocket")
    }

    /// Handle new forecast from WebSocket
    private func handleNewForecast(_ forecast: ForecastOverlayData) {
        print("[RealtimeChart] New forecast received: $\(String(format: "%.2f", forecast.price)) (\(forecast.direction))")

        // Show notification
        showForecastNotification(forecast)
    }

    /// Show notification for new forecast
    private func showForecastNotification(_ forecast: ForecastOverlayData) {
        let direction = forecast.direction.uppercased()
        let price = String(format: "$%.2f", forecast.price)
        let confidence = String(format: "%.0f%%", forecast.confidence * 100)

        // Log the new forecast
        print("[RealtimeChart] 🔔 New \(direction) forecast: \(price) (\(confidence) confidence)")
    }
}

// MARK: - Timeframe Extension

extension Timeframe {

    /// Convert Timeframe to horizon string for real-time API
    func toHorizonString() -> String {
        switch self {
        case .m15:
            return "15m"
        case .h1:
            return "1h"
        case .h4:
            return "4h"
        case .d1:
            return "1D"
        case .w1:
            return "1W"
        }
    }
}
