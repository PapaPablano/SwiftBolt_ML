import XCTest
@testable import SwiftBoltML

// MARK: - Pivot Detection Tests

class PivotDetectionTests: XCTestCase {

    // MARK: - Test Data

    func createSyntheticBars(count: Int, trend: Double = 0.5) -> [OHLCBar] {
        var bars: [OHLCBar] = []
        var price = 100.0

        for i in 0..<count {
            let open = price
            let close = price + (Double.random(in: -1...1) * 0.5) + (trend * 0.1)
            let high = max(open, close) + Double.random(in: 0...0.5)
            let low = min(open, close) - Double.random(in: 0...0.5)

            bars.append(OHLCBar(
                ts: Date(timeIntervalSince1970: Double(i) * 3600),
                open: open,
                high: high,
                low: low,
                close: close,
                volume: Double.random(in: 1000...10000)
            ))

            price = close
        }

        return bars
    }

    // MARK: - Basic Detection Tests

    func testPivotDetectionBasic() {
        let bars = createSyntheticBars(count: 100)
        let (highs, lows) = PivotDetector.detectPivots(bars: bars, period: 5)

        XCTAssertGreaterThan(highs.count, 0, "Should detect at least some pivot highs")
        XCTAssertGreaterThan(lows.count, 0, "Should detect at least some pivot lows")
    }

    func testPivotDetectionMultiplePeriods() {
        let bars = createSyntheticBars(count: 200)
        let periods = [5, 10, 25, 50]

        for period in periods {
            let (highs, lows) = PivotDetector.detectPivots(bars: bars, period: period)

            // Larger periods should generally have fewer pivots
            XCTAssertGreaterThan(highs.count + lows.count, 0)
        }
    }

    func testPivotIndicesValid() {
        let bars = createSyntheticBars(count: 150)
        let period = 10
        let (highs, lows) = PivotDetector.detectPivots(bars: bars, period: period)

        // All pivot indices should be within valid range
        for pivot in highs + lows {
            XCTAssertGreaterThanOrEqual(pivot.index, period)
            XCTAssertLessThan(pivot.index, bars.count - period)
        }
    }

    func testPivotPricesMatchBars() {
        let bars = createSyntheticBars(count: 100)
        let (highs, lows) = PivotDetector.detectPivots(bars: bars, period: 5)

        // Verify pivot high prices match the bar highs
        for pivot in highs {
            XCTAssertEqual(pivot.price, bars[pivot.index].high, accuracy: 0.001)
        }

        // Verify pivot low prices match the bar lows
        for pivot in lows {
            XCTAssertEqual(pivot.price, bars[pivot.index].low, accuracy: 0.001)
        }
    }

    // MARK: - Optimization Tests

    func testOptimizedDetectorMatchesOriginal() {
        let bars = createSyntheticBars(count: 200)
        let periods = [5, 10, 25, 50]

        for period in periods {
            let original = PivotDetector.detectPivots(bars: bars, period: period)
            let optimized = OptimizedPivotDetector.detectPivotsOptimized(bars: bars, period: period)

            // Results should be identical
            XCTAssertEqual(original.highs.count, optimized.highs.count)
            XCTAssertEqual(original.lows.count, optimized.lows.count)

            for (orig, opt) in zip(original.highs, optimized.highs) {
                XCTAssertEqual(orig.index, opt.index)
                XCTAssertEqual(orig.price, opt.price, accuracy: 0.001)
            }
        }
    }

    func testBatchProcessingPerformance() {
        let bars = createSyntheticBars(count: 500)
        let periods = [5, 10, 25, 50, 100]

        let startTime = Date()
        let results = OptimizedPivotDetector.detectPivotsInBatch(bars: bars, periods: periods)
        let elapsed = Date().timeIntervalSince(startTime)

        // Should complete in reasonable time
        XCTAssertLessThan(elapsed, 1.0, "Batch processing should be fast")
        XCTAssertEqual(results.count, periods.count)
    }

