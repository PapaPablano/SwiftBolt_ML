import Foundation
import Combine
import SwiftUI

@MainActor
final class ModelTrainingViewModel: ObservableObject {
    @Published var trainingResult: ModelTrainingResponse?
    @Published var isLoading = false
    @Published var error: String?
    
    @Published var timeframe: String = "d1"
    @Published var lookbackDays: Int = 90
    
    private var cancellables = Set<AnyCancellable>()
    
    var symbol: String?
    
    // MARK: - Computed Properties
    
    var hasResults: Bool {
        trainingResult != nil
    }
    
    var formattedValidationAccuracy: String {
        guard let result = trainingResult else { return "—" }
        return "\(String(format: "%.2f", result.trainingMetrics.validationAccuracy * 100))%"
    }
    
    var validationAccuracyColor: Color {
        guard let result = trainingResult else { return .gray }
        return result.trainingMetrics.validationAccuracy >= 0.6 ? .green : result.trainingMetrics.validationAccuracy >= 0.5 ? .orange : .red
    }
    
    // MARK: - Data Loading
    
    func trainModel(symbol: String, timeframe: String = "d1", lookbackDays: Int = 90) async {
        guard !isLoading else { return }
        
        self.symbol = symbol.uppercased()
        self.timeframe = timeframe
        self.lookbackDays = lookbackDays
        isLoading = true
        error = nil
        trainingResult = nil
        
        let request = ModelTrainingRequest(
            symbol: symbol,
            timeframe: timeframe,
            lookbackDays: lookbackDays
        )
        
        do {
            let response = try await APIClient.shared.trainModel(request: request)
            self.trainingResult = response
            self.isLoading = false
            
            print("[ModelTraining] Training complete: \(String(format: "%.2f", response.trainingMetrics.validationAccuracy * 100))% validation accuracy, \(response.trainingMetrics.trainSamples) train samples")
        } catch {
            self.error = error.localizedDescription
            self.isLoading = false
            print("[ModelTraining] Error training model: \(error)")
        }
    }
    
    func reset() {
        trainingResult = nil
        error = nil
    }
}
