import Foundation
import SwiftUI

// MARK: - Pivot Chart Drawing Utilities

/// Utilities for drawing pivot levels on trading charts
struct PivotChartDrawing {

    // MARK: - Chart Path Generation

    /// Generate a path for a horizontal pivot level across the chart
    /// - Parameters:
    ///   - level: The price level to draw
    ///   - chartWidth: Total width of the chart
    ///   - startIndex: Bar index where the level starts
    ///   - extendMode: Whether to extend left, right, or both
    ///   - yScale: Function to convert price to y-coordinate
    ///   - xScale: Function to convert bar index to x-coordinate
    static func generateLevelPath(
        level: Double,
        chartWidth: CGFloat,
        startIndex: Int,
        endIndex: Int,
        extendMode: PivotExtendMode,
        yScale: (Double) -> CGFloat,
        xScale: (Int) -> CGFloat
    ) -> Path {
        var path = Path()

        let y = yScale(level)
        let startX = xScale(startIndex)
        let endX = xScale(endIndex)

        let lineStart: CGFloat
        let lineEnd: CGFloat

        switch extendMode {
        case .both:
            lineStart = 0
            lineEnd = chartWidth

        case .right:
            lineStart = startX
            lineEnd = chartWidth
        }

        path.move(to: CGPoint(x: lineStart, y: y))
        path.addLine(to: CGPoint(x: lineEnd, y: y))

        return path
    }

    /// Generate dashed pattern for pivot level
    /// - Parameters:
    ///   - style: Line style (solid, dashed, dotted)
    /// - Returns: Dash pattern array
    static func dashPattern(for style: PivotLineStyle) -> [CGFloat] {
        switch style {
        case .solid:
            return []  // No dashing

        case .dashed:
            return [6, 4]  // 6 pixels on, 4 pixels off

        case .dotted:
            return [2, 3]  // 2 pixels on, 3 pixels off
        }
    }

    // MARK: - Pivot Marker Generation

    /// Generate a marker view for a pivot point
    /// - Parameters:
    ///   - pivot: The detected pivot point
    ///   - status: Current status (support, resistance, active)
    ///   - size: Size of the marker
    /// - Returns: View with appropriate marker styling
    static func markerView(
        for pivotType: PivotType,
        status: PivotStatus,
        size: CGFloat = 8
    ) -> some View {
        let color = statusColor(status)
        let shape = pivotType == .high ? AnyShape(Ellipse()) : AnyShape(Ellipse())

        return Circle()
            .fill(color)
            .frame(width: size, height: size)
            .overlay(
                Circle()
                    .stroke(Color.white, lineWidth: 1)
            )
    }

    // MARK: - Color Utilities

    /// Get color for a pivot status
    static func statusColor(_ status: PivotStatus) -> Color {
        switch status {
        case .support:
            return PivotColors.support

        case .resistance:
            return PivotColors.resistance

        case .active:
            return PivotColors.active

        case .inactive:
            return Color.gray.opacity(0.5)
        }
    }

    /// Get glow color (semi-transparent)
    static func glowColor(_ status: PivotStatus, opacity: Double = 0.2) -> Color {
        statusColor(status).opacity(opacity)
    }

    // MARK: - Label Generation

    /// Format a price label for display
    /// - Parameters:
    ///   - price: The price to format
    ///   - decimals: Number of decimal places
    /// - Returns: Formatted price string
    static func formatPrice(_ price: Double, decimals: Int = 2) -> String {
        String(format: "%.\(decimals)f", price)
    }

    /// Format a price label with symbol
    static func formatPriceWithSymbol(_ price: Double, symbol: String = "$", decimals: Int = 2) -> String {
        "\(symbol)\(formatPrice(price, decimals: decimals))"
    }

    // MARK: - Level Range Calculations

    /// Calculate the price range for a set of pivot levels
    /// - Parameters:
    ///   - levels: Array of pivot levels
    /// - Returns: (min, max, range) tuple
    static func priceRange(for levels: [PivotLevel]) -> (min: Double, max: Double, range: Double) {
        let allPrices = levels.flatMap { [$0.levelHigh, $0.levelLow].filter { $0 > 0 } }

        guard !allPrices.isEmpty else {
            return (min: 0, max: 0, range: 0)
        }

        let min = allPrices.min() ?? 0
        let max = allPrices.max() ?? 0

        return (min: min, max: max, range: max - min)
    }

    /// Calculate support/resistance zones from pivot levels
    struct PivotZone {
        let price: Double
        let status: PivotStatus
        let strength: Double  // 0-1, based on number of overlapping levels
        let levels: [PivotLevel]

        var label: String {
            switch status {
            case .support:
                return "Support (\(strength.formatted(.percent.precision(.fractionLength(0)))))"

            case .resistance:
                return "Resistance (\(strength.formatted(.percent.precision(.fractionLength(0)))))"

            case .active:
                return "Active Zone"

            case .inactive:
                return "Inactive"
            }
        }
    }

