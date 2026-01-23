import SwiftUI

/// Main Contract Workbench Inspector View
/// Displays detailed analysis for a selected option contract
/// Uses Apple-standard inspector pattern with progressive disclosure
struct ContractWorkbenchView: View {
    let rank: OptionRank
    let symbol: String
    let allRankings: [OptionRank]
    
    @EnvironmentObject var appViewModel: AppViewModel
    @Environment(\.dismiss) var dismiss
    
    // Local state for the active tab
    @State private var selectedTab: ContractWorkbenchTab = .overview
    
    var body: some View {
        ScrollView {
            VStack(spacing: 0) {
                // Header (persistent at top)
                ContractWorkbenchHeader(
                    rank: rank,
                    symbol: symbol,
                    onClose: {
                        appViewModel.selectedContractState.closeWorkbench()
                    },
                    onAddToStrategy: {
                        // TODO: Implement add to strategy
                    }
                )
                .padding(.horizontal)
                .padding(.top, 16)
                .padding(.bottom, 12)
                
                Divider()
                
                // Key Metrics Strip
                KeyMetricsStrip(rank: rank)
                    .padding(.horizontal)
                    .padding(.vertical, 12)
                
                Divider()
                
                // Tab Picker
                Picker("", selection: $selectedTab) {
                    ForEach(ContractWorkbenchTab.allCases) { tab in
                        Label(tab.displayName, systemImage: tab.icon)
                            .tag(tab)
                    }
                }
                .pickerStyle(.segmented)
                .padding(.horizontal)
                .padding(.top, 12)
                .padding(.bottom, 8)
                
                // Tab Content
                Group {
                    switch selectedTab {
                    case .overview:
                        OverviewTabView(rank: rank, symbol: symbol)
                    case .whyRanked:
                        WhyRankedTabView(
                            rank: rank, 
                            strategy: appViewModel.selectedContractState.gaStrategy,
                            rankingMode: appViewModel.optionsRankerViewModel.rankingMode
                        )
                    case .contract:
                        ContractTabView(rank: rank, symbol: symbol)
                    case .surfaces:
                        SurfacesTabPlaceholder(rank: rank, symbol: symbol)
                    case .risk:
                        RiskTabPlaceholder(rank: rank)
                    case .alerts:
                        AlertsTabPlaceholder(rank: rank)
                    case .notes:
                        NotesTabPlaceholder(rank: rank)
                    }
                }
                .padding(.horizontal)
                .padding(.top, 8)
                .padding(.bottom, 16)
            }
        }
        // Width is controlled by .inspectorColumnWidth() at parent level
        .frame(minHeight: 600)
        .background(Color(nsColor: .windowBackgroundColor))
        .onAppear {
            // Sync local tab state with app state
            selectedTab = appViewModel.selectedContractState.workbenchTab
        }
        .onChange(of: selectedTab) { _, newTab in
            // Update app state when tab changes
            appViewModel.selectedContractState.workbenchTab = newTab
        }
        .onChange(of: appViewModel.selectedContractState.selectedRank?.id) { _, _ in
            // Reset to overview when selection changes (unless remembering last tab)
            if !appViewModel.selectedContractState.rememberLastTab {
                selectedTab = .overview
            }
        }
    }
}

// MARK: - Placeholder Views (will be implemented in later phases)

private struct SurfacesTabPlaceholder: View {
    let rank: OptionRank
    let symbol: String
    
    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "cube.fill")
                .font(.system(size: 48))
                .foregroundStyle(.secondary)
            Text("Surfaces Tab")
                .font(.headline)
            Text("Interactive Greeks and IV surfaces coming soon")
                .font(.caption)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding()
    }
}

private struct RiskTabPlaceholder: View {
    let rank: OptionRank
    
    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 48))
                .foregroundStyle(.secondary)
            Text("Risk Tab")
                .font(.headline)
            Text("Payoff diagrams and P&L calculator coming soon")
                .font(.caption)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding()
    }
}

private struct AlertsTabPlaceholder: View {
    let rank: OptionRank
    
    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "bell.fill")
                .font(.system(size: 48))
                .foregroundStyle(.secondary)
            Text("Alerts Tab")
                .font(.headline)
            Text("Contract monitoring and alerts coming soon")
                .font(.caption)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding()
    }
}

private struct NotesTabPlaceholder: View {
    let rank: OptionRank
    
    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "note.text")
                .font(.system(size: 48))
                .foregroundStyle(.secondary)
            Text("Notes Tab")
                .font(.headline)
            Text("Trade journal and notes coming soon")
                .font(.caption)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding()
    }
}

// MARK: - Preview

#Preview {
    ContractWorkbenchView(
        rank: OptionRank.example,
        symbol: "AAPL",
        allRankings: [OptionRank.example]
    )
    .environmentObject(AppViewModel())
    .frame(width: 450, height: 800)
}
