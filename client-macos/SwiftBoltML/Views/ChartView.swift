import SwiftUI

struct ChartView: View {
    @EnvironmentObject var appViewModel: AppViewModel

    private var chartViewModel: ChartViewModel {
        appViewModel.chartViewModel
    }

    var body: some View {
        VStack(spacing: 0) {
            ChartHeader(
                symbol: appViewModel.selectedSymbol,
                lastBar: chartViewModel.bars.last
            )

            TimeframePicker(
                selectedTimeframe: chartViewModel.timeframe,
                onSelect: { timeframe in
                    Task {
                        await chartViewModel.setTimeframe(timeframe)
                    }
                }
            )
            .padding(.horizontal)
            .padding(.top, 8)

            if chartViewModel.isLoading {
                LoadingChartView()
            } else if let error = chartViewModel.errorMessage {
                ChartErrorView(message: error) {
                    Task {
                        await chartViewModel.loadChart()
                    }
                }
            } else if chartViewModel.bars.isEmpty {
                EmptyChartView()
            } else {
                PriceChartView(bars: chartViewModel.bars)
                    .padding()

                if let latestBar = chartViewModel.bars.last {
                    OHLCBarView(bar: latestBar)
                        .padding(.horizontal)
                        .padding(.bottom)
                }
            }
        }
        .background(Color(nsColor: .controlBackgroundColor))
    }
}

struct ChartHeader: View {
    let symbol: Symbol?
    let lastBar: OHLCBar?

    var body: some View {
        HStack {
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

#Preview {
    ChartView()
        .environmentObject(AppViewModel())
        .frame(width: 800, height: 500)
}
