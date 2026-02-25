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
    
    /// Incremented when a new load starts; used to ignore completion from stale (superseded) loads.
    private var loadGeneration: Int = 0
    
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
    
    func loadIndicators(symbol: String, timeframe: String = "d1", forceRefresh: Bool = false) async {
        let requestedSymbol = symbol.uppercased()
        // Only skip when already loading the same symbol+timeframe (e.g. duplicate call from .task + .onAppear). Allow new load when timeframe/symbol differs so favorites list updates when chart timeframe changes.
        if isLoading, self.symbol == requestedSymbol, self.timeframe == timeframe {
            return
        }
        
        loadGeneration += 1
        let myGeneration = loadGeneration
        self.symbol = requestedSymbol
        self.timeframe = timeframe
        isLoading = true
        error = nil
        
        do {
            // Use request deduplication to prevent duplicate calls (unless forcing refresh)
            let deduplicationKey = forceRefresh ? "" : "technical_indicators_\(symbol.uppercased())_\(timeframe)"
            let response = try await RequestDeduplicator.shared.execute(key: deduplicationKey) {
                // Use retry logic with exponential backoff
                try await withRetry(policy: .default) {
                    try await APIClient.shared.fetchTechnicalIndicators(
                        symbol: symbol,
                        timeframe: timeframe,
                        forceRefresh: forceRefresh
                    )
                }
            }
            
            guard myGeneration == loadGeneration else { return }
            let result = response
            DispatchQueue.main.async { [weak self] in
                guard let self, myGeneration == self.loadGeneration else { return }
                self.indicators = result
                self.lastUpdated = Date()
                self.isLoading = false
                print("[TechnicalIndicators] Loaded \(result.indicators.count) indicators for \(symbol)/\(timeframe)")
            }
        } catch {
            guard myGeneration == loadGeneration else { return }
            let errMsg = error.localizedDescription
            DispatchQueue.main.async { [weak self] in
                guard let self, myGeneration == self.loadGeneration else { return }
                self.error = errMsg
                self.isLoading = false
                print("[TechnicalIndicators] Error loading indicators after retries: \(error)")
            }
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
                guard let self = self else { return }
                guard let symbol = self.symbol, !self.isLoading else { return }
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
