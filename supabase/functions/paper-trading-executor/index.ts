// ============================================================================
// PAPER TRADING EXECUTOR - Real-time Strategy Execution Engine
// File: supabase/functions/paper-trading-executor/index.ts
// Purpose: Evaluate strategies, execute trades, manage positions with race prevention
// ============================================================================

import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.97.0';

// ============================================================================
// TYPE DEFINITIONS
// ============================================================================

// Market data bar
interface Bar {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// Strategy from database
interface Strategy {
  id: string;
  user_id: string | null;
  name: string;
  symbol_id: string;
  timeframe: string;
  paper_trading_enabled: boolean;
  paper_capital: number;
  entry_conditions: any[]; // Condition[]
  exit_conditions: any[]; // Condition[]
  created_at: string;
  updated_at: string;
}

// Position from database
interface PaperPosition {
  id: string;
  user_id: string | null;
  strategy_id: string;
  symbol_id: string;
  status: 'open' | 'closed';
  entry_price: number;
  entry_time: string;
  quantity: number;
  direction: 'long' | 'short';
  stop_loss_price: number;
  take_profit_price: number;
  exit_price?: number;
  exit_time?: string;
  pnl?: number;
  close_reason?: string;
}

// Type-safe execution result with discriminated unions
type ExecutionResult =
  | { success: true; action: 'entry_created' | 'position_closed' | 'no_action'; positionId?: string }
  | { success: false; error: ExecutionError };

type ExecutionError =
  | { type: 'condition_eval_failed'; indicator: string; reason: string }
  | { type: 'position_locked'; reason: 'concurrent_close_detected' }
  | { type: 'invalid_market_data'; reason: string }
  | { type: 'position_constraints_violated'; violations: string[] }
  | { type: 'database_error'; reason: string };

// Semaphore for concurrency limiting
class Semaphore {
  private count: number;
  private waitQueue: (() => void)[] = [];

  constructor(maxConcurrent: number) {
    this.count = maxConcurrent;
  }

  async acquire(): Promise<void> {
    if (this.count > 0) {
      this.count--;
      return;
    }

    return new Promise((resolve) => {
      this.waitQueue.push(() => {
        this.count--;
        resolve();
      });
    });
  }

