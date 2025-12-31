import SwiftUI

/// Detailed view for a ranked option contract
/// Shows comprehensive information including ML breakdown, strike comparison, and full contract specs
struct OptionRankDetailView: View {
    let rank: OptionRank
    let symbol: String
    let allRankings: [OptionRank]
    @Environment(\.dismiss) var dismiss

    // Group rankings by strike for comparison
    private var sameStrikeRankings: [OptionRank] {
        allRankings.filter { $0.strike == rank.strike && $0.side == rank.side }
            .sorted { $0.expiry < $1.expiry }
    }

    private var daysToExpiry: Int {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withFullDate, .withDashSeparatorInDate]

        guard let expiryDate = formatter.date(from: rank.expiry) else {
            return 0
        }

        let calendar = Calendar.current
        let days = calendar.dateComponents([.day], from: Date(), to: expiryDate).day ?? 0
        return max(0, days)
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                // Header
                headerSection

                Divider()

                // ML Score Breakdown
                mlBreakdownSection

                Divider()

                // Contract Details
                contractDetailsSection

                Divider()

                // Strike Comparison (same strike, different expiries)
                if sameStrikeRankings.count > 1 {
                    strikeComparisonSection
                    Divider()
                }

                // Greeks & Risk Metrics
                greeksSection
                
                Divider()
                