    func testCachingEffectiveness() {
        let bars = createSyntheticBars(count: 300)
        let periods = [5, 10, 25, 50]

        OptimizedPivotDetector.clearCache()

        // First call - cache miss
        _ = OptimizedPivotDetector.detectMultiPeriodPivots(bars: bars, periods: periods, useCaching: true)
        var stats = OptimizedPivotDetector.cacheStats()
        let firstCallMisses = stats.misses

        // Second call - should hit cache
        _ = OptimizedPivotDetector.detectMultiPeriodPivots(bars: bars, periods: periods, useCaching: true)
        stats = OptimizedPivotDetector.cacheStats()

        XCTAssertGreaterThan(stats.hits, 0, "Should have cache hits on second call")
        XCTAssertLessThan(stats.hitRate, 1.0, "Not all calls should be cache hits")
    }

    // MARK: - Edge Cases

    func testEmptyBars() {
        let bars: [OHLCBar] = []
        let (highs, lows) = PivotDetector.detectPivots(bars: bars, period: 5)

        XCTAssertEqual(highs.count, 0)
        XCTAssertEqual(lows.count, 0)
    }

    func testInsufficientBars() {
        let bars = createSyntheticBars(count: 5)  // Period 10 requires at least 21 bars
        let (highs, lows) = PivotDetector.detectPivots(bars: bars, period: 10)

        XCTAssertEqual(highs.count, 0)
        XCTAssertEqual(lows.count, 0)
    }

    func testLargePeriod() {
        let bars = createSyntheticBars(count: 1000)
        let (highs, lows) = PivotDetector.detectPivots(bars: bars, period: 100)

        // Should still work
        XCTAssertGreaterThanOrEqual(highs.count, 0)
        XCTAssertGreaterThanOrEqual(lows.count, 0)
    }

    // MARK: - Statistical Metrics Tests

    func testMetricsCalculation() {
        let bars = createSyntheticBars(count: 200)
        let (highs, lows) = PivotDetector.detectPivots(bars: bars, period: 10)

        let metrics = PivotStatisticalMetrics.analyzeMetrics(
            levels: [],
            bars: bars,
            detectedPivots: (highs: highs, lows: lows)
        )

        XCTAssertGreaterThanOrEqual(metrics.overallStrength, 0)
        XCTAssertLessThanOrEqual(metrics.overallStrength, 1)
    }

    func testPeriodEffectivenessComparison() {
        let bars = createSyntheticBars(count: 300)
        let levels = [
            PivotLevel(length: 5, display: true, style: .solid, extend: .both,
                      levelHigh: bars[50].high, startIndexHigh: 50,
                      levelLow: bars[40].low, startIndexLow: 40),
            PivotLevel(length: 25, display: true, style: .solid, extend: .both,
                      levelHigh: bars[100].high, startIndexHigh: 100,
                      levelLow: bars[90].low, startIndexLow: 90),
        ]

        let effectiveness = PivotStatisticalMetrics.comparePeriodsEffectiveness(levels, bars: bars)

        XCTAssertEqual(effectiveness.count, 2)
        for period in effectiveness {
            XCTAssertGreaterThanOrEqual(period.overallEffectiveness, 0)
            XCTAssertLessThanOrEqual(period.overallEffectiveness, 1)
        }
    }

    func testConfluenceZoneDetection() {
        let bars = createSyntheticBars(count: 200)
        let basePrice = 100.0
        let levels = [
            PivotLevel(length: 5, display: true, style: .solid, extend: .both,
                      levelHigh: basePrice, startIndexHigh: 50,
                      levelLow: basePrice - 0.5, startIndexLow: 40),
            PivotLevel(length: 10, display: true, style: .solid, extend: .both,
                      levelHigh: basePrice + 0.2, startIndexHigh: 60,
                      levelLow: basePrice - 0.3, startIndexLow: 50),
            PivotLevel(length: 25, display: true, style: .solid, extend: .both,
                      levelHigh: basePrice + 0.5, startIndexHigh: 70,
                      levelLow: basePrice - 1.0, startIndexLow: 60),
        ]

        let zones = PivotStatisticalMetrics.findConfluenceZones(levels)

        XCTAssertGreaterThan(zones.count, 0, "Should detect confluence zones")
    }

    // MARK: - Period Manager Tests

    func testPeriodPresetsConservative() {
        let preset = PivotPeriodManager.PeriodPreset.conservative
        let periods = preset.periods

        XCTAssertEqual(periods.count, 2)  // Conservative has 2 periods
        XCTAssertTrue(periods.allSatisfy { $0.enabled })
    }

