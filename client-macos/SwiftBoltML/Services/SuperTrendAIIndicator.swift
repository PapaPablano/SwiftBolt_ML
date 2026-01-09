import Foundation
import SwiftUI
import Combine

// MARK: - K-Means Clustering Engine

/// K-Means clustering for adaptive parameter optimization
struct KMeansClustering {

    /// Cluster result with centroid and member indices
    struct Cluster {
        var centroid: Double
        var memberIndices: [Int]

        var isEmpty: Bool { memberIndices.isEmpty }
        var count: Int { memberIndices.count }
    }

    /// Run K-Means clustering on 1D data with multiple runs for robustness
    /// - Parameters:
    ///   - data: Array of values to cluster
    ///   - k: Number of clusters (typically 3: below-average, average, exceptional)
    ///   - maxIterations: Maximum iterations for convergence
    ///   - numRuns: Number of times to run K-means (keeps best result)
    ///   - initialCentroids: Optional initial centroid values (uses quartiles if nil)
    /// - Returns: Array of K clusters sorted by centroid value (ascending)
    static func cluster(
        data: [Double],
        k: Int = 3,
        maxIterations: Int = 100,
        numRuns: Int = 3,
        initialCentroids: [Double]? = nil
    ) -> [Cluster] {
        guard data.count >= k else {
            // Not enough data points, return single cluster
            return [Cluster(centroid: data.first ?? 0, memberIndices: Array(0..<data.count))]
        }

        var bestClusters: [Cluster] = []
        var bestInertia = Double.infinity

        // Run K-means multiple times and keep best result (lowest inertia)
        for run in 0..<numRuns {
            let clusters = runKMeans(
                data: data,
                k: k,
                maxIterations: maxIterations,
                initialCentroids: run == 0 ? initialCentroids : nil
            )

            // Calculate inertia (sum of squared distances to centroids)
            let inertia = calculateInertia(data: data, clusters: clusters)

            if inertia < bestInertia {
                bestInertia = inertia
                bestClusters = clusters
            }
        }

        return bestClusters
    }

    /// Single K-means run
    private static func runKMeans(
        data: [Double],
        k: Int,
        maxIterations: Int,
        initialCentroids: [Double]?
    ) -> [Cluster] {
        // Initialize centroids using quartiles for faster convergence
        var centroids: [Double]
        if let initial = initialCentroids, initial.count == k {
            centroids = initial
        } else {
            let sorted = data.sorted()
            centroids = (0..<k).map { i in
                let idx = Int(Double(sorted.count - 1) * Double(i) / Double(k - 1))
                return sorted[idx]
            }
        }

        var clusters = [Cluster](repeating: Cluster(centroid: 0, memberIndices: []), count: k)

        for _ in 0..<maxIterations {
            // Step 1: Assign each data point to nearest centroid
            var newClusters = (0..<k).map { Cluster(centroid: centroids[$0], memberIndices: []) }

            for (idx, value) in data.enumerated() {
                var minDistance = Double.infinity
                var nearestCluster = 0

                for (clusterIdx, centroid) in centroids.enumerated() {
                    let distance = abs(value - centroid)
                    if distance < minDistance {
                        minDistance = distance
                        nearestCluster = clusterIdx
                    }
                }

                newClusters[nearestCluster].memberIndices.append(idx)
            }

            // Step 2: Update centroids to mean of assigned points
            var converged = true
            for i in 0..<k {
                if newClusters[i].isEmpty {
                    // Keep old centroid for empty clusters
                    newClusters[i].centroid = centroids[i]
                } else {
                    let sum = newClusters[i].memberIndices.reduce(0.0) { $0 + data[$1] }
                    let newCentroid = sum / Double(newClusters[i].count)

                    if abs(newCentroid - centroids[i]) > 1e-6 {
                        converged = false
                    }

                    newClusters[i].centroid = newCentroid
                    centroids[i] = newCentroid
                }
            }

            clusters = newClusters

            if converged {
                break
            }
        }

        // Sort clusters by centroid value (ascending)
        // Index 0 = lowest performers, Index k-1 = highest performers
        return clusters.sorted { $0.centroid < $1.centroid }
    }

