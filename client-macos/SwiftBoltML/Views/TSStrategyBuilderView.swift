import SwiftUI

struct TSStrategyBuilderView: View {
    @StateObject private var viewModel = TSStrategyViewModel()
    @State private var showingNewStrategy = false
    
    var body: some View {
        NavigationView {
            List {
                if !viewModel.isAuthenticated {
                    authSection
                } else {
                    strategySection
                }
            }
            .navigationTitle("TradeStation Strategies")
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    if viewModel.isAuthenticated {
                        Button(action: { showingNewStrategy = true }) {
                            Image(systemName: "plus")
                        }
                    }
                }
            }
            .sheet(isPresented: $showingNewStrategy) {
                NewTStrategySheet(viewModel: viewModel)
                    .frame(minWidth: 400, minHeight: 300)
            }
            .refreshable {
                await viewModel.fetchStrategies()
            }
        }
    }
    
    private var authSection: some View {
        Section {
            VStack(spacing: 16) {
                Image(systemName: "person.badge.key.fill")
                    .font(.system(size: 48))
                    .foregroundColor(.accentColor)
                
                Text("Connect TradeStation")
                    .font(.headline)
                
                Text("Sign in with your TradeStation account to create and execute trading strategies.")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
                
                Button(action: { viewModel.startOAuth() }) {
                    HStack {
                        if viewModel.isLoading {
                            ProgressView()
                                .scaleEffect(0.8)
                        }
                        Text("Connect Account")
                    }
                    .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .disabled(viewModel.isLoading)
                
                if let error = viewModel.error {
                    Text(error)
                        .font(.caption)
                        .foregroundColor(.red)
                }
            }
            .padding()
        }
    }
    
    private var strategySection: some View {
        Section(header: Text("My Strategies")) {
            if viewModel.isLoading && viewModel.strategies.isEmpty {
                ProgressView()
            } else if viewModel.strategies.isEmpty {
                VStack(spacing: 12) {
                    Image(systemName: "chart.line.uptrend.xyaxis")
                        .font(.largeTitle)
                        .foregroundColor(.secondary)
                    Text("No strategies yet")
                        .font(.headline)
                    Text("Create your first trading strategy")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                .frame(maxWidth: .infinity)
                .padding()
            } else {
                ForEach(viewModel.strategies) { strategy in
                    NavigationLink(destination: TSStrategyDetailView(strategy: strategy, viewModel: viewModel)) {
                        TSStrategyRow(strategy: strategy)
                    }
                }
                .onDelete { indexSet in
                    for index in indexSet {
                        let strategy = viewModel.strategies[index]
                        Task {
                            await viewModel.deleteStrategy(strategy.id)
                        }
                    }
                }
            }
        }
    }
}

struct TSStrategyRow: View {
    let strategy: TSStrategyModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(strategy.name)
                    .font(.headline)
                Spacer()
                Circle()
                    .fill(strategy.enabled ? Color.green : Color.gray)
                    .frame(width: 8, height: 8)
            }
            
            if let description = strategy.description, !description.isEmpty {
                Text(description)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .lineLimit(1)
            }
            
            HStack {
                if !strategy.conditions.isEmpty {
                    Label("\(strategy.conditions.count) conditions", systemImage: "function")
                        .font(.caption2)
                }
                Spacer()
                if !strategy.actions.isEmpty {
                    Label("\(strategy.actions.count) actions", systemImage: "bolt.fill")
                        .font(.caption2)
                }
            }
            .foregroundColor(.secondary)
        }
        .padding(.vertical, 4)
    }
}

struct TSStrategyDetailView: View {
    let strategy: TSStrategyModel
    @ObservedObject var viewModel: TSStrategyViewModel
    @State private var showingExecute = false
    @State private var symbol = ""
    @State private var executionResult: TSExecutionResult?
    