                // Historical Strike Analysis
                StrikeAnalysisView(
                    symbol: symbol,
                    strike: rank.strike,
                    side: rank.side.rawValue
                )
            }
            .padding(24)
        }
        .frame(width: 700, height: 800)
        .background(Color(nsColor: .windowBackgroundColor))
    }

    // MARK: - Header Section

    private var headerSection: some View {
        VStack(spacing: 12) {
            HStack {
                // Composite Rank badge
                Text("\(rank.compositeScoreDisplay)")
                    .font(.system(size: 48, weight: .bold, design: .rounded))
                    .foregroundColor(rank.compositeColor)

                VStack(alignment: .leading, spacing: 4) {
                    Text("COMPOSITE RANK")
                        .font(.caption)
                        .foregroundStyle(.secondary)

                    Text(compositeLabel)
                        .font(.headline)
                        .foregroundColor(rank.compositeColor)
                }

                Spacer()

                Button("Close") {
                    dismiss()
                }
                .buttonStyle(.bordered)
            }

            // Contract title with signal badges
            HStack {
                Text("\(symbol) $\(String(format: "%.2f", rank.strike)) \(rank.side.rawValue.uppercased())")
                    .font(.title2.bold())

                // Signal badges in header
                ForEach(rank.activeSignals, id: \.self) { signal in
                    signalBadge(signal)
                }

                Spacer()

                Text("Expires \(formattedExpiry)")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
        }
    }

    private var compositeLabel: String {
        if rank.effectiveCompositeRank >= 75 { return "Strong Buy" }
        if rank.effectiveCompositeRank >= 60 { return "Buy" }
        if rank.effectiveCompositeRank >= 45 { return "Hold" }
        return "Weak"
    }

    // MARK: - ML Breakdown Section

    private var mlBreakdownSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Momentum Framework Breakdown")
                .font(.headline)

            Text("Composite Rank: \(rank.compositeScoreDisplay)/100")
                .font(.subheadline)
                .foregroundStyle(.secondary)

            // Signal badges if any
            if rank.hasSignals {
                HStack(spacing: 8) {
                    Text("Signals:")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    ForEach(rank.activeSignals, id: \.self) { signal in
                        signalBadge(signal)
                    }
                }
                .padding(.bottom, 4)
            }

            VStack(spacing: 12) {
                // Momentum Score (40% weight)
                factorRow(
                    name: "Momentum Score",
                    score: (rank.momentumScore ?? 50) / 100,
                    weight: 0.40,
                    description: "Price momentum, volume/OI ratio, OI growth"
                )

                // Value Score (35% weight)
                factorRow(
                    name: "Value Score",
                    score: (rank.valueScore ?? 50) / 100,
                    weight: 0.35,
                    description: "IV Rank, bid-ask spread tightness"
                )

                // Greeks Score (25% weight)
                factorRow(
                    name: "Greeks Score",
                    score: (rank.greeksScore ?? 50) / 100,
                    weight: 0.25,
                    description: "Delta quality, gamma, vega exposure, theta impact"
                )
            }

            Divider()
                .padding(.vertical, 8)

            // Additional metrics
            VStack(alignment: .leading, spacing: 8) {
                Text("Key Metrics")
                    .font(.subheadline.weight(.medium))

                Grid(alignment: .leading, horizontalSpacing: 24, verticalSpacing: 8) {
                    GridRow {
                        metricLabel("IV Rank")
                        metricValue(rank.ivRank.map { "\(Int($0))%" } ?? "—")

                        metricLabel("Spread")
                        metricValue(rank.spreadPct.map { String(format: "%.1f%%", $0) } ?? "—")
                    }

                    GridRow {
                        metricLabel("Vol/OI")
                        metricValue(rank.volOiRatio.map { String(format: "%.2f", $0) } ?? "—")
                    }
                }
            }
        }
    }

    @ViewBuilder
    private func signalBadge(_ signal: String) -> some View {
        let (color, icon) = signalStyle(signal)
        HStack(spacing: 2) {
            Image(systemName: icon)
                .font(.caption2)
            Text(signal)
                .font(.caption2.bold())
        }
        .padding(.horizontal, 5)
        .padding(.vertical, 2)
        .background(color.opacity(0.2))
        .foregroundStyle(color)
        .clipShape(RoundedRectangle(cornerRadius: 4))
    }

    private func signalStyle(_ signal: String) -> (Color, String) {
        switch signal {
        case "BUY":
            return (.green, "checkmark.circle.fill")
        case "DISCOUNT":
            return (.blue, "tag.fill")
        case "RUNNER":
            return (.orange, "flame.fill")
        case "GREEKS":
            return (.purple, "function")
        default:
            return (.gray, "questionmark.circle")
        }
    }

    private func metricLabel(_ text: String) -> some View {
        Text(text)
            .font(.caption)
            .foregroundStyle(.secondary)
            .frame(minWidth: 60, alignment: .leading)
    }

    private func metricValue(_ text: String) -> some View {
        Text(text)
            .font(.caption.weight(.medium))
            .frame(minWidth: 50, alignment: .leading)
    }

    // MARK: - Contract Details Section

    private var contractDetailsSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Contract Details")
                .font(.headline)

            Grid(alignment: .leading, horizontalSpacing: 40, verticalSpacing: 12) {
                GridRow {
                    detailLabel("Strike Price")
                    detailValue("$\(String(format: "%.2f", rank.strike))")

                    detailLabel("Side")
                    detailValue(rank.side.rawValue.uppercased())
                }

                GridRow {
                    detailLabel("Mark Price")
                    detailValue(rank.mark.map { "$\(String(format: "%.2f", $0))" } ?? "—")

                    detailLabel("Bid/Ask")
                    if let bid = rank.bid, let ask = rank.ask {
                        detailValue("$\(String(format: "%.2f", bid)) / $\(String(format: "%.2f", ask))")
                    } else {
                        detailValue("—")
                    }
                }

                GridRow {
                    detailLabel("Volume")
                    detailValue(rank.volume.map { "\($0)" } ?? "—")

                    detailLabel("Open Interest")
                    detailValue(rank.openInterest.map { "\($0)" } ?? "—")
                }

                GridRow {
                    detailLabel("Days to Expiry")
                    detailValue("\(daysToExpiry) days")

                    detailLabel("Expiration Date")
                    detailValue(formattedExpiry)
                }
            }
        }
    }

    // MARK: - Strike Comparison Section

    private var strikeComparisonSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Strike $\(String(format: "%.2f", rank.strike)) Across Expirations")
                .font(.headline)

            Text("Compare this strike across \(sameStrikeRankings.count) different expiration dates")
                .font(.subheadline)
                .foregroundStyle(.secondary)

            VStack(spacing: 8) {
                ForEach(sameStrikeRankings) { rankItem in
                    StrikeComparisonRow(
                        rank: rankItem,
                        isCurrent: rankItem.id == rank.id
                    )
                }
            }
        }
    }

    // MARK: - Greeks Section

    private var greeksSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Greeks & Risk Metrics")
                .font(.headline)

            Grid(alignment: .leading, horizontalSpacing: 40, verticalSpacing: 12) {
                GridRow {
                    greekLabel("Delta")
                    greekValue(rank.delta, format: "%.3f")
                    greekDescription("Price sensitivity")
                }

                GridRow {
                    greekLabel("Gamma")
                    greekValue(rank.gamma, format: "%.4f")
                    greekDescription("Delta acceleration")
                }

                GridRow {
                    greekLabel("Theta")
                    greekValue(rank.theta, format: "%.3f")
                    greekDescription("Time decay per day")
                }

                GridRow {
                    greekLabel("Vega")
                    greekValue(rank.vega, format: "%.3f")
                    greekDescription("IV sensitivity")
                }

                GridRow {
                    greekLabel("IV")
                    greekValue(rank.impliedVol, format: "%.1f%%", multiplier: 100)
                    greekDescription("Implied volatility")
                }
            }
        }
    }

    // MARK: - Helper Views

    private func factorRow(name: String, score: Double, weight: Double, description: String) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(name)
                    .font(.subheadline.weight(.medium))

                Spacer()

                Text("\(Int(score * 100))%")
                    .font(.subheadline.weight(.semibold))
                    .foregroundColor(factorColor(score))

                Text("(weight: \(Int(weight * 100))%)")
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
            }

            // Progress bar
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(Color.secondary.opacity(0.2))

                    RoundedRectangle(cornerRadius: 4)
                        .fill(factorColor(score))
                        .frame(width: geometry.size.width * score)
                }
            }
            .frame(height: 8)

            Text(description)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(.vertical, 4)
    }

    private func detailLabel(_ text: String) -> some View {
        Text(text)
            .font(.subheadline)
            .foregroundStyle(.secondary)
            .frame(minWidth: 120, alignment: .leading)
    }

    private func detailValue(_ text: String) -> some View {
        Text(text)
            .font(.subheadline.weight(.medium))
            .frame(minWidth: 100, alignment: .leading)
    }

    private func greekLabel(_ text: String) -> some View {
        Text(text)
            .font(.subheadline.weight(.medium))
            .frame(minWidth: 80, alignment: .leading)
    }

    private func greekValue(_ value: Double?, format: String, multiplier: Double = 1) -> some View {
        if let value = value {
            Text(String(format: format, value * multiplier))
                .font(.subheadline.monospacedDigit())
                .frame(minWidth: 80, alignment: .leading)
        } else {
            Text("—")
                .font(.subheadline.monospacedDigit())
                .foregroundStyle(.secondary)
                .frame(minWidth: 80, alignment: .leading)
        }
    }

    private func greekDescription(_ text: String) -> some View {
        Text(text)
            .font(.caption)
            .foregroundStyle(.secondary)
    }

    // MARK: - Computed Properties

    private var scoreColor: Color {
        if rank.effectiveCompositeRank >= 90 { return .green }
        if rank.effectiveCompositeRank >= 75 { return .blue }
        if rank.effectiveCompositeRank >= 60 { return .orange }
        return .red
    }

    private var scoreLabel: String {
        if rank.effectiveCompositeRank >= 90 { return "Excellent" }
        if rank.effectiveCompositeRank >= 75 { return "Good" }
        if rank.effectiveCompositeRank >= 60 { return "Fair" }
        return "Poor"
    }

    private var formattedExpiry: String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withFullDate, .withDashSeparatorInDate]

        guard let expiryDate = formatter.date(from: rank.expiry) else {
            return rank.expiry
        }

        let displayFormatter = DateFormatter()
        displayFormatter.dateFormat = "MMM d, yyyy"
        return displayFormatter.string(from: expiryDate)
    }

    private func calculateMoneyness() -> Double {
        // Simplified - in real app would use current stock price
        // This is a placeholder calculation
        guard let delta = rank.delta else { return 0.70 }
        let atm = abs(delta) > 0.45 && abs(delta) < 0.55
        if atm { return 0.95 }

        let itm = (rank.side == .call && delta > 0.55) || (rank.side == .put && delta < -0.55)
        if itm { return 0.85 }

        return 0.70
    }

    private var moneynesDescription: String {
        let moneyness = calculateMoneyness()
        if moneyness > 0.9 { return "Near the money - optimal risk/reward" }
        if moneyness > 0.8 { return "In the money - higher probability" }
        return "Out of the money - higher leverage"
    }

    private var normalizedIV: Double {
        // Placeholder - would calculate based on IV rank
        guard let iv = rank.impliedVol else { return 0.50 }
        return min(1.0, iv / 0.5)
    }

    private var liquidityScore: Double {
        // Simple heuristic based on volume
        guard let volume = rank.volume else { return 0.50 }
        if volume > 1000 { return 0.95 }
        if volume > 500 { return 0.85 }
        if volume > 100 { return 0.70 }
        return 0.50
    }

    private var deltaScore: Double {
        // Optimal delta is around 0.3-0.4 for most strategies
        guard let delta = rank.delta else { return 0.60 }
        let absDelta = abs(delta)
        if absDelta >= 0.3 && absDelta <= 0.4 { return 0.95 }
        if absDelta >= 0.2 && absDelta <= 0.5 { return 0.80 }
        return 0.60
    }

    private var thetaScore: Double {
        // Lower theta decay is better for long positions
        guard let theta = rank.theta else { return 0.60 }
        let absTheta = abs(theta)
        if absTheta < 0.02 { return 0.90 }
        if absTheta < 0.05 { return 0.75 }
        return 0.60
    }

    private func factorColor(_ score: Double) -> Color {
        if score >= 0.85 { return .green }
        if score >= 0.70 { return .blue }
        if score >= 0.50 { return .orange }
        return .red
    }
}

