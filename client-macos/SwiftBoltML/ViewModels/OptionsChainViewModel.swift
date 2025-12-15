import Foundation

@MainActor
final class OptionsChainViewModel: ObservableObject {
    @Published private(set) var optionsChain: OptionsChainResponse?
    @Published private(set) var isLoading: Bool = false
    @Published var errorMessage: String?
    @Published var selectedExpiration: TimeInterval?
    @Published var filterType: FilterType = .all

    enum FilterType {
        case all
        case calls
        case puts
    }

    var availableExpirations: [TimeInterval] {
        optionsChain?.expirations ?? []
    }

    var filteredContracts: [OptionContract] {
        guard let chain = optionsChain else { return [] }

        var contracts: [OptionContract] = []

        switch filterType {
        case .all:
            contracts = chain.calls + chain.puts
        case .calls:
            contracts = chain.calls
        case .puts:
            contracts = chain.puts
        }

        // Filter by selected expiration if any
        if let selectedExpiration = selectedExpiration {
            contracts = contracts.filter { $0.expiration == selectedExpiration }
        }

        // Sort by strike price
        return contracts.sorted { $0.strike < $1.strike }
    }

    var callContracts: [OptionContract] {
        guard let chain = optionsChain else { return [] }
        var calls = chain.calls

        if let selectedExpiration = selectedExpiration {
            calls = calls.filter { $0.expiration == selectedExpiration }
        }

        return calls.sorted { $0.strike < $1.strike }
    }

    var putContracts: [OptionContract] {
        guard let chain = optionsChain else { return [] }
        var puts = chain.puts

        if let selectedExpiration = selectedExpiration {
            puts = puts.filter { $0.expiration == selectedExpiration }
        }

        return puts.sorted { $0.strike < $1.strike }
    }

    func loadOptionsChain(for symbol: String) async {
        print("[DEBUG] OptionsChainViewModel.loadOptionsChain() CALLED for \(symbol)")

        isLoading = true
        errorMessage = nil

        do {
            let response = try await APIClient.shared.fetchOptionsChain(
                underlying: symbol,
                expiration: selectedExpiration
            )
            optionsChain = response

            // Auto-select nearest expiration if none selected
            if selectedExpiration == nil, let nearest = response.nearestExpiration() {
                selectedExpiration = nearest
            }

            print("[DEBUG] OptionsChainViewModel.loadOptionsChain() - SUCCESS!")
            print("[DEBUG] - Received \(response.calls.count) calls and \(response.puts.count) puts")
            print("[DEBUG] - Expirations: \(response.expirations.count)")
        } catch {
            print("[DEBUG] OptionsChainViewModel.loadOptionsChain() - ERROR: \(error)")
            errorMessage = error.localizedDescription
            optionsChain = nil
        }

        isLoading = false
        print("[DEBUG] OptionsChainViewModel.loadOptionsChain() COMPLETED")
    }

    func refresh(for symbol: String) async {
        await loadOptionsChain(for: symbol)
    }

    func clearData() {
        optionsChain = nil
        errorMessage = nil
        selectedExpiration = nil
    }

    func selectExpiration(_ expiration: TimeInterval?) {
        selectedExpiration = expiration
    }
}
