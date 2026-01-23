import Foundation

/// Prevents duplicate concurrent API requests by tracking in-flight requests.
///
/// When multiple components request the same data simultaneously, only one
/// actual network request is made, and all callers receive the same result.
/// This reduces server load and improves performance.
///
/// **Usage:**
/// ```swift
/// let result = try await RequestDeduplicator.shared.execute(key: "forecast_AAPL_1D") {
///     try await APIClient.shared.fetchForecast(...)
/// }
/// ```
///
/// **Thread Safety:**
/// This is an `actor`, so it's thread-safe and can be used from any context.
actor RequestDeduplicator {
    static let shared = RequestDeduplicator()
    
    // Store tasks with type-erased continuations
    private var inFlightRequests: [String: Any] = [:]
    
    private init() {}
    
    /// Execute a request with deduplication. If a request with the same key
    /// is already in flight, returns the existing task's result.
    ///
    /// - Parameters:
    ///   - key: Unique identifier for this request (e.g., "forecast_quality_AAPL_1D_d1")
    ///   - operation: The async operation to execute
    /// - Returns: The result of the operation
    func execute<T: Sendable>(key: String, operation: @escaping @Sendable () async throws -> T) async throws -> T {
        // Check if request is already in flight
        if let existingTask = inFlightRequests[key] as? Task<T, Error> {
            // Wait for existing task to complete
            return try await existingTask.value
        }
        
        // Create new task
        let task = Task<T, Error> {
            let result = try await operation()
            // Remove from in-flight when complete
            await removeRequest(key: key)
            return result
        }
        
        inFlightRequests[key] = task
        
        do {
            let result = try await task.value
            return result
        } catch {
            // Remove from in-flight on error
            await removeRequest(key: key)
            throw error
        }
    }
    
    /// Cancel and remove an in-flight request
    func cancelRequest(key: String) {
        if let task = inFlightRequests[key] as? Task<Any, Error> {
            task.cancel()
        }
        inFlightRequests.removeValue(forKey: key)
    }
    
    /// Remove a request from tracking (called automatically on completion)
    private func removeRequest(key: String) {
        inFlightRequests.removeValue(forKey: key)
    }
    
    /// Get count of in-flight requests (for debugging)
    func inFlightCount() -> Int {
        inFlightRequests.count
    }
    
    /// Clear all in-flight requests (for testing/debugging)
    func clearAll() {
        for (_, task) in inFlightRequests {
            if let cancellable = task as? Task<Any, Error> {
                cancellable.cancel()
            }
        }
        inFlightRequests.removeAll()
    }
}
