import Foundation
import Combine
import SwiftUI
import os.log

@MainActor
final class BacktestingViewModel: ObservableObject {
    @Published var backtestResult: BacktestResponse?
    @Published var isLoading = false
    @Published var error: String?
    @Published var jobId: String?
    @Published var jobStatus: BacktestJobStatus = .idle

    /// Polling: interval (seconds) and max polls before timeout (e.g. 2s x 300 = 10 min)
    private let pollIntervalSeconds: UInt64 = 2
    private let maxPolls = 300

    @Published var selectedStrategy: TradingStrategy = .supertrendAI
    @Published var startDate: Date = Calendar.current.date(byAdding: .year, value: -1, to: Date()) ?? Date()
    @Published var endDate: Date = Date()
    @Published var selectedPreset: DateRangePreset?
    @Published var initialCapital: Double = 10000
    @Published var strategyParams: [String: Any] = [:]

    /// Incremented on each new backtest to prevent stale results from overlapping runs.
    @Published private(set) var backtestGeneration: Int = 0

    /// Elapsed seconds since backtest started (for UI display).
    @Published var elapsedSeconds: Int = 0

    private var cancellables = Set<AnyCancellable>()
    private var pollingTask: Task<Void, Never>?
    private var timerTask: Task<Void, Never>?

    var symbol: String?
    var timeframe: String = "d1"

    private static let logger = Logger(subsystem: "com.swiftboltml", category: "BacktestingViewModel")

    // MARK: - Computed Properties

    var hasResults: Bool {
        backtestResult != nil
    }

    var formattedReturn: String {
        guard let result = backtestResult else { return "—" }
        let sign = result.totalReturn >= 0 ? "+" : ""
        return "\(sign)\(String(format: "%.2f", result.totalReturn * 100))%"
    }

    var returnColor: Color {
        guard let result = backtestResult else { return .gray }
        return result.totalReturn >= 0 ? .green : .red
    }

    // MARK: - Preset Handling

    func applyPreset(_ preset: DateRangePreset) {
        selectedPreset = preset
        if let range = preset.dateRange {
            startDate = range.start
            endDate = range.end
        }
    }

    func clearPreset() {
        selectedPreset = nil
    }

    // MARK: - Strategy Backtest (new: uses BacktestService with exponential backoff)