// MARK: - Strike Comparison Row

struct StrikeComparisonRow: View {
    let rank: OptionRank
    let isCurrent: Bool

    private var daysToExpiry: Int {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withFullDate, .withDashSeparatorInDate]

        guard let expiryDate = formatter.date(from: rank.expiry) else {
            return 0
        }

        let calendar = Calendar.current
        let days = calendar.dateComponents([.day], from: Date(), to: expiryDate).day ?? 0
        return max(0, days)
    }

    var body: some View {
        HStack(spacing: 12) {
            // Composite Score badge
            Text("\(rank.compositeScoreDisplay)")
                .font(.system(size: 18, weight: .bold, design: .rounded))
                .foregroundColor(rank.compositeColor)
                .frame(width: 50)

            // Expiry info
            VStack(alignment: .leading, spacing: 2) {
                Text(rank.expiry)
                    .font(.subheadline.weight(.medium))
                Text("\(daysToExpiry) DTE")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .frame(width: 120, alignment: .leading)

            // Mark price
            VStack(alignment: .leading, spacing: 2) {
                if let mark = rank.mark {
                    Text("$\(String(format: "%.2f", mark))")
                        .font(.subheadline.weight(.medium))
                } else {
                    Text("—")
                        .font(.subheadline.weight(.medium))
                        .foregroundStyle(.secondary)
                }
                Text("Mark")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .frame(width: 80, alignment: .leading)

            // IV
            VStack(alignment: .leading, spacing: 2) {
                if let iv = rank.impliedVol {
                    Text(String(format: "%.1f%%", iv * 100))
                        .font(.subheadline.weight(.medium))
                } else {
                    Text("—")
                        .font(.subheadline.weight(.medium))
                        .foregroundStyle(.secondary)
                }
                Text("IV")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .frame(width: 60, alignment: .leading)

            // Delta
            VStack(alignment: .leading, spacing: 2) {
                if let delta = rank.delta {
                    Text(String(format: "%.2f", delta))
                        .font(.subheadline.monospacedDigit())
                } else {
                    Text("—")
                        .font(.subheadline.monospacedDigit())
                        .foregroundStyle(.secondary)
                }
                Text("Δ")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .frame(width: 60, alignment: .leading)

            // Volume
            VStack(alignment: .leading, spacing: 2) {
                if let volume = rank.volume {
                    Text("\(volume)")
                        .font(.subheadline.weight(.medium))
                } else {
                    Text("—")
                        .font(.subheadline.weight(.medium))
                        .foregroundStyle(.secondary)
                }
                Text("Vol")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .frame(width: 70, alignment: .leading)

            Spacer()

            if isCurrent {
                Image(systemName: "checkmark.circle.fill")
                    .foregroundColor(.blue)
                    .font(.title3)
            }
        }
        .padding(12)
        .background(isCurrent ? Color.blue.opacity(0.1) : Color.secondary.opacity(0.05))
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(isCurrent ? Color.blue : Color.clear, lineWidth: 2)
        )
    }
}

#Preview {
    OptionRankDetailView(
        rank: OptionRank(
            id: "preview-1",
            contractSymbol: "CRWD251219P00470000",
            expiry: "2025-12-19",
            strike: 470.0,
            side: .put,
            compositeRank: 82.0,
            momentumScore: 85.0,
            valueScore: 78.0,
            greeksScore: 80.0,
            mlScore: 0.82,
            impliedVol: 0.42,
            ivRank: 65.0,
            spreadPct: 1.2,
            delta: -0.10,
            gamma: 0.005,
            theta: -0.02,
            vega: 0.15,
            rho: nil,
            openInterest: 1200,
            volume: 600,
            volOiRatio: 0.50,
            liquidityConfidence: 0.75,
            bid: 1.45,
            ask: 1.51,
            mark: 1.48,
            lastPrice: 1.47,
            signalDiscount: true,
            signalRunner: false,
            signalGreeks: true,
            signalBuy: true,
            signals: "DISCOUNT,GREEKS,BUY",
            runAt: ISO8601DateFormatter().string(from: Date())
        ),
        symbol: "CRWD",
        allRankings: []
    )
}
