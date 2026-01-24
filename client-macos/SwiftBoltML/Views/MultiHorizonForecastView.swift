import SwiftUI

// MARK: - Multi-Horizon Forecast Models

struct MultiHorizonForecast: Codable, Identifiable {
    let id = UUID()
    let timeframe: String
    let symbol: String
    let baseHorizon: String
    let extendedHorizons: [String]
    let forecasts: [String: HorizonForecast]
    let consensusWeights: [String: Double]
    let handoffConfidence: [String: Double]
    let generatedAt: String?
    let currentPrice: Double?
    
    enum CodingKeys: String, CodingKey {
        case timeframe, symbol
        case baseHorizon = "base_horizon"
        case extendedHorizons = "extended_horizons"
        case forecasts
        case consensusWeights = "consensus_weights"
        case handoffConfidence = "handoff_confidence"
        case generatedAt = "generated_at"
        case currentPrice = "current_price"
    }
}

struct HorizonForecast: Codable {
    let target: Double
    let upperBand: Double
    let lowerBand: Double
    let confidence: Double
    let direction: String
    let layersAgreeing: Int
    let reasoning: String
    let keyDrivers: [String]
    
    enum CodingKeys: String, CodingKey {
        case target, confidence, direction, reasoning
        case upperBand = "upper_band"
        case lowerBand = "lower_band"
        case layersAgreeing = "layers_agreeing"
        case keyDrivers = "key_drivers"
    }
}

struct ConsensusForecast: Codable {
    let horizon: String
    let direction: String
    let confidence: Double
    let target: Double
    let upperBand: Double
    let lowerBand: Double
    let contributingTimeframes: [String]
    let agreementScore: Double
    let handoffQuality: Double
    
    enum CodingKeys: String, CodingKey {
        case horizon, direction, confidence, target
        case upperBand = "upper_band"
        case lowerBand = "lower_band"
        case contributingTimeframes = "contributing_timeframes"
        case agreementScore = "agreement_score"
        case handoffQuality = "handoff_quality"
    }
}

// MARK: - Multi-Horizon Forecast Grid View

struct MultiHorizonForecastGridView: View {
    let symbol: String
    let currentPrice: Double?
    
    @State private var multiHorizonForecasts: [String: MultiHorizonForecast] = [:]
    @State private var consensusForecasts: [ConsensusForecast] = []
    @State private var isLoading = false
    @State private var selectedView: ViewMode = .byTimeframe
    
    enum ViewMode: String, CaseIterable {
        case byTimeframe = "By Timeframe"
        case byHorizon = "By Horizon"
        case consensus = "Consensus"
    }
    
    var body: some View {
        VStack(spacing: 12) {
            // Header with view mode selector
            HStack {
                Text("Multi-Horizon Forecasts")
                    .font(.headline)
                
                Spacer()
                
                Picker("View", selection: $selectedView) {
                    ForEach(ViewMode.allCases, id: \.self) { mode in
                        Text(mode.rawValue).tag(mode)
                    }
                }
                .pickerStyle(.segmented)
                .frame(maxWidth: 300)
                
                Button(action: loadForecasts) {
                    Image(systemName: "arrow.clockwise")
                }
                .buttonStyle(.borderless)
                .disabled(isLoading)
            }
            .padding(.horizontal)
            
            if isLoading {
                ProgressView("Loading multi-horizon forecasts...")
                    .padding()
            } else {
                switch selectedView {
                case .byTimeframe:
                    timeframeView
                case .byHorizon:
                    horizonView
                case .consensus:
                    consensusView
                }
            }
        }
        .padding(.vertical, 8)
        .background(Color(nsColor: .controlBackgroundColor).opacity(0.5))
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .onAppear(perform: loadForecasts)
    }
    
    // MARK: - View by Timeframe
    
    private var timeframeView: some View {
        ScrollView {
            LazyVStack(spacing: 16) {
                ForEach(sortedTimeframes, id: \.self) { timeframe in
                    if let forecast = multiHorizonForecasts[timeframe] {
                        MultiHorizonTimeframeCard(
                            forecast: forecast,
                            currentPrice: currentPrice
                        )
                    }
                }
            }
            .padding(.horizontal)
        }
    }
    
    // MARK: - View by Horizon
    
    private var horizonView: some View {
        ScrollView {
            LazyVStack(spacing: 16) {
                ForEach(allHorizons, id: \.self) { horizon in
                    HorizonCascadeCard(
                        horizon: horizon,
                        forecasts: forecastsForHorizon(horizon),
                        currentPrice: currentPrice
                    )
                }
            }
            .padding(.horizontal)
        }
    }
    
