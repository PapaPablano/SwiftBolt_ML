import Foundation
import Combine

// Signal filter options
enum SignalFilter: String, CaseIterable {
    case all = "All"
    case buy = "BUY"
    case discount = "DISCOUNT"
    case runner = "RUNNER"
    case greeks = "GREEKS"
}

// Sort options for rankings (Momentum Framework)
enum RankingSortOption: String, CaseIterable {
    case composite = "Composite"
    case momentum = "Momentum"
    case value = "Value"
    case greeks = "Greeks"
    case gaConfidence = "GA Confidence"
}

enum RankingMode: String, CaseIterable {
    case entry
    case exit
}

@MainActor
class OptionsRankerViewModel: ObservableObject {
    @Published var rankings: [OptionRank] = []
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var isGeneratingRankings = false
    @Published var rankingStatus: RankingStatus = .unknown

    @Published var selectedExpiry: String?
    @Published var selectedSide: OptionSide?
    @Published var selectedSignal: SignalFilter = .all
    @Published var sortOption: RankingSortOption = .composite
    @Published var minScore: Double = 0.0
    @Published var rankingMode: RankingMode = .entry
    @Published var liveQuotes: [String: OptionContractQuote] = [:]
    @Published var lastQuoteRefresh: Date?
    @Published var isRefreshingQuotes: Bool = false
    @Published var minPriceInput: String = ""
    @Published var maxPriceInput: String = ""

    // GA Strategy
    @Published var gaStrategy: GAStrategy?
    @Published var gaRecommendation: GARecommendation?
    @Published var useGAFilter: Bool = false {
        didSet {
            DispatchQueue.main.async { [weak self] in
                self?.applyGAFilterState()
            }
        }
    }
    @Published var isLoadingGA: Bool = false

    // Ranking freshness tracking (Fix D)
    @Published var lastRankingRefresh: Date?

    @Published var isAutoRefreshing: Bool = false
    @Published var autoRefreshInterval: TimeInterval?

    private var cancellables = Set<AnyCancellable>()
    private var quoteTimerCancellable: AnyCancellable?
    private var activeSymbol: String?
    private var gaFilterSnapshot: GAFilterSnapshot?

    private struct GAFilterSnapshot {
        let minScore: Double
        let selectedSignal: SignalFilter
        let sortOption: RankingSortOption
    }

    enum RankingStatus {
        case unknown
        case fresh        // Data < 1 hour old
        case stale        // Data > 1 hour old
        case unavailable  // No data exists
    }

