// ============================================================================
// PAPER TRADING EXECUTOR - Real-time Strategy Execution Engine
// File: supabase/functions/paper-trading-executor/index.ts
// Purpose: Evaluate strategies, execute trades, manage positions with race prevention
// ============================================================================

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.97.0";
import { getSupabaseClientWithAuth } from "../_shared/supabase-client.ts";

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
  status: "open" | "closed";
  entry_price: number;
  entry_time: string;
  quantity: number;
  direction: "long" | "short";
  stop_loss_price: number;
  take_profit_price: number;
  exit_price?: number;
  exit_time?: string;
  pnl?: number;
  close_reason?: string;
}

// Type-safe execution result with discriminated unions
type ExecutionResult =
  | {
    success: true;
    action: "entry_created" | "position_closed" | "no_action";
    positionId?: string;
  }
  | { success: false; error: ExecutionError };

type ExecutionError =
  | { type: "condition_eval_failed"; indicator: string; reason: string }
  | { type: "position_locked"; reason: "concurrent_close_detected" }
  | { type: "invalid_market_data"; reason: string }
  | { type: "position_constraints_violated"; violations: string[] }
  | { type: "database_error"; reason: string };

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
type ComparisonOperator = ">" | "<" | ">=" | "<=" | "==" | "!=";
type CrossOperator = "cross_up" | "cross_down";
type RangeOperator = "touches" | "within_range";

type ConditionOperator = ComparisonOperator | CrossOperator | RangeOperator;

interface Condition {
  id: string;
  indicator: string;
  operator: ConditionOperator;
  value?: number;
  crossWith?: string;
  minValue?: number;
  maxValue?: number;
  logicalOp: "AND" | "OR";
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
    errors.push("No market data provided");
    return { valid: false, errors };
  }

  const latestBar = bars[bars.length - 1];

  if (
    !latestBar.open || !latestBar.high || !latestBar.low || !latestBar.close
  ) {
    errors.push("Null OHLC values detected");
  }

  if (latestBar.high < latestBar.low) {
    errors.push("High < Low (invalid bar)");
  }

  if (latestBar.close < latestBar.low || latestBar.close > latestBar.high) {
    errors.push("Close outside high/low range");
  }

  // Check for gaps (>10% move)
  if (bars.length > 1) {
    const previousBar = bars[bars.length - 2];
    const gap = Math.abs(
      (latestBar.open - previousBar.close) / previousBar.close,
    );
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
  direction: "long" | "short",
): { valid: boolean; errors: string[] } {
  const errors: string[] = [];

  if (entryPrice <= 0) errors.push("Entry price must be positive");
  if (quantity <= 0 || quantity > 1000) {
    errors.push("Quantity out of bounds [1, 1000]");
  }
  if (slPct < 0.1 || slPct > 20) errors.push("SL must be 0.1%-20%");
  if (tpPct < 0.1 || tpPct > 100) errors.push("TP must be 0.1%-100%");

  // Check SL/TP ordering based on direction
  if (direction === "long") {
    // For long: SL should be below entry, TP should be above
    const slPrice = entryPrice * (1 - slPct / 100);
    const tpPrice = entryPrice * (1 + tpPct / 100);
    if (slPrice >= entryPrice) {
      errors.push("Long: SL must be below entry price");
    }
    if (tpPrice <= entryPrice) {
      errors.push("Long: TP must be above entry price");
    }
  } else {
    // For short: SL should be above entry, TP should be below
    const slPrice = entryPrice * (1 + slPct / 100);
    const tpPrice = entryPrice * (1 - tpPct / 100);
    if (slPrice <= entryPrice) {
      errors.push("Short: SL must be above entry price");
    }
    if (tpPrice >= entryPrice) {
      errors.push("Short: TP must be below entry price");
    }
  }

  return { valid: errors.length === 0, errors };
}

// ============================================================================
// CONDITION EVALUATION
// ============================================================================

