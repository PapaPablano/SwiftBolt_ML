import Foundation
import Combine
import SwiftUI

/// ViewModel for managing 3D volatility surface visualization.
@MainActor
class VolatilitySurfaceViewModel: ObservableObject {
    @Published var surfaceData: VolatilitySurfaceResponse?
    @Published var isLoading = false
    @Published var error: String?
    
    private var cancellables = Set<AnyCancellable>()
    private var currentTask: Task<Void, Never>?
    
    /// Fetch volatility surface data
    func fetchSurface(
        symbol: String,
        slices: [VolatilitySurfaceSlice],
        nStrikes: Int = 50,
        nMaturities: Int = 30
    ) async {
        // Cancel any existing task
        currentTask?.cancel()
        
        isLoading = true
        error = nil
        
        currentTask = Task {
            do {
                let request = VolatilitySurfaceRequest(
                    symbol: symbol,
                    slices: slices,
                    nStrikes: nStrikes,
                    nMaturities: nMaturities
                )
                
                let response = try await RequestDeduplicator.shared.execute(
                    key: "volatility_surface_\(symbol)_\(slices.count)"
                ) {
                    try await withRetry(policy: .default) {
                        try await APIClient.shared.fetchVolatilitySurface(request: request)
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
    
    deinit {
        currentTask?.cancel()
    }
}
