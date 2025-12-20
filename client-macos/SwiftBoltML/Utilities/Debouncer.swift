import Foundation
import Combine

// MARK: - Update Frequency Specification

/// Debounce specification for different update types.
/// Use these to prevent CPU spikes from high-frequency updates.
enum UpdateFrequency {
    case realtime      // No debounce (use sparingly)
    case fast          // 100ms - UI interactions, search input
    case normal        // 250ms - Data updates, price changes
    case slow          // 500ms - Heavy computations, indicator recalc
    case lazy          // 1000ms - Background tasks, reconnection

    var interval: TimeInterval {
        switch self {
        case .realtime: return 0
        case .fast: return 0.1
        case .normal: return 0.25
        case .slow: return 0.5
        case .lazy: return 1.0
        }
    }

    var nanoseconds: UInt64 {
        UInt64(interval * 1_000_000_000)
    }
}

// MARK: - Debouncer

/// Thread-safe debouncer for high-frequency events.
/// Waits for a pause in events before executing the action.
///
/// Use cases:
/// - Search input (wait for user to stop typing)
/// - Price updates (batch rapid updates)
/// - Window resize (wait for resize to finish)
actor Debouncer {
    private var task: Task<Void, Never>?
    private let interval: TimeInterval

    init(frequency: UpdateFrequency = .normal) {
        self.interval = frequency.interval
    }

    init(interval: TimeInterval) {
        self.interval = interval
    }

    /// Debounce an action. Cancels any pending action and schedules a new one.
    func debounce(action: @escaping @Sendable () async -> Void) {
        task?.cancel()
        task = Task {
            do {
                try await Task.sleep(nanoseconds: UInt64(interval * 1_000_000_000))
                guard !Task.isCancelled else { return }
                await action()
            } catch {
                // Task was cancelled, do nothing
            }
        }
    }

    /// Cancel any pending debounced action.
    func cancel() {
        task?.cancel()
        task = nil
    }
}

// MARK: - Throttler

/// Thread-safe throttler for rate-limiting events.
/// Ensures minimum interval between executions.
///
/// Use cases:
/// - API calls (prevent rate limiting)
/// - WebSocket reconnection (prevent connection spam)
/// - Heavy computations (limit frequency)
actor Throttler {
    private var lastExecution: Date = .distantPast
    private let interval: TimeInterval
    private var pendingTask: Task<Void, Never>?

    init(frequency: UpdateFrequency = .normal) {
        self.interval = frequency.interval
    }

    init(interval: TimeInterval) {
        self.interval = interval
    }

    /// Throttle an action. Executes immediately if enough time has passed,
    /// otherwise schedules for the next available slot.
    func throttle(action: @escaping @Sendable () async -> Void) async {
        let now = Date()
        let elapsed = now.timeIntervalSince(lastExecution)

        if elapsed >= interval {
            lastExecution = now
            await action()
        }
    }

    /// Throttle with trailing edge - ensures the last call is always executed.
    func throttleWithTrailing(action: @escaping @Sendable () async -> Void) {
        pendingTask?.cancel()

        let now = Date()
        let elapsed = now.timeIntervalSince(lastExecution)

        if elapsed >= interval {
            lastExecution = now
            Task {
                await action()
            }
        } else {
            // Schedule for trailing edge
            let delay = interval - elapsed
            pendingTask = Task {
                do {
                    try await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
                    guard !Task.isCancelled else { return }
                    self.lastExecution = Date()
                    await action()
                } catch {
                    // Task was cancelled
                }
            }
        }
    }
}

// MARK: - Combine Extensions

extension Publisher {
    /// Debounce publisher emissions with specified frequency.
    func debounce(frequency: UpdateFrequency, scheduler: some Scheduler) -> Publishers.Debounce<Self, some Scheduler> {
        debounce(for: .seconds(frequency.interval), scheduler: scheduler)
    }

    /// Throttle publisher emissions with specified frequency.
    func throttle(frequency: UpdateFrequency, scheduler: some Scheduler, latest: Bool = true) -> Publishers.Throttle<Self, some Scheduler> {
        throttle(for: .seconds(frequency.interval), scheduler: scheduler, latest: latest)
    }
}

// MARK: - Debounce Specification Table
/*
 | Component      | Event Type        | Frequency | Interval | Rationale                    |
 |----------------|-------------------|-----------|----------|------------------------------|
 | ChartView      | Price updates     | .normal   | 250ms    | Balance responsiveness/CPU   |
 | ChartView      | Indicator recalc  | .slow     | 500ms    | Heavy computation            |
 | SearchBar      | Text input        | .fast     | 100ms    | Responsive autocomplete      |
 | WatchlistView  | Reorder           | .normal   | 250ms    | Prevent rapid saves          |
 | OptionsTable   | Sort/filter       | .fast     | 100ms    | Quick UI response            |
 | WebSocket      | Reconnect         | .lazy     | 1000ms   | Prevent connection spam      |
 | API Calls      | Rate limiting     | .slow     | 500ms    | Respect API limits           |
 */
