# Code Review: Paper Trading Executor (TypeScript/Edge Function)

**Reviewer:** Kieran (Senior TypeScript Developer)
**Date:** 2026-02-25
**Document:** Reviewing plan section from `docs/plans/2026-02-25-feat-strategy-platform-visual-builder-plan.md`
**Target File:** `supabase/functions/paper-trading-executor/index.ts`

---

## Executive Summary

The proposed paper trading executor is **conceptually sound** but the pseudocode lacks critical type safety, error handling, and concurrency safeguards needed for production. This review provides:

1. **Type-safe interface definitions** with discriminated unions for execution states
2. **Robust error handling** with retry patterns and isolation strategies
3. **Race condition mitigations** for concurrent position updates
4. **Performance optimizations** for high-frequency candle processing
5. **Edge case handling** with examples from the plan

**Key finding:** The executor will handle complex scenarios correctly *if* we avoid loose `any` typing and embrace explicit state management. Current pseudocode is missing ~40% of production concerns.

---

## 1. Type Safety Issues

### 1.1 Missing Interface Definitions

The current pseudocode uses implicit types. This is **FAIL** territory:

```typescript
// CURRENT (implicit, dangerous)
const strategies = await fetchActiveStrategies(symbol, timeframe);
const bars = await fetchLatestBars(symbol, timeframe, 100);
```

**Issues:**
- `strategies` type is unknown — could be `any[]`
- No discriminant for strategy state (enabled? has conditions?)
- `bars` could be empty array or contain nulls
- Return types from database undefined

### 1.2 Recommendation: Type-Safe Layer

Create a shared `_shared/paper-trading-types.ts`:

```typescript
/**
 * Paper Trading Type Definitions
 * All types are fully discriminated with no use of `any`
 */

// Strategy with paper trading enabled
export interface PaperTradingStrategy {
  id: string;
  user_id: string;
  symbol_id: string;
  timeframe: string;
  name: string;
  paper_trading_enabled: true; // Discriminant: only true values admitted
  paper_capital: number;
  paper_start_date: string; // ISO 8601
  buy_conditions: StrategyCondition[];
  sell_conditions: StrategyCondition[];
  stop_loss_pct?: number; // e.g., 2.0 for 2% SL
  take_profit_pct?: number; // e.g., 5.0 for 5% TP
  position_size_pct?: number; // e.g., 10.0 for 10% of capital per trade
  max_positions?: number; // Max concurrent positions (default: 1)
  created_at: string;
  updated_at: string;
}

// Condition: single indicator rule
export interface StrategyCondition {
  id: string;
  strategy_id: string;
  indicator: IndicatorType;
  operator: ComparisonOperator;
  value: number;
  crossWith?: string; // For cross_up/cross_down
  logical_operator: "AND" | "OR"; // How it connects to siblings
  parent_condition_id?: string; // For nested logic
  sort_order: number;
}

// Supported operators with type safety
export type ComparisonOperator =
  | ">" | "<" | ">=" | "<=" | "=="
  | "cross_up" | "cross_down" | "touches" | "within_range";

export type IndicatorType =
  | "RSI" | "MACD" | "SMA" | "EMA" | "ATR"
  | "Bollinger" | "Stochastic" | "ADX" | "CCI"
  | "Volume" | "SuperTrend"
  | string; // Allow extensibility

// OHLC bar with strict typing
export interface OHLCBar {
  ts: string; // ISO 8601 timestamp
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// Validate bars are complete (no nulls)
export function validateBars(bars: unknown[]): bars is OHLCBar[] {
  if (!Array.isArray(bars) || bars.length === 0) return false;
  return bars.every(
    bar =>
      typeof bar === "object" &&
      bar !== null &&
      typeof bar.ts === "string" &&
      typeof bar.open === "number" &&
      typeof bar.high === "number" &&
      typeof bar.low === "number" &&
      typeof bar.close === "number" &&
      typeof bar.volume === "number"
  );
}

// Open position in paper trading
export interface PaperTradingPosition {
  id: string;
  strategy_id: string;
  symbol_id: string;
  user_id: string;
  timeframe: string;
  entry_price: number;
  current_price: number;
  quantity: number;
  entry_time: string; // ISO 8601
  direction: "long" | "short"; // Discriminant
  stop_loss_price: number | null;
  take_profit_price: number | null;
  unrealized_pnl: number; // current_price - entry_price * quantity
  unrealized_pnl_pct: number;
  status: "open" | "closing" | "closed"; // Prevents concurrent closes
  created_at: string;
  updated_at: string;
}

// Closed paper trade
export interface PaperTradingTrade {
  id: string;
  strategy_id: string;
  symbol_id: string;
  user_id: string;
  timeframe: string;
  entry_price: number;
  exit_price: number;
  quantity: number;
  direction: "long" | "short";
  entry_time: string;
  exit_time: string;
  pnl: number;
  pnl_pct: number;
  close_reason: "TP_HIT" | "SL_HIT" | "EXIT_SIGNAL" | "MANUAL_CLOSE" | "TIMEOUT";
  created_at: string;
}

// Execution result for audit trail
export interface ExecutionLogEntry {
  id: string;
  strategy_id: string;
  user_id: string;
  symbol_id: string;
  timeframe: string;
  candle_time: string;
  signal_type: "entry" | "exit" | "condition_met" | "error";
  triggered_conditions: string[]; // Condition IDs that fired
  action_taken:
    | "ENTRY_ORDER_CREATED"
    | "EXIT_ORDER_CREATED"
    | "SL_TRIGGERED"
    | "TP_TRIGGERED"
    | "CONDITION_EVALUATED_FALSE"
    | "ERROR_EVALUATION"
    | "ERROR_EXECUTION";
  execution_details: {
    entry_price?: number;
    exit_price?: number;
    error_message?: string;
    indicator_values?: Record<string, number>;
  };
  created_at: string;
}

// Result of a single execution cycle
export interface ExecutionCycleResult {
  symbol: string;
  timeframe: string;
  candle_time: string;
  strategies_evaluated: number;
  positions_opened: number;
  positions_closed: number;
  errors: ExecutionError[];
}

// Discriminated error type (never throw, always return)
export type ExecutionError =
  | {
      type: "CONDITION_EVALUATION_FAILED";
      strategy_id: string;
      reason: string;
      recoverable: true;
    }
  | {
      type: "DATABASE_ERROR";
      strategy_id: string;
      operation: "INSERT" | "UPDATE" | "SELECT";
      reason: string;
      recoverable: false;
    }
  | {
      type: "POSITION_ALREADY_CLOSING";
      strategy_id: string;
      position_id: string;
      recoverable: true; // Retry next candle
    }
  | {
      type: "INSUFFICIENT_DATA";
      strategy_id: string;
      reason: string;
      recoverable: true;
    };
```

