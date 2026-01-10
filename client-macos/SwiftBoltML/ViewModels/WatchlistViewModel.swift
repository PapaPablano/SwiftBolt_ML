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

            var urlRequest = URLRequest(url: Config.functionURL("watchlist-sync"))
            urlRequest.httpMethod = "POST"
            urlRequest.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
            urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
            urlRequest.httpBody = try JSONEncoder().encode(request)
            
            let response: WatchlistSyncResponse = try await apiClient.performRequest(urlRequest)

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

                // Sync symbol to backend for multi-timeframe backfill
                SymbolSyncService.shared.syncSymbolInBackground(symbol.ticker, source: .watchlist)

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

            var urlRequest = URLRequest(url: Config.functionURL("watchlist-sync"))
            urlRequest.httpMethod = "POST"
            urlRequest.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
            urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
            urlRequest.httpBody = try JSONEncoder().encode(request)
            
            let response: WatchlistSyncResponse = try await apiClient.performRequest(urlRequest)

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

            var urlRequest = URLRequest(url: Config.functionURL("watchlist-sync"))
            urlRequest.httpMethod = "POST"
            urlRequest.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
            urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
            urlRequest.httpBody = try JSONEncoder().encode(request)
            
            let response: WatchlistSyncResponse = try await apiClient.performRequest(urlRequest)

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
    
    /// Reload all watchlist data using Alpaca-only strategy (replaces spec8)
    /// Multi-timeframe rule: Always processes all 5 timeframes together
    func reloadAllData(forceRefresh: Bool = false, timeframes: [String] = ["m15", "h1", "h4", "d1", "w1"]) async {
        isLoading = true
        errorMessage = nil
        
        do {
            print("[WatchlistViewModel] 🔄 Reloading all watchlist data...")
            let response = try await apiClient.reloadWatchlistData(
                forceRefresh: forceRefresh,
                timeframes: timeframes,
                symbols: nil
            )
            
            if response.success {
                print("[WatchlistViewModel] ✅ Reload complete: \(response.summary.success)/\(response.summary.total) symbols")
                
                // Log results for each symbol
                for result in response.results {
                    if result.status == "success" {
                        let bars = result.barsLoaded
                        print("[WatchlistViewModel]   ✓ \(result.symbol): m15=\(bars?.m15 ?? 0), h1=\(bars?.h1 ?? 0), h4=\(bars?.h4 ?? 0), d1=\(bars?.d1 ?? 0), w1=\(bars?.w1 ?? 0)")
                    } else {
                        print("[WatchlistViewModel]   ✗ \(result.symbol): \(result.message ?? "error")")
                    }
                }
                
                // Refresh watchlist to update UI
                await refreshWatchlist()
            } else {
                errorMessage = response.message
            }
        } catch {
            errorMessage = "Failed to reload watchlist data: \(error.localizedDescription)"
            print("[WatchlistViewModel] ❌ Reload error: \(error)")
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
