import Foundation
import Supabase

// MARK: - Data Models

struct PaperPosition: Identifiable, Codable {
    let id: UUID
    let userId: UUID
    let strategyId: UUID
    let symbolId: UUID
    let ticker: String?
    let timeframe: String
    let entryPrice: Double
    var currentPrice: Double?
    let quantity: Int
    let entryTime: Date
    let direction: String // "long" or "short"
    let stopLossPrice: Double?
    let takeProfitPrice: Double?
    let status: String // "open" or "closed"

    var unrealizedPnl: Double? {
        guard let current = currentPrice else { return nil }
        let diff = direction == "long"
            ? (current - entryPrice) * Double(quantity)
            : (entryPrice - current) * Double(quantity)
        return diff
    }

    var unrealizedPnlPct: Double? {
        guard let pnl = unrealizedPnl else { return nil }
        return (pnl / (entryPrice * Double(quantity))) * 100.0
    }

    enum CodingKeys: String, CodingKey {
        case id, timeframe, quantity, direction, status
        case userId = "user_id"
        case strategyId = "strategy_id"
        case symbolId = "symbol_id"
        case ticker
        case entryPrice = "entry_price"
        case currentPrice = "current_price"
        case entryTime = "entry_time"
        case stopLossPrice = "stop_loss_price"
        case takeProfitPrice = "take_profit_price"
    }
}

struct PaperTrade: Identifiable, Codable {
    let id: UUID
    let userId: UUID
    let strategyId: UUID
    let symbolId: UUID
    let ticker: String?
    let timeframe: String
    let entryPrice: Double
    let exitPrice: Double
    let quantity: Int
    let direction: String
    let entryTime: Date
    let exitTime: Date
    let pnl: Double
    let pnlPct: Double
    let tradeReason: String?
    let createdAt: Date?

    enum CodingKeys: String, CodingKey {
        case id, timeframe, quantity, direction, pnl, ticker
        case userId = "user_id"
        case strategyId = "strategy_id"
        case symbolId = "symbol_id"
        case entryPrice = "entry_price"
        case exitPrice = "exit_price"
        case entryTime = "entry_time"
        case exitTime = "exit_time"
        case pnlPct = "pnl_pct"
        case tradeReason = "trade_reason"
        case createdAt = "created_at"
    }
}

struct PositionMetrics {
    let totalTrades: Int
    let winCount: Int
    let lossCount: Int
    let winRate: Double
    let totalPnl: Double
    let openPnl: Double
    let maxDrawdown: Double
    let profitFactor: Double

    static var empty: PositionMetrics {
        PositionMetrics(
            totalTrades: 0, winCount: 0, lossCount: 0,
            winRate: 0, totalPnl: 0, openPnl: 0,
            maxDrawdown: 0, profitFactor: 0
        )
    }
}

// MARK: - Service

@MainActor
final class PaperTradingService: ObservableObject {
    @Published var openPositions: [PaperPosition] = []
    @Published var tradeHistory: [PaperTrade] = []
    @Published var metrics: PositionMetrics = .empty
    @Published var isLoading = false
    @Published var error: String?

    private let supabase = SupabaseService.shared.client
    private var realtimeChannel: RealtimeChannelV2?

    func loadData() async {
        isLoading = true
        error = nil
        defer { isLoading = false }
        async let positions = fetchOpenPositions()
        async let trades = fetchTradeHistory()
        do {
            let (pos, trds) = try await (positions, trades)
            openPositions = pos
            tradeHistory = trds
            metrics = computeMetrics(positions: pos, trades: trds)
        } catch {
            self.error = error.localizedDescription
        }
    }

    func subscribeToPositions() async {
        let channel = supabase.channel("paper_trading_positions")
        realtimeChannel = channel
        let changes = channel.postgresChange(
            AnyAction.self,
            schema: "public",
            table: "paper_trading_positions"
        )
        await channel.subscribe()
        Task { [weak self] in
            for await _ in changes {
                await self?.loadData()
            }
        }
    }

    func unsubscribe() async {
        await realtimeChannel?.unsubscribe()
        realtimeChannel = nil
    }

    // MARK: - Private

    private func fetchOpenPositions() async throws -> [PaperPosition] {
        let response: [PaperPosition] = try await supabase
            .from("paper_trading_positions")
            .select("*")
            .eq("status", value: "open")
            .order("entry_time", ascending: false)
            .execute()
            .value
        return response
    }

    private func fetchTradeHistory() async throws -> [PaperTrade] {
        let response: [PaperTrade] = try await supabase
            .from("paper_trading_trades")
            .select("*")
            .order("exit_time", ascending: false)
            .limit(100)
            .execute()
            .value
        return response
    }

    private func computeMetrics(positions: [PaperPosition], trades: [PaperTrade]) -> PositionMetrics {
        let wins = trades.filter { $0.pnl > 0 }
        let losses = trades.filter { $0.pnl <= 0 }
        let totalPnl = trades.reduce(0) { $0 + $1.pnl }
        let openPnl = positions.compactMap(\.unrealizedPnl).reduce(0, +)
        let winRate = trades.isEmpty ? 0 : Double(wins.count) / Double(trades.count) * 100
        let grossWin = wins.reduce(0) { $0 + $1.pnl }
        let grossLoss = abs(losses.reduce(0) { $0 + $1.pnl })
        let profitFactor = grossLoss == 0 ? (grossWin > 0 ? Double.infinity : 0) : grossWin / grossLoss

        // Simple max drawdown: running peak minus trough
        var peak = 0.0, trough = 0.0, maxDD = 0.0, running = 0.0
        for trade in trades.reversed() {
            running += trade.pnl
            if running > peak { peak = running }
            trough = running - peak
            if trough < maxDD { maxDD = trough }
        }

        return PositionMetrics(
            totalTrades: trades.count,
            winCount: wins.count,
            lossCount: losses.count,
            winRate: winRate,
            totalPnl: totalPnl,
            openPnl: openPnl,
            maxDrawdown: maxDD,
            profitFactor: profitFactor
        )
    }
}