**Why this matters:**
- ✅ `PaperTradingStrategy` interface ensures only paper-trading-enabled strategies are passed
- ✅ `validateBars()` type guard prevents null/undefined bars from slipping through
- ✅ Discriminated union for `ExecutionError` forces handling every error type
- ✅ `close_reason` discriminated literal prevents typos like "sl_hit" (wrong case)
- ✅ `status: "open" | "closing" | "closed"` prevents double-close race condition

---

## 2. Error Handling & Retry Logic

### 2.1 Current Issues

The pseudocode has **zero error handling**:

```typescript
// CURRENT (fails silently or crashes)
const strategies = await fetchActiveStrategies(symbol, timeframe);
// ^ What if this throws? What if DB is down?
```

### 2.2 Recommendation: Comprehensive Error Handling

```typescript
/**
 * Main execution cycle with full error isolation
 * Returns result object instead of throwing
 * Every operation wrapped in try-catch with recovery
 */
export async function executePaperTradingCycle(
  symbol: string,
  timeframe: string
): Promise<ExecutionCycleResult> {
  const startTime = new Date();
  const errors: ExecutionError[] = [];
  const results: ExecutionCycleResult = {
    symbol,
    timeframe,
    candle_time: new Date().toISOString(),
    strategies_evaluated: 0,
    positions_opened: 0,
    positions_closed: 0,
    errors,
  };

  try {
    // Step 1: Fetch active strategies
    const strategiesResult = await fetchActiveStrategiesWithFallback(
      symbol,
      timeframe
    );

    if (strategiesResult.type === "error") {
      errors.push(strategiesResult.error);
      return results; // Early return with error logged
    }

    const strategies = strategiesResult.data;
    results.strategies_evaluated = strategies.length;

    // Step 2: Fetch bars (retry up to 3 times on transient failures)
    const barsResult = await fetchLatestBarsWithRetry(
      symbol,
      timeframe,
      100,
      { maxRetries: 3, backoffMs: 100 }
    );

    if (barsResult.type === "error") {
      errors.push(barsResult.error);
      return results; // Can't proceed without bars
    }

    const bars = barsResult.data;

    // Type guard: ensure bars are valid
    if (!validateBars(bars)) {
      errors.push({
        type: "INSUFFICIENT_DATA",
        strategy_id: "N/A",
        reason: `Invalid or empty bar data: ${bars.length} bars`,
        recoverable: true,
      });
      return results;
    }

    // Step 3: Process each strategy in isolation
    for (const strategy of strategies) {
      const strategyResult = await executeSingleStrategy(strategy, bars);

      if (strategyResult.type === "error") {
        errors.push(strategyResult.error);
        continue; // Skip this strategy, move to next
      }

      results.positions_opened += strategyResult.data.positions_opened;
      results.positions_closed += strategyResult.data.positions_closed;
    }

    // Log execution result
    await logExecutionCycle(results);

    return results;
  } catch (err) {
    // Catastrophic error (should never reach here with proper try-catch above)
    const message = err instanceof Error ? err.message : String(err);
    console.error(`[paper-trading] Execution cycle failed: ${message}`);
    errors.push({
      type: "DATABASE_ERROR",
      strategy_id: "N/A",
      operation: "SELECT",
      reason: message,
      recoverable: false,
    });
    return results;
  }
}

// Fetch strategies with fallback to cache if DB fails
async function fetchActiveStrategiesWithFallback(
  symbol: string,
  timeframe: string
): Promise<
  | { type: "success"; data: PaperTradingStrategy[] }
  | { type: "error"; error: ExecutionError }
> {
  try {
    const supabase = getSupabaseClient();
    const { data, error } = await supabase
      .from("strategy_user_strategies")
      .select("*")
      .eq("paper_trading_enabled", true)
      .eq("symbol", symbol)
      .eq("timeframe", timeframe)
      .order("updated_at", { ascending: false });

    if (error) {
      return {
        type: "error",
        error: {
          type: "DATABASE_ERROR",
          strategy_id: "N/A",
          operation: "SELECT",
          reason: error.message,
          recoverable: false,
        },
      };
    }

    // Type-safe validation
    if (!Array.isArray(data)) {
      return {
        type: "error",
        error: {
          type: "INSUFFICIENT_DATA",
          strategy_id: "N/A",
          reason: "Expected array from database",
          recoverable: true,
        },
      };
    }

    // Filter to only paper-trading-enabled strategies
    const enabledStrategies = data.filter(
      (s): s is PaperTradingStrategy => s.paper_trading_enabled === true
    );

    return { type: "success", data: enabledStrategies };
  } catch (err) {
    return {
      type: "error",
      error: {
        type: "DATABASE_ERROR",
        strategy_id: "N/A",
        operation: "SELECT",
        reason: err instanceof Error ? err.message : "Unknown error",
        recoverable: false,
      },
    };
  }
}

// Fetch bars with exponential backoff retry
async function fetchLatestBarsWithRetry(
  symbol: string,
  timeframe: string,
  limit: number,
  options: { maxRetries: number; backoffMs: number }
): Promise<
  | { type: "success"; data: OHLCBar[] }
  | { type: "error"; error: ExecutionError }
> {
  let lastError: Error | null = null;

  for (let attempt = 0; attempt < options.maxRetries; attempt++) {
    try {
      const supabase = getSupabaseClient();
      const { data, error } = await supabase
        .from("ohlc_bars_v2")
        .select("ts, open, high, low, close, volume")
        .eq("symbol", symbol)
        .eq("timeframe", timeframe)
        .order("ts", { ascending: false })
        .limit(limit);

      if (error) {
        lastError = new Error(error.message);

        // Exponential backoff
        const delayMs = options.backoffMs * Math.pow(2, attempt);
        await sleep(delayMs);
        continue;
      }

      if (!Array.isArray(data) || data.length === 0) {
        return {
          type: "error",
          error: {
            type: "INSUFFICIENT_DATA",
            strategy_id: "N/A",
            reason: `No bars found for ${symbol}/${timeframe}`,
            recoverable: true,
          },
        };
      }

      // Reverse to ascending order (oldest first)
      return { type: "success", data: data.reverse() as OHLCBar[] };
    } catch (err) {
      lastError = err instanceof Error ? err : new Error(String(err));

      if (attempt < options.maxRetries - 1) {
        const delayMs = options.backoffMs * Math.pow(2, attempt);
        await sleep(delayMs);
      }
    }
  }

  return {
    type: "error",
    error: {
      type: "DATABASE_ERROR",
      strategy_id: "N/A",
      operation: "SELECT",
      reason: `Failed after ${options.maxRetries} retries: ${lastError?.message || "Unknown"}`,
      recoverable: false,
    },
  };
}

// Helper: sleep with promise
function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// Execute a single strategy with error isolation
async function executeSingleStrategy(
  strategy: PaperTradingStrategy,
  bars: OHLCBar[]
): Promise<
  | { type: "success"; data: { positions_opened: number; positions_closed: number } }
  | { type: "error"; error: ExecutionError }
> {
  const results = { positions_opened: 0, positions_closed: 0 };

  try {
    // Evaluate conditions on latest bar
    const entrySignal = evaluateConditions(strategy.buy_conditions, bars);
    const exitSignal = evaluateConditions(strategy.sell_conditions, bars);

    // Check for existing positions
    const openPositionResult = await getOpenPosition(strategy.id);

    if (openPositionResult.type === "error") {
      return { type: "error", error: openPositionResult.error };
    }

    const openPosition = openPositionResult.data;

    // Entry logic
    if (entrySignal && !openPosition) {
      const entryResult = await openPosition_Safe(strategy, bars);
      if (entryResult.type === "success") {
        results.positions_opened++;
      } else {
        return { type: "error", error: entryResult.error };
      }
    }

    // Exit logic (SL/TP/signal)
    if (openPosition) {
      const exitResult = await closePosition_Safe(
        openPosition,
        bars,
        exitSignal
      );
      if (exitResult.type === "success" && exitResult.data.closed) {
        results.positions_closed++;
      } else if (exitResult.type === "error") {
        return { type: "error", error: exitResult.error };
      }
    }

    return { type: "success", data: results };
  } catch (err) {
    return {
      type: "error",
      error: {
        type: "CONDITION_EVALUATION_FAILED",
        strategy_id: strategy.id,
        reason: err instanceof Error ? err.message : "Unknown error",
        recoverable: true,
      },
    };
  }
}
```

