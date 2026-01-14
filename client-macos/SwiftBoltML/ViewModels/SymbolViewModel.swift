import Foundation

@MainActor
final class SymbolViewModel: ObservableObject {
    private var isUpdatingFromSelectedSymbol = false

    @Published var activeTicker: String {
        didSet {
            if isUpdatingFromSelectedSymbol {
                return
            }
            if activeTicker != oldValue {
                selectedSymbol = nil
            }
        }
    }

    @Published var assetType: String

    @Published var selectedSymbol: Symbol? {
        didSet {
            if let symbol = selectedSymbol {
                isUpdatingFromSelectedSymbol = true
                defer { isUpdatingFromSelectedSymbol = false }
                if activeTicker != symbol.ticker {
                    activeTicker = symbol.ticker
                }
                if assetType != symbol.assetType {
                    assetType = symbol.assetType
                }
            }
        }
    }

    init(activeTicker: String = "", assetType: String = "stock", selectedSymbol: Symbol? = nil) {
        self.activeTicker = activeTicker
        self.assetType = assetType
        self.selectedSymbol = selectedSymbol

        if let symbol = selectedSymbol {
            self.activeTicker = symbol.ticker
            self.assetType = symbol.assetType
        }
    }

    func setSelectedSymbol(_ symbol: Symbol?) {
        selectedSymbol = symbol
    }
}
