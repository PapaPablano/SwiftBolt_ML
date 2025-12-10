import Foundation

struct OHLCBar: Codable, Identifiable {
    let ts: Date
    let open: Double
    let high: Double
    let low: Double
    let close: Double
    let volume: Double

    var id: Date { ts }

    // Static formatters to handle multiple ISO8601 formats
    private static let iso8601FormatterWithFractional: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter
    }()

    private static let iso8601FormatterWithoutFractional: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]
        return formatter
    }()

    // Additional fallback formatters for edge cases
    private static let iso8601FormatterColonTimezone: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withColonSeparatorInTimeZone]
        return formatter
    }()

    private static let iso8601FormatterColonTimezoneWithFractional: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds, .withColonSeparatorInTimeZone]
        return formatter
    }()

    enum CodingKeys: String, CodingKey {
        case ts, open, high, low, close, volume
    }

    init(ts: Date, open: Double, high: Double, low: Double, close: Double, volume: Double) {
        self.ts = ts
        self.open = open
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)

        let tsString = try container.decode(String.self, forKey: .ts)

        // Try multiple ISO8601 formats in order of likelihood:
        // 1. With fractional seconds: 2025-09-02T04:00:00.000Z
        // 2. Without fractional: 2025-12-05T14:00:00+00:00
        // 3. With colon in timezone: 2025-12-05T14:00:00+00:00
        // 4. With colon and fractional: 2025-12-05T14:00:00.000+00:00
        let formatters = [
            Self.iso8601FormatterWithFractional,
            Self.iso8601FormatterWithoutFractional,
            Self.iso8601FormatterColonTimezone,
            Self.iso8601FormatterColonTimezoneWithFractional
        ]

        var parsedDate: Date?
        for formatter in formatters {
            if let date = formatter.date(from: tsString) {
                parsedDate = date
                break
            }
        }

        guard let date = parsedDate else {
            print("[DEBUG] ⚠️ FAILED TO PARSE DATE: '\(tsString)'")
            print("[DEBUG] Tried all ISO8601 formatters")
            throw DecodingError.dataCorruptedError(
                forKey: .ts,
                in: container,
                debugDescription: "Invalid date format: '\(tsString)'. Tried multiple ISO8601 formats."
            )
        }

        self.ts = date
        self.open = try container.decode(Double.self, forKey: .open)
        self.high = try container.decode(Double.self, forKey: .high)
        self.low = try container.decode(Double.self, forKey: .low)
        self.close = try container.decode(Double.self, forKey: .close)
        self.volume = try container.decode(Double.self, forKey: .volume)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(Self.iso8601FormatterWithFractional.string(from: ts), forKey: .ts)
        try container.encode(open, forKey: .open)
        try container.encode(high, forKey: .high)
        try container.encode(low, forKey: .low)
        try container.encode(close, forKey: .close)
        try container.encode(volume, forKey: .volume)
    }
}
