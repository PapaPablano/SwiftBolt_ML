import Foundation
import Combine

@MainActor
class OptionsRankerViewModel: ObservableObject {
    @Published var rankings: [OptionRank] = []
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var isGeneratingRankings = false
    @Published var rankingStatus: RankingStatus = .unknown

    @Published var selectedExpiry: String?
    @Published var selectedSide: OptionSide?
    @Published var minScore: Double = 0.0

    private var cancellables = Set<AnyCancellable>()

    enum RankingStatus {
        case unknown
        case fresh        // Data < 1 hour old
        case stale        // Data > 1 hour old
        case unavailable  // No data exists
    }

    var filteredRankings: [OptionRank] {
        rankings.filter { rank in
            rank.mlScore >= minScore
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
}
