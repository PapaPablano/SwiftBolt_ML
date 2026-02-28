import SwiftUI

// MARK: - Main View

struct PaperTradingDashboardView: View {
    @StateObject private var service = PaperTradingService()

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                // TOP TIER: Key metrics
                MetricsGridView(metrics: service.metrics)

                Divider()

                // MIDDLE TIER: Open positions
                SectionHeaderView(
                    title: "Open Positions",
                    count: service.openPositions.count,
                    systemImage: "arrow.up.arrow.down.circle"
                )
                if service.openPositions.isEmpty {
                    EmptyRowView(message: "No open positions")
                } else {
                    OpenPositionsTableView(positions: service.openPositions)
                }

                Divider()

                // BOTTOM TIER: Trade history
                SectionHeaderView(
                    title: "Trade History",
                    count: service.tradeHistory.count,
                    systemImage: "clock.arrow.trianglehead.counterclockwise.rotate.90"
                )
                if service.tradeHistory.isEmpty {
                    EmptyRowView(message: "No closed trades yet")
                } else {
                    TradeHistoryTableView(trades: service.tradeHistory)
                }
            }
            .padding()
        }
        .navigationTitle("Paper Trading")
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button {
                    Task { await service.loadData() }
                } label: {
                    Label("Refresh", systemImage: "arrow.clockwise")
                }
                .disabled(service.isLoading)
            }
        }
        .overlay {
            if service.isLoading {
                ProgressView("Loading...")
                    .padding()
                    .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 10))
            }
        }
        .alert("Error", isPresented: Binding(
            get: { service.error != nil },
            set: { if !$0 { service.error = nil } }
        )) {
            Button("OK") { service.error = nil }
        } message: {
            Text(service.error ?? "")
        }
        .task {
            await service.loadData()
            await service.subscribeToPositions()
        }
        .onDisappear {
            Task { await service.unsubscribe() }
        }
    }
}

// MARK: - Metrics Grid

private struct MetricsGridView: View {
    let metrics: PositionMetrics

    private let columns = Array(repeating: GridItem(.flexible(), spacing: 12), count: 4)

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Performance Overview")
                .font(.headline)
            LazyVGrid(columns: columns, spacing: 12) {
                MetricCard(label: "Total P&L", value: formatCurrency(metrics.totalPnl), color: pnlColor(metrics.totalPnl))
                MetricCard(label: "Open P&L", value: formatCurrency(metrics.openPnl), color: pnlColor(metrics.openPnl))
                MetricCard(label: "Win Rate", value: String(format: "%.1f%%", metrics.winRate), color: .primary)
                MetricCard(label: "Total Trades", value: "\(metrics.totalTrades)", color: .primary)
                MetricCard(label: "Wins", value: "\(metrics.winCount)", color: .green)
                MetricCard(label: "Losses", value: "\(metrics.lossCount)", color: .red)
                MetricCard(label: "Profit Factor", value: formatFactor(metrics.profitFactor), color: .primary)
                MetricCard(label: "Max Drawdown", value: formatCurrency(metrics.maxDrawdown), color: metrics.maxDrawdown < 0 ? .red : .secondary)
            }
        }
    }
}

private struct MetricCard: View {
    let label: String
    let value: String
    let color: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label)
                .font(.caption)
                .foregroundStyle(.secondary)
            Text(value)
                .font(.title3.bold())
                .foregroundStyle(color)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(10)
        .background(.quaternary, in: RoundedRectangle(cornerRadius: 8))
    }
}

// MARK: - Open Positions Table

private struct OpenPositionsTableView: View {
    let positions: [PaperPosition]

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Text("Symbol").frame(width: 80, alignment: .leading)
                Text("Direction").frame(width: 70, alignment: .leading)
                Text("Qty").frame(width: 50, alignment: .trailing)
                Text("Entry").frame(width: 80, alignment: .trailing)
                Text("Current").frame(width: 80, alignment: .trailing)
                Text("P&L").frame(width: 90, alignment: .trailing)
                Text("P&L %").frame(width: 80, alignment: .trailing)
                Text("SL").frame(width: 70, alignment: .trailing)
                Text("TP").frame(width: 70, alignment: .trailing)
            }
            .font(.caption.bold())
            .foregroundStyle(.secondary)
            .padding(.horizontal, 8)
            .padding(.vertical, 6)
            .background(.quaternary)

            Divider()

            ForEach(positions) { position in
                PositionRowView(position: position)
                Divider()
            }
        }
        .background(.background)
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .overlay(RoundedRectangle(cornerRadius: 8).stroke(.separator, lineWidth: 0.5))
    }
}

private struct PositionRowView: View {
    let position: PaperPosition

