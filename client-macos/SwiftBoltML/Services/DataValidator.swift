import Foundation

/// Data validation service to ensure OHLCV data integrity
/// Implements cross-reference checks and anomaly detection
class DataValidator {
    
    // MARK: - Validation Results
    
    struct ValidationResult {
        let isValid: Bool
        let issues: [ValidationIssue]
        let confidence: Double  // 0-1
        
        var hasWarnings: Bool {
            issues.contains { $0.severity == .warning }
        }
        
        var hasErrors: Bool {
            issues.contains { $0.severity == .error }
        }
    }
    
    struct ValidationIssue {
        enum Severity {
            case warning
            case error
        }
        
        let severity: Severity
        let message: String
        let barIndex: Int?
        let timestamp: Date?
    }
    
    // MARK: - Validation Rules
    
    /// Validate OHLCV data integrity
    func validate(bars: [OHLCBar], symbol: String) -> ValidationResult {
        var issues: [ValidationIssue] = []
        
        // 1. Basic OHLC consistency checks
        issues.append(contentsOf: validateOHLCConsistency(bars: bars))
        
        // 2. Price continuity checks (gaps, spikes)
        issues.append(contentsOf: validatePriceContinuity(bars: bars))
        
        // 3. Volume sanity checks
        issues.append(contentsOf: validateVolume(bars: bars))
        
        // 4. Timestamp sequence validation
        issues.append(contentsOf: validateTimestamps(bars: bars))
        
        // 5. Statistical outlier detection
        issues.append(contentsOf: detectOutliers(bars: bars))
        
        // Calculate confidence score
        let errorCount = issues.filter { $0.severity == .error }.count
        let warningCount = issues.filter { $0.severity == .warning }.count
        let confidence = max(0.0, 1.0 - (Double(errorCount) * 0.2) - (Double(warningCount) * 0.05))
        
        return ValidationResult(
            isValid: errorCount == 0,
            issues: issues,
            confidence: confidence
        )
    }
    
    // MARK: - Individual Validation Methods
    
    private func validateOHLCConsistency(bars: [OHLCBar]) -> [ValidationIssue] {
        var issues: [ValidationIssue] = []
        
        for (index, bar) in bars.enumerated() {
            // High must be >= Low
            if bar.high < bar.low {
                issues.append(ValidationIssue(
                    severity: .error,
                    message: "Invalid OHLC: High (\(bar.high)) < Low (\(bar.low))",
                    barIndex: index,
                    timestamp: bar.ts
                ))
            }
            
            // High must be >= Open and Close
            if bar.high < bar.open || bar.high < bar.close {
                issues.append(ValidationIssue(
                    severity: .error,
                    message: "Invalid OHLC: High not highest value",
                    barIndex: index,
                    timestamp: bar.ts
                ))
            }
            
            // Low must be <= Open and Close
            if bar.low > bar.open || bar.low > bar.close {
                issues.append(ValidationIssue(
                    severity: .error,
                    message: "Invalid OHLC: Low not lowest value",
                    barIndex: index,
                    timestamp: bar.ts
                ))
            }
            
            // Check for zero or negative prices
            if bar.open <= 0 || bar.high <= 0 || bar.low <= 0 || bar.close <= 0 {
                issues.append(ValidationIssue(
                    severity: .error,
                    message: "Invalid price: Zero or negative value",
                    barIndex: index,
                    timestamp: bar.ts
                ))
            }
        }
        
        return issues
    }
    
    private func validatePriceContinuity(bars: [OHLCBar]) -> [ValidationIssue] {
        var issues: [ValidationIssue] = []
        
        guard bars.count > 1 else { return issues }
        
        for i in 1..<bars.count {
            let prevBar = bars[i - 1]
            let currBar = bars[i]
            
            // Calculate price change percentage
            let priceChange = abs(currBar.open - prevBar.close) / prevBar.close
            
            // Flag gaps > 20% (potential data error or stock split)
            if priceChange > 0.20 {
                issues.append(ValidationIssue(
                    severity: .warning,
                    message: String(format: "Large price gap: %.1f%% (possible split or data error)", priceChange * 100),
                    barIndex: i,
                    timestamp: currBar.ts
                ))
            }
            
            // Flag extreme intrabar moves (> 50% range)
            let range = currBar.high - currBar.low
            let rangePercent = range / currBar.open
            if rangePercent > 0.50 {
                issues.append(ValidationIssue(
                    severity: .warning,
                    message: String(format: "Extreme intrabar range: %.1f%%", rangePercent * 100),
                    barIndex: i,
                    timestamp: currBar.ts
                ))
            }
        }
        
        return issues
    }
    
