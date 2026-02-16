import Foundation
import SwiftUI

/// Manages user preferences for futures contract selection
/// Persists the last selected expiry per root so returning users
/// see the same contract without re-picking
class FuturesPreferences: ObservableObject {
    static let shared = FuturesPreferences()
    
    private let defaults = UserDefaults.standard
    private let lastSelectedKey = "futures.lastSelectedExpiry"
    private let defaultContinuousKey = "futures.defaultToContinuous"
    
    /// Get the last selected expiry symbol for a given root
    /// - Parameter root: The futures root symbol (e.g., "GC", "ES")
    /// - Returns: The last selected symbol, or nil if never selected
    func lastSelectedExpiry(for root: String) -> String? {
        let dict = defaults.dictionary(forKey: lastSelectedKey) as? [String: String]
        return dict?[root.uppercased()]
    }
    
    /// Save the selected expiry for a given root
    /// - Parameters:
    ///   - symbol: The selected symbol (e.g., "GCJ26", "GC1!")
    ///   - root: The futures root symbol
    func setLastSelectedExpiry(_ symbol: String, for root: String) {
        var dict = defaults.dictionary(forKey: lastSelectedKey) as? [String: String] ?? [:]
        dict[root.uppercased()] = symbol
        defaults.set(dict, forKey: lastSelectedKey)
    }
    
    /// Get the preferred symbol for a root
    /// Returns the last selected symbol, or defaults to front-month
    /// - Parameter root: The futures root symbol
    /// - Returns: The preferred symbol to chart
    func preferredSymbol(for root: String) -> String {
        // If user has a preference, use it
        if let lastSelected = lastSelectedExpiry(for: root) {
            return lastSelected
        }
        
        // Default to continuous (GC1!, ES1!, etc.)
        return "\(root.uppercased())1!"
    }
    
    /// Check if we need to fetch the front month contract
    func needsFrontMonthFetch(for root: String) -> Bool {
        return lastSelectedExpiry(for: root) == nil
    }
    
    /// Check if the user prefers continuous contracts by default
    var defaultToContinuous: Bool {
        get {
            defaults.bool(forKey: defaultContinuousKey)
        }
        set {
            defaults.set(newValue, forKey: defaultContinuousKey)
        }
    }
    
    /// Clear all preferences (useful for testing or reset)
    func clearAllPreferences() {
        defaults.removeObject(forKey: lastSelectedKey)
        defaults.removeObject(forKey: defaultContinuousKey)
    }
}

// MARK: - SwiftUI Integration

private struct FuturesPreferencesKey: EnvironmentKey {
    static let defaultValue = FuturesPreferences.shared
}

extension EnvironmentValues {
    var futuresPreferences: FuturesPreferences {
        get { self[FuturesPreferencesKey.self] }
        set { self[FuturesPreferencesKey.self] = newValue }
    }
}
