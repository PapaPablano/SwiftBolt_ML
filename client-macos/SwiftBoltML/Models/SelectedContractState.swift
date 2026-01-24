import Foundation
import SwiftUI

// MARK: - Contract Workbench Tab Enum

enum ContractWorkbenchTab: String, CaseIterable, Identifiable {
    case overview
    case whyRanked
    case contract
    case surfaces
    case risk
    case alerts
    case notes
    
    var id: String { rawValue }
    
    var displayName: String {
        switch self {
        case .overview: return "Overview"
        case .whyRanked: return "Why Ranked"
        case .contract: return "Contract"
        case .surfaces: return "Surfaces"
        case .risk: return "Risk"
        case .alerts: return "Alerts"
        case .notes: return "Notes"
        }
    }
    
    var icon: String {
        switch self {
        case .overview: return "chart.bar.fill"
        case .whyRanked: return "star.fill"
        case .contract: return "doc.text.fill"
        case .surfaces: return "cube.fill"
        case .risk: return "exclamationmark.triangle.fill"
        case .alerts: return "bell.fill"
        case .notes: return "note.text"
        }
    }
}

// MARK: - Surface Visualization Enums

enum SurfaceScope: String, CaseIterable, Codable {
    case nearby
    case wholeChain
    
    var displayName: String {
        switch self {
        case .nearby: return "Nearby"
        case .wholeChain: return "Whole Chain"
        }
    }
    
    var icon: String {
        switch self {
        case .nearby: return "scope"
        case .wholeChain: return "rectangle.expand.vertical"
        }
    }
    
    var tooltip: String {
        switch self {
        case .nearby: return "±3 strikes, ±2 expiries from selected contract"
        case .wholeChain: return "Full options chain surface"
        }
    }
}

enum SurfaceMetric: String, CaseIterable, Codable, Identifiable {
    case iv
    case delta
    case gamma
    case theta
    case vega
    
    var id: String { rawValue }
    
    var displayName: String {
        switch self {
        case .iv: return "IV"
        case .delta: return "Δ"
        case .gamma: return "Γ"
        case .theta: return "Θ"
        case .vega: return "V"
        }
    }
    
    var fullName: String {
        switch self {
        case .iv: return "Implied Volatility"
        case .delta: return "Delta"
        case .gamma: return "Gamma"
        case .theta: return "Theta"
        case .vega: return "Vega"
        }
    }
}

// MARK: - Selected Contract State

/// Observable state for the Contract Workbench
/// Manages the currently selected contract and workbench UI state
class SelectedContractState: ObservableObject {
    
    // MARK: - Selection State
    
    /// ID of the currently selected rank
    @Published var selectedRankId: String?
    
    /// Full snapshot of the selected option rank
    @Published var selectedRank: OptionRank?
    
    /// GA Strategy for the current symbol (if available)
    @Published var gaStrategy: GAStrategy?
    
    // MARK: - Workbench UI State
    
    /// Whether the workbench inspector is currently presented
    @Published var isWorkbenchPresented: Bool = false
    
    /// Currently active tab in the workbench
    @Published var workbenchTab: ContractWorkbenchTab = .overview
    
    // MARK: - Surfaces Tab State
    
    /// Scope for surface visualization (nearby vs whole chain)
    @Published var surfaceScope: SurfaceScope = .nearby
    
    /// Currently selected metric for surface visualization
    @Published var surfaceMetric: SurfaceMetric = .iv
    
    /// Whether to show historical comparison on surfaces
    @Published var showHistoricalComparison: Bool = false
    
    // MARK: - Advanced Display Options
    
    /// Show advanced controls (for power users)
    @AppStorage("contractWorkbench.showAdvancedControls") 
    var showAdvancedControls: Bool = false
    
    /// Remember last used tab per session
    @AppStorage("contractWorkbench.rememberLastTab") 
    var rememberLastTab: Bool = true
    
    // MARK: - Methods
    
    /// Select a contract and optionally open the workbench
    func select(rank: OptionRank, openWorkbench: Bool = true) {
        self.selectedRankId = rank.id
        self.selectedRank = rank
        
        if openWorkbench {
            self.isWorkbenchPresented = true
        }
        
        // Reset to overview tab unless remembering last tab
        if !rememberLastTab {
            self.workbenchTab = .overview
        }
    }
    
    /// Clear the current selection
    func clearSelection() {
        self.selectedRankId = nil
        self.selectedRank = nil
    }
    
    /// Close the workbench but keep selection
    func closeWorkbench() {
        self.isWorkbenchPresented = false
    }
    
    /// Check if a specific rank is currently selected
    func isSelected(_ rank: OptionRank) -> Bool {
        return selectedRankId == rank.id
    }
    
    /// Update GA strategy when symbol changes
    func updateGAStrategy(_ strategy: GAStrategy?) {
        self.gaStrategy = strategy
    }
}

// MARK: - Preview Helper

extension SelectedContractState {
    static let preview: SelectedContractState = {
        let state = SelectedContractState()
        state.selectedRank = OptionRank.example
        state.isWorkbenchPresented = true
        state.gaStrategy = GAStrategy.example
        return state
    }()
}