    private func validateVolume(bars: [OHLCBar]) -> [ValidationIssue] {
        var issues: [ValidationIssue] = []
        
        // Calculate average volume
        let avgVolume = bars.map { $0.volume }.reduce(0, +) / Double(bars.count)
        
        for (index, bar) in bars.enumerated() {
            // Check for zero volume (suspicious for liquid stocks)
            if bar.volume == 0 {
                issues.append(ValidationIssue(
                    severity: .warning,
                    message: "Zero volume bar",
                    barIndex: index,
                    timestamp: bar.ts
                ))
            }
            
            // Flag volume spikes > 10x average
            if bar.volume > avgVolume * 10 {
                issues.append(ValidationIssue(
                    severity: .warning,
                    message: String(format: "Volume spike: %.1fx average", bar.volume / avgVolume),
                    barIndex: index,
                    timestamp: bar.ts
                ))
            }
        }
        
        return issues
    }
    
    private func validateTimestamps(bars: [OHLCBar]) -> [ValidationIssue] {
        var issues: [ValidationIssue] = []
        
        guard bars.count > 1 else { return issues }
        
        for i in 1..<bars.count {
            let prevBar = bars[i - 1]
            let currBar = bars[i]
            
            // Timestamps must be sequential
            if currBar.ts <= prevBar.ts {
                issues.append(ValidationIssue(
                    severity: .error,
                    message: "Non-sequential timestamps",
                    barIndex: i,
                    timestamp: currBar.ts
                ))
            }
            
            // Check for future timestamps
            if currBar.ts > Date() {
                issues.append(ValidationIssue(
                    severity: .error,
                    message: "Future timestamp detected",
                    barIndex: i,
                    timestamp: currBar.ts
                ))
            }
        }
        
        return issues
    }
    
    private func detectOutliers(bars: [OHLCBar]) -> [ValidationIssue] {
        var issues: [ValidationIssue] = []
        
        guard bars.count > 20 else { return issues }
        
        // Calculate returns
        var returns: [Double] = []
        for i in 1..<bars.count {
            let ret = (bars[i].close - bars[i-1].close) / bars[i-1].close
            returns.append(ret)
        }
        
        // Calculate mean and std dev
        let mean = returns.reduce(0, +) / Double(returns.count)
        let variance = returns.map { pow($0 - mean, 2) }.reduce(0, +) / Double(returns.count)
        let stdDev = sqrt(variance)
        
        // Flag returns > 5 standard deviations (likely data error)
        for (index, ret) in returns.enumerated() {
            let zScore = abs(ret - mean) / stdDev
            if zScore > 5.0 {
                issues.append(ValidationIssue(
                    severity: .warning,
                    message: String(format: "Statistical outlier: %.1fσ return", zScore),
                    barIndex: index + 1,
                    timestamp: bars[index + 1].ts
                ))
            }
        }
        
        return issues
    }
    
    // MARK: - Cross-Reference Validation
    
    /// Compare data from two sources and flag discrepancies
    func crossValidate(
        primary: [OHLCBar],
        secondary: [OHLCBar],
        tolerance: Double = 0.02  // 2% tolerance
    ) -> ValidationResult {
        var issues: [ValidationIssue] = []
        
        // Match bars by timestamp
        let primaryDict = Dictionary(uniqueKeysWithValues: primary.map { ($0.ts, $0) })
        
        for secondaryBar in secondary {
            guard let primaryBar = primaryDict[secondaryBar.ts] else {
                issues.append(ValidationIssue(
                    severity: .warning,
                    message: "Bar missing in primary source",
                    barIndex: nil,
                    timestamp: secondaryBar.ts
                ))
                continue
            }
            
            // Compare close prices (most important)
            let closeDiff = abs(primaryBar.close - secondaryBar.close) / primaryBar.close
            if closeDiff > tolerance {
                issues.append(ValidationIssue(
                    severity: .error,
                    message: String(format: "Price mismatch: %.2f%% difference", closeDiff * 100),
                    barIndex: nil,
                    timestamp: primaryBar.ts
                ))
            }
            
            // Compare volume (more lenient tolerance)
            let volumeDiff = abs(primaryBar.volume - secondaryBar.volume) / primaryBar.volume
            if volumeDiff > 0.10 {  // 10% tolerance for volume
                issues.append(ValidationIssue(
                    severity: .warning,
                    message: String(format: "Volume mismatch: %.1f%% difference", volumeDiff * 100),
                    barIndex: nil,
                    timestamp: primaryBar.ts
                ))
            }
        }
        
        let errorCount = issues.filter { $0.severity == .error }.count
        let confidence = max(0.0, 1.0 - (Double(errorCount) * 0.1))
        
        return ValidationResult(
            isValid: errorCount == 0,
            issues: issues,
            confidence: confidence
        )
    }
}
