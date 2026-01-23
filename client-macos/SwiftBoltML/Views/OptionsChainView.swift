import SwiftUI

struct OptionsChainView: View {
    @EnvironmentObject var appViewModel: AppViewModel

    private var viewModel: OptionsChainViewModel {
        appViewModel.optionsChainViewModel
    }

    var body: some View {
        VStack(spacing: 0) {
            // Tab selector
            Picker("", selection: $appViewModel.selectedOptionsTab) {
                Label("ML Ranker", systemImage: "brain.head.profile").tag(0)
                Label("Full Chain", systemImage: "chart.bar.doc.horizontal").tag(1)
            }
            .pickerStyle(.segmented)
            .padding(.horizontal)
            .padding(.vertical, 8)
            .background(Color(nsColor: .windowBackgroundColor))

            Divider()

            // Tab content
            if appViewModel.selectedOptionsTab == 0 {
                OptionsRankerView()
                    .environmentObject(appViewModel)
            } else {
                OptionsChainContent()
                    .environmentObject(appViewModel)
            }
        }
        .toolbar {
            ToolbarItem(placement: .automatic) {
                Button {
                    appViewModel.selectedContractState.isWorkbenchPresented.toggle()
                } label: {
                    Label(
                        "Toggle Workbench",
                        systemImage: appViewModel.selectedContractState.isWorkbenchPresented ? "sidebar.right" : "sidebar.trailing"
                    )
                }
                .disabled(appViewModel.selectedContractState.selectedRank == nil)
                .help("Toggle Contract Workbench (⌘⌥I)")
                .keyboardShortcut("i", modifiers: [.command, .option])
            }
        }
        // Inspector moved to DetailView level for proper layout coordination
    }
}

struct OptionsChainContent: View {
    @EnvironmentObject var appViewModel: AppViewModel

    private var viewModel: OptionsChainViewModel {
        appViewModel.optionsChainViewModel
    }

    var body: some View {
        Group {
            if viewModel.isLoading {
                LoadingOptionsView()
            } else if let error = viewModel.errorMessage {
                OptionsErrorView(message: error) {
                    Task {
                        await viewModel.refresh(for: appViewModel.selectedSymbol?.ticker ?? "")
                    }
                }
            } else if viewModel.optionsChain == nil {
                EmptyOptionsView()
            } else {
                OptionsChainList()
                    .environmentObject(appViewModel)
            }
        }
    }
}

struct OptionsChainList: View {
    @EnvironmentObject var appViewModel: AppViewModel

    private var viewModel: OptionsChainViewModel {
        appViewModel.optionsChainViewModel
    }

    var body: some View {
        VStack(spacing: 0) {
            // Header with expiration selector
            OptionsChainHeader()
                .environmentObject(appViewModel)

            Divider()

            // Options chain table
            ScrollView {
                VStack(spacing: 0) {
                    // Calls and Puts side by side
                    HStack(alignment: .top, spacing: 0) {
                        // Calls (left side)
                        VStack(spacing: 0) {
                            Text("CALLS")
                                .font(.caption)
                                .fontWeight(.bold)
                                .foregroundStyle(.green)
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 8)
                                .background(Color.green.opacity(0.1))

                            ForEach(viewModel.callContracts) { contract in
                                OptionContractRow(contract: contract)
                            }
                        }
                        .frame(maxWidth: .infinity)

                        Divider()

                        // Puts (right side)
                        VStack(spacing: 0) {
                            Text("PUTS")
                                .font(.caption)
                                .fontWeight(.bold)
                                .foregroundStyle(.red)
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 8)
                                .background(Color.red.opacity(0.1))

                            ForEach(viewModel.putContracts) { contract in
                                OptionContractRow(contract: contract)
                            }
                        }
                        .frame(maxWidth: .infinity)
                    }
                }
            }
        }
        .onChange(of: viewModel.selectedExpiration) { oldValue, newValue in
            // Reload options chain when expiration changes
            if let symbol = appViewModel.selectedSymbol?.ticker, oldValue != newValue {
                Task {
                    await viewModel.loadOptionsChain(for: symbol)
                }
            }
        }
    }
}

struct OptionsChainHeader: View {
    @EnvironmentObject var appViewModel: AppViewModel

    private var viewModel: OptionsChainViewModel {
        appViewModel.optionsChainViewModel
    }

    var body: some View {
        VStack(spacing: 8) {
            HStack {
                Text("Expiration:")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)

                Picker("", selection: Binding(
                    get: { viewModel.selectedExpiration },
                    set: { (expiration: TimeInterval?) in viewModel.selectExpiration(expiration) }
                )) {
                    Text("All").tag(nil as TimeInterval?)
                    ForEach(viewModel.availableExpirations, id: \.self) { expiration in
                        Text(formatExpiration(expiration))
                            .tag(expiration as TimeInterval?)
                    }
                }
                .labelsHidden()

                Spacer()

                Button {
                    Task {
                        await viewModel.refresh(for: appViewModel.selectedSymbol?.ticker ?? "")
                    }
                } label: {
                    Image(systemName: "arrow.clockwise")
                }
                .buttonStyle(.borderless)
            }
            .padding(.horizontal)
            .padding(.vertical, 8)
        }
    }

    private func formatExpiration(_ timestamp: TimeInterval) -> String {
        let date = Date(timeIntervalSince1970: timestamp)
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        return formatter.string(from: date)
    }
}

struct OptionContractRow: View {
    let contract: OptionContract

    var body: some View {
        VStack(spacing: 4) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(String(format: "$%.2f", contract.strike))
                        .font(.headline)

                    if let iv = contract.impliedVolatility {
                        Text(String(format: "IV: %.1f%%", iv * 100))
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                }

                Spacer()

                VStack(alignment: .trailing, spacing: 2) {
                    Text(String(format: "$%.2f", contract.mark))
                        .font(.subheadline)
                        .fontWeight(.semibold)

                    HStack(spacing: 4) {
                        Text(String(format: "%.2f", contract.bid))
                        Text("×")
                        Text(String(format: "%.2f", contract.ask))
                    }
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                }
            }

            HStack {
                if let delta = contract.delta {
                    Label(String(format: "Δ %.3f", delta), systemImage: "waveform.path.ecg")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }

                Spacer()

                Text("Vol: \(Int(contract.volume))")
                    .font(.caption2)
                    .foregroundStyle(.secondary)

                Text("OI: \(Int(contract.openInterest))")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(.horizontal)
        .padding(.vertical, 8)
        .background(Color(nsColor: .controlBackgroundColor).opacity(0.5))
        .overlay(
            Rectangle()
                .stroke(Color.primary.opacity(0.05), lineWidth: 1)
        )
    }
}

struct LoadingOptionsView: View {
    var body: some View {
        VStack(spacing: 12) {
            ProgressView()
            Text("Loading options chain...")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct OptionsErrorView: View {
    let message: String
    let onRetry: () -> Void

    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: "chart.bar.doc.horizontal")
                .font(.largeTitle)
                .foregroundStyle(.orange)
            Text("Failed to load options chain")
                .font(.headline)
            Text(message)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
            Button("Retry", action: onRetry)
                .buttonStyle(.borderedProminent)
        }
        .padding()
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct EmptyOptionsView: View {
    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: "chart.bar.doc.horizontal")
                .font(.largeTitle)
                .foregroundStyle(.secondary)
            Text("No options data available")
                .font(.headline)
                .foregroundStyle(.secondary)
            Text("Options chain data will appear here when available")
                .font(.subheadline)
                .foregroundStyle(.tertiary)
                .multilineTextAlignment(.center)
        }
        .padding()
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
