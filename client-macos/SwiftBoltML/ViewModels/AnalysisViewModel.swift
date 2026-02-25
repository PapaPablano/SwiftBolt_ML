import Foundation
import Combine

@MainActor
class AnalysisViewModel: ObservableObject {
    @Published var alerts: [ScannerAlert] = []
    @Published var isLoadingAlerts = false
    @Published var alertsError: String?
    
    // Enhanced ML insights
    @Published var multiTimeframeConsensus: MultiTimeframeConsensus?
    @Published var forecastExplanation: ForecastExplanation?
    @Published var dataQuality: DataQualityReport?
    @Published var isLoadingEnhancedInsights = false
    @Published var enhancedInsightsError: String?
    
    // Support & Resistance
    @Published var supportResistance: SupportResistanceResponse?
    @Published var isLoadingSR = false
    @Published var srError: String?

    private var cancellables = Set<AnyCancellable>()

    var criticalAlerts: [ScannerAlert] {
        alerts.filter { $0.severity == .critical && !$0.isRead }
    }

    var warningAlerts: [ScannerAlert] {
        alerts.filter { $0.severity == .warning && !$0.isRead }
    }

    var infoAlerts: [ScannerAlert] {
        alerts.filter { $0.severity == .info && !$0.isRead }
    }

    var unreadCount: Int {
        alerts.filter { !$0.isRead }.count
    }

    func loadAlerts(for symbol: String) async {
        isLoadingAlerts = true
        alertsError = nil

        do {
            let response = try await APIClient.shared.scanWatchlist(symbols: [symbol])
            let filtered = response.alerts.filter { $0.symbol == symbol }
            DispatchQueue.main.async { [weak self] in
                self?.alerts = filtered
                self?.isLoadingAlerts = false
                print("[Analysis] Loaded \(filtered.count) alerts for \(symbol)")
            }
        } catch {
            let errMsg = error.localizedDescription
            DispatchQueue.main.async { [weak self] in
                self?.alertsError = errMsg
                self?.isLoadingAlerts = false
                print("[Analysis] Error loading alerts: \(error)")
            }
        }
    }

    func refresh(for symbol: String) async {
        await loadAlerts(for: symbol)
        await loadEnhancedInsights(for: symbol)
        await loadSupportResistance(for: symbol)
    }
    
    // MARK: - Support & Resistance
    
    func loadSupportResistance(for symbol: String) async {
        isLoadingSR = true
        srError = nil
        
        do {
            let response = try await APIClient.shared.fetchSupportResistance(symbol: symbol)
            DispatchQueue.main.async { [weak self] in
                self?.supportResistance = response
                self?.isLoadingSR = false
                print("[Analysis] Loaded S/R levels for \(symbol)")
            }
        } catch {
            let errMsg = error.localizedDescription
            DispatchQueue.main.async { [weak self] in
                self?.srError = errMsg
                self?.isLoadingSR = false
                print("[Analysis] S/R levels not available: \(errMsg)")
            }
        }
    }
    
    // MARK: - Enhanced ML Insights
    
    func loadEnhancedInsights(for symbol: String) async {
        isLoadingEnhancedInsights = true
        enhancedInsightsError = nil
        
        do {
            let response = try await APIClient.shared.fetchEnhancedPrediction(symbol: symbol)
            let mtf = response.multiTimeframe
            let expl = response.explanation
            let dq = response.dataQuality
            DispatchQueue.main.async { [weak self] in
                self?.multiTimeframeConsensus = mtf
                self?.forecastExplanation = expl
                self?.dataQuality = dq
                self?.isLoadingEnhancedInsights = false
                print("[Analysis] Loaded enhanced insights for \(symbol)")
            }
        } catch {
            let errMsg = error.localizedDescription
            DispatchQueue.main.async { [weak self] in
                self?.enhancedInsightsError = errMsg
                self?.isLoadingEnhancedInsights = false
                print("[Analysis] Enhanced insights not available: \(errMsg)")
            }
        }
    }
}