    /// Calculate inertia (sum of squared distances to centroids)
    /// Lower inertia = better clustering
    private static func calculateInertia(data: [Double], clusters: [Cluster]) -> Double {
        var inertia = 0.0
        for cluster in clusters {
            for memberIdx in cluster.memberIndices {
                let distance = data[memberIdx] - cluster.centroid
                inertia += distance * distance
            }
        }
        return inertia
    }
}

// MARK: - Factor Performance Tracker

/// Tracks performance of each SuperTrend factor configuration
struct FactorPerformance {
    let factor: Double
    var performance: Double = 0.0
    var lastSignal: Int = 0  // 1 = bullish, -1 = bearish, 0 = none
}

// MARK: - SuperTrend AI Result

/// Result from SuperTrend AI calculation
struct SuperTrendAIResult {
    let supertrend: [Double?]           // Adaptive SuperTrend line
    let trend: [Int]                    // 1 = bullish, -1 = bearish
    let adaptiveFactor: [Double]        // Factor used at each bar
    let performanceMetrics: [Double?]   // Performance metric at each bar
    let adaptiveMA: [Double?]           // Adaptive moving average of SuperTrend
    let clusterAssignments: [Int]       // Which cluster each bar's factor came from
}

// MARK: - SuperTrend AI Indicator

/// SuperTrend AI with K-Means Clustering for Adaptive Factor Selection
/// Based on the hypothesis: "The optimal configuration at time t comes from
/// the weighted average of top-performing instance settings"
@MainActor
class SuperTrendAIIndicator: ObservableObject {

    // MARK: - Settings

    struct Settings {
        // ATR Configuration
        var atrLength: Int = 10

        // Factor Range (tests multiple factors within this range)
        var factorMin: Double = 1.0
        var factorMax: Double = 5.0
        var factorStep: Double = 0.5

        // Performance Memory (α in the EMA formula)
        // Higher values = longer-term performance tracking
        // P(t) = P(t-1) + α * (ΔC(t) × S(t-1) - P(t-1))
        var performanceMemory: Double = 0.1  // α between 0 and 1

        // Clustering
        var numClusters: Int = 3  // K=3: below-average, average, exceptional
        var fromCluster: Int = 2  // 0=worst, 1=middle, 2=best (exceptional performers)
        var maxIterations: Int = 100
        var numRuns: Int = 3  // Run K-means multiple times, keep best (LuxAlgo robustness)

        // Adaptive Moving Average
        var adaptiveMALength: Int = 14

        // Display
        var showPerformanceMetrics: Bool = true
        var showAdaptiveMA: Bool = true
    }

    // MARK: - Published Properties

    @Published var result: SuperTrendAIResult?
    @Published var settings: Settings = Settings()
    @Published var isLoading: Bool = false
    @Published var errorMessage: String?

    // Current state
    @Published var currentFactor: Double = 3.0
    @Published var currentTrend: Int = 0
    @Published var currentPerformance: Double = 0.0
    @Published var currentCluster: Int = 0

    // MARK: - Private Properties

    private var bars: [OHLCBar] = []
    private var factorPerformances: [FactorPerformance] = []

    // MARK: - Computed Properties

    /// All factors being tested
    var testFactors: [Double] {
        var factors: [Double] = []
        var factor = settings.factorMin
        while factor <= settings.factorMax {
            factors.append(factor)
            factor += settings.factorStep
        }
        return factors
    }

    // MARK: - Public Methods

    /// Calculate SuperTrend AI with adaptive factor selection
    func calculate(bars: [OHLCBar]) {
        guard !bars.isEmpty else {
            result = nil
            return
        }

        isLoading = true
        errorMessage = nil
        self.bars = bars

        // Initialize factor performances
        initializeFactorPerformances()

        // Calculate ATR for all bars
        let atrValues = calculateATR(bars: bars)

        // Run SuperTrend for all factors and track performance
        var allFactorResults: [Double: SuperTrendFactorResult] = [:]
        for factor in testFactors {
            allFactorResults[factor] = calculateSuperTrendForFactor(
                bars: bars,
                atr: atrValues,
                factor: factor
            )
        }

        // Calculate adaptive SuperTrend using K-Means clustering
        let adaptiveResult = calculateAdaptiveSuperTrend(
            bars: bars,
            atr: atrValues,
            allFactorResults: allFactorResults
        )

        result = adaptiveResult

        // Update current state
        if let lastTrend = adaptiveResult.trend.last {
            currentTrend = lastTrend
        }
        if let lastFactor = adaptiveResult.adaptiveFactor.last {
            currentFactor = lastFactor
        }
        if let lastPerf = adaptiveResult.performanceMetrics.last {
            currentPerformance = lastPerf ?? 0
        }
        if let lastCluster = adaptiveResult.clusterAssignments.last {
            currentCluster = lastCluster
        }

        isLoading = false
    }

