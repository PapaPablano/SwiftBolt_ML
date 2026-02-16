import SwiftUI

struct SymbolSearchView: View {
    @EnvironmentObject var appViewModel: AppViewModel

    private var searchViewModel: SymbolSearchViewModel {
        appViewModel.searchViewModel
    }

    var body: some View {
        let _ = print("[DEBUG] 🔴 SymbolSearchView.body rendering")
        let _ = print("[DEBUG] - Search results count: \(searchViewModel.searchResults.count)")
        let _ = print("[DEBUG] - Search query: '\(searchViewModel.searchQuery)'")
        let _ = print("[DEBUG] - Is searching: \(searchViewModel.isSearching)")

        return VStack(spacing: 0) {
            SearchField(
                text: Binding(
                    get: { searchViewModel.searchQuery },
                    set: { searchViewModel.searchQuery = $0 }
                ),
                isSearching: searchViewModel.isSearching
            )
            .padding()

            if searchViewModel.isActive {
                if !searchViewModel.searchResults.isEmpty {
                    let _ = print("[DEBUG] 🟠 Showing SearchResultsList with \(searchViewModel.searchResults.count) results")
                    SearchResultsList(
                        results: searchViewModel.searchResults,
                        onSelect: { symbol in
                            print("[DEBUG] ========================================")
                            print("[DEBUG] SymbolSearchView - User tapped symbol")
                            print("[DEBUG] - Ticker: \(symbol.ticker)")
                            print("[DEBUG] - Asset Type: \(symbol.assetType)")
                            print("[DEBUG] - Calling appViewModel.selectSymbol()...")
                            print("[DEBUG] ========================================")
                            searchViewModel.trackSymbolSelection(symbol)
                            appViewModel.selectSymbol(symbol)
                        }
                    )
                } else if let error = searchViewModel.errorMessage {
                    let _ = print("[DEBUG] 🔴 Showing error banner: \(error)")
                    ErrorBanner(message: error)
                        .padding(.horizontal)
                } else {
                    let _ = print("[DEBUG] ⚪ No search results, no error - showing nothing")
                    Color.clear.frame(height: 0)
                }
            } else {
                Color.clear.frame(height: 0)
            }
        }
    }
}

struct SearchField: View {
    @Binding var text: String
    let isSearching: Bool

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: "magnifyingglass")
                .foregroundStyle(.secondary)

            TextField("Search symbols...", text: $text)
                .textFieldStyle(.plain)

            if isSearching {
                ProgressView()
                    .controlSize(.small)
            } else if !text.isEmpty {
                Button {
                    text = ""
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundStyle(.secondary)
                }
                .buttonStyle(.plain)
            }
        }
        .padding(8)
        .background(.quaternary)
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}

struct SearchResultsList: View {
    let results: [Symbol]
    let onSelect: (Symbol) -> Void

    var body: some View {
        ScrollView {
            LazyVStack(spacing: 2) {
                ForEach(results) { symbol in
                    SearchResultRow(
                        symbol: symbol,
                        onSelect: { selected in
                            print("[DEBUG] !!! BUTTON TAPPED IN SearchResultsList !!!")
                            print("[DEBUG] !!! Symbol: \(selected.ticker) !!!")
                            onSelect(selected)
                        }
                    )
                }
            }
            .padding(.horizontal)
            .padding(.bottom)
        }
        .frame(maxHeight: 300)
    }
}

struct SearchResultRow: View {
    let symbol: Symbol
    let onSelect: (Symbol) -> Void
    @State private var isHovered = false
    @State private var isExpanded = false
    @State private var contracts: [FuturesContract] = []
    @EnvironmentObject var appViewModel: AppViewModel

    private var isWatched: Bool {
        appViewModel.watchlistViewModel.isWatched(symbol)
    }

