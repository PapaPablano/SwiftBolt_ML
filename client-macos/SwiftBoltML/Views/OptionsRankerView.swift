import SwiftUI

struct OptionsRankerView: View {
    @EnvironmentObject var appViewModel: AppViewModel

    private var rankerViewModel: OptionsRankerViewModel {
        appViewModel.optionsRankerViewModel
    }

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
        .onChange(of: appViewModel.selectedSymbol) { _, newValue in
            if let symbol = newValue?.ticker {
                Task {
                    await rankerViewModel.ensureLoaded(for: symbol)
                }
            }
        }
        .onAppear {
            if let symbol = appViewModel.selectedSymbol?.ticker {
                Task {
                    await rankerViewModel.ensureLoaded(for: symbol)
                }
            }
        }
        .onDisappear {
            rankerViewModel.stopAutoRefresh()
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
    @EnvironmentObject var appViewModel: AppViewModel
    @State private var selectedModalRank: OptionRank?

    var body: some View {
        VStack(spacing: 0) {
            // Header with title and filters
            RankerHeader(
                rankerViewModel: rankerViewModel,
                symbol: symbol
            )

            Divider()

            // Ranked options list
            if rankerViewModel.filteredRankings.isEmpty {
                VStack(spacing: 12) {
                    Image(systemName: "line.3.horizontal.decrease.circle")
                        .font(.system(size: 36))
                        .foregroundStyle(.purple)
                    Text("No contracts match the current filters")
                        .font(.headline)
                    Text("Try relaxing the filters or disabling the GA filter.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal)

                    HStack(spacing: 12) {
                        if rankerViewModel.useGAFilter {
                            Button("Disable GA Filter") {
                                rankerViewModel.useGAFilter = false
                            }
                            .buttonStyle(.borderedProminent)
                        }

                        Button("Reset Filters") {
                            rankerViewModel.minScore = 0
                            rankerViewModel.setSignalFilter(.all)
                            rankerViewModel.setSortOption(.composite)
                            rankerViewModel.clearPriceFilters()
                        }
                        .buttonStyle(.bordered)
                    }
                }
                .padding()
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                ScrollView {
                    LazyVStack(spacing: 8) {
                        ForEach(rankerViewModel.filteredRankings) { rank in
                            RankedOptionRow(
                                rank: rank,
                                liveQuote: rankerViewModel.liveQuotes[rank.contractSymbol],
                                symbol: symbol,
                                rankingMode: rankerViewModel.rankingMode
                            )
                                .padding(.horizontal)
                                .background(
                                    appViewModel.selectedContractState.isSelected(rank) ?
                                        Color.accentColor.opacity(0.1) : Color.clear
                                )
                                .onTapGesture {
                                    // Single click: Open inspector workbench
                                    appViewModel.selectedContractState.select(rank: rank, openWorkbench: true)
                                }
                                .onTapGesture(count: 2) {
                                    // Double click: Open full modal
                                    selectedModalRank = rank
                                }
                        }
                    }
                    .padding(.vertical, 8)
                }
            }
        }
        .sheet(item: $selectedModalRank) { rank in
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

                if rankerViewModel.isRefreshingQuotes {
                    HStack(spacing: 4) {
                        ProgressView()
                            .scaleEffect(0.6)
                        Text("Refreshing quotes…")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                } else if let status = quoteStatusText() {
                    Text(status)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }

                if rankerViewModel.isAutoRefreshing, let interval = rankerViewModel.autoRefreshInterval {
                    HStack(spacing: 4) {
                        Circle()
                            .fill(Color.green)
                            .frame(width: 6, height: 6)
                            .shadow(color: .green.opacity(0.6), radius: 3)
                        Text("LIVE • \(Int(interval))s")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                }

                Text("\(rankerViewModel.filteredRankings.count) contracts")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .padding(.horizontal)
            .padding(.top, 12)

            // Filters
            VStack(spacing: 8) {
                // Row 0: Entry/Exit/Monitor Mode Toggle
                HStack {
                    Text("Ranking Mode")
                        .font(.caption2)
                        .foregroundStyle(.secondary)

                    Picker("", selection: $rankerViewModel.rankingMode) {
                        ForEach(RankingMode.allCases) { mode in
                            Label(mode.displayName, systemImage: mode.icon)
                                .tag(mode)
                        }
                    }
                    .pickerStyle(.segmented)
                    .frame(width: 220)

                    Spacer()

                    // Mode description
                    Text(rankerViewModel.rankingMode.description)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
                .onChange(of: rankerViewModel.rankingMode) { _, _ in
                    Task {
                        await rankerViewModel.loadRankings(for: symbol)
                    }
                }

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

                // Row 3: Price range filter
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text("Price Range")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                        Spacer()
                        Button("Clear") {
                            rankerViewModel.clearPriceFilters()
                        }
                        .font(.caption2)
                        .buttonStyle(.borderless)
                        .disabled(rankerViewModel.minPriceInput.isEmpty && rankerViewModel.maxPriceInput.isEmpty)
                    }

                    HStack(spacing: 8) {
                        TextField("Min $", text: $rankerViewModel.minPriceInput)
                            .textFieldStyle(.roundedBorder)
                            .frame(width: 80)

                        Text("–")
                            .foregroundStyle(.secondary)

                        TextField("Max $", text: $rankerViewModel.maxPriceInput)
                            .textFieldStyle(.roundedBorder)
                            .frame(width: 80)
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
            HStack(spacing: 4) {
                Text("FRESH")
                    .font(.caption2.bold())
                // Fix D: Show relative timestamp if available
                if let lastRefresh = rankerViewModel.lastRankingRefresh {
                    Text("(\(relativeTimeString(from: lastRefresh)))")
                        .font(.caption2)
                }
            }
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(Color.green.opacity(0.2))
            .foregroundStyle(.green)
            .clipShape(RoundedRectangle(cornerRadius: 4))
        case .stale:
            HStack(spacing: 4) {
                Text("STALE")
                    .font(.caption2.bold())
                // Fix D: Show relative timestamp if available
                if let lastRefresh = rankerViewModel.lastRankingRefresh {
                    Text("(\(relativeTimeString(from: lastRefresh)))")
                        .font(.caption2)
                }
            }
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(Color.orange.opacity(0.2))
            .foregroundStyle(.orange)
            .clipShape(RoundedRectangle(cornerRadius: 4))
        case .unavailable:
            EmptyView()
        case .unknown:
            // Fix D: Show unknown badge instead of hiding it completely
            Text("UNKNOWN")
                .font(.caption2.bold())
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
                .background(Color.gray.opacity(0.2))
                .foregroundStyle(.gray)
                .clipShape(RoundedRectangle(cornerRadius: 4))
        }
    }

    private func relativeTimeString(from date: Date) -> String {
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .abbreviated
        return formatter.localizedString(for: date, relativeTo: Date())
    }

    private func formatExpiry(_ expiry: String) -> String {
        guard let date = ISO8601DateFormatter().date(from: expiry) else {
            return expiry
        }
        let formatter = DateFormatter()
        formatter.dateFormat = "MMM d, yyyy"
        return formatter.string(from: date)
    }

    private func quoteStatusText() -> String? {
        if rankerViewModel.liveQuotes.isEmpty, rankerViewModel.lastQuoteRefresh == nil {
            return "Quotes pending (using snapshot)"
        }

        guard let last = rankerViewModel.lastQuoteRefresh else {
            return nil
        }

        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .abbreviated
        let relative = formatter.localizedString(for: last, relativeTo: Date())
        return "Quotes \(relative)"
    }
}

struct RankedOptionRow: View {
    let rank: OptionRank
    let liveQuote: OptionContractQuote?
    let symbol: String
    let rankingMode: RankingMode
    var symbolId: String = ""
    @State private var isHovering = false
    @State private var showStrikeAnalysis = false
    @State private var showHistoryChart = false
    @State private var showAddToStrategy = false
    
    // Mode-specific rank display
    private var displayRank: Int {
        switch rankingMode {
        case .entry:
            return Int(rank.entryRank ?? rank.effectiveCompositeRank)
        case .exit:
            return Int(rank.exitRank ?? rank.effectiveCompositeRank)
        case .monitor:
            return rank.compositeScoreDisplay
        }
    }
    
    private var rankColor: Color {
        switch rankingMode {
        case .entry:
            let r = rank.entryRank ?? rank.effectiveCompositeRank
            return rankScoreColor(r)
        case .exit:
            let r = rank.exitRank ?? rank.effectiveCompositeRank
            return rankScoreColor(r)
        case .monitor:
            return rank.compositeColor
        }
    }
    
    private func rankScoreColor(_ score: Double) -> Color {
        if score >= 75 { return .green }
        if score >= 60 { return .blue }
        if score >= 45 { return .orange }
        return .red
    }

    var body: some View {
        HStack(spacing: 12) {
            // Mode-specific Score badge
            VStack(spacing: 2) {
                Text("\(displayRank)")
                    .font(.title3.bold())
                    .foregroundStyle(rankColor)
                Text(rankingMode.displayName.uppercased())
                    .font(.system(size: 8, weight: .bold))
                    .foregroundStyle(.secondary)
            }
            .frame(width: 50)
            .padding(.vertical, 8)
            .background(rankColor.opacity(0.1))
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

                    quoteStack
                }

                if let metaLine = providerMetaLine {
                    HStack(spacing: 8) {
                        if let price = rank.priceProvider {
                            Label("Px: \(price.uppercased())", systemImage: "bolt.fill")
                        }
                        if let oi = rank.oiProvider {
                            Label("OI: \(oi.uppercased())", systemImage: "chart.bar.doc.horizontal")
                        }
                        if let history = rank.historyCoverageLabel {
                            Label(history, systemImage: "clock.arrow.circlepath")
                        }
                    }
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                    .truncationMode(.tail)
                    .accessibilityElement(children: .ignore)
                    .accessibilityLabel(metaLine)
                    .accessibilityHint("Data providers and history coverage")
                }

                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 12) {
                        if let dte = rank.daysToExpiry {
                            metricBlock(title: "DTE:", value: "\(dte)", systemImage: "calendar")
                        }
                        if let ivRank = rank.ivRank {
                            metricBlock(title: "IV Rank", value: "\(Int(ivRank))%", systemImage: "chart.bar.fill")
                        } else if let iv = rank.impliedVol {
                            metricBlock(title: "IV", value: "\(Int(iv * 100))%", systemImage: "waveform.path.ecg")
                        }
                        if let delta = rank.delta {
                            metricBlock(title: "Delta", value: String(format: "%.2f", delta), systemImage: "triangle.fill")
                        }
                        if let volume = rank.volume {
                            metricBlock(title: "Vol", value: formatNumber(volume), systemImage: "chart.bar.xaxis")
                        }
                        if let sp = rank.spreadPctDisplay {
                            metricBlock(title: "Spread %", value: String(format: "%.1f%%", sp), systemImage: "arrow.left.and.right")
                        }
                        if let liq = rank.liquidityScore {
                            metricBlock(title: "Liquidity", value: String(format: "%.2f", liq), systemImage: "drop.fill", color: rank.liquidityColor)
                        }
                        if rank.runAtDate != nil {
                            metricBlock(title: "Snapshot", value: rank.markAgeLabel, systemImage: "clock", color: quoteAgeColor)
                        }
                    }
                }
            }

            Divider()

            // Action buttons
            VStack(spacing: 8) {
                // Add to Strategy button
                Button {
                    showAddToStrategy = true
                } label: {
                    Image(systemName: "plus.rectangle.on.folder")
                        .font(.caption)
                        .foregroundStyle(.purple)
                }
                .buttonStyle(.borderless)
                .help("Add to Strategy")

                // Historical price chart button
                Button {
                    showHistoryChart = true
                } label: {
                    Image(systemName: "chart.line.uptrend.xyaxis")
                        .font(.caption)
                        .foregroundStyle(.blue)
                }
                .buttonStyle(.borderless)
                .help("View historical mark price chart")
            }
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
        .sheet(isPresented: $showHistoryChart) {
            OptionHistoryChartView(
                symbol: symbol,
                strike: rank.strike,
                side: rank.side.rawValue,
                expiry: rank.expiry,
                contractSymbol: rank.contractSymbol
            )
        }
        .sheet(isPresented: $showAddToStrategy) {
            AddToStrategySheet(
                optionRank: rank,
                symbol: symbol,
                symbolId: symbolId
            )
        }
    }

    @ViewBuilder
    private var quoteStack: some View {
        let resolved = resolvedQuote
        let displayBid = resolved.bid
        let displayAsk = resolved.ask
        let displayMark = resolved.mark

        if let bid = displayBid, let ask = displayAsk {
            VStack(alignment: .trailing, spacing: 2) {
                Text("Bid / Ask")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                HStack(spacing: 4) {
                    Text("$\(String(format: "%.2f", bid))")
                        .font(.title3.bold())
                        .foregroundStyle(.green)
                    Text("/")
                        .font(.title3.bold())
                        .foregroundStyle(.secondary)
                    Text("$\(String(format: "%.2f", ask))")
                        .font(.title3.bold())
                        .foregroundStyle(.red)
                }
                if let label = quoteAgeLabel {
                    Text(label)
                        .font(.caption2)
                        .foregroundStyle(quoteAgeColor)
                }
            }
        } else if let mark = displayMark {
            VStack(alignment: .trailing, spacing: 2) {
                Text(resolved.isLive ? "Mid (live)" : "Mid (snapshot)")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                Text("$\(String(format: "%.2f", mark))")
                    .font(.title3.bold())
                if let label = quoteAgeLabel {
                    Text(label)
                        .font(.caption2)
                        .foregroundStyle(quoteAgeColor)
                }
            }
        } else {
            Text("No quote")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
    }

    private var quoteAgeLabel: String? {
        let resolved = resolvedQuote
        guard let secs = resolved.ageSeconds, let label = resolved.ageLabel else { return nil }
        if secs > 900 {
            return "Stale \(label)"
        }
        return "\(resolved.isLive ? "Live" : "Snapshot") \(label)"
    }

    private var quoteAgeColor: Color {
        let ageSeconds = resolvedQuote.ageSeconds
        guard let secs = ageSeconds else { return .secondary }
        return secs > 900 ? .orange : .secondary
    }

    private struct ResolvedQuote {
        let bid: Double?
        let ask: Double?
        let mark: Double?
        let ageLabel: String?
        let ageSeconds: TimeInterval?
        let isLive: Bool
    }

    private var resolvedQuote: ResolvedQuote {
        let liveDate = liveQuote?.updatedAtDate
        let rankDate = rank.runAtDate
        let shouldUseLive: Bool

        if let liveDate, let rankDate {
            shouldUseLive = liveDate >= rankDate
        } else {
            shouldUseLive = liveDate != nil
        }

        if shouldUseLive, let liveQuote {
            return ResolvedQuote(
                bid: liveQuote.bid,
                ask: liveQuote.ask,
                mark: liveQuote.mark ?? liveQuote.last,
                ageLabel: liveQuote.ageLabel,
                ageSeconds: liveQuote.ageSeconds,
                isLive: true
            )
        }

        return ResolvedQuote(
            bid: rank.bid,
            ask: rank.ask,
            mark: rank.derivedMark,
            ageLabel: rank.markAgeLabel,
            ageSeconds: rank.markAgeSeconds,
            isLive: false
        )
    }

    @ViewBuilder
    private func signalBadge(_ signal: String) -> some View {
        let (color, icon) = signalStyle(signal)
        Image(systemName: icon)
            .font(.caption.bold())
            .foregroundStyle(.white)
            .frame(width: 20, height: 20)
            .background(color)
            .clipShape(RoundedRectangle(cornerRadius: 4))
            .help(signal)
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

    private func metricBlock(
        title: String,
        value: String,
        systemImage: String,
        color: Color = .secondary
    ) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Label(title, systemImage: systemImage)
                .font(.caption2)
                .foregroundStyle(color)
            Text(value)
                .font(.body.bold())
                .foregroundStyle(.primary)
        }
    }

    private var providerMetaLine: String? {
        let parts = [
            rank.priceProvider.map { "Price: \($0.uppercased())" },
            rank.oiProvider.map { "OI: \($0.uppercased())" },
            rank.historyCoverageLabel.map { "History: \($0)" }
        ].compactMap { $0 }
        return parts.isEmpty ? nil : parts.joined(separator: " • ")
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

            Text("This takes about 5 seconds")
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

            Text("Scoring options contracts...")
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