    // MARK: - Consensus View
    
    private var consensusView: some View {
        ScrollView {
            LazyVStack(spacing: 12) {
                ForEach(consensusForecasts, id: \.horizon) { consensus in
                    ConsensusForecastCard(
                        consensus: consensus,
                        currentPrice: currentPrice
                    )
                }
            }
            .padding(.horizontal)
        }
    }
    
    // MARK: - Helpers
    
    private var sortedTimeframes: [String] {
        ["m15", "h1", "h4", "d1", "w1"].filter { multiHorizonForecasts.keys.contains($0) }
    }
    
    private var allHorizons: [String] {
        let horizons = Set(multiHorizonForecasts.values.flatMap { $0.forecasts.keys })
        return horizons.sorted { parseHorizonDays($0) < parseHorizonDays($1) }
    }
    
    private func forecastsForHorizon(_ horizon: String) -> [(String, HorizonForecast)] {
        multiHorizonForecasts.compactMap { timeframe, mhForecast in
            guard let forecast = mhForecast.forecasts[horizon] else { return nil }
            return (timeframe, forecast)
        }.sorted { lhs, rhs in
            let order = ["m15", "h1", "h4", "d1", "w1"]
            return (order.firstIndex(of: lhs.0) ?? 0) < (order.firstIndex(of: rhs.0) ?? 0)
        }
    }
    
    private func parseHorizonDays(_ horizon: String) -> Double {
        let h = horizon.lowercased()
        if h.hasSuffix("h") {
            return Double(h.dropLast()) ?? 0 / 24.0
        } else if h.hasSuffix("d") {
            return Double(h.dropLast()) ?? 0
        } else if h.hasSuffix("w") {
            return (Double(h.dropLast()) ?? 0) * 7
        } else if h.hasSuffix("m") {
            return (Double(h.dropLast()) ?? 0) * 30
        } else if h.hasSuffix("y") {
            return (Double(h.dropLast()) ?? 0) * 365
        }
        return 0
    }
    
    private func loadForecasts() {
        isLoading = true
        // TODO: Load from API
        // For now, placeholder
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            isLoading = false
        }
    }
}

// MARK: - Multi-Horizon Timeframe Card

struct MultiHorizonTimeframeCard: View {
    let forecast: MultiHorizonForecast
    let currentPrice: Double?
    
    @State private var isExpanded = true
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header
            HStack {
                Text(forecast.timeframe.uppercased())
                    .font(.title3.bold())
                
                Spacer()
                
                Button(action: { isExpanded.toggle() }) {
                    Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                        .font(.caption)
                }
                .buttonStyle(.borderless)
            }
            
            if isExpanded {
                // Primary (base) horizon
                if let baseForecast = forecast.forecasts[forecast.baseHorizon] {
                    PrimaryForecastView(
                        horizon: forecast.baseHorizon,
                        forecast: baseForecast,
                        currentPrice: currentPrice,
                        isPrimary: true
                    )
                }
                
                // Extended horizons
                ForEach(forecast.extendedHorizons, id: \.self) { horizon in
                    if let extForecast = forecast.forecasts[horizon] {
                        ExtendedForecastView(
                            horizon: horizon,
                            forecast: extForecast,
                            handoffConfidence: forecast.handoffConfidence[horizon] ?? 0,
                            currentPrice: currentPrice
                        )
                    }
                }
            }
        }
        .padding()
        .background(Color(nsColor: .controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(Color.secondary.opacity(0.2), lineWidth: 1)
        )
    }
}

// MARK: - Primary Forecast View

struct PrimaryForecastView: View {
    let horizon: String
    let forecast: HorizonForecast
    let currentPrice: Double?
    let isPrimary: Bool
    
    private var labelColor: Color {
        switch forecast.direction.lowercased() {
        case "bullish": return .green
        case "bearish": return .red
        default: return .orange
        }
    }
    
