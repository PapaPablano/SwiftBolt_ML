import SwiftUI

struct ChartView: View {
    @EnvironmentObject var appViewModel: AppViewModel

    private var chartViewModel: ChartViewModel {
        appViewModel.chartViewModel
    }

    private var debugDescription: String {
        let isLoading = chartViewModel.isLoading
        let error = chartViewModel.errorMessage ?? "nil"

        let barCount: Int
        if let data = chartViewModel.chartData {
            barCount = data.bars.count
        } else {
            barCount = -1 // sentinel: no data set
        }

        return """
        [DEBUG] ChartView.body
        - isLoading: \(isLoading)
        - error: \(error)
        - chartData is \(chartViewModel.chartData == nil ? "nil" : "non-nil")
        - barCount: \(barCount)
        """
    }

    var body: some View {
        print(debugDescription)

        // Force body re-evaluation by accessing published properties
        let _ = chartViewModel.chartData?.bars.count
        let _ = chartViewModel.isLoading
        let _ = appViewModel.chartViewModel.chartData

        return VStack(spacing: 0) {
            ChartHeader(
                symbol: chartViewModel.selectedSymbol,
                lastBar: chartViewModel.bars.last
            )

            HStack {
                TimeframePicker(
                    selectedTimeframe: chartViewModel.timeframe,
                    onSelect: { timeframe in
                        Task {
                            await chartViewModel.setTimeframe(timeframe)
                        }
                    }
                )

                Spacer()

                Button(action: {
                    Task {
                        await chartViewModel.loadChart()
                    }
                }) {
                    Image(systemName: "arrow.clockwise")
                        .font(.system(size: 14))
                        .foregroundColor(.secondary)
                }
                .buttonStyle(.plain)
                .help("Refresh chart data")
                .padding(.trailing, 8)

                IndicatorToggleMenu(config: $appViewModel.chartViewModel.indicatorConfig)
            }
            .padding(.horizontal)
            .padding(.top, 8)

            // Simplified conditional logic - check data directly
            if chartViewModel.isLoading {
                LoadingChartView()
            } else if let error = chartViewModel.errorMessage {
                ChartErrorView(message: error) {
                    Task {
                        await chartViewModel.loadChart()
                    }
                }
            } else if let chartData = chartViewModel.chartData, !chartData.bars.isEmpty {
                // ✅ Always render the chart if we have bars
                VStack(spacing: 0) {
                    // ML Report Card (if available)
                    if let mlSummary = chartData.mlSummary {
                        MLReportCard(mlSummary: mlSummary)
                            .padding(.horizontal)
                            .padding(.top, 8)
                    }

                    AdvancedChartView(
                        bars: chartData.bars,
                        sma20: chartViewModel.sma20,
                        sma50: chartViewModel.sma50,
                        ema9: chartViewModel.ema9,
                        ema21: chartViewModel.ema21,
                        rsi: chartViewModel.rsi,
                        config: chartViewModel.indicatorConfig,
                        mlSummary: chartData.mlSummary,
                        macdLine: chartViewModel.macdLine,
                        macdSignal: chartViewModel.macdSignal,
                        macdHistogram: chartViewModel.macdHistogram,
                        stochasticK: chartViewModel.stochasticK,
                        stochasticD: chartViewModel.stochasticD,
                        kdjK: chartViewModel.kdjK,
                        kdjD: chartViewModel.kdjD,
                        kdjJ: chartViewModel.kdjJ,
                        adxLine: chartViewModel.adxLine,
                        plusDI: chartViewModel.plusDI,
                        minusDI: chartViewModel.minusDI,
                        superTrendLine: chartViewModel.superTrendLine,
                        superTrendTrend: chartViewModel.superTrendTrend,
                        bollingerUpper: chartViewModel.bollingerUpper,
                        bollingerMiddle: chartViewModel.bollingerMiddle,
                        bollingerLower: chartViewModel.bollingerLower,
                        atr: chartViewModel.atr
                    )
                    .padding()
                    .id("advanced-chart-\(chartData.bars.count)-\(chartData.bars.first?.ts.timeIntervalSince1970 ?? 0)")

                    if let latestBar = chartData.bars.last {
                        OHLCBarView(bar: latestBar)
                            .padding(.horizontal)
                            .padding(.bottom)
                    }
                }
                .id("chart-container-\(chartData.bars.count)")
            } else if let chartData = chartViewModel.chartData, chartData.bars.isEmpty {
                // Data loaded, but empty
                EmptyChartView()
            } else {
                // No request has been made yet (first launch & no symbol)
                Color.clear
            }
        }
        .background(Color(nsColor: .controlBackgroundColor))
        .onChange(of: chartChangeToken, initial: true) { oldValue, newValue in
            print("[DEBUG] 🔄 ChartView.onChange - chartData changed!")
            print("[DEBUG] - Old bars: \(oldValue.barCount) | New bars: \(newValue.barCount)")
            print("[DEBUG] - Old first ts: \(oldValue.firstTimestamp) | New first ts: \(newValue.firstTimestamp)")

            if let newData = chartViewModel.chartData {
                print("[DEBUG] - New symbol: \(newData.symbol)")
                print("[DEBUG] - New timeframe: \(newData.timeframe)")
            }
        }
        .onChange(of: chartViewModel.isLoading) { oldValue, newValue in
            print("[DEBUG] 🔄 ChartView.onChange - isLoading changed from \(oldValue) to \(newValue)")
        }
    }

