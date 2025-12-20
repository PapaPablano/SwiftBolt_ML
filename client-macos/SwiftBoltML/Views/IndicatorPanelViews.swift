import SwiftUI
import Charts

// MARK: - MACD Panel View

struct MACDPanelView: View {
    let bars: [OHLCBar]
    let macdLine: [IndicatorDataPoint]
    let signalLine: [IndicatorDataPoint]
    let histogram: [IndicatorDataPoint]
    let visibleRange: ClosedRange<Int>

    private func indicatorIndex(for date: Date) -> Int? {
        bars.firstIndex(where: { Calendar.current.isDate($0.ts, equalTo: date, toGranularity: .second) })
    }

    var body: some View {
        Chart {
            // MACD Histogram (bars)
            ForEach(histogram) { point in
                if let value = point.value, let index = indicatorIndex(for: point.date), visibleRange.contains(index) {
                    BarMark(
                        x: .value("Index", index),
                        y: .value("Histogram", value)
                    )
                    .foregroundStyle(value >= 0 ? Color.green.opacity(0.6) : Color.red.opacity(0.6))
                }
            }

            // MACD Line (blue)
            ForEach(macdLine) { point in
                if let value = point.value, let index = indicatorIndex(for: point.date), visibleRange.contains(index) {
                    LineMark(
                        x: .value("Index", index),
                        y: .value("MACD", value)
                    )
                    .foregroundStyle(.blue)
                    .lineStyle(StrokeStyle(lineWidth: 1.5))
                    .interpolationMethod(.catmullRom)
                }
            }

            // Signal Line (orange)
            ForEach(signalLine) { point in
                if let value = point.value, let index = indicatorIndex(for: point.date), visibleRange.contains(index) {
                    LineMark(
                        x: .value("Index", index),
                        y: .value("Signal", value)
                    )
                    .foregroundStyle(.orange)
                    .lineStyle(StrokeStyle(lineWidth: 1.5))
                    .interpolationMethod(.catmullRom)
                }
            }

            // Zero line
            RuleMark(y: .value("Zero", 0))
                .foregroundStyle(.gray.opacity(0.3))
                .lineStyle(StrokeStyle(lineWidth: 1, dash: [5, 3]))
        }
        .chartXScale(domain: visibleRange.lowerBound...visibleRange.upperBound)
        .chartXAxis(.hidden)
        .chartYAxis {
            AxisMarks(position: .trailing, values: .automatic(desiredCount: 3)) { _ in
                AxisGridLine()
                AxisValueLabel()
            }
        }
        .chartLegend(position: .top, alignment: .leading) {
            HStack(spacing: 12) {
                LegendItem(color: .blue, label: "MACD", value: macdLine.last?.value)
                LegendItem(color: .orange, label: "Signal", value: signalLine.last?.value)
                if let histVal = histogram.last?.value {
                    HStack(spacing: 4) {
                        Rectangle()
                            .fill(histVal >= 0 ? Color.green : Color.red)
                            .frame(width: 8, height: 8)
                        Text("Hist")
                            .font(.caption)
                        Text(String(format: "%.2f", histVal))
                            .font(.caption.monospacedDigit())
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .padding(.horizontal, 8)
        }
    }
}

// MARK: - Stochastic Panel View

struct StochasticPanelView: View {
    let bars: [OHLCBar]
    let kLine: [IndicatorDataPoint]
    let dLine: [IndicatorDataPoint]
    let visibleRange: ClosedRange<Int>

    private func indicatorIndex(for date: Date) -> Int? {
        bars.firstIndex(where: { Calendar.current.isDate($0.ts, equalTo: date, toGranularity: .second) })
    }

    var body: some View {
        Chart {
            // %K Line (blue)
            ForEach(kLine) { point in
                if let value = point.value, let index = indicatorIndex(for: point.date), visibleRange.contains(index) {
                    LineMark(
                        x: .value("Index", index),
                        y: .value("%K", value)
                    )
                    .foregroundStyle(.blue)
                    .lineStyle(StrokeStyle(lineWidth: 1.5))
                    .interpolationMethod(.catmullRom)
                }
            }

            // %D Line (orange)
            ForEach(dLine) { point in
                if let value = point.value, let index = indicatorIndex(for: point.date), visibleRange.contains(index) {
                    LineMark(
                        x: .value("Index", index),
                        y: .value("%D", value)
                    )
                    .foregroundStyle(.orange)
                    .lineStyle(StrokeStyle(lineWidth: 1.5))
                    .interpolationMethod(.catmullRom)
                }
            }

            // Overbought (80)
            RuleMark(y: .value("Overbought", 80))
                .foregroundStyle(.red.opacity(0.3))
                .lineStyle(StrokeStyle(lineWidth: 1, dash: [5, 3]))

            // Oversold (20)
            RuleMark(y: .value("Oversold", 20))
                .foregroundStyle(.green.opacity(0.3))
                .lineStyle(StrokeStyle(lineWidth: 1, dash: [5, 3]))
        }
        .chartXScale(domain: visibleRange.lowerBound...visibleRange.upperBound)
        .chartYScale(domain: 0...100)
        .chartXAxis(.hidden)
        .chartYAxis {
            AxisMarks(position: .trailing, values: [20, 50, 80]) { _ in
                AxisGridLine()
                AxisValueLabel()
            }
        }
        .chartLegend(position: .top, alignment: .leading) {
            HStack(spacing: 12) {
                LegendItem(color: .blue, label: "%K(14)", value: kLine.last?.value)
                LegendItem(color: .orange, label: "%D(3)", value: dLine.last?.value)
            }
            .padding(.horizontal, 8)
        }
    }
}

// MARK: - KDJ Panel View

struct KDJPanelView: View {
    let bars: [OHLCBar]
    let kLine: [IndicatorDataPoint]
    let dLine: [IndicatorDataPoint]
    let jLine: [IndicatorDataPoint]
    let visibleRange: ClosedRange<Int>

    private func indicatorIndex(for date: Date) -> Int? {
        bars.firstIndex(where: { Calendar.current.isDate($0.ts, equalTo: date, toGranularity: .second) })
    }

    var body: some View {
        Chart {
            // K Line (blue)
            ForEach(kLine) { point in
                if let value = point.value, let index = indicatorIndex(for: point.date), visibleRange.contains(index) {
                    LineMark(
                        x: .value("Index", index),
                        y: .value("K", value)
                    )
                    .foregroundStyle(.blue)
                    .lineStyle(StrokeStyle(lineWidth: 1.5))
                    .interpolationMethod(.catmullRom)
                }
            }

            // D Line (orange)
            ForEach(dLine) { point in
                if let value = point.value, let index = indicatorIndex(for: point.date), visibleRange.contains(index) {
                    LineMark(
                        x: .value("Index", index),
                        y: .value("D", value)
                    )
                    .foregroundStyle(.orange)
                    .lineStyle(StrokeStyle(lineWidth: 1.5))
                    .interpolationMethod(.catmullRom)
                }
            }

            // J Line (purple - most sensitive)
            ForEach(jLine) { point in
                if let value = point.value, let index = indicatorIndex(for: point.date), visibleRange.contains(index) {
                    LineMark(
                        x: .value("Index", index),
                        y: .value("J", value)
                    )
                    .foregroundStyle(.purple)
                    .lineStyle(StrokeStyle(lineWidth: 1.5))
                    .interpolationMethod(.catmullRom)
                }
            }

            // Overbought (80)
            RuleMark(y: .value("Overbought", 80))
                .foregroundStyle(.red.opacity(0.3))
                .lineStyle(StrokeStyle(lineWidth: 1, dash: [5, 3]))

            // Oversold (20)
            RuleMark(y: .value("Oversold", 20))
                .foregroundStyle(.green.opacity(0.3))
                .lineStyle(StrokeStyle(lineWidth: 1, dash: [5, 3]))
        }
        .chartXScale(domain: visibleRange.lowerBound...visibleRange.upperBound)
        .chartYScale(domain: -20...120)  // J can exceed 0-100
        .chartXAxis(.hidden)
        .chartYAxis {
            AxisMarks(position: .trailing, values: [0, 20, 50, 80, 100]) { _ in
                AxisGridLine()
                AxisValueLabel()
            }
        }
        .chartLegend(position: .top, alignment: .leading) {
            HStack(spacing: 12) {
                LegendItem(color: .blue, label: "K", value: kLine.last?.value)
                LegendItem(color: .orange, label: "D", value: dLine.last?.value)
                LegendItem(color: .purple, label: "J", value: jLine.last?.value)
            }
            .padding(.horizontal, 8)
        }
    }
}

// MARK: - ADX Panel View

struct ADXPanelView: View {
    let bars: [OHLCBar]
    let adxLine: [IndicatorDataPoint]
    let plusDI: [IndicatorDataPoint]
    let minusDI: [IndicatorDataPoint]
    let visibleRange: ClosedRange<Int>

    private func indicatorIndex(for date: Date) -> Int? {
        bars.firstIndex(where: { Calendar.current.isDate($0.ts, equalTo: date, toGranularity: .second) })
    }

    var body: some View {
        Chart {
            // ADX Line (yellow - trend strength)
            ForEach(adxLine) { point in
                if let value = point.value, let index = indicatorIndex(for: point.date), visibleRange.contains(index) {
                    LineMark(
                        x: .value("Index", index),
                        y: .value("ADX", value)
                    )
                    .foregroundStyle(.yellow)
                    .lineStyle(StrokeStyle(lineWidth: 2))
                    .interpolationMethod(.catmullRom)
                }
            }

            // +DI Line (green - bullish)
            ForEach(plusDI) { point in
                if let value = point.value, let index = indicatorIndex(for: point.date), visibleRange.contains(index) {
                    LineMark(
                        x: .value("Index", index),
                        y: .value("+DI", value)
                    )
                    .foregroundStyle(.green)
                    .lineStyle(StrokeStyle(lineWidth: 1.5))
                    .interpolationMethod(.catmullRom)
                }
            }

            // -DI Line (red - bearish)
            ForEach(minusDI) { point in
                if let value = point.value, let index = indicatorIndex(for: point.date), visibleRange.contains(index) {
                    LineMark(
                        x: .value("Index", index),
                        y: .value("-DI", value)
                    )
                    .foregroundStyle(.red)
                    .lineStyle(StrokeStyle(lineWidth: 1.5))
                    .interpolationMethod(.catmullRom)
                }
            }

            // Trend strength threshold (25)
            RuleMark(y: .value("Trend", 25))
                .foregroundStyle(.gray.opacity(0.3))
                .lineStyle(StrokeStyle(lineWidth: 1, dash: [5, 3]))
        }
        .chartXScale(domain: visibleRange.lowerBound...visibleRange.upperBound)
        .chartYScale(domain: 0...100)
        .chartXAxis(.hidden)
        .chartYAxis {
            AxisMarks(position: .trailing, values: [0, 25, 50, 75]) { _ in
                AxisGridLine()
                AxisValueLabel()
            }
        }
        .chartLegend(position: .top, alignment: .leading) {
            HStack(spacing: 12) {
                LegendItem(color: .yellow, label: "ADX", value: adxLine.last?.value)
                LegendItem(color: .green, label: "+DI", value: plusDI.last?.value)
                LegendItem(color: .red, label: "-DI", value: minusDI.last?.value)
            }
            .padding(.horizontal, 8)
        }
    }
}

// MARK: - ATR Panel View

struct ATRPanelView: View {
    let bars: [OHLCBar]
    let atrLine: [IndicatorDataPoint]
    let visibleRange: ClosedRange<Int>

    private func indicatorIndex(for date: Date) -> Int? {
        bars.firstIndex(where: { Calendar.current.isDate($0.ts, equalTo: date, toGranularity: .second) })
    }

    private var visibleATRRange: ClosedRange<Double> {
        let visibleValues = atrLine.compactMap { point -> Double? in
            guard let value = point.value,
                  let index = indicatorIndex(for: point.date),
                  visibleRange.contains(index) else { return nil }
            return value
        }
        let minVal = visibleValues.min() ?? 0
        let maxVal = visibleValues.max() ?? 1
        let padding = (maxVal - minVal) * 0.1
        return max(0, minVal - padding)...(maxVal + padding)
    }

    var body: some View {
        Chart {
            ForEach(atrLine) { point in
                if let value = point.value, let index = indicatorIndex(for: point.date), visibleRange.contains(index) {
                    LineMark(
                        x: .value("Index", index),
                        y: .value("ATR", value)
                    )
                    .foregroundStyle(.cyan)
                    .lineStyle(StrokeStyle(lineWidth: 1.5))
                    .interpolationMethod(.catmullRom)

                    AreaMark(
                        x: .value("Index", index),
                        y: .value("ATR", value)
                    )
                    .foregroundStyle(.cyan.opacity(0.1))
                    .interpolationMethod(.catmullRom)
                }
            }
        }
        .chartXScale(domain: visibleRange.lowerBound...visibleRange.upperBound)
        .chartYScale(domain: visibleATRRange)
        .chartXAxis(.hidden)
        .chartYAxis {
            AxisMarks(position: .trailing, values: .automatic(desiredCount: 3)) { value in
                AxisGridLine()
                AxisValueLabel {
                    if let atr = value.as(Double.self) {
                        Text(String(format: "%.2f", atr))
                            .font(.caption2)
                    }
                }
            }
        }
        .chartLegend(position: .top, alignment: .leading) {
            HStack(spacing: 8) {
                Label("ATR(14)", systemImage: "waveform")
                    .font(.caption)
                    .foregroundStyle(.cyan)
                Spacer()
                if let latestATR = atrLine.last?.value {
                    Text(String(format: "%.2f", latestATR))
                        .font(.caption.bold().monospacedDigit())
                        .foregroundStyle(.cyan)
                }
            }
            .padding(.horizontal, 8)
        }
    }
}