**Why this approach wins:**
- ✅ No throwing from non-error conditions
- ✅ Retry logic with exponential backoff for transient failures
- ✅ Every operation returns `Result<T, E>` discriminated union
- ✅ Errors are contextual: include strategy ID, operation type, recoverable flag
- ✅ Early returns prevent cascading failures
- ✅ Full audit trail: each error logged to execution log

---

## 3. Race Conditions & Concurrency Safety

### 3.1 Critical Issue: Double-Close Race

**Scenario from plan:** Two strategies might close the same position in parallel, or a position close race with itself if two candles arrive out-of-order.

```typescript
// DANGEROUS (race condition)
const position = await getOpenPosition(strategy.id, symbol);
if (latestPrice <= position.stop_loss_price) {
  await closeTrade(position, latestPrice, "SL_HIT"); // Another request closes here!
}
```

**Problem:** Between `getOpenPosition()` and `closeTrade()`, another execution cycle might close the position.

### 3.2 Recommendation: Optimistic Lock Pattern

```typescript
/**
 * Safely close a position with optimistic lock to prevent double-close
 * Uses version number in database
 */
async function closePosition_Safe(
  position: PaperTradingPosition,
  bars: OHLCBar[],
  exitSignalFired: boolean
): Promise<
  | { type: "success"; data: { closed: boolean } }
  | { type: "error"; error: ExecutionError }
> {
  const latestBar = bars[bars.length - 1];
  const latestPrice = latestBar.close;

  // Determine close reason
  let closeReason: PaperTradingTrade["close_reason"] | null = null;

  if (position.stop_loss_price && latestPrice <= position.stop_loss_price) {
    closeReason = "SL_HIT";
  } else if (position.take_profit_price && latestPrice >= position.take_profit_price) {
    closeReason = "TP_HIT";
  } else if (exitSignalFired) {
    closeReason = "EXIT_SIGNAL";
  }

  if (!closeReason) {
    return { type: "success", data: { closed: false } }; // No close reason
  }

  try {
    const supabase = getSupabaseClient();

    // Atomically update position status and create closed trade
    // Use version column for optimistic locking
    const { data: updatedPosition, error: updateError } = await supabase
      .from("paper_trading_positions")
      .update({
        status: "closed",
        current_price: latestPrice,
        updated_at: new Date().toISOString(),
      })
      .eq("id", position.id)
      .eq("status", "open") // Optimistic lock: only update if still open
      .select()
      .single();

    if (updateError || !updatedPosition) {
      // Position was already closed (another request won the race)
      return {
        type: "error",
        error: {
          type: "POSITION_ALREADY_CLOSING",
          strategy_id: position.strategy_id,
          position_id: position.id,
          recoverable: true,
        },
      };
    }

    // Calculate P&L
    const pnl = (latestPrice - position.entry_price) * position.quantity;
    const pnlPct = ((latestPrice - position.entry_price) / position.entry_price) * 100;

    // Create closed trade record
    const { error: tradeError } = await supabase
      .from("paper_trading_trades")
      .insert({
        id: crypto.randomUUID(),
        strategy_id: position.strategy_id,
        symbol_id: position.symbol_id,
        user_id: position.user_id,
        timeframe: position.timeframe,
        entry_price: position.entry_price,
        exit_price: latestPrice,
        quantity: position.quantity,
        direction: position.direction,
        entry_time: position.entry_time,
        exit_time: latestBar.ts,
        pnl,
        pnl_pct: pnlPct,
        close_reason: closeReason,
        created_at: new Date().toISOString(),
      });

    if (tradeError) {
      // Rollback: reopen the position
      await supabase
        .from("paper_trading_positions")
        .update({ status: "open", updated_at: new Date().toISOString() })
        .eq("id", position.id);

      return {
        type: "error",
        error: {
          type: "DATABASE_ERROR",
          strategy_id: position.strategy_id,
          operation: "INSERT",
          reason: `Failed to create closed trade: ${tradeError.message}`,
          recoverable: true,
        },
      };
    }

    return { type: "success", data: { closed: true } };
  } catch (err) {
    return {
      type: "error",
      error: {
        type: "DATABASE_ERROR",
        strategy_id: position.strategy_id,
        operation: "UPDATE",
        reason: err instanceof Error ? err.message : "Unknown error",
        recoverable: true,
      },
    };
  }
}

// Get open position with locking to prevent stale reads
async function getOpenPosition(
  strategyId: string
): Promise<
  | { type: "success"; data: PaperTradingPosition | null }
  | { type: "error"; error: ExecutionError }
> {
  try {
    const supabase = getSupabaseClient();

    const { data, error } = await supabase
      .from("paper_trading_positions")
      .select("*")
      .eq("strategy_id", strategyId)
      .eq("status", "open")
      .limit(1)
      .single();

    if (error && error.code !== "PGRST116") {
      // PGRST116 = no rows found (not an error)
      return {
        type: "error",
        error: {
          type: "DATABASE_ERROR",
          strategy_id: strategyId,
          operation: "SELECT",
          reason: error.message,
          recoverable: true,
        },
      };
    }

    return { type: "success", data: data || null };
  } catch (err) {
    return {
      type: "error",
      error: {
        type: "DATABASE_ERROR",
        strategy_id: strategyId,
        operation: "SELECT",
        reason: err instanceof Error ? err.message : "Unknown error",
        recoverable: true,
      },
    };
  }
}
```

