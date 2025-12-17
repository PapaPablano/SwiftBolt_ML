import Foundation
import Combine

@MainActor
class AnalysisViewModel: ObservableObject {
    @Published var alerts: [ScannerAlert] = []
    @Published var isLoadingAlerts = false
    @Published var alertsError: String?

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

            // Filter alerts for the current symbol
            alerts = response.alerts.filter { $0.symbol == symbol }
            isLoadingAlerts = false

            print("[Analysis] Loaded \(alerts.count) alerts for \(symbol)")
        } catch {
            alertsError = error.localizedDescription
            isLoadingAlerts = false
            print("[Analysis] Error loading alerts: \(error)")
        }
    }

    func refresh(for symbol: String) async {
        await loadAlerts(for: symbol)
    }
}
