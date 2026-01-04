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
                        onSelect: {
                            print("[DEBUG] !!! BUTTON TAPPED IN SearchResultsList !!!")
                            print("[DEBUG] !!! Symbol: \(symbol.ticker) !!!")
                            onSelect(symbol)
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
    let onSelect: () -> Void
    @State private var isHovered = false
    @EnvironmentObject var appViewModel: AppViewModel

    private var isWatched: Bool {
        appViewModel.watchlistViewModel.isWatched(symbol)
    }

    var body: some View {
        print("[DEBUG] 🟢 SearchResultRow.body rendering for: \(symbol.ticker)")
        return Button {
            print("[DEBUG] 🔵🔵🔵 SearchResultRow BUTTON PRESSED for \(symbol.ticker)")
            onSelect()
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

                Text(symbol.assetType.capitalized)
                    .font(.caption2)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(.blue.opacity(0.2))
                    .clipShape(Capsule())

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
