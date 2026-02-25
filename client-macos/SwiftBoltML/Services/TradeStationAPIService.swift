import Foundation

@MainActor
class TradeStationAPIService: ObservableObject {
    static let shared = TradeStationAPIService()
    
    @Published var isLoading = false
    @Published var error: String?
    
    private let baseURL = "https://api.tradestation.com"
    private let clientId = "x3IYfpnSYevmXREQuW34LJUyeXaHBK"
    
    private init() {}
    
    func getAccountInfo() async -> TradeStationAccount? {
        guard let token = TradeStationAuthService.shared.loadTokens()?.accessToken else {
            error = "No access token available"
            return nil
        }
        
        isLoading = true
        error = nil
        
        var request = URLRequest(url: URL(string: "\(baseURL)/v1/accounts")!)
        request.httpMethod = "GET"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            
            guard let httpResponse = response as? HTTPURLResponse else {
                throw NSError(domain: "TradeStation", code: -1, userInfo: [NSLocalizedDescriptionKey: "Invalid response"])
            }
            
            if httpResponse.statusCode != 200 {
                throw NSError(domain: "TradeStation", code: httpResponse.statusCode, userInfo: [NSLocalizedDescriptionKey: "Failed to fetch account info"])
            }
            
            let account = try JSONDecoder().decode(TradeStationAccount.self, from: data)
            isLoading = false
            return account
            
        } catch {
            self.error = error.localizedDescription
            isLoading = false
            return nil
        }
    }
    
    func getMarketData(symbol: String) async -> TradeStationMarketData? {
        guard let token = TradeStationAuthService.shared.loadTokens()?.accessToken else {
            error = "No access token available"
            return nil
        }
        
        isLoading = true
        error = nil
        
        var request = URLRequest(url: URL(string: "\(baseURL)/v1/marketdata/\(symbol)")!)
        request.httpMethod = "GET"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            
            guard let httpResponse = response as? HTTPURLResponse else {
                throw NSError(domain: "TradeStation", code: -1, userInfo: [NSLocalizedDescriptionKey: "Invalid response"])
            }
            
            if httpResponse.statusCode != 200 {
                throw NSError(domain: "TradeStation", code: httpResponse.statusCode, userInfo: [NSLocalizedDescriptionKey: "Failed to fetch market data"])
            }
            
            let marketData = try JSONDecoder().decode(TradeStationMarketData.self, from: data)
            isLoading = false
            return marketData
            
        } catch {
            self.error = error.localizedDescription
            isLoading = false
            return nil
        }
    }
    
    func placeOrder(symbol: String, quantity: Double, orderType: TradeStationOrderType, side: TradeStationSide, price: Double? = nil) async -> TradeStationOrder? {
        guard let token = TradeStationAuthService.shared.loadTokens()?.accessToken else {
            error = "No access token available"
            return nil
        }
        
        isLoading = true
        error = nil
        
        var request = URLRequest(url: URL(string: "\(baseURL)/v1/orders")!)
        request.httpMethod = "POST"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body: [String: Any] = [
            "symbol": symbol,
            "quantity": quantity,
            "orderType": orderType.rawValue,
            "side": side.rawValue,
            "price": price ?? 0.0
        ]
        
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        
        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            
            guard let httpResponse = response as? HTTPURLResponse else {
                throw NSError(domain: "TradeStation", code: -1, userInfo: [NSLocalizedDescriptionKey: "Invalid response"])
            }
            
            if httpResponse.statusCode != 200 {
                throw NSError(domain: "TradeStation", code: httpResponse.statusCode, userInfo: [NSLocalizedDescriptionKey: "Failed to place order"])
            }
            
            let order = try JSONDecoder().decode(TradeStationOrder.self, from: data)
            isLoading = false
            return order
            
        } catch {
            self.error = error.localizedDescription
            isLoading = false
            return nil
        }
    }
    
    func getOrders() async -> [TradeStationOrder]? {
        guard let token = TradeStationAuthService.shared.loadTokens()?.accessToken else {
            error = "No access token available"
            return nil
        }
        
        isLoading = true
        error = nil
        
        var request = URLRequest(url: URL(string: "\(baseURL)/v1/orders")!)
        request.httpMethod = "GET"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            
            guard let httpResponse = response as? HTTPURLResponse else {
                throw NSError(domain: "TradeStation", code: -1, userInfo: [NSLocalizedDescriptionKey: "Invalid response"])
            }
            
            if httpResponse.statusCode != 200 {
                throw NSError(domain: "TradeStation", code: httpResponse.statusCode, userInfo: [NSLocalizedDescriptionKey: "Failed to fetch orders"])
            }
            
            let orders = try JSONDecoder().decode([TradeStationOrder].self, from: data)
            isLoading = false
            return orders
            
        } catch {
            self.error = error.localizedDescription
            isLoading = false
            return nil
        }
    }
}

// MARK: - Data Models
struct TradeStationAccount: Codable {
    let accountId: String
    let accountName: String
    let accountType: String
    let balance: Double
    let buyingPower: Double
    let availableFunds: Double
    
    enum CodingKeys: String, CodingKey {
        case accountId = "account_id"
        case accountName = "account_name"
        case accountType = "account_type"
        case balance
        case buyingPower = "buying_power"
        case availableFunds = "available_funds"
    }
}

struct TradeStationMarketData: Codable {
    let symbol: String
    let open: Double
    let high: Double
    let low: Double
    let close: Double
    let volume: Int
    let lastTradePrice: Double
    let timestamp: String
    
    enum CodingKeys: String, CodingKey {
        case symbol
        case open
        case high
        case low
        case close
        case volume
        case lastTradePrice = "last_trade_price"
        case timestamp
    }
}

enum TradeStationOrderType: String, Codable {
    case market = "Market"
    case limit = "Limit"
    case stop = "Stop"
    case stopLimit = "StopLimit"
}

enum TradeStationSide: String, Codable {
    case buy = "Buy"
    case sell = "Sell"
}

struct TradeStationOrder: Codable {
    let orderId: String
    let symbol: String
    let quantity: Double
    let orderType: TradeStationOrderType
    let side: TradeStationSide
    let status: String
    let price: Double
    let timestamp: String
    
    enum CodingKeys: String, CodingKey {
        case orderId = "order_id"
        case symbol
        case quantity
        case orderType = "order_type"
        case side
        case status
        case price
        case timestamp
    }
}