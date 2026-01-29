import Foundation
import Combine

// MARK: - Filter Options

enum StrategyStatusFilter: String, CaseIterable {
    case all = "All"
    case open = "Open"
    case closed = "Closed"
    case expired = "Expired"

    var apiValue: StrategyStatus? {
        switch self {
        case .all: return nil
        case .open: return .open
        case .closed: return .closed
        case .expired: return .expired
        }
    }
}

enum StrategySortOption: String, CaseIterable {
    case newest = "Newest"
    case oldest = "Oldest"
    case plHighToLow = "P&L (High)"
    case plLowToHigh = "P&L (Low)"
    case dteAsc = "DTE (Low)"
    case dteDesc = "DTE (High)"
    case name = "Name"
}

/// Live Greeks from options-quotes (per leg and combined).
struct LiveGreeks {
    let combinedDelta: Double
    let combinedGamma: Double
    let combinedTheta: Double
    let combinedVega: Double
    let combinedRho: Double
    let perLeg: [String: LegLiveGreeks]
}

struct LegLiveGreeks {
    let delta: Double
    let gamma: Double
    let theta: Double
    let vega: Double
    let rho: Double
}

// MARK: - ViewModel

@MainActor
class MultiLegViewModel: ObservableObject {
    // MARK: - Published Properties

    @Published var strategies: [MultiLegStrategy] = []
    @Published var selectedStrategy: MultiLegStrategy?
    @Published var strategyDetail: StrategyDetailResponse?
    @Published var templates: [StrategyTemplate] = []

    // Loading states
    @Published var isLoading = false
    @Published var isLoadingDetail = false
    @Published var isCreating = false
    @Published var isClosing = false
    @Published var errorMessage: String?

    // Filters
    @Published var statusFilter: StrategyStatusFilter = .open
    @Published var strategyTypeFilter: StrategyType?
    @Published var symbolFilter: String?
    @Published var sortOption: StrategySortOption = .newest
    @Published var searchText: String = ""

    // Pagination
    @Published var hasMore = false
    @Published var totalCount = 0
    private var currentOffset = 0
    private let pageSize = 50

    // Auto-refresh
    @Published var lastRefresh: Date?
    @Published var isAutoRefreshing = false
    private var refreshTimer: AnyCancellable?

    /// Live Greeks from options-quotes (keyed by strategy id); used when DB Greeks are missing.
    @Published var liveGreeksByStrategyId: [String: LiveGreeks] = [:]

    private var cancellables = Set<AnyCancellable>()

    // MARK: - Computed Properties

    var filteredStrategies: [MultiLegStrategy] {
        var result = strategies

        // Apply search filter
        if !searchText.isEmpty {
            let searchLower = searchText.lowercased()
            result = result.filter { strategy in
                strategy.name.lowercased().contains(searchLower) ||
                strategy.underlyingTicker.lowercased().contains(searchLower) ||
                strategy.strategyType.displayName.lowercased().contains(searchLower)
            }
        }

        // Apply strategy type filter
        if let typeFilter = strategyTypeFilter {
            result = result.filter { $0.strategyType == typeFilter }
        }

        // Apply symbol filter
        if let symbol = symbolFilter, !symbol.isEmpty {
            result = result.filter { $0.underlyingTicker.uppercased() == symbol.uppercased() }
        }

        // Apply sorting
        switch sortOption {
        case .newest:
            result.sort { ($0.createdAtDate ?? .distantPast) > ($1.createdAtDate ?? .distantPast) }
        case .oldest:
            result.sort { ($0.createdAtDate ?? .distantPast) < ($1.createdAtDate ?? .distantPast) }
        case .plHighToLow:
            result.sort { ($0.totalPL ?? 0) > ($1.totalPL ?? 0) }
        case .plLowToHigh:
            result.sort { ($0.totalPL ?? 0) < ($1.totalPL ?? 0) }
        case .dteAsc:
            result.sort { ($0.minDTE ?? Int.max) < ($1.minDTE ?? Int.max) }
        case .dteDesc:
            result.sort { ($0.minDTE ?? 0) > ($1.minDTE ?? 0) }
        case .name:
            result.sort { $0.name.lowercased() < $1.name.lowercased() }
        }

        return result
    }

