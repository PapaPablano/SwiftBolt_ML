import Foundation

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

struct TSTradingAction: Codable, Identifiable {
    let id: String
    var strategyId: String
    var actionType: String
    var parameters: [String: AnyCodable]
    var priority: Int
    
    enum CodingKeys: String, CodingKey {
        case id, priority
        case strategyId = "strategy_id"
        case actionType = "action_type"
        case parameters
    }
}

struct TSIndicator: Codable, Identifiable {
    let id: String
    var name: String
    var description: String?
    var parameters: [String: AnyCodable]?
}

struct AnyCodable: Codable {
    let value: Any
    
    init(_ value: Any) {
        self.value = value
    }
    
    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let string = try? container.decode(String.self) {
            value = string
        } else if let int = try? container.decode(Int.self) {
            value = int
        } else if let double = try? container.decode(Double.self) {
            value = double
        } else if let bool = try? container.decode(Bool.self) {
            value = bool
        } else if let dict = try? container.decode([String: AnyCodable].self) {
            value = dict.mapValues { $0.value }
        } else if let array = try? container.decode([AnyCodable].self) {
            value = array.map { $0.value }
        } else {
            value = NSNull()
        }
    }
    
    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        if let string = value as? String {
            try container.encode(string)
        } else if let int = value as? Int {
            try container.encode(int)
        } else if let double = value as? Double {
            try container.encode(double)
        } else if let bool = value as? Bool {
            try container.encode(bool)
        } else if let dict = value as? [String: Any] {
            try container.encode(dict.mapValues { AnyCodable($0) })
        } else if let array = value as? [Any] {
            try container.encode(array.map { AnyCodable($0) })
        } else {
            try container.encodeNil()
        }
    }
}

struct TSExecutionResult: Codable {
    let executed: Bool
    let reason: String?
    let results: [TSActionResult]?
}

struct TSActionResult: Codable {
    let action: String
    let result: [String: AnyCodable]?
}

struct TSCredentialsStatus: Codable {
    let connected: Bool
    let expired: Bool
}
