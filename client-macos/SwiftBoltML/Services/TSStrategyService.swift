import Foundation

@MainActor
class TSStrategyService: ObservableObject {
    static let shared = TSStrategyService()
    
    @Published var strategies: [TSStrategy] = []
    @Published var indicators: [TSIndicator] = []
    @Published var isLoading = false
    @Published var error: String?
    @Published var isAuthenticated = false
    
    private let baseURL: String
    private let supabaseURL: String
    
    init() {
        self.supabaseURL = Config.shared.supabaseURL
        self.baseURL = "\(supabaseURL)/functions/v1/ts-strategies"
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
            strategies = try JSONDecoder().decode([TSStrategy].self, from: data)
        } catch {
            self.error = error.localizedDescription
        }
        
        isLoading = false
    }
    
    func fetchIndicators() async {
        // Indicators are predefined - load from local or fetch
        indicators = [
            TSIndicator(id: "1", name: "RSI", description: "Relative Strength Index", parameters: ["period": AnyCodable(14), "overbought": AnyCodable(70), "oversold": AnyCodable(30)]),
            TSIndicator(id: "2", name: "MACD", description: "Moving Average Convergence Divergence", parameters: ["fast_period": AnyCodable(12), "slow_period": AnyCodable(26), "signal_period": AnyCodable(9)]),
            TSIndicator(id: "3", name: "SMA", description: "Simple Moving Average", parameters: ["period": AnyCodable(20)]),
            TSIndicator(id: "4", name: "EMA", description: "Exponential Moving Average", parameters: ["period": AnyCodable(20)]),
            TSIndicator(id: "5", name: "BB", description: "Bollinger Bands", parameters: ["period": AnyCodable(20), "std_dev": AnyCodable(2)]),
            TSIndicator(id: "6", name: "ATR", description: "Average True Range", parameters: ["period": AnyCodable(14)]),
            TSIndicator(id: "7", name: "STOCH", description: "Stochastic Oscillator", parameters: ["k_period": AnyCodable(14), "d_period": AnyCodable(3)]),
            TSIndicator(id: "8", name: "VWAP", description: "Volume Weighted Average Price", parameters: [:])
        ]
    }
    
    func createStrategy(name: String, description: String?) async -> TSStrategy? {
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
            let strategy = try JSONDecoder().decode(TSStrategy.self, from: data)
            strategies.insert(strategy, at: 0)
            return strategy
        } catch {
            self.error = error.localizedDescription
            return nil
        }
    }
    
    func updateStrategy(_ strategy: TSStrategy) async -> Bool {
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
        // This would need a separate endpoint or include in strategy update
        // Simplified for now
        return true
    }
    
    func addAction(to strategyId: String, actionType: String, parameters: [String: Any]) async -> Bool {
        // This would need a separate endpoint
        return true
    }
}