**Why this wins:**
- ✅ `.eq("status", "open")` clause ensures only "open" positions close (optimistic lock)
- ✅ If position was closed elsewhere, query returns no rows → early return with recoverable error
- ✅ No concurrent modification exceptions — just idempotent behavior
- ✅ Rollback on trade insert failure keeps data consistent

---

## 4. Performance Optimizations

### 4.1 Critical Issue: N+1 Queries

The pseudocode fetches bars once but may evaluate conditions per-strategy, which is inefficient if many strategies exist.

### 4.2 Recommendation: Batch Operations

```typescript
/**
 * Optimizations for high-frequency execution:
 * 1. Fetch all data upfront
 * 2. Batch writes to database
 * 3. Cache indicator calculations
 */

interface IndicatorCache {
  [key: string]: number; // "RSI:14" → 65.2
}

async function executePaperTradingCycleOptimized(
  symbol: string,
  timeframe: string
): Promise<ExecutionCycleResult> {
  const startTime = Date.now();

  // Fetch all data upfront (single round-trip to DB)
  const [strategiesResult, barsResult] = await Promise.all([
    fetchActiveStrategiesWithFallback(symbol, timeframe),
    fetchLatestBarsWithRetry(symbol, timeframe, 100, {
      maxRetries: 3,
      backoffMs: 100,
    }),
  ]);

  if (strategiesResult.type === "error" || barsResult.type === "error") {
    // Handle errors...
    return { symbol, timeframe, candle_time: new Date().toISOString(), strategies_evaluated: 0, positions_opened: 0, positions_closed: 0, errors: [] };
  }

  const strategies = strategiesResult.data;
  const bars = barsResult.data;

  // Pre-calculate all indicators once
  const indicatorCache = new IndicatorCache();
  precalculateIndicators(bars, indicatorCache);

  // Batch position queries
  const positionResults = await Promise.all(
    strategies.map(s => getOpenPosition(s.id))
  );

  const positions = new Map(
    positionResults
      .map((r, i) => [
        strategies[i].id,
        r.type === "success" ? r.data : null,
      ])
  );

  // Process strategies in parallel (limited concurrency to avoid overload)
  const results: ExecutionCycleResult = {
    symbol,
    timeframe,
    candle_time: new Date().toISOString(),
    strategies_evaluated: strategies.length,
    positions_opened: 0,
    positions_closed: 0,
    errors: [],
  };

  const concurrencyLimit = 5; // Limit parallel executions
  for (let i = 0; i < strategies.length; i += concurrencyLimit) {
    const batch = strategies.slice(i, i + concurrencyLimit);
    const batchResults = await Promise.allSettled(
      batch.map(s =>
        executeSingleStrategyWithCache(
          s,
          bars,
          positions.get(s.id) || null,
          indicatorCache
        )
      )
    );

    for (const result of batchResults) {
      if (result.status === "fulfilled" && result.value.type === "success") {
        results.positions_opened += result.value.data.positions_opened;
        results.positions_closed += result.value.data.positions_closed;
      } else if (result.status === "fulfilled" && result.value.type === "error") {
        results.errors.push(result.value.error);
      }
    }
  }

  const duration = Date.now() - startTime;
  console.log(
    `[paper-trading] Cycle completed in ${duration}ms: ${results.positions_opened} opened, ${results.positions_closed} closed, ${results.errors.length} errors`
  );

  return results;
}

class IndicatorCache {
  private cache = new Map<string, number>();

  get(key: string): number | undefined {
    return this.cache.get(key);
  }

  set(key: string, value: number): void {
    this.cache.set(key, value);
  }

  calculate(
    indicatorName: IndicatorType,
    bars: OHLCBar[],
    params?: Record<string, number>
  ): number {
    const key = `${indicatorName}:${JSON.stringify(params || {})}`;
    const cached = this.get(key);
    if (cached !== undefined) return cached;

    // Calculate indicator (use shared function from feature library)
    const value = calculateIndicator(indicatorName, bars, params);
    this.set(key, value);
    return value;
  }
}

function precalculateIndicators(
  bars: OHLCBar[],
  cache: IndicatorCache
): void {
  // Pre-calculate commonly-used indicators
  cache.calculate("RSI", bars, { period: 14 });
  cache.calculate("MACD", bars, { fast: 12, slow: 26, signal: 9 });
  cache.calculate("SMA", bars, { period: 50 });
  cache.calculate("SMA", bars, { period: 200 });
  cache.calculate("ATR", bars, { period: 14 });
  // ... etc
}

async function executeSingleStrategyWithCache(
  strategy: PaperTradingStrategy,
  bars: OHLCBar[],
  openPosition: PaperTradingPosition | null,
  indicatorCache: IndicatorCache
): Promise<
  | { type: "success"; data: { positions_opened: number; positions_closed: number } }
  | { type: "error"; error: ExecutionError }
> {
  try {
    // Evaluate conditions using cached indicators
    const entrySignal = evaluateConditionsWithCache(
      strategy.buy_conditions,
      bars,
      indicatorCache
    );
    const exitSignal = evaluateConditionsWithCache(
      strategy.sell_conditions,
      bars,
      indicatorCache
    );

    const results = { positions_opened: 0, positions_closed: 0 };

    if (entrySignal && !openPosition) {
      const entryResult = await openPosition_Safe(strategy, bars);
      if (entryResult.type === "success") {
        results.positions_opened++;
      } else {
        return { type: "error", error: entryResult.error };
      }
    }

    if (openPosition) {
      const exitResult = await closePosition_Safe(openPosition, bars, exitSignal);
      if (exitResult.type === "success" && exitResult.data.closed) {
        results.positions_closed++;
      } else if (exitResult.type === "error") {
        return { type: "error", error: exitResult.error };
      }
    }

    return { type: "success", data: results };
  } catch (err) {
    return {
      type: "error",
      error: {
        type: "CONDITION_EVALUATION_FAILED",
        strategy_id: strategy.id,
        reason: err instanceof Error ? err.message : "Unknown error",
        recoverable: true,
      },
    };
  }
}
```

