import Foundation
import os.log

// MARK: - Strategy List ViewModel

/// Manages the user's strategies from Supabase. Uses `@Observable` for
/// fine-grained SwiftUI observation. Replaces the in-memory `StrategyBuilderViewModel`.
@Observable
@MainActor
final class StrategyListViewModel {

    // MARK: - State

    var strategies: [SupabaseStrategy] = []
    var selectedStrategy: SupabaseStrategy?
    var isLoading = false
    var error: String?
    var isSaving = false

    // MARK: - Private

    private let service = StrategyService.shared
    private static let logger = Logger(subsystem: "com.swiftboltml", category: "StrategyListViewModel")

    // MARK: - Load

    func loadStrategies() async {
        guard !isLoading else { return }
        isLoading = true
        error = nil
        do {
            strategies = try await service.listStrategies()
            Self.logger.info("Loaded \(self.strategies.count) strategies")
        } catch {
            self.error = error.localizedDescription
            Self.logger.error("Load strategies failed: \(error)")
        }
        isLoading = false
    }

    // MARK: - Create

    /// Creates a new strategy from native `Strategy` model conditions.
    func createStrategy(name: String, entryConditions: [StrategyCondition], exitConditions: [StrategyCondition], parameters: [String: Double] = [:]) async {
        guard !isSaving else { return }
        isSaving = true
        error = nil
        do {
            let config = StrategyConfig(
                entryConditions: entryConditions.map { toSupabaseCondition($0) },
                exitConditions: exitConditions.map { toSupabaseCondition($0) },
                filters: [],
                parameters: parameters.mapValues { .double($0) }
            )
            let created = try await service.createStrategy(name: name, config: config)
            strategies.insert(created, at: 0)
            selectedStrategy = created
            Self.logger.info("Created strategy: \(name)")
        } catch {
            self.error = error.localizedDescription
            Self.logger.error("Create strategy failed: \(error)")
        }
        isSaving = false
    }

    // MARK: - Update

    func updateStrategy(_ strategy: SupabaseStrategy, name: String?, config: StrategyConfig?) async {
        guard !isSaving else { return }
        isSaving = true
        error = nil
        do {
            let updated = try await service.updateStrategy(id: strategy.id, name: name, config: config)
            if let index = strategies.firstIndex(where: { $0.id == strategy.id }) {
                strategies[index] = updated
            }
            if selectedStrategy?.id == strategy.id {
                selectedStrategy = updated
            }
            Self.logger.info("Updated strategy: \(updated.name)")
        } catch {
            self.error = error.localizedDescription
            Self.logger.error("Update strategy failed: \(error)")
        }
        isSaving = false
    }

    // MARK: - Delete

    func deleteStrategy(_ strategy: SupabaseStrategy) async {
        // Optimistic removal
        let removedIndex = strategies.firstIndex(where: { $0.id == strategy.id })
        if let removedIndex {
            strategies.remove(at: removedIndex)
        }
        if selectedStrategy?.id == strategy.id {
            selectedStrategy = strategies.first
        }

        do {
            try await service.deleteStrategy(id: strategy.id)
            Self.logger.info("Deleted strategy: \(strategy.name)")
        } catch {
            // Rollback on failure
            if let removedIndex {
                strategies.insert(strategy, at: min(removedIndex, strategies.count))
            }
            self.error = error.localizedDescription
            Self.logger.error("Delete strategy failed: \(error)")
        }
    }
}