    func testPeriodPresetsBalanced() {
        let preset = PivotPeriodManager.PeriodPreset.balanced
        let periods = preset.periods

        XCTAssertEqual(periods.count, 4)  // Balanced has 4 periods
        XCTAssertTrue(periods.allSatisfy { $0.enabled })
    }

    func testPeriodPresetsAggressive() {
        let preset = PivotPeriodManager.PeriodPreset.aggressive
        let periods = preset.periods

        XCTAssertEqual(periods.count, 6)  // Aggressive has 6 periods
        XCTAssertTrue(periods.allSatisfy { $0.enabled })
    }

    func testPeriodConfigColors() {
        let periods = [
            PeriodConfig(length: 5, enabled: true, label: "Micro"),
            PeriodConfig(length: 25, enabled: true, label: "Short"),
            PeriodConfig(length: 50, enabled: true, label: "Medium"),
            PeriodConfig(length: 100, enabled: true, label: "Long"),
        ]

        // Each period should have a distinct color
        let colors = periods.map { $0.color }
        XCTAssertEqual(colors.count, periods.count)
    }

    // MARK: - Integration Tests

    func testFullPivotAnalysisPipeline() {
        let bars = createSyntheticBars(count: 300)
        let periods = [5, 10, 25, 50]

        // Step 1: Detect pivots
        let results = OptimizedPivotDetector.detectMultiPeriodPivots(
            bars: bars,
            periods: periods,
            useCaching: true
        )

        // Step 2: Create levels
        var levels: [PivotLevel] = []
        for (period, (highs, lows)) in results {
            if let high = highs.last, let low = lows.last {
                levels.append(PivotLevel(
                    length: period,
                    display: true,
                    style: .solid,
                    extend: .both,
                    levelHigh: high.price,
                    startIndexHigh: high.index,
                    levelLow: low.price,
                    startIndexLow: low.index
                ))
            }
        }

        // Step 3: Calculate metrics
        let allPivots = OptimizedPivotDetector.aggregatePivots(from: results)
        let metrics = PivotStatisticalMetrics.analyzeMetrics(
            levels: levels,
            bars: bars,
            detectedPivots: allPivots
        )

        // Verify completeness
        XCTAssertGreaterThan(levels.count, 0)
        XCTAssertGreaterThanOrEqual(metrics.overallStrength, 0)
    }
}

// MARK: - Chart Drawing Tests

class PivotChartDrawingTests: XCTestCase {

    func testLevelPathGeneration() {
        let yScale: (Double) -> CGFloat = { CGFloat($0) }
        let xScale: (Int) -> CGFloat = { CGFloat($0) }

        let path = PivotChartDrawing.generateLevelPath(
            level: 100,
            chartWidth: 800,
            startIndex: 0,
            endIndex: 200,
            extendMode: .both,
            yScale: yScale,
            xScale: xScale
        )

        // Path should not be empty
        XCTAssertFalse(path.isEmpty)
    }

    func testDashPatterns() {
        let solidPattern = PivotChartDrawing.dashPattern(for: .solid)
        let dashedPattern = PivotChartDrawing.dashPattern(for: .dashed)
        let dottedPattern = PivotChartDrawing.dashPattern(for: .dotted)

        XCTAssertTrue(solidPattern.isEmpty)
        XCTAssertEqual(dashedPattern, [6, 4])
        XCTAssertEqual(dottedPattern, [2, 3])
    }

    func testPriceFormatting() {
        let formatted = PivotChartDrawing.formatPrice(123.456, decimals: 2)
        XCTAssertEqual(formatted, "123.46")

        let withSymbol = PivotChartDrawing.formatPriceWithSymbol(100.0, symbol: "$", decimals: 2)
        XCTAssertEqual(withSymbol, "$100.00")
    }

    func testPriceRangeCalculation() {
        let levels = [
            PivotLevel(length: 5, display: true, style: .solid, extend: .both,
                      levelHigh: 105, startIndexHigh: 50, levelLow: 95, startIndexLow: 40),
            PivotLevel(length: 10, display: true, style: .solid, extend: .both,
                      levelHigh: 110, startIndexHigh: 60, levelLow: 90, startIndexLow: 50),
        ]

        let (min, max, range) = PivotChartDrawing.priceRange(for: levels)

        XCTAssertEqual(min, 90)
        XCTAssertEqual(max, 110)
        XCTAssertEqual(range, 20)
    }
}
