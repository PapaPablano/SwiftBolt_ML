import Foundation
import Combine

@MainActor
final class AppViewModel: ObservableObject {
    @Published var selectedSymbol: Symbol? {
        didSet {
            if oldValue?.ticker == selectedSymbol?.ticker {
                return
            }
            print("[DEBUG] 🔴 selectedSymbol DIDSET TRIGGERED")
            print("[DEBUG] - Old value: \(oldValue?.ticker ?? "nil")")
            print("[DEBUG] - New value: \(selectedSymbol?.ticker ?? "nil")")
            if oldValue != nil && selectedSymbol == nil {
                let stack = Thread.callStackSymbols.prefix(12).joined(separator: "\n")
                print("[DEBUG] 🔴 selectedSymbol cleared to nil. Call stack:\n\(stack)")
            }
            handleSymbolChange()
        }
    }

    @Published var symbolViewModel: SymbolViewModel
    @Published var chartViewModel: ChartViewModel
    @Published var indicatorsViewModel: IndicatorsViewModel
    @Published var newsViewModel: NewsViewModel
    @Published var optionsChainViewModel: OptionsChainViewModel
    @Published var optionsRankerViewModel: OptionsRankerViewModel
    @Published var selectedDetailTab: Int = 0
    @Published var selectedOptionsTab: Int = 0
    let searchViewModel: SymbolSearchViewModel
    let watchlistViewModel: WatchlistViewModel

    private var refreshTask: Task<Void, Never>?
    private var cancellables = Set<AnyCancellable>()

    init() {
        self.symbolViewModel = SymbolViewModel()
        self.chartViewModel = ChartViewModel()
        self.indicatorsViewModel = IndicatorsViewModel(config: IndicatorConfig())
        self.newsViewModel = NewsViewModel()
        self.optionsChainViewModel = OptionsChainViewModel()
        self.optionsRankerViewModel = OptionsRankerViewModel()
        self.searchViewModel = SymbolSearchViewModel()
        self.watchlistViewModel = WatchlistViewModel()

        // Keep indicator config in sync (IndicatorsViewModel <-> ChartViewModel)
        indicatorsViewModel.$config
            .removeDuplicates()
            .sink { [weak self] config in
                guard let self else { return }
                if self.chartViewModel.indicatorConfig != config {
                    self.chartViewModel.indicatorConfig = config
                }
            }
            .store(in: &cancellables)

        chartViewModel.$indicatorConfig
            .removeDuplicates()
            .sink { [weak self] config in
                guard let self else { return }
                if self.indicatorsViewModel.config != config {
                    self.indicatorsViewModel.config = config
                }
            }
            .store(in: &cancellables)

        // Keep symbol selection in sync (SymbolViewModel <-> AppViewModel)
        $selectedSymbol
            .removeDuplicates(by: { $0?.ticker == $1?.ticker })
            .receive(on: RunLoop.main)
            .sink { [weak self] symbol in
                guard let self else { return }
                if self.symbolViewModel.selectedSymbol?.ticker != symbol?.ticker {
                    self.symbolViewModel.selectedSymbol = symbol
                }
            }
            .store(in: &cancellables)

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

        // Relay optionsRankerViewModel changes to trigger AppViewModel updates
        optionsRankerViewModel.objectWillChange.sink { [weak self] _ in
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
        optionsRankerViewModel.clearData()

        print("[DEBUG] - Setting chartViewModel.selectedSymbol to: \(selectedSymbol?.ticker ?? "nil")")
        // Setting selectedSymbol triggers didSet which calls loadChart() automatically
        // Do NOT call loadChart() explicitly here to avoid duplicate/cancelled requests
        if chartViewModel.selectedSymbol?.ticker != selectedSymbol?.ticker {
            chartViewModel.selectedSymbol = selectedSymbol
        }
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
        async let rankerLoad: () = optionsRankerViewModel.ensureLoaded(for: selectedSymbol?.ticker ?? "")

        _ = await (newsLoad, optionsLoad, rankerLoad)
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