    var openStrategiesCount: Int {
        strategies.filter { $0.status == .open }.count
    }

    var totalPL: Double {
        strategies.compactMap { $0.totalPL }.reduce(0, +)
    }

    var totalRealizedPL: Double {
        strategies.compactMap { $0.realizedPL }.reduce(0, +)
    }

    var activeAlertCount: Int {
        strategies.reduce(0) { $0 + $1.activeAlertCount }
    }

    var criticalAlertCount: Int {
        strategies.reduce(0) { $0 + $1.criticalAlertCount }
    }

    // MARK: - Initialization

    init() {
        setupFilterObservers()
    }

    private func setupFilterObservers() {
        // Debounce search text changes
        $searchText
            .debounce(for: .milliseconds(300), scheduler: RunLoop.main)
            .removeDuplicates()
            .sink { [weak self] _ in
                // Defer to next run loop to avoid "Publishing changes from within view updates"
                DispatchQueue.main.async {
                    self?.objectWillChange.send()
                }
            }
            .store(in: &cancellables)

        // Reload when status filter changes
        $statusFilter
            .dropFirst()
            .sink { [weak self] _ in
                Task { await self?.loadStrategies(reset: true) }
            }
            .store(in: &cancellables)
    }

    // MARK: - Data Loading

    func loadStrategies(reset: Bool = false) async {
        if reset {
            currentOffset = 0
            strategies = []
        }

        guard !isLoading else { return }
        isLoading = true
        errorMessage = nil

        do {
            let response = try await APIClient.shared.listMultiLegStrategies(
                status: statusFilter.apiValue,
                underlyingSymbolId: nil,
                strategyType: strategyTypeFilter,
                limit: pageSize,
                offset: currentOffset
            )

            if reset {
                strategies = response.strategies
            } else {
                strategies.append(contentsOf: response.strategies)
            }

            totalCount = response.total
            hasMore = response.hasMore
            currentOffset += response.strategies.count
            lastRefresh = Date()

            print("[MultiLeg] Loaded \(response.strategies.count) strategies, total: \(response.total)")
        } catch {
            errorMessage = error.localizedDescription
            print("[MultiLeg] Error loading strategies: \(error)")
        }

        isLoading = false
    }

    func loadMore() async {
        guard hasMore && !isLoading else { return }
        await loadStrategies(reset: false)
    }

    func refresh() async {
        await loadStrategies(reset: true)
    }

    // MARK: - Strategy Detail
    
    private var detailLoadTask: Task<Void, Never>?
    private var currentLoadingStrategyId: String?

    func loadStrategyDetail(strategyId: String) async {
        // Prevent duplicate calls for the same strategy
        guard currentLoadingStrategyId != strategyId else {
            print("[MultiLeg] Already loading detail for strategy: \(strategyId), skipping duplicate call")
            return
        }
        
        // Cancel any existing load task
        detailLoadTask?.cancel()
        
        currentLoadingStrategyId = strategyId
        isLoadingDetail = true
        errorMessage = nil

        detailLoadTask = Task {
            do {
                let response = try await APIClient.shared.getMultiLegStrategyDetail(strategyId: strategyId)
                
                // Check if task was cancelled
                guard !Task.isCancelled else { return }
                
                strategyDetail = response

                // Fetch live Greeks when DB Greeks are missing (options-quotes)
                await refreshLiveGreeks(strategy: response.strategy, legs: response.legs)

                // Update the strategy in the list if it exists
                if let index = strategies.firstIndex(where: { $0.id == strategyId }) {
                    var updated = response.strategy
                    updated.legs = response.legs
                    updated.alerts = response.alerts
                    strategies[index] = updated
                }

                print("[MultiLeg] Loaded detail for strategy: \(response.strategy.name)")
            } catch is CancellationError {
                // Swallow cancellation errors
            } catch {
                errorMessage = error.localizedDescription
                print("[MultiLeg] Error loading strategy detail: \(error)")
            }
            
            currentLoadingStrategyId = nil
            isLoadingDetail = false
        }
        
        await detailLoadTask?.value
    }

