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
            // MACD Histogram (bars) - rendered first so lines are on top
            ForEach(histogram) { point in
                if let value = point.value, let index = indicatorIndex(for: point.date), visibleRange.contains(index) {
                    BarMark(
                        x: .value("Index", index),
                        y: .value("Histogram", value)
                    )
                    .foregroundStyle(value >= 0 ? ChartColors.macdHistogramPos.opacity(0.6) : ChartColors.macdHistogramNeg.opacity(0.6))
                }
            }

            // MACD Line (cyan - fast line)
            ForEach(macdLine) { point in
                if let value = point.value, let index = indicatorIndex(for: point.date), visibleRange.contains(index) {
                    LineMark(
                        x: .value("Index", index),
                        y: .value("MACD", value),
                        series: .value("Series", "MACD")
                    )
                    .foregroundStyle(ChartColors.macdLine)
                    .lineStyle(StrokeStyle(lineWidth: 2.5))
                    .interpolationMethod(.catmullRom)
                }
            }

            // Signal Line (orange - slow line)
            ForEach(signalLine) { point in
                if let value = point.value, let index = indicatorIndex(for: point.date), visibleRange.contains(index) {
                    LineMark(
                        x: .value("Index", index),
                        y: .value("Signal", value),
                        series: .value("Series", "Signal")
                    )
                    .foregroundStyle(ChartColors.macdSignal)
                    .lineStyle(StrokeStyle(lineWidth: 2.5))
                    .interpolationMethod(.catmullRom)
                }
            }

            // Zero line
            RuleMark(y: .value("Zero", 0))
                .foregroundStyle(ChartColors.midline)
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
                LegendItem(color: ChartColors.macdLine, label: "MACD", value: macdLine.last?.value)
                LegendItem(color: ChartColors.macdSignal, label: "Signal", value: signalLine.last?.value)
                if let histVal = histogram.last?.value {
                    HStack(spacing: 4) {
                        Rectangle()
                            .fill(histVal >= 0 ? ChartColors.macdHistogramPos : ChartColors.macdHistogramNeg)
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
            // Overbought zone shading (80-100)
            RectangleMark(
                xStart: .value("Start", visibleRange.lowerBound),
                xEnd: .value("End", visibleRange.upperBound),
                yStart: .value("Low", 80),
                yEnd: .value("High", 100)
            )
            .foregroundStyle(Color.red.opacity(0.08))

            // Oversold zone shading (0-20)
            RectangleMark(
                xStart: .value("Start", visibleRange.lowerBound),
                xEnd: .value("End", visibleRange.upperBound),
                yStart: .value("Low", 0),
                yEnd: .value("High", 20)
            )
            .foregroundStyle(Color.green.opacity(0.08))

            // %K Line (cyan - faster line)
            ForEach(kLine) { point in
                if let value = point.value, let index = indicatorIndex(for: point.date), visibleRange.contains(index) {
                    LineMark(
                        x: .value("Index", index),
                        y: .value("%K", value),
                        series: .value("Series", "K")
                    )
                    .foregroundStyle(ChartColors.stochasticK)
                    .lineStyle(StrokeStyle(lineWidth: 2.5))
                    .interpolationMethod(.catmullRom)
                }
            }

            // %D Line (orange - slower line)
            ForEach(dLine) { point in
                if let value = point.value, let index = indicatorIndex(for: point.date), visibleRange.contains(index) {
                    LineMark(
                        x: .value("Index", index),
                        y: .value("%D", value),
                        series: .value("Series", "D")
                    )
                    .foregroundStyle(ChartColors.stochasticD)
                    .lineStyle(StrokeStyle(lineWidth: 2.5))
                    .interpolationMethod(.catmullRom)
                }
            }

            // Overbought (80)
            RuleMark(y: .value("Overbought", 80))
                .foregroundStyle(ChartColors.overbought)
                .lineStyle(StrokeStyle(lineWidth: 1, dash: [5, 3]))

            // Oversold (20)
            RuleMark(y: .value("Oversold", 20))
                .foregroundStyle(ChartColors.oversold)
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
                LegendItem(color: ChartColors.stochasticK, label: "%K(14)", value: kLine.last?.value)
                LegendItem(color: ChartColors.stochasticD, label: "%D(3)", value: dLine.last?.value)
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
            // Overbought zone shading (80-120)
            RectangleMark(
                xStart: .value("Start", visibleRange.lowerBound),
                xEnd: .value("End", visibleRange.upperBound),
                yStart: .value("Low", 80),
                yEnd: .value("High", 120)
            )
            .foregroundStyle(Color.red.opacity(0.08))

            // Oversold zone shading (-20 to 20)
            RectangleMark(
                xStart: .value("Start", visibleRange.lowerBound),
                xEnd: .value("End", visibleRange.upperBound),
                yStart: .value("Low", -20),
                yEnd: .value("High", 20)
            )
            .foregroundStyle(Color.green.opacity(0.08))

            // K Line (BRIGHT RED - most visible)
            ForEach(kLine) { point in
                if let value = point.value, let index = indicatorIndex(for: point.date), visibleRange.contains(index) {
                    LineMark(
                        x: .value("Index", index),
                        y: .value("K", value),
                        series: .value("Series", "KDJ-K")
                    )
                    .foregroundStyle(ChartColors.kdjK)
                    .lineStyle(StrokeStyle(lineWidth: 2.5))
                    .interpolationMethod(.catmullRom)
                }
            }

            // D Line (BRIGHT GREEN - clearly distinct)
            ForEach(dLine) { point in
                if let value = point.value, let index = indicatorIndex(for: point.date), visibleRange.contains(index) {
                    LineMark(
                        x: .value("Index", index),
                        y: .value("D", value),
                        series: .value("Series", "KDJ-D")
                    )
                    .foregroundStyle(ChartColors.kdjD)
                    .lineStyle(StrokeStyle(lineWidth: 2.5))
                    .interpolationMethod(.catmullRom)
                }
            }

            // J Line (BRIGHT BLUE - third distinct color)
            ForEach(jLine) { point in
                if let value = point.value, let index = indicatorIndex(for: point.date), visibleRange.contains(index) {
                    LineMark(
                        x: .value("Index", index),
                        y: .value("J", value),
                        series: .value("Series", "KDJ-J")
                    )
                    .foregroundStyle(ChartColors.kdjJ)
                    .lineStyle(StrokeStyle(lineWidth: 2.5))
                    .interpolationMethod(.catmullRom)
                }
            }

            // Overbought (80)
            RuleMark(y: .value("Overbought", 80))
                .foregroundStyle(ChartColors.overbought)
                .lineStyle(StrokeStyle(lineWidth: 1, dash: [5, 3]))

            // Oversold (20)
            RuleMark(y: .value("Oversold", 20))
                .foregroundStyle(ChartColors.oversold)
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
                LegendItem(color: ChartColors.kdjK, label: "K", value: kLine.last?.value)
                LegendItem(color: ChartColors.kdjD, label: "D", value: dLine.last?.value)
                LegendItem(color: ChartColors.kdjJ, label: "J", value: jLine.last?.value)
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
            // Strong trend zone shading (above 25)
            RectangleMark(
                xStart: .value("Start", visibleRange.lowerBound),
                xEnd: .value("End", visibleRange.upperBound),
                yStart: .value("Low", 25),
                yEnd: .value("High", 100)
            )
            .foregroundStyle(Color.yellow.opacity(0.05))

            // ADX Line (gold - trend strength)
            ForEach(adxLine) { point in
                if let value = point.value, let index = indicatorIndex(for: point.date), visibleRange.contains(index) {
                    LineMark(
                        x: .value("Index", index),
                        y: .value("ADX", value)
                    )
                    .foregroundStyle(ChartColors.adx)
                    .lineStyle(StrokeStyle(lineWidth: 3.0))
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
                    .foregroundStyle(ChartColors.plusDI)
                    .lineStyle(StrokeStyle(lineWidth: 2.0))
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
                    .foregroundStyle(ChartColors.minusDI)
                    .lineStyle(StrokeStyle(lineWidth: 2.0))
                    .interpolationMethod(.catmullRom)
                }
            }

            // Trend strength threshold (25)
            RuleMark(y: .value("Trend", 25))
                .foregroundStyle(ChartColors.midline)
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
                LegendItem(color: ChartColors.adx, label: "ADX", value: adxLine.last?.value)
                LegendItem(color: ChartColors.plusDI, label: "+DI", value: plusDI.last?.value)
                LegendItem(color: ChartColors.minusDI, label: "-DI", value: minusDI.last?.value)
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
        let padding = (maxVal - minVal) * 0.15
        return max(0, minVal - padding)...(maxVal + padding)
    }

    var body: some View {
        Chart {
            // ATR area fill
            ForEach(atrLine) { point in
                if let value = point.value, let index = indicatorIndex(for: point.date), visibleRange.contains(index) {
                    AreaMark(
                        x: .value("Index", index),
                        y: .value("ATR", value)
                    )
                    .foregroundStyle(
                        LinearGradient(
                            colors: [ChartColors.atr.opacity(0.2), ChartColors.atr.opacity(0.02)],
                            startPoint: .top,
                            endPoint: .bottom
                        )
                    )
                    .interpolationMethod(.catmullRom)
                }
            }

            // ATR line
            ForEach(atrLine) { point in
                if let value = point.value, let index = indicatorIndex(for: point.date), visibleRange.contains(index) {
                    LineMark(
                        x: .value("Index", index),
                        y: .value("ATR", value)
                    )
                    .foregroundStyle(ChartColors.atr)
                    .lineStyle(StrokeStyle(lineWidth: 2.5))
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
                Circle()
                    .fill(ChartColors.atr)
                    .frame(width: 8, height: 8)
                Text("ATR(14)")
                    .font(.caption.bold())
                    .foregroundStyle(.primary)
                Spacer()
                if let latestATR = atrLine.last?.value {
                    Text(String(format: "%.2f", latestATR))
                        .font(.caption.bold().monospacedDigit())
                        .foregroundStyle(ChartColors.atr)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(ChartColors.atr.opacity(0.15))
                        .clipShape(Capsule())
                }
            }
            .padding(.horizontal, 8)
        }
    }
}
