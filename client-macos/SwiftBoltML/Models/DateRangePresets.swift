import Foundation

enum DateRangePreset: String, CaseIterable, Identifiable {
    case lastMonth = "last_month"
    case last3Months = "last_3_months"
    case last6Months = "last_6_months"
    case lastYear = "last_year"
    case last2Years = "last_2_years"
    case last5Years = "last_5_years"
    case allTime = "all_time"
    
    // Market Regime Presets
    case dotComBubble = "dot_com_bubble"
    case dotComBust = "dot_com_bust"
    case gfc = "gfc"
    case postGfcExpansion = "post_gfc_expansion"
    case covidCrash = "covid_crash"
    case covidRebound = "covid_rebound"
    case rateHikeBear2022 = "rate_hike_bear_2022"
    case aiBull2022_2024 = "ai_bull_2022_2024"
    
    var id: String { rawValue }
    
    var displayName: String {
        switch self {
        case .lastMonth: return "Last Month"
        case .last3Months: return "Last 3 Months"
        case .last6Months: return "Last 6 Months"
        case .lastYear: return "Last Year"
        case .last2Years: return "Last 2 Years"
        case .last5Years: return "Last 5 Years"
        case .allTime: return "All Time"
        case .dotComBubble: return "Dot-com Bubble (1995-2000)"
        case .dotComBust: return "Dot-com Bust (2000-2002)"
        case .gfc: return "GFC (2007-2009)"
        case .postGfcExpansion: return "Post-GFC Expansion (2009-2020)"
        case .covidCrash: return "COVID Crash (Feb-Mar 2020)"
        case .covidRebound: return "COVID Rebound (Mar-Aug 2020)"
        case .rateHikeBear2022: return "2022 Rate Hike Bear"
        case .aiBull2022_2024: return "AI Bull (2022-2024)"
        }
    }
    
    var description: String {
        switch self {
        case .lastMonth: return "Last 30 days"
        case .last3Months: return "Last 90 days"
        case .last6Months: return "Last 180 days"
        case .lastYear: return "Last 365 days"
        case .last2Years: return "Last 2 years"
        case .last5Years: return "Last 5 years"
        case .allTime: return "All available data"
        case .dotComBubble: return "Tech boom / risk-on regime"
        case .dotComBust: return "Bear market / tech unwind"
        case .gfc: return "Deep recession / crisis"
        case .postGfcExpansion: return "Long expansion / risk-on"
        case .covidCrash: return "Short, sharp recession"
        case .covidRebound: return "Violent rebound / policy-driven"
        case .rateHikeBear2022: return "Bear market / macro tightening"
        case .aiBull2022_2024: return "Bull market / AI boom narrative"
        }
    }
    
    var icon: String {
        switch self {
        case .lastMonth, .last3Months, .last6Months, .lastYear, .last2Years, .last5Years, .allTime:
            return "calendar"
        case .dotComBubble, .dotComBust:
            return "chart.line.uptrend.xyaxis"
        case .gfc:
            return "arrow.down.circle"
        case .postGfcExpansion:
            return "chart.line.uptrend.xyaxis"
        case .covidCrash:
            return "exclamationmark.triangle"
        case .covidRebound:
            return "arrow.up.circle"
        case .rateHikeBear2022:
            return "arrow.down.right"
        case .aiBull2022_2024:
            return "brain"
        }
    }
    
    var dateRange: (start: Date, end: Date)? {
        let calendar = Calendar.current
        let now = Date()
        
        switch self {
        case .lastMonth:
            return (calendar.date(byAdding: .month, value: -1, to: now)!, now)
        case .last3Months:
            return (calendar.date(byAdding: .month, value: -3, to: now)!, now)
        case .last6Months:
            return (calendar.date(byAdding: .month, value: -6, to: now)!, now)
        case .lastYear:
            return (calendar.date(byAdding: .year, value: -1, to: now)!, now)
        case .last2Years:
            return (calendar.date(byAdding: .year, value: -2, to: now)!, now)
        case .last5Years:
            return (calendar.date(byAdding: .year, value: -5, to: now)!, now)
        case .allTime:
            return (calendar.date(byAdding: .year, value: -10, to: now)!, now)
        case .dotComBubble:
            return (dateFromString("1995-01-01"), dateFromString("2000-03-10"))
        case .dotComBust:
            return (dateFromString("2000-03-10"), dateFromString("2002-10-09"))
        case .gfc:
            return (dateFromString("2007-12-01"), dateFromString("2009-06-01"))
        case .postGfcExpansion:
            return (dateFromString("2009-06-01"), dateFromString("2020-02-19"))
        case .covidCrash:
            return (dateFromString("2020-02-19"), dateFromString("2020-03-23"))
        case .covidRebound:
            return (dateFromString("2020-03-23"), dateFromString("2020-08-31"))
        case .rateHikeBear2022:
            return (dateFromString("2022-01-03"), dateFromString("2022-10-15"))
        case .aiBull2022_2024:
            return (dateFromString("2022-10-12"), dateFromString("2024-01-19"))
        }
    }
    
    var category: PresetCategory {
        switch self {
        case .lastMonth, .last3Months, .last6Months, .lastYear, .last2Years, .last5Years, .allTime:
            return .recent
        case .dotComBubble, .dotComBust:
            return .dotCom
        case .gfc, .postGfcExpansion:
            return .financialCrisis
        case .covidCrash, .covidRebound:
            return .pandemic
        case .rateHikeBear2022, .aiBull2022_2024:
            return .modern
        }
    }
    
    private func dateFromString(_ string: String) -> Date {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.date(from: string) ?? Date()
    }
}

enum PresetCategory: String, CaseIterable {
    case recent = "Recent"
    case dotCom = "Dot-com Era"
    case financialCrisis = "Financial Crises"
    case pandemic = "Pandemic"
    case modern = "Modern (2022+)"
    
    var presets: [DateRangePreset] {
        DateRangePreset.allCases.filter { $0.category == self }
    }
}
