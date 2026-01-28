import Foundation
import SwiftUI

// MARK: - Period Configuration Manager

/// Manages custom pivot period configurations with presets and validation
@MainActor
class PivotPeriodManager: ObservableObject {

    // MARK: - Published Properties

    @Published var selectedPreset: PeriodPreset = .balanced {
        didSet {
            currentPeriods = selectedPreset.periods
            savePreference()
        }
    }

    @Published var currentPeriods: [PeriodConfig] = PeriodPreset.balanced.periods {
        didSet {
            // Validate and update
            validatePeriods()
            savePreference()
        }
    }

    @Published var isCustomized: Bool = false

    // MARK: - Singleton

    static let shared = PivotPeriodManager()
    private init() {
        loadPreference()
    }

    // MARK: - Period Presets

    enum PeriodPreset: String, CaseIterable {
        case conservative = "Conservative"
        case balanced = "Balanced"
        case aggressive = "Aggressive"

        var displayName: String {
            self.rawValue
        }

        var description: String {
            switch self {
            case .conservative:
                return "Fewer, larger periods - More stable signals"
            case .balanced:
                return "Mix of periods - Good for most conditions"
            case .aggressive:
                return "Many periods - More signals, higher sensitivity"
            }
        }

        var periods: [PeriodConfig] {
            switch self {
            case .conservative:
                return [
                    PeriodConfig(length: 50, style: .solid, extend: .both, enabled: true, label: "Medium"),
                    PeriodConfig(length: 100, style: .solid, extend: .both, enabled: true, label: "Long"),
                ]

            case .balanced:
                return [
                    PeriodConfig(length: 5, style: .dashed, extend: .both, enabled: true, label: "Micro"),
                    PeriodConfig(length: 25, style: .solid, extend: .both, enabled: true, label: "Short"),
                    PeriodConfig(length: 50, style: .solid, extend: .both, enabled: true, label: "Medium"),
                    PeriodConfig(length: 100, style: .solid, extend: .both, enabled: true, label: "Long"),
                ]

            case .aggressive:
                return [
                    PeriodConfig(length: 3, style: .dotted, extend: .both, enabled: true, label: "Ultra"),
                    PeriodConfig(length: 5, style: .dashed, extend: .both, enabled: true, label: "Micro"),
                    PeriodConfig(length: 13, style: .dashed, extend: .both, enabled: true, label: "Short-Short"),
                    PeriodConfig(length: 25, style: .solid, extend: .both, enabled: true, label: "Short"),
                    PeriodConfig(length: 50, style: .solid, extend: .both, enabled: true, label: "Medium"),
                    PeriodConfig(length: 100, style: .solid, extend: .both, enabled: true, label: "Long"),
                ]
            }
        }
    }

    // MARK: - Public Methods

    /// Add a custom period
    func addPeriod(_ period: PeriodConfig) {
        guard !currentPeriods.contains(where: { $0.length == period.length }) else {
            return // Period already exists
        }

        currentPeriods.append(period)
        currentPeriods.sort { $0.length < $1.length }
        isCustomized = true
    }

    /// Remove a period by length
    func removePeriod(_ length: Int) {
        currentPeriods.removeAll { $0.length == length }
        isCustomized = true
    }

    /// Update a period's configuration
    func updatePeriod(_ period: PeriodConfig) {
        if let index = currentPeriods.firstIndex(where: { $0.length == period.length }) {
            currentPeriods[index] = period
            isCustomized = true
        }
    }

    /// Reset to a preset
    func resetToPreset(_ preset: PeriodPreset) {
        selectedPreset = preset
        isCustomized = false
    }

    /// Get all enabled periods
    var enabledPeriods: [Int] {
        currentPeriods.filter { $0.enabled }.map { $0.length }.sorted()
    }

    /// Get enabled periods with full config
    var enabledConfigs: [PeriodConfig] {
        currentPeriods.filter { $0.enabled }.sorted { $0.length < $1.length }
    }

    /// Get the period with the largest length (macro)
    var macroPeriod: PeriodConfig? {
        currentPeriods.filter { $0.enabled }.max { $0.length < $1.length }
    }

    /// Get the period with the smallest length (micro)
    var microPeriod: PeriodConfig? {
        currentPeriods.filter { $0.enabled }.min { $0.length < $1.length }
    }

