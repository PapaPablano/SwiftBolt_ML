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
    /// Stored task handle so the subscription loop can be cancelled on re-entry or view disappear.
    private var subscriptionTask: Task<Void, Never>?
    /// Debouncer prevents full reload on every realtime event during burst updates.
    private let reloadDebouncer = Debouncer(frequency: .slow) // 500ms

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
        // Cancel any existing subscription loop before creating a new one.
        subscriptionTask?.cancel()
        await realtimeChannel?.unsubscribe()

        let channel = supabase.channel("paper_trading_positions")
        realtimeChannel = channel

        // Scope subscription to the current user's rows for defense-in-depth
        // (RLS provides server-side enforcement; this is an additional client filter).
        let filter: RealtimePostgresFilter? = supabase.auth.currentUser.map { .eq("user_id", value: $0.id) }
        let changes = channel.postgresChange(
            AnyAction.self,
            schema: "public",
            table: "paper_trading_positions",
            filter: filter
        )
        do {
            try await channel.subscribeWithError()
        } catch {
            self.error = error.localizedDescription
        }

        subscriptionTask = Task { [weak self] in
            for await _ in changes {
                guard !Task.isCancelled else { break }
                await self?.reloadDebouncer.debounce { [weak self] in
                    await self?.loadData()
                }
            }
        }
    }

    func unsubscribe() async {
        subscriptionTask?.cancel()
        subscriptionTask = nil
        await realtimeChannel?.unsubscribe()
        realtimeChannel = nil
    }

    // MARK: - Private

    private func fetchOpenPositions() async throws -> [PaperPosition] {
        // Build filter chain first (eq must precede order/limit on the builder)
        var query = supabase
            .from("paper_trading_positions")
            .select("id,user_id,strategy_id,symbol_id,ticker,timeframe,entry_price,current_price,quantity,entry_time,direction,stop_loss_price,take_profit_price,status")
            .eq("status", value: "open")

        // Client-side user scoping (defense-in-depth alongside RLS)
        if let userId = supabase.auth.currentUser?.id {
            query = query.eq("user_id", value: userId)
        }

        let response: [PaperPosition] = try await query
            .order("entry_time", ascending: false)
            .execute().value
        return response
    }

    private func fetchTradeHistory() async throws -> [PaperTrade] {
        var query = supabase
            .from("paper_trading_trades")
            .select("id,user_id,strategy_id,symbol_id,ticker,timeframe,entry_price,exit_price,quantity,direction,entry_time,exit_time,pnl,pnl_pct,trade_reason,created_at")

        if let userId = supabase.auth.currentUser?.id {
            query = query.eq("user_id", value: userId)
        }

        let response: [PaperTrade] = try await query
            .order("exit_time", ascending: false)
            .limit(100)
            .execute().value
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

        // Max drawdown: running peak minus current equity
        var peak = 0.0, maxDD = 0.0, running = 0.0
        for trade in trades.reversed() {
            running += trade.pnl
            if running > peak { peak = running }
            let drawdown = running - peak
            if drawdown < maxDD { maxDD = drawdown }
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
