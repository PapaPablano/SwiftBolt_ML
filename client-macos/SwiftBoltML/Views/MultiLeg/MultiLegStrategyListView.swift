import SwiftUI

struct MultiLegStrategyListView: View {
    @EnvironmentObject private var appViewModel: AppViewModel
    @StateObject private var viewModel = MultiLegViewModel()
    @State private var showCreateSheet = false
    @State private var selectedStrategyId: String?
    @State private var strategyToDelete: MultiLegStrategy?
    @State private var listDeleteError: String?

    var body: some View {
        VStack(spacing: 0) {
            // Header with stats
            headerSection

            Divider()

            // Filters
            filterSection

            Divider()

            // Content
            contentSection
        }
        .sheet(isPresented: $showCreateSheet) {
            MultiLegCreateStrategyView(viewModel: viewModel, isPresented: $showCreateSheet)
        }
        .sheet(item: $viewModel.selectedStrategy) { strategy in
            MultiLegStrategyDetailView(
                viewModel: viewModel,
                strategy: strategy
            )
            .environmentObject(appViewModel)
        }
        .task {
            await viewModel.loadStrategies(reset: true)
        }
        .confirmationDialog("Delete Strategy", isPresented: Binding(
            get: { strategyToDelete != nil },
            set: { if !$0 { strategyToDelete = nil } }
        ), titleVisibility: .visible) {
            Button("Delete", role: .destructive) {
                guard let s = strategyToDelete else { return }
                strategyToDelete = nil
                Task {
                    let success = await viewModel.deleteStrategy(strategyId: s.id)
                    if !success {
                        listDeleteError = viewModel.errorMessage ?? "Delete failed."
                    }
                }
            }
            Button("Cancel", role: .cancel) { strategyToDelete = nil }
        } message: {
            if let s = strategyToDelete {
                Text("Permanently delete '\(s.name)'? This cannot be undone.")
            }
        }
        .alert("Delete Failed", isPresented: Binding(
            get: { listDeleteError != nil },
            set: { if !$0 { listDeleteError = nil } }
        )) {
            Button("OK") { listDeleteError = nil }
        } message: {
            if let msg = listDeleteError { Text(msg) }
        }
    }

    // MARK: - Header Section

    private var headerSection: some View {
        HStack(spacing: 16) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Multi-Leg Strategies")
                    .font(.title2.bold())

                HStack(spacing: 12) {
                    StatBadge(
                        label: "Open",
                        value: "\(viewModel.openStrategiesCount)",
                        color: .green
                    )

                    StatBadge(
                        label: "Total P&L",
                        value: String(format: "%+.0f", viewModel.totalPL),
                        color: viewModel.totalPL >= 0 ? .green : .red
                    )

                    if viewModel.criticalAlertCount > 0 {
                        StatBadge(
                            label: "Alerts",
                            value: "\(viewModel.criticalAlertCount)",
                            color: .red
                        )
                    }
                }
            }

            Spacer()

