import Foundation

/// Formats API errors into user-friendly messages for display in the UI.
///
/// Converts technical error types (APIError, URLError) into contextual,
/// user-friendly messages with appropriate titles and icons.
///
/// **Usage:**
/// ```swift
/// let formatted = ErrorFormatter.userFriendlyMessage(from: error)
/// // formatted.title: "Network Error"
/// // formatted.message: "Please check your internet connection..."
/// // formatted.icon: "wifi.slash"
/// ```
enum ErrorFormatter {
    /// Convert an error into a user-friendly message
    static func userFriendlyMessage(from error: Error) -> (title: String, message: String, icon: String) {
        if let apiError = error as? APIError {
            return formatAPIError(apiError)
        }
        
        if let urlError = error as? URLError {
            return formatURLError(urlError)
        }
        
        // Generic error
        return (
            title: "Something went wrong",
            message: error.localizedDescription,
            icon: "exclamationmark.triangle.fill"
        )
    }
    
    private static func formatAPIError(_ error: APIError) -> (title: String, message: String, icon: String) {
        switch error {
        case .networkError(let underlyingError):
            if let urlError = underlyingError as? URLError {
                return formatURLError(urlError)
            }
            return (
                title: "Network Error",
                message: "Unable to connect to the server. Please check your internet connection.",
                icon: "wifi.slash"
            )
            
        case .rateLimitExceeded(let retryAfter):
            let message: String
            if let seconds = retryAfter {
                message = "Too many requests. Please wait \(seconds) seconds before trying again."
            } else {
                message = "Too many requests. Please try again in a few moments."
            }
            return (
                title: "Rate Limit Exceeded",
                message: message,
                icon: "clock.fill"
            )
            
        case .serviceUnavailable(let message):
            return (
                title: "Service Unavailable",
                message: message.isEmpty ? "The server is temporarily unavailable. Please try again later." : message,
                icon: "server.rack"
            )
            
        case .authenticationError(let message):
            return (
                title: "Authentication Error",
                message: message.isEmpty ? "Your session has expired. Please sign in again." : message,
                icon: "lock.fill"
            )
            
        case .invalidSymbol(let symbol):
            return (
                title: "Invalid Symbol",
                message: "The symbol '\(symbol)' was not found or is invalid.",
                icon: "xmark.circle.fill"
            )
            
        case .httpError(let statusCode, let message):
            let title = "HTTP Error \(statusCode)"
            let userMessage = message?.isEmpty == false ? message! : "An error occurred while processing your request."
            return (
                title: title,
                message: userMessage,
                icon: "exclamationmark.triangle.fill"
            )
            
        case .decodingError:
            return (
                title: "Data Error",
                message: "The server returned data in an unexpected format. Please try again.",
                icon: "doc.badge.ellipsis"
            )
            
        case .invalidURL, .invalidResponse:
            return (
                title: "Invalid Response",
                message: "The server returned an invalid response. Please try again.",
                icon: "exclamationmark.triangle.fill"
            )
        }
    }
    
    private static func formatURLError(_ error: URLError) -> (title: String, message: String, icon: String) {
        switch error.code {
        case .notConnectedToInternet:
            return (
                title: "No Internet Connection",
                message: "Please check your internet connection and try again.",
                icon: "wifi.slash"
            )
            
        case .timedOut:
            return (
                title: "Request Timed Out",
                message: "The request took too long. Please try again.",
                icon: "clock.fill"
            )
            
        case .cannotConnectToHost:
            return (
                title: "Cannot Connect",
                message: "Unable to reach the server. Please check your connection.",
                icon: "network.slash"
            )
            
        case .networkConnectionLost:
            return (
                title: "Connection Lost",
                message: "Your connection was interrupted. Please try again.",
                icon: "wifi.exclamationmark"
            )
            
        case .dnsLookupFailed:
            return (
                title: "DNS Lookup Failed",
                message: "Unable to resolve the server address. Please check your connection.",
                icon: "network.slash"
            )
            
        default:
            return (
                title: "Network Error",
                message: error.localizedDescription,
                icon: "exclamationmark.triangle.fill"
            )
        }
    }
}
