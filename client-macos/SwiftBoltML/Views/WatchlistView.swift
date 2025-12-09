import SwiftUI

struct WatchlistView: View {
    @EnvironmentObject var appViewModel: AppViewModel

    private var watchlistViewModel: WatchlistViewModel {
        appViewModel.watchlistViewModel
    }

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Text("Watchlist")
                    .font(.headline)
                Spacer()
                Text("\(watchlistViewModel.watchedSymbols.count)")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(.quaternary)
                    .clipShape(Capsule())
            }
            .padding()

            Divider()

            if watchlistViewModel.watchedSymbols.isEmpty {
                EmptyWatchlistView()
            } else {
                ScrollView {
                    LazyVStack(spacing: 0) {
                        ForEach(watchlistViewModel.watchedSymbols) { symbol in
                            WatchlistRow(
                                symbol: symbol,
                                isSelected: appViewModel.selectedSymbol?.id == symbol.id,
                                onSelect: {
                                    appViewModel.selectSymbol(symbol)
                                },
                                onRemove: {
                                    watchlistViewModel.removeSymbol(symbol)
                                }
                            )
                            Divider()
                        }
                    }
                }
            }
        }
        .background(Color(nsColor: .controlBackgroundColor))
    }
}

struct WatchlistRow: View {
    let symbol: Symbol
    let isSelected: Bool
    let onSelect: () -> Void
    let onRemove: () -> Void

    @State private var isHovered = false

    var body: some View {
        HStack(spacing: 8) {
            VStack(alignment: .leading, spacing: 2) {
                Text(symbol.ticker)
                    .font(.headline)
                    .foregroundStyle(isSelected ? Color.accentColor : .primary)

                Text(symbol.description)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }

            Spacer()

            if isHovered {
                Button {
                    onRemove()
                } label: {
                    Image(systemName: "star.slash.fill")
                        .font(.caption)
                        .foregroundStyle(.orange)
                }
                .buttonStyle(.plain)
            } else {
                Image(systemName: "star.fill")
                    .font(.caption)
                    .foregroundStyle(.orange)
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(isSelected ? Color.accentColor.opacity(0.1) : (isHovered ? Color.primary.opacity(0.05) : Color.clear))
        .contentShape(Rectangle())
        .onTapGesture {
            onSelect()
        }
        .onHover { hovering in
            isHovered = hovering
            if hovering {
                NSCursor.pointingHand.push()
            } else {
                NSCursor.pop()
            }
        }
    }
}

struct EmptyWatchlistView: View {
    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "star")
                .font(.system(size: 48))
                .foregroundStyle(.secondary)

            VStack(spacing: 4) {
                Text("No Symbols Watched")
                    .font(.headline)

                Text("Search for symbols and\nadd them to your watchlist")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding()
    }
}

#Preview {
    WatchlistView()
        .environmentObject(AppViewModel())
        .frame(width: 300, height: 400)
}