    /// Validate period configurations
    private func validatePeriods() {
        // Ensure minimum gap between periods
        let sorted = currentPeriods.sorted { $0.length < $1.length }
        for i in 0..<sorted.count - 1 {
            if sorted[i + 1].length < sorted[i].length * 2 {
                // Warn about small gaps but don't prevent
                print("⚠️ Warning: Period gap might be too small: \(sorted[i].length) → \(sorted[i + 1].length)")
            }
        }

        // Ensure no duplicate lengths
        let lengths = currentPeriods.map { $0.length }
        if lengths.count != Set(lengths).count {
            currentPeriods.removeAll { config in
                lengths.filter { $0 == config.length }.count > 1
            }
        }
    }

    // MARK: - Persistence

    private func savePreference() {
        do {
            let encoder = JSONEncoder()
            let data = try encoder.encode(currentPeriods)
            UserDefaults.standard.set(data, forKey: "PivotPeriodConfigs")
            UserDefaults.standard.set(isCustomized, forKey: "PivotPeriodsCustomized")
        } catch {
            print("❌ Failed to save period preferences: \(error)")
        }
    }

    private func loadPreference() {
        if let data = UserDefaults.standard.data(forKey: "PivotPeriodConfigs") {
            do {
                let decoder = JSONDecoder()
                currentPeriods = try decoder.decode([PeriodConfig].self, from: data)
                isCustomized = UserDefaults.standard.bool(forKey: "PivotPeriodsCustomized")
            } catch {
                print("❌ Failed to load period preferences: \(error)")
                currentPeriods = PeriodPreset.balanced.periods
            }
        } else {
            currentPeriods = PeriodPreset.balanced.periods
        }
    }
}

// MARK: - Period Configuration

/// Configuration for a single pivot period
struct PeriodConfig: Identifiable, Codable, Equatable {
    let id = UUID()
    let length: Int              // Period in bars (e.g., 5, 25, 50, 100)
    let style: PivotLineStyle    // Line style (solid, dashed, dotted)
    let extend: PivotExtendMode  // Extension mode (both, right)
    var enabled: Bool = true     // Is this period enabled?
    let label: String            // Display label (e.g., "Short", "Medium", "Long")

    // Computed properties
    var coreLineWidth: CGFloat {
        switch length {
        case 1...5: return 1
        case 6...25: return 2
        case 26...75: return 3
        default: return 4
        }
    }

    var glowLineWidth: CGFloat {
        switch length {
        case 1...5: return 3
        case 6...25: return 7
        case 26...75: return 10
        default: return 15
        }
    }

    var color: Color {
        // Assign colors based on period size for visual hierarchy
        switch length {
        case 1...5:
            return Color(red: 0.8, green: 0.8, blue: 0.8)  // Light gray (micro)
        case 6...25:
            return Color(red: 0.2, green: 0.7, blue: 1.0)  // Blue (short-term)
        case 26...75:
            return Color(red: 0.2, green: 1.0, blue: 0.8)  // Cyan (medium-term)
        default:
            return Color(red: 1.0, green: 0.8, blue: 0.2)  // Gold (long-term)
        }
    }

    enum CodingKeys: String, CodingKey {
        case length, style, extend, enabled, label
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(length, forKey: .length)
        try container.encode(style.rawValue, forKey: .style)
        try container.encode(extend.rawValue, forKey: .extend)
        try container.encode(enabled, forKey: .enabled)
        try container.encode(label, forKey: .label)
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        length = try container.decode(Int.self, forKey: .length)
        let styleRaw = try container.decode(String.self, forKey: .style)
        style = PivotLineStyle(rawValue: styleRaw) ?? .solid
        let extendRaw = try container.decode(String.self, forKey: .extend)
        extend = PivotExtendMode(rawValue: extendRaw) ?? .both
        enabled = try container.decode(Bool.self, forKey: .enabled)
        label = try container.decode(String.self, forKey: .label)
    }

    init(length: Int, style: PivotLineStyle = .solid, extend: PivotExtendMode = .both, enabled: Bool = true, label: String = "") {
        self.length = length
        self.style = style
        self.extend = extend
        self.enabled = enabled
        self.label = label.isEmpty ? "Period \(length)" : label
    }
}
