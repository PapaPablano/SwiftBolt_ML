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
    }

    private func formatPrice(_ price: Double) -> String {
        String(format: "$%.2f", price)
    }
}

struct CandlestickChartView: View {
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
            RectangleMark(
                x: .value("Date", bar.ts),
                yStart: .value("Open", bar.open),
                yEnd: .value("Close", bar.close),
                width: 6
            )
            .foregroundStyle(bar.close >= bar.open ? .green : .red)

            RuleMark(
                x: .value("Date", bar.ts),
                yStart: .value("Low", bar.low),
                yEnd: .value("High", bar.high)
            )
            .foregroundStyle(bar.close >= bar.open ? .green : .red)
            .lineStyle(StrokeStyle(lineWidth: 1))
        }
        .chartYScale(domain: priceRange)
        .chartXAxis {
            AxisMarks(values: .automatic(desiredCount: 6)) { _ in
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
    }

    private func formatPrice(_ price: Double) -> String {
        String(format: "$%.2f", price)
    }
}

// Preview removed - OHLCBar requires Codable initialization
