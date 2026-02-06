import Foundation

struct ChartDataV2Response: Codable, Equatable {
    let symbol: String
    let symbolId: String?
    let timeframe: String
    let layers: ChartLayers
    let metadata: ChartMetadata
    let dataQuality: DataQuality?
    let mlSummary: MLSummary?
    let indicators: IndicatorData?
    let superTrendAI: SuperTrendAIData?

    private enum CodingKeys: String, CodingKey {
        case symbol
        case symbolId = "symbol_id"
        case timeframe
        case layers
        case metadata
        case dataQuality
        case mlSummary
        case indicators
        case superTrendAI
    }

    private enum LegacyCodingKeys: String, CodingKey {
        case meta
        case layers
    }

    private struct LegacyMeta: Decodable {
        let symbol: String?
        let timeframeEnum: String?
        let timeframeInput: String?
        let start: String?
        let end: String?

        enum CodingKeys: String, CodingKey {
            case symbol
            case timeframeEnum = "timeframe_enum"
            case timeframeInput = "timeframe_input"
            case start
            case end
        }
    }

    private struct LegacyLayers: Decodable {
        let historical: [OHLCBar]
        let intraday: [OHLCBar]
        let forecast: [OHLCBar]

        private enum CodingKeys: String, CodingKey {
            case historical
            case intraday
            case forecast
        }

        init(from decoder: Decoder) throws {
            let container = try decoder.container(keyedBy: CodingKeys.self)
            historical = Self.decodeBars(container, forKey: .historical)
            intraday = Self.decodeBars(container, forKey: .intraday)
            forecast = Self.decodeBars(container, forKey: .forecast)
        }

        private static func decodeBars(_ container: KeyedDecodingContainer<CodingKeys>, forKey key: CodingKeys) -> [OHLCBar] {
            if let bars = try? container.decode([OHLCBar].self, forKey: key) {
                return bars
            }

            // Some legacy responses wrap each layer as an object (count/provider/data/...)
            if let layer = try? container.decode(LayerData.self, forKey: key) {
                return layer.data
            }

            return []
        }
    }

    init(from decoder: Decoder) throws {
        var decodedSymbol = ""
        var decodedSymbolId: String?
        var decodedTimeframe = ""

        var decodedLayers = ChartLayers(
            historical: LayerData(count: 0, provider: "", data: [], oldestBar: nil, newestBar: nil),
            intraday: LayerData(count: 0, provider: "", data: [], oldestBar: nil, newestBar: nil),
            forecast: LayerData(count: 0, provider: "", data: [], oldestBar: nil, newestBar: nil)
        )

        var decodedMetadata = ChartMetadata(totalBars: 0, startDate: "", endDate: "")

        var decodedDataQuality: DataQuality?
        var decodedMLSummary: MLSummary?
        var decodedIndicators: IndicatorData?
        var decodedSuperTrendAI: SuperTrendAIData?

        do {
            let container = try decoder.container(keyedBy: CodingKeys.self)
            decodedSymbol = try container.decode(String.self, forKey: .symbol)
            decodedSymbolId = try container.decodeIfPresent(String.self, forKey: .symbolId)
            decodedTimeframe = try container.decode(String.self, forKey: .timeframe)
            decodedLayers = try container.decode(ChartLayers.self, forKey: .layers)
            decodedMetadata = try container.decode(ChartMetadata.self, forKey: .metadata)
            decodedDataQuality = try container.decodeIfPresent(DataQuality.self, forKey: .dataQuality)
            decodedMLSummary = try container.decodeIfPresent(MLSummary.self, forKey: .mlSummary)
            decodedIndicators = try container.decodeIfPresent(IndicatorData.self, forKey: .indicators)
            decodedSuperTrendAI = try container.decodeIfPresent(SuperTrendAIData.self, forKey: .superTrendAI)
        } catch {
            let legacy = try decoder.container(keyedBy: LegacyCodingKeys.self)
            let meta = try legacy.decode(LegacyMeta.self, forKey: .meta)
            let rawLayers = try legacy.decode(LegacyLayers.self, forKey: .layers)

            let historicalBars = rawLayers.historical
            let intradayBars = rawLayers.intraday
            let forecastBars = rawLayers.forecast

            let allBars = (historicalBars + intradayBars + forecastBars).sorted(by: { $0.ts < $1.ts })
            let computedStart = allBars.first?.ts.ISO8601Format()
            let computedEnd = allBars.last?.ts.ISO8601Format()

            decodedSymbol = meta.symbol ?? ""
            decodedSymbolId = nil
            decodedTimeframe = meta.timeframeEnum ?? meta.timeframeInput ?? ""

            decodedLayers = ChartLayers(
                historical: LayerData(
                    count: historicalBars.count,
                    provider: "unknown",
                    data: historicalBars,
                    oldestBar: historicalBars.first?.ts.ISO8601Format(),
                    newestBar: historicalBars.last?.ts.ISO8601Format()
                ),
                intraday: LayerData(
                    count: intradayBars.count,
                    provider: "unknown",
                    data: intradayBars,
                    oldestBar: intradayBars.first?.ts.ISO8601Format(),
                    newestBar: intradayBars.last?.ts.ISO8601Format()
                ),
                forecast: LayerData(
                    count: forecastBars.count,
                    provider: "unknown",
                    data: forecastBars,
                    oldestBar: forecastBars.first?.ts.ISO8601Format(),
                    newestBar: forecastBars.last?.ts.ISO8601Format()
                )
            )

            decodedMetadata = ChartMetadata(
                totalBars: allBars.count,
                startDate: meta.start ?? computedStart ?? "",
                endDate: meta.end ?? computedEnd ?? ""
            )

            decodedDataQuality = nil
            decodedMLSummary = nil
            decodedIndicators = nil
            decodedSuperTrendAI = nil
        }

        self.symbol = decodedSymbol
        self.symbolId = decodedSymbolId
        self.timeframe = decodedTimeframe
        self.layers = decodedLayers
        self.metadata = decodedMetadata
        self.dataQuality = decodedDataQuality
        self.mlSummary = decodedMLSummary
        self.indicators = decodedIndicators
        self.superTrendAI = decodedSuperTrendAI
    }

