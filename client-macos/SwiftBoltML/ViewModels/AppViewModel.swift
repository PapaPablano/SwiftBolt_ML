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
    let searchViewModel: SymbolSearchViewModel
    let watchlistViewModel: WatchlistViewModel

    private var refreshTask: Task<Void, Never>?

    init() {
        self.chartViewModel = ChartViewModel()
        self.newsViewModel = NewsViewModel()
        self.searchViewModel = SymbolSearchViewModel()
        self.watchlistViewModel = WatchlistViewModel()
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

        print("[DEBUG] - Setting chartViewModel.selectedSymbol to: \(selectedSymbol?.ticker ?? "nil")")
        chartViewModel.selectedSymbol = selectedSymbol
        print("[DEBUG] - chartViewModel.selectedSymbol (AFTER): \(chartViewModel.selectedSymbol?.ticker ?? "nil")")

        guard selectedSymbol != nil else {
            print("[DEBUG] - No symbol selected, skipping load")
            print("[DEBUG] ========================================")
            return
        }

        print("[DEBUG] - Calling chartViewModel.loadChart() and newsViewModel.loadNews()...")

        async let chartLoad: () = chartViewModel.loadChart()
        async let newsLoad: () = newsViewModel.loadNews(for: selectedSymbol?.ticker)

        _ = await (chartLoad, newsLoad)
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
