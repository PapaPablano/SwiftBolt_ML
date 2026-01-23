import Foundation
import Combine
import SwiftUI

/// ViewModel for managing forecast quality metrics display and interaction.
///
/// Handles fetching, caching, and displaying forecast quality data with support for:
/// - Multiple forecast horizons (1D, 1W, 1M)
/// - Caching with freshness tiers
/// - Request deduplication
/// - Retry logic with exponential backoff
/// - Offline mode detection
/// - User-friendly error messages
///
/// **Usage:**
/// ```swift
/// @StateObject private var viewModel = ForecastQualityViewModel()
/// await viewModel.fetchQuality(symbol: "AAPL", horizon: "1D", timeframe: "d1")
/// ```
@MainActor
final class ForecastQualityViewModel: ObservableObject {
    @Published var qualityResult: ForecastQualityResponse?
    @Published var isLoading = false
    @Published var error: String?
    @Published var isOffline = false
    
    @Published var horizon: String = "1D"
    @Published var timeframe: String = "d1"
    
    private var cancellables = Set<AnyCancellable>()
    private var currentTask: Task<Void, Never>?
    private let networkMonitor: NetworkMonitor
    
    var symbol: String?
    
    init(networkMonitor: NetworkMonitor = .shared) {
        self.networkMonitor = networkMonitor
        
        // Monitor network status
        networkMonitor.$isConnected
            .receive(on: DispatchQueue.main)
            .sink { [weak self] connected in
                self?.isOffline = !connected
            }
            .store(in: &cancellables)
    }
    
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
    
    func fetchQuality(symbol: String, horizon: String = "1D", timeframe: String = "d1", forceRefresh: Bool = false) async {
        // Cancel any existing request
        currentTask?.cancel()
        
        // Check cache first (unless forcing refresh)
        let cacheKey = "forecast_quality_\(symbol.uppercased())_\(horizon)_\(timeframe)"
        if !forceRefresh {
            if let cached = await CacheManager.shared.get(cacheKey, type: ForecastQualityResponse.self) {
                let (value, freshness) = cached
                
                // Use cached data if fresh or warm
                if freshness == .fresh || freshness == .warm {
                    self.qualityResult = value
                    self.symbol = symbol.uppercased()
                    self.horizon = horizon
                    self.timeframe = timeframe
                    
                    // Background refresh if warm (only if online)
                    if freshness == .warm && networkMonitor.isConnected {
                        Task {
                            await fetchQuality(symbol: symbol, horizon: horizon, timeframe: timeframe, forceRefresh: true)
                        }
                    }
                    return
                }
            }
        }
        
        // If offline, try to use stale cache
        if isOffline || !networkMonitor.isConnected {
            if let cached = await CacheManager.shared.get(cacheKey, type: ForecastQualityResponse.self) {
                let (value, _) = cached
                self.qualityResult = value
                self.symbol = symbol.uppercased()
                self.horizon = horizon
                self.timeframe = timeframe
                self.error = "Showing cached data (offline)"
                return
            } else {
                self.error = "No cached data available. Please connect to the internet."
                return
            }
        }
        
        guard !isLoading else { return }
        
        self.symbol = symbol.uppercased()
        self.horizon = horizon
        self.timeframe = timeframe
        isLoading = true
        error = nil
        
        // Only clear result if forcing refresh
        if forceRefresh {
            qualityResult = nil
        }
        
        let request = ForecastQualityRequest(
            symbol: symbol,
            horizon: horizon,
            timeframe: timeframe
        )
        
        currentTask = Task {
            do {
                // Use request deduplication to prevent duplicate calls
                let deduplicationKey = "forecast_quality_\(symbol.uppercased())_\(horizon)_\(timeframe)"
                let response = try await RequestDeduplicator.shared.execute(key: deduplicationKey) {
                    // Use retry logic with exponential backoff
                    try await withRetry(policy: .default) {
                        try await APIClient.shared.fetchForecastQuality(request: request)
                    }
                }
                
                // Check if task was cancelled
                guard !Task.isCancelled else { return }
                
                self.qualityResult = response
                self.isLoading = false
                
                // Cache the response
                let cacheKey = "forecast_quality_\(symbol.uppercased())_\(horizon)_\(timeframe)"
                await CacheManager.shared.set(cacheKey, value: response)
                
                print("[ForecastQuality] Quality fetched: \(String(format: "%.1f", response.qualityScore * 100))% score, \(response.issues.count) issues")
            } catch {
                // Check if task was cancelled
                guard !Task.isCancelled else { return }
                
                // Store user-friendly error message
                let formatted = ErrorFormatter.userFriendlyMessage(from: error)
                self.error = formatted.message
                self.isLoading = false
                print("[ForecastQuality] Error fetching quality after retries: \(error)")
            }
        }
        
        await currentTask?.value
    }
    
    func reset() {
        currentTask?.cancel()
        qualityResult = nil
        error = nil
        isLoading = false
    }
}
