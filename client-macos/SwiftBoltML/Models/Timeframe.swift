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

    /// Friendly label for UI
    var displayName: String {
        switch self {
        case .m15: return "15m"
        case .h1:  return "1h"
        case .h4:  return "4h"
        case .d1:  return "1D"
        case .w1:  return "1W"
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
}

