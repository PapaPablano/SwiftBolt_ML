import SwiftUI

struct TechnicalIndicatorsView: View {
    @Environment(\.dismiss) private var dismiss
    @EnvironmentObject var appViewModel: AppViewModel
    @StateObject private var viewModel = TechnicalIndicatorsViewModel()
    let symbol: String
    let timeframe: String

    @State private var selectedCategory: IndicatorCategory? = nil
    @State private var expandedCategories: Set<IndicatorCategory> = Set(IndicatorCategory.allCases)

    private var favoritesStore: IndicatorFavoritesStore { appViewModel.indicatorFavoritesStore }
    
    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                // Header
                headerView
                
                // Price Summary Card
                if let priceData = viewModel.priceData {
                    priceSummaryCard(priceData)
                }
                
                // Indicators by Category
                if viewModel.hasIndicators {
                    indicatorsByCategoryView
                } else if viewModel.isLoading {
                    loadingView
                } else if let error = viewModel.error {
                    errorView(error)
                } else {
                    emptyStateView
                }
            }
            .padding()
        }
        .navigationTitle("Technical Indicators")
        .navigationBarBackButtonHidden(true)
        .toolbar {
            ToolbarItem(placement: .cancellationAction) {
                Button("Back") {
                    // Defer dismiss to avoid re-entrant view updates / Metal/IconRendering crash on pop (macOS 26 / Tahoe)
                    DispatchQueue.main.async { dismiss() }
                }
            }
        }
        .task {
            await viewModel.loadIndicators(symbol: symbol, timeframe: timeframe)
        }
        .refreshable {
            await viewModel.refresh()
        }
        .onAppear {
            // #region agent log
            _agentLog("TechnicalIndicatorsView onAppear", location: "TechnicalIndicatorsView.swift:onAppear", data: ["symbol": symbol, "timeframe": timeframe], hypothesisId: "A")
            // #endregion
        }
    }
    
    // MARK: - Header
    
    private var headerView: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text("\(symbol) - \(timeframe.uppercased())")
                    .font(.title2.bold())
                
                if let lastUpdated = viewModel.lastUpdated {
                    HStack(spacing: 4) {
                        Image(systemName: "clock")
                            .font(.caption2)
                        Text("Updated \(lastUpdated, style: .relative)")
                            .font(.caption)
                    }
                    .foregroundStyle(.secondary)
                }
            }
            
            Spacer()
            
            Button(action: {
                Task {
                    await viewModel.refresh()
                }
            }) {
                HStack(spacing: 4) {
                    Image(systemName: "arrow.clockwise")
                    if viewModel.isLoading {
                        ProgressView()
                            .scaleEffect(0.7)
                    }
                }
            }
            .buttonStyle(.bordered)
            .disabled(viewModel.isLoading)
        }
    }
    
    // MARK: - Price Summary Card
    
    private func priceSummaryCard(_ price: TechnicalIndicatorsResponse.PriceData) -> some View {
        DashboardCard(title: "Price Data", icon: "dollarsign.circle", iconColor: .blue) {
            HStack(spacing: 20) {
                priceMetric(label: "Open", value: price.open)
                Divider()
                priceMetric(label: "High", value: price.high)
                Divider()
                priceMetric(label: "Low", value: price.low)
                Divider()
                priceMetric(label: "Close", value: price.close, isHighlighted: true)
                Divider()
                priceMetric(label: "Volume", value: price.volume, format: .number)
            }
        }
    }
    
    private func priceMetric(label: String, value: Double, isHighlighted: Bool = false, format: FloatingPointFormatStyle<Double> = .number) -> some View {
        VStack(spacing: 4) {
            Text(label)
                .font(.caption)
                .foregroundStyle(.secondary)
            Text(value, format: format)
                .font(isHighlighted ? .headline.bold() : .subheadline)
                .foregroundStyle(isHighlighted ? .primary : .secondary)
        }
        .frame(maxWidth: .infinity)
    }
    
    // MARK: - Indicators by Category
    
    private var indicatorsByCategoryView: some View {
        VStack(spacing: 16) {
            ForEach(IndicatorCategory.allCases, id: \.self) { category in
                if let indicators = viewModel.indicatorsByCategory[category], !indicators.isEmpty {
                    categoryCard(category: category, indicators: indicators)
                }
            }
        }
    }
    
    private func categoryCard(category: IndicatorCategory, indicators: [IndicatorItem]) -> some View {
        DashboardCard(
            title: category.displayName,
            icon: category.icon,
            iconColor: categoryColor(category)
        ) {
            LazyVGrid(columns: [
                GridItem(.adaptive(minimum: 140), spacing: 12)
            ], spacing: 12) {
                ForEach(indicators) { indicator in
                    IndicatorCard(
                        indicator: indicator,
                        isFavorite: favoritesStore.isFavorite(indicator.name),
                        canAddFavorite: favoritesStore.favoriteNames.count < IndicatorFavoritesStore.maxFavorites || favoritesStore.isFavorite(indicator.name),
                        onToggleFavorite: { favoritesStore.toggleFavorite(indicator.name) }
                    )
                }
            }
        }
    }
    
    private func categoryColor(_ category: IndicatorCategory) -> Color {
        switch category {
        case .momentum: return .orange
        case .volatility: return .purple
        case .volume: return .blue
        case .trend: return .green
        case .price: return .yellow
        case .other: return .gray
        }
    }
    
    // MARK: - Loading/Error/Empty States
    
    private var loadingView: some View {
        VStack(spacing: 16) {
            ProgressView()
            Text("Loading indicators...")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 40)
    }
    
    private func errorView(_ error: String) -> some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle")
                .font(.largeTitle)
                .foregroundStyle(.orange)
            Text("Error loading indicators")
                .font(.headline)
            Text(error)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
            
            Button("Retry") {
                Task {
                    await viewModel.refresh()
                }
            }
            .buttonStyle(.borderedProminent)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 40)
    }
    
    private var emptyStateView: some View {
        VStack(spacing: 16) {
            Image(systemName: "chart.line.uptrend.xyaxis")
                .font(.largeTitle)
                .foregroundStyle(.secondary)
            Text("No indicators available")
                .font(.headline)
            Text("Indicators will appear here once data is loaded")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 40)
    }
}