    func selectStrategy(_ strategy: MultiLegStrategy) {
        selectedStrategy = strategy
        Task {
            await loadStrategyDetail(strategyId: strategy.id)
        }
    }

    func clearSelection() {
        detailLoadTask?.cancel()
        detailLoadTask = nil
        currentLoadingStrategyId = nil
        selectedStrategy = nil
        strategyDetail = nil
        liveGreeksByStrategyId.removeAll()
    }

    /// Fetch options quotes for open legs and compute live Greeks (combined + per leg).
    func refreshLiveGreeks(strategy: MultiLegStrategy, legs: [OptionsLeg]) async {
        let openLegs = legs.filter { !$0.isClosed }
        guard !openLegs.isEmpty else { return }
        let symbol = strategy.underlyingTicker
        let contracts = openLegs.map { $0.occSymbol(underlying: symbol) }.filter { !$0.isEmpty }
        guard contracts.count == openLegs.count else { return }
        do {
            let response = try await APIClient.shared.fetchOptionsQuotes(symbol: symbol, contracts: contracts)
            let normalizedKey: (String) -> String = { $0.uppercased().replacingOccurrences(of: " ", with: "") }
            let quoteBySymbol = Dictionary(uniqueKeysWithValues: response.quotes.map { (normalizedKey($0.contractSymbol), $0) })
            var perLeg: [String: LegLiveGreeks] = [:]
            var combinedDelta: Double = 0, combinedGamma: Double = 0, combinedTheta: Double = 0, combinedVega: Double = 0, combinedRho: Double = 0
            var hasAnyGreek = false
            for leg in openLegs {
                let occ = leg.occSymbol(underlying: symbol)
                guard let quote = quoteBySymbol[occ.uppercased().replacingOccurrences(of: " ", with: "")] else { continue }
                let d = quote.delta ?? 0, g = quote.gamma ?? 0, t = quote.theta ?? 0, v = quote.vega ?? 0, r = quote.rho ?? 0
                if quote.delta != nil || quote.gamma != nil || quote.theta != nil || quote.vega != nil { hasAnyGreek = true }
                let sign = leg.positionType == .long ? 1.0 : -1.0
                let mult = Double(leg.contracts) * 100.0
                perLeg[leg.id] = LegLiveGreeks(delta: d * sign, gamma: g * sign, theta: t * sign, vega: v * sign, rho: r * sign)
                combinedDelta += d * sign * mult
                combinedGamma += g * sign * mult
                combinedTheta += t * sign * mult
                combinedVega += v * sign * mult
                combinedRho += r * sign * mult
            }
            if !perLeg.isEmpty && hasAnyGreek {
                liveGreeksByStrategyId[strategy.id] = LiveGreeks(
                    combinedDelta: combinedDelta,
                    combinedGamma: combinedGamma,
                    combinedTheta: combinedTheta,
                    combinedVega: combinedVega,
                    combinedRho: combinedRho,
                    perLeg: perLeg
                )
            }
        } catch {
            // Non-fatal: keep DB Greeks or N/A
        }
    }

    // MARK: - Create Strategy

    func createStrategy(_ request: CreateStrategyRequest) async -> MultiLegStrategy? {
        isCreating = true
        errorMessage = nil

        do {
            let response = try await APIClient.shared.createMultiLegStrategy(request)

            // Add to the list
            var newStrategy = response.strategy
            newStrategy.legs = response.legs
            strategies.insert(newStrategy, at: 0)
            totalCount += 1

            print("[MultiLeg] Created strategy: \(response.strategy.name)")
            isCreating = false
            return newStrategy
        } catch {
            errorMessage = error.localizedDescription
            print("[MultiLeg] Error creating strategy: \(error)")
            isCreating = false
            return nil
        }
    }

