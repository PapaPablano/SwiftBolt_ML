import Foundation
import SwiftUI
import Combine

// MARK: - Polynomial Regression Engine

/// Polynomial regression calculator for curve fitting
/// Uses normalized X values for numerical stability
struct PolynomialRegression {

    enum RegressionType: String, CaseIterable {
        case linear = "Linear"
        case quadratic = "Quadratic"
        case cubic = "Cubic"

        var degrees: [Int] {
            switch self {
            case .linear: return [0, 1]
            case .quadratic: return [0, 1, 2]
            case .cubic: return [0, 1, 2, 3]
            }
        }
    }

    /// Coefficients with normalization parameters for stable prediction
    struct Coefficients {
        var values: [Double]
        var xMin: Double = 0
        var xMax: Double = 1

        subscript(index: Int) -> Double {
            get { index < values.count ? values[index] : 0 }
            set { if index < values.count { values[index] = newValue } }
        }

        /// Normalize x value to [0, 1] range
        func normalizeX(_ x: Double) -> Double {
            let range = xMax - xMin
            guard range > 0 else { return 0.5 }
            return (x - xMin) / range
        }
    }

    /// Fit polynomial regression to data points using standard degrees
    static func fit(xValues: [Double], yValues: [Double], type: RegressionType) -> Coefficients? {
        return fit(xValues: xValues, yValues: yValues, degrees: type.degrees)
    }

    /// Fit polynomial regression with custom degrees
    /// - Parameters:
    ///   - xValues: X coordinates (bar offsets, where 0 = current bar, positive = past)
    ///   - yValues: Y coordinates (prices)
    ///   - degrees: Custom polynomial degrees e.g. [0, 1, 2] for quadratic
    /// - Returns: Polynomial coefficients with normalization parameters
    static func fit(xValues: [Double], yValues: [Double], degrees: [Int]) -> Coefficients? {
        guard xValues.count == yValues.count, xValues.count >= 2 else { return nil }
        guard degrees.count <= xValues.count else { return nil }

        // Normalize X values to [0, 1] for numerical stability
        let xMin = xValues.min() ?? 0
        let xMax = xValues.max() ?? 1
        let xRange = xMax - xMin

        let normalizedX: [Double]
        if xRange > 0 {
            normalizedX = xValues.map { ($0 - xMin) / xRange }
        } else {
            normalizedX = xValues.map { _ in 0.5 }
        }

        // Build Vandermonde matrix with normalized X
        let matrix = buildMatrix(normalizedX, degrees: degrees)

        // Solve using least squares
        guard let coeffs = solveLeastSquares(matrix: matrix, y: yValues) else {
            return nil
        }

        var result = Coefficients(values: coeffs)
        result.xMin = xMin
        result.xMax = xMax
        return result
    }

    /// Predict Y value for given X (uses stored normalization parameters)
    /// - Parameters:
    ///   - coefficients: Fitted coefficients with normalization params
    ///   - x: X value (0 = current bar, positive = past, negative = future)
    /// - Returns: Predicted Y value
    static func predict(coefficients: Coefficients, x: Double) -> Double {
        // Normalize x using the stored parameters
        let normalizedX = coefficients.normalizeX(x)

        var result: Double = 0
        for (index, coeff) in coefficients.values.enumerated() {
            result += coeff * pow(normalizedX, Double(index))
        }
        return result
    }

    // MARK: - Private Methods

    private static func buildMatrix(_ xValues: [Double], degrees: [Int]) -> [[Double]] {
        var matrix: [[Double]] = Array(
            repeating: Array(repeating: 0.0, count: degrees.count),
            count: xValues.count
        )

        for (row, x) in xValues.enumerated() {
            for (col, degree) in degrees.enumerated() {
                matrix[row][col] = pow(x, Double(degree))
            }
        }

        return matrix
    }

    private static func solveLeastSquares(matrix: [[Double]], y: [Double]) -> [Double]? {
        let m = matrix.count      // rows
        let n = matrix[0].count   // columns

        // A^T * A
        var ata = Array(repeating: Array(repeating: 0.0, count: n), count: n)

        for i in 0..<n {
            for j in 0..<n {
                var sum: Double = 0
                for k in 0..<m {
                    sum += matrix[k][i] * matrix[k][j]
                }
                ata[i][j] = sum
            }
        }

        // A^T * b
        var atb = Array(repeating: 0.0, count: n)
        for i in 0..<n {
            var sum: Double = 0
            for k in 0..<m {
                sum += matrix[k][i] * y[k]
            }
            atb[i] = sum
        }

        // Gaussian elimination
        return gaussianElimination(ata, b: atb)
    }

