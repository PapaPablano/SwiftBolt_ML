import Foundation
import Combine
import SwiftUI

/// ViewModel for managing ML model training operations and results.
///
/// Handles model training requests, caching, and displaying training metrics with support for:
/// - Configurable lookback periods
/// - Multiple timeframes
/// - Caching with appropriate TTL
/// - Request deduplication
/// - Retry logic (conservative policy for training)
/// - Offline mode detection
/// - User-friendly error messages
///
/// **Usage:**
/// ```swift
/// @StateObject private var viewModel = ModelTrainingViewModel()
/// await viewModel.trainModel(symbol: "AAPL", timeframe: "d1", lookbackDays: 90)
/// ```
@MainActor
final class ModelTrainingViewModel: ObservableObject {
    @Published var trainingResult: ModelTrainingResponse?
    @Published var isLoading = false
    @Published var error: String?
    @Published var isOffline = false
    
    @Published var timeframe: String = "d1"
    @Published var lookbackDays: Int = 90
    
    private var cancellables = Set<AnyCancellable>()
    private var currentTask: Task<Void, Never>?
    private let networkMonitor: NetworkMonitor
    
    var symbol: String?
    
    init(networkMonitor: NetworkMonitor? = nil) {
        // Access NetworkMonitor.shared on main actor
        self.networkMonitor = networkMonitor ?? NetworkMonitor.shared
        
        // Monitor network status
        self.networkMonitor.$isConnected
            .receive(on: DispatchQueue.main)
            .sink { [weak self] connected in
                self?.isOffline = !connected
            }
            .store(in: &cancellables)
    }
    
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
    
    func trainModel(symbol: String, timeframe: String = "d1", lookbackDays: Int = 90, forceRefresh: Bool = false) async {
        // Cancel any existing request
        currentTask?.cancel()
        
        // Check cache first (unless forcing refresh or training - training should always be fresh)
        // Note: Training results are cached but with shorter TTL since they change when models retrain
        let cacheKey = "model_training_\(symbol.uppercased())_\(timeframe)_\(lookbackDays)"
        if !forceRefresh {
            if let cached = await CacheManager.shared.get(cacheKey, type: ModelTrainingResponse.self) {
                let (value, freshness) = cached
                
                // Use cached data if fresh (training results are less frequently updated)
                if freshness == .fresh {
                    self.trainingResult = value
                    self.symbol = symbol.uppercased()
                    self.timeframe = timeframe
                    self.lookbackDays = lookbackDays
                    return
                }
            }
        }
        
        // If offline, try to use stale cache
        if isOffline || !networkMonitor.isConnected {
            if let cached = await CacheManager.shared.get(cacheKey, type: ModelTrainingResponse.self) {
                let (value, _) = cached
                self.trainingResult = value
                self.symbol = symbol.uppercased()
                self.timeframe = timeframe
                self.lookbackDays = lookbackDays
                self.error = "Showing cached training results (offline). Training requires internet connection."
                return
            } else {
                self.error = "No cached data available. Training requires internet connection."
                return
            }
        }
        
        guard !isLoading else { return }
        
        self.symbol = symbol.uppercased()
        self.timeframe = timeframe
        self.lookbackDays = lookbackDays
        isLoading = true
        error = nil
        
        // Only clear result if forcing refresh
        if forceRefresh {
            trainingResult = nil
        }
        
        let request = ModelTrainingRequest(
            symbol: symbol,
            timeframe: timeframe,
            lookbackDays: lookbackDays
        )
        
        currentTask = Task {
            do {
                // Use request deduplication to prevent duplicate calls
                let deduplicationKey = "model_training_\(symbol.uppercased())_\(timeframe)_\(lookbackDays)"
                let response = try await RequestDeduplicator.shared.execute(key: deduplicationKey) {
                    // Use retry logic with exponential backoff (conservative for training)
                    try await withRetry(policy: .conservative) {
                        try await APIClient.shared.trainModel(request: request)
                    }
                }
                
                // Check if task was cancelled
                guard !Task.isCancelled else { return }
                
                self.trainingResult = response
                self.isLoading = false
                
                // Cache the response (training results are cached but may be stale quickly)
                let cacheKey = "model_training_\(symbol.uppercased())_\(timeframe)_\(lookbackDays)"
                await CacheManager.shared.set(cacheKey, value: response)
                
                print("[ModelTraining] Training complete: \(String(format: "%.2f", response.trainingMetrics.validationAccuracy * 100))% validation accuracy, \(response.trainingMetrics.trainSamples) train samples")
            } catch {
                // Check if task was cancelled
                guard !Task.isCancelled else { return }
                
                // Store user-friendly error message
                let formatted = ErrorFormatter.userFriendlyMessage(from: error)
                self.error = formatted.message
                self.isLoading = false
                print("[ModelTraining] Error training model after retries: \(error)")
            }
        }
        
        await currentTask?.value
    }
    
    func reset() {
        currentTask?.cancel()
        trainingResult = nil
        error = nil
        isLoading = false
    }
}