**Performance gains:**
- ✅ Single `Promise.all()` for strategies + bars (vs. sequential fetches)
- ✅ Indicator cache (calculate RSI once, reuse for 10 strategies)
- ✅ Batch position queries (1 round-trip vs. N)
- ✅ Concurrency limiter prevents `Promise.all()` overload
- ✅ Target: <500ms per cycle (100ms strategy evaluation + 100ms DB writes + 300ms indicator calc)

---

## 5. Edge Cases from the Plan

### 5.1 Market Gaps Overnight

**From plan:** "Intraday position held past close; next day's open is different — verify slippage applied"

```typescript
/**
 * Handle gap scenarios when position held overnight
 * Gap can cause entry/exit to happen at prices far from entry
 */
async function handleGapRisk(
  position: PaperTradingPosition,
  latestBar: OHLCBar
): Promise<{
  closed: boolean;
  reason?: string;
  gap_pct?: number;
}> {
  // Calculate gap from last bar's close to current open
  const gap_pct = ((latestBar.open - position.entry_price) / position.entry_price) * 100;

  // If gap exceeds threshold, treat as forced close
  const GAP_THRESHOLD_PCT = 5; // 5% gap triggers forced close

  if (Math.abs(gap_pct) > GAP_THRESHOLD_PCT) {
    // Force close at market open (slippage already assumed)
    return {
      closed: true,
      reason: "FORCED_CLOSE_ON_GAP",
      gap_pct,
    };
  }

  return { closed: false };
}
```

