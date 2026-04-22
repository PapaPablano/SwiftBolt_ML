import SwiftUI

// MARK: - Sidebar Status Bar

/// Compact status bar showing active symbol, market status, and connectivity.
/// Placed between the watchlist and collapsible navigation sections.
struct SidebarStatusBar: View {
    @ObservedObject var appViewModel: AppViewModel
    @ObservedObject var marketService: MarketStatusService

    var body: some View {
        HStack(spacing: DesignTokens.Spacing.sm) {
            // Active symbol badge
            if let symbol = appViewModel.selectedSymbol {
                Text(symbol.ticker)
                    .font(DesignTokens.Typography.mono)
                    .fontWeight(.semibold)
                    .padding(.horizontal, DesignTokens.Spacing.sm)
                    .padding(.vertical, DesignTokens.Spacing.xs)
                    .background(DesignTokens.Colors.primary.opacity(0.15))
                    .cornerRadius(6)
            }

            Spacer()

            // Market status (compact)
            HStack(spacing: 4) {
                Circle()
                    .fill(marketService.isMarketOpen ? DesignTokens.Colors.success : DesignTokens.Colors.error)
                    .frame(width: 7, height: 7)
                Text(marketService.isMarketOpen ? "Open" : "Closed")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }

            // Connectivity warning
            if appViewModel.supabaseUnreachable {
                Image(systemName: "wifi.exclamationmark")
                    .font(.caption)
                    .foregroundStyle(DesignTokens.Colors.warning)
                    .help("Supabase unreachable — using cached data")
            }
        }
        .padding(.horizontal, DesignTokens.Spacing.md)
        .padding(.vertical, DesignTokens.Spacing.sm)
    }
}
