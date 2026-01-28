import Foundation

// MARK: - Pivot Statistical Metrics

/// Analyzes pivot levels for strength, frequency, and other statistical properties
struct PivotStatisticalMetrics {

    // MARK: - Metrics Calculation

    /// Calculate comprehensive statistics for a set of pivot levels
    static func analyzeMetrics(
        levels: [PivotLevel],
        bars: [OHLCBar],
        detectedPivots: (highs: [DetectedPivot], lows: [DetectedPivot])
    ) -> PivotMetricsReport {
        let highMetrics = calculatePivotMetrics(for: detectedPivots.highs, levels: levels, bars: bars, type: .high)
        let lowMetrics = calculatePivotMetrics(for: detectedPivots.lows, levels: levels, bars: bars, type: .low)

        return PivotMetricsReport(
            highPivotMetrics: highMetrics,
            lowPivotMetrics: lowMetrics,
            overallStrength: (highMetrics.strength + lowMetrics.strength) / 2,
            period: Date(),
            barCount: bars.count
        )
    }

    /// Calculate metrics for a specific pivot type
    private static func calculatePivotMetrics(
        for pivots: [DetectedPivot],
        levels: [PivotLevel],
        bars: [OHLCBar],
        type: PivotType
    ) -> PivotTypeMetrics {
        guard !bars.isEmpty else {
            return PivotTypeMetrics(type: type, pivotCount: 0, strength: 0)
        }

        let frequency = calculateFrequency(pivots)
        let strength = calculateStrength(pivots, bars: bars)
        let clustering = calculateClustering(pivots, bars: bars)
        let recency = calculateRecency(pivots, barCount: bars.count)

        return PivotTypeMetrics(
            type: type,
            pivotCount: pivots.count,
            strength: strength,
            frequency: frequency,
            clustering: clustering,
            recency: recency,
            averageSpacing: calculateAverageSpacing(pivots),
            consistency: calculateConsistency(pivots)
        )
    }

    // MARK: - Individual Metric Calculations

    /// Calculate pivot frequency (pivots per bar)
    private static func calculateFrequency(_ pivots: [DetectedPivot]) -> Double {
        guard !pivots.isEmpty else { return 0 }
        // Frequency = number of pivots / number of bars analyzed
        return min(Double(pivots.count) / 100.0, 1.0)  // Normalize to 0-1
    }

    /// Calculate pivot strength based on how often price bounces off them
    private static func calculateStrength(_ pivots: [DetectedPivot], bars: [OHLCBar]) -> Double {
        guard !pivots.isEmpty, !bars.isEmpty else { return 0 }

        var bounceCount = 0

        for (index, pivot) in pivots.enumerated() {
            guard pivot.index > 0, pivot.index < bars.count - 1 else { continue }

            let beforeBar = bars[pivot.index - 1]
            let afterBar = bars[pivot.index + 1]

            // Check if price bounced off the pivot
            let distBefore = abs(beforeBar.close - pivot.price)
            let distAfter = abs(afterBar.close - pivot.price)

            if distAfter < distBefore {
                bounceCount += 1
            }
        }

        return Double(bounceCount) / Double(pivots.count)
    }

    /// Calculate clustering of pivots (how close they are together)
    private static func calculateClustering(_ pivots: [DetectedPivot], bars: [OHLCBar]) -> Double {
        guard pivots.count > 1 else { return 0 }

        let indices = pivots.map { $0.index }
        let spacings = stride(from: 0, to: indices.count - 1, by: 1)
            .map { indices[$0 + 1] - indices[$0] }

        let avgSpacing = Double(spacings.reduce(0, +)) / Double(spacings.count)
        let minSpacing = Double(spacings.min() ?? 1)

        // Clustering = how much spacing varies (inverse of variance)
        let variance = spacings.map { pow(Double($0) - avgSpacing, 2) }.reduce(0, +) / Double(spacings.count)
        let standardDev = sqrt(variance)

        return max(0, 1.0 - (standardDev / avgSpacing))  // 0-1, higher = more clustered
    }

    /// Calculate recency (how recent are the pivots)
    private static func calculateRecency(_ pivots: [DetectedPivot], barCount: Int) -> Double {
        guard !pivots.isEmpty else { return 0 }

        let recentPivots = pivots.filter { $0.index > barCount - 50 }.count
        return Double(recentPivots) / Double(min(50, pivots.count))
    }

    /// Calculate average spacing between pivots
    private static func calculateAverageSpacing(_ pivots: [DetectedPivot]) -> Double {
        guard pivots.count > 1 else { return 0 }

        let indices = pivots.map { $0.index }
        let spacings = stride(from: 0, to: indices.count - 1, by: 1)
            .map { indices[$0 + 1] - indices[$0] }

        return Double(spacings.reduce(0, +)) / Double(spacings.count)
    }

