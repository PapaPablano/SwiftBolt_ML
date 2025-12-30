import SwiftUI

// MARK: - Support & Resistance Overlay View

/// Unified overlay view for all three S&R indicators:
/// - BigBeluga Pivot Levels (multi-timeframe)
/// - Polynomial Regression S&R
/// - Logistic Regression S&R (ML-based)
struct SupportResistanceOverlayView: View {
    @ObservedObject var pivotIndicator: PivotLevelsIndicator
    @ObservedObject var polyIndicator: PolynomialRegressionIndicator
    @ObservedObject var logisticIndicator: LogisticRegressionIndicator

    let chartWidth: CGFloat
    let chartHeight: CGFloat
    let priceMin: Double
    let priceMax: Double
    let visibleRange: ClosedRange<Int>
    let barCount: Int

    /// Unique identifier combining all indicator states to force Canvas redraw
    private var canvasChangeId: String {
        let polyRes = polyIndicator.currentResistance ?? 0
        let polySup = polyIndicator.currentSupport ?? 0
        let pivotCount = pivotIndicator.pivotLevels.count
        let logisticCount = logisticIndicator.regressionLevels.count
        return "\(polyRes)-\(polySup)-\(pivotCount)-\(logisticCount)-\(priceMin)-\(priceMax)"
    }

    var body: some View {
        Canvas { context, size in
            // Draw Pivot Levels (BigBeluga style)
            drawPivotLevels(context: context)

            // Draw Polynomial Regression lines
            drawPolynomialRegression(context: context)

            // Draw Logistic Regression S&R levels
            drawLogisticRegressionLevels(context: context)
        }
        .id(canvasChangeId)  // Force Canvas recreation when indicator data changes
    }

    // MARK: - Price to Y Conversion

    private func priceToY(_ price: Double) -> CGFloat {
        let normalized = (price - priceMin) / (priceMax - priceMin)
        return chartHeight * (1 - normalized)
    }

    private func indexToX(_ index: Int) -> CGFloat {
        let visibleCount = visibleRange.upperBound - visibleRange.lowerBound + 1
        guard visibleCount > 0 else { return 0 }
        let relativeIndex = index - visibleRange.lowerBound
        return (CGFloat(relativeIndex) / CGFloat(visibleCount)) * chartWidth
    }

    // MARK: - Pivot Levels Drawing

    private func drawPivotLevels(context: GraphicsContext) {
        for level in pivotIndicator.pivotLevels {
            guard level.display else { continue }

            let lineWidth = pivotIndicator.lineWidth(for: level.length)
            let glowWidth = pivotIndicator.glowWidth(for: level.length)

            // Draw high pivot level
            if level.levelHigh > 0 {
                let yHigh = priceToY(level.levelHigh)

                // Glow effect
                var glowPath = Path()
                glowPath.move(to: CGPoint(x: 0, y: yHigh))
                glowPath.addLine(to: CGPoint(x: chartWidth, y: yHigh))
                context.stroke(
                    glowPath,
                    with: .color(level.highColor.opacity(0.2)),
                    lineWidth: glowWidth
                )

                // Core line
                var corePath = Path()
                corePath.move(to: CGPoint(x: 0, y: yHigh))
                corePath.addLine(to: CGPoint(x: chartWidth, y: yHigh))
                context.stroke(
                    corePath,
                    with: .color(level.highColor),
                    style: StrokeStyle(lineWidth: lineWidth, dash: level.style == .dashed ? [6, 4] : level.style == .dotted ? [2, 3] : [])
                )

                // Price label
                let priceText = String(format: "%.2f", level.levelHigh)
                let textPoint = CGPoint(x: chartWidth - 50, y: yHigh - 12)
                context.draw(
                    Text(priceText).font(.caption2).foregroundColor(level.highColor),
                    at: textPoint
                )
            }

            // Draw low pivot level
            if level.levelLow > 0 {
                let yLow = priceToY(level.levelLow)

                // Glow effect
                var glowPath = Path()
                glowPath.move(to: CGPoint(x: 0, y: yLow))
                glowPath.addLine(to: CGPoint(x: chartWidth, y: yLow))
                context.stroke(
                    glowPath,
                    with: .color(level.lowColor.opacity(0.2)),
                    lineWidth: glowWidth
                )

                // Core line
                var corePath = Path()
                corePath.move(to: CGPoint(x: 0, y: yLow))
                corePath.addLine(to: CGPoint(x: chartWidth, y: yLow))
                context.stroke(
                    corePath,
                    with: .color(level.lowColor),
                    style: StrokeStyle(lineWidth: lineWidth, dash: level.style == .dashed ? [6, 4] : level.style == .dotted ? [2, 3] : [])
                )

                // Price label
                let priceText = String(format: "%.2f", level.levelLow)
                let textPoint = CGPoint(x: chartWidth - 50, y: yLow + 12)
                context.draw(
                    Text(priceText).font(.caption2).foregroundColor(level.lowColor),
                    at: textPoint
                )
            }
        }
    }

    // MARK: - Polynomial Regression Drawing

