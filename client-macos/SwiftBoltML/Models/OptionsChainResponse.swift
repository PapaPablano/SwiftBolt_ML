import Foundation

struct OptionsChainResponse: Codable {
    let underlying: String
    let timestamp: TimeInterval
    let expirations: [TimeInterval]
    let calls: [OptionContract]
    let puts: [OptionContract]

    var expirationDates: [Date] {
        expirations.map { Date(timeIntervalSince1970: $0) }
    }

    func contracts(for expiration: TimeInterval) -> (calls: [OptionContract], puts: [OptionContract]) {
        let filteredCalls = calls.filter { $0.expiration == expiration }
        let filteredPuts = puts.filter { $0.expiration == expiration }
        return (filteredCalls, filteredPuts)
    }

    func nearestExpiration(to date: Date = Date()) -> TimeInterval? {
        let now = date.timeIntervalSince1970
        return expirations
            .filter { $0 >= now }
            .min()
    }
}