    // MARK: - Private Methods

    private func initializeFactorPerformances() {
        factorPerformances = testFactors.map { FactorPerformance(factor: $0) }
    }

    /// Calculate ATR for all bars
    private func calculateATR(bars: [OHLCBar]) -> [Double] {
        guard bars.count > 1 else {
            return Array(repeating: 0, count: bars.count)
        }

        var trueRanges: [Double] = []
        for i in 0..<bars.count {
            if i == 0 {
                trueRanges.append(bars[i].high - bars[i].low)
            } else {
                let tr = max(
                    bars[i].high - bars[i].low,
                    abs(bars[i].high - bars[i - 1].close),
                    abs(bars[i].low - bars[i - 1].close)
                )
                trueRanges.append(tr)
            }
        }

        // Calculate ATR using Wilder's smoothing
        var atr: [Double] = Array(repeating: 0, count: bars.count)
        guard bars.count > settings.atrLength else { return atr }

        var currentATR = trueRanges.prefix(settings.atrLength).reduce(0, +) / Double(settings.atrLength)

        for i in settings.atrLength..<bars.count {
            currentATR = (currentATR * Double(settings.atrLength - 1) + trueRanges[i]) / Double(settings.atrLength)
            atr[i] = currentATR
        }

        // Fill in early values
        for i in 0..<settings.atrLength {
            atr[i] = currentATR
        }

        return atr
    }

    /// SuperTrend result for a single factor
    private struct SuperTrendFactorResult {
        let supertrend: [Double]
        let trend: [Int]  // 1 = bullish, -1 = bearish
    }

    /// Calculate SuperTrend for a specific factor
    private func calculateSuperTrendForFactor(
        bars: [OHLCBar],
        atr: [Double],
        factor: Double
    ) -> SuperTrendFactorResult {
        var supertrend: [Double] = []
        var trend: [Int] = []
        var finalUpper: [Double] = []
        var finalLower: [Double] = []

        for i in 0..<bars.count {
            let hl2 = (bars[i].high + bars[i].low) / 2
            let atrValue = atr[i]

            let basicUpper = hl2 + factor * atrValue
            let basicLower = hl2 - factor * atrValue

            if i == 0 {
                finalUpper.append(basicUpper)
                finalLower.append(basicLower)
                trend.append(1)  // Start bullish
                supertrend.append(basicLower)
            } else {
                let close = bars[i].close
                let prevClose = bars[i - 1].close
                let prevTrend = trend[i - 1]

                // Upper band can only move down
                let newUpper: Double
                if basicUpper < finalUpper[i - 1] || prevClose > finalUpper[i - 1] {
                    newUpper = basicUpper
                } else {
                    newUpper = finalUpper[i - 1]
                }

                // Lower band can only move up
                let newLower: Double
                if basicLower > finalLower[i - 1] || prevClose < finalLower[i - 1] {
                    newLower = basicLower
                } else {
                    newLower = finalLower[i - 1]
                }

                finalUpper.append(newUpper)
                finalLower.append(newLower)

                // Determine trend
                let currentTrend: Int
                if prevTrend == 1 {
                    currentTrend = close < newLower ? -1 : 1
                } else {
                    currentTrend = close > newUpper ? 1 : -1
                }

                trend.append(currentTrend)
                supertrend.append(currentTrend == 1 ? newLower : newUpper)
            }
        }

        return SuperTrendFactorResult(supertrend: supertrend, trend: trend)
    }

