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

    private var cancellables = Set<AnyCancellable>()

    enum RankingStatus {
        case unknown
        case fresh        // Data < 1 hour old
        case stale        // Data > 1 hour old
        case unavailable  // No data exists
    }

    var filteredRankings: [OptionRank] {
        rankings
            .filter { rank in
                // Score filter using composite rank (0-100)
                let score = rank.compositeRank / 100
                guard score >= minScore else { return false }

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
            .sorted { lhs, rhs in
                switch sortOption {
                case .composite:
                    return lhs.compositeRank > rhs.compositeRank
                case .momentum:
                    return (lhs.momentumScore ?? 0) > (rhs.momentumScore ?? 0)
                case .value:
                    return (lhs.valueScore ?? 0) > (rhs.valueScore ?? 0)
                case .greeks:
                    return (lhs.greeksScore ?? 0) > (rhs.greeksScore ?? 0)
                }
            }
    }

    var availableExpiries: [String] {
        let expiries = Set(rankings.map { $0.expiry })
        return Array(expiries).sorted()
    }

    func loadRankings(for symbol: String) async {
        isLoading = true
        errorMessage = nil

        do {
            let response = try await APIClient.shared.fetchOptionsRankings(
                symbol: symbol,
                expiry: selectedExpiry,
                side: selectedSide,
                limit: 100
            )

            rankings = response.ranks
            updateRankingStatus()
            isLoading = false

            print("[OptionsRanker] Loaded \(rankings.count) ranked options for \(symbol)")
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
    
    /// Coordinated refresh: sync fresh data first, then queue options ranking job
    func syncAndRank(for symbol: String) async {
        isGeneratingRankings = true
        errorMessage = nil
        rankingStatus = .unknown

        print("[OptionsRanker] Starting coordinated sync & rank for \(symbol)...")

        do {
            // Step 1: Refresh data and queue options ranking job
            let refreshResponse = try await APIClient.shared.refreshData(
                symbol: symbol,
                refreshML: true,
                refreshOptions: true
            )
            print("[OptionsRanker] Data sync complete: \(refreshResponse.message)")
            
            // Step 2: Wait for job to process (estimate ~30 seconds)
            print("[OptionsRanker] Waiting for ranking job to complete...")
            try await Task.sleep(nanoseconds: 30 * 1_000_000_000)
            
            // Step 3: Reload rankings
            await loadRankings(for: symbol)
            print("[OptionsRanker] Sync & rank completed for \(symbol)")
            
        } catch {
            errorMessage = "Sync failed: \(error.localizedDescription)"
            print("[OptionsRanker] Error in sync & rank: \(error)")
        }

        isGeneratingRankings = false
    }

    private func updateRankingStatus() {
        guard let firstRank = rankings.first else {
            rankingStatus = .unavailable
            return
        }

        // Parse the run_at timestamp
        let dateFormatter = ISO8601DateFormatter()
        if let runAt = dateFormatter.date(from: firstRank.runAt) {
            let hourAgo = Date().addingTimeInterval(-3600)
            rankingStatus = runAt > hourAgo ? .fresh : .stale
        } else {
            rankingStatus = .unknown
        }
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
}
