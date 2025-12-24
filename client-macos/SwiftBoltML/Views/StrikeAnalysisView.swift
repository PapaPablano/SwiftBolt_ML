import SwiftUI
import Charts

struct StrikeAnalysisView: View {
    let symbol: String
    let strike: Double
    let side: String
    
    @State private var analysis: StrikeAnalysisResponse?
    @State private var isLoading = false
    @State private var error: String?
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Header
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("\(symbol) $\(String(format: "%.0f", strike)) \(side.uppercased())")
                        .font(.headline)
                    Text("Strike Price Analysis")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                
                Spacer()
                
                if isLoading {
                    ProgressView()
                        .scaleEffect(0.8)
                }
            }
            
            if let error = error {
                StrikeErrorBanner(message: error)
            } else if let analysis = analysis {
                StrikeAnalysisContent(analysis: analysis)
            } else if !isLoading {
                Text("Loading strike analysis...")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .padding()
        .background(Color(nsColor: .controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .task {
            await loadAnalysis()
        }
    }
    
    private func loadAnalysis() async {
        isLoading = true
        error = nil
        
        do {
            analysis = try await APIClient.shared.fetchStrikeAnalysis(
                symbol: symbol,
                strike: strike,
                side: side
            )
            isLoading = false
        } catch {
            self.error = error.localizedDescription
            isLoading = false
        }
    }
}

// MARK: - Strike Analysis Content

struct StrikeAnalysisContent: View {
    let analysis: StrikeAnalysisResponse
    
    var body: some View {
        VStack(spacing: 16) {
            // Summary metrics
            SummaryMetricsRow(analysis: analysis)
            
            Divider()
            
            // Expiration comparison
            if !analysis.expirations.isEmpty {
                ExpirationComparisonSection(expirations: analysis.expirations)
            }
            
            // Price history chart
            if !analysis.priceHistory.isEmpty {
                PriceHistoryChartSection(
                    priceHistory: analysis.priceHistory,
                    avgMark: analysis.overallStats.avgMark
                )
            }
        }
    }
}

// MARK: - Summary Metrics

struct SummaryMetricsRow: View {
    let analysis: StrikeAnalysisResponse
    
    var body: some View {
        HStack(spacing: 12) {
            // Current vs Average
            if let currentVsAvg = analysis.currentVsAvgPct {
                StrikeMetricBadge(
                    title: "vs Avg",
                    value: String(format: "%+.1f%%", currentVsAvg),
                    color: currentVsAvg < 0 ? .green : .red,
                    subtitle: currentVsAvg < 0 ? "Discount" : "Premium"
                )
            }
            
            // Best discount
            if let best = analysis.bestDiscount {
                StrikeMetricBadge(
                    title: "Best Deal",
                    value: best.formattedExpiry,
                    color: .green,
                    subtitle: String(format: "%.1f%% off", best.discountPct ?? 0)
                )
            }
            
            // Sample count
            StrikeMetricBadge(
                title: "Data Points",
                value: "\(analysis.overallStats.sampleCount)",
                color: .blue,
                subtitle: "\(analysis.lookbackDays)d lookback"
            )
            
            // Discounts found
            let discountCount = analysis.discountExpirations.count
            StrikeMetricBadge(
                title: "Discounts",
                value: "\(discountCount)/\(analysis.expirations.count)",
                color: discountCount > 0 ? .green : .orange,
                subtitle: "expirations"
            )
        }
    }
}

struct StrikeMetricBadge: View {
    let title: String
    let value: String
    let color: Color
    let subtitle: String
    
    var body: some View {
        VStack(spacing: 4) {
            Text(title)
                .font(.caption2)
                .foregroundStyle(.secondary)
            
            Text(value)
                .font(.subheadline.bold())
                .foregroundStyle(color)
            
            Text(subtitle)
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(8)
        .background(color.opacity(0.1))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}

// MARK: - Expiration Comparison

struct ExpirationComparisonSection: View {
    let expirations: [StrikeExpiryData]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Expiration Comparison")
                .font(.caption.bold())
                .foregroundStyle(.secondary)
            
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(expirations.prefix(8)) { exp in
                        ExpirationCard(expiry: exp)
                    }
                }
            }
        }
    }
}

struct ExpirationCard: View {
    let expiry: StrikeExpiryData
    
    private var statusColor: Color {
        if expiry.isDiscount {
            return .green
        } else if let diff = expiry.pctDiffFromAvg, diff > 5 {
            return .red
        }
        return .orange
    }
    
    var body: some View {
        VStack(spacing: 6) {
            // Expiry date
            Text(expiry.formattedExpiry)
                .font(.caption.bold())
            
            // Days to expiry
            if let days = expiry.daysToExpiry {
                Text("\(days)d")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
            
            Divider()
            
            // Current mark
            if let mark = expiry.currentMark {
                Text(String(format: "$%.2f", mark))
                    .font(.caption)
            }
            
            // Discount/premium indicator
            if let diff = expiry.pctDiffFromAvg {
                HStack(spacing: 2) {
                    Image(systemName: diff < 0 ? "arrow.down" : "arrow.up")
                        .font(.system(size: 8))
                    Text(String(format: "%.1f%%", abs(diff)))
                        .font(.caption2)
                }
                .foregroundStyle(statusColor)
            }
            
            // Status badge
            Text(expiry.isDiscount ? "DEAL" : "PREM")
                .font(.system(size: 8, weight: .bold))
                .foregroundStyle(.white)
                .padding(.horizontal, 4)
                .padding(.vertical, 2)
                .background(statusColor)
                .clipShape(Capsule())
        }
        .frame(width: 70)
        .padding(8)
        .background(Color(nsColor: .windowBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(statusColor.opacity(0.3), lineWidth: 1)
        )
    }
}

// MARK: - Price History Chart

struct PriceHistoryChartSection: View {
    let priceHistory: [StrikePriceHistoryPoint]
    let avgMark: Double?
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Price History")
                .font(.caption.bold())
                .foregroundStyle(.secondary)
            
            Chart {
                ForEach(priceHistory) { point in
                    if let mark = point.mark, let date = point.date {
                        LineMark(
                            x: .value("Date", date),
                            y: .value("Price", mark)
                        )
                        .foregroundStyle(.blue)
                    }
                }
                
                // Average line
                if let avg = avgMark {
                    RuleMark(y: .value("Average", avg))
                        .foregroundStyle(.orange)
                        .lineStyle(StrokeStyle(lineWidth: 1, dash: [5, 3]))
                        .annotation(position: .top, alignment: .trailing) {
                            Text("Avg: $\(String(format: "%.2f", avg))")
                                .font(.caption2)
                                .foregroundStyle(.orange)
                        }
                }
            }
            .frame(height: 120)
            .chartXAxis {
                AxisMarks(values: .automatic(desiredCount: 4)) { _ in
                    AxisGridLine()
                    AxisValueLabel(format: .dateTime.month().day())
                }
            }
            .chartYAxis {
                AxisMarks(position: .leading) { _ in
                    AxisGridLine()
                    AxisValueLabel()
                }
            }
        }
    }
}

// MARK: - Strike Error Banner

struct StrikeErrorBanner: View {
    let message: String
    
    var body: some View {
        HStack {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundStyle(.orange)
            Text(message)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(8)
        .background(Color.orange.opacity(0.1))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}

#Preview {
    StrikeAnalysisView(symbol: "AAPL", strike: 180, side: "call")
        .frame(width: 400)
        .padding()
}
