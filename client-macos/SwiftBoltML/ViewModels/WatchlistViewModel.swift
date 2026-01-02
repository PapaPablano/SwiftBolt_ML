import Foundation

@MainActor
final class WatchlistViewModel: ObservableObject {
    @Published private(set) var watchedSymbols: [Symbol] = []
    @Published private(set) var jobStatuses: [String: WatchlistJobStatus] = [:]
    @Published private(set) var isLoading = false
    @Published var errorMessage: String?

    private let apiClient: APIClient
    private let storageKey = "watchlist_symbols"

    init(apiClient: APIClient = .shared) {
        self.apiClient = apiClient
        loadWatchlist()
    }

    // MARK: - Public Methods

    func addSymbol(_ symbol: Symbol) async {
        guard !isWatched(symbol) else { return }

        isLoading = true
        errorMessage = nil

        do {
            let request = WatchlistSyncRequest(
                action: .add,
                symbol: symbol.ticker,
                watchlistId: nil
            )

            let response: WatchlistSyncResponse = try await apiClient.post(
                endpoint: "watchlist-sync",
                body: request
            )

            if response.success {
                // Create symbol with OHLC averages from response
                let enrichedSymbol = Symbol(
                    id: symbol.id,
                    ticker: symbol.ticker,
                    assetType: symbol.assetType,
                    description: symbol.description,
                    avgDailyVolumeAll: response.avgDailyVolumeAll,
                    avgDailyVolume10d: response.avgDailyVolume10d,
                    avgLastPriceAll: response.avgLastPriceAll,
                    avgLastPrice10d: response.avgLastPrice10d
                )
                watchedSymbols.append(enrichedSymbol)
                saveWatchlist()

                // Update job status if provided
                if let jobStatus = response.jobStatus {
                    updateJobStatuses(jobStatus)
                }

                print("[WatchlistViewModel] ✅ Added \(symbol.ticker) to watchlist, jobs queued")
            } else {
                errorMessage = response.message ?? "Failed to add symbol"
            }
        } catch {
            errorMessage = "Failed to sync watchlist: \(error.localizedDescription)"
            print("[WatchlistViewModel] Error adding symbol: \(error)")
        }

        isLoading = false
    }

    func removeSymbol(_ symbol: Symbol) async {
        isLoading = true
        errorMessage = nil

        do {
            let request = WatchlistSyncRequest(
                action: .remove,
                symbol: symbol.ticker,
                watchlistId: nil
            )

            let response: WatchlistSyncResponse = try await apiClient.post(
                endpoint: "watchlist-sync",
                body: request
            )

            if response.success {
                watchedSymbols.removeAll { $0.ticker == symbol.ticker }
                jobStatuses.removeValue(forKey: symbol.ticker)
                saveWatchlist()
                print("[WatchlistViewModel] ✅ Removed \(symbol.ticker) from watchlist")
            } else {
                errorMessage = response.message ?? "Failed to remove symbol"
            }
        } catch {
            errorMessage = "Failed to sync watchlist: \(error.localizedDescription)"
            print("[WatchlistViewModel] Error removing symbol: \(error)")
        }

        isLoading = false
    }

    func isWatched(_ symbol: Symbol) -> Bool {
        watchedSymbols.contains { $0.ticker == symbol.ticker }
    }

    func toggleSymbol(_ symbol: Symbol) async {
        if isWatched(symbol) {
            await removeSymbol(symbol)
        } else {
            await addSymbol(symbol)
        }
    }

    func refreshWatchlist() async {
        isLoading = true
        errorMessage = nil

        do {
            let request = WatchlistSyncRequest(
                action: .list,
                symbol: nil,
                watchlistId: nil
            )

            let response: WatchlistSyncResponse = try await apiClient.post(
                endpoint: "watchlist-sync",
                body: request
            )

            if response.success, let items = response.items {
                // Convert items to Symbol objects
                watchedSymbols = items.map { item in
                    Symbol(
                        ticker: item.symbol,
                        avgDailyVolumeAll: item.avgDailyVolumeAll,
                        avgDailyVolume10d: item.avgDailyVolume10d,
                        avgLastPriceAll: item.avgLastPriceAll,
                        avgLastPrice10d: item.avgLastPrice10d
                    )
                }

                // Update job statuses
                for item in items {
                    if let status = item.jobStatus {
                        jobStatuses[item.symbol] = status
                    }
                }

                saveWatchlist()
                print("[WatchlistViewModel] ✅ Refreshed watchlist: \(watchedSymbols.count) symbols")
            } else {
                errorMessage = response.message ?? "Failed to refresh watchlist"
            }
        } catch {
            errorMessage = "Failed to refresh watchlist: \(error.localizedDescription)"
            print("[WatchlistViewModel] Error refreshing: \(error)")
        }

        isLoading = false
    }

    func getJobStatus(for symbol: Symbol) -> WatchlistJobStatus? {
        jobStatuses[symbol.ticker]
    }

    // MARK: - Private Helpers

    private func updateJobStatuses(_ statuses: [JobStatus]) {
        for _ in statuses {
            // Extract symbol from job (assuming job has symbol context)
            // For now, we'll need to track this differently or modify API response
            // This is a placeholder implementation
        }
    }

    // MARK: - Local Persistence (Backup)

    private func saveWatchlist() {
        do {
            let encoder = JSONEncoder()
            let data = try encoder.encode(watchedSymbols)
            UserDefaults.standard.set(data, forKey: storageKey)
        } catch {
            print("[WatchlistViewModel] Error saving watchlist locally: \(error)")
        }
    }

    private func loadWatchlist() {
        guard let data = UserDefaults.standard.data(forKey: storageKey) else { return }

        do {
            let decoder = JSONDecoder()
            watchedSymbols = try decoder.decode([Symbol].self, from: data)
        } catch {
            print("[WatchlistViewModel] Error loading watchlist locally: \(error)")
            watchedSymbols = []
        }
    }

    func clearWatchlist() {
        watchedSymbols = []
        jobStatuses = [:]
        UserDefaults.standard.removeObject(forKey: storageKey)
    }
}