    /// Run a backtest for a custom strategy config via BacktestService.
    /// Posts `.backtestTradesUpdated` notification on completion with symbol guard data.
    func runStrategyBacktest(strategyConfig: StrategyConfig, symbol: String, startDate: Date, endDate: Date) async {
        guard !isLoading else { return }

        let sym = symbol.uppercased()
        self.symbol = sym
        isLoading = true
        error = nil
        backtestResult = nil
        stopPolling()
        backtestGeneration += 1
        let generation = backtestGeneration
        elapsedSeconds = 0
        startTimer()

        let dateFormatter = DateFormatter()
        dateFormatter.dateFormat = "yyyy-MM-dd"
        dateFormatter.locale = Locale(identifier: "en_US_POSIX")
        let startDateStr = dateFormatter.string(from: startDate)
        let endDateStr = dateFormatter.string(from: endDate)

        do {
            let jid = try await BacktestService.shared.submitBacktest(
                symbol: sym,
                strategyConfig: strategyConfig,
                startDate: startDateStr,
                endDate: endDateStr,
                initialCapital: initialCapital
            )
            jobId = jid
            jobStatus = .pending

            // Poll with exponential backoff
            pollingTask?.cancel()
            pollingTask = Task { [weak self] in
                guard let self else { return }
                do {
                    let result = try await BacktestService.shared.pollBacktest(jobId: jid)

                    // Check generation to prevent stale results
                    guard self.backtestGeneration == generation else {
                        #if DEBUG
                        Self.logger.debug("Stale backtest result (gen \(generation) != \(self.backtestGeneration)), discarding")
                        #endif
                        return
                    }

                    let display = BacktestResponse.from(
                        result: result,
                        symbol: sym,
                        strategy: "custom",
                        startDate: startDateStr,
                        endDate: endDateStr,
                        initialCapital: self.initialCapital
                    )

                    self.backtestResult = display
                    self.jobStatus = .completed
                    self.finishPolling(idle: false)

                    // Convert to [[String: Any]] so WebChartView can cast it correctly.
                    // display.trades is [BacktestResponse.Trade] (a struct), not [[String: Any]].
                    let tradesPayload: [[String: Any]] = display.trades.map { trade in
                        var dict: [String: Any] = [
                            "date": trade.date,
                            "symbol": trade.symbol,
                            "action": trade.action,
                            "quantity": trade.quantity,
                            "price": trade.price
                        ]
                        if let v = trade.pnl { dict["pnl"] = v }
                        if let v = trade.entryPrice { dict["entryPrice"] = v }
                        if let v = trade.exitPrice { dict["exitPrice"] = v }
                        if let v = trade.duration { dict["duration"] = v }
                        if let v = trade.fees { dict["fees"] = v }
                        return dict
                    }
                    // Post notification for chart overlay with symbol + generation guard data
                    NotificationCenter.default.post(
                        name: .backtestTradesUpdated,
                        object: nil,
                        userInfo: [
                            "trades": tradesPayload,
                            "symbol": sym,
                            "generation": generation
                        ]
                    )

                    #if DEBUG
                    Self.logger.info("Strategy backtest complete: \(String(format: "%.2f", display.totalReturn * 100))% return, \(display.metrics.totalTrades) trades")
                    #endif
                } catch is CancellationError {
                    self.finishPolling(idle: true)
                } catch {
                    self.error = error.localizedDescription
                    self.jobStatus = .failed
                    self.finishPolling(idle: false)
                }
            }
        } catch {
            self.error = error.localizedDescription
            self.isLoading = false
            jobStatus = .failed
            #if DEBUG
            Self.logger.error("Strategy backtest submit failed: \(error)")
            #endif
        }
    }

    // MARK: - Preset Strategy Backtest (existing: uses APIClient)

    func runBacktest(symbol: String, timeframe: String = "d1") async {
        guard !isLoading else { return }

        let sym = symbol.uppercased()
        self.symbol = sym
        self.timeframe = timeframe
        isLoading = true
        error = nil
        backtestResult = nil
        stopPolling()
        backtestGeneration += 1
        elapsedSeconds = 0
        startTimer()

        let dateFormatter = DateFormatter()
        dateFormatter.dateFormat = "yyyy-MM-dd"
        let startDateStr = dateFormatter.string(from: startDate)
        let endDateStr = dateFormatter.string(from: endDate)

        var params = strategyParams
        if params.isEmpty {
            params = selectedStrategy.defaultParams
        }

        let request = BacktestRequest(
            symbol: sym,
            strategy: selectedStrategy.rawValue,
            startDate: startDateStr,
            endDate: endDateStr,
            timeframe: timeframe,
            initialCapital: initialCapital,
            params: params.isEmpty ? nil : params
        )

        do {
            let queued = try await APIClient.shared.queueBacktestJob(request: request)
            jobId = queued.jobId
            jobStatus = BacktestJobStatus(apiStatus: queued.status)
            let strategyName = selectedStrategy.rawValue
            let capital = initialCapital
            startPolling(jobId: queued.jobId, sym: sym, startDateStr: startDateStr, endDateStr: endDateStr, strategyName: strategyName, initialCapital: capital)
        } catch {
            self.error = error.localizedDescription
            self.isLoading = false
            jobStatus = .failed
            #if DEBUG
            print("[Backtesting] Error queueing backtest: \(error)")
            #endif
        }
    }

