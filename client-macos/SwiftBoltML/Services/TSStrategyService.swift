import Foundation

@MainActor
class TSStrategyService: ObservableObject {
    static let shared = TSStrategyService()
    
    @Published var strategies: [TSStrategyModel] = []
    @Published var indicators: [TSIndicator] = []
    @Published var isLoading = false
    @Published var error: String?
    @Published var isAuthenticated = false
    
    private var baseURL: String {
        let supabaseURL = Config.shared.supabaseURL.absoluteString
        return "\(supabaseURL)/functions/v1/ts-strategies"
    }
    
    private var authToken: String? {
        KeychainService.load("SUPABASE_AUTH_TOKEN")
    }
    
    func checkAuthStatus() async {
        guard let token = authToken else {
            isAuthenticated = false
            return
        }
        
        var request = URLRequest(url: URL(string: "\(baseURL)/auth")!)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        
        let body = ["action": "status"]
        request.httpBody = try? JSONEncoder().encode(body)
        
        do {
            let (data, _) = try await URLSession.shared.data(for: request)
            let status = try JSONDecoder().decode(TSCredentialsStatus.self, from: data)
            isAuthenticated = status.connected && !status.expired
        } catch {
            isAuthenticated = false
        }
    }
    
    func fetchStrategies() async {
        isLoading = true
        error = nil
        
        guard let token = authToken else {
            error = "Not authenticated"
            isLoading = false
            return
        }
        
        var request = URLRequest(url: URL(string: baseURL)!)
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        
        do {
            let (data, _) = try await URLSession.shared.data(for: request)
            strategies = try JSONDecoder().decode([TSStrategyModel].self, from: data)
        } catch {
            self.error = error.localizedDescription
        }
        
        isLoading = false
    }
    
    func fetchIndicators() async {
        indicators = [
            TSIndicator(id: "1", name: "RSI", description: "Relative Strength Index", parameters: ["period": .int(14), "overbought": .int(70), "oversold": .int(30)]),
            TSIndicator(id: "2", name: "MACD", description: "Moving Average Convergence Divergence", parameters: ["fast_period": .int(12), "slow_period": .int(26), "signal_period": .int(9)]),
            TSIndicator(id: "3", name: "SMA", description: "Simple Moving Average", parameters: ["period": .int(20)]),
            TSIndicator(id: "4", name: "EMA", description: "Exponential Moving Average", parameters: ["period": .int(20)]),
            TSIndicator(id: "5", name: "BB", description: "Bollinger Bands", parameters: ["period": .int(20), "std_dev": .int(2)]),
            TSIndicator(id: "6", name: "ATR", description: "Average True Range", parameters: ["period": .int(14)]),
            TSIndicator(id: "7", name: "STOCH", description: "Stochastic Oscillator", parameters: ["k_period": .int(14), "d_period": .int(3)]),
            TSIndicator(id: "8", name: "VWAP", description: "Volume Weighted Average Price", parameters: nil)
        ]
    }
    
    func createStrategy(name: String, description: String?) async -> TSStrategyModel? {
        guard let token = authToken else { return nil }
        
        var request = URLRequest(url: URL(string: baseURL)!)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        
        let body: [String: Any] = [
            "name": name,
            "description": description ?? ""
        ]
        
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        
        do {
            let (data, _) = try await URLSession.shared.data(for: request)
            let strategy = try JSONDecoder().decode(TSStrategyModel.self, from: data)
            strategies.insert(strategy, at: 0)
            return strategy
        } catch {
            self.error = error.localizedDescription
            return nil
        }
    }
    
    func updateStrategy(_ strategy: TSStrategyModel) async -> Bool {
        guard let token = authToken else { return false }
        
        var request = URLRequest(url: URL(string: "\(baseURL)/\(strategy.id)")!)
        request.httpMethod = "PUT"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        
        let body: [String: Any] = [
            "name": strategy.name,
            "description": strategy.description ?? "",
            "enabled": strategy.enabled
        ]
        
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        
        do {
            _ = try await URLSession.shared.data(for: request)
            if let index = strategies.firstIndex(where: { $0.id == strategy.id }) {
                strategies[index] = strategy
            }
            return true
        } catch {
            self.error = error.localizedDescription
            return false
        }
    }
    
    func deleteStrategy(_ id: String) async -> Bool {
        guard let token = authToken else { return false }
        
        var request = URLRequest(url: URL(string: "\(baseURL)/\(id)")!)
        request.httpMethod = "DELETE"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        
        do {
            _ = try await URLSession.shared.data(for: request)
            strategies.removeAll { $0.id == id }
            return true
        } catch {
            self.error = error.localizedDescription
            return false
        }
    }
    
    func executeStrategy(_ strategyId: String, symbol: String, useSim: Bool = true) async -> TSExecutionResult? {
        guard let token = authToken else { return nil }
        
        var request = URLRequest(url: URL(string: "\(baseURL)/execute")!)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        
        let body: [String: Any] = [
            "strategy_id": strategyId,
            "symbol": symbol,
            "use_sim": useSim
        ]
        
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        
        do {
            let (data, _) = try await URLSession.shared.data(for: request)
            return try JSONDecoder().decode(TSExecutionResult.self, from: data)
        } catch {
            self.error = error.localizedDescription
            return nil
        }
    }
    
    func addCondition(to strategyId: String, indicatorId: String, threshold: Double, conditionOperator: String, logicalOperator: String) async -> Bool {
        return true
    }
    
    func addAction(to strategyId: String, actionType: String, parameters: [String: Any]) async -> Bool {
        return true
    }
}
