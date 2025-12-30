import Foundation
import SwiftUI

// MARK: - Pivot Level Model

/// Represents a multi-period pivot level for S&R detection
/// Matches TradingView "Pivot Levels [BigBeluga]" indicator
struct PivotLevel: Identifiable {
    let id = UUID()

    // Configuration
    let length: Int              // Period (e.g., 5, 25, 50, 100)
    let display: Bool            // Show this level?
    let style: PivotLineStyle    // -- - or ..
    let extend: PivotExtendMode  // Both or Right

    // Pivot High Values
    var levelHigh: Double        // Pivot high price level
    var startIndexHigh: Int      // Bar index where high pivot formed

    // Pivot Low Values
    var levelLow: Double         // Pivot low price level
    var startIndexLow: Int       // Bar index where low pivot formed

    // Adaptive Color State (separate for high and low)
    var highStatus: PivotStatus = .inactive
    var lowStatus: PivotStatus = .inactive

    /// Get color for high pivot based on its status
    /// PineScript: color1 = low > H+atr ? colorSup : high < H-atr ? colorRes : colorActive
    var highColor: Color {
        switch highStatus {
        case .support: return PivotColors.support
        case .resistance: return PivotColors.resistance
        case .active: return PivotColors.active
        case .inactive: return .gray
        }
    }

    /// Get color for low pivot based on its status
    /// PineScript: color2 = low > L+atr ? colorSup : high < L-atr ? colorRes : colorActive
    var lowColor: Color {
        switch lowStatus {
        case .support: return PivotColors.support
        case .resistance: return PivotColors.resistance
        case .active: return PivotColors.active
        case .inactive: return .gray
        }
    }

    /// Get glow color for high pivot (80% transparent)
    /// PineScript: color.new(color1, 80)
    var highGlowColor: Color {
        highColor.opacity(0.2)
    }

    /// Get glow color for low pivot (80% transparent)
    var lowGlowColor: Color {
        lowColor.opacity(0.2)
    }
}

// MARK: - Supporting Enums

/// Pivot status determines the color
/// PineScript logic:
///   - Support (green): price low > level + ATR threshold
///   - Resistance (orange): price high < level - ATR threshold
///   - Active (blue): price is within ATR threshold of level
enum PivotStatus {
    case support        // Price well above level → Green (bullish zone)
    case resistance     // Price well below level → Orange (bearish zone)
    case active         // Price testing level → Blue (neutral/active)
    case inactive       // Not calculated yet
}

/// Line style for pivot levels
/// Matches PineScript: ["--", "-", ".."]
enum PivotLineStyle: String, CaseIterable {
    case dashed = "--"
    case solid = "-"
    case dotted = ".."

    var strokeStyle: StrokeStyle {
        switch self {
        case .dashed:
            return StrokeStyle(lineWidth: 1, dash: [6, 4])
        case .solid:
            return StrokeStyle(lineWidth: 1)
        case .dotted:
            return StrokeStyle(lineWidth: 1, dash: [2, 3])
        }
    }

    /// Convert from PineScript line.style constants
    var pineScriptStyle: String {
        switch self {
        case .dashed: return "line.style_dashed"
        case .solid: return "line.style_solid"
        case .dotted: return "line.style_dotted"
        }
    }
}

/// Line extend mode
/// Matches PineScript: ["Both", "Right"]
enum PivotExtendMode: String, CaseIterable {
    case both   // Extend left and right (extend.both)
    case right  // Extend right only (extend.right)
}

// MARK: - Color Constants

/// Standard pivot colors matching BigBeluga indicator
/// PineScript:
///   colorSup = color.rgb(30, 214, 125)    // Green
///   colorRes = #eb7c14                     // Orange
///   colorActive = color.rgb(27, 133, 255)  // Blue
struct PivotColors {
    static let support = Color(red: 30/255, green: 214/255, blue: 125/255)     // #1ED67D Green
    static let resistance = Color(red: 235/255, green: 124/255, blue: 20/255)  // #EB7C14 Orange
    static let active = Color(red: 27/255, green: 133/255, blue: 255/255)      // #1B85FF Blue
}

// MARK: - Period Configuration

/// Configuration for a pivot period
struct PivotPeriodConfig {
    let length: Int
    let defaultStyle: PivotLineStyle
    let defaultExtend: PivotExtendMode
    let defaultDisplay: Bool

    /// Core line width based on period
    /// PineScript: width1 = len == len1 ? 1 : len == len2 ? 2 : len == len3 ? 3 : 4
    var coreLineWidth: CGFloat {
        switch length {
        case 5: return 1
        case 25: return 2
        case 50: return 3
        case 100: return 4
        default: return 1
        }
    }

    /// Glow line width (wider for larger periods)
    /// PineScript: width2 = len == len1 ? 3 : len == len2 ? 7 : len == len3 ? 10 : 15
    var glowLineWidth: CGFloat {
        switch length {
        case 5: return 3
        case 25: return 7
        case 50: return 10
        case 100: return 15
        default: return 3
        }
    }
}

/// Standard pivot period configurations (matching BigBeluga defaults)
let PIVOT_CONFIGS: [PivotPeriodConfig] = [
    PivotPeriodConfig(length: 5, defaultStyle: .dashed, defaultExtend: .both, defaultDisplay: true),
    PivotPeriodConfig(length: 25, defaultStyle: .solid, defaultExtend: .both, defaultDisplay: true),
    PivotPeriodConfig(length: 50, defaultStyle: .solid, defaultExtend: .both, defaultDisplay: true),
    PivotPeriodConfig(length: 100, defaultStyle: .solid, defaultExtend: .both, defaultDisplay: true),
]

// MARK: - Detected Pivot Point

/// A single detected pivot point (high or low)
/// Used during pivot detection process
struct DetectedPivot: Identifiable {
    let id = UUID()
    let index: Int       // Bar index where pivot occurred
    let price: Double    // Price level (high for pivot high, low for pivot low)
    let date: Date       // Timestamp of the pivot bar
    let type: PivotType  // High or low
}

/// Type of pivot point
enum PivotType {
    case high  // Local maximum
    case low   // Local minimum
}