    private static func gaussianElimination(_ a: [[Double]], b: [Double]) -> [Double]? {
        var matrix = a
        var rhs = b
        let n = matrix.count

        // Forward elimination
        for i in 0..<n {
            // Find pivot
            var maxRow = i
            for k in (i + 1)..<n {
                if abs(matrix[k][i]) > abs(matrix[maxRow][i]) {
                    maxRow = k
                }
            }

            // Swap rows
            (matrix[i], matrix[maxRow]) = (matrix[maxRow], matrix[i])
            (rhs[i], rhs[maxRow]) = (rhs[maxRow], rhs[i])

            // Check for singular matrix
            if abs(matrix[i][i]) < 1e-10 {
                return nil
            }

            // Eliminate column
            for k in (i + 1)..<n {
                let factor = matrix[k][i] / matrix[i][i]
                for j in i..<n {
                    matrix[k][j] -= factor * matrix[i][j]
                }
                rhs[k] -= factor * rhs[i]
            }
        }

        // Back substitution
        var solution = Array(repeating: 0.0, count: n)
        for i in stride(from: n - 1, through: 0, by: -1) {
            solution[i] = rhs[i]
            for j in (i + 1)..<n {
                solution[i] -= matrix[i][j] * solution[j]
            }
            solution[i] /= matrix[i][i]
        }

        return solution
    }
}

// MARK: - Regression Line Result

/// Represents a computed regression line
struct RegressionLine: Identifiable {
    let id = UUID()
    let coefficients: PolynomialRegression.Coefficients
    let startIndex: Int
    let endIndex: Int
    let predictedPoints: [CGPoint]
    let isSupport: Bool
}

/// Signal detected from regression analysis
struct RegressionSignal: Identifiable {
    let id = UUID()
    let type: RegressionSignalType
    let price: Double
    let index: Int
    let date: Date
}

enum RegressionSignalType {
    case resistanceBreak
    case resistanceTest
    case supportBreak
    case supportTest
}

// MARK: - Support Resistance Polynomial Indicator

/// Polynomial regression-based support and resistance indicator
@MainActor
class PolynomialRegressionIndicator: ObservableObject {

    // MARK: - Settings

    struct Settings {
        // Resistance pivot detection
        var resistanceEnabled: Bool = true
        var resistanceType: PolynomialRegression.RegressionType = .linear
        var resistancePivotSizeL: Int = 5   // Bars to the left
        var resistancePivotSizeR: Int = 5   // Bars to the right
        var resistanceYOffset: Double = 0
        var resistanceCustomDegrees: [Int]? = nil  // For custom polynomial

        // Support pivot detection
        var supportEnabled: Bool = true
        var supportType: PolynomialRegression.RegressionType = .linear
        var supportPivotSizeL: Int = 5
        var supportPivotSizeR: Int = 5
        var supportYOffset: Double = 0
        var supportCustomDegrees: [Int]? = nil

        // General
        var extendFuture: Int = 20  // Bars to extend into future (reduced from 150 for better visibility)
        var showPivots: Bool = true
        var showTests: Bool = true
        var showBreaks: Bool = true
        var rollingCalculation: Bool = false  // Recalculate as bars update

        // Lookback window - only use pivots from the last N bars (nil = all bars)
        // TradingView style typically uses ~150 bar window for cleaner trend lines
        var lookbackBars: Int? = 150

        // Data range (optional - if nil, use lookbackBars or all pivots)
        var resistanceStartIndex: Int? = nil
        var resistanceEndIndex: Int? = nil
        var supportStartIndex: Int? = nil
        var supportEndIndex: Int? = nil

        // Colors
        var supportColor: Color = .green
        var resistanceColor: Color = .red
        var centerLineColor: Color = .white.opacity(0.3)
    }

    // MARK: - Published Properties

