import Foundation
import Combine
import SwiftUI

@MainActor
final class ForecastQualityViewModel: ObservableObject {
    @Published var qualityResult: ForecastQualityResponse?
    @Published var isLoading = false
    @Published var error: String?
    
    @Published var horizon: String = "1D"
    @Published var timeframe: String = "d1"
    
    private var cancellables = Set<AnyCancellable>()
    
    var symbol: String?
    
    // MARK: - Computed Properties
    
    var hasResults: Bool {
        qualityResult != nil
    }
    
    var formattedQualityScore: String {
        guard let result = qualityResult else { return "—" }
        return "\(String(format: "%.1f", result.qualityScore * 100))%"
    }
    
    var qualityScoreColor: Color {
        guard let result = qualityResult else { return .gray }
        return result.qualityScore >= 0.7 ? .green : result.qualityScore >= 0.5 ? .orange : .red
    }
    
    var hasIssues: Bool {
        guard let result = qualityResult else { return false }
        return !result.issues.isEmpty
    }
    
    // MARK: - Data Loading
    
    func fetchQuality(symbol: String, horizon: String = "1D", timeframe: String = "d1") async {
        guard !isLoading else { return }
        
        self.symbol = symbol.uppercased()
        self.horizon = horizon
        self.timeframe = timeframe
        isLoading = true
        error = nil
        qualityResult = nil
        
        let request = ForecastQualityRequest(
            symbol: symbol,
            horizon: horizon,
            timeframe: timeframe
        )
        
        do {
            let response = try await APIClient.shared.fetchForecastQuality(request: request)
            self.qualityResult = response
            self.isLoading = false
            
            print("[ForecastQuality] Quality fetched: \(String(format: "%.1f", response.qualityScore * 100))% score, \(response.issues.count) issues")
        } catch {
            self.error = error.localizedDescription
            self.isLoading = false
            print("[ForecastQuality] Error fetching quality: \(error)")
        }
    }
    
    func reset() {
        qualityResult = nil
        error = nil
    }
}
