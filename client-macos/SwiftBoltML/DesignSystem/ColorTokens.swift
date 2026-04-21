import SwiftUI

// MARK: - Design Tokens: Colors

/// Centralized color tokens for SwiftBolt ML.
/// Use these instead of inline Color literals to ensure consistency and dark mode support.
enum DesignTokens {

    // MARK: - Semantic Colors

    enum Colors {
        // Brand / UI
        static let primary = Color.accentColor
        static let secondary = Color.secondary

        // Status
        static let success = Color(light: Color(red: 30/255, green: 214/255, blue: 125/255),
                                   dark: Color(red: 40/255, green: 224/255, blue: 140/255))
        static let warning = Color(light: Color(red: 235/255, green: 180/255, blue: 20/255),
                                   dark: Color(red: 245/255, green: 190/255, blue: 40/255))
        static let error = Color(light: Color(red: 239/255, green: 83/255, blue: 80/255),
                                 dark: Color(red: 249/255, green: 100/255, blue: 97/255))

        // Chart: Pivot / S&R (ported from PivotColors)
        static let chartSupport = Color(light: Color(red: 30/255, green: 214/255, blue: 125/255),
                                        dark: Color(red: 40/255, green: 224/255, blue: 140/255))    // #1ED67D
        static let chartResistance = Color(light: Color(red: 235/255, green: 124/255, blue: 20/255),
                                           dark: Color(red: 245/255, green: 134/255, blue: 35/255)) // #EB7C14
        static let chartActive = Color(light: Color(red: 27/255, green: 133/255, blue: 255/255),
                                       dark: Color(red: 50/255, green: 150/255, blue: 255/255))     // #1B85FF

        // Chart: Signals (mirroring chart.js const colors naming)
        static let bullish = Color(light: Color(red: 38/255, green: 166/255, blue: 154/255),
                                   dark: Color(red: 48/255, green: 180/255, blue: 168/255))   // #26a69a
        static let bearish = Color(light: Color(red: 239/255, green: 83/255, blue: 80/255),
                                   dark: Color(red: 249/255, green: 100/255, blue: 97/255))   // #ef5350
        static let neutral = Color(light: Color(red: 136/255, green: 136/255, blue: 136/255),
                                   dark: Color(red: 160/255, green: 160/255, blue: 160/255))  // #888888

        // Chart: Pivot Period colors (from PivotPeriodManager)
        static let periodMicro = Color(light: Color(red: 0.8, green: 0.8, blue: 0.8),
                                       dark: Color(red: 0.6, green: 0.6, blue: 0.6))
        static let periodShort = Color(light: Color(red: 0.2, green: 0.5, blue: 1.0),
                                       dark: Color(red: 0.3, green: 0.6, blue: 1.0))
        static let periodMedium = Color(light: Color(red: 0.0, green: 0.8, blue: 0.8),
                                        dark: Color(red: 0.1, green: 0.9, blue: 0.9))
        static let periodLong = Color(light: Color(red: 1.0, green: 0.8, blue: 0.2),
                                      dark: Color(red: 1.0, green: 0.85, blue: 0.3))

        // Forecast
        static let forecastPositive = Color(light: Color(red: 38/255, green: 166/255, blue: 154/255),
                                            dark: Color(red: 48/255, green: 180/255, blue: 168/255))
        static let forecastNegative = Color(light: Color(red: 239/255, green: 83/255, blue: 80/255),
                                            dark: Color(red: 249/255, green: 100/255, blue: 97/255))

        // Backgrounds
        static let surfacePrimary = Color(nsColor: .windowBackgroundColor)
        static let surfaceSecondary = Color(nsColor: .controlBackgroundColor)
    }
}

// MARK: - Adaptive Color Helper

extension Color {
    /// Creates an adaptive color that switches between light and dark variants.
    init(light: Color, dark: Color) {
        self.init(nsColor: NSColor(name: nil) { appearance in
            if appearance.bestMatch(from: [.aqua, .darkAqua]) == .darkAqua {
                return NSColor(dark)
            } else {
                return NSColor(light)
            }
        })
    }
}
