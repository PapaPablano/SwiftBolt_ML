/**
 * Unified Condition Evaluator
 * Single source of truth for strategy condition evaluation
 * Used by both backtest engine (Python) and paper trading executor (TypeScript)
 *
 * This module must stay in sync with Python implementation in ml/src/evaluation/condition_evaluator.py
 */

export interface Bar {
  time: number | string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// ============================================================================
// TYPE-SAFE OPERATOR DEFINITIONS
// ============================================================================

// Discriminated union: ensures cross_up/cross_down require crossWith field
export type ComparisonOperator = ">" | "<" | ">=" | "<=" | "==";
export type CrossOperator = "cross_up" | "cross_down";
export type RangeOperator = "touches" | "within_range";

export type Operator = ComparisonOperator | CrossOperator | RangeOperator;

/**
 * Condition represents a single rule (e.g., "RSI > 70")
 * Discriminated union ensures type safety:
 * - Comparison operators: require numeric value
 * - Cross operators: require crossWith (indicator name)
 */
export type Condition =
  | {
    id: string;
    indicator: string;
    operator: ComparisonOperator;
    value: number;
    logicalOp?: "AND" | "OR";
    parentId?: string;
  }
  | {
    id: string;
    indicator: string;
    operator: CrossOperator;
    crossWith: string; // REQUIRED for cross_up/cross_down
    logicalOp?: "AND" | "OR";
    parentId?: string;
  }
  | {
    id: string;
    indicator: string;
    operator: RangeOperator;
    minValue: number;
    maxValue: number;
    logicalOp?: "AND" | "OR";
    parentId?: string;
  };

/**
 * ConditionTree represents the hierarchical AND/OR structure
 */
export interface ConditionTree {
  id: string;
  condition: Condition;
  children: ConditionTree[];
  logicalOp: "AND" | "OR";
}

// ============================================================================
// INDICATOR CALCULATION CACHE
// ============================================================================

/**
 * Cache to avoid recalculating the same indicator multiple times per candle
 * Strategy 1: RSI, Strategy 2: RSI → calculate once, use twice
 */
export class IndicatorCache {
  private cache: Map<string, number> = new Map();
  private calculatedInCandle: Set<string> = new Set();

  /**
   * Get cached indicator value, or undefined if not calculated yet
   */
  get(key: string): number | undefined {
    return this.cache.get(key);
  }

  /**
   * Set indicator value in cache
   */
  set(key: string, value: number): void {
    this.cache.set(key, value);
    this.calculatedInCandle.add(key);
  }

  /**
   * Check if indicator was calculated this candle
   */
  wasCalculated(key: string): boolean {
    return this.calculatedInCandle.has(key);
  }

  /**
   * Clear cache for new candle
   */
  clearCandle(): void {
    this.calculatedInCandle.clear();
  }

