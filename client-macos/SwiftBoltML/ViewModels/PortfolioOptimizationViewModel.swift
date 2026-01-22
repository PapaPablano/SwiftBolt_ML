import Foundation
import Combine

@MainActor
final class PortfolioOptimizationViewModel: ObservableObject {
    @Published var optimizationResult: PortfolioOptimizeResponse?
    @Published var isLoading = false
    @Published var error: String?
    
    @Published var symbols: [String] = []
    @Published var selectedMethod: OptimizationMethod = .maxSharpe
    @Published var timeframe: String = "d1"
    @Published var lookbackDays: Int = 252
    @Published var riskFreeRate: Double = 0.02
    @Published var targetReturn: Double = 0.10
    @Published var minWeight: Double = 0.0
    @Published var maxWeight: Double = 1.0
    
    private var cancellables = Set<AnyCancellable>()
    
    // MARK: - Computed Properties
    
    var hasResults: Bool {
        optimizationResult != nil
    }
    
    var formattedSharpeRatio: String {
        guard let result = optimizationResult else { return "—" }
        return "\(result.allocation.sharpeRatio, specifier: "%.2f")"
    }
    
    var sharpeRatioColor: Color {
        guard let result = optimizationResult else { return .gray }
        return result.allocation.sharpeRatio > 1.0 ? .green : result.allocation.sharpeRatio > 0.5 ? .orange : .red
    }
    
    // MARK: - Data Loading
    
    func optimizePortfolio() async {
        guard !isLoading, !symbols.isEmpty else { return }
        
        isLoading = true
        error = nil
        optimizationResult = nil
        
        let request = PortfolioOptimizeRequest(
            symbols: symbols.map { $0.uppercased() },
            method: selectedMethod,
            timeframe: timeframe,
            lookbackDays: lookbackDays,
            riskFreeRate: riskFreeRate,
            targetReturn: selectedMethod == .efficient ? targetReturn : nil,
            minWeight: minWeight,
            maxWeight: maxWeight
        )
        
        do {
            let response = try await APIClient.shared.optimizePortfolio(request: request)
            self.optimizationResult = response
            self.isLoading = false
            
            print("[PortfolioOptimization] Complete: \(response.allocation.sharpeRatio, specifier: "%.2f") Sharpe, \(response.allocation.expectedReturn * 100, specifier: "%.2f")% return")
        } catch {
            self.error = error.localizedDescription
            self.isLoading = false
            print("[PortfolioOptimization] Error: \(error)")
        }
    }
    
    func reset() {
        optimizationResult = nil
        error = nil
    }
    
    func addSymbol(_ symbol: String) {
        let upper = symbol.uppercased().trimmingCharacters(in: .whitespaces)
        if !upper.isEmpty && !symbols.contains(upper) {
            symbols.append(upper)
        }
    }
    
    func removeSymbol(_ symbol: String) {
        symbols.removeAll { $0 == symbol }
    }
}

// MARK: - Color Extension

import SwiftUI

extension Color {
    // Already available in SwiftUI
}
