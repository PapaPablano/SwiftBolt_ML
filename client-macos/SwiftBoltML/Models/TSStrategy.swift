import Foundation

struct TSStrategyModel: Codable, Identifiable {
    let id: String
    let name: String
    let description: String?
    var enabled: Bool
    let createdAt: Date
    var updatedAt: Date
    let conditions: [TSCondition]
    let actions: [TSAction]
    
    enum CodingKeys: String, CodingKey {
        case id
        case name
        case description
        case enabled
        case createdAt = "created_at"
        case updatedAt = "updated_at"
        case conditions
        case actions
    }
    
    init(id: String = UUID().uuidString,
         name: String,
         description: String? = nil,
         enabled: Bool = true,
         createdAt: Date = Date(),
         updatedAt: Date = Date(),
         conditions: [TSCondition] = [],
         actions: [TSAction] = []) {
        self.id = id
        self.name = name
        self.description = description
        self.enabled = enabled
        self.createdAt = createdAt
        self.updatedAt = updatedAt
        self.conditions = conditions
        self.actions = actions
    }
}

struct TSCondition: Codable, Identifiable {
    let id: String
    let indicatorId: String
    let threshold: Double
    let conditionOperator: TSOperator
    let logicalOperator: TSLogicalOperator
    
    enum CodingKeys: String, CodingKey {
        case id
        case indicatorId = "indicator_id"
        case threshold
        case conditionOperator = "operator"
        case logicalOperator = "logical_operator"
    }
    
    init(id: String = UUID().uuidString,
         indicatorId: String,
         threshold: Double,
         conditionOperator: TSOperator,
         logicalOperator: TSLogicalOperator = .and) {
        self.id = id
        self.indicatorId = indicatorId
        self.threshold = threshold
        self.conditionOperator = conditionOperator
        self.logicalOperator = logicalOperator
    }
}

struct TSAction: Codable, Identifiable {
    let id: String
    let actionType: TSActionType
    let parameters: [String: ParameterValue]
    
    enum CodingKeys: String, CodingKey {
        case id
        case actionType = "action_type"
        case parameters
    }
    
    init(id: String = UUID().uuidString,
         actionType: TSActionType,
         parameters: [String: ParameterValue] = [:]) {
        self.id = id
        self.actionType = actionType
        self.parameters = parameters
    }
}

enum TSOperator: String, Codable {
    case greaterThan = ">"
    case lessThan = "<"
    case equalTo = "="
    case greaterThanOrEqual = ">="
    case lessThanOrEqual = "<="
}

enum TSLogicalOperator: String, Codable {
    case and = "AND"
    case or = "OR"
}

enum TSActionType: String, Codable {
    case buy = "BUY"
    case sell = "SELL"
    case hold = "HOLD"
    case exit = "EXIT"
    case alert = "ALERT"
}