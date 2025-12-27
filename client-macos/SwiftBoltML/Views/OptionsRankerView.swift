import SwiftUI

struct OptionsRankerView: View {
    @EnvironmentObject var appViewModel: AppViewModel
    @StateObject private var rankerViewModel = OptionsRankerViewModel()

    var body: some View {
        VStack(spacing: 0) {
            if rankerViewModel.isGeneratingRankings {
                GeneratingRankingsView()
            } else if rankerViewModel.isLoading {
                LoadingRankerView()
            } else if let error = rankerViewModel.errorMessage {
                RankerErrorView(
                    message: error,
                    symbol: appViewModel.selectedSymbol?.ticker ?? "",
                    rankerViewModel: rankerViewModel
                )
            } else if rankerViewModel.rankings.isEmpty {
                EmptyRankerView(
                    symbol: appViewModel.selectedSymbol?.ticker ?? "",
                    rankerViewModel: rankerViewModel
                )
            } else {
                RankedOptionsContent(
                    rankerViewModel: rankerViewModel,
                    symbol: appViewModel.selectedSymbol?.ticker ?? ""
                )
            }
        }
        .onChange(of: appViewModel.selectedSymbol) { oldValue, newValue in
            if let symbol = newValue?.ticker {
                Task {
                    await rankerViewModel.loadRankings(for: symbol)
                }
            }
        }
        .onAppear {
            if let symbol = appViewModel.selectedSymbol?.ticker {
                Task {
                    await rankerViewModel.loadRankings(for: symbol)
                }
            }
        }
    }
}

struct RankedOptionsContent: View {
    @ObservedObject var rankerViewModel: OptionsRankerViewModel
    let symbol: String
    @State private var viewMode: ViewMode = .allContracts

    enum ViewMode: String, CaseIterable {
        case allContracts = "All Contracts"
        case byExpiry = "By Expiry"
    }

    var body: some View {
        VStack(spacing: 0) {
            // View mode toggle
            Picker("View Mode", selection: $viewMode) {
                ForEach(ViewMode.allCases, id: \.self) { mode in
                    Text(mode.rawValue).tag(mode)
                }
            }
            .pickerStyle(.segmented)
            .padding(.horizontal)
            .padding(.vertical, 8)

            Divider()

            // Content based on view mode
            switch viewMode {
            case .allContracts:
                AllContractsView(rankerViewModel: rankerViewModel, symbol: symbol)
            case .byExpiry:
                OptionsRankerExpiryView(rankerViewModel: rankerViewModel, symbol: symbol)
            }
        }
    }
}

struct AllContractsView: View {
    @ObservedObject var rankerViewModel: OptionsRankerViewModel
    let symbol: String
    @State private var selectedRank: OptionRank?

    var body: some View {
        VStack(spacing: 0) {
            // Header with title and filters
            RankerHeader(
                rankerViewModel: rankerViewModel,
                symbol: symbol
            )

            Divider()

            // Ranked options list
            ScrollView {
                LazyVStack(spacing: 8) {
                    ForEach(rankerViewModel.filteredRankings) { rank in
                        RankedOptionRow(rank: rank, symbol: symbol)
                            .padding(.horizontal)
                            .onTapGesture {
                                selectedRank = rank
                            }
                    }
                }
                .padding(.vertical, 8)
            }
        }
        .sheet(item: $selectedRank) { rank in
            OptionRankDetailView(
                rank: rank,
                symbol: symbol,
                allRankings: rankerViewModel.rankings
            )
        }
    }
}

struct RankerHeader: View {
    @ObservedObject var rankerViewModel: OptionsRankerViewModel
    let symbol: String