    private var deltaPct: Double? {
        guard let current = currentPrice, current > 0 else { return nil }
        return ((forecast.target - current) / current) * 100
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                // Horizon badge
                Text(horizon.uppercased())
                    .font(.caption.bold())
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(labelColor.opacity(0.2))
                    .clipShape(Capsule())
                
                if isPrimary {
                    Text("PRIMARY")
                        .font(.caption2.bold())
                        .foregroundStyle(.secondary)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(Color.secondary.opacity(0.1))
                        .clipShape(Capsule())
                }
                
                Spacer()
                
                // Confidence
                HStack(spacing: 4) {
                    Image(systemName: "chart.bar.fill")
                        .font(.caption2)
                    Text("\(Int(forecast.confidence * 100))%")
                        .font(.caption.bold())
                }
                .foregroundStyle(labelColor)
            }
            
            // Direction and target
            HStack(alignment: .firstTextBaseline) {
                Text(forecast.direction.uppercased())
                    .font(.title2.bold())
                    .foregroundStyle(labelColor)
                
                Spacer()
                
                VStack(alignment: .trailing, spacing: 2) {
                    Text("$\(String(format: "%.2f", forecast.target))")
                        .font(.title3.bold())
                    
                    if let delta = deltaPct {
                        Text(delta >= 0 ? "+\(String(format: "%.1f", delta))%" : "\(String(format: "%.1f", delta))%")
                            .font(.caption)
                            .foregroundStyle(delta >= 0 ? .green : .red)
                    }
                }
            }
            
            // Bands
            HStack(spacing: 16) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Lower")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                    Text("$\(String(format: "%.2f", forecast.lowerBand))")
                        .font(.caption.bold())
                }
                
                VStack(alignment: .leading, spacing: 2) {
                    Text("Upper")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                    Text("$\(String(format: "%.2f", forecast.upperBand))")
                        .font(.caption.bold())
                }
                
                Spacer()
                
                VStack(alignment: .trailing, spacing: 2) {
                    Text("Layers")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                    Text("\(forecast.layersAgreeing)/3")
                        .font(.caption.bold())
                }
            }
            
            // Key drivers
            if !forecast.keyDrivers.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Key Drivers:")
                        .font(.caption2.bold())
                        .foregroundStyle(.secondary)
                    
                    ForEach(forecast.keyDrivers.prefix(3), id: \.self) { driver in
                        HStack(spacing: 4) {
                            Image(systemName: "circle.fill")
                                .font(.system(size: 4))
                                .foregroundStyle(.secondary)
                            Text(driver)
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
            }
        }
        .padding(12)
        .background(labelColor.opacity(0.05))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}

// MARK: - Extended Forecast View

struct ExtendedForecastView: View {
    let horizon: String
    let forecast: HorizonForecast
    let handoffConfidence: Double
    let currentPrice: Double?
    
    private var labelColor: Color {
        switch forecast.direction.lowercased() {
        case "bullish": return .green
        case "bearish": return .red
        default: return .orange
        }
    }
    
    private var deltaPct: Double? {
        guard let current = currentPrice, current > 0 else { return nil }
        return ((forecast.target - current) / current) * 100
    }
    
    var body: some View {
        HStack(spacing: 12) {
            // Horizon
            Text(horizon.uppercased())
                .font(.caption.bold())
                .frame(width: 50, alignment: .leading)
            
            // Direction indicator
            Image(systemName: forecast.direction.lowercased() == "bullish" ? "arrow.up.right" : "arrow.down.right")
                .font(.caption)
                .foregroundStyle(labelColor)
                .frame(width: 20)
            
            // Target
            Text("$\(String(format: "%.2f", forecast.target))")
                .font(.subheadline.bold())
                .frame(width: 80, alignment: .trailing)
            
            // Delta
            if let delta = deltaPct {
                Text(delta >= 0 ? "+\(String(format: "%.1f", delta))%" : "\(String(format: "%.1f", delta))%")
                    .font(.caption)
                    .foregroundStyle(delta >= 0 ? .green : .red)
                    .frame(width: 60, alignment: .trailing)
            }
            
            Spacer()
            
            // Handoff confidence
            HStack(spacing: 4) {
                Image(systemName: "arrow.right.circle.fill")
                    .font(.caption2)
                Text("\(Int(handoffConfidence * 100))%")
                    .font(.caption2.bold())
            }
            .foregroundStyle(handoffConfidence > 0.7 ? .green : handoffConfidence > 0.5 ? .orange : .red)
            
            // Confidence
            Text("\(Int(forecast.confidence * 100))%")
                .font(.caption.bold())
                .foregroundStyle(labelColor)
                .frame(width: 50, alignment: .trailing)
        }
        .padding(.vertical, 8)
        .padding(.horizontal, 12)
        .background(Color(nsColor: .controlBackgroundColor).opacity(0.5))
        .clipShape(RoundedRectangle(cornerRadius: 6))
    }
}