    @Published var resistanceLine: RegressionLine?
    @Published var supportLine: RegressionLine?
    @Published var signals: [RegressionSignal] = []
    @Published var pivots: (highs: [DetectedPivot], lows: [DetectedPivot]) = ([], [])
    @Published var settings: Settings = Settings()
    @Published var isLoading: Bool = false
    @Published var errorMessage: String?

    // MARK: - Private Properties

    private var bars: [OHLCBar] = []

    // MARK: - Public Methods

    /// Calculate polynomial regression S&R for given bars
    /// Optimized for macOS performance with minimal allocations
    func calculate(bars: [OHLCBar]) {
        // Always reset state first to ensure clean calculation for new data
        resistanceLine = nil
        supportLine = nil
        signals = []
        pivots = ([], [])
        self.bars = []

        guard !bars.isEmpty else { return }

        isLoading = true
        errorMessage = nil
        self.bars = bars

        #if DEBUG
        if let firstBar = bars.first, let lastBar = bars.last {
            print("[PolynomialSR] ========================================")
            print("[PolynomialSR] Calculating for \(bars.count) bars")
            print("[PolynomialSR] First bar close: \(String(format: "%.2f", firstBar.close))")
            print("[PolynomialSR] Last bar close: \(String(format: "%.2f", lastBar.close))")
        }
        #endif

        // Detect pivots with separate left/right sizes
        // Use autoreleasepool for better memory management on macOS
        let resistancePivots = detectPivotsWithLeftRight(
            bars: bars,
            leftSize: settings.resistancePivotSizeL,
            rightSize: settings.resistancePivotSizeR,
            type: .high
        )

        let supportPivots = detectPivotsWithLeftRight(
            bars: bars,
            leftSize: settings.supportPivotSizeL,
            rightSize: settings.supportPivotSizeR,
            type: .low
        )

        self.pivots = (resistancePivots, supportPivots)

        #if DEBUG
        print("[PolynomialSR] Found \(resistancePivots.count) resistance pivots, \(supportPivots.count) support pivots")
        if !resistancePivots.isEmpty {
            let resPrices = resistancePivots.prefix(5).map { String(format: "%.2f", $0.price) }.joined(separator: ", ")
            print("[PolynomialSR] Resistance pivot prices (first 5): [\(resPrices)]")
        }
        if !supportPivots.isEmpty {
            let supPrices = supportPivots.prefix(5).map { String(format: "%.2f", $0.price) }.joined(separator: ", ")
            print("[PolynomialSR] Support pivot prices (first 5): [\(supPrices)]")
        }
        #endif

        // Calculate resistance regression
        if settings.resistanceEnabled && !resistancePivots.isEmpty {
            calculateResistanceRegression(pivots: resistancePivots, bars: bars)
        }

        // Calculate support regression
        if settings.supportEnabled && !supportPivots.isEmpty {
            calculateSupportRegression(pivots: supportPivots, bars: bars)
        }

        // Detect signals (only if enabled)
        if settings.showTests || settings.showBreaks {
            detectSignals(bars: bars)
        }

        #if DEBUG
        print("[PolynomialSR] Result: R=\(currentResistance.map { String(format: "%.2f", $0) } ?? "nil"), S=\(currentSupport.map { String(format: "%.2f", $0) } ?? "nil")")
        #endif

        isLoading = false
    }

    /// Get current resistance price level
    var currentResistance: Double? {
        guard let line = resistanceLine else { return nil }
        return PolynomialRegression.predict(coefficients: line.coefficients, x: 0)
    }

    /// Get current support price level
    var currentSupport: Double? {
        guard let line = supportLine else { return nil }
        return PolynomialRegression.predict(coefficients: line.coefficients, x: 0)
    }

    /// Get forecasted resistance at N bars into the future
    func forecastResistance(barsAhead: Int) -> Double? {
        guard let line = resistanceLine else { return nil }
        // Future = negative x values (since x=0 is current, positive is past)
        return PolynomialRegression.predict(coefficients: line.coefficients, x: Double(-barsAhead))
    }

    /// Get forecasted support at N bars into the future
    func forecastSupport(barsAhead: Int) -> Double? {
        guard let line = supportLine else { return nil }
        return PolynomialRegression.predict(coefficients: line.coefficients, x: Double(-barsAhead))
    }

