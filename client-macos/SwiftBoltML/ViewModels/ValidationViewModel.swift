import Foundation
import Combine

@MainActor
final class ValidationViewModel: ObservableObject {
    @Published private(set) var symbol: String?
    @Published var validator: UnifiedValidator?
    @Published var isLoading = false
    @Published var error: String?
    @Published var isOffline = false
    @Published var lastSyncTime: Date?
    @Published var weights: ValidationWeights {
        didSet {
            weights.save()
            applyWeightsToCurrentValidator()
        }
    }

    private let pollInterval: TimeInterval = 300
    private let cacheDuration: TimeInterval = 300
    private var pollTask: Task<Void, Never>?
    private var refreshTask: Task<Void, Never>?
    private var networkCancellable: AnyCancellable?
    private let networkMonitor: NetworkMonitor
    private let userDefaults: UserDefaults

    init(networkMonitor: NetworkMonitor? = nil, userDefaults: UserDefaults = .standard) {
        self.networkMonitor = networkMonitor ?? NetworkMonitor.shared
        self.userDefaults = userDefaults
        self.weights = ValidationWeights.load()

        networkCancellable = self.networkMonitor.$isConnected
            .receive(on: RunLoop.main)
            .sink { [weak self] connected in
                guard let self else { return }
                self.isOffline = !connected
                if connected {
                    Task { await self.refresh(force: false) }
                } else {
                    self.loadFromCache()
                }
            }
    }

    deinit {
        pollTask?.cancel()
        networkCancellable?.cancel()
    }

    func startMonitoring(symbol: String) {
        let normalized = symbol.uppercased()
        guard self.symbol != normalized else {
            if pollTask == nil {
                startPolling()
            }
            return
        }

        stopMonitoring()
        self.symbol = normalized
        loadFromCache()
        
        // Cancel any existing refresh task and start new one
        refreshTask?.cancel()
        refreshTask = Task { await refresh(force: true) }
        startPolling()
    }

    func stopMonitoring() {
        pollTask?.cancel()
        pollTask = nil
        refreshTask?.cancel()
        refreshTask = nil
        symbol = nil
        isLoading = false
        error = nil
    }

    func manualRefresh() {
        // Cancel any existing refresh and start new one
        refreshTask?.cancel()
        refreshTask = Task { await refresh(force: true) }
    }

    private func startPolling() {
        pollTask?.cancel()
        pollTask = Task { [weak self] in
            guard let self else { return }
            while !Task.isCancelled {
                await self.refresh(force: false)
                try? await Task.sleep(nanoseconds: UInt64(pollInterval * 1_000_000_000))
            }
        }
    }

    private func cacheKey(for symbol: String) -> String {
        "validationCache_\(symbol)"
    }

    private func cache(validator: UnifiedValidator) {
        guard let symbol else { return }
        do {
            let data = try JSONEncoder().encode(validator)
            userDefaults.set(data, forKey: cacheKey(for: symbol))
        } catch {
            #if DEBUG
            print("[ValidationViewModel] Failed to cache validator: \(error)")
            #endif
        }
    }

    private func loadFromCache() {
        guard let symbol else { return }
        guard let data = userDefaults.data(forKey: cacheKey(for: symbol)) else { return }
        do {
            let cached = try JSONDecoder().decode(UnifiedValidator.self, from: data)
            validator = cached.updatingWeights(weights)
            if lastSyncTime == nil {
                lastSyncTime = cached.timestamp
            }
        } catch {
            #if DEBUG
            print("[ValidationViewModel] Failed to load cached validator: \(error)")
            #endif
        }
    }

    private func applyWeightsToCurrentValidator() {
        guard let current = validator else { return }
        validator = current.updatingWeights(weights)
    }

    private func isCacheFresh(for validator: UnifiedValidator) -> Bool {
        Date().timeIntervalSince(validator.timestamp) <= cacheDuration
    }

    private func updateErrorForOfflineState() {
        guard let validator else { return }
        if !isOffline {
            error = nil
        } else if !isCacheFresh(for: validator) {
            error = "Showing cached data (stale)"
        } else {
            error = "Showing cached data"
        }
    }

    private func updateState(with validator: UnifiedValidator) {
        let reweighted = validator.updatingWeights(weights)
        self.validator = reweighted
        self.lastSyncTime = Date()
        self.error = nil
        cache(validator: reweighted)
        Task.detached { [symbol = self.symbol, weights = self.weights] in
            guard let symbol else { return }
            await APIClient.shared.logValidationAudit(
                symbol: symbol,
                validator: reweighted,
                weights: weights,
                clientState: ["source": "app"]
            )
        }
    }

    func refresh(force: Bool) async {
        guard let symbol else { return }
        
        // Check if already refreshing (unless forced)
        guard force || !isLoading else {
            print("[ValidationViewModel] Already refreshing, skipping duplicate call")
            return
        }

        if isOffline {
            if force {
                loadFromCache()
            }
            updateErrorForOfflineState()
            return
        }

        if force || validator == nil {
            isLoading = true
        }

        do {
            let latest = try await APIClient.shared.fetchUnifiedValidation(symbol: symbol)
            // Check if task was cancelled before updating state
            guard !Task.isCancelled else { return }
            updateState(with: latest)
            isLoading = false
        } catch is CancellationError {
            // Swallow cancellation errors
            isLoading = false
        } catch {
            self.error = error.localizedDescription
            self.isLoading = false
            if validator == nil {
                loadFromCache()
            }
        }
    }
}
