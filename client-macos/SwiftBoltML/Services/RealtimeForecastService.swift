//
//  RealtimeForecastService.swift
//  SwiftBoltML
//
//  Service for fetching real-time forecast chart data
//  Connects to FastAPI backend on http://localhost:8000
//

import Foundation

extension APIClient {
    
    // MARK: - Real-time Forecast API
    
    /// Fetch complete chart data with forecasts from real-time API
    /// - Parameters:
    ///   - symbol: Stock symbol (e.g., "AAPL")
    ///   - horizon: Timeframe ("15m", "1h", "4h", "1D", etc.)
    ///   - daysBack: Number of days of historical data (default: 30)
    /// - Returns: RealtimeChartData with OHLC bars and forecast overlays
    func fetchRealtimeChartData(
        symbol: String,
        horizon: String,
        daysBack: Int = 30
    ) async throws -> RealtimeChartData {
        
        // FastAPI backend URL
        guard let backendURL = URL(string: "http://localhost:8000") else {
            throw APIError.invalidURL
        }
        
        // Build endpoint: /api/v1/chart-data/{symbol}/{horizon}
        let endpoint = backendURL
            .appendingPathComponent("api")
            .appendingPathComponent("v1")
            .appendingPathComponent("chart-data")
            .appendingPathComponent(symbol.uppercased())
            .appendingPathComponent(horizon)
        
        // Add query parameter
        var components = URLComponents(url: endpoint, resolvingAgainstBaseURL: false)
        components?.queryItems = [
            URLQueryItem(name: "days_back", value: String(daysBack))
        ]
        
        guard let url = components?.url else {
            throw APIError.invalidURL
        }
        
        // Create request
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.timeoutInterval = 30
        
        // Execute request
        let (data, response) = try await URLSession.shared.data(for: request)
        
        // Validate response
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        
        // Handle HTTP errors
        guard (200...299).contains(httpResponse.statusCode) else {
            let message = String(data: data, encoding: .utf8)
            throw APIError.httpError(statusCode: httpResponse.statusCode, message: message)
        }
        
        // Decode response
        do {
            let decoder = JSONDecoder()
            let chartData = try decoder.decode(RealtimeChartData.self, from: data)
            return chartData
        } catch {
            throw APIError.decodingError(error)
        }
    }
    
    /// Check if FastAPI backend is available.
    /// Uses shared FastAPIBackoff so repeated failures (e.g. backend not running) don't spam the console.
    func checkRealtimeAPIHealth() async -> Bool {
        guard let url = URL(string: "http://localhost:8000/api/v1/health/realtime-charts") else {
            return false
        }

        if FastAPIBackoff.shouldSkip(url: url) {
            return false
        }

        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.timeoutInterval = 1.5

        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse else {
                FastAPIBackoff.recordFailure(url: url)
                return false
            }
            let ok = (200...299).contains(httpResponse.statusCode)
            if ok { FastAPIBackoff.clearSuccess(url: url) }
            else { FastAPIBackoff.recordFailure(url: url) }
            return ok
        } catch {
            FastAPIBackoff.recordFailure(url: url)
            #if DEBUG
            print("[RealtimeForecast] Health check failed. Test from this machine: curl -v \"\(url.absoluteString)\"")
            #endif
            return false
        }
    }
}

// MARK: - WebSocket Service for Live Updates

/// WebSocket service for real-time forecast updates
class RealtimeForecastWebSocket: NSObject {
    
    private var webSocket: URLSessionWebSocketTask?
    private var isConnected = false
    
    /// Callback when new forecast is received
    var onForecastUpdate: ((ForecastOverlayData) -> Void)?
    
    /// Callback when connection status changes
    var onConnectionChange: ((Bool) -> Void)?
    
    /// Connect to WebSocket for live updates
    /// - Parameters:
    ///   - symbol: Stock symbol
    ///   - horizon: Timeframe
    func connect(symbol: String, horizon: String) {
        guard let url = URL(string: "ws://localhost:8000/api/v1/ws/live-forecasts/\(symbol.uppercased())/\(horizon)") else {
            print("[RealtimeForecastWebSocket] Invalid WebSocket URL")
            return
        }
        
        let session = URLSession(configuration: .default)
        webSocket = session.webSocketTask(with: url)
        webSocket?.resume()
        
        isConnected = true
        onConnectionChange?(true)
        
        print("[RealtimeForecastWebSocket] Connected to \(symbol)/\(horizon)")
        
        // Start receiving messages
        receiveMessage()
    }
    
    /// Disconnect from WebSocket
    func disconnect() {
        webSocket?.cancel(with: .goingAway, reason: nil)
        webSocket = nil
        isConnected = false
        onConnectionChange?(false)
        print("[RealtimeForecastWebSocket] Disconnected")
    }
    
    /// Receive messages from WebSocket
    private func receiveMessage() {
        webSocket?.receive { [weak self] result in
            switch result {
            case .success(let message):
                switch message {
                case .string(let text):
                    self?.handleMessage(text)
                case .data(let data):
                    if let text = String(data: data, encoding: .utf8) {
                        self?.handleMessage(text)
                    }
                @unknown default:
                    break
                }
                
                // Continue receiving
                self?.receiveMessage()
                
            case .failure(let error):
                print("[RealtimeForecastWebSocket] Error: \(error)")
                self?.disconnect()
            }
        }
    }
    
    /// Handle incoming WebSocket message
    private func handleMessage(_ text: String) {
        guard let data = text.data(using: .utf8) else { return }
        
        do {
            let decoder = JSONDecoder()
            let update = try decoder.decode(RealtimeForecastUpdate.self, from: data)
            
            print("[RealtimeForecastWebSocket] Received: \(update.type)")
            
            // Handle different message types
            switch update.type {
            case "connection_confirmed":
                print("[RealtimeForecastWebSocket] \(update.message ?? "Connected")")
                
            case "new_forecast":
                if let forecastData = update.data {
                    print("[RealtimeForecastWebSocket] New forecast: $\(String(format: "%.2f", forecastData.price)) (\(forecastData.direction))")
                    onForecastUpdate?(forecastData)
                }
                
            case "price_update":
                // Handle price updates if needed
                break
                
            default:
                break
            }
            
        } catch {
            print("[RealtimeForecastWebSocket] Failed to decode message: \(error)")
        }
    }
    
    deinit {
        disconnect()
    }
}