    // MARK: - Private Methods

    /// Detect pivots with separate left and right lookback periods
    private func detectPivotsWithLeftRight(
        bars: [OHLCBar],
        leftSize: Int,
        rightSize: Int,
        type: PivotType
    ) -> [DetectedPivot] {
        var pivots: [DetectedPivot] = []

        guard bars.count > leftSize + rightSize else { return [] }

        for i in leftSize..<(bars.count - rightSize) {
            let bar = bars[i]

            if type == .high {
                // Check pivot high
                var isHigh = true

                // Check left side
                for j in (i - leftSize)..<i {
                    if bars[j].high > bar.high {
                        isHigh = false
                        break
                    }
                }

                // Check right side
                if isHigh {
                    for j in (i + 1)...(i + rightSize) {
                        if bars[j].high > bar.high {
                            isHigh = false
                            break
                        }
                    }
                }

                if isHigh {
                    pivots.append(DetectedPivot(index: i, price: bar.high, date: bar.ts, type: .high))
                }
            } else {
                // Check pivot low
                var isLow = true

                // Check left side
                for j in (i - leftSize)..<i {
                    if bars[j].low < bar.low {
                        isLow = false
                        break
                    }
                }

                // Check right side
                if isLow {
                    for j in (i + 1)...(i + rightSize) {
                        if bars[j].low < bar.low {
                            isLow = false
                            break
                        }
                    }
                }

                if isLow {
                    pivots.append(DetectedPivot(index: i, price: bar.low, date: bar.ts, type: .low))
                }
            }
        }

        return pivots
    }

    private func calculateResistanceRegression(pivots: [DetectedPivot], bars: [OHLCBar]) {
        let lastIndex = bars.count - 1

        // Filter pivots by lookback window first
        var filteredPivots = pivots
        if let lookback = settings.lookbackBars {
            let minIndex = max(0, lastIndex - lookback)
            filteredPivots = pivots.filter { $0.index >= minIndex }
        }

        // Then apply custom data range if specified
        if let startIdx = settings.resistanceStartIndex, let endIdx = settings.resistanceEndIndex {
            filteredPivots = filteredPivots.filter { $0.index >= startIdx && $0.index <= endIdx }
        }

        guard !filteredPivots.isEmpty else {
            resistanceLine = nil
            return
        }

        // Prepare data - preallocate arrays for better performance
        // X convention: 0 = current bar, positive = past, negative = future
        var xValues = [Double]()
        var yValues = [Double]()
        xValues.reserveCapacity(filteredPivots.count)
        yValues.reserveCapacity(filteredPivots.count)

        for pivot in filteredPivots {
            xValues.append(Double(lastIndex - pivot.index))
            yValues.append(pivot.price)
        }

        // Determine the best polynomial type based on pivot count
        let effectiveType = determineEffectiveType(
            requestedType: settings.resistanceType,
            customDegrees: settings.resistanceCustomDegrees,
            pivotCount: filteredPivots.count
        )

        // Fit with custom or standard degrees
        var coefficients: PolynomialRegression.Coefficients?
        if let customDegrees = settings.resistanceCustomDegrees {
            coefficients = PolynomialRegression.fit(xValues: xValues, yValues: yValues, degrees: customDegrees)
                ?? PolynomialRegression.fit(xValues: xValues, yValues: yValues, type: .linear)
        } else {
            coefficients = PolynomialRegression.fit(xValues: xValues, yValues: yValues, type: effectiveType)
        }

        guard var adjustedCoeffs = coefficients else {
            resistanceLine = nil
            return
        }

        // Apply Y offset
        adjustedCoeffs[0] += settings.resistanceYOffset

        #if DEBUG
        print("[PolynomialSR] Resistance: \(effectiveType.rawValue), pivots=\(filteredPivots.count), range=[\(String(format: "%.0f", adjustedCoeffs.xMin))-\(String(format: "%.0f", adjustedCoeffs.xMax))], pred@0=\(String(format: "%.2f", PolynomialRegression.predict(coefficients: adjustedCoeffs, x: 0)))")
        #endif

        // Generate points from oldest pivot through forecast
        let oldestPivotIndex = filteredPivots.map(\.index).min() ?? 0
        let oldestX = Double(lastIndex - oldestPivotIndex)

        let predictedPoints = generateForecastPoints(
            coefficients: adjustedCoeffs,
            lastIndex: lastIndex,
            oldestX: oldestX,
            extend: settings.extendFuture
        )

        #if DEBUG
        if let firstPt = predictedPoints.first, let lastPt = predictedPoints.last {
            print("[PolynomialSR]   Generated \(predictedPoints.count) points")
            print("[PolynomialSR]   First point: barIdx=\(Int(firstPt.x)), price=\(String(format: "%.2f", firstPt.y))")
            print("[PolynomialSR]   Last point: barIdx=\(Int(lastPt.x)), price=\(String(format: "%.2f", lastPt.y))")
        }
        #endif

        resistanceLine = RegressionLine(
            coefficients: adjustedCoeffs,
            startIndex: oldestPivotIndex,
            endIndex: lastIndex + settings.extendFuture,
            predictedPoints: predictedPoints,
            isSupport: false
        )
    }