    /// Calculate consistency of pivot spacing
    private static func calculateConsistency(_ pivots: [DetectedPivot]) -> Double {
        guard pivots.count > 2 else { return 0 }

        let indices = pivots.map { $0.index }
        let spacings = stride(from: 0, to: indices.count - 1, by: 1)
            .map { indices[$0 + 1] - indices[$0] }

        let avgSpacing = Double(spacings.reduce(0, +)) / Double(spacings.count)
        guard avgSpacing > 0 else { return 0 }

        let deviations = spacings.map { abs(Double($0) - avgSpacing) / avgSpacing }
        let avgDeviation = deviations.reduce(0, +) / Double(deviations.count)

        return max(0, 1.0 - avgDeviation)  // 0-1, higher = more consistent
    }

    // MARK: - Level-Specific Analysis

    /// Analyze a specific pivot level's effectiveness
    static func analyzePivotLevel(_ level: PivotLevel, bars: [OHLCBar]) -> PivotLevelAnalysis {
        let touchCount = countLevelTouches(level: level.levelHigh, bars: bars, tolerance: level.levelHigh * 0.001)
        let bounceCount = countLevelBounces(level: level.levelHigh, bars: bars, tolerance: level.levelHigh * 0.001)

        let effectiveness = touchCount > 0 ? Double(bounceCount) / Double(touchCount) : 0
        let distance = calculateDistanceFromCurrent(level: level.levelHigh, bars: bars)

        return PivotLevelAnalysis(
            level: level.levelHigh,
            touchCount: touchCount,
            bounceCount: bounceCount,
            effectiveness: min(effectiveness, 1.0),
            distanceFromCurrent: distance,
            lastTouchIndex: findLastTouch(level: level.levelHigh, bars: bars, tolerance: level.levelHigh * 0.001)
        )
    }

    /// Count how many times price touched a level
    private static func countLevelTouches(level: Double, bars: [OHLCBar], tolerance: Double) -> Int {
        bars.filter { bar in
            (bar.low <= level + tolerance && bar.low >= level - tolerance) ||
            (bar.high <= level + tolerance && bar.high >= level - tolerance)
        }.count
    }

    /// Count how many times price bounced off a level
    private static func countLevelBounces(level: Double, bars: [OHLCBar], tolerance: Double) -> Int {
        var bounces = 0

        for i in 1..<bars.count {
            let prevBar = bars[i - 1]
            let currentBar = bars[i]

            // Check for touch
            let touched = (prevBar.low <= level + tolerance && prevBar.low >= level - tolerance) ||
                         (prevBar.high <= level + tolerance && prevBar.high >= level - tolerance)

            if touched {
                // Check if price reversed after touch
                if prevBar.close < level && currentBar.close > level + tolerance {
                    bounces += 1  // Bounced up
                } else if prevBar.close > level && currentBar.close < level - tolerance {
                    bounces += 1  // Bounced down
                }
            }
        }

        return bounces
    }

    /// Calculate distance from current price to a level
    private static func calculateDistanceFromCurrent(level: Double, bars: [OHLCBar]) -> Double {
        guard let lastBar = bars.last else { return 0 }
        return abs(lastBar.close - level)
    }

    /// Find the index of the last time a level was touched
    private static func findLastTouch(level: Double, bars: [OHLCBar], tolerance: Double) -> Int? {
        for i in stride(from: bars.count - 1, through: 0, by: -1) {
            let bar = bars[i]
            if (bar.low <= level + tolerance && bar.low >= level - tolerance) ||
               (bar.high <= level + tolerance && bar.high >= level - tolerance) {
                return i
            }
        }
        return nil
    }

    // MARK: - Multi-Level Analysis

    /// Compare effectiveness of different period levels
    static func comparePeriodsEffectiveness(_ levels: [PivotLevel], bars: [OHLCBar]) -> [PeriodEffectiveness] {
        return levels.map { level in
            let highAnalysis = analyzePivotLevel(level, bars: bars)
            let analysis = PivotLevelAnalysis(
                level: level.levelLow,
                touchCount: countLevelTouches(level: level.levelLow, bars: bars, tolerance: level.levelLow * 0.001),
                bounceCount: countLevelBounces(level: level.levelLow, bars: bars, tolerance: level.levelLow * 0.001),
                effectiveness: 0,
                distanceFromCurrent: calculateDistanceFromCurrent(level: level.levelLow, bars: bars),
                lastTouchIndex: findLastTouch(level: level.levelLow, bars: bars, tolerance: level.levelLow * 0.001)
            )

            return PeriodEffectiveness(
                period: level.length,
                highLevelAnalysis: highAnalysis,
                lowLevelAnalysis: analysis,
                overallEffectiveness: (highAnalysis.effectiveness + analysis.effectiveness) / 2
            )
        }.sorted { $0.overallEffectiveness > $1.overallEffectiveness }
    }

