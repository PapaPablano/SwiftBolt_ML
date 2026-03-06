import SwiftUI

// MARK: - File-level Formatters (avoid per-cell allocation)

private let currencyFormatter: NumberFormatter = {
    let f = NumberFormatter()
    f.numberStyle = .currency
    f.locale = Locale(identifier: "en_US")
    f.minimumFractionDigits = 2
    f.maximumFractionDigits = 2
    return f
}()

private let percentFormatter: NumberFormatter = {
    let f = NumberFormatter()
    f.numberStyle = .percent
    f.minimumFractionDigits = 2
    f.maximumFractionDigits = 2
    f.multiplier = 100
    return f
}()

private let decimalFormatter: NumberFormatter = {
    let f = NumberFormatter()
    f.numberStyle = .decimal
    f.minimumFractionDigits = 2
    f.maximumFractionDigits = 2
    return f
}()

// MARK: - Backtest Results View

/// Displays backtest results: summary stats grid + scrollable trade log.
struct BacktestResultsView: View {
    let result: BacktestResponse

    @State private var sortOrder = [KeyPathComparator(\BacktestResponse.Trade.date)]
    @State private var selectedTab = 0 // 0 = Summary, 1 = Trades

    var body: some View {
        VStack(spacing: 0) {
            // Tab selector
            Picker("", selection: $selectedTab) {
                Text("Summary").tag(0)
                Text("Trade Log (\(result.trades.count))").tag(1)
            }
            .pickerStyle(.segmented)
            .padding(.horizontal, 16)
            .padding(.vertical, 8)

            Divider()

            if selectedTab == 0 {
                summaryView
            } else {
                tradeLogView
            }
        }
    }

    // MARK: - Summary

    private var summaryView: some View {
        ScrollView {
            VStack(spacing: 16) {
                // Top-level P&L banner
                HStack(spacing: 24) {
                    StatCard(
                        title: "Total Return",
                        value: formatPercent(result.totalReturn),
                        color: result.totalReturn >= 0 ? .green : .red,
                        large: true
                    )
                    StatCard(
                        title: "Final Value",
                        value: formatCurrency(result.finalValue),
                        color: .primary,
                        large: true
                    )
                    StatCard(
                        title: "Initial Capital",
                        value: formatCurrency(result.initialCapital),
                        color: .secondary,
                        large: true
                    )
                }

                Divider()

                // Metrics grid
                LazyVGrid(columns: [
                    GridItem(.flexible()),
                    GridItem(.flexible()),
                    GridItem(.flexible()),
                    GridItem(.flexible())
                ], spacing: 12) {
                    StatCard(title: "Total Trades", value: "\(result.metrics.totalTrades)", color: .primary)
                    StatCard(title: "Win Rate", value: formatPercent(result.metrics.winRate), color: winRateColor)
                    StatCard(title: "Profit Factor", value: formatDecimal(result.metrics.profitFactor), color: profitFactorColor)
                    StatCard(title: "Sharpe Ratio", value: formatDecimal(result.metrics.sharpeRatio), color: sharpeColor)
                    StatCard(title: "Max Drawdown", value: formatPercent(result.metrics.maxDrawdown), color: .red)
                    StatCard(title: "Avg Trade", value: formatPercent(result.metrics.averageTrade), color: avgTradeColor)
                    StatCard(title: "CAGR", value: formatPercent(result.metrics.cagr), color: .primary)
                    StatCard(title: "Bars Used", value: "\(result.barsUsed)", color: .secondary)
                }

                // Period info
                HStack {
                    Label(result.period.start, systemImage: "calendar")
                    Text("to")
                        .foregroundStyle(.secondary)
                    Text(result.period.end)
                    Spacer()
                    Label(result.strategy, systemImage: "gearshape.2")
                        .foregroundStyle(.secondary)
                }
                .font(.caption)
                .foregroundStyle(.secondary)
                .padding(.top, 4)
            }
            .padding(16)
        }
    }

    // MARK: - Trade Log

    private var tradeLogView: some View {
        Table(result.trades, sortOrder: $sortOrder) {
            TableColumn("Date", value: \.date) { trade in
                Text(trade.date)
                    .font(.system(size: 12, design: .monospaced))
            }
            .width(min: 100, ideal: 130)

            TableColumn("Action") { trade in
                HStack(spacing: 4) {
                    Circle()
                        .fill(trade.action.lowercased() == "buy" ? Color.green : Color.red)
                        .frame(width: 8, height: 8)
                    Text(trade.action.uppercased())
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundStyle(trade.action.lowercased() == "buy" ? .green : .red)
                }
            }
            .width(min: 60, ideal: 80)

            TableColumn("Qty") { trade in
                Text("\(trade.quantity)")
                    .font(.system(size: 12, design: .monospaced))
            }
            .width(min: 40, ideal: 60)

            TableColumn("Price") { trade in
                Text(formatCurrency(trade.price))
                    .font(.system(size: 12, design: .monospaced))
            }
            .width(min: 80, ideal: 100)

            TableColumn("P&L") { trade in
                if let pnl = trade.pnl {
                    Text(formatCurrency(pnl))
                        .font(.system(size: 12, weight: .medium, design: .monospaced))
                        .foregroundStyle(pnl >= 0 ? .green : .red)
                } else {
                    Text("—")
                        .foregroundStyle(.tertiary)
                }
            }
            .width(min: 80, ideal: 100)
        }
        .tableStyle(.bordered)
    }

    // MARK: - Formatting Helpers

    private func formatCurrency(_ value: Double) -> String {
        currencyFormatter.string(from: NSNumber(value: value)) ?? "$\(value)"
    }

    private func formatPercent(_ value: Double?) -> String {
        guard let value else { return "—" }
        return percentFormatter.string(from: NSNumber(value: value)) ?? "\(value)%"
    }

    private func formatDecimal(_ value: Double?) -> String {
        guard let value else { return "—" }
        return decimalFormatter.string(from: NSNumber(value: value)) ?? "\(value)"
    }

    // MARK: - Color Helpers

    private var winRateColor: Color {
        guard let wr = result.metrics.winRate else { return .secondary }
        return wr >= 0.5 ? .green : .orange
    }

    private var profitFactorColor: Color {
        guard let pf = result.metrics.profitFactor else { return .secondary }
        return pf >= 1.0 ? .green : .red
    }

    private var sharpeColor: Color {
        guard let sr = result.metrics.sharpeRatio else { return .secondary }
        if sr >= 1.0 { return .green }
        if sr >= 0 { return .orange }
        return .red
    }

    private var avgTradeColor: Color {
        guard let at = result.metrics.averageTrade else { return .secondary }
        return at >= 0 ? .green : .red
    }
}

// MARK: - Stat Card

private struct StatCard: View {
    let title: String
    let value: String
    let color: Color
    var large: Bool = false

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.caption)
                .foregroundStyle(.secondary)
            Text(value)
                .font(large ? .system(size: 20, weight: .bold, design: .rounded) : .system(size: 15, weight: .semibold, design: .rounded))
                .foregroundStyle(color)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(Color(.controlBackgroundColor))
        .cornerRadius(8)
    }
}