    /// Determine the effective polynomial type based on available pivot count
    /// Automatically falls back to simpler types when not enough data points
    private func determineEffectiveType(
        requestedType: PolynomialRegression.RegressionType,
        customDegrees: [Int]?,
        pivotCount: Int
    ) -> PolynomialRegression.RegressionType {
        // Custom degrees take precedence
        if customDegrees != nil { return requestedType }

        // Need at least N+1 points for degree N polynomial
        // Linear (degree 1): need 2+ points
        // Quadratic (degree 2): need 3+ points
        // Cubic (degree 3): need 4+ points
        switch requestedType {
        case .cubic:
            if pivotCount >= 4 { return .cubic }
            else if pivotCount >= 3 { return .quadratic }
            else { return .linear }
        case .quadratic:
            if pivotCount >= 3 { return .quadratic }
            else { return .linear }
        case .linear:
            return .linear
        }
    }

    private func calculateSupportRegression(pivots: [DetectedPivot], bars: [OHLCBar]) {
        let lastIndex = bars.count - 1

        // Filter pivots by lookback window first
        var filteredPivots = pivots
        if let lookback = settings.lookbackBars {
            let minIndex = max(0, lastIndex - lookback)
            filteredPivots = pivots.filter { $0.index >= minIndex }
        }

        // Then apply custom data range if specified
        if let startIdx = settings.supportStartIndex, let endIdx = settings.supportEndIndex {
            filteredPivots = filteredPivots.filter { $0.index >= startIdx && $0.index <= endIdx }
        }

        guard !filteredPivots.isEmpty else {
            supportLine = nil
            return
        }

        // Prepare data - preallocate arrays for better performance
        var xValues = [Double]()
        var yValues = [Double]()
        xValues.reserveCapacity(filteredPivots.count)
        yValues.reserveCapacity(filteredPivots.count)

        for pivot in filteredPivots {
            xValues.append(Double(lastIndex - pivot.index))
            yValues.append(pivot.price)
        }

        // Determine the best polynomial type based on pivot count
        let effectiveType = determineEffectiveType(
            requestedType: settings.supportType,
            customDegrees: settings.supportCustomDegrees,
            pivotCount: filteredPivots.count
        )

        // Fit with custom or standard degrees
        var coefficients: PolynomialRegression.Coefficients?
        if let customDegrees = settings.supportCustomDegrees {
            coefficients = PolynomialRegression.fit(xValues: xValues, yValues: yValues, degrees: customDegrees)
                ?? PolynomialRegression.fit(xValues: xValues, yValues: yValues, type: .linear)
        } else {
            coefficients = PolynomialRegression.fit(xValues: xValues, yValues: yValues, type: effectiveType)
        }

        guard var adjustedCoeffs = coefficients else {
            supportLine = nil
            return
        }

        // Apply Y offset
        adjustedCoeffs[0] += settings.supportYOffset

        #if DEBUG
        print("[PolynomialSR] Support: \(effectiveType.rawValue), pivots=\(filteredPivots.count), range=[\(String(format: "%.0f", adjustedCoeffs.xMin))-\(String(format: "%.0f", adjustedCoeffs.xMax))], pred@0=\(String(format: "%.2f", PolynomialRegression.predict(coefficients: adjustedCoeffs, x: 0)))")
        #endif

        // Generate points from oldest pivot through forecast
        let oldestPivotIndex = filteredPivots.map(\.index).min() ?? 0
        let oldestX = Double(lastIndex - oldestPivotIndex)

        let predictedPoints = generateForecastPoints(
            coefficients: adjustedCoeffs,
            lastIndex: lastIndex,
            oldestX: oldestX,
            extend: settings.extendFuture
        )

        #if DEBUG
        if let firstPt = predictedPoints.first, let lastPt = predictedPoints.last {
            print("[PolynomialSR]   Generated \(predictedPoints.count) points")
            print("[PolynomialSR]   First point: barIdx=\(Int(firstPt.x)), price=\(String(format: "%.2f", firstPt.y))")
            print("[PolynomialSR]   Last point: barIdx=\(Int(lastPt.x)), price=\(String(format: "%.2f", lastPt.y))")
        }
        print("[PolynomialSR] ========================================")
        #endif

        supportLine = RegressionLine(
            coefficients: adjustedCoeffs,
            startIndex: oldestPivotIndex,
            endIndex: lastIndex + settings.extendFuture,
            predictedPoints: predictedPoints,
            isSupport: true
        )
    }