    private func parsePrice(_ input: String) -> Double? {
        let trimmed = input.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return nil }
        let sanitized = trimmed
            .replacingOccurrences(of: "$", with: "")
            .replacingOccurrences(of: ",", with: "")
        return Double(sanitized)
    }

    var filteredRankings: [OptionRank] {
        let minPrice = parsePrice(minPriceInput)
        let maxPrice = parsePrice(maxPriceInput)

        return rankings
            .filter { rank in
                // Score filter using effective composite rank (0-100)
                let score = rank.effectiveCompositeRank / 100
                guard score >= minScore else { return false }

                // GA filter (if enabled and strategy exists)
                if useGAFilter, let genes = gaStrategy?.genes {
                    guard rank.passesGAFilters(genes) else { return false }
                }

                // Signal filter
                switch selectedSignal {
                case .all:
                    return true
                case .buy:
                    return rank.signalBuy == true
                case .discount:
                    return rank.signalDiscount == true
                case .runner:
                    return rank.signalRunner == true
                case .greeks:
                    return rank.signalGreeks == true
                }
            }
            .filter { rank in
                guard minPrice != nil || maxPrice != nil else {
                    return true
                }

                guard let price = rank.derivedMark ?? rank.mark ?? rank.lastPrice else {
                    return false
                }

                if let minPrice {
                    guard price >= minPrice else { return false }
                }

                if let maxPrice {
                    guard price <= maxPrice else { return false }
                }

                return true
            }
            .sorted { lhs, rhs in
                switch sortOption {
                case .composite:
                    return lhs.effectiveCompositeRank > rhs.effectiveCompositeRank
                case .momentum:
                    return (lhs.momentumScore ?? 0) > (rhs.momentumScore ?? 0)
                case .value:
                    return (lhs.valueScore ?? 0) > (rhs.valueScore ?? 0)
                case .greeks:
                    return (lhs.greeksScore ?? 0) > (rhs.greeksScore ?? 0)
                case .gaConfidence:
                    guard let genes = gaStrategy?.genes else {
                        return lhs.effectiveCompositeRank > rhs.effectiveCompositeRank
                    }
                    return lhs.gaConfidence(genes) > rhs.gaConfidence(genes)
                }
            }
    }

    var availableExpiries: [String] {
        let expiries = Set(rankings.map { $0.expiry })
        return Array(expiries).sorted()
    }

    func loadRankings(for symbol: String, allowExitFallback: Bool = true) async {
        isLoading = true
        errorMessage = nil

        do {
            let response = try await APIClient.shared.fetchOptionsRankings(
                symbol: symbol,
                expiry: selectedExpiry,
                side: selectedSide,
                mode: rankingMode.rawValue,
                limit: 100
            )

            if response.ranks.isEmpty, rankingMode == .exit, allowExitFallback {
                await MainActor.run {
                    self.rankingMode = .entry
                }
                await loadRankings(for: symbol, allowExitFallback: false)
                return
            }

            rankings = response.ranks
            updateRankingStatus()
            isLoading = false
            activeSymbol = symbol

            print("[OptionsRanker] Loaded \(rankings.count) ranked options for \(symbol)")

            await refreshQuotes(for: symbol)
        } catch {
            errorMessage = error.localizedDescription
            rankingStatus = .unavailable
            isLoading = false
            print("[OptionsRanker] Error: \(error)")
        }
    }

    func refresh(for symbol: String) async {
        await loadRankings(for: symbol)
    }

    func clearData() {
        rankings = []
        liveQuotes = [:]
        lastQuoteRefresh = nil
        errorMessage = nil
        isLoading = false
        isGeneratingRankings = false
        rankingStatus = .unknown
        gaStrategy = nil
        gaRecommendation = nil
        isLoadingGA = false
        lastRankingRefresh = nil
        activeSymbol = nil
        stopAutoRefresh()
    }

    func ensureLoaded(for symbol: String) async {
        if activeSymbol == symbol, !rankings.isEmpty {
            startAutoRefresh(for: symbol)
            return
        }

        await loadRankings(for: symbol)
        await loadGAStrategy(for: symbol)
        startAutoRefresh(for: symbol)
    }

    func triggerRankingJob(for symbol: String) async {
        isGeneratingRankings = true
        errorMessage = nil

        print("[OptionsRanker] Triggering ranking job for \(symbol)...")

        // Show user that job is running
        rankingStatus = .unknown

        do {
            // Trigger the actual ranking job via Edge Function
            let response = try await APIClient.shared.triggerRankingJob(for: symbol)
            print("[OptionsRanker] Job triggered: \(response.message)")

            // Wait for estimated completion time
            let waitSeconds = UInt64(response.estimatedCompletionSeconds)
            print("[OptionsRanker] Waiting \(waitSeconds) seconds for job to complete...")
            try await Task.sleep(nanoseconds: waitSeconds * 1_000_000_000)

            // Reload rankings after job completes
            await loadRankings(for: symbol)
            print("[OptionsRanker] Ranking job completed for \(symbol)")
        } catch {
            errorMessage = "Failed to trigger ranking job: \(error.localizedDescription)"
            print("[OptionsRanker] Error triggering job: \(error)")
        }

        isGeneratingRankings = false
    }

    func refreshQuotes(for symbol: String) async {
        // Avoid overlapping refreshes if a previous request is in-flight
        if isRefreshingQuotes { return }

        guard !rankings.isEmpty else { return }
        let contracts = rankings.map { $0.contractSymbol }
        guard !contracts.isEmpty else { return }

        isRefreshingQuotes = true

        do {
            let response = try await APIClient.shared.fetchOptionsQuotes(
                symbol: symbol,
                contracts: Array(contracts.prefix(120))
            )

            var quoteMap: [String: OptionContractQuote] = [:]
            for quote in response.quotes {
                quoteMap[quote.contractSymbol] = quote
            }

            liveQuotes = quoteMap
            lastQuoteRefresh = ISO8601DateFormatter().date(from: response.timestamp)
        } catch {
            print("[OptionsRanker] Failed to refresh quotes: \(error)")
        }

        isRefreshingQuotes = false
    }
    
    /// Coordinated refresh: trigger inline ranking job which fetches fresh data and ranks
    func syncAndRank(for symbol: String) async {
        // Use the same inline ranking process as triggerRankingJob
        await triggerRankingJob(for: symbol)
    }

    private func updateRankingStatus() {
        guard let firstRank = rankings.first else {
            rankingStatus = .unavailable
            lastRankingRefresh = nil
            return
        }

        // Fix D: Try multiple ISO8601 formats with fallbacks
        let runAtDate = parseISO8601Date(firstRank.runAt)

        if let runAt = runAtDate {
            lastRankingRefresh = runAt
            let hourAgo = Date().addingTimeInterval(-3600)
            rankingStatus = runAt > hourAgo ? .fresh : .stale
        } else {
            // Fallback: use current time as "unknown freshness" but still show the badge
            lastRankingRefresh = nil
            rankingStatus = .unknown
        }
    }

    /// Helper to parse ISO8601 dates with multiple format fallbacks (Fix D)
    private func parseISO8601Date(_ dateString: String) -> Date? {
        // Try with fractional seconds first
        let isoFormatter = ISO8601DateFormatter()
        isoFormatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = isoFormatter.date(from: dateString) {
            return date
        }

        // Try without fractional seconds
        isoFormatter.formatOptions = [.withInternetDateTime]
        if let date = isoFormatter.date(from: dateString) {
            return date
        }

        // Try basic date formatter as last resort
        let basicFormatter = DateFormatter()
        basicFormatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSSZ"
        if let date = basicFormatter.date(from: dateString) {
            return date
        }

        basicFormatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ssZ"
        return basicFormatter.date(from: dateString)
    }

    func setExpiry(_ expiry: String?) {
        selectedExpiry = expiry
    }

    func setSide(_ side: OptionSide?) {
        selectedSide = side
    }

    func setSignalFilter(_ signal: SignalFilter) {
        selectedSignal = signal
    }

    func setSortOption(_ option: RankingSortOption) {
        sortOption = option
    }

    func setUseGAFilter(_ enabled: Bool) {
        useGAFilter = enabled
    }

    private func applyGAFilterState() {
        guard useGAFilter else {
            if let snapshot = gaFilterSnapshot {
                minScore = snapshot.minScore
                selectedSignal = snapshot.selectedSignal
                sortOption = snapshot.sortOption
                gaFilterSnapshot = nil
            }
            return
        }

        guard let genes = gaStrategy?.genes else { return }

        if gaFilterSnapshot == nil {
            gaFilterSnapshot = GAFilterSnapshot(
                minScore: minScore,
                selectedSignal: selectedSignal,
                sortOption: sortOption
            )
        }

        minScore = max(minScore, genes.minCompositeRank / 100)

        if let gaSignal = mapGASignalFilter(genes.signalFilter) {
            selectedSignal = gaSignal
        }

        sortOption = .gaConfidence
    }

    private func mapGASignalFilter(_ raw: String) -> SignalFilter? {
        switch raw.lowercased() {
        case "buy":
            return .buy
        case "discount":
            return .discount
        case "runner":
            return .runner
        case "greeks":
            return .greeks
        case "any", "all", "":
            return nil
        default:
            return nil
        }
    }

    func clearPriceFilters() {
        minPriceInput = ""
        maxPriceInput = ""
    }

    // MARK: - GA Strategy

    func loadGAStrategy(for symbol: String) async {
        isLoadingGA = true

        do {
            let response = try await APIClient.shared.fetchGAStrategy(symbol: symbol)
            gaStrategy = response.strategy
            gaRecommendation = response.recommendation

            if useGAFilter {
                applyGAFilterState()
            }

            if response.hasStrategy {
                print("[OptionsRanker] Loaded GA strategy for \(symbol)")
            } else {
                print("[OptionsRanker] Using default GA strategy for \(symbol)")
            }
        } catch {
            print("[OptionsRanker] Failed to load GA strategy: \(error)")
            // Don't show error to user, just use default
        }

        isLoadingGA = false
    }

    func triggerGAOptimization(for symbol: String) async {
        isLoadingGA = true
        errorMessage = nil

        print("[OptionsRanker] Triggering GA optimization for \(symbol)...")

        do {
            let response = try await APIClient.shared.triggerGAOptimization(
                symbol: symbol,
                generations: 50,
                trainingDays: 30
            )

            if response.success {
                print("[OptionsRanker] GA optimization queued: \(response.runId ?? "unknown")")
                print("[OptionsRanker] Estimated time: \(response.estimatedMinutes ?? 0) minutes")
            } else {
                errorMessage = response.message
            }
        } catch {
            errorMessage = "Failed to trigger GA optimization: \(error.localizedDescription)"
            print("[OptionsRanker] GA trigger error: \(error)")
        }

        isLoadingGA = false
    }

    /// Get GA confidence score for an option rank (if GA strategy is loaded)
    func gaConfidenceScore(for rank: OptionRank) -> Double? {
        guard let genes = gaStrategy?.genes else { return nil }
        return rank.gaConfidence(genes)
    }

    /// Check if an option passes all GA entry criteria
    func passesGAEntry(rank: OptionRank) -> Bool {
        guard let genes = gaStrategy?.genes else { return true }
        return rank.passesGAFilters(genes)
    }

    // MARK: - Auto Refresh Quotes

    func startAutoRefresh(for symbol: String) {
        stopAutoRefresh()

        // Choose interval based on market hours
        let interval: TimeInterval = isMarketOpen() ? 15 : 90
        autoRefreshInterval = interval
        isAutoRefreshing = true

        quoteTimerCancellable = Timer
            .publish(every: interval, on: .main, in: .common)
            .autoconnect()
            .sink { [weak self] _ in
                guard let self = self else { return }
                Task { [weak self] in
                    guard let self = self else { return }
                    await self.refreshQuotes(for: symbol)
                }
            }
    }

    func stopAutoRefresh() {
        quoteTimerCancellable?.cancel()
        quoteTimerCancellable = nil
        isAutoRefreshing = false
        autoRefreshInterval = nil
    }

    private func isMarketOpen() -> Bool {
        // Simple market hours check for NYSE/Nasdaq: 9:30–16:00 ET, Mon–Fri
        // This is a heuristic; replace with an exchange calendar if available.
        let tz = TimeZone(identifier: "America/New_York") ?? .current
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = tz

        let now = Date()
        let comps = calendar.dateComponents([.weekday, .hour, .minute], from: now)
        guard let weekday = comps.weekday, let hour = comps.hour, let minute = comps.minute else { return false }
        // Weekday 1=Sun, 7=Sat; open Mon–Fri
        guard (2...6).contains(weekday) else { return false }

        let minutesSinceMidnight = hour * 60 + minute
        let openMinutes = 9 * 60 + 30   // 9:30
        let closeMinutes = 16 * 60      // 16:00
        return minutesSinceMidnight >= openMinutes && minutesSinceMidnight < closeMinutes
    }
}