    private func drawPolynomialRegression(context: GraphicsContext) {
        // Draw resistance line
        if let resLine = polyIndicator.resistanceLine {
            drawRegressionCurve(
                context: context,
                points: resLine.predictedPoints,
                color: polyIndicator.settings.resistanceColor,
                lineWidth: 2
            )
        }

        // Draw support line
        if let supLine = polyIndicator.supportLine {
            drawRegressionCurve(
                context: context,
                points: supLine.predictedPoints,
                color: polyIndicator.settings.supportColor,
                lineWidth: 2
            )
        }

        // Draw pivots if enabled
        if polyIndicator.settings.showPivots {
            for pivot in polyIndicator.pivots.highs {
                let x = indexToX(pivot.index)
                let y = priceToY(pivot.price)

                if x >= 0 && x <= chartWidth {
                    let circle = Path(ellipseIn: CGRect(x: x - 3, y: y - 3, width: 6, height: 6))
                    context.fill(circle, with: .color(polyIndicator.settings.resistanceColor))
                }
            }

            for pivot in polyIndicator.pivots.lows {
                let x = indexToX(pivot.index)
                let y = priceToY(pivot.price)

                if x >= 0 && x <= chartWidth {
                    let circle = Path(ellipseIn: CGRect(x: x - 3, y: y - 3, width: 6, height: 6))
                    context.fill(circle, with: .color(polyIndicator.settings.supportColor))
                }
            }
        }

        // Draw signals
        for signal in polyIndicator.signals {
            let x = indexToX(signal.index)
            let y = priceToY(signal.price)

            if x >= 0 && x <= chartWidth {
                switch signal.type {
                case .resistanceBreak, .supportBreak:
                    let diamond = diamondPath(at: CGPoint(x: x, y: y), size: 8)
                    context.fill(diamond, with: .color(.blue))
                case .resistanceTest:
                    let triangle = trianglePath(at: CGPoint(x: x, y: y), size: 6, pointingDown: true)
                    context.fill(triangle, with: .color(polyIndicator.settings.resistanceColor))
                case .supportTest:
                    let triangle = trianglePath(at: CGPoint(x: x, y: y), size: 6, pointingDown: false)
                    context.fill(triangle, with: .color(polyIndicator.settings.supportColor))
                }
            }
        }
    }

    private func drawRegressionCurve(
        context: GraphicsContext,
        points: [CGPoint],
        color: Color,
        lineWidth: CGFloat
    ) {
        guard points.count >= 2 else { return }

        var path = Path()
        var started = false

        for point in points {
            let x = indexToX(Int(point.x))
            let y = priceToY(point.y)

            guard x >= -50 && x <= chartWidth + 50 else { continue }

            if !started {
                path.move(to: CGPoint(x: x, y: y))
                started = true
            } else {
                path.addLine(to: CGPoint(x: x, y: y))
            }
        }

        if started {
            context.stroke(path, with: .color(color), lineWidth: lineWidth)
        }
    }

    // MARK: - Logistic Regression Drawing

    private func drawLogisticRegressionLevels(context: GraphicsContext) {
        for level in logisticIndicator.regressionLevels {
            let y = priceToY(level.level)

            // Calculate line extent
            let startX = indexToX(level.startIndex)
            let endX = level.endIndex != nil ? indexToX(level.endIndex!) : chartWidth

            guard endX > 0 && startX < chartWidth else { continue }

            let clampedStartX = max(0, startX)
            let clampedEndX = min(chartWidth, endX)

            // Draw the S/R line
            var path = Path()
            path.move(to: CGPoint(x: clampedStartX, y: y))
            path.addLine(to: CGPoint(x: clampedEndX, y: y))

            let color = level.isSupport ? logisticIndicator.settings.supportColor : logisticIndicator.settings.resistanceColor

            context.stroke(path, with: .color(color), lineWidth: 3)

            // Draw prediction label if enabled
            if logisticIndicator.settings.showPredictionLabels {
                let labelX = (clampedStartX + clampedEndX) / 2
                let labelY = level.isSupport ? y + 12 : y - 12
                let predictionText = String(format: "%.0f%%", level.detectedPrediction * 100)

                context.draw(
                    Text(predictionText).font(.caption2).foregroundColor(color),
                    at: CGPoint(x: labelX, y: labelY)
                )
            }
        }

        // Draw signal labels if enabled
        if logisticIndicator.settings.showRetests || logisticIndicator.settings.showBreaks {
            for signal in logisticIndicator.currentSignals {
                let labelText: String
                let labelColor: Color

                switch signal {
                case .supportRetest:
                    guard logisticIndicator.settings.showRetests else { continue }
                    labelText = "R"
                    labelColor = logisticIndicator.settings.supportColor
                case .supportBreak:
                    guard logisticIndicator.settings.showBreaks else { continue }
                    labelText = "B"
                    labelColor = .blue
                case .resistanceRetest:
                    guard logisticIndicator.settings.showRetests else { continue }
                    labelText = "R"
                    labelColor = logisticIndicator.settings.resistanceColor
                case .resistanceBreak:
                    guard logisticIndicator.settings.showBreaks else { continue }
                    labelText = "B"
                    labelColor = .blue
                }

                context.draw(
                    Text(labelText).font(.caption).bold().foregroundColor(labelColor),
                    at: CGPoint(x: chartWidth - 20, y: 20)
                )
            }
        }
    }