function evaluateCondition(
  condition: Condition,
  bars: Bar[],
  indicatorCache: Map<string, number>,
): boolean {
  if (!bars || bars.length === 0) return false;

  const latestBar = bars[bars.length - 1];

  // Get indicator value
  let indicatorValue: number | undefined;

  // Built-in OHLCV indicators
  switch (condition.indicator) {
    case "Close":
      indicatorValue = latestBar.close;
      break;
    case "Open":
      indicatorValue = latestBar.open;
      break;
    case "High":
      indicatorValue = latestBar.high;
      break;
    case "Low":
      indicatorValue = latestBar.low;
      break;
    case "Volume":
      indicatorValue = latestBar.volume;
      break;
    default:
      // Check cache for computed indicators (RSI, MACD, etc.)
      indicatorValue = indicatorCache.get(condition.indicator);
  }

  if (indicatorValue === undefined) {
    console.log(
      `[WARN] Indicator ${condition.indicator} not found in cache or OHLCV`,
    );
    return false;
  }

  // Evaluate based on operator
  if (
    "value" in condition && condition.operator !== "cross_up" &&
    condition.operator !== "cross_down"
  ) {
    const value = condition.value!;
    switch (condition.operator as ComparisonOperator) {
      case ">":
        return indicatorValue > value;
      case "<":
        return indicatorValue < value;
      case ">=":
        return indicatorValue >= value;
      case "<=":
        return indicatorValue <= value;
      case "==": {
        const epsilon = 0.0001;
        return Math.abs(indicatorValue - value) < epsilon;
      }
      case "!=":
        return indicatorValue !== value;
      default:
        return false;
    }
  }

  // Cross operators — compare current value against previous bar's value
  if (
    condition.operator === "cross_up" || condition.operator === "cross_down"
  ) {
    const prevValue = indicatorCache.get(`${condition.indicator}_prev`) ??
      indicatorValue;
    if (condition.operator === "cross_up") {
      return prevValue <= 50 && indicatorValue > 50;
    } else {
      return prevValue >= 50 && indicatorValue < 50;
    }
  }

  // Range operators
  if ("minValue" in condition && "maxValue" in condition) {
    return indicatorValue >= condition.minValue! &&
      indicatorValue <= condition.maxValue!;
  }

  return false;
}