    /// Find clustered pivot levels (zones where multiple levels are close)
    /// - Parameters:
    ///   - levels: Array of pivot levels
    ///   - tolerance: Price tolerance for clustering
    /// - Returns: Array of pivot zones
    static func findPivotZones(in levels: [PivotLevel], tolerance: Double = 0.5) -> [PivotZone] {
        var zones: [PivotZone] = []
        var processedLevels = Set<UUID>()

        for level in levels {
            guard !processedLevels.contains(level.id) else { continue }

            // Check high pivot
            if level.levelHigh > 0 {
                let nearby = levels.filter { l in
                    (l.levelHigh > 0 && abs(l.levelHigh - level.levelHigh) <= tolerance) ||
                    (l.levelLow > 0 && abs(l.levelLow - level.levelHigh) <= tolerance)
                }

                let strength = Double(nearby.count) / Double(levels.count)
                zones.append(PivotZone(
                    price: level.levelHigh,
                    status: level.highStatus,
                    strength: strength,
                    levels: nearby
                ))

                for l in nearby {
                    processedLevels.insert(l.id)
                }
            }

            // Check low pivot
            if level.levelLow > 0 {
                let nearby = levels.filter { l in
                    (l.levelLow > 0 && abs(l.levelLow - level.levelLow) <= tolerance) ||
                    (l.levelHigh > 0 && abs(l.levelHigh - level.levelLow) <= tolerance)
                }

                let strength = Double(nearby.count) / Double(levels.count)
                zones.append(PivotZone(
                    price: level.levelLow,
                    status: level.lowStatus,
                    strength: strength,
                    levels: nearby
                ))

                for l in nearby {
                    processedLevels.insert(l.id)
                }
            }
        }

        // Remove duplicates and sort by price
        return zones
            .filter { !$0.levels.isEmpty }
            .sorted { $0.price < $1.price }
    }

    // MARK: - Animation Helpers

    /// Generate animation for pivot level appearance
    static func appearanceAnimation() -> Animation {
        Animation.easeInOut(duration: 0.5)
    }

    /// Generate animation for pivot level status change
    static func statusChangeAnimation() -> Animation {
        Animation.easeInOut(duration: 0.3)
    }

    /// Generate animation for glow effect
    static func glowAnimation() -> Animation {
        Animation.easeInOut(duration: 1).repeatForever(autoreverses: true)
    }
}

// MARK: - Pivot Level Tooltip

/// Data for displaying pivot level information in a tooltip
struct PivotLevelTooltip {
    let period: Int
    let levelHigh: Double
    let levelLow: Double
    let highStatus: PivotStatus
    let lowStatus: PivotStatus
    let highBarsSincePivot: Int
    let lowBarsSincePivot: Int

    var highLabel: String {
        "High: \(PivotChartDrawing.formatPrice(levelHigh, decimals: 4)) (\(highStatus))"
    }

    var lowLabel: String {
        "Low: \(PivotChartDrawing.formatPrice(levelLow, decimals: 4)) (\(lowStatus))"
    }

    var statusSummary: String {
        if highStatus == .active || lowStatus == .active {
            return "🔵 ACTIVE"
        } else if highStatus == .support || lowStatus == .support {
            return "🟢 SUPPORT"
        } else if highStatus == .resistance || lowStatus == .resistance {
            return "🔴 RESISTANCE"
        } else {
            return "⚪ INACTIVE"
        }
    }
}

// MARK: - Pivot Strength Indicator

/// Calculates and represents pivot level strength
struct PivotStrength {
    let level: Double
    let strength: Double  // 0-1
    let status: PivotStatus
    let frequency: Int     // How many times this level was touched
    let avgDistance: Double // Average distance price traveled from level

    var strengthLabel: String {
        switch strength {
        case 0.8...1.0:
            return "Very Strong"
        case 0.6..<0.8:
            return "Strong"
        case 0.4..<0.6:
            return "Moderate"
        case 0.2..<0.4:
            return "Weak"
        default:
            return "Very Weak"
        }
    }

    var icon: String {
        switch strength {
        case 0.8...1.0:
            return "●●●●●"
        case 0.6..<0.8:
            return "●●●●○"
        case 0.4..<0.6:
            return "●●●○○"
        case 0.2..<0.4:
            return "●●○○○"
        default:
            return "●○○○○"
        }
    }
}

// MARK: - Helper Type

struct AnyShape: Shape {
    let path: (CGRect) -> Path

    init<S: Shape>(_ shape: S) {
        self.path = { shape.path(in: $0) }
    }

    func path(in rect: CGRect) -> Path {
        self.path(rect)
    }
}