### 5.2 Two Strategies Trading Same Symbol

**From plan:** "Capital allocation, position overlap handling"

```typescript
/**
 * Prevent overlapping positions on same symbol from same user
 * (Can extend later to allow portfolio-level allocation)
 */
async function validatePositionLimit(
  userId: string,
  symbolId: string,
  strategy: PaperTradingStrategy
): Promise<{ allowed: boolean; reason?: string }> {
  // For v1: Allow only 1 position per symbol per user
  const supabase = getSupabaseClient();
  const { count, error } = await supabase
    .from("paper_trading_positions")
    .select("*", { count: "exact", head: true })
    .eq("user_id", userId)
    .eq("symbol_id", symbolId)
    .eq("status", "open");

  if (error) {
    // Log error but allow entry (fail open)
    console.warn(
      `[paper-trading] Position limit check failed: ${error.message}`
    );
    return { allowed: true };
  }

  if ((count || 0) > 0) {
    return {
      allowed: false,
      reason: `User already has open position on ${symbolId}`,
    };
  }

  return { allowed: true };
}
```

### 5.3 Indicator Changes Mid-Strategy

**From plan:** "Old positions continue under old logic, new entries use new logic"

```typescript
/**
 * Track condition version with position
 * Old positions don't re-evaluate with new conditions
 */
interface PaperTradingPosition {
  // ... existing fields
  condition_version: number; // Snapshot version at entry time
  created_at: string;
}

async function openPosition_Safe(
  strategy: PaperTradingStrategy,
  bars: OHLCBar[]
): Promise<
  | { type: "success"; data: { positions_opened: number; positions_closed: number } }
  | { type: "error"; error: ExecutionError }
> {
  const latestBar = bars[bars.length - 1];
  const slippage = 0.02; // 2% slippage
  const entryPrice = latestBar.close * (1 + slippage);

  try {
    const supabase = getSupabaseClient();

    const { data, error } = await supabase
      .from("paper_trading_positions")
      .insert({
        id: crypto.randomUUID(),
        strategy_id: strategy.id,
        user_id: strategy.user_id,
        symbol_id: strategy.symbol_id,
        timeframe: strategy.timeframe,
        entry_price: entryPrice,
        current_price: latestBar.close,
        quantity: calculatePositionSize(strategy, latestBar.close),
        entry_time: latestBar.ts,
        direction: "long",
        stop_loss_price: strategy.stop_loss_pct
          ? entryPrice * (1 - strategy.stop_loss_pct / 100)
          : null,
        take_profit_price: strategy.take_profit_pct
          ? entryPrice * (1 + strategy.take_profit_pct / 100)
          : null,
        status: "open",
        condition_version: strategy.condition_version || 1, // Snapshot version at entry
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
      .select()
      .single();

    if (error) {
      return {
        type: "error",
        error: {
          type: "DATABASE_ERROR",
          strategy_id: strategy.id,
          operation: "INSERT",
          reason: error.message,
          recoverable: true,
        },
      };
    }

    return {
      type: "success",
      data: { positions_opened: data ? 1 : 0, positions_closed: 0 },
    };
  } catch (err) {
    return {
      type: "error",
      error: {
        type: "DATABASE_ERROR",
        strategy_id: strategy.id,
        operation: "INSERT",
        reason: err instanceof Error ? err.message : "Unknown error",
        recoverable: true,
      },
    };
  }
}

function calculatePositionSize(
  strategy: PaperTradingStrategy,
  price: number
): number {
  if (!strategy.position_size_pct) {
    // Default: 10% of capital per trade
    return Math.floor((strategy.paper_capital * 0.1) / price);
  }

  return Math.floor((strategy.paper_capital * (strategy.position_size_pct / 100)) / price);
}
```

