import Foundation

@MainActor
final class WatchlistViewModel: ObservableObject {
    @Published private(set) var watchedSymbols: [Symbol] = []

    private let storageKey = "watchlist_symbols"

    init() {
        loadWatchlist()
    }

    // MARK: - Public Methods

    func addSymbol(_ symbol: Symbol) {
        guard !isWatched(symbol) else { return }
        watchedSymbols.append(symbol)
        saveWatchlist()
    }

    func removeSymbol(_ symbol: Symbol) {
        watchedSymbols.removeAll { $0.id == symbol.id }
        saveWatchlist()
    }

    func isWatched(_ symbol: Symbol) -> Bool {
        watchedSymbols.contains { $0.id == symbol.id }
    }

    func toggleSymbol(_ symbol: Symbol) {
        if isWatched(symbol) {
            removeSymbol(symbol)
        } else {
            addSymbol(symbol)
        }
    }

    // MARK: - Persistence

    private func saveWatchlist() {
        do {
            let encoder = JSONEncoder()
            let data = try encoder.encode(watchedSymbols)
            UserDefaults.standard.set(data, forKey: storageKey)
        } catch {
            print("[WatchlistViewModel] Error saving watchlist: \(error)")
        }
    }

    private func loadWatchlist() {
        guard let data = UserDefaults.standard.data(forKey: storageKey) else { return }

        do {
            let decoder = JSONDecoder()
            watchedSymbols = try decoder.decode([Symbol].self, from: data)
        } catch {
            print("[WatchlistViewModel] Error loading watchlist: \(error)")
            watchedSymbols = []
        }
    }

    func clearWatchlist() {
        watchedSymbols = []
        UserDefaults.standard.removeObject(forKey: storageKey)
    }
}