    var body: some View {
        VStack(spacing: 12) {
            // Title with status badge
            HStack {
                Image(systemName: "chart.line.uptrend.xyaxis.circle.fill")
                    .foregroundStyle(.purple)
                Text("Options Momentum Ranker")
                    .font(.headline)

                // Status badge
                if rankerViewModel.rankingStatus != .unknown {
                    statusBadge
                }

                Spacer()

                // Quick refresh - just reload existing rankings
                Button(action: {
                    Task {
                        await rankerViewModel.loadRankings(for: symbol)
                    }
                }) {
                    Image(systemName: "arrow.clockwise")
                        .font(.caption)
                }
                .buttonStyle(.borderless)
                .help("Reload rankings")
                
                // Full sync - fetch fresh data + generate new rankings
                Button(action: {
                    Task {
                        await rankerViewModel.syncAndRank(for: symbol)
                    }
                }) {
                    HStack(spacing: 2) {
                        Image(systemName: "arrow.triangle.2.circlepath")
                            .font(.caption2)
                        Text("Sync")
                            .font(.caption2)
                    }
                }
                .buttonStyle(.borderless)
                .help("Sync data & generate new rankings")

                Text("\(rankerViewModel.filteredRankings.count) contracts")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .padding(.horizontal)
            .padding(.top, 12)

            // Filters
            VStack(spacing: 8) {
                // Row 1: Expiry, Side, Signal
                HStack {
                    // Expiry filter
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Expiry")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                        Picker("", selection: Binding(
                            get: { rankerViewModel.selectedExpiry },
                            set: { rankerViewModel.setExpiry($0) }
                        )) {
                            Text("All").tag(nil as String?)
                            ForEach(rankerViewModel.availableExpiries, id: \.self) { expiry in
                                Text(formatExpiry(expiry))
                                    .tag(expiry as String?)
                            }
                        }
                        .labelsHidden()
                        .frame(maxWidth: .infinity)
                    }

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

                    // Signal filter
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Signal")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                        Picker("", selection: Binding(
                            get: { rankerViewModel.selectedSignal },
                            set: { rankerViewModel.setSignalFilter($0) }
                        )) {
                            ForEach(SignalFilter.allCases, id: \.self) { signal in
                                Text(signal.rawValue).tag(signal)
                            }
                        }
                        .labelsHidden()
                        .frame(maxWidth: .infinity)
                    }
                }

                // Row 2: Sort option and min score slider
                HStack(spacing: 16) {
                    // Sort option
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Sort By")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                        Picker("", selection: Binding(
                            get: { rankerViewModel.sortOption },
                            set: { rankerViewModel.setSortOption($0) }
                        )) {
                            ForEach(RankingSortOption.allCases, id: \.self) { option in
                                Text(option.rawValue).tag(option)
                            }
                        }
                        .labelsHidden()
                        .frame(width: 100)
                    }

                    // Min score slider
                    VStack(alignment: .leading, spacing: 4) {
                        HStack {
                            Text("Min Rank")
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                            Spacer()
                            Text("\(Int(rankerViewModel.minScore * 100))")
                                .font(.caption2.bold())
                                .foregroundStyle(.purple)
                        }

                        Slider(value: $rankerViewModel.minScore, in: 0...1, step: 0.05)
                            .tint(.purple)
                    }
                }
            }
            .padding(.horizontal)
            .padding(.bottom, 12)
        }
        .background(Color(nsColor: .controlBackgroundColor))
    }

    @ViewBuilder
    private var statusBadge: some View {
        switch rankerViewModel.rankingStatus {
        case .fresh:
            Text("FRESH")
                .font(.caption2.bold())
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
                .background(Color.green.opacity(0.2))
                .foregroundStyle(.green)
                .clipShape(RoundedRectangle(cornerRadius: 4))
        case .stale:
            Text("STALE")
                .font(.caption2.bold())
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
                .background(Color.orange.opacity(0.2))
                .foregroundStyle(.orange)
                .clipShape(RoundedRectangle(cornerRadius: 4))
        case .unavailable:
            EmptyView()
        case .unknown:
            EmptyView()
        }
    }

    private func formatExpiry(_ expiry: String) -> String {
        guard let date = ISO8601DateFormatter().date(from: expiry) else {
            return expiry
        }
        let formatter = DateFormatter()
        formatter.dateFormat = "MMM d, yyyy"
        return formatter.string(from: date)
    }
}

struct RankedOptionRow: View {
    let rank: OptionRank
    let symbol: String
    @State private var isHovering = false
    @State private var showStrikeAnalysis = false

