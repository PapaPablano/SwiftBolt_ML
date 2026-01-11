import Foundation
import Combine

struct MarketStatus: Codable {
    let isOpen: Bool
    let nextOpen: String
    let nextClose: String
    let timestamp: String
}

struct CorporateAction: Codable, Identifiable {
    var id: String { "\(symbol)-\(type)-\(exDate)" }
    let symbol: String
    let type: String
    let exDate: String
    let ratio: Double?
    let cashAmount: Double?
}

struct MarketStatusResponse: Codable {
    let market: MarketStatus
    let pendingActions: [CorporateAction]
}

@MainActor
class MarketStatusService: ObservableObject {
    @Published var isMarketOpen: Bool = false
    @Published var nextEvent: Date?
    @Published var pendingActions: [CorporateAction] = []
    
    private let supabaseURL: String
    private let supabaseKey: String
    private var timer: Timer?
    private var cancellables = Set<AnyCancellable>()
    
    init(supabaseURL: String, supabaseKey: String) {
        self.supabaseURL = supabaseURL
        self.supabaseKey = supabaseKey
        startMonitoring()
    }
    
    func startMonitoring() {
        // Check every 60 seconds
        timer = Timer.scheduledTimer(withTimeInterval: 60, repeats: true) { [weak self] _ in
            Task { @MainActor in
                await self?.fetchMarketStatus()
            }
        }
        
        Task {
            await fetchMarketStatus()
        }
    }
    
    func stopMonitoring() {
        timer?.invalidate()
        timer = nil
    }
    
    func fetchMarketStatus(for symbol: String? = nil) async {
        var urlString = "\(supabaseURL)/functions/v1/market-status"
        if let symbol = symbol {
            urlString += "?symbol=\(symbol)"
        }
        
        guard let url = URL(string: urlString) else {
            print("[MarketStatusService] Invalid URL")
            return
        }
        
        var request = URLRequest(url: url)
        request.setValue("Bearer \(supabaseKey)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            
            guard let httpResponse = response as? HTTPURLResponse,
                  httpResponse.statusCode == 200 else {
                print("[MarketStatusService] HTTP error: \((response as? HTTPURLResponse)?.statusCode ?? 0)")
                return
            }
            
            let decoder = JSONDecoder()
            decoder.keyDecodingStrategy = .convertFromSnakeCase
            let statusResponse = try decoder.decode(MarketStatusResponse.self, from: data)
            
            self.isMarketOpen = statusResponse.market.isOpen
            self.pendingActions = statusResponse.pendingActions
            
            // Parse next event
            let isoFormatter = ISO8601DateFormatter()
            if statusResponse.market.isOpen {
                self.nextEvent = isoFormatter.date(from: statusResponse.market.nextClose)
            } else {
                self.nextEvent = isoFormatter.date(from: statusResponse.market.nextOpen)
            }
            
            print("[MarketStatusService] Market is \(isMarketOpen ? "OPEN" : "CLOSED"), \(pendingActions.count) pending actions")
            
        } catch {
            print("[MarketStatusService] Error fetching market status: \(error)")
        }
    }
    
    func checkPendingActions(for symbol: String) async -> [CorporateAction] {
        await fetchMarketStatus(for: symbol)
        return pendingActions.filter { $0.symbol == symbol }
    }
    
    deinit {
        timer?.invalidate()
        timer = nil
    }
}
