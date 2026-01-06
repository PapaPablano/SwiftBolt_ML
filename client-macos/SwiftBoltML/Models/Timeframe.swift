import Foundation

enum Timeframe: String, Codable, CaseIterable {
    case m15, h1, h4, d1, w1
    
    var isIntraday: Bool {
        self == .m15 || self == .h1 || self == .h4
    }
    
    /// API token format expected by chart-data-v2 endpoint
    var apiToken: String {
        switch self {
        case .m15: return "15m"
        case .h1:  return "1h"
        case .h4:  return "4h"
        case .d1:  return "1d"
        case .w1:  return "1w"
        }
    }
    
    /// Display name for UI
    var displayName: String {
        switch self {
        case .m15: return "15 Min"
        case .h1:  return "1 Hour"
        case .h4:  return "4 Hour"
        case .d1:  return "Daily"
        case .w1:  return "Weekly"
        }
    }
    
    /// SuperTrend parameters optimized for this timeframe
    var superTrendParams: (period: Int, multiplier: Double) {
        switch self {
        case .m15: return (period: 7, multiplier: 2.0)   // Fast, tight stops
        case .h1:  return (period: 8, multiplier: 2.5)   // Slightly wider
        case .h4:  return (period: 10, multiplier: 3.0)  // Standard
        case .d1:  return (period: 10, multiplier: 3.0)  // Standard
        case .w1:  return (period: 14, multiplier: 4.0)  // Wide, less noise
        }
    }
}
