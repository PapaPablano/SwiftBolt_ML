import Foundation

// Consolidated TradeStation Models - Fixed to eliminate duplicates and ensure Codable conformance

// Generic parameter value type that conforms to Codable
enum ParameterValue: Codable {
    case int(Int)
    case double(Double)
    case string(String)
    case bool(Bool)
    
    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let intVal = try? container.decode(Int.self) {
            self = .int(intVal)
        } else if let doubleVal = try? container.decode(Double.self) {
            self = .double(doubleVal)
        } else if let stringVal = try? container.decode(String.self) {
            self = .string(stringVal)
        } else if let boolVal = try? container.decode(Bool.self) {
            self = .bool(boolVal)
        } else {
            throw DecodingError.typeMismatch(ParameterValue.self, DecodingError.Context(codingPath: decoder.codingPath, debugDescription: "Unsupported type"))
        }
    }
    
    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .int(let val): try container.encode(val)
        case .double(let val): try container.encode(val)
        case .string(let val): try container.encode(val)
        case .bool(let val): try container.encode(val)
        }
    }
    
    var intValue: Int? {
        if case .int(let val) = self { return val }
        return nil
    }
    
    var doubleValue: Double? {
        if case .double(let val) = self { return val }
        return nil
    }
    
    var stringValue: String? {
        if case .string(let val) = self { return val }
        return nil
    }
}

// Strategy model
struct TSStrategy: Codable, Identifiable {
    let id: String
    var name: String
    var description: String?
    var enabled: Bool
    var createdAt: Date
    var updatedAt: Date
    var conditions: [TSStrategyCondition]?
    var actions: [TSTradingAction]?
    
    enum CodingKeys: String, CodingKey {
        case id, name, description, enabled
        case createdAt = "created_at"
        case updatedAt = "updated_at"
        case conditions = "ts_strategy_conditions"
        case actions = "ts_trading_actions"
    }
}

// Strategy condition
struct TSStrategyCondition: Codable, Identifiable {
    let id: String
    var strategyId: String
    var indicatorId: String
    var threshold: Double
    var conditionOperator: String
    var logicalOperator: String
    var position: Int
    var indicator: TSIndicator?
    
    enum CodingKeys: String, CodingKey {
        case id, threshold, position
        case conditionOperator = "operator"
        case strategyId = "strategy_id"
        case indicatorId = "indicator_id"
        case logicalOperator = "logical_operator"
        case indicator = "ts_indicators"
    }
}

// Trading action
struct TSTradingAction: Codable, Identifiable {
    let id: String
    var strategyId: String
    var actionType: String
    var parameters: [String: ParameterValue]
    var priority: Int
    
    enum CodingKeys: String, CodingKey {
        case id, priority
        case strategyId = "strategy_id"
        case actionType = "action_type"
        case parameters
    }
}

// Indicator model
struct TSIndicator: Codable, Identifiable {
    let id: String
    var name: String
    var description: String?
    var parameters: [String: ParameterValue]?
}

// Execution result
struct TSExecutionResult: Codable {
    let executed: Bool
    let reason: String?
    let results: [TSActionResult]?
}

// Action result
struct TSActionResult: Codable {
    let action: String
    let result: [String: ParameterValue]?
}

// Credentials status
struct TSCredentialsStatus: Codable {
    let connected: Bool
    let expired: Bool
    let lastUpdated: Date
    
    enum CodingKeys: String, CodingKey {
        case connected
        case expired
        case lastUpdated = "last_updated"
    }
    
    init(connected: Bool, expired: Bool) {
        self.connected = connected
        self.expired = expired
        self.lastUpdated = Date()
    }
}