import Foundation
import SwiftUI

@MainActor
class TSStrategyViewModel: ObservableObject {
    @Published var strategies: [TSStrategyModel] = []
    @Published var indicators: [TSIndicator] = []
    @Published var isLoading = false
    @Published var error: String?
    @Published var isAuthenticated = false
    
    private let strategyService = TSStrategyService.shared
    private let authService = TradeStationAuthService.shared
    
    init() {
        Task {
            // Force simulation mode - always authenticated
            self.isAuthenticated = true
            await fetchStrategies()
            await fetchIndicators()
        }
    }
    
    func isSimulationMode() -> Bool {
        // Check for simulation environment - you might want to use a more robust method
        // This could be reading from an environment variable or config file
        let isSim = ProcessInfo.processInfo.environment["SIMULATION_MODE"] == "true"
        print("[TSStrategy] isSimulationMode check: \(isSim)")
        return isSim
    }
    
    func startOAuth() {
        // In simulation mode, skip OAuth completely
        if isSimulationMode() {
            self.isAuthenticated = true
            return
        }
        
        authService.startOAuthFlow { [weak self] success in
            Task { @MainActor in
                // Update auth status after completion
                await self?.checkAuthStatus()
            }
        }
    }
    
    func checkAuthStatus() async {
        // In simulation mode, we're always authenticated
        if isSimulationMode() {
            self.isAuthenticated = true
            return
        }
        
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
    
    func createStrategy(name: String, description: String?) async -> TSStrategyModel? {
        print("[TSStrategy] createStrategy called: \(name), simulationMode: \(isSimulationMode())")
        
        // For simulation mode, allow creation without auth check
        if isSimulationMode() {
            // Mock the creation in simulation mode
            let strategy = TSStrategyModel(id: UUID().uuidString, name: name, description: description, enabled: true, createdAt: Date(), updatedAt: Date(), conditions: [], actions: [])
            strategies.append(strategy)
            print("[TSStrategy] Created mock strategy: \(strategy.name), total: \(strategies.count)")
            return strategy
        }
        
        let strategy = await strategyService.createStrategy(name: name, description: description)
        if strategy != nil {
            await fetchStrategies()
        }
        return strategy
    }
    
    func updateStrategy(_ strategy: TSStrategyModel) async {
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
    
    func toggleEnabled(_ strategy: TSStrategyModel) {
        var updated = strategy
        updated.enabled = !strategy.enabled
        Task {
            await updateStrategy(updated)
        }
    }
    
    func executeStrategy(_ strategyId: String, symbol: String) async -> TSExecutionResult? {
        isLoading = true
        let result = await strategyService.executeStrategy(strategyId, symbol: symbol, useSim: isSimulationMode())
        error = strategyService.error
        isLoading = false
        return result
    }
}