function evaluateConditionList(
  conditions: Condition[],
  bars: Bar[],
  indicatorCache: Map<string, number>,
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
  strategyId: string,
): Promise<{ data: PaperPosition | null; error?: string }> {
  try {
    const { data, error } = await supabase
      .from("paper_trading_positions")
      .select("id, symbol_id, symbol, direction, entry_price, current_price, quantity, status, stop_loss, take_profit, user_id, created_at")
      .eq("strategy_id", strategyId)
      .eq("status", "open")
      .single();

    if (error) {
      if (error.code === "PGRST116") {
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
  direction: "long" | "short",
  slPrice: number,
  tpPrice: number,
): Promise<ExecutionResult> {
  try {
    // Validate first
    const slPct = Math.abs((entryPrice - slPrice) / entryPrice) * 100;
    const tpPct = Math.abs((tpPrice - entryPrice) / entryPrice) * 100;

    const validation = validatePositionConstraints(
      entryPrice,
      quantity,
      slPct,
      tpPct,
      direction,
    );
    if (!validation.valid) {
      return {
        success: false,
        error: {
          type: "position_constraints_violated",
          violations: validation.errors,
        },
      };
    }

    const { data, error } = await supabase
      .from("paper_trading_positions")
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
        status: "open",
      })
      .select()
      .single();

    if (error) {
      return {
        success: false,
        error: {
          type: "database_error",
          reason: error.message,
        },
      };
    }

    return {
      success: true,
      action: "entry_created",
      positionId: data.id,
    };
  } catch (err: any) {
    return {
      success: false,
      error: {
        type: "database_error",
        reason: err.message,
      },
    };
  }
}

function determineCloseReason(
  position: PaperPosition,
  currentPrice: number,
  exitSignal: boolean,
  bars: Bar[],
): "SL_HIT" | "TP_HIT" | "EXIT_SIGNAL" | "GAP_FORCED_CLOSE" | null {
  // Check for gaps (>10% move)
  if (bars.length > 1) {
    const previousClose = bars[bars.length - 2].close;
    const gap = Math.abs((currentPrice - previousClose) / previousClose);
    if (gap > 0.1) {
      return "GAP_FORCED_CLOSE";
    }
  }

  // Check stop loss and take profit
  if (currentPrice <= position.stop_loss_price) return "SL_HIT";
  if (currentPrice >= position.take_profit_price) return "TP_HIT";
  if (exitSignal) return "EXIT_SIGNAL";

  return null;
}

async function closePosition(
  supabase: any,
  position: PaperPosition,
  exitPrice: number,
  closeReason: string,
): Promise<ExecutionResult> {
  try {
    // Calculate P&L
    let pnl: number;
    if (position.direction === "long") {
      pnl = (exitPrice - position.entry_price) * position.quantity;
    } else {
      pnl = (position.entry_price - exitPrice) * position.quantity;
    }

    // Use optimistic locking: only update if status is still 'open'
    const { data, error } = await supabase
      .from("paper_trading_positions")
      .update({
        status: "closed",
        exit_price: exitPrice,
        exit_time: new Date().toISOString(),
        pnl,
        close_reason: closeReason,
      })
      .eq("id", position.id)
      .eq("status", "open") // Race condition prevention!
      .select()
      .single();

    if (error || !data) {
      // If no row returned, concurrent close detected
      return {
        success: false,
        error: {
          type: "position_locked",
          reason: "concurrent_close_detected",
        },
      };
    }

    return {
      success: true,
      action: "position_closed",
      positionId: position.id,
    };
  } catch (err: any) {
    return {
      success: false,
      error: {
        type: "database_error",
        reason: err.message,
      },
    };
  }
}

// ============================================================================
// INDICATOR COMPUTATION
// ============================================================================

function computeRSI(bars: { close: number }[], period = 14): number {
  if (bars.length < period + 1) return 50;
  const closes = bars.map((b) => b.close);
  let gains = 0, losses = 0;
  for (let i = 1; i <= period; i++) {
    const diff = closes[i] - closes[i - 1];
    if (diff > 0) gains += diff;
    else losses -= diff;
  }
  let avgGain = gains / period, avgLoss = losses / period;
  for (let i = period + 1; i < closes.length; i++) {
    const diff = closes[i] - closes[i - 1];
    avgGain = (avgGain * (period - 1) + Math.max(0, diff)) / period;
    avgLoss = (avgLoss * (period - 1) + Math.max(0, -diff)) / period;
  }
  if (avgLoss === 0) return 100;
  const rs = avgGain / avgLoss;
  return 100 - 100 / (1 + rs);
}

function computeEMA(values: number[], period: number): number[] {
  const k = 2 / (period + 1);
  const ema = [values[0]];
  for (let i = 1; i < values.length; i++) {
    ema.push(values[i] * k + ema[i - 1] * (1 - k));
  }
  return ema;
}

function computeMACD(bars: { close: number }[]): number {
  const closes = bars.map((b) => b.close);
  if (closes.length < 26) return 0;
  const ema12 = computeEMA(closes, 12);
  const ema26 = computeEMA(closes, 26);
  const macdLine = ema12.map((v, i) => v - ema26[i]);
  return macdLine[macdLine.length - 1];
}

function computeVolumeMA(bars: { volume: number }[], period = 20): number {
  const slice = bars.slice(-period);
  return slice.reduce((sum, b) => sum + (b.volume || 0), 0) / slice.length;
}

// ============================================================================
// MAIN EXECUTOR
// ============================================================================

async function executePaperTradingCycle(
  supabase: any,
  symbol: string,
  timeframe: string,
): Promise<ExecutionResult[]> {
  try {
    // 1. Fetch active strategies for this symbol/timeframe
    const { data: strategies, error: stratError } = await supabase
      .from("strategy_user_strategies")
      .select("id, name, config, is_active, paper_trading_enabled")
      .eq("symbol_id", symbol)
      .eq("timeframe", timeframe)
      .eq("paper_trading_enabled", true);

    if (stratError) {
      console.error("Failed to fetch strategies:", stratError);
      return [
        {
          success: false,
          error: {
            type: "database_error",
            reason: stratError.message,
          },
        },
      ];
    }

    if (!strategies || strategies.length === 0) {
      return [
        {
          success: true,
          action: "no_action",
        },
      ];
    }

    // 2. Fetch latest market data (ONCE - reuse for all strategies)
    const { data: bars, error: barError } = await supabase
      .from("ohlc_bars_v2")
      .select("ts, open, high, low, close, volume")
      .eq("symbol_id", symbol)
      .eq("timeframe", timeframe)
      .order("ts", { ascending: false })
      .limit(100);

    if (barError || !bars) {
      console.error("Failed to fetch market data:", barError);
      return [
        {
          success: false,
          error: {
            type: "invalid_market_data",
            reason: barError?.message || "No bars found",
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
      console.warn("Market data validation warnings:", validation.errors);
    }

    // 3. Update current_price on all open positions for this symbol so the native
    //    dashboard can display live unrealised P&L without a separate price fetch.
    const latestClose = sortedBars[sortedBars.length - 1].close;
    await supabase
      .from("paper_trading_positions")
      .update({ current_price: latestClose })
      .eq("symbol_id", symbol)
      .eq("status", "open");

    // 4. Pre-calculate indicators (shared cache)
    const indicatorCache = new Map<string, number>();

    // Current bar indicators
    indicatorCache.set("RSI", computeRSI(sortedBars));
    indicatorCache.set("MACD", computeMACD(sortedBars));
    indicatorCache.set("Volume_MA", computeVolumeMA(sortedBars));

    // Previous bar indicators for crossover detection
    const prevBars = sortedBars.slice(0, -1);
    const prevRSI = prevBars.length >= 15 ? computeRSI(prevBars) : 50;
    indicatorCache.set("RSI_prev", prevRSI);
    const prevMACD = prevBars.length >= 27 ? computeMACD(prevBars) : 0;
    indicatorCache.set("MACD_prev", prevMACD);

    // 5. Execute strategies with concurrency limiting
    const results: ExecutionResult[] = [];
    const limiter = new Semaphore(CONCURRENCY_LIMIT);

    for (const strategy of strategies) {
      await limiter.acquire();

      try {
        const result = await executeStrategy(
          supabase,
          strategy,
          sortedBars,
          indicatorCache,
        );
        results.push(result);
      } finally {
        limiter.release();
      }
    }

    return results;
  } catch (error: any) {
    console.error("Executor error:", error);
    return [
      {
        success: false,
        error: {
          type: "condition_eval_failed",
          indicator: "unknown",
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
  indicatorCache: Map<string, number>,
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
        indicatorCache,
      );

      const closeReason = determineCloseReason(
        openPosition,
        latestPrice,
        exitSignal,
        bars,
      );

      if (closeReason) {
        const result = await closePosition(
          supabase,
          openPosition,
          latestPrice,
          closeReason,
        );
        return result;
      }

      return { success: true, action: "no_action" };
    } else {
      // No open position - check for entry signal
      const entrySignal = evaluateConditionList(
        strategy.entry_conditions,
        bars,
        indicatorCache,
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
          "long",
          slPrice,
          tpPrice,
        );

        return result;
      }

      return { success: true, action: "no_action" };
    }
  } catch (error: any) {
    return {
      success: false,
      error: {
        type: "condition_eval_failed",
        indicator: "unknown",
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
    const corsHeaders = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, Authorization, apikey",
    };

    // CORS preflight
    if (req.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders });
    }

    // Initialize Supabase service-role client (used for writes / execution)
    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    );

    const url = new URL(req.url);

    // ========================================================================
    // GET — Read endpoints for positions, trades, and summary
    // ========================================================================
    if (req.method === "GET") {
      // Authenticate the requesting user via their JWT
      const authHeader = req.headers.get("Authorization") ?? "";
      const supabaseAuth = getSupabaseClientWithAuth(authHeader);
      const { data: { user }, error: authError } = await supabaseAuth.auth
        .getUser();
      if (authError || !user) {
        return new Response(
          JSON.stringify({ error: "Authentication required" }),
          {
            status: 401,
            headers: { "Content-Type": "application/json", ...corsHeaders },
          },
        );
      }

      const action = url.searchParams.get("action") ?? "positions";
      const limit = Math.min(
        50,
        Math.max(1, Number(url.searchParams.get("limit") || 50)),
      );
      const offset = Math.max(
        0,
        Number(url.searchParams.get("offset") || 0),
      );

      if (action === "positions") {
        // List open positions for the authenticated user
        const { data: positions, error } = await supabase
          .from("paper_trading_positions")
          .select(
            "id, strategy_id, symbol_id, direction, entry_price, current_price, quantity, status, stop_loss_price, take_profit_price, entry_time, created_at, updated_at",
          )
          .eq("user_id", user.id)
          .eq("status", "open")
          .order("created_at", { ascending: false })
          .range(offset, offset + limit - 1);

        if (error) {
          console.error(
            "[paper-trading-executor] positions query error:",
            error,
          );
          return new Response(
            JSON.stringify({ error: "Failed to fetch positions" }),
            {
              status: 500,
              headers: { "Content-Type": "application/json", ...corsHeaders },
            },
          );
        }

        return new Response(
          JSON.stringify({
            positions: positions ?? [],
            total: positions?.length ?? 0,
            offset,
            limit,
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json", ...corsHeaders },
          },
        );
      }

      if (action === "trades") {
        // List closed trades for the authenticated user
        const { data: trades, error } = await supabase
          .from("paper_trading_trades")
          .select(
            "id, strategy_id, symbol_id, direction, entry_price, exit_price, quantity, pnl, pnl_pct, close_reason, entry_time, exit_time, created_at",
          )
          .eq("user_id", user.id)
          .order("created_at", { ascending: false })
          .range(offset, offset + limit - 1);

        if (error) {
          console.error(
            "[paper-trading-executor] trades query error:",
            error,
          );
          return new Response(
            JSON.stringify({ error: "Failed to fetch trades" }),
            {
              status: 500,
              headers: { "Content-Type": "application/json", ...corsHeaders },
            },
          );
        }

        return new Response(
          JSON.stringify({
            trades: trades ?? [],
            total: trades?.length ?? 0,
            offset,
            limit,
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json", ...corsHeaders },
          },
        );
      }

      if (action === "summary") {
        // Aggregate performance metrics for the authenticated user
        const { data: trades } = await supabase
          .from("paper_trading_trades")
          .select("pnl, pnl_pct")
          .eq("user_id", user.id);

        const allTrades = trades ?? [];
        const totalTrades = allTrades.length;
        const winningTrades = allTrades.filter((t) => (t.pnl ?? 0) > 0).length;
        const totalPnl = allTrades.reduce(
          (sum: number, t: { pnl: number | null }) => sum + (t.pnl ?? 0),
          0,
        );
        const winRate = totalTrades > 0 ? winningTrades / totalTrades : 0;

        return new Response(
          JSON.stringify({
            total_trades: totalTrades,
            win_rate: winRate,
            total_pnl: totalPnl,
            winning_trades: winningTrades,
            losing_trades: totalTrades - winningTrades,
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json", ...corsHeaders },
          },
        );
      }

      return new Response(
        JSON.stringify({
          error: "Unknown action. Use: positions, trades, summary",
        }),
        {
          status: 400,
          headers: { "Content-Type": "application/json", ...corsHeaders },
        },
      );
    }

    // Parse POST request body
    const body = await req.json();
    const { action } = body;

    // Manual close-position action — allows native clients to close positions on demand.
    if (action === "close_position") {
      const { position_id, exit_price } = body;
      if (!position_id || typeof exit_price !== "number") {
        return new Response(
          JSON.stringify({ error: "position_id and exit_price are required" }),
          { status: 400, headers: { "Content-Type": "application/json" } },
        );
      }

      // Fetch position to compute P&L
      const { data: pos, error: fetchErr } = await supabase
        .from("paper_trading_positions")
        .select("id,direction,entry_price,quantity,status")
        .eq("id", position_id)
        .eq("status", "open")
        .single();

      if (fetchErr || !pos) {
        return new Response(
          JSON.stringify({ error: "Position not found or already closed" }),
          { status: 404, headers: { "Content-Type": "application/json" } },
        );
      }

      const pnl = pos.direction === "long"
        ? (exit_price - pos.entry_price) * pos.quantity
        : (pos.entry_price - exit_price) * pos.quantity;

      const result = await closePosition(supabase, pos as PaperPosition, exit_price, "MANUAL");
      return new Response(JSON.stringify({ ...result, pnl }), {
        headers: { "Content-Type": "application/json" },
      });
    }

    const { symbol, timeframe } = body;

    if (!symbol || !timeframe) {
      return new Response(
        JSON.stringify({ error: "symbol and timeframe are required" }),
        {
          status: 400,
          headers: { "Content-Type": "application/json" },
        },
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
        headers: { "Content-Type": "application/json" },
      },
    );
  } catch (error: unknown) {
    console.error("[paper-trading-executor] Edge function error:", error);
    return new Response(
      JSON.stringify({
        success: false,
        error: "An internal error occurred",
      }),
      {
        status: 500,
        headers: { "Content-Type": "application/json" },
      },
    );
  }
});