    // MARK: - Update Strategy

    func updateStrategy(strategyId: String, update: UpdateStrategyRequest) async -> Bool {
        errorMessage = nil

        do {
            let updated = try await APIClient.shared.updateMultiLegStrategy(strategyId: strategyId, update: update)

            // Update in list
            if let index = strategies.firstIndex(where: { $0.id == strategyId }) {
                strategies[index] = updated
            }

            // Update selected if it's the same
            if selectedStrategy?.id == strategyId {
                selectedStrategy = updated
            }

            print("[MultiLeg] Updated strategy: \(updated.name)")
            return true
        } catch {
            errorMessage = error.localizedDescription
            print("[MultiLeg] Error updating strategy: \(error)")
            return false
        }
    }

    // MARK: - Close Operations

    func closeLeg(strategyId: String, legId: String, exitPrice: Double, notes: String? = nil) async -> Bool {
        isClosing = true
        errorMessage = nil

        do {
            let request = CloseLegRequest(legId: legId, exitPrice: exitPrice, notes: notes)
            let response = try await APIClient.shared.closeMultiLegLeg(strategyId: strategyId, request: request)

            // Update strategy in list
            if let index = strategies.firstIndex(where: { $0.id == strategyId }) {
                strategies[index] = response.strategy
            }

            // Update selected strategy
            if selectedStrategy?.id == strategyId {
                selectedStrategy = response.strategy
            }

            // Refresh detail to get updated legs
            await loadStrategyDetail(strategyId: strategyId)

            print("[MultiLeg] Closed leg: \(legId)")
            isClosing = false
            return true
        } catch {
            errorMessage = error.localizedDescription
            print("[MultiLeg] Error closing leg: \(error)")
            isClosing = false
            return false
        }
    }

    func closeStrategy(strategyId: String, exitPrices: [(legId: String, exitPrice: Double)], notes: String? = nil) async -> Bool {
        isClosing = true
        errorMessage = nil

        do {
            let request = CloseStrategyRequest(
                strategyId: strategyId,
                exitPrices: exitPrices.map { CloseStrategyRequest.LegExitPrice(legId: $0.legId, exitPrice: $0.exitPrice) },
                notes: notes
            )
            let response = try await APIClient.shared.closeMultiLegStrategy(request)

            // Update strategy in list
            if let index = strategies.firstIndex(where: { $0.id == strategyId }) {
                var updated = response.strategy
                updated.legs = response.legs
                strategies[index] = updated
            }

            // Update selected strategy
            if selectedStrategy?.id == strategyId {
                var updated = response.strategy
                updated.legs = response.legs
                selectedStrategy = updated
            }

            print("[MultiLeg] Closed strategy: \(strategyId)")
            isClosing = false
            return true
        } catch {
            errorMessage = error.localizedDescription
            print("[MultiLeg] Error closing strategy: \(error)")
            isClosing = false
            return false
        }
    }

    // MARK: - Delete Strategy

    @Published var isDeleting = false

    func deleteStrategy(strategyId: String) async -> Bool {
        isDeleting = true
        errorMessage = nil

        do {
            let response = try await APIClient.shared.deleteMultiLegStrategy(strategyId: strategyId)

            // Remove from list
            strategies.removeAll { $0.id == strategyId }
            totalCount -= 1

            // Clear selection if it was the deleted strategy
            if selectedStrategy?.id == strategyId {
                selectedStrategy = nil
                strategyDetail = nil
            }

            print("[MultiLeg] Deleted strategy: \(response.deletedName) (\(response.deletedId))")
            isDeleting = false
            return true
        } catch {
            errorMessage = error.localizedDescription
            print("[MultiLeg] Error deleting strategy: \(error)")
            isDeleting = false
            return false
        }
    }