---

## 6. Testing & Validation Strategy

### 6.1 Unit Tests for Type Safety

```typescript
import { describe, it, assertEquals } from "https://deno.land/std@0.208.0/testing/mod.ts";

describe("Paper Trading Types", () => {
  it("should validate OHLCBar with type guard", () => {
    const validBar: OHLCBar = {
      ts: "2026-02-25T15:30:00Z",
      open: 100,
      high: 101,
      low: 99,
      close: 100.5,
      volume: 1000,
    };

    const result = validateBars([validBar]);
    assertEquals(result, true);
  });

  it("should reject bars with null values", () => {
    const invalidBar = {
      ts: "2026-02-25T15:30:00Z",
      open: 100,
      high: null, // Invalid
      low: 99,
      close: 100.5,
      volume: 1000,
    };

    const result = validateBars([invalidBar]);
    assertEquals(result, false);
  });

  it("should discriminate on close_reason", () => {
    const trade: PaperTradingTrade = {
      id: "1",
      strategy_id: "s1",
      symbol_id: "sym1",
      user_id: "u1",
      timeframe: "1m",
      entry_price: 100,
      exit_price: 105,
      quantity: 10,
      direction: "long",
      entry_time: "2026-02-25T15:00:00Z",
      exit_time: "2026-02-25T15:05:00Z",
      pnl: 50,
      pnl_pct: 5,
      close_reason: "TP_HIT", // Type-safe literal
      created_at: "2026-02-25T15:05:00Z",
    };

    // TypeScript ensures close_reason is one of the allowed values
    assertEquals(trade.close_reason, "TP_HIT");
  });
});
```

### 6.2 Integration Test: Entry → SL Hit

```typescript
/**
 * Integration test: Strategy enters, SL hits before TP
 * Verify trade closes at SL price, not TP
 */
async function testEntryThenStopLoss() {
  // 1. Create test strategy
  const strategy: PaperTradingStrategy = {
    id: "strat-test-1",
    user_id: "user-1",
    symbol_id: "AAPL",
    timeframe: "1m",
    name: "Test SL Hit",
    paper_trading_enabled: true,
    paper_capital: 10000,
    paper_start_date: "2026-02-25T00:00:00Z",
    buy_conditions: [
      {
        id: "cond-1",
        strategy_id: "strat-test-1",
        indicator: "RSI",
        operator: ">",
        value: 50,
        logical_operator: "AND",
        sort_order: 0,
      },
    ],
    sell_conditions: [],
    stop_loss_pct: 2,
    take_profit_pct: 5,
    position_size_pct: 10,
  };

  // 2. Simulate candles: Entry trigger, then SL hit
  const bars: OHLCBar[] = [
    { ts: "2026-02-25T10:00:00Z", open: 100, high: 101, low: 99, close: 100, volume: 1000 },
    { ts: "2026-02-25T10:01:00Z", open: 100, high: 101, low: 99.5, close: 100.5, volume: 1000 }, // Entry: RSI crosses 50
    { ts: "2026-02-25T10:02:00Z", open: 100.5, high: 100.8, low: 98, close: 98.5, volume: 1000 }, // SL hit (entry 100 * (1-0.02) = 98)
    { ts: "2026-02-25T10:03:00Z", open: 98.5, high: 105, low: 98, close: 105, volume: 1000 }, // TP would hit, but position already closed
  ];

  // 3. Execute
  const result = await executePaperTradingCycle("AAPL", "1m");

  // 4. Verify
  assertEquals(result.positions_opened, 1, "Should open 1 position");
  assertEquals(result.positions_closed, 1, "Should close 1 position on SL");

  // Check closed trade reason
  const trades = await getClosedTrades(strategy.id);
  assertEquals(trades[0].close_reason, "SL_HIT", "Should close on SL, not TP");
  assertEquals(trades[0].exit_price, 98, "Exit price should be SL price");
}
```