    var body: some View {
        List {
            Section(header: Text("Details")) {
                LabeledContent("Name", value: strategy.name)
                LabeledContent("Enabled", value: strategy.enabled ? "Yes" : "No")
                LabeledContent("Created", value: strategy.createdAt.formatted())
                if let description = strategy.description {
                    LabeledContent("Description", value: description)
                }
            }
            
            Section(header: Text("Conditions")) {
                if !strategy.conditions.isEmpty {
                    ForEach(strategy.conditions) { condition in
                        ConditionRow(condition: condition)
                    }
                } else {
                    Text("No conditions defined")
                        .foregroundColor(.secondary)
                }
                Button(action: {}) {
                    Label("Add Condition", systemImage: "plus")
                }
            }
            
            Section(header: Text("Actions")) {
                if !strategy.actions.isEmpty {
                    ForEach(strategy.actions) { action in
                        ActionRow(action: action)
                    }
                } else {
                    Text("No actions defined")
                        .foregroundColor(.secondary)
                }
                Button(action: {}) {
                    Label("Add Action", systemImage: "plus")
                }
            }
            
            Section(header: Text("Execute")) {
                TextField("Symbol (e.g., AAPL)", text: $symbol)
                
                Button(action: { Task { executionResult = await viewModel.executeStrategy(strategy.id, symbol: symbol) } }) {
                    HStack {
                        if viewModel.isLoading {
                            ProgressView()
                                .scaleEffect(0.8)
                        }
                        Text("Execute Strategy")
                    }
                    .frame(maxWidth: .infinity)
                }
                .disabled(symbol.isEmpty || viewModel.isLoading)
                
                if let result = executionResult {
                    ExecutionResultView(result: result)
                }
            }
        }
        .navigationTitle(strategy.name)
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Menu {
                    Button(action: { viewModel.toggleEnabled(strategy) }) {
                        Label(strategy.enabled ? "Disable" : "Enable", systemImage: strategy.enabled ? "pause.circle" : "play.circle")
                    }
                    Button(role: .destructive, action: { Task { await viewModel.deleteStrategy(strategy.id) } }) {
                        Label("Delete", systemImage: "trash")
                    }
                } label: {
                    Image(systemName: "ellipsis.circle")
                }
            }
        }
    }
}

struct ConditionRow: View {
    let condition: TSCondition
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("Indicator")
                .font(.subheadline)
                .fontWeight(.medium)
            
            HStack {
                Text("\(condition.threshold, specifier: "%.2f")")
                Text(condition.conditionOperator.rawValue)
                Text(condition.logicalOperator.rawValue)
            }
            .font(.caption)
            .foregroundColor(.secondary)
        }
    }
}

struct ActionRow: View {
    let action: TSAction
    
    var body: some View {
        HStack {
            Image(systemName: action.actionType == .buy ? "arrow.up.circle.fill" : (action.actionType == .sell ? "arrow.down.circle.fill" : "bolt.circle.fill"))
                .foregroundColor(action.actionType == .buy ? .green : (action.actionType == .sell ? .red : .orange))
            
            VStack(alignment: .leading) {
                Text(action.actionType.rawValue)
                    .font(.subheadline)
                    .fontWeight(.medium)
                
                if let qty = action.parameters["quantity"]?.intValue {
                    Text("Qty: \(qty)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            
            Spacer()
        }
    }
}

struct ExecutionResultView: View {
    let result: TSExecutionResult
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: result.executed ? "checkmark.circle.fill" : "xmark.circle.fill")
                    .foregroundColor(result.executed ? .green : .red)
                Text(result.executed ? "Executed" : "Not Executed")
                    .fontWeight(.medium)
            }
            
            if let reason = result.reason {
                Text(reason)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .padding()
        .background(Color.secondary.opacity(0.1))
        .cornerRadius(8)
    }
}

struct NewTStrategySheet: View {
    @ObservedObject var viewModel: TSStrategyViewModel
    @Environment(\.dismiss) private var dismiss
    @State private var name = ""
    @State private var description = ""
    @State private var isCreating = false
    
    var body: some View {
        VStack(spacing: 20) {
            Text("Create New Strategy")
                .font(.headline)
            
            TextField("Strategy Name", text: $name)
                .textFieldStyle(.roundedBorder)
                .frame(width: 300)
            
            TextField("Description (optional)", text: $description)
                .textFieldStyle(.roundedBorder)
                .frame(width: 300)
            
            HStack(spacing: 20) {
                Button("Cancel") {
                    dismiss()
                }
                .buttonStyle(.bordered)
                
                Button("Create") {
                    isCreating = true
                    print("[NewStrategySheet] Create tapped, name: '\(name)'")
                    Task {
                        print("[NewStrategySheet] Task started")
                        let result = await viewModel.createStrategy(name: name, description: description.isEmpty ? nil : description)
                        print("[NewStrategySheet] Result: \(String(describing: result)), strategies count: \(viewModel.strategies.count)")
                        isCreating = false
                        dismiss()
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(name.isEmpty || isCreating)
            }
        }
        .padding(40)
    }
}