    var body: some View {
        HStack {
            Text(position.ticker ?? "—")
                .font(.system(.body, design: .monospaced).bold())
                .frame(width: 80, alignment: .leading)

            DirectionBadge(direction: position.direction)
                .frame(width: 70, alignment: .leading)

            Text("\(position.quantity)")
                .frame(width: 50, alignment: .trailing)

            Text(formatPrice(position.entryPrice))
                .frame(width: 80, alignment: .trailing)

            Text(position.currentPrice.map(formatPrice) ?? "—")
                .frame(width: 80, alignment: .trailing)

            Text(position.unrealizedPnl.map(formatCurrency) ?? "—")
                .foregroundStyle(pnlColor(position.unrealizedPnl ?? 0))
                .frame(width: 90, alignment: .trailing)

            Text(position.unrealizedPnlPct.map { String(format: "%.2f%%", $0) } ?? "—")
                .foregroundStyle(pnlColor(position.unrealizedPnlPct ?? 0))
                .frame(width: 80, alignment: .trailing)

            Text(position.stopLossPrice.map(formatPrice) ?? "—")
                .foregroundStyle(.red.opacity(0.8))
                .frame(width: 70, alignment: .trailing)

            Text(position.takeProfitPrice.map(formatPrice) ?? "—")
                .foregroundStyle(.green.opacity(0.8))
                .frame(width: 70, alignment: .trailing)
        }
        .font(.system(.caption, design: .monospaced))
        .padding(.horizontal, 8)
        .padding(.vertical, 6)
    }
}

// MARK: - Trade History Table

private struct TradeHistoryTableView: View {
    let trades: [PaperTrade]

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Text("Symbol").frame(width: 80, alignment: .leading)
                Text("Dir").frame(width: 50, alignment: .leading)
                Text("Qty").frame(width: 50, alignment: .trailing)
                Text("Entry").frame(width: 80, alignment: .trailing)
                Text("Exit").frame(width: 80, alignment: .trailing)
                Text("P&L").frame(width: 90, alignment: .trailing)
                Text("P&L %").frame(width: 80, alignment: .trailing)
                Text("Reason").frame(width: 100, alignment: .trailing)
                Text("Duration").frame(width: 80, alignment: .trailing)
            }
            .font(.caption.bold())
            .foregroundStyle(.secondary)
            .padding(.horizontal, 8)
            .padding(.vertical, 6)
            .background(.quaternary)

            Divider()

            ForEach(trades) { trade in
                TradeRowView(trade: trade)
                Divider()
            }
        }
        .background(.background)
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .overlay(RoundedRectangle(cornerRadius: 8).stroke(.separator, lineWidth: 0.5))
    }
}

private struct TradeRowView: View {
    let trade: PaperTrade

    private var duration: String {
        let interval = trade.exitTime.timeIntervalSince(trade.entryTime)
        let hours = Int(interval) / 3600
        let minutes = (Int(interval) % 3600) / 60
        return hours > 0 ? "\(hours)h \(minutes)m" : "\(minutes)m"
    }

    var body: some View {
        HStack {
            Text(trade.ticker ?? "—")
                .font(.system(.body, design: .monospaced).bold())
                .frame(width: 80, alignment: .leading)

            DirectionBadge(direction: trade.direction)
                .frame(width: 50, alignment: .leading)

            Text("\(trade.quantity)")
                .frame(width: 50, alignment: .trailing)

            Text(formatPrice(trade.entryPrice))
                .frame(width: 80, alignment: .trailing)

            Text(formatPrice(trade.exitPrice))
                .frame(width: 80, alignment: .trailing)

            Text(formatCurrency(trade.pnl))
                .foregroundStyle(pnlColor(trade.pnl))
                .frame(width: 90, alignment: .trailing)

            Text(String(format: "%.2f%%", trade.pnlPct))
                .foregroundStyle(pnlColor(trade.pnlPct))
                .frame(width: 80, alignment: .trailing)

            Text(trade.tradeReason ?? "—")
                .font(.caption)
                .foregroundStyle(.secondary)
                .lineLimit(1)
                .frame(width: 100, alignment: .trailing)

            Text(duration)
                .font(.caption)
                .foregroundStyle(.secondary)
                .frame(width: 80, alignment: .trailing)
        }
        .font(.system(.caption, design: .monospaced))
        .padding(.horizontal, 8)
        .padding(.vertical, 6)
    }
}

// MARK: - Supporting Views

private struct DirectionBadge: View {
    let direction: String

    var body: some View {
        Text(direction.uppercased())
            .font(.caption2.bold())
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(direction == "long" ? Color.green.opacity(0.15) : Color.red.opacity(0.15))
            .foregroundStyle(direction == "long" ? .green : .red)
            .clipShape(Capsule())
    }
}

private struct SectionHeaderView: View {
    let title: String
    let count: Int
    let systemImage: String

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: systemImage)
                .foregroundStyle(.secondary)
            Text(title)
                .font(.headline)
            Text("(\(count))")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
    }
}

private struct EmptyRowView: View {
    let message: String

    var body: some View {
        Text(message)
            .foregroundStyle(.tertiary)
            .frame(maxWidth: .infinity, alignment: .center)
            .padding()
            .background(.quaternary, in: RoundedRectangle(cornerRadius: 8))
    }
}

// MARK: - Formatters

private func formatCurrency(_ value: Double) -> String {
    let formatter = NumberFormatter()
    formatter.numberStyle = .currency
    formatter.currencyCode = "USD"
    formatter.maximumFractionDigits = 2
    return formatter.string(from: NSNumber(value: value)) ?? "$0.00"
}

private func formatPrice(_ value: Double) -> String {
    String(format: "$%.2f", value)
}

private func formatFactor(_ value: Double) -> String {
    value.isInfinite ? "∞" : String(format: "%.2f", value)
}

private func pnlColor(_ value: Double) -> Color {
    if value > 0 { return .green }
    if value < 0 { return .red }
    return .primary
}

#Preview {
    PaperTradingDashboardView()
}
