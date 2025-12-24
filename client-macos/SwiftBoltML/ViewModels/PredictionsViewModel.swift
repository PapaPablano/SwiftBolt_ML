import Foundation
import Combine

@MainActor
class PredictionsViewModel: ObservableObject {
    @Published var dashboardData: MLDashboardResponse?
    @Published var isLoading = false
    @Published var error: String?

    private var cancellables = Set<AnyCancellable>()

    // MARK: - Computed Properties

    var overview: DashboardOverview? {
        dashboardData?.overview
    }

    var recentForecasts: [ForecastSummary] {
        dashboardData?.recentForecasts ?? []
    }

    var symbolPerformance: [SymbolPerformance] {
        dashboardData?.symbolPerformance ?? []
    }

    var featureStats: [FeatureStats] {
        dashboardData?.featureStats ?? []
    }

    var confidenceDistribution: ConfidenceDistribution? {
        dashboardData?.confidenceDistribution
    }

    // Grouped features by category
    var featuresByCategory: [String: [FeatureStats]] {
        Dictionary(grouping: featureStats, by: { $0.category })
    }

    // Top performing symbols (by confidence)
    var topPerformingSymbols: [SymbolPerformance] {
        symbolPerformance.sorted { $0.avgConfidence > $1.avgConfidence }.prefix(10).map { $0 }
    }

    // MARK: - Data Loading

    func loadDashboard() async {
        isLoading = true
        error = nil

        do {
            let response = try await APIClient.shared.fetchMLDashboard()
            dashboardData = response
            isLoading = false
            print("[Predictions] Loaded dashboard: \(response.overview.totalForecasts) forecasts, \(response.overview.totalSymbols) symbols")
        } catch {
            self.error = error.localizedDescription
            isLoading = false
            print("[Predictions] Error loading dashboard: \(error)")
        }
    }

    func refresh() async {
        await loadDashboard()
    }
}