// MARK: - Horizon Cascade Card

struct HorizonCascadeCard: View {
    let horizon: String
    let forecasts: [(String, HorizonForecast)]
    let currentPrice: Double?
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(horizon.uppercased())
                .font(.headline.bold())
            
            ForEach(forecasts, id: \.0) { timeframe, forecast in
                CascadeForecastRow(
                    timeframe: timeframe,
                    forecast: forecast,
                    currentPrice: currentPrice
                )
            }
        }
        .padding()
        .background(Color(nsColor: .controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

struct CascadeForecastRow: View {
    let timeframe: String
    let forecast: HorizonForecast
    let currentPrice: Double?
    
    private var labelColor: Color {
        switch forecast.direction.lowercased() {
        case "bullish": return .green
        case "bearish": return .red
        default: return .orange
        }
    }
    
    var body: some View {
        HStack {
            Text(timeframe.uppercased())
                .font(.caption.bold())
                .frame(width: 40, alignment: .leading)
            
            Text(forecast.direction.uppercased())
                .font(.caption.bold())
                .foregroundStyle(labelColor)
                .frame(width: 80, alignment: .leading)
            
            Text("$\(String(format: "%.2f", forecast.target))")
                .font(.caption)
                .frame(width: 70, alignment: .trailing)
            
            Spacer()
            
            Text("\(Int(forecast.confidence * 100))%")
                .font(.caption.bold())
                .foregroundStyle(labelColor)
        }
        .padding(.vertical, 4)
    }
}

// MARK: - Consensus Forecast Card

struct ConsensusForecastCard: View {
    let consensus: ConsensusForecast
    let currentPrice: Double?
    
    private var labelColor: Color {
        switch consensus.direction.lowercased() {
        case "bullish": return .green
        case "bearish": return .red
        default: return .orange
        }
    }
    
    private var deltaPct: Double? {
        guard let current = currentPrice, current > 0 else { return nil }
        return ((consensus.target - current) / current) * 100
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text(consensus.horizon.uppercased())
                    .font(.headline.bold())
                
                Text("CONSENSUS")
                    .font(.caption2.bold())
                    .foregroundStyle(.white)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Color.blue)
                    .clipShape(Capsule())
                
                Spacer()
                
                Text("\(Int(consensus.confidence * 100))%")
                    .font(.title3.bold())
                    .foregroundStyle(labelColor)
            }
            
            HStack(alignment: .firstTextBaseline) {
                Text(consensus.direction.uppercased())
                    .font(.title2.bold())
                    .foregroundStyle(labelColor)
                
                Spacer()
                
                VStack(alignment: .trailing, spacing: 2) {
                    Text("$\(String(format: "%.2f", consensus.target))")
                        .font(.title3.bold())
                    
                    if let delta = deltaPct {
                        Text(delta >= 0 ? "+\(String(format: "%.1f", delta))%" : "\(String(format: "%.1f", delta))%")
                            .font(.caption)
                            .foregroundStyle(delta >= 0 ? .green : .red)
                    }
                }
            }
            
            HStack(spacing: 16) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Agreement")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                    Text("\(Int(consensus.agreementScore * 100))%")
                        .font(.caption.bold())
                }
                
                VStack(alignment: .leading, spacing: 2) {
                    Text("Handoff Quality")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                    Text("\(Int(consensus.handoffQuality * 100))%")
                        .font(.caption.bold())
                }
                
                Spacer()
                
                VStack(alignment: .trailing, spacing: 2) {
                    Text("Timeframes")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                    Text("\(consensus.contributingTimeframes.count)")
                        .font(.caption.bold())
                }
            }
            
            // Contributing timeframes
            HStack(spacing: 4) {
                ForEach(consensus.contributingTimeframes, id: \.self) { tf in
                    Text(tf.uppercased())
                        .font(.caption2.bold())
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(Color.secondary.opacity(0.2))
                        .clipShape(Capsule())
                }
            }
        }
        .padding()
        .background(labelColor.opacity(0.08))
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(labelColor.opacity(0.3), lineWidth: 2)
        )
    }
}

// MARK: - Previews

#if DEBUG
struct MultiHorizonForecastView_Previews: PreviewProvider {
    static var previews: some View {
        MultiHorizonForecastGridView(
            symbol: "AAPL",
            currentPrice: 150.0
        )
        .frame(width: 800, height: 600)
    }
}
#endif
