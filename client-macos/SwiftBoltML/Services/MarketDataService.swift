import Foundation

struct MarketDataPayload {
    let bars: [OHLCBar]
    let mlSummary: MLSummary?
}

final class MarketDataService {
    private let session: URLSession
    private let tokenProvider: @Sendable () async throws -> String

    init(
        session: URLSession = .shared,
        tokenProvider: @escaping @Sendable () async throws -> String = { Config.supabaseAnonKey }
    ) {
        self.session = session
        self.tokenProvider = tokenProvider
    }

    func fetchChart(symbol: String, timeframe: String) async throws -> MarketDataPayload {
        let token = try await tokenProvider()
        let response = try await APIClient.shared.fetchConsolidatedChart(
            symbol: symbol,
            timeframe: timeframe,
            start: nil,
            end: nil,
            includeOptions: false,
            includeForecast: true,
            bearerToken: token
        )

        let bars = try response.bars.map { bar in
            OHLCBar(
                ts: try Self.parseISO8601(bar.ts),
                open: bar.open,
                high: bar.high,
                low: bar.low,
                close: bar.close,
                volume: bar.volume
            )
        }

        let mlSummary: MLSummary?
        if let forecast = response.forecast {
            let points: [ForecastPoint] = try forecast.points.map { p in
                ForecastPoint(
                    ts: Int(Self.parseISO8601(p.ts).timeIntervalSince1970),
                    value: p.value,
                    lower: p.lower,
                    upper: p.upper
                )
            }

            mlSummary = MLSummary(
                overallLabel: forecast.label,
                confidence: forecast.confidence,
                horizons: [ForecastSeries(horizon: forecast.horizon, points: points)],
                srLevels: nil,
                srDensity: nil,
                ensembleType: nil,
                modelAgreement: nil,
                trainingStats: nil
            )
        } else {
            mlSummary = nil
        }

        return MarketDataPayload(bars: bars, mlSummary: mlSummary)
    }

    private static func parseISO8601(_ value: String) throws -> Date {
        let f1 = ISO8601DateFormatter()
        f1.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let f2 = ISO8601DateFormatter()
        f2.formatOptions = [.withInternetDateTime]
        let f3 = ISO8601DateFormatter()
        f3.formatOptions = [.withInternetDateTime, .withColonSeparatorInTimeZone]
        let f4 = ISO8601DateFormatter()
        f4.formatOptions = [.withInternetDateTime, .withFractionalSeconds, .withColonSeparatorInTimeZone]

        if let d = f1.date(from: value) ?? f2.date(from: value) ?? f3.date(from: value) ?? f4.date(from: value) {
            return d
        }

        throw APIError.decodingError(NSError(domain: "MarketDataService", code: 1))
    }
}
