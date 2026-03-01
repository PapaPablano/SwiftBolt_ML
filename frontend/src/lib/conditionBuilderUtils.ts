/** Types, constants, and pure helper functions for StrategyConditionBuilder. */

// ============================================================================
// TYPE DEFINITIONS
// ============================================================================

// Discriminated union types for type-safe operators
export type ComparisonOperator = '>' | '<' | '>=' | '<=' | '==' | '!=';
export type CrossOperator = 'cross_up' | 'cross_down';
export type RangeOperator = 'touches' | 'within_range';

export type Condition =
  | {
      id: string;
      indicator: string;
      operator: ComparisonOperator;
      value: number;
      logicalOp: 'AND' | 'OR';
      parentId?: string;
    }
  | {
      id: string;
      indicator: string;
      operator: CrossOperator;
      crossWith: string;
      logicalOp: 'AND' | 'OR';
      parentId?: string;
    }
  | {
      id: string;
      indicator: string;
      operator: RangeOperator;
      minValue: number;
      maxValue: number;
      logicalOp: 'AND' | 'OR';
      parentId?: string;
    };

export interface ConditionBuilderProps {
  signalType: 'entry' | 'exit' | 'stoploss' | 'takeprofit';
  initialConditions: Condition[];
  onConditionsChange: (conditions: Condition[]) => void;
  availableIndicators: string[];
}

export interface ConditionError {
  conditionId: string;
  message: string;
}

export interface ConditionTreeNode {
  condition: Condition;
  children: ConditionTreeNode[];
}

// ============================================================================
// CONSTANTS
// ============================================================================

export const COMPARISON_OPERATORS: ComparisonOperator[] = ['>', '<', '>=', '<=', '==', '!='];
export const CROSS_OPERATORS: CrossOperator[] = ['cross_up', 'cross_down'];
export const RANGE_OPERATORS: RangeOperator[] = ['touches', 'within_range'];
export const MAX_CONDITIONS_PER_SIGNAL = 5;

/** Typical indicator ranges for quick validation. */
export const INDICATOR_RANGES: Record<string, { min: number; max: number }> = {
  RSI: { min: 0, max: 100 },
  STOCH: { min: 0, max: 100 },
  CCI: { min: -200, max: 200 },
  Volume: { min: 0, max: Infinity },
  Close: { min: 0, max: Infinity },
  Open: { min: 0, max: Infinity },
  High: { min: 0, max: Infinity },
  Low: { min: 0, max: Infinity },
};

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

export function generateId(): string {
  return `cond_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

export function validateCondition(condition: Condition): string | null {
  const indicatorRange = INDICATOR_RANGES[condition.indicator];

  if ('crossWith' in condition) {
    if (!condition.crossWith) return `${condition.operator} requires a cross target`;
  }

  if ('value' in condition) {
    if (
      indicatorRange &&
      (condition.value < indicatorRange.min || condition.value > indicatorRange.max)
    ) {
      return `${condition.indicator} value should be between ${indicatorRange.min} and ${indicatorRange.max}`;
    }
  }

  if ('minValue' in condition && 'maxValue' in condition) {
    if (condition.minValue >= condition.maxValue) return `Min value must be less than max value`;
  }

  return null;
}

export function buildConditionTree(conditions: Condition[]): ConditionTreeNode | null {
  if (conditions.length === 0) return null;
  const roots = conditions.filter((c) => !c.parentId);
  if (roots.length === 0) return null;

  function buildNode(condition: Condition): ConditionTreeNode {
    const children = conditions.filter((c) => c.parentId === condition.id);
    return { condition, children: children.map((c) => buildNode(c)) };
  }

  return buildNode(roots[0]);
}