    var body: some View {
        print("[DEBUG] 🟢 SearchResultRow.body rendering for: \(symbol.ticker)")
        
        return VStack(alignment: .leading, spacing: 0) {
            // Main row
            Button {
                print("[DEBUG] 🔵🔵🔵 SearchResultRow BUTTON PRESSED for \(symbol.ticker)")
                handleTap()
            } label: {
                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(symbol.ticker)
                            .font(.headline)
                        Text(symbol.description)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .lineLimit(1)
                    }

                    Spacer()

                    // Futures indicator
                    if symbol.assetType == "future" {
                        if symbol.isFuturesRoot {
                            Text("[Select Expiry →]")
                                .font(.caption)
                                .foregroundColor(.accentColor)
                            Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                                .foregroundColor(.secondary)
                                .font(.caption)
                        } else if symbol.isContinuous == true {
                            Text("Continuous")
                                .font(.caption2)
                                .padding(.horizontal, 6)
                                .padding(.vertical, 2)
                                .background(Color.blue.opacity(0.2))
                                .clipShape(Capsule())
                        } else {
                            Text("Dated")
                                .font(.caption2)
                                .padding(.horizontal, 6)
                                .padding(.vertical, 2)
                                .background(Color.green.opacity(0.2))
                                .clipShape(Capsule())
                        }
                    } else {
                        Text(symbol.assetType.capitalized)
                            .font(.caption2)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(.blue.opacity(0.2))
                            .clipShape(Capsule())
                    }

                    // Watchlist star button - use onTapGesture to prevent event propagation
                    Image(systemName: isWatched ? "star.fill" : "star")
                        .font(.caption)
                        .foregroundStyle(.orange)
                        .frame(width: 24, height: 24)
                        .contentShape(Rectangle())
                        .onTapGesture {
                            print("[DEBUG] ⭐⭐⭐ Watchlist star tapped for \(symbol.ticker)")
                            Task {
                                await appViewModel.watchlistViewModel.toggleSymbol(symbol)
                            }
                        }
                        .help(isWatched ? "Remove from watchlist" : "Add to watchlist")
                }
                .padding(.vertical, 8)
                .padding(.horizontal, 12)
                .background(isHovered ? Color.accentColor.opacity(0.2) : Color.primary.opacity(0.05))
                .clipShape(RoundedRectangle(cornerRadius: 6))
            }
            .buttonStyle(.plain)
            .onHover { hovering in
                print("[DEBUG] 🟣 Hover state changed to: \(hovering) for \(symbol.ticker)")
                isHovered = hovering
                if hovering {
                    NSCursor.pointingHand.push()
                } else {
                    NSCursor.pop()
                }
            }
            
            // Inline expiry picker for futures roots
            if isExpanded && symbol.isFuturesRoot {
                FuturesExpiryPickerInline(
                    rootSymbol: symbol.ticker,
                    contracts: contracts,
                    onSelect: { selectedSymbol in
                        // Create a new symbol object for the selected contract
                        let contractSymbol = Symbol(
                            ticker: selectedSymbol,
                            assetType: "future",
                            description: "\(symbol.description) - \(selectedSymbol)",
                            rootSymbol: symbol.ticker,
                            isContinuous: selectedSymbol.contains("!")
                        )
                        onSelect(contractSymbol)
                        isExpanded = false
                    }
                )
                .padding(.leading, 16)
                .padding(.vertical, 8)
                .background(Color.secondary.opacity(0.05))
                .clipShape(RoundedRectangle(cornerRadius: 6))
            }
        }
    }
    
    private func handleTap() {
        if symbol.isFuturesRoot {
            withAnimation(.easeInOut(duration: 0.2)) {
                isExpanded.toggle()
                if isExpanded && contracts.isEmpty {
                    loadContracts()
                }
            }
        } else {
            onSelect(symbol)
        }
    }
    
    private func loadContracts() {
        Task {
            do {
                let fetchedContracts = try await APIClient.shared.fetchFuturesChain(root: symbol.ticker)
                await MainActor.run {
                    contracts = fetchedContracts
                }
            } catch {
                print("[DEBUG] Failed to load futures contracts: \(error)")
            }
        }
    }
}

struct ErrorBanner: View {
    let message: String

    var body: some View {
        HStack {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundStyle(.orange)
            Text(message)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(8)
        .frame(maxWidth: .infinity)
        .background(.orange.opacity(0.1))
        .clipShape(RoundedRectangle(cornerRadius: 6))
    }
}

#Preview {
    SymbolSearchView()
        .environmentObject(AppViewModel())
        .frame(width: 300)
}
