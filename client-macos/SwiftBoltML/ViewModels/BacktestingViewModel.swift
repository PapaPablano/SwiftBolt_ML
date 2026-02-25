import Foundation
import Combine

// #region agent log
private func _e2eLog(_ hypothesisId: String, _ location: String, _ message: String, _ data: [String: Any]) {
    let path = "/Users/ericpeterson/SwiftBolt_ML/.cursor/debug-b8f949.log"
    let payload: [String: Any] = [
        "sessionId": "b8f949", "hypothesisId": hypothesisId, "location": location,
        "message": message, "data": data, "timestamp": Int(Date().timeIntervalSince1970 * 1000)
    ]
    guard let json = try? JSONSerialization.data(withJSONObject: payload),
          let line = String(data: json, encoding: .utf8) else { return }
    let lineData = (line + "\n").data(using: .utf8)!
    let url = URL(fileURLWithPath: path)
    if !FileManager.default.fileExists(atPath: path) { try? lineData.write(to: url); return }
    guard let h = try? FileHandle(forUpdating: url) else { return }
    h.seekToEndOfFile(); h.write(lineData); try? h.close()
}
// #endregion

@MainActor
final class BacktestingViewModel: ObservableObject {
    @Published var backtestResult: BacktestResponse?
    @Published var isLoading = false
    @Published var error: String?
    @Published var jobId: String?
    @Published var jobStatus: BacktestJobStatus = .idle

    /// Polling: interval (seconds) and max polls before timeout (e.g. 2s × 300 = 10 min)
    private let pollIntervalSeconds: UInt64 = 2
    private let maxPolls = 300

    @Published var selectedStrategy: TradingStrategy = .supertrendAI
    @Published var startDate: Date = Calendar.current.date(byAdding: .year, value: -1, to: Date()) ?? Date()
    @Published var endDate: Date = Date()
    @Published var selectedPreset: DateRangePreset?
    @Published var initialCapital: Double = 10000
    @Published var strategyParams: [String: Any] = [:]

    private var cancellables = Set<AnyCancellable>()
    private var pollingTask: Task<Void, Never>?

    var symbol: String?
    var timeframe: String = "d1"
    
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
    
    // MARK: - Data Loading (job-based flow)

    func runBacktest(symbol: String, timeframe: String = "d1") async {
        guard !isLoading else { return }

        let sym = symbol.uppercased()
        self.symbol = sym
        self.timeframe = timeframe
        isLoading = true
        error = nil
        backtestResult = nil
        stopPolling()

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
            // #region agent log
            _e2eLog("A", "BacktestingViewModel.runBacktest:afterQueue", "queue ok", ["jobId": queued.jobId, "status": queued.status])
            // #endregion
            jobId = queued.jobId
            jobStatus = BacktestJobStatus(apiStatus: queued.status)
            let strategyName = selectedStrategy.rawValue
            let capital = initialCapital
            startPolling(jobId: queued.jobId, sym: sym, startDateStr: startDateStr, endDateStr: endDateStr, strategyName: strategyName, initialCapital: capital)
        } catch {
            // #region agent log
            _e2eLog("A", "BacktestingViewModel.runBacktest:catch", "queue failed", ["error": String(describing: error)])
            // #endregion
            self.error = error.localizedDescription
            self.isLoading = false
            jobStatus = .failed
            print("[Backtesting] Error queueing backtest: \(error)")
        }
    }

    private func startPolling(jobId: String, sym: String, startDateStr: String, endDateStr: String, strategyName: String, initialCapital: Double) {
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
                    // #region agent log
                    _e2eLog("B", "BacktestingViewModel.startPolling:poll", "status", ["status": status.status, "hasResult": status.result != nil, "pollCount": pollCount])
                    // #endregion
                    await MainActor.run { self.jobStatus = statusEnum }

                    if statusEnum == .completed, let result = status.result {
                        // #region agent log
                        _e2eLog("C", "BacktestingViewModel.startPolling:beforeFrom", "building display", ["equityCount": result.equityCurve.count, "tradesCount": result.trades.count])
                        // #endregion
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
                            // #region agent log
                            let eqNil = display.equityCurve.filter { $0.dateValue == nil }.count
                            let tradeNil = display.trades.filter { $0.dateValue == nil }.count
                            _e2eLog("D", "BacktestingViewModel.startPolling:afterSet", "result set", ["equityDateNil": eqNil, "tradeDateNil": tradeNil, "totalReturn": display.totalReturn])
                            // #endregion
                        }
                        print("[Backtesting] Backtest complete: \(String(format: "%.2f", display.totalReturn * 100))% return, \(display.metrics.totalTrades) trades")
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
                    // #region agent log
                    _e2eLog("B", "BacktestingViewModel.startPolling:pollCatch", "poll request failed", ["error": String(describing: error), "pollCount": pollCount])
                    // #endregion
                    await MainActor.run { self.error = error.localizedDescription }
                }
            }
            if pollCount >= self.maxPolls {
                // #region agent log
                _e2eLog("B", "BacktestingViewModel.startPolling:timeout", "max polls reached", ["pollCount": pollCount])
                // #endregion
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
        if idle {
            jobStatus = .idle
        }
    }

    private func stopPolling() {
        pollingTask?.cancel()
        pollingTask = nil
    }
    
    func reset() {
        stopPolling()
        backtestResult = nil
        error = nil
        jobId = nil
        jobStatus = .idle
        isLoading = false
    }
    
    // MARK: - Strategy Parameters
    
    func updateStrategyParam(key: String, value: Any) {
        strategyParams[key] = value
    }
    
    func resetStrategyParams() {
        strategyParams = selectedStrategy.defaultParams
    }
}

// MARK: - Color Extension

import SwiftUI

extension Color {
    // Already available in SwiftUI
}