    // MARK: - Shape Helpers

    private func diamondPath(at point: CGPoint, size: CGFloat) -> Path {
        var path = Path()
        path.move(to: CGPoint(x: point.x, y: point.y - size))
        path.addLine(to: CGPoint(x: point.x + size, y: point.y))
        path.addLine(to: CGPoint(x: point.x, y: point.y + size))
        path.addLine(to: CGPoint(x: point.x - size, y: point.y))
        path.closeSubpath()
        return path
    }

    private func trianglePath(at point: CGPoint, size: CGFloat, pointingDown: Bool) -> Path {
        var path = Path()
        if pointingDown {
            path.move(to: CGPoint(x: point.x, y: point.y + size))
            path.addLine(to: CGPoint(x: point.x + size, y: point.y - size))
            path.addLine(to: CGPoint(x: point.x - size, y: point.y - size))
        } else {
            path.move(to: CGPoint(x: point.x, y: point.y - size))
            path.addLine(to: CGPoint(x: point.x + size, y: point.y + size))
            path.addLine(to: CGPoint(x: point.x - size, y: point.y + size))
        }
        path.closeSubpath()
        return path
    }
}

// MARK: - Individual Indicator Views

/// Standalone view for just Pivot Levels
struct PivotLevelsOverlayView: View {
    @ObservedObject var indicator: PivotLevelsIndicator
    let chartWidth: CGFloat
    let chartHeight: CGFloat
    let priceMin: Double
    let priceMax: Double

    var body: some View {
        Canvas { context, size in
            for level in indicator.pivotLevels {
                guard level.display else { continue }

                let lineWidth = indicator.lineWidth(for: level.length)

                // High level
                if level.levelHigh > 0 {
                    let y = chartHeight * (1 - (level.levelHigh - priceMin) / (priceMax - priceMin))

                    var path = Path()
                    path.move(to: CGPoint(x: 0, y: y))
                    path.addLine(to: CGPoint(x: chartWidth, y: y))

                    context.stroke(path, with: .color(level.highColor), lineWidth: lineWidth)
                }

                // Low level
                if level.levelLow > 0 {
                    let y = chartHeight * (1 - (level.levelLow - priceMin) / (priceMax - priceMin))

                    var path = Path()
                    path.move(to: CGPoint(x: 0, y: y))
                    path.addLine(to: CGPoint(x: chartWidth, y: y))

                    context.stroke(path, with: .color(level.lowColor), lineWidth: lineWidth)
                }
            }
        }
    }
}

/// Standalone view for Polynomial Regression S&R
struct PolynomialRegressionOverlayView: View {
    @ObservedObject var indicator: PolynomialRegressionIndicator
    let chartWidth: CGFloat
    let chartHeight: CGFloat
    let priceMin: Double
    let priceMax: Double
    let visibleRange: ClosedRange<Int>

    var body: some View {
        Canvas { context, size in
            // Draw current S/R levels as horizontal lines
            if let res = indicator.currentResistance {
                let y = chartHeight * (1 - (res - priceMin) / (priceMax - priceMin))
                var path = Path()
                path.move(to: CGPoint(x: 0, y: y))
                path.addLine(to: CGPoint(x: chartWidth, y: y))
                context.stroke(path, with: .color(indicator.settings.resistanceColor), lineWidth: 2)
            }

            if let sup = indicator.currentSupport {
                let y = chartHeight * (1 - (sup - priceMin) / (priceMax - priceMin))
                var path = Path()
                path.move(to: CGPoint(x: 0, y: y))
                path.addLine(to: CGPoint(x: chartWidth, y: y))
                context.stroke(path, with: .color(indicator.settings.supportColor), lineWidth: 2)
            }
        }
    }
}

/// Standalone view for Logistic Regression S&R
struct LogisticRegressionOverlayView: View {
    @ObservedObject var indicator: LogisticRegressionIndicator
    let chartWidth: CGFloat
    let chartHeight: CGFloat
    let priceMin: Double
    let priceMax: Double

    var body: some View {
        Canvas { context, size in
            for level in indicator.regressionLevels {
                let y = chartHeight * (1 - (level.level - priceMin) / (priceMax - priceMin))

                var path = Path()
                path.move(to: CGPoint(x: 0, y: y))
                path.addLine(to: CGPoint(x: chartWidth, y: y))

                let color = level.isSupport ? indicator.settings.supportColor : indicator.settings.resistanceColor
                context.stroke(path, with: .color(color), lineWidth: 3)

                // Prediction label
                if indicator.settings.showPredictionLabels {
                    let text = String(format: "%.0f%%", level.detectedPrediction * 100)
                    context.draw(
                        Text(text).font(.caption2).foregroundColor(color),
                        at: CGPoint(x: chartWidth - 40, y: y - 10)
                    )
                }
            }
        }
    }
}
