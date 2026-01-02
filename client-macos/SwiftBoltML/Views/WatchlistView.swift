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

                if watchlistViewModel.isLoading {
                    ProgressView()
                        .scaleEffect(0.7)
                        .frame(width: 16, height: 16)
                }

                Button {
                    Task {
                        await watchlistViewModel.refreshWatchlist()
                    }
                } label: {
                    Image(systemName: "arrow.clockwise")
                        .font(.caption)
                }
                .buttonStyle(.plain)
                .help("Refresh watchlist")

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
                                    Task {
                                        await watchlistViewModel.removeSymbol(symbol)
                                    }
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

    @EnvironmentObject var appViewModel: AppViewModel
    @State private var isHovered = false

    private var jobStatus: WatchlistJobStatus? {
        appViewModel.watchlistViewModel.getJobStatus(for: symbol)
    }

    var body: some View {
        HStack(spacing: 8) {
            VStack(alignment: .leading, spacing: 4) {
                Text(symbol.ticker)
                    .font(.headline)
                    .foregroundStyle(isSelected ? Color.accentColor : .primary)

                Text(symbol.description)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)

                if symbol.avgDailyVolumeAll != nil || symbol.avgDailyVolume10d != nil || symbol.avgLastPriceAll != nil || symbol.avgLastPrice10d != nil {
                    VStack(alignment: .leading, spacing: 2) {
                        HStack(spacing: 6) {
                            Text("Avg Vol")
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                            Text("All: \(formatCompact(symbol.avgDailyVolumeAll))")
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                            Text("10D: \(formatCompact(symbol.avgDailyVolume10d))")
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                        }

                        HStack(spacing: 6) {
                            Text("Avg Px")
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                            Text("All: \(formatPrice(symbol.avgLastPriceAll))")
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                            Text("10D: \(formatPrice(symbol.avgLastPrice10d))")
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                        }
                    }
                }

                // Job status indicators
                if let status = jobStatus {
                    HStack(spacing: 6) {
                        jobStatusBadge(label: "ML", status: status.forecastStatus)
                        jobStatusBadge(label: "Rank", status: status.rankingStatus)
                    }
                }
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

    private func formatCompact(_ value: Double?) -> String {
        guard let value else { return "-" }
        let absValue = abs(value)
        if absValue >= 1_000_000_000 {
            return String(format: "%.2fB", value / 1_000_000_000)
        }
        if absValue >= 1_000_000 {
            return String(format: "%.2fM", value / 1_000_000)
        }
        if absValue >= 1_000 {
            return String(format: "%.1fK", value / 1_000)
        }
        return String(format: "%.0f", value)
    }

    private func formatPrice(_ value: Double?) -> String {
        guard let value else { return "-" }
        return String(format: "$%.2f", value)
    }

    private func jobStatusBadge(label: String, status: JobStatusState) -> some View {
        HStack(spacing: 3) {
            Circle()
                .fill(statusColor(status))
                .frame(width: 6, height: 6)

            Text(label)
                .font(.system(size: 9))
                .fontWeight(.medium)
        }
        .padding(.horizontal, 4)
        .padding(.vertical, 2)
        .background(Color(.windowBackgroundColor).opacity(0.5))
        .clipShape(Capsule())
        .help("\(label): \(status.displayName)")
    }

    private func statusColor(_ status: JobStatusState) -> Color {
        switch status {
        case .pending: return .gray
        case .running: return .blue
        case .completed: return .green
        case .failed: return .red
        case .unknown: return .gray
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
