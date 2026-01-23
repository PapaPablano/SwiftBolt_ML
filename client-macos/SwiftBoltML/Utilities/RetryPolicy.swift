import Foundation

/// Retry policy configuration for API requests with exponential backoff.
///
/// Provides configurable retry strategies for handling transient failures.
/// Supports different policies (default, conservative, aggressive) based on
/// the type of operation and acceptable retry behavior.
///
/// **Usage:**
/// ```swift
/// let result = try await withRetry(policy: .default) {
///     try await APIClient.shared.fetchData(...)
/// }
/// ```
struct RetryPolicy {
    /// Maximum number of retry attempts
    let maxAttempts: Int
    
    /// Initial delay before first retry (in seconds)
    let initialDelay: TimeInterval
    
    /// Maximum delay between retries (in seconds)
    let maxDelay: TimeInterval
    
    /// Multiplier for exponential backoff
    let backoffMultiplier: Double
    
    /// Whether to retry on network errors
    let retryOnNetworkError: Bool
    
    /// Whether to retry on server errors (5xx)
    let retryOnServerError: Bool
    
    /// Whether to retry on rate limit errors (429)
    let retryOnRateLimit: Bool
    
    /// Default retry policy for most API calls
    static let `default` = RetryPolicy(
        maxAttempts: 3,
        initialDelay: 1.0,
        maxDelay: 10.0,
        backoffMultiplier: 2.0,
        retryOnNetworkError: true,
        retryOnServerError: true,
        retryOnRateLimit: true
    )
    
    /// Conservative retry policy (fewer retries, longer delays)
    static let conservative = RetryPolicy(
        maxAttempts: 2,
        initialDelay: 2.0,
        maxDelay: 15.0,
        backoffMultiplier: 2.5,
        retryOnNetworkError: true,
        retryOnServerError: false,
        retryOnRateLimit: true
    )
    
    /// Aggressive retry policy (more retries, shorter delays)
    static let aggressive = RetryPolicy(
        maxAttempts: 5,
        initialDelay: 0.5,
        maxDelay: 8.0,
        backoffMultiplier: 1.8,
        retryOnNetworkError: true,
        retryOnServerError: true,
        retryOnRateLimit: true
    )
    
    /// Calculate delay for a given attempt number (exponential backoff)
    func delay(for attempt: Int) -> TimeInterval {
        let exponentialDelay = initialDelay * pow(backoffMultiplier, Double(attempt - 1))
        return min(exponentialDelay, maxDelay)
    }
    
    /// Determine if an error should be retried
    func shouldRetry(error: Error) -> Bool {
        if let apiError = error as? APIError {
            switch apiError {
            case .networkError:
                return retryOnNetworkError
            case .rateLimitExceeded:
                return retryOnRateLimit
            case .serviceUnavailable:
                return retryOnServerError
            case .httpError(let statusCode, _):
                // Retry on 5xx server errors
                if (500...599).contains(statusCode) {
                    return retryOnServerError
                }
                // Retry on 429 rate limit
                if statusCode == 429 {
                    return retryOnRateLimit
                }
                return false
            default:
                return false
            }
        }
        
        // Retry on network errors (URLError)
        if let urlError = error as? URLError {
            switch urlError.code {
            case .timedOut, .networkConnectionLost, .notConnectedToInternet, .cannotConnectToHost:
                return retryOnNetworkError
            default:
                return false
            }
        }
        
        return false
    }
}

/// Execute an async operation with retry logic and exponential backoff
func withRetry<T>(
    policy: RetryPolicy = .default,
    operation: @escaping () async throws -> T
) async throws -> T {
    var lastError: Error?
    
    for attempt in 1...policy.maxAttempts {
        do {
            return try await operation()
        } catch {
            lastError = error
            
            // Check if we should retry this error
            guard policy.shouldRetry(error: error) else {
                throw error
            }
            
            // Don't delay after the last attempt
            guard attempt < policy.maxAttempts else {
                break
            }
            
            // Calculate delay with exponential backoff
            let delay = policy.delay(for: attempt)
            
            // For rate limit errors, use the Retry-After header if available
            if let apiError = error as? APIError,
               case .rateLimitExceeded(let retryAfter) = apiError,
               let retryAfterSeconds = retryAfter {
                try await Task.sleep(nanoseconds: UInt64(retryAfterSeconds) * 1_000_000_000)
            } else {
                try await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
            }
            
            print("[RetryPolicy] Retrying attempt \(attempt + 1)/\(policy.maxAttempts) after \(delay)s delay")
        }
    }
    
    // If we get here, all retries failed
    throw lastError ?? NSError(domain: "RetryPolicy", code: -1, userInfo: [NSLocalizedDescriptionKey: "All retry attempts failed"])
}
