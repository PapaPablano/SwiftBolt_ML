import Foundation

/// Persisted list of up to 16 favorite technical indicator names for the Analysis panel.
@MainActor
final class IndicatorFavoritesStore: ObservableObject {
    static let maxFavorites = 16
    private static let userDefaultsKey = "technical_indicators_favorite_names"

    @Published private(set) var favoriteNames: [String] = [] {
        didSet {
            UserDefaults.standard.set(favoriteNames, forKey: Self.userDefaultsKey)
        }
    }

    init() {
        if let saved = UserDefaults.standard.stringArray(forKey: Self.userDefaultsKey) {
            favoriteNames = Array(saved.prefix(Self.maxFavorites))
        }
    }

    func isFavorite(_ name: String) -> Bool {
        favoriteNames.contains(name)
    }

    /// Toggle favorite for an indicator. Add if not present (only if < maxFavorites); remove if present.
    func toggleFavorite(_ name: String) {
        if let idx = favoriteNames.firstIndex(of: name) {
            favoriteNames.remove(at: idx)
        } else if favoriteNames.count < Self.maxFavorites {
            favoriteNames.append(name)
        }
    }

    /// Set the order of favorites (e.g. after user reorders in Analysis). Preserves the same set; only order changes.
    func setOrder(_ names: [String]) {
        let current = Set(favoriteNames)
        let newOrder = names.filter { current.contains($0) }
        if newOrder.count == current.count {
            favoriteNames = newOrder
        }
    }

    /// Ordered list of favorite names (for resolving to IndicatorItem in Analysis panel).
    var orderedFavorites: [String] {
        favoriteNames
    }
}
