import SwiftUI
import Charts
import CoreGraphics

// === LTTB DOWNSAMPLER (local, to avoid scope/import issues) ===
@inline(__always)
private func lttbDownsample(points: [CGPoint], threshold: Int) -> [CGPoint] {
    let n = points.count
    guard threshold > 2, n > threshold else { return points }
    var sampled: [CGPoint] = []
    sampled.reserveCapacity(threshold)

    let bucketSize = Double(n - 2) / Double(threshold - 2)

    // Always include first point
    sampled.append(points[0])

    var a = 0
    for i in 0..<(threshold - 2) {
        let start = Int(floor((Double(i) + 1.0) * bucketSize)) + 1
        let end   = Int(floor((Double(i) + 2.0) * bucketSize)) + 1
        let rangeEnd = min(end, n - 1)

        // Compute average of next bucket
        var avgX = 0.0, avgY = 0.0
        let rCount = max(1, rangeEnd - start)
        if rCount > 0 {
            for j in start..<rangeEnd {
                avgX += Double(points[j].x)
                avgY += Double(points[j].y)
            }
            avgX /= Double(rCount)
            avgY /= Double(rCount)
        } else {
            avgX = Double(points[a].x)
            avgY = Double(points[a].y)
        }

        // Pick point with largest triangle area relative to A and avg
        let rangeStart = Int(floor(Double(i) * bucketSize)) + 1
        let rangeStartClamped = min(max(rangeStart, 1), n - 2)
        let rangeLimit = min(rangeEnd, n - 1)

        var maxArea = -1.0
        var nextA = rangeStartClamped

        let ax = Double(points[a].x), ay = Double(points[a].y)

        if rangeStartClamped < rangeLimit {
            for j in rangeStartClamped..<rangeLimit {
                let bx = Double(points[j].x), by = Double(points[j].y)
                // triangle area via cross product
                let area = abs((ax - avgX) * (by - ay) - (ax - bx) * (avgY - ay))
                if area > maxArea {
                    maxArea = area
                    nextA = j
                }
            }
        }

        sampled.append(points[nextA])
        a = nextA
    }

    // Always include last point
    sampled.append(points[n - 1])
    return sampled
}

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
    
    return lttbDownsample(points: validPoints, threshold: threshold)
}

// MARK: - MACD Panel View

struct MACDPanelView: View {
    let bars: [OHLCBar]
    let macdLine: [IndicatorDataPoint]
    let signalLine: [IndicatorDataPoint]
    let histogram: [IndicatorDataPoint]
    let visibleRange: ClosedRange<Int>

