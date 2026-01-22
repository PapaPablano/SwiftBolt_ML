import Foundation
import Combine

@MainActor
final class WalkForwardViewModel: ObservableObject {
    @Published var walkForwardResult: WalkForwardResponse?
    @Published var isLoading = false
    @Published var error: String?
    
    @Published var selectedForecaster: ForecasterType = .baseline
    @Published var selectedHorizon: ForecastHorizon = .oneDay
    @Published var timeframe: String = "d1"
    @Published var customWindows: WindowConfig?
    
    private var cancellables = Set<AnyCancellable>()
    
    var symbol: String?
    
    // MARK: - Computed Properties
    
    var hasResults: Bool {
        walkForwardResult != nil
    }
    
    var formattedAccuracy: String {
        guard let result = walkForwardResult else { return "—" }
        return "\(result.metrics.accuracy * 100, specifier: "%.2f")%"
    }
    
    var accuracyColor: Color {
        guard let result = walkForwardResult else { return .gray }
        return result.metrics.accuracy >= 0.6 ? .green : result.metrics.accuracy >= 0.5 ? .orange : .red
    }
    
    // MARK: - Window Config
    
    struct WindowConfig {
        var trainWindow: Int?
        var testWindow: Int?
        var stepSize: Int?
    }
    
    // MARK: - Data Loading
    
    func runWalkForward(symbol: String, timeframe: String = "d1") async {
        guard !isLoading else { return }
        
        self.symbol = symbol.uppercased()
        self.timeframe = timeframe
        isLoading = true
        error = nil
        walkForwardResult = nil
        
        let request = WalkForwardRequest(
            symbol: symbol,
            horizon: selectedHorizon.rawValue,
            forecaster: selectedForecaster.rawValue,
            timeframe: timeframe,
            windows: customWindows.map { config in
                WalkForwardRequest.WindowConfig(
                    trainWindow: config.trainWindow,
                    testWindow: config.testWindow,
                    stepSize: config.stepSize
                )
            }
        )
        
        do {
            let response = try await APIClient.shared.runWalkForward(request: request)
            self.walkForwardResult = response
            self.isLoading = false
            
            print("[WalkForward] Optimization complete: \(response.metrics.accuracy * 100, specifier: "%.2f")% accuracy, \(response.metrics.totalTrades) trades")
        } catch {
            self.error = error.localizedDescription
            self.isLoading = false
            print("[WalkForward] Error running optimization: \(error)")
        }
    }
    
    func reset() {
        walkForwardResult = nil
        error = nil
    }
}

// MARK: - Color Extension

import SwiftUI

extension Color {
    // Already available in SwiftUI
}
