import SwiftUI
import Charts

struct PriceChartView: View {
    let bars: [OHLCBar]

    private var minPrice: Double {
        bars.map(\.low).min() ?? 0
    }

    private var maxPrice: Double {
        bars.map(\.high).max() ?? 0
    }

    private var priceRange: ClosedRange<Double> {
        let padding = (maxPrice - minPrice) * 0.05
        return (minPrice - padding)...(maxPrice + padding)
    }

    var body: some View {
        Chart(bars) { bar in
            LineMark(
                x: .value("Date", bar.ts),
                y: .value("Price", bar.close)
            )
            .foregroundStyle(.blue)
            .interpolationMethod(.catmullRom)

            AreaMark(
                x: .value("Date", bar.ts),
                y: .value("Price", bar.close)
            )
            .foregroundStyle(
                LinearGradient(
                    colors: [.blue.opacity(0.3), .blue.opacity(0.05)],
                    startPoint: .top,
                    endPoint: .bottom
                )
            )
            .interpolationMethod(.catmullRom)
        }
        .chartYScale(domain: priceRange)
        .chartXAxis {
            AxisMarks(values: .automatic(desiredCount: 6)) { value in
                AxisGridLine()
                AxisTick()
                AxisValueLabel(format: .dateTime.month().day())
            }
        }
        .chartYAxis {
            AxisMarks(position: .trailing, values: .automatic(desiredCount: 5)) { value in
                AxisGridLine()
                AxisTick()
                AxisValueLabel {
                    if let price = value.as(Double.self) {
                        Text(formatPrice(price))
                            .font(.caption.monospacedDigit())
                    }
                }
            }
        }
        .id("price-chart-\(bars.count)-\(bars.first?.ts.timeIntervalSince1970 ?? 0)")
    }

    private func formatPrice(_ price: Double) -> String {
        String(format: "$%.2f", price)
    }
}

struct CandlestickChartView: View {
    let bars: [OHLCBar]
    @State private var selectedBar: OHLCBar?

    private var minPrice: Double {
        bars.map(\.low).min() ?? 0
    }

    private var maxPrice: Double {
        bars.map(\.high).max() ?? 0
    }

    private var priceRange: ClosedRange<Double> {
        let padding = (maxPrice - minPrice) * 0.05
        return (minPrice - padding)...(maxPrice + padding)
    }

    var body: some View {
        Chart(bars) { bar in
            // Candlestick body (rectangle between open and close)
            RectangleMark(
                x: .value("Date", bar.ts),
                yStart: .value("Open", min(bar.open, bar.close)),
                yEnd: .value("Close", max(bar.open, bar.close)),
                width: .ratio(0.6)
            )
            .foregroundStyle(bar.close >= bar.open ? Color.green : Color.red)
            .opacity(bar.ts == selectedBar?.ts ? 1.0 : 0.8)

            // Candlestick wick (line from low to high)
            RuleMark(
                x: .value("Date", bar.ts),
                yStart: .value("Low", bar.low),
                yEnd: .value("High", bar.high)
            )
            .foregroundStyle(bar.close >= bar.open ? Color.green.opacity(0.8) : Color.red.opacity(0.8))
            .lineStyle(StrokeStyle(lineWidth: 1.5))

            // Selection indicator
            if bar.ts == selectedBar?.ts {
                RuleMark(x: .value("Date", bar.ts))
                    .foregroundStyle(.blue.opacity(0.3))
                    .lineStyle(StrokeStyle(lineWidth: 1, dash: [5, 3]))
            }
        }
        .chartYScale(domain: priceRange)
        .chartXAxis {
            AxisMarks(values: .stride(by: .day, count: bars.count / 6)) { value in
                AxisGridLine()
                AxisTick()
                AxisValueLabel(format: .dateTime.month().day())
            }
        }
        .chartYAxis {
            AxisMarks(position: .trailing, values: .automatic(desiredCount: 8)) { value in
                AxisGridLine()
                AxisTick()
                AxisValueLabel {
                    if let price = value.as(Double.self) {
                        Text(formatPrice(price))
                            .font(.caption.monospacedDigit())
                    }
                }
            }
        }
        .chartOverlay { proxy in
            GeometryReader { geometry in
                Rectangle()
                    .fill(.clear)
                    .contentShape(Rectangle())
                    .onContinuousHover { phase in
                        switch phase {
                        case .active(let location):
                            updateSelection(at: location, proxy: proxy, geometry: geometry)
                        case .ended:
                            selectedBar = nil
                        }
                    }
            }
        }
        .overlay(alignment: .topLeading) {
            if let bar = selectedBar {
                CandlestickTooltip(bar: bar)
                    .padding(8)
            }
        }
        .id("candlestick-chart-\(bars.count)-\(bars.first?.ts.timeIntervalSince1970 ?? 0)")
    }

    private func updateSelection(at location: CGPoint, proxy: ChartProxy, geometry: GeometryProxy) {
        guard let plotFrame = proxy.plotFrame else { return }
        let xPosition = location.x - geometry[plotFrame].origin.x
        guard let date: Date = proxy.value(atX: xPosition) else { return }

        // Find the closest bar to the selected date
        selectedBar = bars.min(by: { abs($0.ts.timeIntervalSince(date)) < abs($1.ts.timeIntervalSince(date)) })
    }

    private func formatPrice(_ price: Double) -> String {
        String(format: "$%.2f", price)
    }
}

struct CandlestickTooltip: View {
    let bar: OHLCBar

    private var isGreen: Bool {
        bar.close >= bar.open
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(bar.ts, format: .dateTime.month().day().hour().minute())
                .font(.caption.bold())
                .foregroundStyle(.secondary)

            Divider()

            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    TooltipRow(label: "O", value: bar.open)
                    TooltipRow(label: "H", value: bar.high)
                    TooltipRow(label: "L", value: bar.low)
                    TooltipRow(label: "C", value: bar.close)
                    TooltipRow(label: "Vol", value: bar.volume, isVolume: true)
                }

                Spacer()

                // Price change indicator
                VStack(alignment: .trailing, spacing: 2) {
                    Image(systemName: isGreen ? "arrow.up.right" : "arrow.down.right")
                        .font(.caption)
                    Text(formatChange())
                        .font(.caption.bold())
                }
                .foregroundStyle(isGreen ? .green : .red)
            }
        }
        .padding(8)
        .background(.thinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .shadow(radius: 2)
    }

    private func formatChange() -> String {
        let change = bar.close - bar.open
        let changePercent = (change / bar.open) * 100
        return String(format: "%+.2f\n(%.2f%%)", change, changePercent)
    }
}

struct TooltipRow: View {
    let label: String
    let value: Double
    var isVolume: Bool = false

    var body: some View {
        HStack(spacing: 4) {
            Text(label + ":")
                .foregroundStyle(.secondary)
            Text(isVolume ? formatVolume(value) : formatPrice(value))
                .bold()
        }
        .font(.caption.monospacedDigit())
    }

    private func formatPrice(_ price: Double) -> String {
        String(format: "$%.2f", price)
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

// Preview removed - OHLCBar requires Codable initialization
