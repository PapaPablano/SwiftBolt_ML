import Foundation

// MARK: - Optimized Pivot Detector with Caching

/// High-performance pivot detector with batch processing and caching
struct OptimizedPivotDetector {

    // MARK: - Cache Management

    private static var detectionCache: [String: CachedDetectionResult] = [:]
    private static var cacheHits: Int = 0
    private static var cacheMisses: Int = 0

    struct CachedDetectionResult {
        let highs: [DetectedPivot]
        let lows: [DetectedPivot]
        let timestamp: Date
        let barCount: Int
    }

    // MARK: - Main Detection Method

    /// Detect pivots with automatic caching
    /// - Parameters:
    ///   - bars: OHLC bar data
    ///   - periods: Array of periods to detect pivots for
    ///   - useCaching: Enable result caching
    /// - Returns: Dictionary mapping period to detected pivots
    static func detectMultiPeriodPivots(
        bars: [OHLCBar],
        periods: [Int],
        useCaching: Bool = true
    ) -> [Int: (highs: [DetectedPivot], lows: [DetectedPivot])] {
        var results: [Int: (highs: [DetectedPivot], lows: [DetectedPivot])] = [:]

        for period in periods {
            if useCaching, let cached = getCachedResult(for: period, barCount: bars.count) {
                results[period] = (highs: cached.highs, lows: cached.lows)
            } else {
                let detected = detectPivotsOptimized(bars: bars, period: period)
                results[period] = detected

                if useCaching {
                    cacheResult(detected, for: period, barCount: bars.count)
                }
            }
        }

        return results
    }

    // MARK: - Optimized Detection Algorithm

    /// Optimized pivot detection using early termination
    private static func detectPivotsOptimized(
        bars: [OHLCBar],
        period: Int
    ) -> (highs: [DetectedPivot], lows: [DetectedPivot]) {
        var pivotHighs: [DetectedPivot] = []
        var pivotLows: [DetectedPivot] = []

        guard bars.count > period * 2 else { return ([], []) }

        // Precompute price arrays for faster access
        let highs = bars.map { $0.high }
        let lows = bars.map { $0.low }
        let timestamps = bars.map { $0.ts }

        // Detect pivots using optimized loop
        for i in period..<(bars.count - period) {
            // Pivot high detection with early termination
            var isHigh = true
            let currentHigh = highs[i]

            // Check backward
            for j in stride(from: i - 1, through: i - period, by: -1) {
                if highs[j] > currentHigh {
                    isHigh = false
                    break
                }
            }

            // Check forward only if backward check passed
            if isHigh {
                for j in (i + 1)...(i + period) {
                    if highs[j] > currentHigh {
                        isHigh = false
                        break
                    }
                }
            }

            if isHigh {
                pivotHighs.append(DetectedPivot(index: i, price: currentHigh, date: timestamps[i], type: .high))
            }

            // Pivot low detection with early termination
            var isLow = true
            let currentLow = lows[i]

            // Check backward
            for j in stride(from: i - 1, through: i - period, by: -1) {
                if lows[j] < currentLow {
                    isLow = false
                    break
                }
            }

            // Check forward only if backward check passed
            if isLow {
                for j in (i + 1)...(i + period) {
                    if lows[j] < currentLow {
                        isLow = false
                        break
                    }
                }
            }

            if isLow {
                pivotLows.append(DetectedPivot(index: i, price: currentLow, date: timestamps[i], type: .low))
            }
        }

        return (pivotHighs, pivotLows)
    }

    // MARK: - Batch Processing

    /// Process multiple periods efficiently in a single pass
    static func detectPivotsInBatch(
        bars: [OHLCBar],
        periods: [Int]
    ) -> [Int: (highs: [DetectedPivot], lows: [DetectedPivot])] {
        let sortedPeriods = periods.sorted()
        let maxPeriod = sortedPeriods.last ?? 0

        guard bars.count > maxPeriod * 2 else {
            return [:]
        }

        // Precompute price arrays once
        let highs = bars.map { $0.high }
        let lows = bars.map { $0.low }
        let timestamps = bars.map { $0.ts }

        var results: [Int: (highs: [DetectedPivot], lows: [DetectedPivot])] = [:]

        // Initialize result arrays for each period
        for period in sortedPeriods {
            results[period] = ([], [])
        }

        // Single pass through bars
        for i in maxPeriod..<(bars.count - maxPeriod) {
            let currentHigh = highs[i]
            let currentLow = lows[i]

            // Check each period
            for period in sortedPeriods {
                // Check pivot high
                var isHigh = true
                for j in (i - period)..<i {
                    if highs[j] > currentHigh {
                        isHigh = false
                        break
                    }
                }
                if isHigh {
                    for j in (i + 1)...(i + period) {
                        if highs[j] > currentHigh {
                            isHigh = false
                            break
                        }
                    }
                }

                if isHigh {
                    results[period]!.highs.append(DetectedPivot(index: i, price: currentHigh, date: timestamps[i], type: .high))
                }

                // Check pivot low
                var isLow = true
                for j in (i - period)..<i {
                    if lows[j] < currentLow {
                        isLow = false
                        break
                    }
                }
                if isLow {
                    for j in (i + 1)...(i + period) {
                        if lows[j] < currentLow {
                            isLow = false
                            break
                        }
                    }
                }

                if isLow {
                    results[period]!.lows.append(DetectedPivot(index: i, price: currentLow, date: timestamps[i], type: .low))
                }
            }
        }

        return results
    }

