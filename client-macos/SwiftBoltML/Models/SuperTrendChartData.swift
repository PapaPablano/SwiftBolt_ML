import Foundation
import SwiftUI
import Combine

/// Data model for the SuperTrend AI dedicated chart panel
@MainActor
class SuperTrendChartData: ObservableObject {

    // MARK: - Published Properties

    /// The SuperTrend AI indicator (source of truth)
    @Published var indicator: SuperTrendAIIndicator?

    /// OHLC bars for reference
    @Published var bars: [OHLCBar] = []

    /// Detected signals from SuperTrend AI
    @Published var signals: [SuperTrendSignal] = []

    /// Current trend direction (1 = bullish, -1 = bearish)
    @Published var currentTrend: Int = 0

    /// Current adaptive factor being used
    @Published var currentFactor: Double = 3.0

    /// Current performance metric
    @Published var currentPerformance: Double = 0.0

    /// Current cluster assignment (0 = worst, 1 = middle, 2 = best)
    @Published var currentCluster: Int = 0

    // MARK: - Computed Properties

    /// SuperTrend AI result (if available)
    var result: SuperTrendAIResult? {
        indicator?.result
    }

    /// SuperTrend line values for charting
    var superTrendLine: [Double?] {
        result?.supertrend ?? []
    }

    /// Trend values for each bar
    var trendValues: [Int] {
        result?.trend ?? []
    }

    /// Adaptive factor values for each bar
    var adaptiveFactors: [Double] {
        result?.adaptiveFactor ?? []
    }

    /// Performance metrics for each bar
    var performanceMetrics: [Double?] {
        result?.performanceMetrics ?? []
    }

    /// Adaptive MA of SuperTrend
    var adaptiveMA: [Double?] {
        result?.adaptiveMA ?? []
    }

    /// Cluster assignments for each bar
    var clusterAssignments: [Int] {
        result?.clusterAssignments ?? []
    }

    /// Trend label for display
    var trendLabel: String {
        switch currentTrend {
        case 1: return "BULLISH"
        case -1: return "BEARISH"
        default: return "NEUTRAL"
        }
    }

    /// Trend color for display
    var trendColor: Color {
        switch currentTrend {
        case 1: return .green
        case -1: return .red
        default: return .gray
        }
    }

    /// Cluster label for display
    var clusterLabel: String {
        switch currentCluster {
        case 0: return "Below Avg"
        case 1: return "Average"
        case 2: return "Exceptional"
        default: return "Unknown"
        }
    }

    // MARK: - Methods

    /// Update data from ChartViewModel
    func update(from chartViewModel: ChartViewModel) {
        self.bars = chartViewModel.bars
        self.indicator = chartViewModel.superTrendAIIndicator
        self.signals = chartViewModel.superTrendAISignals

        // Update current state from indicator
        if let ind = indicator {
            self.currentTrend = ind.currentTrend
            self.currentFactor = ind.currentFactor
            self.currentPerformance = ind.currentPerformance
            self.currentCluster = ind.currentCluster
        }
    }

    /// Update data directly from indicator and bars
    func update(indicator: SuperTrendAIIndicator?, bars: [OHLCBar], signals: [SuperTrendSignal]) {
        self.indicator = indicator
        self.bars = bars
        self.signals = signals

        // Update current state from indicator
        if let ind = indicator {
            self.currentTrend = ind.currentTrend
            self.currentFactor = ind.currentFactor
            self.currentPerformance = ind.currentPerformance
            self.currentCluster = ind.currentCluster
        }
    }
}
