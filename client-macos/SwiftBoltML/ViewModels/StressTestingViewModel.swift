import Foundation
import Combine

@MainActor
final class StressTestingViewModel: ObservableObject {
    @Published var stressTestResult: StressTestResponse?
    @Published var isLoading = false
    @Published var error: String?
    
    @Published var positions: [String: Double] = [:]
    @Published var prices: [String: Double] = [:]
    @Published var selectedScenario: HistoricalScenario?
    @Published var customShocks: [String: Double] = [:]
    @Published var useCustomScenario: Bool = false
    @Published var varLevel: Double = 0.05
    
    private var cancellables = Set<AnyCancellable>()
    
    // MARK: - Computed Properties
    
    var hasResults: Bool {
        stressTestResult != nil
    }
    
    var portfolioValue: Double {
        positions.reduce(0.0) { total, pair in
            total + (pair.value * (prices[pair.key] ?? 0))
        }
    }
    
    var formattedImpact: String {
        guard let result = stressTestResult else { return "—" }
        let sign = result.portfolio.change >= 0 ? "+" : ""
        return "\(sign)\(result.portfolio.changePercent * 100, specifier: "%.2f")%"
    }
    
    var impactColor: Color {
        guard let result = stressTestResult else { return .gray }
        return result.portfolio.change >= 0 ? .green : .red
    }
    
    var severity: StressSeverity? {
        guard let result = stressTestResult else { return nil }
        return StressSeverity(rawValue: result.risk.severity)
    }
    
    // MARK: - Data Loading
    
    func runStressTest() async {
        guard !isLoading, !positions.isEmpty else { return }
        
        isLoading = true
        error = nil
        stressTestResult = nil
        
        let request = StressTestRequest(
            positions: positions,
            prices: prices,
            scenario: useCustomScenario ? nil : selectedScenario,
            customShocks: useCustomScenario ? customShocks : nil,
            varLevel: varLevel
        )
        
        do {
            let response = try await APIClient.shared.runStressTest(request: request)
            self.stressTestResult = response
            self.isLoading = false
            
            print("[StressTesting] Complete: \(response.portfolio.changePercent * 100, specifier: "%.2f")% impact, \(response.risk.severity) severity")
        } catch {
            self.error = error.localizedDescription
            self.isLoading = false
            print("[StressTesting] Error: \(error)")
        }
    }
    
    func reset() {
        stressTestResult = nil
        error = nil
    }
    
    func addPosition(symbol: String, quantity: Double, price: Double) {
        let upper = symbol.uppercased().trimmingCharacters(in: .whitespaces)
        if !upper.isEmpty {
            positions[upper] = quantity
            prices[upper] = price
        }
    }
    
    func removePosition(_ symbol: String) {
        positions.removeValue(forKey: symbol)
        prices.removeValue(forKey: symbol)
    }
    
    func addCustomShock(symbol: String, shockPercent: Double) {
        let upper = symbol.uppercased().trimmingCharacters(in: .whitespaces)
        if !upper.isEmpty {
            customShocks[upper] = shockPercent
        }
    }
    
    func removeCustomShock(_ symbol: String) {
        customShocks.removeValue(forKey: symbol)
    }
}

// MARK: - Color Extension

import SwiftUI

extension Color {
    // Already available in SwiftUI
}