// MARK: - Indicator Card

struct IndicatorCard: View {
    let indicator: IndicatorItem
    var isFavorite: Bool = false
    var canAddFavorite: Bool = true
    var onToggleFavorite: (() -> Void)? = nil

    private var interpretation: IndicatorInterpretation { indicator.interpretation }
    private var interpretationColor: Color { interpretation.swiftUIColor }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 8) {
                    Text(indicator.formattedName)
                        .font(.caption.bold())
                        .foregroundStyle(.primary)

                    Text(indicator.displayValue)
                        .font(.title3.bold().monospacedDigit())
                        .foregroundStyle(interpretationColor)

                    HStack(spacing: 4) {
                        Circle()
                            .fill(interpretationColor)
                            .frame(width: 6, height: 6)
                        Text(interpretation.label)
                            .font(.caption2)
                            .foregroundStyle(interpretationColor)
                    }
                }
                Spacer(minLength: 4)
                if onToggleFavorite != nil {
                    Button(action: {
                        guard canAddFavorite || isFavorite else { return }
                        onToggleFavorite?()
                    }) {
                        Image(systemName: isFavorite ? "star.fill" : "star")
                            .font(.caption)
                            .foregroundStyle(isFavorite ? .yellow : .secondary)
                    }
                    .buttonStyle(.plain)
                    .disabled(!canAddFavorite && !isFavorite)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(Color(nsColor: .controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(interpretationColor.opacity(0.3), lineWidth: 1)
        )
    }
}

// Note: DashboardCard is defined in PredictionsView.swift and reused here

// MARK: - Preview

#Preview {
    TechnicalIndicatorsView(symbol: "AAPL", timeframe: "d1")
        .environmentObject(AppViewModel())
        .frame(width: 900, height: 800)
}
