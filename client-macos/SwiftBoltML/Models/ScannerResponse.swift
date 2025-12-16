import Foundation
import SwiftUI

// MARK: - Scanner Watchlist Response

struct ScannerWatchlistResponse: Codable {
    let watchlist: [WatchlistItem]
    let alerts: [ScannerAlert]
    let scannedAt: String

    var scannedDate: Date? {
        ISO8601DateFormatter().date(from: scannedAt)
    }
}

// MARK: - Watchlist Item (with ML and Alert info)

struct WatchlistItem: Codable, Identifiable {
    var id: String { symbol }

    let symbol: String
    let assetType: String
    let mlLabel: MLTrendLabel?
    let mlConfidence: Double?
    let unreadAlertCount: Int
    let hasCriticalAlert: Bool
    let lastPrice: Double?
    let priceChange: Double?
    let priceChangePercent: Double?

    var priceChangeColor: Color {
        guard let change = priceChange else { return .secondary }
        if change > 0 {
            return .green
        } else if change < 0 {
            return .red
        } else {
            return .secondary
        }
    }

    var mlLabelColor: Color {
        guard let label = mlLabel else { return .secondary }
        switch label {
        case .bullish:
            return .green
        case .neutral:
            return .orange
        case .bearish:
            return .red
        }
    }

    var hasAlerts: Bool {
        unreadAlertCount > 0
    }

    var alertBadgeColor: Color {
        if hasCriticalAlert {
            return .red
        } else if unreadAlertCount > 0 {
            return .orange
        } else {
            return .clear
        }
    }
}

// MARK: - Scanner Alert

struct ScannerAlert: Codable, Identifiable {
    let id: String
    let symbol: String
    let triggeredAt: String
    let conditionLabel: String
    let conditionType: AlertConditionType?
    let severity: AlertSeverity
    let details: [String: AnyCodable]?
    let isRead: Bool

    var triggeredDate: Date? {
        ISO8601DateFormatter().date(from: triggeredAt)
    }

    var severityColor: Color {
        switch severity {
        case .info:
            return .blue
        case .warning:
            return .orange
        case .critical:
            return .red
        }
    }

    var severityIcon: String {
        switch severity {
        case .info:
            return "info.circle.fill"
        case .warning:
            return "exclamationmark.triangle.fill"
        case .critical:
            return "exclamationmark.octagon.fill"
        }
    }

    var conditionTypeIcon: String {
        guard let type = conditionType else { return "chart.line.uptrend.xyaxis" }
        switch type {
        case .technical:
            return "waveform.path.ecg"
        case .ml:
            return "brain.head.profile"
        case .volume:
            return "chart.bar.fill"
        case .price:
            return "dollarsign.circle.fill"
        }
    }
}

enum AlertConditionType: String, Codable {
    case technical
    case ml
    case volume
    case price
}

enum AlertSeverity: String, Codable {
    case info
    case warning
    case critical
}

// MARK: - AnyCodable for JSON details

struct AnyCodable: Codable {
    let value: Any

    init(_ value: Any) {
        self.value = value
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()

        if let bool = try? container.decode(Bool.self) {
            value = bool
        } else if let int = try? container.decode(Int.self) {
            value = int
        } else if let double = try? container.decode(Double.self) {
            value = double
        } else if let string = try? container.decode(String.self) {
            value = string
        } else if let array = try? container.decode([AnyCodable].self) {
            value = array.map { $0.value }
        } else if let dictionary = try? container.decode([String: AnyCodable].self) {
            value = dictionary.mapValues { $0.value }
        } else {
            value = NSNull()
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()

        switch value {
        case let bool as Bool:
            try container.encode(bool)
        case let int as Int:
            try container.encode(int)
        case let double as Double:
            try container.encode(double)
        case let string as String:
            try container.encode(string)
        case let array as [Any]:
            try container.encode(array.map { AnyCodable($0) })
        case let dictionary as [String: Any]:
            try container.encode(dictionary.mapValues { AnyCodable($0) })
        default:
            try container.encodeNil()
        }
    }
}

// MARK: - Example Data

extension WatchlistItem {
    static let example = WatchlistItem(
        symbol: "AAPL",
        assetType: "stock",
        mlLabel: .bullish,
        mlConfidence: 0.78,
        unreadAlertCount: 2,
        hasCriticalAlert: false,
        lastPrice: 195.50,
        priceChange: 2.30,
        priceChangePercent: 1.19
    )
}

extension ScannerAlert {
    static let example = ScannerAlert(
        id: UUID().uuidString,
        symbol: "AAPL",
        triggeredAt: ISO8601DateFormatter().string(from: Date()),
        conditionLabel: "RSI Oversold",
        conditionType: .technical,
        severity: .warning,
        details: ["rsi": AnyCodable(28.5), "threshold": AnyCodable(30.0)],
        isRead: false
    )
}
