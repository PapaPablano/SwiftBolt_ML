/**
 * Canonical Strategy Condition Translator
 *
 * Bridges the three-way condition format mismatch:
 *  - Frontend:  { type: 'rsi', operator: '>', value: 30, params: {} }
 *  - Worker:    { type: 'indicator', name: 'rsi', operator: 'above', value: 30 }
 *  - Executor:  { id: string, indicator: 'RSI', operator: '>', value: 30, logicalOp: 'AND' }
 *
 * Single source of truth — both worker and executor import from here.
 */

// ============================================================================
// FORMAT TYPES
// ============================================================================

/** Frontend condition format (camelCase, type = indicator id). */
export interface FrontendCondition {
  type: string;
  operator?: string;
  value?: number;
  params?: Record<string, unknown>;
}

/** Worker condition format (snake_case, name = indicator id, text operators). */
export interface WorkerCondition {
  type: string;
  name: string;
  operator?: string;
  value?: number;
  params?: Record<string, unknown>;
}

/** Executor condition format (PascalCase indicator, symbol operators, with id + logicalOp). */
export interface ExecutorCondition {
  id: string;
  indicator: string;
  operator: string;
  value?: number;
  crossWith?: string;
  minValue?: number;
  maxValue?: number;
  logicalOp: "AND" | "OR";
  parentId?: string;
}

// ============================================================================
// OPERATOR MAPPINGS
// ============================================================================

/** Frontend symbol operators → Worker text operators.
 *  Preserves >= / <= distinction so the backtest engine can apply correct comparison. */
const OPERATOR_TO_WORKER: Record<string, string> = {
  ">": "above",
  ">=": "above_equal",
  "<": "below",
  "<=": "below_equal",
  "==": "equals",
  "!=": "not_equals",
  "cross_up": "cross_up",
  "cross_down": "cross_down",
};

/** Worker text operators → Frontend symbol operators. */
const OPERATOR_FROM_WORKER: Record<string, string> = {
  above: ">",
  above_equal: ">=",
  below: "<",
  below_equal: "<=",
  equals: "==",
  not_equals: "!=",
  cross_up: "cross_up",
  cross_down: "cross_down",
};

// ============================================================================
// INDICATOR NAME NORMALIZATION
// ============================================================================

/** Canonical indicator names (PascalCase, as used by executor cache). */
const INDICATOR_CANONICAL: Record<string, string> = {
  rsi: "RSI",
  macd: "MACD",
  macd_signal: "MACD",
  macd_hist: "MACD",
  stochastic: "STOCH",
  stoch: "STOCH",
  cci: "CCI",
  volume: "Volume",
  volume_ratio: "Volume",
  volume_ma: "Volume_MA",
  close: "Close",
  open: "Open",
  high: "High",
  low: "Low",
  sma: "Close",
  ema: "Close",
  sma_cross: "Close",
  ema_cross: "Close",
  adx: "RSI", // ADX uses similar range
  bb: "Close",
  bb_upper: "Close",
  bb_lower: "Close",
  atr: "Close",
};

/**
 * Normalize an indicator name to its canonical form.
 * Returns the PascalCase form used by the executor's indicator cache.
 */
export function normalizeIndicatorName(name: string): string {
  const lower = name.toLowerCase().replace(/[-\s]/g, "_");
  return INDICATOR_CANONICAL[lower] ?? name;
}

/**
 * Lowercase an indicator name to frontend form.
 * Returns the lowercase form used by the frontend condition builder.
 */
export function toFrontendIndicatorName(name: string): string {
  return name.toLowerCase();
}

// ============================================================================
// CONVERSION FUNCTIONS
// ============================================================================

/** Convert a frontend condition to worker format. */
export function frontendToWorker(c: FrontendCondition): WorkerCondition {
  return {
    type: "indicator",
    name: c.type,
    operator: OPERATOR_TO_WORKER[c.operator ?? ">"] ?? "above",
    value: c.value ?? 0,
    params: c.params,
  };
}

/** Convert a worker condition to frontend format. */
export function workerToFrontend(c: WorkerCondition): FrontendCondition {
  return {
    type: c.name,
    operator: OPERATOR_FROM_WORKER[c.operator ?? "above"] ?? ">",
    value: c.value ?? 0,
    params: c.params,
  };
}

/** Convert a frontend condition to executor format. */
export function frontendToExecutor(
  c: FrontendCondition,
  index: number,
): ExecutorCondition {
  const base: ExecutorCondition = {
    id: `cond-${index}`,
    indicator: normalizeIndicatorName(c.type),
    operator: c.operator ?? ">",
    logicalOp: "AND",
  };

  if (c.operator === "cross_up" || c.operator === "cross_down") {
    base.crossWith = `${normalizeIndicatorName(c.type)}_prev`;
  } else {
    base.value = c.value ?? 0;
  }

  return base;
}

/** Convert an executor condition to frontend format. */
export function executorToFrontend(c: ExecutorCondition): FrontendCondition {
  return {
    type: toFrontendIndicatorName(c.indicator),
    operator: c.operator,
    value: c.value,
  };
}

/** Convert a worker condition to executor format. */
export function workerToExecutor(
  c: WorkerCondition,
  index: number,
): ExecutorCondition {
  const frontendOp = OPERATOR_FROM_WORKER[c.operator ?? "above"] ?? ">";
  return frontendToExecutor(
    { ...workerToFrontend(c), operator: frontendOp },
    index,
  );
}

// ============================================================================
// BATCH NORMALIZATION (for strategy configs)
// ============================================================================

export interface StrategyConfigRaw {
  entry_conditions?: WorkerCondition[];
  exit_conditions?: WorkerCondition[];
  entryConditions?: FrontendCondition[];
  exitConditions?: FrontendCondition[];
}

/**
 * Normalize a strategy config from any format to worker format.
 * Handles both camelCase (frontend) and snake_case (worker) field names.
 */
export function normalizeToWorkerFormat(
  raw: StrategyConfigRaw,
): { entry_conditions: WorkerCondition[]; exit_conditions: WorkerCondition[] } {
  const entry = raw.entry_conditions ?? [];
  const exit = raw.exit_conditions ?? [];

  if (entry.length > 0 || exit.length > 0) {
    return { entry_conditions: entry, exit_conditions: exit };
  }

  return {
    entry_conditions: (raw.entryConditions ?? []).map(frontendToWorker),
    exit_conditions: (raw.exitConditions ?? []).map(frontendToWorker),
  };
}

/**
 * Normalize a strategy config from any format to executor format.
 */
export function normalizeToExecutorFormat(
  raw: StrategyConfigRaw,
): {
  entry_conditions: ExecutorCondition[];
  exit_conditions: ExecutorCondition[];
} {
  // First normalize to worker, then convert to executor
  const { entry_conditions, exit_conditions } = normalizeToWorkerFormat(raw);
  return {
    entry_conditions: entry_conditions.map((c, i) => workerToExecutor(c, i)),
    exit_conditions: exit_conditions.map((c, i) =>
      workerToExecutor(c, i + entry_conditions.length)
    ),
  };
}