    // MARK: - Cache Operations

    private static func getCacheKey(for period: Int, barCount: Int) -> String {
        "pivot_\(period)_\(barCount)"
    }

    private static func getCachedResult(for period: Int, barCount: Int) -> CachedDetectionResult? {
        let key = getCacheKey(for: period, barCount: barCount)

        if let cached = detectionCache[key] {
            // Invalidate if bars have been added (cache is only valid if bar count matches)
            if cached.barCount == barCount {
                cacheHits += 1
                return cached
            }
        }

        cacheMisses += 1
        return nil
    }

    private static func cacheResult(
        _ result: (highs: [DetectedPivot], lows: [DetectedPivot]),
        for period: Int,
        barCount: Int
    ) {
        let key = getCacheKey(for: period, barCount: barCount)
        detectionCache[key] = CachedDetectionResult(
            highs: result.highs,
            lows: result.lows,
            timestamp: Date(),
            barCount: barCount
        )

        // Keep cache size under control (max 100 entries)
        if detectionCache.count > 100 {
            let oldestKey = detectionCache.min { $0.value.timestamp < $1.value.timestamp }?.key
            if let key = oldestKey {
                detectionCache.removeValue(forKey: key)
            }
        }
    }

    /// Clear cache (useful after data reload)
    static func clearCache() {
        detectionCache.removeAll()
        cacheHits = 0
        cacheMisses = 0
    }

    /// Get cache statistics
    static func cacheStats() -> (hits: Int, misses: Int, hitRate: Double) {
        let total = cacheHits + cacheMisses
        let hitRate = total > 0 ? Double(cacheHits) / Double(total) : 0
        return (hits: cacheHits, misses: cacheMisses, hitRate: hitRate)
    }

    // MARK: - Filtering & Aggregation

    /// Get the most recent pivot for each period
    static func getRecentPivots(
        from multiPeriodResults: [Int: (highs: [DetectedPivot], lows: [DetectedPivot])]
    ) -> [Int: (high: DetectedPivot?, low: DetectedPivot?)] {
        var recent: [Int: (high: DetectedPivot?, low: DetectedPivot?)] = [:]

        for (period, (highs, lows)) in multiPeriodResults {
            recent[period] = (high: highs.last, low: lows.last)
        }

        return recent
    }

    /// Filter pivots by price range
    static func filterByPriceRange(
        pivots: [DetectedPivot],
        minPrice: Double,
        maxPrice: Double
    ) -> [DetectedPivot] {
        pivots.filter { $0.price >= minPrice && $0.price <= maxPrice }
    }

    /// Filter pivots by time range
    static func filterByTimeRange(
        pivots: [DetectedPivot],
        startDate: Date,
        endDate: Date
    ) -> [DetectedPivot] {
        pivots.filter { $0.date >= startDate && $0.date <= endDate }
    }

    /// Aggregate pivots across periods
    static func aggregatePivots(
        from multiPeriodResults: [Int: (highs: [DetectedPivot], lows: [DetectedPivot])]
    ) -> (allHighs: [DetectedPivot], allLows: [DetectedPivot]) {
        var allHighs: [DetectedPivot] = []
        var allLows: [DetectedPivot] = []

        for (_, (highs, lows)) in multiPeriodResults {
            allHighs.append(contentsOf: highs)
            allLows.append(contentsOf: lows)
        }

        return (
            allHighs: allHighs.sorted { $0.index < $1.index },
            allLows: allLows.sorted { $0.index < $1.index }
        )
    }

    // MARK: - Performance Metrics

    struct PerformanceMetrics {
        let detectionTimeMs: Int
        let barCount: Int
        let periodCount: Int
        let pivotCount: Int
        let cacheHitRate: Double

        var summary: String {
            """
            ⚡ Performance Metrics
            Detection Time: \(detectionTimeMs)ms
            Bars Processed: \(barCount)
            Periods Analyzed: \(periodCount)
            Pivots Found: \(pivotCount)
            Cache Hit Rate: \(String(format: "%.1f%%", cacheHitRate * 100))
            """
        }
    }

    /// Measure detection performance
    static func measurePerformance(
        bars: [OHLCBar],
        periods: [Int]
    ) -> PerformanceMetrics {
        let startTime = Date()

        let results = detectMultiPeriodPivots(bars: bars, periods: periods)
        let totalPivots = results.values.reduce(0) { $0 + $1.highs.count + $1.lows.count }

        let elapsed = Int(Date().timeIntervalSince(startTime) * 1000)
        let stats = cacheStats()

        return PerformanceMetrics(
            detectionTimeMs: elapsed,
            barCount: bars.count,
            periodCount: periods.count,
            pivotCount: totalPivots,
            cacheHitRate: stats.hitRate
        )
    }
}
