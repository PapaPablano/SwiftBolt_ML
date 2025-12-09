import Foundation

struct NewsResponse: Codable {
    let symbol: String?
    let items: [NewsItem]
}
