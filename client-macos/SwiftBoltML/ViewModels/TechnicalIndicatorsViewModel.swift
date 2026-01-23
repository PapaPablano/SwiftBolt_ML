import Foundation
import Combine

@MainActor
final class TechnicalIndicatorsViewModel: ObservableObject {
    @Published var indicators: TechnicalIndicatorsResponse?
    @Published var isLoading = false
    @Published var error: String?
    @Published var lastUpdated: Date?
    
    private var cancellables = Set<AnyCancellable>()
    private var refreshTimer: Timer?
    private let refreshInterval: TimeInterval = 300 // 5 minutes
    
    var symbol: String?
    var timeframe: String = "d1"
    
    // MARK: - Computed Properties
    
    var indicatorsByCategory: [IndicatorCategory: [IndicatorItem]] {
        indicators?.indicatorsByCategory ?? [:]
    }
    
    var allIndicators: [IndicatorItem] {
        indicators?.allIndicators ?? []
    }
    
    var hasIndicators: Bool {
        indicators != nil && !allIndicators.isEmpty
    }
    
    var priceData: TechnicalIndicatorsResponse.PriceData? {
        indicators?.price
    }
    
    var isStale: Bool {
        guard let lastUpdated = lastUpdated else { return true }
        let age = Date().timeIntervalSince(lastUpdated)
        let maxAge: TimeInterval = timeframe.isIntraday ? 300 : 3600 // 5 min or 1 hour
        return age > maxAge
    }
    
    // MARK: - Initialization
    
    init() {
        // Auto-refresh timer
        setupAutoRefresh()
    }
    
    deinit {
        refreshTimer?.invalidate()
    }
    
    // MARK: - Data Loading
    
    func loadIndicators(symbol: String, timeframe: String = "d1") async {
        guard !isLoading else { return }
        
        self.symbol = symbol.uppercased()
        self.timeframe = timeframe
        isLoading = true
        error = nil
        
        do {
            let response = try await APIClient.shared.fetchTechnicalIndicators(
                symbol: symbol,
                timeframe: timeframe
            )
            
            self.indicators = response
            self.lastUpdated = Date()
            self.isLoading = false
            
            print("[TechnicalIndicators] Loaded \(response.indicators.count) indicators for \(symbol)/\(timeframe)")
        } catch {
            self.error = error.localizedDescription
            self.isLoading = false
            print("[TechnicalIndicators] Error loading indicators: \(error)")
        }
    }
    
    func refresh() async {
        guard let symbol = symbol else { return }
        await loadIndicators(symbol: symbol, timeframe: timeframe)
    }
    
    // MARK: - Auto-Refresh
    
    private func setupAutoRefresh() {
        refreshTimer = Timer.scheduledTimer(withTimeInterval: refreshInterval, repeats: true) { [weak self] _ in
            Task { @MainActor in
                guard let self = self, let symbol = self.symbol, !self.isLoading else { return }
                // Only auto-refresh if data is stale
                if self.isStale {
                    await self.loadIndicators(symbol: symbol, timeframe: self.timeframe)
                }
            }
        }
    }
    
    func stopAutoRefresh() {
        refreshTimer?.invalidate()
        refreshTimer = nil
    }
    
    // MARK: - Helper Methods
    
    func getIndicatorValue(_ name: String) -> Double? {
        indicators?.indicators[name] ?? nil
    }
    
    func getIndicatorInterpretation(_ name: String) -> IndicatorInterpretation {
        guard let item = allIndicators.first(where: { $0.name == name }) else {
            return .neutral
        }
        return item.interpretation
    }
}

// MARK: - Timeframe Extension

extension String {
    var isIntraday: Bool {
        self.starts(with: "m") || self == "h1" || self == "h4"
    }
}
