// Timeframe.swift
import Foundation

public enum Timeframe: String, CaseIterable, Codable, Hashable, Identifiable {
    case m15, h1, h4, d1, w1
    public var id: String { rawValue }

    /// Is this an intraday timeframe?
    var isIntraday: Bool { self == .m15 || self == .h1 || self == .h4 }

    /// Token sent to your API
    var apiToken: String {
        switch self {
        case .m15: return "m15"
        case .h1:  return "h1"
        case .h4:  return "h4"
        case .d1:  return "d1"
        case .w1:  return "w1"
        }
    }

    /// Friendly short label for UI (kept short for compact cards)
    var displayName: String {
        switch self {
        case .m15: return "15m"
        case .h1:  return "1h"
        case .h4:  return "4h"
        case .d1:  return "1D"
        case .w1:  return "1W"
        }
    }

    /// Longer descriptive label if UI needs it
    var fullDisplayName: String {
        switch self {
        case .m15: return "15 Minute"
        case .h1:  return "1 Hour"
        case .h4:  return "4 Hour"
        case .d1:  return "1 Day"
        case .w1:  return "1 Week"
        }
    }

    /// Order index (low -> high) for consistent sorting in multi-timeframe views
    var orderIndex: Int {
        switch self {
        case .m15: return 0
        case .h1:  return 1
        case .h4:  return 2
        case .d1:  return 3
        case .w1:  return 4
        }
    }

    /// Convenience: all timeframes in canonical order
    static var allOrdered: [Timeframe] {
        return [.m15, .h1, .h4, .d1, .w1]
    }

    /// Robust initializer that accepts a variety of legacy/remote tokens and normalizes them.
    /// Examples accepted: "m15", "15m", "15min", "M15", "1h", "H1", "1hour", "d1", "1D", "1day", "w1", "1w", "week"
    init?(from raw: String) {
        let cleaned = raw
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .replacingOccurrences(of: "-", with: "")
            .replacingOccurrences(of: "_", with: "")
            .lowercased()

        switch cleaned {
        case "m15", "15m", "15min", "15mins", "15minute", "15minutes": self = .m15
        case "h1", "1h", "1hour", "1hours", "hour": self = .h1
        case "h4", "4h", "4hour", "4hours": self = .h4
        case "d1", "1d", "1day", "day", "daily": self = .d1
        case "w1", "1w", "1week", "week", "weekly": self = .w1
        default:
            return nil
        }
    }

    /// SuperTrend defaults by timeframe (tune as you like)
    var superTrendParams: (period: Int, multiplier: Double) {
        switch self {
        case .m15: return (10, 2.0)
        case .h1:  return (10, 2.2)
        case .h4:  return (10, 2.4)
        case .d1:  return (10, 3.0)
        case .w1:  return (7,  3.0)
        }
    }
    
    /// SPEC-8: Backfill window in days for coverage checks
    var backfillWindowDays: Int {
        switch self {
        case .m15: return 30
        case .h1, .h4: return 90
        case .d1, .w1: return 365
        }
    }
    
    /// Alpaca API format (what Alpaca expects in the timeframe parameter)
    var alpacaFormat: String {
        switch self {
        case .m15: return "15Min"
        case .h1:  return "1Hour"
        case .h4:  return "4Hour"
        case .d1:  return "1Day"
        case .w1:  return "1Week"
        }
    }
    
    /// Chart auto-refresh interval in nanoseconds (matches timeframe duration)
    /// Used for automatic chart data updates during market hours
    var chartRefreshInterval: UInt64 {
        switch self {
        case .m15: return 15 * 60 * 1_000_000_000      // 15 minutes
        case .h1:  return 60 * 60 * 1_000_000_000      // 1 hour
        case .h4:  return 4 * 60 * 60 * 1_000_000_000  // 4 hours
        case .d1:  return 24 * 60 * 60 * 1_000_000_000 // 24 hours (end of day)
        case .w1:  return 7 * 24 * 60 * 60 * 1_000_000_000 // 1 week
        }
    }
    
    /// Minimum refresh interval in seconds (for rate limiting)
    var minRefreshSeconds: Double {
        switch self {
        case .m15: return 60     // Don't refresh more than once per minute
        case .h1:  return 300    // Don't refresh more than once per 5 minutes
        case .h4:  return 900    // Don't refresh more than once per 15 minutes
        case .d1:  return 3600   // Don't refresh more than once per hour
        case .w1:  return 86400  // Don't refresh more than once per day
        }
    }
}
