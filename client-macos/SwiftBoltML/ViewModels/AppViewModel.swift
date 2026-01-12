import Foundation
import Combine

@MainActor
final class AppViewModel: ObservableObject {
    @Published var selectedSymbol: Symbol? {
        didSet {
            print("[DEBUG] 🔴 selectedSymbol DIDSET TRIGGERED")
            print("[DEBUG] - Old value: \(oldValue?.ticker ?? "nil")")
            print("[DEBUG] - New value: \(selectedSymbol?.ticker ?? "nil")")
            handleSymbolChange()
        }
    }

    @Published var chartViewModel: ChartViewModel
    @Published var newsViewModel: NewsViewModel
    @Published var optionsChainViewModel: OptionsChainViewModel
    let searchViewModel: SymbolSearchViewModel
    let watchlistViewModel: WatchlistViewModel

    private var refreshTask: Task<Void, Never>?
    private var cancellables = Set<AnyCancellable>()

    init() {
        self.chartViewModel = ChartViewModel()
        self.newsViewModel = NewsViewModel()
        self.optionsChainViewModel = OptionsChainViewModel()
        self.searchViewModel = SymbolSearchViewModel()
        self.watchlistViewModel = WatchlistViewModel()

        // Relay chartViewModel changes to trigger AppViewModel updates
        chartViewModel.objectWillChange.sink { [weak self] _ in
            DispatchQueue.main.async {
                self?.objectWillChange.send()
            }
        }.store(in: &cancellables)

        // Relay newsViewModel changes to trigger AppViewModel updates
        newsViewModel.objectWillChange.sink { [weak self] _ in
            DispatchQueue.main.async {
                self?.objectWillChange.send()
            }
        }.store(in: &cancellables)

        // Relay optionsChainViewModel changes to trigger AppViewModel updates
        optionsChainViewModel.objectWillChange.sink { [weak self] _ in
            DispatchQueue.main.async {
                self?.objectWillChange.send()
            }
        }.store(in: &cancellables)

    }

    private func handleSymbolChange() {
        print("[DEBUG] ========================================")
        print("[DEBUG] AppViewModel.handleSymbolChange() triggered")
        print("[DEBUG] - New symbol: \(selectedSymbol?.ticker ?? "nil")")
        print("[DEBUG] - Asset type: \(selectedSymbol?.assetType ?? "nil")")
        print("[DEBUG] ========================================")

        refreshTask?.cancel()

        refreshTask = Task {
            await refreshData()
        }
    }

    func refreshData() async {
        print("[DEBUG] ========================================")
        print("[DEBUG] AppViewModel.refreshData() START")
        print("[DEBUG] - selectedSymbol (AppViewModel): \(selectedSymbol?.ticker ?? "nil")")
        print("[DEBUG] - chartViewModel.selectedSymbol (BEFORE): \(chartViewModel.selectedSymbol?.ticker ?? "nil")")

        // Clear stale data immediately to show loading states
        chartViewModel.clearData()
        newsViewModel.clearData()
        optionsChainViewModel.clearData()

        print("[DEBUG] - Setting chartViewModel.selectedSymbol to: \(selectedSymbol?.ticker ?? "nil")")
        // Setting selectedSymbol triggers didSet which calls loadChart() automatically
        // Do NOT call loadChart() explicitly here to avoid duplicate/cancelled requests
        chartViewModel.selectedSymbol = selectedSymbol
        print("[DEBUG] - chartViewModel.selectedSymbol (AFTER): \(chartViewModel.selectedSymbol?.ticker ?? "nil")")

        guard selectedSymbol != nil else {
            print("[DEBUG] - No symbol selected, skipping load")
            print("[DEBUG] ========================================")
            return
        }

        print("[DEBUG] - Loading news and options (chart loads via didSet)...")

        // Chart loading is handled by chartViewModel.selectedSymbol.didSet
        // Only load news and options here to avoid duplicate chart requests
        async let newsLoad: () = newsViewModel.loadNews(for: selectedSymbol?.ticker)
        async let optionsLoad: () = optionsChainViewModel.loadOptionsChain(for: selectedSymbol?.ticker ?? "")

        _ = await (newsLoad, optionsLoad)
        print("[DEBUG] AppViewModel.refreshData() COMPLETED")
        print("[DEBUG] ========================================")
    }

    func selectSymbol(_ symbol: Symbol) {
        print("[DEBUG] ========================================")
        print("[DEBUG] AppViewModel.selectSymbol() CALLED")
        print("[DEBUG] - Ticker: \(symbol.ticker)")
        print("[DEBUG] - Asset Type: \(symbol.assetType)")
        print("[DEBUG] - Description: \(symbol.description)")
        print("[DEBUG] ========================================")

        selectedSymbol = symbol
        searchViewModel.clearSearch()
    }

    func clearSelection() {
        selectedSymbol = nil
    }

    #if DEBUG
    func bootstrapForDebug() {
        print("[DEBUG] ========================================")
        print("[DEBUG] bootstrapForDebug() - Loading AAPL for testing")
        print("[DEBUG] ========================================")

        let symbol = Symbol(
            id: UUID(),
            ticker: "AAPL",
            assetType: "stock",
            description: "Apple Inc."
        )
        selectSymbol(symbol)
    }
    #endif
}