    /// Identify confluence zones (multiple levels at similar prices)
    static func findConfluenceZones(_ levels: [PivotLevel], tolerance: Double = 0.005) -> [ConfluenceZone] {
        var zones: [ConfluenceZone] = []
        var processedIndices = Set<Int>()

        for i in 0..<levels.count {
            guard !processedIndices.contains(i) else { continue }

            var convergingLevels: [PivotLevel] = [levels[i]]
            let basePrice = levels[i].levelHigh > 0 ? levels[i].levelHigh : levels[i].levelLow

            for j in (i + 1)..<levels.count {
                guard !processedIndices.contains(j) else { continue }

                let comparePrice = levels[j].levelHigh > 0 ? levels[j].levelHigh : levels[j].levelLow
                if abs(comparePrice - basePrice) / basePrice < tolerance {
                    convergingLevels.append(levels[j])
                    processedIndices.insert(j)
                }
            }

            if convergingLevels.count > 1 {
                let avgPrice = convergingLevels.map { $0.levelHigh > 0 ? $0.levelHigh : $0.levelLow }.reduce(0, +) / Double(convergingLevels.count)
                zones.append(ConfluenceZone(price: avgPrice, convergingLevels: convergingLevels))
            }

            processedIndices.insert(i)
        }

        return zones.sorted { $0.convergingLevels.count > $1.convergingLevels.count }
    }
}

// MARK: - Data Structures

struct PivotMetricsReport {
    let highPivotMetrics: PivotTypeMetrics
    let lowPivotMetrics: PivotTypeMetrics
    let overallStrength: Double
    let period: Date
    let barCount: Int

    var summary: String {
        """
        📊 Pivot Metrics Report
        Overall Strength: \(String(format: "%.1f%%", overallStrength * 100))

        High Pivots:
        - Count: \(highPivotMetrics.pivotCount)
        - Strength: \(String(format: "%.1f%%", highPivotMetrics.strength * 100))
        - Frequency: \(String(format: "%.1f%%", highPivotMetrics.frequency * 100))

        Low Pivots:
        - Count: \(lowPivotMetrics.pivotCount)
        - Strength: \(String(format: "%.1f%%", lowPivotMetrics.strength * 100))
        - Frequency: \(String(format: "%.1f%%", lowPivotMetrics.frequency * 100))
        """
    }
}

struct PivotTypeMetrics {
    let type: PivotType
    let pivotCount: Int
    let strength: Double
    let frequency: Double
    let clustering: Double
    let recency: Double
    let averageSpacing: Double
    let consistency: Double

    var qualityRating: String {
        let score = (strength + consistency + recency) / 3
        switch score {
        case 0.8...1.0: return "Excellent"
        case 0.6..<0.8: return "Good"
        case 0.4..<0.6: return "Moderate"
        default: return "Fair"
        }
    }
}

struct PivotLevelAnalysis {
    let level: Double
    let touchCount: Int
    let bounceCount: Int
    let effectiveness: Double
    let distanceFromCurrent: Double
    let lastTouchIndex: Int?

    var qualityDescription: String {
        switch effectiveness {
        case 0.8...1.0: return "Very Effective"
        case 0.6..<0.8: return "Effective"
        case 0.4..<0.6: return "Moderately Effective"
        default: return "Weak"
        }
    }
}

struct PeriodEffectiveness {
    let period: Int
    let highLevelAnalysis: PivotLevelAnalysis
    let lowLevelAnalysis: PivotLevelAnalysis
    let overallEffectiveness: Double

    var ranking: String {
        switch overallEffectiveness {
        case 0.8...1.0: return "⭐⭐⭐⭐⭐"
        case 0.6..<0.8: return "⭐⭐⭐⭐"
        case 0.4..<0.6: return "⭐⭐⭐"
        case 0.2..<0.4: return "⭐⭐"
        default: return "⭐"
        }
    }
}

struct ConfluenceZone {
    let price: Double
    let convergingLevels: [PivotLevel]

    var strength: Int {
        convergingLevels.count
    }

    var description: String {
        "Confluence of \(strength) levels at \(String(format: "%.4f", price))"
    }
}