    private var chartChangeToken: ChartChangeToken {
        ChartChangeToken(
            barCount: chartViewModel.chartData?.bars.count ?? 0,
            firstTimestamp: chartViewModel.chartData?.bars.first?.ts.timeIntervalSince1970 ?? 0
        )
    }
}

private struct ChartChangeToken: Equatable {
    let barCount: Int
    let firstTimestamp: TimeInterval
}

struct ChartHeader: View {
    let symbol: Symbol?
    let lastBar: OHLCBar?

    var body: some View {
        print("[DEBUG] 🔵 ChartHeader.body rendering with symbol: \(symbol?.ticker ?? "nil")")

        return HStack {
            VStack(alignment: .leading, spacing: 4) {
                if let symbol = symbol {
                    Text(symbol.ticker)
                        .font(.title.bold())
                    Text(symbol.description)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
            }

            Spacer()

            if let bar = lastBar {
                VStack(alignment: .trailing, spacing: 4) {
                    Text(formatPrice(bar.close))
                        .font(.title2.bold().monospacedDigit())
                    PriceChangeView(open: bar.open, close: bar.close)
                }
            }
        }
        .padding()
    }

    private func formatPrice(_ price: Double) -> String {
        String(format: "$%.2f", price)
    }
}

struct PriceChangeView: View {
    let open: Double
    let close: Double

    private var change: Double {
        close - open
    }

    private var changePercent: Double {
        guard open != 0 else { return 0 }
        return (change / open) * 100
    }

    private var isPositive: Bool {
        change >= 0
    }

    var body: some View {
        HStack(spacing: 4) {
            Image(systemName: isPositive ? "arrow.up.right" : "arrow.down.right")
            Text(String(format: "%+.2f (%.2f%%)", change, changePercent))
                .monospacedDigit()
        }
        .font(.subheadline)
        .foregroundStyle(isPositive ? .green : .red)
    }
}

struct TimeframePicker: View {
    let selectedTimeframe: String
    let onSelect: (String) -> Void

    private let timeframes: [(String, String)] = [
        ("m15", "15M"),
        ("h1", "1H"),
        ("h4", "4H"),
        ("d1", "D"),
        ("w1", "W")
    ]

    var body: some View {
        HStack(spacing: 4) {
            ForEach(timeframes, id: \.0) { timeframe, label in
                Button {
                    onSelect(timeframe)
                } label: {
                    Text(label)
                        .font(.caption.bold())
                        .frame(minWidth: 36)
                        .padding(.vertical, 6)
                        .padding(.horizontal, 8)
                        .background(selectedTimeframe == timeframe ? Color.accentColor : Color.clear)
                        .foregroundStyle(selectedTimeframe == timeframe ? .white : .primary)
                        .clipShape(RoundedRectangle(cornerRadius: 6))
                }
                .buttonStyle(.plain)
            }

            Spacer()
        }
    }
}

struct OHLCBarView: View {
    let bar: OHLCBar