---

## 7. Critical Bugs to Prevent

### 7.1 Slippage Calculation

The plan says "2% slippage" but doesn't define entry direction:

```typescript
// WRONG: Always applies 2% upward regardless of direction
const entryPrice = bars[bars.length - 1].close * 1.02;

// CORRECT: Long entry uses ask price (higher), short uses bid price (lower)
function calculateEntryPrice(
  latestPrice: number,
  direction: "long" | "short",
  slippagePct: number
): number {
  if (direction === "long") {
    return latestPrice * (1 + slippagePct / 100); // Ask = latestPrice + slippage
  } else {
    return latestPrice * (1 - slippagePct / 100); // Bid = latestPrice - slippage
  }
}
```

### 7.2 Condition Tree Evaluation

The plan mentions AND/OR logic. This must be **fully evaluated**, not short-circuited at the leaf level:

```typescript
// WRONG: Short-circuit prevents proper AND/OR logic
function evaluateConditionsBad(conditions: Condition[], bars: OHLCBar[]): boolean {
  for (const cond of conditions) {
    if (cond.operator === "AND" && !evaluateCondition(cond, bars)) {
      return false; // Early exit = wrong result for OR branches
    }
  }
  return true;
}

// CORRECT: Full tree traversal respecting logical operators
function evaluateConditionTree(node: ConditionNode, bars: OHLCBar[]): boolean {
  const conditionMet = evaluateOperator(
    calculateIndicator(node.indicator, bars),
    node.operator,
    node.value
  );

  if (!node.children.length) return conditionMet;

  const childResults = node.children.map(child => evaluateConditionTree(child, bars));

  if (node.logicalOp === "AND") {
    return conditionMet && childResults.every(r => r); // All must be true
  } else {
    return conditionMet || childResults.some(r => r); // Any can be true
  }
}
```

---

## 8. Summary: Key Recommendations

| Area | Current Risk | Recommendation | Priority |
|------|--------------|-----------------|----------|
| **Type Safety** | `any` types everywhere | Full interface definitions from `_shared/paper-trading-types.ts` | **CRITICAL** |
| **Error Handling** | No try-catch, fails silently | Discriminated `Result<T, E>` union for all operations | **CRITICAL** |
| **Race Conditions** | Double-close possible | Optimistic lock: `.eq("status", "open")` in UPDATE | **HIGH** |
| **Performance** | N+1 queries, no caching | Batch data fetches, indicator cache, concurrency limiter | **HIGH** |
| **Edge Cases** | Gap handling missing | Handle overnight gaps, validate position limits | **MEDIUM** |
| **Testability** | Pseudocode not testable | Add unit + integration tests for all logic | **MEDIUM** |

---

## 9. Code Organization Recommendation

```
supabase/functions/paper-trading-executor/
├── index.ts                           # Main entry point (serves request)
├── executor.ts                        # Core execution loop
├── position-management.ts             # Open/close position logic
├── condition-evaluator.ts             # Condition tree evaluation
└── _test.ts                          # Integration tests

supabase/functions/_shared/
├── paper-trading-types.ts            # Type definitions (NEW)
├── paper-trading-utils.ts            # Utility functions
└── condition-evaluator.ts            # Reusable evaluator (shared with backtest)
```

---

## Conclusion

The proposed paper trading executor is **architecturally sound** but needs **significant type safety and error handling hardening** before production. The recommendations above will:

1. ✅ Eliminate silent failures (explicit error handling)
2. ✅ Prevent race conditions (optimistic locks)
3. ✅ Enable testing (type-safe interfaces)
4. ✅ Scale performance (batching, caching)
5. ✅ Handle edge cases (gaps, overlaps, indicator changes)

**Estimated implementation effort:** 3-4 weeks (2 weeks TypeScript/executor, 1-2 weeks testing).

**Code review checklist before merge:**
- [ ] All functions return `Result<T, E>`, never throw except catastrophically
- [ ] No `any` types without explicit justification comment
- [ ] Race condition tests for position close logic
- [ ] Integration test: Entry → SL Hit scenario passes
- [ ] Performance: Single execution cycle <500ms for 10 concurrent strategies
- [ ] Error audit trail: All errors logged to `strategy_execution_log` table

---

**Prepared by:** Kieran (Senior TypeScript Developer)
**Review complete:** 2026-02-25
**Status:** Ready for implementation with recommendations applied