    /// Calculate adaptive SuperTrend using K-Means clustering
    private func calculateAdaptiveSuperTrend(
        bars: [OHLCBar],
        atr: [Double],
        allFactorResults: [Double: SuperTrendFactorResult]
    ) -> SuperTrendAIResult {
        let factors = testFactors
        let α = settings.performanceMemory

        // Performance tracking for each factor
        // P(t, factor) = P(t-1, factor) + α * (ΔC(t) × S(t-1, factor) - P(t-1, factor))
        var performances: [[Double]] = factors.map { _ in Array(repeating: 0.0, count: bars.count) }

        // Initialize performance tracking
        for i in 1..<bars.count {
            let deltaC = bars[i].close - bars[i - 1].close

            for (fIdx, factor) in factors.enumerated() {
                guard let factorResult = allFactorResults[factor] else { continue }

                // Signal from previous bar
                let prevSignal = Double(factorResult.trend[i - 1])

                // Performance update: EMA of (price change × signal direction)
                let prevPerf = performances[fIdx][i - 1]
                let newPerf = prevPerf + α * (deltaC * prevSignal - prevPerf)
                performances[fIdx][i] = newPerf
            }
        }

        // Adaptive SuperTrend calculation
        var adaptiveSupertrend: [Double?] = Array(repeating: nil, count: bars.count)
        var adaptiveTrend: [Int] = Array(repeating: 0, count: bars.count)
        var adaptiveFactor: [Double] = Array(repeating: factors[factors.count / 2], count: bars.count)
        var performanceMetrics: [Double?] = Array(repeating: nil, count: bars.count)
        var clusterAssignments: [Int] = Array(repeating: 0, count: bars.count)

        // Guard: ensure we have enough bars for the range
        let startIndex = max(1, settings.atrLength)
        guard startIndex < bars.count else {
            // Not enough bars for calculation
            return SuperTrendAIResult(
                supertrend: adaptiveSupertrend,
                trend: adaptiveTrend,
                adaptiveFactor: adaptiveFactor,
                performanceMetrics: performanceMetrics,
                adaptiveMA: Array(repeating: nil, count: bars.count),
                clusterAssignments: clusterAssignments
            )
        }

        // Process each bar
        for i in startIndex..<bars.count {
            // Get current performance for all factors
            let currentPerformances = factors.enumerated().map { (idx, _) in
                performances[idx][i]
            }

            // Run K-Means clustering on performances
            let clusters = KMeansClustering.cluster(
                data: currentPerformances,
                k: settings.numClusters,
                maxIterations: settings.maxIterations,
                numRuns: settings.numRuns
            )

            // Select cluster (0=worst, 1=middle, 2=best for K=3)
            let selectedClusterIdx = min(settings.fromCluster, clusters.count - 1)
            let selectedCluster = clusters[selectedClusterIdx]

            clusterAssignments[i] = selectedClusterIdx

            // Calculate weighted average factor from selected cluster
            var totalWeight = 0.0
            var weightedFactorSum = 0.0

            for memberIdx in selectedCluster.memberIndices {
                let factor = factors[memberIdx]
                let performance = currentPerformances[memberIdx]
                // Weight by performance (use abs to handle negative performance)
                let weight = max(0.001, abs(performance) + 0.1)
                weightedFactorSum += factor * weight
                totalWeight += weight
            }

            let optimalFactor: Double
            if totalWeight > 0 && !selectedCluster.isEmpty {
                optimalFactor = weightedFactorSum / totalWeight
            } else {
                // Fallback to median factor
                optimalFactor = factors[factors.count / 2]
            }

            adaptiveFactor[i] = optimalFactor

            // Calculate SuperTrend with optimal factor
            let hl2 = (bars[i].high + bars[i].low) / 2
            let atrValue = atr[i]

            let basicUpper = hl2 + optimalFactor * atrValue
            let basicLower = hl2 - optimalFactor * atrValue

            // Use previous adaptive values or initialize
            let prevTrend = adaptiveTrend[i - 1]
            let close = bars[i].close
            let prevClose = bars[i - 1].close

            // Trailing stop logic
            var newUpper = basicUpper
            var newLower = basicLower

            if i > 1 {
                let prevUpper = adaptiveTrend[i - 1] == -1 ? (adaptiveSupertrend[i - 1] ?? basicUpper) : basicUpper
                let prevLower = adaptiveTrend[i - 1] == 1 ? (adaptiveSupertrend[i - 1] ?? basicLower) : basicLower

                if basicUpper < prevUpper || prevClose > prevUpper {
                    newUpper = basicUpper
                } else {
                    newUpper = prevUpper
                }

                if basicLower > prevLower || prevClose < prevLower {
                    newLower = basicLower
                } else {
                    newLower = prevLower
                }
            }

            // Determine trend
            let currentTrend: Int
            if prevTrend == 1 || prevTrend == 0 {
                currentTrend = close < newLower ? -1 : 1
            } else {
                currentTrend = close > newUpper ? 1 : -1
            }

            adaptiveTrend[i] = currentTrend
            adaptiveSupertrend[i] = currentTrend == 1 ? newLower : newUpper

            // Performance metric for this bar
            // Use the performance of the optimal factor cluster
            performanceMetrics[i] = selectedCluster.centroid
        }

        // Calculate adaptive MA of SuperTrend
        let adaptiveMA = calculateAdaptiveMA(
            supertrend: adaptiveSupertrend,
            length: settings.adaptiveMALength
        )

        return SuperTrendAIResult(
            supertrend: adaptiveSupertrend,
            trend: adaptiveTrend,
            adaptiveFactor: adaptiveFactor,
            performanceMetrics: performanceMetrics,
            adaptiveMA: adaptiveMA,
            clusterAssignments: clusterAssignments
        )
    }

