import Foundation
import Combine

@MainActor
final class AppViewModel: ObservableObject {
    @Published var selectedSymbol: Symbol? {
        didSet {
            handleSymbolChange()
        }
    }

    let chartViewModel: ChartViewModel
    let newsViewModel: NewsViewModel
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
        print("[DEBUG] AppViewModel.refreshData() START")
        print("[DEBUG] - Symbol to load: \(selectedSymbol?.ticker ?? "nil")")
        print("[DEBUG] - Setting chartViewModel.selectedSymbol...")

        chartViewModel.selectedSymbol = selectedSymbol

        print("[DEBUG] - chartViewModel.selectedSymbol set to: \(chartViewModel.selectedSymbol?.ticker ?? "nil")")
        print("[DEBUG] - Calling chartViewModel.loadChart() and newsViewModel.loadNews()...")

        async let chartLoad: () = chartViewModel.loadChart()
        async let newsLoad: () = newsViewModel.loadNews(for: selectedSymbol?.ticker)

        _ = await (chartLoad, newsLoad)
        print("[DEBUG] AppViewModel.refreshData() COMPLETED")
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