    /// Generate forecast points with correct x-value direction
    /// X convention: 0 = current bar, positive = past, negative = future
    /// Optimized with preallocated array for better macOS performance
    private func generateForecastPoints(
        coefficients: PolynomialRegression.Coefficients,
        lastIndex: Int,
        oldestX: Double,
        extend: Int
    ) -> [CGPoint] {
        let startX = Int(oldestX)  // Positive, into the past
        let endX = -extend         // Negative, into the future
        let pointCount = startX - endX + 1

        // Preallocate array for better performance
        var points = [CGPoint]()
        points.reserveCapacity(pointCount)

        for x in stride(from: startX, through: endX, by: -1) {
            let predictedY = PolynomialRegression.predict(coefficients: coefficients, x: Double(x))
            let barIndex = lastIndex - x
            points.append(CGPoint(x: CGFloat(barIndex), y: predictedY))
        }

        return points
    }

    private func detectSignals(bars: [OHLCBar]) {
        var detectedSignals: [RegressionSignal] = []

        guard bars.count >= 2 else {
            signals = []
            return
        }

        let lastBar = bars[bars.count - 1]
        let prevBar = bars[bars.count - 2]
        let lastIndex = bars.count - 1

        // Check resistance signals
        if let resLine = resistanceLine {
            // x=0 is current bar, x=1 is previous bar
            let currentRes = PolynomialRegression.predict(coefficients: resLine.coefficients, x: 0)
            let prevRes = PolynomialRegression.predict(coefficients: resLine.coefficients, x: 1)

            // Test: high touched resistance from below
            if lastBar.high >= currentRes && prevBar.high < prevRes && settings.showTests {
                detectedSignals.append(RegressionSignal(
                    type: .resistanceTest,
                    price: lastBar.high,
                    index: lastIndex,
                    date: lastBar.ts
                ))
            }

            // Break: close crossed above resistance
            if lastBar.close > currentRes && prevBar.close <= prevRes && settings.showBreaks {
                detectedSignals.append(RegressionSignal(
                    type: .resistanceBreak,
                    price: lastBar.close,
                    index: lastIndex,
                    date: lastBar.ts
                ))
            }
        }

        // Check support signals
        if let supLine = supportLine {
            let currentSup = PolynomialRegression.predict(coefficients: supLine.coefficients, x: 0)
            let prevSup = PolynomialRegression.predict(coefficients: supLine.coefficients, x: 1)

            // Test: low touched support from above
            if lastBar.low <= currentSup && prevBar.low > prevSup && settings.showTests {
                detectedSignals.append(RegressionSignal(
                    type: .supportTest,
                    price: lastBar.low,
                    index: lastIndex,
                    date: lastBar.ts
                ))
            }

            // Break: close crossed below support
            if lastBar.close < currentSup && prevBar.close >= prevSup && settings.showBreaks {
                detectedSignals.append(RegressionSignal(
                    type: .supportBreak,
                    price: lastBar.close,
                    index: lastIndex,
                    date: lastBar.ts
                ))
            }
        }

        signals = detectedSignals
    }
}
