import SwiftUI
import Charts
import CoreGraphics

// Helper to downsample data for better performance
private func downsample(_ data: [IndicatorDataPoint], visibleRange: ClosedRange<Int>) -> [CGPoint] {
    let pixelWidth = 600.0 // Approximate panel width
    let threshold = Int(pixelWidth * 2)
    
    let start = max(0, visibleRange.lowerBound)
    let end = min(data.count - 1, visibleRange.upperBound)
    guard start <= end else { return [] }
    
    // If count is small, return all points directly
    if (end - start + 1) <= threshold {
        var points: [CGPoint] = []
        points.reserveCapacity(end - start + 1)
        for i in start...end {
            if let val = data[i].value {
                points.append(CGPoint(x: Double(i), y: val))
            }
        }
        return points
    }
    
    // Collect points for downsampling
    var validPoints: [CGPoint] = []
    validPoints.reserveCapacity(end - start + 1)
    for i in start...end {
        if let val = data[i].value {
            validPoints.append(CGPoint(x: Double(i), y: val))
        }
    }
    
    return Downsampler.lttb(points: validPoints, threshold: threshold)
}

// MARK: - MACD Panel View

struct MACDPanelView: View {
    let bars: [OHLCBar]
    let macdLine: [IndicatorDataPoint]
    let signalLine: [IndicatorDataPoint]
    let histogram: [IndicatorDataPoint]
    let visibleRange: ClosedRange<Int>

