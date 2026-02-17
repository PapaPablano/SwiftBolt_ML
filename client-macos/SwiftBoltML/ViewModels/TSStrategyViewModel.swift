import Foundation
import SwiftUI

@MainActor
class TSStrategyViewModel: ObservableObject {
    @Published var strategies: [TSStrategy] = []
    @Published var indicators: [TSIndicator] = []
    @Published var isLoading = false
    @Published var error: String?
    @Published var isAuthenticated = false
    
    private let strategyService = TSStrategyService.shared
    private let authService = TradeStationAuthService.shared
    
    init() {
        Task {
            await fetchStrategies()
            await fetchIndicators()
            await checkAuthStatus()
        }
    }
    
    func startOAuth() {
        authService.startOAuthFlow()
        
        // Observe auth changes
        Task {
            try? await Task.sleep(nanoseconds: 2_000_000_000)
            await checkAuthStatus()
        }
    }
    
    func checkAuthStatus() async {
        await strategyService.checkAuthStatus()
        isAuthenticated = strategyService.isAuthenticated
    }
    
    func fetchStrategies() async {
        isLoading = true
        await strategyService.fetchStrategies()
        strategies = strategyService.strategies
        error = strategyService.error
        isLoading = false
    }
    
    func fetchIndicators() async {
        await strategyService.fetchIndicators()
        indicators = strategyService.indicators
    }
    
    func createStrategy(name: String, description: String?) async -> TSStrategy? {
        let strategy = await strategyService.createStrategy(name: name, description: description)
        if strategy != nil {
            await fetchStrategies()
        }
        return strategy
    }
    
    func updateStrategy(_ strategy: TSStrategy) async {
        let success = await strategyService.updateStrategy(strategy)
        if success {
            await fetchStrategies()
        }
    }
    
    func deleteStrategy(_ id: String) async {
        let success = await strategyService.deleteStrategy(id)
        if success {
            strategies.removeAll { $0.id == id }
        }
    }
    
    func toggleEnabled(_ strategy: TSStrategy) {
        var updated = strategy
        updated.enabled = !strategy.enabled
        Task {
            await updateStrategy(updated)
        }
    }
    
    func executeStrategy(_ strategyId: String, symbol: String) async -> TSExecutionResult? {
        isLoading = true
        let result = await strategyService.executeStrategy(strategyId, symbol: symbol)
        error = strategyService.error
        isLoading = false
        return result
    }
}
