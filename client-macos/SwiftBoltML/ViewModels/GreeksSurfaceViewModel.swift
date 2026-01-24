import Foundation
import Combine
import SwiftUI

/// ViewModel for managing 3D Greeks surface visualization.
@MainActor
class GreeksSurfaceViewModel: ObservableObject {
    @Published var surfaceData: GreeksSurfaceResponse?
    @Published var isLoading = false
    @Published var error: String?
    @Published var selectedGreek: GreekType = .delta
    
    private var cancellables = Set<AnyCancellable>()
    private var currentTask: Task<Void, Never>?
    
    enum GreekType: String, CaseIterable {
        case delta = "Delta"
        case gamma = "Gamma"
        case theta = "Theta"
        case vega = "Vega"
        case rho = "Rho"
        
        var description: String {
            switch self {
            case .delta: return "Price sensitivity to underlying"
            case .gamma: return "Delta sensitivity to underlying"
            case .theta: return "Time decay per day"
            case .vega: return "Volatility sensitivity"
            case .rho: return "Interest rate sensitivity"
            }
        }
    }
    
    /// Fetch Greeks surface data
    func fetchSurface(
        symbol: String,
        underlyingPrice: Double,
        volatility: Double,
        riskFreeRate: Double = 0.05,
        optionType: String = "call",
        nStrikes: Int = 50,
        nTimes: Int = 50
    ) async {
        // Cancel any existing task
        currentTask?.cancel()
        
        isLoading = true
        error = nil
        
        currentTask = Task {
            do {
                let request = GreeksSurfaceRequest(
                    symbol: symbol,
                    underlyingPrice: underlyingPrice,
                    riskFreeRate: riskFreeRate,
                    volatility: volatility,
                    optionType: optionType,
                    nStrikes: nStrikes,
                    nTimes: nTimes
                )
                
                let response = try await RequestDeduplicator.shared.execute(
                    key: "greeks_surface_\(symbol)_\(underlyingPrice)_\(volatility)"
                ) {
                    try await withRetry(policy: .default) {
                        try await APIClient.shared.fetchGreeksSurface(request: request)
                    }
                }
                
                if !Task.isCancelled {
                    self.surfaceData = response
                    self.isLoading = false
                }
            } catch {
                if !Task.isCancelled {
                    let formatted = ErrorFormatter.userFriendlyMessage(from: error)
                    self.error = formatted.message
                    self.isLoading = false
                }
            }
        }
        
        await currentTask?.value
    }
    
    /// Get current Greek values as 2D grid
    func getCurrentGreekGrid() -> [[Double]]? {
        guard let data = surfaceData else { return nil }
        
        switch selectedGreek {
        case .delta:
            return data.delta
        case .gamma:
            return data.gamma
        case .theta:
            return data.theta
        case .vega:
            return data.vega
        case .rho:
            return data.rho
        }
    }
    
    deinit {
        currentTask?.cancel()
    }
}