    var body: some View {
        HStack(spacing: 12) {
            // Composite Score badge (Momentum Framework 0-100)
            VStack(spacing: 2) {
                Text("\(rank.compositeScoreDisplay)")
                    .font(.title3.bold())
                    .foregroundStyle(rank.compositeColor)
                Text("RANK")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
            .frame(width: 50)
            .padding(.vertical, 8)
            .background(rank.compositeColor.opacity(0.1))
            .clipShape(RoundedRectangle(cornerRadius: 8))

            Divider()

            // Contract details
            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text("$\(String(format: "%.2f", rank.strike))")
                        .font(.headline)
                    Text(rank.side == .call ? "CALL" : "PUT")
                        .font(.caption.bold())
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(rank.side == .call ? Color.green.opacity(0.2) : Color.red.opacity(0.2))
                        .foregroundStyle(rank.side == .call ? .green : .red)
                        .clipShape(RoundedRectangle(cornerRadius: 4))

                    // Signal badges
                    ForEach(rank.activeSignals, id: \.self) { signal in
                        signalBadge(signal)
                    }

                    Spacer()

                    if let mark = rank.mark {
                        Text("$\(String(format: "%.2f", mark))")
                            .font(.subheadline.bold())
                    }
                }

                HStack(spacing: 12) {
                    if let dte = rank.daysToExpiry {
                        Label("\(dte)d", systemImage: "calendar")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }

                    if let ivRank = rank.ivRank {
                        Label("IV Rank \(Int(ivRank))%", systemImage: "chart.bar.fill")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    } else if let iv = rank.impliedVol {
                        Label("\(Int(iv * 100))% IV", systemImage: "waveform.path.ecg")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }

                    if let delta = rank.delta {
                        Label("Δ \(String(format: "%.2f", delta))", systemImage: "triangle.fill")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }

                    Spacer()

                    if let volume = rank.volume {
                        Text("Vol: \(formatNumber(volume))")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                }
            }

            Divider()

            // Strike analysis button
            Button {
                showStrikeAnalysis = true
            } label: {
                Image(systemName: "chart.line.uptrend.xyaxis")
                    .font(.caption)
                    .foregroundStyle(.blue)
            }
            .buttonStyle(.borderless)
            .help("Compare strike across expirations")
        }
        .padding(12)
        .background(isHovering ? Color(nsColor: .controlBackgroundColor).opacity(0.8) : Color(nsColor: .controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(isHovering ? rank.compositeColor.opacity(0.6) : rank.compositeColor.opacity(0.3), lineWidth: isHovering ? 2 : 1)
        )
        .scaleEffect(isHovering ? 1.01 : 1.0)
        .animation(.easeInOut(duration: 0.15), value: isHovering)
        .onHover { hovering in
            isHovering = hovering
        }
        .help("Click to view detailed analysis")
        .sheet(isPresented: $showStrikeAnalysis) {
            StrikePriceComparisonView(
                symbol: symbol,
                strike: rank.strike,
                side: rank.side.rawValue
            )
        }
    }

    @ViewBuilder
    private func signalBadge(_ signal: String) -> some View {
        let (color, icon) = signalStyle(signal)
        HStack(spacing: 2) {
            Image(systemName: icon)
                .font(.caption2)
            Text(signal)
                .font(.caption2.bold())
        }
        .padding(.horizontal, 5)
        .padding(.vertical, 2)
        .background(color.opacity(0.2))
        .foregroundStyle(color)
        .clipShape(RoundedRectangle(cornerRadius: 4))
    }

    private func signalStyle(_ signal: String) -> (Color, String) {
        switch signal {
        case "BUY":
            return (.green, "checkmark.circle.fill")
        case "DISCOUNT":
            return (.blue, "tag.fill")
        case "RUNNER":
            return (.orange, "flame.fill")
        case "GREEKS":
            return (.purple, "function")
        default:
            return (.gray, "questionmark.circle")
        }
    }

    private func formatNumber(_ number: Int) -> String {
        if number >= 1000 {
            return String(format: "%.1fK", Double(number) / 1000)
        }
        return String(number)
    }
}

struct LoadingRankerView: View {
    var body: some View {
        VStack(spacing: 12) {
            ProgressView()
            Text("Loading ML rankings...")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct RankerErrorView: View {
    let message: String
    let symbol: String
    @ObservedObject var rankerViewModel: OptionsRankerViewModel

    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 48))
                .foregroundStyle(.orange)
            Text("Failed to load rankings")
                .font(.headline)
            Text(message)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal)

            HStack(spacing: 12) {
                Button("Retry") {
                    Task {
                        await rankerViewModel.refresh(for: symbol)
                    }
                }
                .buttonStyle(.bordered)

                Button("Generate Rankings") {
                    Task {
                        await rankerViewModel.triggerRankingJob(for: symbol)
                    }
                }
                .buttonStyle(.borderedProminent)
            }
        }
        .padding()
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct EmptyRankerView: View {
    let symbol: String
    @ObservedObject var rankerViewModel: OptionsRankerViewModel

    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "brain.head.profile")
                .font(.system(size: 48))
                .foregroundStyle(.purple)
            Text("No rankings available for \(symbol)")
                .font(.headline)
            Text("Options rankings haven't been generated yet. Generate rankings to see ML-scored options contracts.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal)

            Button("Generate Rankings") {
                Task {
                    await rankerViewModel.triggerRankingJob(for: symbol)
                }
            }
            .buttonStyle(.borderedProminent)

            Text("This will take about 30 seconds")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding()
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct GeneratingRankingsView: View {
    var body: some View {
        VStack(spacing: 16) {
            ProgressView()
                .scaleEffect(1.5)

            Text("Generating ML rankings...")
                .font(.headline)

            Text("This may take 20-30 seconds while we score options contracts")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

#Preview {
    OptionsRankerView()
        .environmentObject(AppViewModel())
        .frame(width: 400, height: 600)
}