    var body: some View {
        Chart {
            // MACD Histogram (bars) - rendered first so lines are on top
            let histPoints = downsample(histogram, visibleRange: visibleRange)
            ForEach(histPoints.indices, id: \.self) { i in
                let pt = histPoints[i]
                let index = Int(pt.x)
                let value = pt.y
                
                BarMark(
                    x: .value("Index", index),
                    y: .value("Histogram", value)
                )
                .foregroundStyle(value >= 0 ? ChartColors.macdHistogramPos.opacity(0.6) : ChartColors.macdHistogramNeg.opacity(0.6))
            }

            // MACD Line (cyan - fast line)
            let macdPoints = downsample(macdLine, visibleRange: visibleRange)
            ForEach(macdPoints.indices, id: \.self) { i in
                let pt = macdPoints[i]
                LineMark(
                    x: .value("Index", pt.x),
                    y: .value("MACD", pt.y),
                    series: .value("Series", "MACD")
                )
                .foregroundStyle(ChartColors.macdLine)
                .lineStyle(StrokeStyle(lineWidth: 2.5))
                .interpolationMethod(.catmullRom)
            }

            // Signal Line (orange - slow line)
            let signalPoints = downsample(signalLine, visibleRange: visibleRange)
            ForEach(signalPoints.indices, id: \.self) { i in
                let pt = signalPoints[i]
                LineMark(
                    x: .value("Index", pt.x),
                    y: .value("Signal", pt.y),
                    series: .value("Series", "Signal")
                )
                .foregroundStyle(ChartColors.macdSignal)
                .lineStyle(StrokeStyle(lineWidth: 2.5))
                .interpolationMethod(.catmullRom)
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
            let kPoints = downsample(kLine, visibleRange: visibleRange)
            ForEach(kPoints.indices, id: \.self) { i in
                let pt = kPoints[i]
                LineMark(
                    x: .value("Index", pt.x),
                    y: .value("%K", pt.y),
                    series: .value("Series", "K")
                )
                .foregroundStyle(ChartColors.stochasticK)
                .lineStyle(StrokeStyle(lineWidth: 2.5))
                .interpolationMethod(.catmullRom)
            }

            // %D Line (orange - slower line)
            let dPoints = downsample(dLine, visibleRange: visibleRange)
            ForEach(dPoints.indices, id: \.self) { i in
                let pt = dPoints[i]
                LineMark(
                    x: .value("Index", pt.x),
                    y: .value("%D", pt.y),
                    series: .value("Series", "D")
                )
                .foregroundStyle(ChartColors.stochasticD)
                .lineStyle(StrokeStyle(lineWidth: 2.5))
                .interpolationMethod(.catmullRom)
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
            let kPoints = downsample(kLine, visibleRange: visibleRange)
            ForEach(kPoints.indices, id: \.self) { i in
                let pt = kPoints[i]
                LineMark(
                    x: .value("Index", pt.x),
                    y: .value("K", pt.y),
                    series: .value("Series", "KDJ-K")
                )
                .foregroundStyle(ChartColors.kdjK)
                .lineStyle(StrokeStyle(lineWidth: 2.5))
                .interpolationMethod(.catmullRom)
            }

            // D Line (BRIGHT GREEN - clearly distinct)
            let dPoints = downsample(dLine, visibleRange: visibleRange)
            ForEach(dPoints.indices, id: \.self) { i in
                let pt = dPoints[i]
                LineMark(
                    x: .value("Index", pt.x),
                    y: .value("D", pt.y),
                    series: .value("Series", "KDJ-D")
                )
                .foregroundStyle(ChartColors.kdjD)
                .lineStyle(StrokeStyle(lineWidth: 2.5))
                .interpolationMethod(.catmullRom)
            }

            // J Line (BRIGHT BLUE - third distinct color)
            let jPoints = downsample(jLine, visibleRange: visibleRange)
            ForEach(jPoints.indices, id: \.self) { i in
                let pt = jPoints[i]
                LineMark(
                    x: .value("Index", pt.x),
                    y: .value("J", pt.y),
                    series: .value("Series", "KDJ-J")
                )
                .foregroundStyle(ChartColors.kdjJ)
                .lineStyle(StrokeStyle(lineWidth: 2.5))
                .interpolationMethod(.catmullRom)
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
/// ADX indicator panel with histogram display
/// - Green histogram bars when +DI > -DI (bullish trend)
/// - Red histogram bars when -DI > +DI (bearish trend)
/// - Color intensity based on ADX value (trend strength)
/// ADX interpretation:
///   0-20: No trend / ranging market
///   20-30: Trend beginning
///   30-50: Strong trend
///   50+: Very strong trend (possible exhaustion)

struct ADXPanelView: View {
    let bars: [OHLCBar]
    let adxLine: [IndicatorDataPoint]
    let plusDI: [IndicatorDataPoint]
    let minusDI: [IndicatorDataPoint]
    let visibleRange: ClosedRange<Int>
    
    /// Threshold for trend confirmation (default 20)
    var limit: Double = 20

    /// Determine if bullish (+DI > -DI) at given index
    private func isBullish(at index: Int) -> Bool {
        guard index < plusDI.count, index < minusDI.count,
              let plusVal = plusDI[index].value,
              let minusVal = minusDI[index].value else {
            return true // Default to bullish if data missing
        }
        return plusVal > minusVal
    }
    
    /// Get ADX color based on value and direction
    private func adxColor(value: Double, bullish: Bool) -> Color {
        let baseColor = bullish ? ChartColors.plusDI : ChartColors.minusDI
        // Intensity based on ADX strength
        if value >= limit {
            return baseColor
        } else {
            return baseColor.opacity(0.5)
        }
    }
    
    /// Current trend status text
    private var trendStatus: String {
        guard let lastADX = adxLine.last?.value else { return "N/A" }
        let bullish = isBullishAtEnd
        let direction = bullish ? "Bullish" : "Bearish"
        
        if lastADX < 20 {
            return "Ranging"
        } else if lastADX < 30 {
            return "\(direction) Starting"
        } else if lastADX < 50 {
            return "Strong \(direction)"
        } else {
            return "Very Strong \(direction)"
        }
    }
    
    private var isBullishAtEnd: Bool {
        guard let lastPlus = plusDI.last?.value,
              let lastMinus = minusDI.last?.value else { return true }
        return lastPlus > lastMinus
    }

    var body: some View {
        Chart {
            // Ranging zone shading (0-20) - gray/neutral
            RectangleMark(
                xStart: .value("Start", visibleRange.lowerBound),
                xEnd: .value("End", visibleRange.upperBound),
                yStart: .value("Low", 0),
                yEnd: .value("High", 20)
            )
            .foregroundStyle(Color.gray.opacity(0.08))
            
            // Strong trend zone shading (30-50)
            RectangleMark(
                xStart: .value("Start", visibleRange.lowerBound),
                xEnd: .value("End", visibleRange.upperBound),
                yStart: .value("Low", 30),
                yEnd: .value("High", 50)
            )
            .foregroundStyle(Color.yellow.opacity(0.06))
            
            // Very strong trend zone (50+)
            RectangleMark(
                xStart: .value("Start", visibleRange.lowerBound),
                xEnd: .value("End", visibleRange.upperBound),
                yStart: .value("Low", 50),
                yEnd: .value("High", 100)
            )
            .foregroundStyle(Color.orange.opacity(0.06))

            // ADX Histogram - Green for bullish, Red for bearish
            let adxPoints = downsample(adxLine, visibleRange: visibleRange)
            ForEach(adxPoints.indices, id: \.self) { i in
                let pt = adxPoints[i]
                let index = Int(pt.x)
                let value = pt.y
                let bullish = isBullish(at: index)
                
                BarMark(
                    x: .value("Index", index),
                    y: .value("ADX", value)
                )
                .foregroundStyle(adxColor(value: value, bullish: bullish))
            }

            // Threshold lines
            // Limit line (20 - trend begins)
            RuleMark(y: .value("Limit", 20))
                .foregroundStyle(ChartColors.midline)
                .lineStyle(StrokeStyle(lineWidth: 1, dash: [5, 3]))
            
            // Strong trend line (30)
            RuleMark(y: .value("Strong", 30))
                .foregroundStyle(Color.yellow.opacity(0.5))
                .lineStyle(StrokeStyle(lineWidth: 1, dash: [3, 2]))
            
            // Very strong / exhaustion line (50)
            RuleMark(y: .value("VeryStrong", 50))
                .foregroundStyle(Color.orange.opacity(0.5))
                .lineStyle(StrokeStyle(lineWidth: 1, dash: [3, 2]))
            
            // Zero line
            RuleMark(y: .value("Zero", 0))
                .foregroundStyle(ChartColors.midline.opacity(0.3))
        }
        .chartXScale(domain: visibleRange.lowerBound...visibleRange.upperBound)
        .chartYScale(domain: 0...100)
        .chartXAxis(.hidden)
        .chartYAxis {
            AxisMarks(position: .trailing, values: [0, 20, 30, 50]) { _ in
                AxisGridLine()
                AxisValueLabel()
            }
        }
        .chartLegend(position: .top, alignment: .leading) {
            HStack(spacing: 12) {
                // ADX value with trend color
                if let lastADX = adxLine.last?.value {
                    HStack(spacing: 4) {
                        Rectangle()
                            .fill(isBullishAtEnd ? ChartColors.plusDI : ChartColors.minusDI)
                            .frame(width: 10, height: 10)
                            .cornerRadius(2)
                        Text("ADX")
                            .font(.caption)
                        Text(String(format: "%.1f", lastADX))
                            .font(.caption.monospacedDigit())
                            .foregroundStyle(.secondary)
                    }
                }
                
                // Trend status badge
                Text(trendStatus)
                    .font(.caption.bold())
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(
                        RoundedRectangle(cornerRadius: 4)
                            .fill(isBullishAtEnd ? ChartColors.plusDI.opacity(0.2) : ChartColors.minusDI.opacity(0.2))
                    )
                    .foregroundStyle(isBullishAtEnd ? ChartColors.plusDI : ChartColors.minusDI)
                
                Spacer()
                
                // +DI / -DI values
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

    private var visibleATRRange: ClosedRange<Double> {
        // Efficiently find min/max in visible range using indices
        var minVal: Double = Double.infinity
        var maxVal: Double = -Double.infinity
        var found = false
        
        let start = max(0, visibleRange.lowerBound)
        let end = min(atrLine.count - 1, visibleRange.upperBound)
        
        if start <= end {
            for i in start...end {
                if let val = atrLine[i].value {
                    minVal = min(minVal, val)
                    maxVal = max(maxVal, val)
                    found = true
                }
            }
        }
        
        if !found { return 0...1 }
        
        let padding = (maxVal - minVal) * 0.15
        return max(0, minVal - padding)...(maxVal + padding)
    }

    var body: some View {
        Chart {
            // ATR area fill
            let atrPoints = downsample(atrLine, visibleRange: visibleRange)
            ForEach(atrPoints.indices, id: \.self) { i in
                let pt = atrPoints[i]
                AreaMark(
                    x: .value("Index", pt.x),
                    y: .value("ATR", pt.y)
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

            // ATR line
            ForEach(atrPoints.indices, id: \.self) { i in
                let pt = atrPoints[i]
                LineMark(
                    x: .value("Index", pt.x),
                    y: .value("ATR", pt.y)
                )
                .foregroundStyle(ChartColors.atr)
                .lineStyle(StrokeStyle(lineWidth: 2.5))
                .interpolationMethod(.catmullRom)
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
