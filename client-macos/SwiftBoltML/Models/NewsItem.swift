import Foundation

struct NewsItem: Codable, Identifiable {
    let id: String
    let title: String
    let source: String
    let url: String
    let publishedAt: Date
    let summary: String?

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

    enum CodingKeys: String, CodingKey {
        case id, title, source, url
        case publishedAt = "publishedAt"
        case summary
    }

    init(id: String, title: String, source: String, url: String, publishedAt: Date, summary: String?) {
        self.id = id
        self.title = title
        self.source = source
        self.url = url
        self.publishedAt = publishedAt
        self.summary = summary
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)

        self.id = try container.decode(String.self, forKey: .id)
        self.title = try container.decode(String.self, forKey: .title)
        self.source = try container.decode(String.self, forKey: .source)
        self.url = try container.decode(String.self, forKey: .url)
        self.summary = try container.decodeIfPresent(String.self, forKey: .summary)

        let dateString = try container.decode(String.self, forKey: .publishedAt)

        // Try with fractional seconds first, then without
        if let date = Self.iso8601FormatterWithFractional.date(from: dateString) {
            self.publishedAt = date
        } else if let date = Self.iso8601FormatterWithoutFractional.date(from: dateString) {
            self.publishedAt = date
        } else {
            throw DecodingError.dataCorruptedError(
                forKey: .publishedAt,
                in: container,
                debugDescription: "Invalid date format: \(dateString)"
            )
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(id, forKey: .id)
        try container.encode(title, forKey: .title)
        try container.encode(source, forKey: .source)
        try container.encode(url, forKey: .url)
        try container.encode(summary, forKey: .summary)
        try container.encode(Self.iso8601FormatterWithFractional.string(from: publishedAt), forKey: .publishedAt)
    }
}