    private func startPolling(jobId: String, sym: String, startDateStr: String, endDateStr: String, strategyName: String, initialCapital: Double) {
        let generation = backtestGeneration
        pollingTask?.cancel()
        pollingTask = Task { [weak self] in
            guard let self else { return }
            let pollIntervalNs = self.pollIntervalSeconds * 1_000_000_000
            var pollCount = 0
            while !Task.isCancelled && pollCount < self.maxPolls {
                try? await Task.sleep(nanoseconds: pollIntervalNs)
                guard !Task.isCancelled else {
                    self.finishPolling(idle: true)
                    return
                }
                pollCount += 1

                do {
                    let status = try await APIClient.shared.getBacktestJobStatus(jobId: jobId)
                    let statusEnum = BacktestJobStatus(apiStatus: status.status)
                    await MainActor.run { self.jobStatus = statusEnum }

                    if statusEnum == .completed, let result = status.result {
                        guard self.backtestGeneration == generation else { return }
                        let display = BacktestResponse.from(
                            result: result,
                            symbol: sym,
                            strategy: strategyName,
                            startDate: startDateStr,
                            endDate: endDateStr,
                            initialCapital: initialCapital
                        )
                        await MainActor.run {
                            self.backtestResult = display
                            self.jobStatus = .completed
                            self.finishPolling(idle: false)
                        }

                        // Convert to [[String: Any]] so WebChartView can cast it correctly.
                        // display.trades is [BacktestResponse.Trade] (a struct), not [[String: Any]].
                        let tradesPayload: [[String: Any]] = display.trades.map { trade in
                            var dict: [String: Any] = [
                                "date": trade.date,
                                "symbol": trade.symbol,
                                "action": trade.action,
                                "quantity": trade.quantity,
                                "price": trade.price
                            ]
                            if let v = trade.pnl { dict["pnl"] = v }
                            if let v = trade.entryPrice { dict["entryPrice"] = v }
                            if let v = trade.exitPrice { dict["exitPrice"] = v }
                            if let v = trade.duration { dict["duration"] = v }
                            if let v = trade.fees { dict["fees"] = v }
                            return dict
                        }
                        NotificationCenter.default.post(
                            name: .backtestTradesUpdated,
                            object: nil,
                            userInfo: [
                                "trades": tradesPayload,
                                "symbol": sym,
                                "generation": generation
                            ]
                        )

                        #if DEBUG
                        Self.logger.info("Backtest complete: \(String(format: "%.2f", display.totalReturn * 100))% return, \(display.metrics.totalTrades) trades")
                        #endif
                        return
                    } else if statusEnum == .failed {
                        await MainActor.run {
                            self.error = status.error ?? "Backtest failed"
                            self.jobStatus = .failed
                            self.finishPolling(idle: false)
                        }
                        return
                    }
                } catch {
                    await MainActor.run { self.error = error.localizedDescription }
                }
            }
            if pollCount >= self.maxPolls {
                await MainActor.run {
                    self.error = "Backtest timed out"
                    self.jobStatus = .failed
                    self.finishPolling(idle: false)
                }
            }
        }
    }

    private func finishPolling(idle: Bool) {
        isLoading = false
        pollingTask?.cancel()
        pollingTask = nil
        timerTask?.cancel()
        timerTask = nil
        if idle {
            jobStatus = .idle
        }
    }

    private func stopPolling() {
        pollingTask?.cancel()
        pollingTask = nil
        timerTask?.cancel()
        timerTask = nil
    }

    private func startTimer() {
        timerTask?.cancel()
        timerTask = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(1))
                guard !Task.isCancelled, let self else { return }
                self.elapsedSeconds += 1
            }
        }
    }

    func reset() {
        stopPolling()
        backtestResult = nil
        error = nil
        jobId = nil
        jobStatus = .idle
        isLoading = false
        elapsedSeconds = 0
    }

    // MARK: - Strategy Parameters

    func updateStrategyParam(key: String, value: Any) {
        strategyParams[key] = value
    }

    func resetStrategyParams() {
        strategyParams = selectedStrategy.defaultParams
    }
}