    /// Calculate adaptive moving average of SuperTrend (bounds-safe)
    private func calculateAdaptiveMA(supertrend: [Double?], length: Int) -> [Double?] {
        guard length > 0, !supertrend.isEmpty else {
            return Array(repeating: nil, count: supertrend.count)
        }

        var ma = Array(repeating: Double?.none, count: supertrend.count)

        for i in 0..<supertrend.count {
            // Clamp window to available history
            let window = min(length, i + 1)
            let start = i + 1 - window

            var sum = 0.0
            var count = 0

            if start <= i {
                for j in start...i {
                    if let v = supertrend[j] { sum += v; count += 1 }
                }
            }

            ma[i] = count > 0 ? sum / Double(count) : nil
        }
        return ma
    }

    // MARK: - Signal Detection

    /// Detect buy/sell signals with performance metrics
    func detectSignals() -> [SuperTrendSignal] {
        guard let res = result, bars.count > 1 else { return [] }

        var signals: [SuperTrendSignal] = []

        for i in 1..<bars.count {
            let prevTrend = res.trend[i - 1]
            let currTrend = res.trend[i]

            // Trend change detection
            if prevTrend != currTrend && currTrend != 0 {
                let isBuy = currTrend == 1
                let performance = res.performanceMetrics[i] ?? 0
                let factor = res.adaptiveFactor[i]

                signals.append(SuperTrendSignal(
                    type: isBuy ? .buy : .sell,
                    barIndex: i,
                    price: bars[i].close,
                    date: bars[i].ts,
                    performance: performance,
                    factor: factor,
                    cluster: res.clusterAssignments[i]
                ))
            }
        }

        return signals
    }

    /// Get signal strength (0-10) based on performance metric
    func signalStrength(performance: Double) -> Int {
        // Normalize performance to 0-10 scale
        // Higher absolute performance = stronger signal
        let normalized = min(10, max(0, abs(performance) * 100))
        return Int(normalized)
    }
}

// MARK: - SuperTrend Signal

struct SuperTrendSignal: Identifiable {
    let id = UUID()
    let type: SignalType
    let barIndex: Int
    let price: Double
    let date: Date
    let performance: Double
    let factor: Double
    let cluster: Int

    enum SignalType {
        case buy
        case sell

        var label: String {
            switch self {
            case .buy: return "BUY"
            case .sell: return "SELL"
            }
        }
    }

    /// Signal strength 0-10 based on performance
    var strength: Int {
        let normalized = min(10, max(0, abs(performance) * 100))
        return Int(normalized)
    }
}
