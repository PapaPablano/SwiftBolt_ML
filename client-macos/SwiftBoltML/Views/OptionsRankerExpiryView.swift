import SwiftUI

/// Multi-expiry comparison view for options ranker
/// Shows top ranked options grouped by expiration date for easy comparison
struct OptionsRankerExpiryView: View {
    @ObservedObject var rankerViewModel: OptionsRankerViewModel
    let symbol: String

    // Group rankings by expiry
    private var rankingsByExpiry: [(expiry: String, ranks: [OptionRank])] {
        let grouped = Dictionary(grouping: rankerViewModel.filteredRankings, by: { $0.expiry })
        return grouped.map { (expiry: $0.key, ranks: $0.value) }
            .sorted { $0.expiry < $1.expiry } // Sort by date
    }

    var body: some View {
        VStack(spacing: 0) {
            // Header
            ExpiryViewHeader(
                rankerViewModel: rankerViewModel,
                symbol: symbol,
                expiryCount: rankingsByExpiry.count
            )

            Divider()

            // Scrollable content
            ScrollView {
                LazyVStack(spacing: 16, pinnedViews: [.sectionHeaders]) {
                    ForEach(rankingsByExpiry, id: \.expiry) { group in
                        Section {
                            // Show top 10 for each expiry
                            ForEach(Array(group.ranks.prefix(10))) { rank in
                                CompactRankRow(rank: rank)
                                    .padding(.horizontal)
                            }
                        } header: {
                            ExpiryHeader(
                                expiry: group.expiry,
                                totalCount: group.ranks.count
                            )
                        }
                    }
                }
                .padding(.vertical, 8)
            }
        }
    }
}

struct ExpiryViewHeader: View {
    @ObservedObject var rankerViewModel: OptionsRankerViewModel
    let symbol: String
    let expiryCount: Int

    var body: some View {
        VStack(spacing: 12) {
            HStack {
                Image(systemName: "calendar.badge.clock")
                    .foregroundStyle(.purple)
                Text("Multi-Expiry Comparison")
                    .font(.headline)

                Spacer()

                // Refresh button
                Button(action: {
                    Task {
                        await rankerViewModel.triggerRankingJob(for: symbol)
                    }
                }) {
                    Image(systemName: "arrow.clockwise")
                        .font(.caption)
                }
                .buttonStyle(.borderless)
                .help("Generate new rankings")

                Text("\(expiryCount) expiries")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .padding(.horizontal)
            .padding(.top, 12)

            // Filters
            HStack {
                // Side filter
                VStack(alignment: .leading, spacing: 4) {
                    Text("Side")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                    Picker("", selection: Binding(
                        get: { rankerViewModel.selectedSide },
                        set: { rankerViewModel.setSide($0) }
                    )) {
                        Text("All").tag(nil as OptionSide?)
                        Text("Calls").tag(OptionSide.call as OptionSide?)
                        Text("Puts").tag(OptionSide.put as OptionSide?)
                    }
                    .labelsHidden()
                    .frame(maxWidth: .infinity)
                }

                // Min score slider
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text("Min Score")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                        Spacer()
                        Text("\(Int(rankerViewModel.minScore * 100))%")
                            .font(.caption2.bold())
                            .foregroundStyle(.purple)
                    }

                    Slider(value: $rankerViewModel.minScore, in: 0...1, step: 0.05)
                        .tint(.purple)
                }
            }
            .padding(.horizontal)
            .padding(.bottom, 12)
        }
        .background(Color(nsColor: .controlBackgroundColor))
    }
}

struct ExpiryHeader: View {
    let expiry: String
    let totalCount: Int

    private var formattedDate: String {
        guard let date = ISO8601DateFormatter().date(from: expiry) else {
            return expiry
        }
        let formatter = DateFormatter()
        formatter.dateFormat = "EEE, MMM d, yyyy"
        return formatter.string(from: date)
    }

    private var daysToExpiry: Int? {
        guard let date = ISO8601DateFormatter().date(from: expiry) else { return nil }
        return Calendar.current.dateComponents([.day], from: Date(), to: date).day
    }

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(formattedDate)
                    .font(.subheadline.bold())

                if let dte = daysToExpiry {
                    Text("\(dte) days to expiry")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }

            Spacer()

            Text("\(totalCount) contracts")
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
        .padding(.horizontal)
        .padding(.vertical, 8)
        .background(Color(nsColor: .windowBackgroundColor))
    }
}

struct CompactRankRow: View {
    let rank: OptionRank

    var body: some View {
        HStack(spacing: 12) {
            // ML Score badge (compact)
            VStack(spacing: 2) {
                Text("\(Int(rank.scorePercentage))")
                    .font(.callout.bold())
                    .foregroundStyle(rank.scoreColor)
                Text("ML")
                    .font(.system(size: 9))
                    .foregroundStyle(.secondary)
            }
            .frame(width: 45)
            .padding(.vertical, 6)
            .background(rank.scoreColor.opacity(0.1))
            .clipShape(RoundedRectangle(cornerRadius: 6))

            // Contract info
            VStack(alignment: .leading, spacing: 3) {
                HStack(spacing: 6) {
                    Text("$\(String(format: "%.2f", rank.strike))")
                        .font(.subheadline.bold())

                    Text(rank.side == .call ? "C" : "P")
                        .font(.caption2.bold())
                        .padding(.horizontal, 4)
                        .padding(.vertical, 2)
                        .background(rank.side == .call ? Color.green.opacity(0.2) : Color.red.opacity(0.2))
                        .foregroundStyle(rank.side == .call ? .green : .red)
                        .clipShape(RoundedRectangle(cornerRadius: 3))

                    if let mark = rank.mark {
                        Text("$\(String(format: "%.2f", mark))")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }

                HStack(spacing: 8) {
                    if let iv = rank.impliedVol {
                        Label("\(Int(iv * 100))%", systemImage: "waveform.path.ecg")
                            .font(.system(size: 10))
                            .foregroundStyle(.secondary)
                    }

                    if let delta = rank.delta {
                        Label("Δ\(String(format: "%.2f", abs(delta)))", systemImage: "triangle.fill")
                            .font(.system(size: 10))
                            .foregroundStyle(.secondary)
                    }

                    if let volume = rank.volume {
                        Label("\(formatNumber(volume))", systemImage: "chart.bar.fill")
                            .font(.system(size: 10))
                            .foregroundStyle(.secondary)
                    }
                }
            }

            Spacer()
        }
        .padding(8)
        .background(Color(nsColor: .controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(rank.scoreColor.opacity(0.3), lineWidth: 1)
        )
    }

    private func formatNumber(_ number: Int) -> String {
        if number >= 1000000 {
            return String(format: "%.1fM", Double(number) / 1000000)
        } else if number >= 1000 {
            return String(format: "%.1fK", Double(number) / 1000)
        }
        return String(number)
    }
}

// Preview
struct OptionsRankerExpiryView_Previews: PreviewProvider {
    static var previews: some View {
        OptionsRankerExpiryView(
            rankerViewModel: OptionsRankerViewModel(),
            symbol: "AAPL"
        )
        .frame(width: 800, height: 600)
    }
}