  /**
   * Full reset (for strategy change)
   */
  reset(): void {
    this.cache.clear();
    this.calculatedInCandle.clear();
  }
}

// ============================================================================
// CONDITION EVALUATION
// ============================================================================

/**
 * Evaluate a single condition against the latest bar
 * Returns true if condition is met
 */
export function evaluateCondition(
  condition: Condition,
  bars: Bar[],
  cache: IndicatorCache,
): boolean {
  if (bars.length === 0) return false;

  const latestBar = bars[bars.length - 1];
  const cacheKey = `${condition.indicator}_latest`;

  // Get indicator value
  let indicatorValue: number;

  // Check cache first
  const cachedValue = cache.get(cacheKey);
  if (cachedValue !== undefined) {
    indicatorValue = cachedValue;
  } else {
    // Calculate indicator
    indicatorValue = calculateIndicator(condition.indicator, bars);
    cache.set(cacheKey, indicatorValue);
  }

  // Evaluate based on operator type
  if ("value" in condition) {
    // ComparisonOperator
    return evaluateComparison(
      indicatorValue,
      condition.operator as ComparisonOperator,
      condition.value,
    );
  } else if ("crossWith" in condition) {
    // CrossOperator
    const crossWithValue = calculateIndicator(condition.crossWith, bars);
    return evaluateCross(
      indicatorValue,
      crossWithValue,
      condition.operator as CrossOperator,
      bars,
    );
  } else if ("minValue" in condition) {
    // RangeOperator
    return evaluateRange(
      indicatorValue,
      condition.minValue,
      condition.maxValue,
      condition.operator as RangeOperator,
    );
  }

  return false;
}

/**
 * Evaluate comparison operators: >, <, >=, <=, ==
 */
function evaluateComparison(
  value: number,
  operator: ComparisonOperator,
  target: number,
): boolean {
  switch (operator) {
    case ">":
      return value > target;
    case "<":
      return value < target;
    case ">=":
      return value >= target;
    case "<=":
      return value <= target;
    case "==":
      return Math.abs(value - target) < 0.0001; // Float comparison with epsilon
    default:
      return false;
  }
}

/**
 * Evaluate cross operators: cross_up, cross_down
 * Current bar vs previous bar
 */
function evaluateCross(
  currentValue: number,
  currentCross: number,
  operator: CrossOperator,
  bars: Bar[],
): boolean {
  if (bars.length < 2) return false;

  // Get previous bar's values
  const prevBar = bars[bars.length - 2];
  const prevCacheKey = `${operator}_prev`;

  // For simplicity, we'll return true if crossover condition met on this bar
  // In production, you'd calculate previous bar's indicator values

  switch (operator) {
    case "cross_up":
      // Previous value was below, current value is above
      // This is a simplified check; full implementation would track previous values
      return currentValue > currentCross;
    case "cross_down":
      // Previous value was above, current value is below
      return currentValue < currentCross;
    default:
      return false;
  }
}

/**
 * Evaluate range operators: touches, within_range
 */
function evaluateRange(
  value: number,
  min: number,
  max: number,
  operator: RangeOperator,
): boolean {
  switch (operator) {
    case "within_range":
      return value >= min && value <= max;
    case "touches": {
      // Touches at min or max boundary
      const epsilon = 0.0001;
      return (Math.abs(value - min) < epsilon) ||
        (Math.abs(value - max) < epsilon);
    }
    default:
      return false;
  }
}

// ============================================================================
// TREE EVALUATION (AND/OR LOGIC)
// ============================================================================

/**
 * Evaluate entire condition tree with AND/OR logic
 */
export function evaluateConditionTree(
  tree: ConditionTree | null,
  bars: Bar[],
  cache: IndicatorCache,
): boolean {
  if (!tree) return false;

  // Evaluate this node
  const nodeResult = evaluateCondition(tree.condition, bars, cache);

  // If no children, return node result
  if (!tree.children || tree.children.length === 0) {
    return nodeResult;
  }

  // Evaluate children
  const childResults = tree.children.map((child) =>
    evaluateConditionTree(child, bars, cache)
  );

  // Combine with logical operator
  if (tree.logicalOp === "AND") {
    return nodeResult && childResults.every((r) => r);
  } else {
    return nodeResult || childResults.some((r) => r);
  }
}

// ============================================================================
// INDICATOR CALCULATION
// ============================================================================

/**
 * Calculate indicator value from bars
 * Stub: actual indicator implementations depend on which indicator
 * In production, this would call actual indicator calculators
 */
function calculateIndicator(name: string, bars: Bar[]): number {
  const lowerName = name.toLowerCase();

  switch (lowerName) {
    case "rsi":
      return calculateRSI(bars, 14);
    case "close":
      return bars[bars.length - 1].close;
    case "open":
      return bars[bars.length - 1].open;
    case "high":
      return bars[bars.length - 1].high;
    case "low":
      return bars[bars.length - 1].low;
    case "volume":
      return bars[bars.length - 1].volume;
    default:
      // Return last close as fallback
      return bars[bars.length - 1].close;
  }
}

/**
 * Simplified RSI calculation (14-period)
 */
function calculateRSI(bars: Bar[], period: number = 14): number {
  if (bars.length < period + 1) return 50; // Default to neutral

  const changes = [];
  for (let i = 1; i < bars.length; i++) {
    changes.push(bars[i].close - bars[i - 1].close);
  }

  const gains = changes.filter((c) => c > 0).reduce((a, b) => a + b, 0) /
    period;
  const losses =
    Math.abs(changes.filter((c) => c < 0).reduce((a, b) => a + b, 0)) / period;

  if (losses === 0) return 100;
  const rs = gains / losses;
  return 100 - (100 / (1 + rs));
}

// ============================================================================
// CONDITION TREE BUILDER
// ============================================================================

/**
 * Build condition tree from flat list of conditions
 * Used to reconstruct AND/OR hierarchy from database
 */
export function buildConditionTree(
  conditions: Condition[],
): ConditionTree | null {
  if (!conditions || conditions.length === 0) return null;

  // Create map of conditions by ID for easy lookup
  const conditionMap = new Map<string, Condition>();
  conditions.forEach((c) => conditionMap.set(c.id, c));

  // Find root conditions (those without parentId)
  const rootConditions = conditions.filter((c) => !c.parentId);

  if (rootConditions.length === 0) {
    // Fallback: treat first condition as root
    return {
      id: conditions[0].id,
      condition: conditions[0],
      children: [],
      logicalOp: "AND",
    };
  }

  // Build tree for first root condition
  return buildTreeNode(rootConditions[0], conditionMap);
}

/**
 * Recursively build tree node and its children
 */
function buildTreeNode(
  condition: Condition,
  conditionMap: Map<string, Condition>,
): ConditionTree {
  // Find children of this condition
  const children = Array.from(conditionMap.values()).filter((c) =>
    c.parentId === condition.id
  );

  const childNodes = children.map((child) =>
    buildTreeNode(child, conditionMap)
  );

  return {
    id: condition.id,
    condition,
    children: childNodes,
    logicalOp: condition.logicalOp || "AND",
  };
}

// ============================================================================
// BATCH EVALUATION
// ============================================================================

/**
 * Evaluate entry and exit signals in one pass
 * Reuses indicator cache for both entry and exit conditions
 */
export function evaluateStrategySignals(
  entryConditions: Condition[],
  exitConditions: Condition[],
  bars: Bar[],
): { entry: boolean; exit: boolean } {
  const cache = new IndicatorCache();

  const entryTree = buildConditionTree(entryConditions);
  const exitTree = buildConditionTree(exitConditions);

  const entry = evaluateConditionTree(entryTree, bars, cache);
  const exit = evaluateConditionTree(exitTree, bars, cache);

  return { entry, exit };
}
