import Foundation

// MARK: - Stress Test Request

struct StressTestRequest {
    let positions: [String: Double]
    let prices: [String: Double]
    let scenario: HistoricalScenario?
    let customShocks: [String: Double]?
    let varLevel: Double?
}

// MARK: - Stress Test Response

struct StressTestResponse: Decodable {
    let scenario: String
    let portfolio: PortfolioImpact
    let risk: RiskMetrics
    let positionChanges: [String: Double]
    let positions: [String: Double]
    let prices: [String: Double]
    let error: String?
    
    struct PortfolioImpact: Decodable {
        let currentValue: Double
        let change: Double
        let changePercent: Double
    }
    
    struct RiskMetrics: Decodable {
        let varLevel: Double
        let varBreached: Bool
        let severity: String
    }
}

// MARK: - Historical Scenario

enum HistoricalScenario: String, CaseIterable {
    case financialCrisis2008 = "2008_financial_crisis"
    case covidCrash2020 = "2020_covid_crash"
    case euDebtCrisis2011 = "2011_eu_debt_crisis"
    case blackMonday1987 = "1987_black_monday"
    case chinaDevaluation2015 = "2015_china_devaluation"
    
    var displayName: String {
        switch self {
        case .financialCrisis2008: return "2008 Financial Crisis"
        case .covidCrash2020: return "COVID-19 Crash (2020)"
        case .euDebtCrisis2011: return "EU Debt Crisis (2011)"
        case .blackMonday1987: return "Black Monday (1987)"
        case .chinaDevaluation2015: return "China Devaluation (2015)"
        }
    }
    
    var description: String {
        switch self {
        case .financialCrisis2008: return "Sep-Oct 2008 market crash"
        case .covidCrash2020: return "Feb-Mar 2020 pandemic crash"
        case .euDebtCrisis2011: return "European sovereign debt crisis"
        case .blackMonday1987: return "October 19, 1987 single-day crash"
        case .chinaDevaluation2015: return "August 2015 currency devaluation"
        }
    }
    
    var icon: String {
        switch self {
        case .financialCrisis2008: return "exclamationmark.triangle.fill"
        case .covidCrash2020: return "cross.case.fill"
        case .euDebtCrisis2011: return "eurosign.circle.fill"
        case .blackMonday1987: return "calendar.badge.exclamationmark"
        case .chinaDevaluation2015: return "yensign.circle.fill"
        }
    }
}

// MARK: - Severity

enum StressSeverity: String {
    case low = "Low"
    case medium = "Medium"
    case high = "High"
    case extreme = "Extreme"
    
    var color: Color {
        switch self {
        case .low: return .green
        case .medium: return .yellow
        case .high: return .orange
        case .extreme: return .red
        }
    }
}

import SwiftUI
