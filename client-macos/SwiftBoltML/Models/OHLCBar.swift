import Foundation

struct OHLCBar: Codable, Identifiable {
    let ts: Date
    let open: Double
    let high: Double
    let low: Double
    let close: Double
    let volume: Double

    var id: Date { ts }

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
        guard let date = ISO8601DateFormatter().date(from: tsString) else {
            throw DecodingError.dataCorruptedError(
                forKey: .ts,
                in: container,
                debugDescription: "Invalid date format: \(tsString)"
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
        try container.encode(ISO8601DateFormatter().string(from: ts), forKey: .ts)
        try container.encode(open, forKey: .open)
        try container.encode(high, forKey: .high)
        try container.encode(low, forKey: .low)
        try container.encode(close, forKey: .close)
        try container.encode(volume, forKey: .volume)
    }
}