    // MARK: - Templates

    func loadTemplates() async {
        do {
            let response = try await APIClient.shared.fetchStrategyTemplates()
            templates = response.templates
            print("[MultiLeg] Loaded \(templates.count) templates")
        } catch {
            print("[MultiLeg] Error loading templates: \(error)")
        }
    }

    // MARK: - Auto Refresh

    func startAutoRefresh(interval: TimeInterval = 60) {
        stopAutoRefresh()
        isAutoRefreshing = true

        refreshTimer = Timer.publish(every: interval, on: .main, in: .common)
            .autoconnect()
            .sink { [weak self] _ in
                Task { await self?.refresh() }
            }
    }

    func stopAutoRefresh() {
        refreshTimer?.cancel()
        refreshTimer = nil
        isAutoRefreshing = false
    }

    // MARK: - Helpers

    func strategyForId(_ id: String) -> MultiLegStrategy? {
        strategies.first { $0.id == id }
    }

    func strategiesForSymbol(_ ticker: String) -> [MultiLegStrategy] {
        strategies.filter { $0.underlyingTicker.uppercased() == ticker.uppercased() }
    }

    func openStrategiesForSymbol(_ ticker: String) -> [MultiLegStrategy] {
        strategiesForSymbol(ticker).filter { $0.status == .open }
    }

    func clearFilters() {
        statusFilter = .open
        strategyTypeFilter = nil
        symbolFilter = nil
        searchText = ""
        sortOption = .newest
    }
}

// MARK: - Strategy Creation Helper

struct StrategyCreationHelper {
    static func buildRequest(
        name: String,
        strategyType: StrategyType,
        symbolId: String,
        ticker: String,
        legs: [LegCreationInput],
        forecastAlignment: ForecastAlignment? = nil,
        notes: String? = nil,
        tags: [String: String]? = nil
    ) -> CreateStrategyRequest {
        let legInputs = legs.enumerated().map { index, leg in
            CreateLegInput(
                legNumber: index + 1,
                legRole: leg.role,
                positionType: leg.position,
                optionType: leg.optionType,
                strike: leg.strike,
                expiry: leg.expiry,
                entryPrice: leg.entryPrice,
                contracts: leg.contracts,
                delta: leg.delta,
                gamma: leg.gamma,
                theta: leg.theta,
                vega: leg.vega,
                rho: leg.rho,
                impliedVol: leg.impliedVol
            )
        }

        return CreateStrategyRequest(
            name: name,
            strategyType: strategyType,
            underlyingSymbolId: symbolId,
            underlyingTicker: ticker,
            legs: legInputs,
            forecastId: nil,
            forecastAlignment: forecastAlignment,
            notes: notes,
            tags: tags
        )
    }
}

struct LegCreationInput {
    let position: PositionType
    let optionType: MultiLegOptionType
    let strike: Double
    let expiry: String
    let entryPrice: Double
    let contracts: Int
    let role: LegRole?
    let delta: Double?
    let gamma: Double?
    let theta: Double?
    let vega: Double?
    let rho: Double?
    let impliedVol: Double?

    init(
        position: PositionType,
        optionType: MultiLegOptionType,
        strike: Double,
        expiry: String,
        entryPrice: Double,
        contracts: Int = 1,
        role: LegRole? = nil,
        delta: Double? = nil,
        gamma: Double? = nil,
        theta: Double? = nil,
        vega: Double? = nil,
        rho: Double? = nil,
        impliedVol: Double? = nil
    ) {
        self.position = position
        self.optionType = optionType
        self.strike = strike
        self.expiry = expiry
        self.entryPrice = entryPrice
        self.contracts = contracts
        self.role = role
        self.delta = delta
        self.gamma = gamma
        self.theta = theta
        self.vega = vega
        self.rho = rho
        self.impliedVol = impliedVol
    }
}
