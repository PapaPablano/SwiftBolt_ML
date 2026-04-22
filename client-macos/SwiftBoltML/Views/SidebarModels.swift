import Foundation

// MARK: - Sidebar Section Models

enum ResearchSection: Hashable {
    case chartsAndAnalysis
    case predictions
}

enum BuildSection: Hashable {
    case strategyBuilder
    case backtesting
    case multiLeg
}

enum TradeSection: Hashable {
    case paperTrading
    case liveTrading
    case portfolio
}

enum SidebarSection: Hashable {
    case research(ResearchSection)
    case buildAndTest(BuildSection)
    case trade(TradeSection)
    #if DEBUG
    case devtools
    #endif
}
