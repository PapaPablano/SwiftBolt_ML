import Foundation
import Combine

@MainActor
final class BacktestingViewModel: ObservableObject {
    @Published var backtestResult: BacktestResponse?
    @Published var isLoading = false
    @Published var error: String?
    
    @Published var selectedStrategy: TradingStrategy = .supertrendAI
    @Published var startDate: Date = Calendar.current.date(byAdding: .year, value: -1, to: Date()) ?? Date()
    @Published var endDate: Date = Date()
    @Published var initialCapital: Double = 10000
    @Published var strategyParams: [String: Any] = [:]
    
    private var cancellables = Set<AnyCancellable>()
    
    var symbol: String?
    var timeframe: String = "d1"
    
    // MARK: - Computed Properties
    
    var hasResults: Bool {
        backtestResult != nil
    }
    
    var formattedReturn: String {
        guard let result = backtestResult else { return "—" }
        let sign = result.totalReturn >= 0 ? "+" : ""
        return "\(sign)\(result.totalReturn * 100, specifier: "%.2f")%"
    }
    
    var returnColor: Color {
        guard let result = backtestResult else { return .gray }
        return result.totalReturn >= 0 ? .green : .red
    }
    
    // MARK: - Data Loading
    
    func runBacktest(symbol: String, timeframe: String = "d1") async {
        guard !isLoading else { return }
        
        self.symbol = symbol.uppercased()
        self.timeframe = timeframe
        isLoading = true
        error = nil
        backtestResult = nil
        
        // Format dates
        let dateFormatter = DateFormatter()
        dateFormatter.dateFormat = "yyyy-MM-dd"
        let startDateStr = dateFormatter.string(from: startDate)
        let endDateStr = dateFormatter.string(from: endDate)
        
        // Build request
        var params = strategyParams
        if params.isEmpty {
            params = selectedStrategy.defaultParams
        }
        
        let request = BacktestRequest(
            symbol: symbol,
            strategy: selectedStrategy.rawValue,
            startDate: startDateStr,
            endDate: endDateStr,
            timeframe: timeframe,
            initialCapital: initialCapital,
            params: params.isEmpty ? nil : params
        )
        
        do {
            let response = try await APIClient.shared.runBacktest(request: request)
            self.backtestResult = response
            self.isLoading = false
            
            print("[Backtesting] Backtest complete: \(response.totalReturn * 100, specifier: "%.2f")% return, \(response.metrics.totalTrades) trades")
        } catch {
            self.error = error.localizedDescription
            self.isLoading = false
            print("[Backtesting] Error running backtest: \(error)")
        }
    }
    
    func reset() {
        backtestResult = nil
        error = nil
    }
    
    // MARK: - Strategy Parameters
    
    func updateStrategyParam(key: String, value: Any) {
        strategyParams[key] = value
    }
    
    func resetStrategyParams() {
        strategyParams = selectedStrategy.defaultParams
    }
}

// MARK: - Color Extension

import SwiftUI

extension Color {
    // Already available in SwiftUI
}
