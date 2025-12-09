import Foundation

struct NewsItem: Codable, Identifiable {
    let id: String
    let title: String
    let source: String
    let url: String
    let publishedAt: Date
    let summary: String?

    enum CodingKeys: String, CodingKey {
        case id, title, source, url
        case publishedAt = "published_at"
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
        guard let date = ISO8601DateFormatter().date(from: dateString) else {
            throw DecodingError.dataCorruptedError(
                forKey: .publishedAt,
                in: container,
                debugDescription: "Invalid date format: \(dateString)"
            )
        }
        self.publishedAt = date
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(id, forKey: .id)
        try container.encode(title, forKey: .title)
        try container.encode(source, forKey: .source)
        try container.encode(url, forKey: .url)
        try container.encode(summary, forKey: .summary)
        try container.encode(ISO8601DateFormatter().string(from: publishedAt), forKey: .publishedAt)
    }
}