            HStack(spacing: 8) {
                Button {
                    Task { await viewModel.refresh() }
                } label: {
                    Image(systemName: "arrow.clockwise")
                }
                .buttonStyle(.bordered)
                .disabled(viewModel.isLoading)

                Button {
                    showCreateSheet = true
                } label: {
                    Label("New Strategy", systemImage: "plus")
                }
                .buttonStyle(.borderedProminent)
            }
        }
        .padding()
    }

    // MARK: - Filter Section

    private var filterSection: some View {
        HStack(spacing: 12) {
            // Search
            HStack {
                Image(systemName: "magnifyingglass")
                    .foregroundColor(.secondary)
                TextField("Search strategies...", text: deferredBinding(get: { viewModel.searchText }, set: { viewModel.searchText = $0 }))
                    .textFieldStyle(.plain)

                if !viewModel.searchText.isEmpty {
                    Button {
                        DispatchQueue.main.async { viewModel.searchText = "" }
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundColor(.secondary)
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(8)
            .background(Color.gray.opacity(0.1))
            .cornerRadius(8)
            .frame(maxWidth: 200)

            // Status filter
            Picker("Status", selection: deferredBinding(get: { viewModel.statusFilter }, set: { viewModel.statusFilter = $0 })) {
                ForEach(StrategyStatusFilter.allCases, id: \.self) { status in
                    Text(status.rawValue).tag(status)
                }
            }
            .pickerStyle(.segmented)
            .frame(maxWidth: 250)

            // Sort
            Picker("Sort", selection: deferredBinding(get: { viewModel.sortOption }, set: { viewModel.sortOption = $0 })) {
                ForEach(StrategySortOption.allCases, id: \.self) { option in
                    Text(option.rawValue).tag(option)
                }
            }
            .frame(width: 120)

            Spacer()

            // Strategy type filter
            Menu {
                Button("All Types") {
                    DispatchQueue.main.async { viewModel.strategyTypeFilter = nil }
                }
                Divider()
                ForEach(StrategyType.allCases, id: \.self) { type in
                    Button(type.displayName) {
                        DispatchQueue.main.async { viewModel.strategyTypeFilter = type }
                    }
                }
            } label: {
                HStack {
                    Text(viewModel.strategyTypeFilter?.displayName ?? "All Types")
                    Image(systemName: "chevron.down")
                }
            }

            if viewModel.strategyTypeFilter != nil || !viewModel.searchText.isEmpty {
                Button("Clear") {
                    DispatchQueue.main.async { viewModel.clearFilters() }
                }
                .buttonStyle(.borderless)
                .foregroundColor(.accentColor)
            }
        }
        .padding(.horizontal)
        .padding(.vertical, 8)
    }

    // MARK: - Content Section

    @ViewBuilder
    private var contentSection: some View {
        if viewModel.isLoading && viewModel.strategies.isEmpty {
            loadingView
        } else if let error = viewModel.errorMessage {
            errorView(error)
        } else if viewModel.filteredStrategies.isEmpty {
            emptyView
        } else {
            strategyList
        }
    }

    private var loadingView: some View {
        VStack(spacing: 16) {
            ProgressView()
            Text("Loading strategies...")
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private func errorView(_ error: String) -> some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle")
                .font(.largeTitle)
                .foregroundColor(.orange)
            Text("Error loading strategies")
                .font(.headline)
            Text(error)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)

            Button("Retry") {
                Task { await viewModel.refresh() }
            }
            .buttonStyle(.bordered)
        }
        .padding()
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var emptyView: some View {
        VStack(spacing: 16) {
            Image(systemName: "rectangle.stack.badge.plus")
                .font(.system(size: 48))
                .foregroundColor(.secondary)

            Text("No strategies found")
                .font(.headline)

            if viewModel.statusFilter != .all || viewModel.strategyTypeFilter != nil || !viewModel.searchText.isEmpty {
                Text("Try adjusting your filters")
                    .foregroundColor(.secondary)

                Button("Clear Filters") {
                    viewModel.clearFilters()
                }
                .buttonStyle(.bordered)
            } else {
                Text("Create your first multi-leg options strategy")
                    .foregroundColor(.secondary)

                Button {
                    showCreateSheet = true
                } label: {
                    Label("Create Strategy", systemImage: "plus")
                }
                .buttonStyle(.borderedProminent)
            }
        }
        .padding()
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var strategyList: some View {
        ScrollView {
            LazyVStack(spacing: 8) {
                ForEach(viewModel.filteredStrategies) { strategy in
                    MultiLegStrategyRow(strategy: strategy, onDelete: { strategyToDelete = strategy })
                        .contentShape(Rectangle())
                        .onTapGesture {
                            viewModel.selectStrategy(strategy)
                        }
                        .contextMenu {
                            Button("Delete", role: .destructive) {
                                strategyToDelete = strategy
                            }
                        }
                }

                if viewModel.hasMore {
                    ProgressView()
                        .padding()
                        .onAppear {
                            Task { await viewModel.loadMore() }
                        }
                }
            }
            .padding()
        }
    }
}

// MARK: - Stat Badge

struct StatBadge: View {
    let label: String
    let value: String
    let color: Color

    var body: some View {
        HStack(spacing: 4) {
            Text(label)
                .font(.caption)
                .foregroundColor(.secondary)
            Text(value)
                .font(.caption.bold())
                .foregroundColor(color)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(color.opacity(0.1))
        .cornerRadius(6)
    }
}

// MARK: - Strategy Row

struct MultiLegStrategyRow: View {
    let strategy: MultiLegStrategy
    var onDelete: (() -> Void)?

    var body: some View {
        HStack(spacing: 12) {
            // Status indicator
            Circle()
                .fill(strategy.status.color)
                .frame(width: 10, height: 10)

            // Main info
            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text(strategy.name)
                        .font(.headline)

                    Text(strategy.underlyingTicker)
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(Color.gray.opacity(0.15))
                        .cornerRadius(4)
                }

                HStack(spacing: 8) {
                    Text(strategy.strategyType.displayName)
                        .font(.caption)
                        .foregroundColor(.secondary)

                    if let legs = strategy.legs {
                        Text("\(legs.filter { !$0.isClosed }.count)/\(legs.count) legs")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }

                    Text(strategy.dteLabel)
                        .font(.caption)
                        .foregroundColor(dteColor)
                }
            }

            Spacer()

            // Greeks summary
            if strategy.combinedDelta != nil {
                greeksSummary
            }

            // P&L
            VStack(alignment: .trailing, spacing: 2) {
                Text(strategy.plFormatted)
                    .font(.headline)
                    .foregroundColor(strategy.plColor)

                Text(strategy.plPctFormatted)
                    .font(.caption)
                    .foregroundColor(strategy.plColor)
            }
            .frame(minWidth: 80, alignment: .trailing)

            // Alerts badge
            if strategy.activeAlertCount > 0 {
                alertBadge
            }

            // Delete (visible for all strategies, including 0-leg)
            if let onDelete = onDelete {
                Button {
                    onDelete()
                } label: {
                    Image(systemName: "trash")
                        .font(.system(size: 12))
                        .foregroundColor(.secondary)
                }
                .buttonStyle(.plain)
                .help("Delete strategy")
            }

            // Chevron
            Image(systemName: "chevron.right")
                .foregroundColor(.secondary)
        }
        .padding()
        .background(Color.gray.opacity(0.05))
        .cornerRadius(8)
    }

    private var dteColor: Color {
        guard let dte = strategy.minDTE else { return .secondary }
        if dte <= 3 { return .red }
        if dte <= 7 { return .orange }
        return .secondary
    }

    private var greeksSummary: some View {
        HStack(spacing: 8) {
            if let delta = strategy.combinedDelta {
                VStack(spacing: 0) {
                    Text("Delta")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                    Text(String(format: "%.2f", delta))
                        .font(.caption.monospacedDigit())
                }
            }

            if let theta = strategy.combinedTheta {
                VStack(spacing: 0) {
                    Text("Theta")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                    Text(String(format: "%.2f", theta))
                        .font(.caption.monospacedDigit())
                        .foregroundColor(theta < 0 ? .red : .green)
                }
            }
        }
        .padding(.horizontal, 8)
    }

    private var alertBadge: some View {
        ZStack {
            Circle()
                .fill(strategy.criticalAlertCount > 0 ? Color.red : Color.orange)
                .frame(width: 24, height: 24)

            Text("\(strategy.activeAlertCount)")
                .font(.caption2.bold())
                .foregroundColor(.white)
        }
    }
}

// MARK: - Preview

#Preview {
    MultiLegStrategyListView()
        .frame(width: 900, height: 600)
}