  release(): void {
    if (this.waitQueue.length > 0) {
      const next = this.waitQueue.shift();
      if (next) {
        this.count++;
        next();
      }
    } else {
      this.count++;
    }
  }
}

// Discriminated union for operator types
type ComparisonOperator = '>' | '<' | '>=' | '<=' | '==' | '!=';
type CrossOperator = 'cross_up' | 'cross_down';
type RangeOperator = 'touches' | 'within_range';

type ConditionOperator = ComparisonOperator | CrossOperator | RangeOperator;

interface Condition {
  id: string;
  indicator: string;
  operator: ConditionOperator;
  value?: number;
  crossWith?: string;
  minValue?: number;
  maxValue?: number;
  logicalOp: 'AND' | 'OR';
  parentId?: string;
}

// ============================================================================
// CONSTANTS & CONFIGURATION
// ============================================================================

const CONCURRENCY_LIMIT = 5;
const DEFAULT_SLIPPAGE_PCT = 0.1;
const MAX_EXECUTION_TIME_MS = 30000; // 30 second timeout per strategy

// Indicator ranges for validation
const INDICATOR_RANGES: Record<string, { min: number; max: number }> = {
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
// VALIDATOR FUNCTIONS
// ============================================================================

function validateMarketData(bars: Bar[]): { valid: boolean; errors: string[] } {
  const errors: string[] = [];

  if (!bars || bars.length === 0) {
    errors.push('No market data provided');
    return { valid: false, errors };
  }

  const latestBar = bars[bars.length - 1];

  if (!latestBar.open || !latestBar.high || !latestBar.low || !latestBar.close) {
    errors.push('Null OHLC values detected');
  }

  if (latestBar.high < latestBar.low) {
    errors.push('High < Low (invalid bar)');
  }

  if (latestBar.close < latestBar.low || latestBar.close > latestBar.high) {
    errors.push('Close outside high/low range');
  }

  // Check for gaps (>10% move)
  if (bars.length > 1) {
    const previousBar = bars[bars.length - 2];
    const gap = Math.abs((latestBar.open - previousBar.close) / previousBar.close);
    if (gap > 0.1) {
      errors.push(`Gap detected: ${(gap * 100).toFixed(2)}% (>10%)`);
    }
  }

  return { valid: errors.length === 0, errors };
}

function validatePositionConstraints(
  entryPrice: number,
  quantity: number,
  slPct: number,
  tpPct: number,
  direction: 'long' | 'short'
): { valid: boolean; errors: string[] } {
  const errors: string[] = [];

  if (entryPrice <= 0) errors.push('Entry price must be positive');
  if (quantity <= 0 || quantity > 1000) errors.push('Quantity out of bounds [1, 1000]');
  if (slPct < 0.1 || slPct > 20) errors.push('SL must be 0.1%-20%');
  if (tpPct < 0.1 || tpPct > 100) errors.push('TP must be 0.1%-100%');

  // Check SL/TP ordering based on direction
  if (direction === 'long') {
    // For long: SL should be below entry, TP should be above
    const slPrice = entryPrice * (1 - slPct / 100);
    const tpPrice = entryPrice * (1 + tpPct / 100);
    if (slPrice >= entryPrice) errors.push('Long: SL must be below entry price');
    if (tpPrice <= entryPrice) errors.push('Long: TP must be above entry price');
  } else {
    // For short: SL should be above entry, TP should be below
    const slPrice = entryPrice * (1 + slPct / 100);
    const tpPrice = entryPrice * (1 - tpPct / 100);
    if (slPrice <= entryPrice) errors.push('Short: SL must be above entry price');
    if (tpPrice >= entryPrice) errors.push('Short: TP must be below entry price');
  }

  return { valid: errors.length === 0, errors };
}

// ============================================================================
// CONDITION EVALUATION
// ============================================================================

function evaluateCondition(
  condition: Condition,
  bars: Bar[],
  indicatorCache: Map<string, number>
): boolean {
  if (!bars || bars.length === 0) return false;

  const latestBar = bars[bars.length - 1];

  // Get indicator value
  let indicatorValue: number | undefined;

  // Built-in OHLCV indicators
  switch (condition.indicator) {
    case 'Close':
      indicatorValue = latestBar.close;
      break;
    case 'Open':
      indicatorValue = latestBar.open;
      break;
    case 'High':
      indicatorValue = latestBar.high;
      break;
    case 'Low':
      indicatorValue = latestBar.low;
      break;
    case 'Volume':
      indicatorValue = latestBar.volume;
      break;
    default:
      // Check cache for computed indicators (RSI, MACD, etc.)
      indicatorValue = indicatorCache.get(condition.indicator);
  }

  if (indicatorValue === undefined) {
    console.log(`[WARN] Indicator ${condition.indicator} not found in cache or OHLCV`);
    return false;
  }

  // Evaluate based on operator
  if ('value' in condition && condition.operator !== 'cross_up' && condition.operator !== 'cross_down') {
    const value = condition.value!;
    switch (condition.operator as ComparisonOperator) {
      case '>':
        return indicatorValue > value;
      case '<':
        return indicatorValue < value;
      case '>=':
        return indicatorValue >= value;
      case '<=':
        return indicatorValue <= value;
      case '==':
        const epsilon = 0.0001;
        return Math.abs(indicatorValue - value) < epsilon;
      case '!=':
        return indicatorValue !== value;
      default:
        return false;
    }
  }

  // Cross operators (simplified: would need historical data for true cross detection)
  if (condition.operator === 'cross_up' || condition.operator === 'cross_down') {
    // In production, this would compare against crossWith indicator
    // For now, simplified logic: check if indicator > threshold
    return condition.operator === 'cross_up' ? indicatorValue > 50 : indicatorValue < 50;
  }

  // Range operators
  if ('minValue' in condition && 'maxValue' in condition) {
    return indicatorValue >= condition.minValue! && indicatorValue <= condition.maxValue!;
  }

  return false;
}

function evaluateConditionList(
  conditions: Condition[],
  bars: Bar[],
  indicatorCache: Map<string, number>
): boolean {
  if (!conditions || conditions.length === 0) return false;

  // Simplified: treat all as AND
  for (const condition of conditions) {
    if (!evaluateCondition(condition, bars, indicatorCache)) {
      return false;
    }
  }

  return true;
}

// ============================================================================
// POSITION MANAGEMENT
// ============================================================================

async function getOpenPosition(
  supabase: any,
  strategyId: string
): Promise<{ data: PaperPosition | null; error?: string }> {
  try {
    const { data, error } = await supabase
      .from('paper_trading_positions')
      .select('*')
      .eq('strategy_id', strategyId)
      .eq('status', 'open')
      .single();

    if (error) {
      if (error.code === 'PGRST116') {
        // No rows returned - this is expected, not an error
        return { data: null };
      }
      return { data: null, error: error.message };
    }

    return { data };
  } catch (err: any) {
    return { data: null, error: err.message };
  }
}

async function createPosition(
  supabase: any,
  strategy: Strategy,
  entryPrice: number,
  quantity: number,
  direction: 'long' | 'short',
  slPrice: number,
  tpPrice: number
): Promise<ExecutionResult> {
  try {
    // Validate first
    const slPct = Math.abs((entryPrice - slPrice) / entryPrice) * 100;
    const tpPct = Math.abs((tpPrice - entryPrice) / entryPrice) * 100;

    const validation = validatePositionConstraints(entryPrice, quantity, slPct, tpPct, direction);
    if (!validation.valid) {
      return {
        success: false,
        error: {
          type: 'position_constraints_violated',
          violations: validation.errors,
        },
      };
    }

    const { data, error } = await supabase
      .from('paper_trading_positions')
      .insert({
        user_id: strategy.user_id,
        strategy_id: strategy.id,
        symbol_id: strategy.symbol_id,
        timeframe: strategy.timeframe,
        entry_price: entryPrice,
        entry_time: new Date().toISOString(),
        quantity,
        direction,
        stop_loss_price: slPrice,
        take_profit_price: tpPrice,
        status: 'open',
      })
      .select()
      .single();

    if (error) {
      return {
        success: false,
        error: {
          type: 'database_error',
          reason: error.message,
        },
      };
    }

    return {
      success: true,
      action: 'entry_created',
      positionId: data.id,
    };
  } catch (err: any) {
    return {
      success: false,
      error: {
        type: 'database_error',
        reason: err.message,
      },
    };
  }
}

function determineCloseReason(
  position: PaperPosition,
  currentPrice: number,
  exitSignal: boolean,
  bars: Bar[]
): 'SL_HIT' | 'TP_HIT' | 'EXIT_SIGNAL' | 'GAP_FORCED_CLOSE' | null {
  // Check for gaps (>10% move)
  if (bars.length > 1) {
    const previousClose = bars[bars.length - 2].close;
    const gap = Math.abs((currentPrice - previousClose) / previousClose);
    if (gap > 0.1) {
      return 'GAP_FORCED_CLOSE';
    }
  }

  // Check stop loss and take profit
  if (currentPrice <= position.stop_loss_price) return 'SL_HIT';
  if (currentPrice >= position.take_profit_price) return 'TP_HIT';
  if (exitSignal) return 'EXIT_SIGNAL';

  return null;
}

async function closePosition(
  supabase: any,
  position: PaperPosition,
  exitPrice: number,
  closeReason: string
): Promise<ExecutionResult> {
  try {
    // Calculate P&L
    let pnl: number;
    if (position.direction === 'long') {
      pnl = (exitPrice - position.entry_price) * position.quantity;
    } else {
      pnl = (position.entry_price - exitPrice) * position.quantity;
    }

    // Use optimistic locking: only update if status is still 'open'
    const { data, error } = await supabase
      .from('paper_trading_positions')
      .update({
        status: 'closed',
        exit_price: exitPrice,
        exit_time: new Date().toISOString(),
        pnl,
        close_reason: closeReason,
      })
      .eq('id', position.id)
      .eq('status', 'open') // Race condition prevention!
      .select()
      .single();

    if (error || !data) {
      // If no row returned, concurrent close detected
      return {
        success: false,
        error: {
          type: 'position_locked',
          reason: 'concurrent_close_detected',
        },
      };
    }

    return {
      success: true,
      action: 'position_closed',
      positionId: position.id,
    };
  } catch (err: any) {
    return {
      success: false,
      error: {
        type: 'database_error',
        reason: err.message,
      },
    };
  }
}

// ============================================================================
// MAIN EXECUTOR
// ============================================================================

async function executePaperTradingCycle(
  supabase: any,
  symbol: string,
  timeframe: string
): Promise<ExecutionResult[]> {
  try {
    // 1. Fetch active strategies for this symbol/timeframe
    const { data: strategies, error: stratError } = await supabase
      .from('strategy_user_strategies')
      .select('*')
      .eq('symbol_id', symbol)
      .eq('timeframe', timeframe)
      .eq('paper_trading_enabled', true);

    if (stratError) {
      console.error('Failed to fetch strategies:', stratError);
      return [
        {
          success: false,
          error: {
            type: 'database_error',
            reason: stratError.message,
          },
        },
      ];
    }

    if (!strategies || strategies.length === 0) {
      return [
        {
          success: true,
          action: 'no_action',
        },
      ];
    }

    // 2. Fetch latest market data (ONCE - reuse for all strategies)
    const { data: bars, error: barError } = await supabase
      .from('ohlc_bars_v2')
      .select('*')
      .eq('symbol_id', symbol)
      .eq('timeframe', timeframe)
      .order('ts', { ascending: false })
      .limit(100);

    if (barError || !bars) {
      console.error('Failed to fetch market data:', barError);
      return [
        {
          success: false,
          error: {
            type: 'invalid_market_data',
            reason: barError?.message || 'No bars found',
          },
        },
      ];
    }

    // Reverse to get chronological order
    const sortedBars: Bar[] = bars
      .reverse()
      .map((b: any) => ({
        time: b.ts,
        open: b.open,
        high: b.high,
        low: b.low,
        close: b.close,
        volume: b.volume,
      }));

    // Validate market data
    const validation = validateMarketData(sortedBars);
    if (!validation.valid) {
      console.warn('Market data validation warnings:', validation.errors);
    }

    // 3. Pre-calculate indicators (shared cache)
    const indicatorCache = new Map<string, number>();
    // In production, calculate RSI, MACD, etc. here
    // For now, mock some indicator values
    indicatorCache.set('RSI', 55);
    indicatorCache.set('MACD', 0.5);
    indicatorCache.set('Volume_MA', 1000000);

    // 4. Execute strategies with concurrency limiting
    const results: ExecutionResult[] = [];
    const limiter = new Semaphore(CONCURRENCY_LIMIT);

    for (const strategy of strategies) {
      await limiter.acquire();

      try {
        const result = await executeStrategy(
          supabase,
          strategy,
          sortedBars,
          indicatorCache
        );
        results.push(result);
      } finally {
        limiter.release();
      }
    }

    return results;
  } catch (error: any) {
    console.error('Executor error:', error);
    return [
      {
        success: false,
        error: {
          type: 'condition_eval_failed',
          indicator: 'unknown',
          reason: error.message,
        },
      },
    ];
  }
}

async function executeStrategy(
  supabase: any,
  strategy: Strategy,
  bars: Bar[],
  indicatorCache: Map<string, number>
): Promise<ExecutionResult> {
  try {
    const latestPrice = bars[bars.length - 1].close;

    // Check for open position
    const { data: openPosition } = await getOpenPosition(supabase, strategy.id);

    if (openPosition) {
      // Position is open - check for exit signal
      const exitSignal = evaluateConditionList(
        strategy.exit_conditions,
        bars,
        indicatorCache
      );

      const closeReason = determineCloseReason(
        openPosition,
        latestPrice,
        exitSignal,
        bars
      );

      if (closeReason) {
        const result = await closePosition(supabase, openPosition, latestPrice, closeReason);
        return result;
      }

      return { success: true, action: 'no_action' };
    } else {
      // No open position - check for entry signal
      const entrySignal = evaluateConditionList(
        strategy.entry_conditions,
        bars,
        indicatorCache
      );

      if (entrySignal) {
        // Create position with realistic SL/TP (default: 2% SL, 5% TP)
        const slPrice = latestPrice * 0.98; // 2% stop loss
        const tpPrice = latestPrice * 1.05; // 5% take profit
        const quantity = 10; // Default: 10 shares

        const result = await createPosition(
          supabase,
          strategy,
          latestPrice,
          quantity,
          'long',
          slPrice,
          tpPrice
        );

        return result;
      }

      return { success: true, action: 'no_action' };
    }
  } catch (error: any) {
    return {
      success: false,
      error: {
        type: 'condition_eval_failed',
        indicator: 'unknown',
        reason: error.message,
      },
    };
  }
}

// ============================================================================
// EDGE FUNCTION HANDLER
// ============================================================================

Deno.serve(async (req) => {
  try {
    // CORS headers
    if (req.method === 'OPTIONS') {
      return new Response(null, {
        headers: {
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'POST, OPTIONS',
          'Access-Control-Allow-Headers': 'Content-Type, Authorization',
        },
      });
    }

    // Initialize Supabase client
    const supabase = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_SERVICE_KEY')!
    );

    // Parse request
    const body = await req.json();
    const { symbol, timeframe } = body;

    if (!symbol || !timeframe) {
      return new Response(
        JSON.stringify({ error: 'symbol and timeframe are required' }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    // Execute paper trading cycle
    const results = await executePaperTradingCycle(supabase, symbol, timeframe);

    // Count successes/failures
    const successCount = results.filter((r) => r.success).length;
    const failureCount = results.length - successCount;

    return new Response(
      JSON.stringify({
        success: true,
        execution_time: new Date().toISOString(),
        symbol,
        timeframe,
        strategies_processed: results.length,
        successful: successCount,
        failed: failureCount,
        results,
      }),
      {
        headers: { 'Content-Type': 'application/json' },
      }
    );
  } catch (error: any) {
    console.error('Edge function error:', error);
    return new Response(
      JSON.stringify({
        success: false,
        error: error.message,
      }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }
});