    init(
        symbol: String,
        symbolId: String? = nil,
        timeframe: String,
        layers: ChartLayers,
        metadata: ChartMetadata,
        dataQuality: DataQuality?,
        mlSummary: MLSummary?,
        indicators: IndicatorData?,
        superTrendAI: SuperTrendAIData?
    ) {
        self.symbol = symbol
        self.symbolId = symbolId
        self.timeframe = timeframe
        self.layers = layers
        self.metadata = metadata
        self.dataQuality = dataQuality
        self.mlSummary = mlSummary
        self.indicators = indicators
        self.superTrendAI = superTrendAI
    }
}

struct ChartLayers: Codable, Equatable {
    let historical: LayerData
    let intraday: LayerData
    let forecast: LayerData
}

struct LayerData: Codable, Equatable {
    let count: Int
    let provider: String
    let data: [OHLCBar]
    let oldestBar: String?
    let newestBar: String?
}

struct ChartMetadata: Codable, Equatable {
    let totalBars: Int
    let startDate: String
    let endDate: String
    
    enum CodingKeys: String, CodingKey {
        case totalBars = "total_bars"
        case startDate = "start_date"
        case endDate = "end_date"
    }
}

struct DataQuality: Codable, Equatable {
    let dataAgeHours: Int?
    let isStale: Bool
    let hasRecentData: Bool
    let historicalDepthDays: Int
    let sufficientForML: Bool
    let barCount: Int
    
    var statusDescription: String {
        if isStale {
            return "⚠️ Data is stale (> 24 hours old)"
        } else if hasRecentData {
            return "✅ Fresh data (< 4 hours old)"
        } else {
            return "🔄 Recent data (< 24 hours old)"
        }
    }
    
    var mlTrainingStatus: String {
        if sufficientForML {
            return "✅ Sufficient for ML (\(barCount) bars)"
        } else {
            return "⚠️ Insufficient for ML (need 250+ bars, have \(barCount))"
        }
    }
}

extension ChartDataV2Response {
    var allBars: [OHLCBar] {
        layers.historical.data + layers.intraday.data
    }
    
    var allBarsWithForecast: [OHLCBar] {
        layers.historical.data + layers.intraday.data + layers.forecast.data
    }
    
    var hasIntraday: Bool {
        layers.intraday.count > 0
    }
    
    var hasForecast: Bool {
        layers.forecast.count > 0
    }
    
    var isDataFresh: Bool {
        dataQuality?.hasRecentData ?? false
    }
    
    var isDataStale: Bool {
        dataQuality?.isStale ?? true
    }
    
    var dataAgeDescription: String {
        guard let ageHours = dataQuality?.dataAgeHours else {
            return "Unknown age"
        }
        if ageHours < 1 {
            return "< 1 hour old"
        } else if ageHours < 24 {
            return "\(ageHours) hours old"
        } else {
            let days = ageHours / 24
            return "\(days) days old"
        }
    }
}