    var body: some View {
        // Precompute all points outside Chart for deterministic rendering
        let histPoints = downsample(histogram, visibleRange: visibleRange)
        let macdPoints = downsample(macdLine, visibleRange: visibleRange)
        let signalPoints = downsample(signalLine, visibleRange: visibleRange)
        
        Chart {
            // MACD Histogram (bars) - rendered first so lines are on top
            ForEach(0..<histPoints.count, id: \.self) { i in
                let pt = histPoints[i]
                let index = Int(Double(pt.x).rounded())
                let value = Double(pt.y)
                
                BarMark(
                    x: .value("Index", index),
                    y: .value("Histogram", value)
                )
                .foregroundStyle(value >= 0 ? ChartColors.macdHistogramPos.opacity(0.6) : ChartColors.macdHistogramNeg.opacity(0.6))
            }

            // MACD Line (cyan - fast line)
            ForEach(0..<macdPoints.count, id: \.self) { i in
                let pt = macdPoints[i]
                LineMark(
                    x: .value("Index", Double(pt.x)),
                    y: .value("MACD", Double(pt.y)),
                    series: .value("Series", "MACD")
                )
                .foregroundStyle(ChartColors.macdLine)
                .lineStyle(StrokeStyle(lineWidth: 2.5))
                .interpolationMethod(.catmullRom)
            }

            // Signal Line (orange - slow line)
            ForEach(0..<signalPoints.count, id: \.self) { i in
                let pt = signalPoints[i]
                LineMark(
                    x: .value("Index", Double(pt.x)),
                    y: .value("Signal", Double(pt.y)),
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
        .id(histPoints.count ^ macdPoints.count ^ signalPoints.count ^ visibleRange.lowerBound ^ visibleRange.upperBound)
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
        .allowsHitTesting(false) // forward pan/zoom gestures to the main chart
    }
}

// MARK: - Stochastic Panel View

struct StochasticPanelView: View {
    let bars: [OHLCBar]
    let kLine: [IndicatorDataPoint]
    let dLine: [IndicatorDataPoint]
    let visibleRange: ClosedRange<Int>

    var body: some View {
        // Precompute all points outside Chart for deterministic rendering
        let kPoints = downsample(kLine, visibleRange: visibleRange)
        let dPoints = downsample(dLine, visibleRange: visibleRange)
        
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
            ForEach(0..<kPoints.count, id: \.self) { i in
                let pt = kPoints[i]
                LineMark(
                    x: .value("Index", Double(pt.x)),
                    y: .value("%K", Double(pt.y)),
                    series: .value("Series", "K")
                )
                .foregroundStyle(ChartColors.stochasticK)
                .lineStyle(StrokeStyle(lineWidth: 2.5))
                .interpolationMethod(.catmullRom)
            }

            // %D Line (orange - slower line)
            ForEach(0..<dPoints.count, id: \.self) { i in
                let pt = dPoints[i]
                LineMark(
                    x: .value("Index", Double(pt.x)),
                    y: .value("%D", Double(pt.y)),
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
        .id(kPoints.count ^ dPoints.count ^ visibleRange.lowerBound ^ visibleRange.upperBound)
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
        .allowsHitTesting(false) // forward pan/zoom gestures to the main chart
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
        // Precompute all points outside Chart for deterministic rendering
        let kPoints = downsample(kLine, visibleRange: visibleRange)
        let dPoints = downsample(dLine, visibleRange: visibleRange)
        let jPoints = downsample(jLine, visibleRange: visibleRange)
        
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
            ForEach(0..<kPoints.count, id: \.self) { i in
                let pt = kPoints[i]
                LineMark(
                    x: .value("Index", Double(pt.x)),
                    y: .value("K", Double(pt.y)),
                    series: .value("Series", "KDJ-K")
                )
                .foregroundStyle(ChartColors.kdjK)
                .lineStyle(StrokeStyle(lineWidth: 2.5))
                .interpolationMethod(.catmullRom)
            }

            // D Line (BRIGHT GREEN - clearly distinct)
            ForEach(0..<dPoints.count, id: \.self) { i in
                let pt = dPoints[i]
                LineMark(
                    x: .value("Index", Double(pt.x)),
                    y: .value("D", Double(pt.y)),
                    series: .value("Series", "KDJ-D")
                )
                .foregroundStyle(ChartColors.kdjD)
                .lineStyle(StrokeStyle(lineWidth: 2.5))
                .interpolationMethod(.catmullRom)
            }

            // J Line (BRIGHT BLUE - third distinct color)
            ForEach(0..<jPoints.count, id: \.self) { i in
                let pt = jPoints[i]
                LineMark(
                    x: .value("Index", Double(pt.x)),
                    y: .value("J", Double(pt.y)),
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
        .id(kPoints.count ^ dPoints.count ^ jPoints.count ^ visibleRange.lowerBound ^ visibleRange.upperBound)
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
        .allowsHitTesting(false) // forward pan/zoom gestures to the main chart
    }
}

// MARK: - ADX Panel View

struct ADXPanelView: View {
    let bars: [OHLCBar]
    let adxLine: [IndicatorDataPoint]
    let plusDI: [IndicatorDataPoint]
    let minusDI: [IndicatorDataPoint]
    let visibleRange: ClosedRange<Int>
    
    var body: some View {
        // Precompute all points outside Chart for deterministic rendering
        let adxPoints = downsample(adxLine, visibleRange: visibleRange)
        let plusPoints = downsample(plusDI, visibleRange: visibleRange)
        let minusPoints = downsample(minusDI, visibleRange: visibleRange)
        
        Chart {
            // ADX Histogram - Green for bullish, Red for bearish
            ForEach(0..<adxPoints.count, id: \.self) { i in
                let pt = adxPoints[i]
                let index = Int(Double(pt.x).rounded())
                let value = Double(pt.y)
                
                BarMark(
                    x: .value("Index", index),
                    y: .value("ADX", value)
                )
                .foregroundStyle(value >= 25 ? ChartColors.adx.opacity(0.6) : ChartColors.adx.opacity(0.3))
            }
            
            // +DI Line (green)
            ForEach(0..<plusPoints.count, id: \.self) { i in
                let pt = plusPoints[i]
                LineMark(
                    x: .value("Index", Double(pt.x)),
                    y: .value("+DI", Double(pt.y)),
                    series: .value("Series", "+DI")
                )
                .foregroundStyle(ChartColors.plusDI)
                .lineStyle(StrokeStyle(lineWidth: 2))
                .interpolationMethod(.catmullRom)
            }
            
            // -DI Line (red)
            ForEach(0..<minusPoints.count, id: \.self) { i in
                let pt = minusPoints[i]
                LineMark(
                    x: .value("Index", Double(pt.x)),
                    y: .value("-DI", Double(pt.y)),
                    series: .value("Series", "-DI")
                )
                .foregroundStyle(ChartColors.minusDI)
                .lineStyle(StrokeStyle(lineWidth: 2))
                .interpolationMethod(.catmullRom)
            }
            
            // Trend strength threshold (25)
            RuleMark(y: .value("Threshold", 25))
                .foregroundStyle(ChartColors.midline)
                .lineStyle(StrokeStyle(lineWidth: 1, dash: [5, 3]))
        }
        .id(adxPoints.count ^ plusPoints.count ^ minusPoints.count ^ visibleRange.lowerBound ^ visibleRange.upperBound)
        .chartXScale(domain: visibleRange.lowerBound...visibleRange.upperBound)
        .chartYScale(domain: 0...100)
        .chartXAxis(.hidden)
        .chartYAxis {
            AxisMarks(position: .trailing, values: [0, 25, 50, 75, 100]) { _ in
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
        .allowsHitTesting(false) // forward pan/zoom gestures to the main chart
    }
}

// MARK: - ATR Panel View

struct ATRPanelView: View {
    let bars: [OHLCBar]
    let atrLine: [IndicatorDataPoint]
    let visibleRange: ClosedRange<Int>
    
    /// Determine visible ATR range for chart
    private var visibleATRRange: ClosedRange<Double> {
        var minVal = Double.infinity
        var maxVal = -Double.infinity
        var found = false
        
        let start = max(0, visibleRange.lowerBound)
        let end = min(atrLine.count - 1, visibleRange.upperBound)
        
        if start <= end {
            for i in start...end {
                if let v = atrLine[i].value {
                    minVal = min(minVal, v)
                    maxVal = max(maxVal, v)
                    found = true
                }
            }
        }
        guard found else { return 0...1 }
        
        let span = max(1e-6, maxVal - minVal)            // never zero
        let pad  = max(span * 0.15, 1e-6)                // always some padding
        let lo   = max(0, minVal - pad)
        let hi   = max(lo + 1e-6, maxVal + pad)          // ensure hi > lo
        return lo...hi
    }

    var body: some View {
        // Precompute all points outside Chart for deterministic rendering
        let atrPoints = downsample(atrLine, visibleRange: visibleRange)
        
        Chart {
            // ATR area fill
            ForEach(0..<atrPoints.count, id: \.self) { i in
                let pt = atrPoints[i]
                AreaMark(
                    x: .value("Index", Double(pt.x)),
                    yStart: .value("Zero", 0),
                    yEnd: .value("ATR", Double(pt.y))
                )
                .foregroundStyle(
                    LinearGradient(
                        gradient: Gradient(colors: [ChartColors.atr.opacity(0.3), ChartColors.atr.opacity(0.05)]),
                        startPoint: .top,
                        endPoint: .bottom
                    )
                )
            }

            // ATR line
            ForEach(0..<atrPoints.count, id: \.self) { i in
                let pt = atrPoints[i]
                LineMark(
                    x: .value("Index", Double(pt.x)),
                    y: .value("ATR", Double(pt.y)),
                    series: .value("Series", "ATR")
                )
                .foregroundStyle(ChartColors.atr)
                .lineStyle(StrokeStyle(lineWidth: 2.5))
                .interpolationMethod(.catmullRom)
            }
        }
        .id(atrPoints.count ^ visibleRange.lowerBound ^ visibleRange.upperBound)
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
        .allowsHitTesting(false) // forward pan/zoom gestures to the main chart
    }
}