    var body: some View {
        HStack(spacing: 16) {
            OHLCItem(label: "O", value: bar.open)
            OHLCItem(label: "H", value: bar.high)
            OHLCItem(label: "L", value: bar.low)
            OHLCItem(label: "C", value: bar.close)
            OHLCItem(label: "Vol", value: bar.volume, isVolume: true)
            Spacer()
        }
        .font(.caption.monospacedDigit())
        .foregroundStyle(.secondary)
    }
}

struct OHLCItem: View {
    let label: String
    let value: Double
    var isVolume: Bool = false

    var body: some View {
        HStack(spacing: 4) {
            Text(label)
                .foregroundStyle(.tertiary)
            Text(isVolume ? formatVolume(value) : formatPrice(value))
        }
    }

    private func formatPrice(_ price: Double) -> String {
        String(format: "%.2f", price)
    }

    private func formatVolume(_ volume: Double) -> String {
        if volume >= 1_000_000 {
            return String(format: "%.1fM", volume / 1_000_000)
        } else if volume >= 1_000 {
            return String(format: "%.1fK", volume / 1_000)
        }
        return String(format: "%.0f", volume)
    }
}

struct LoadingChartView: View {
    var body: some View {
        VStack {
            ProgressView()
            Text("Loading chart data...")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct ChartErrorView: View {
    let message: String
    let onRetry: () -> Void

    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: "exclamationmark.triangle")
                .font(.largeTitle)
                .foregroundStyle(.orange)
            Text("Failed to load chart")
                .font(.headline)
            Text(message)
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Button("Retry", action: onRetry)
                .buttonStyle(.borderedProminent)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct EmptyChartView: View {
    var body: some View {
        VStack {
            Image(systemName: "chart.line.flattrend.xyaxis")
                .font(.largeTitle)
                .foregroundStyle(.secondary)
            Text("No chart data available")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct IndicatorToggleMenu: View {
    @Binding var config: IndicatorConfig

    var body: some View {
        Menu {
            Section("Moving Averages") {
                Toggle("SMA(20)", isOn: $config.showSMA20)
                Toggle("SMA(50)", isOn: $config.showSMA50)
                Toggle("SMA(200)", isOn: $config.showSMA200)
                Toggle("EMA(9)", isOn: $config.showEMA9)
                Toggle("EMA(21)", isOn: $config.showEMA21)
            }

            Section("Oscillators") {
                Toggle("RSI(14)", isOn: $config.showRSI)
                Toggle("MACD(12,26,9)", isOn: $config.showMACD)
                Toggle("Stochastic(14,3)", isOn: $config.showStochastic)
                Toggle("KDJ(9,3,3)", isOn: $config.showKDJ)
            }

            Section("Trend & Volatility") {
                Toggle("ADX(14)", isOn: $config.showADX)
                Toggle("SuperTrend(10,3)", isOn: $config.showSuperTrend)
                Toggle("Bollinger Bands", isOn: $config.showBollingerBands)
                Toggle("ATR(14)", isOn: $config.showATR)
            }

            Section("SuperTrend AI") {
                Toggle("Trend Zones", isOn: $config.showTrendZones)
                Toggle("Signal Markers", isOn: $config.showSignalMarkers)
                Toggle("Confidence Badges", isOn: $config.showConfidenceBadges)
            }

            Section("Display") {
                Toggle("Volume", isOn: $config.showVolume)
            }
        } label: {
            Label("Indicators", systemImage: "chart.line.uptrend.xyaxis")
                .font(.caption)
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(Color.accentColor.opacity(0.1))
                .foregroundStyle(.primary)
                .clipShape(RoundedRectangle(cornerRadius: 6))
        }
        .menuStyle(.borderlessButton)
        .frame(maxWidth: .infinity, alignment: .trailing)
    }
}

#Preview {
    ChartView()
        .environmentObject(AppViewModel())
        .frame(width: 800, height: 500)
}
