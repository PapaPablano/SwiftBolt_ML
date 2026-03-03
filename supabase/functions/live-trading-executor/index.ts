// ============================================================================
// LIVE TRADING EXECUTOR — Real-money strategy execution via TradeStation
// File: supabase/functions/live-trading-executor/index.ts
//
// Architecture: Mirrors paper-trading-executor structure.
// Uses _shared/condition-evaluator.ts for signal evaluation.
// Uses _shared/tradestation-client.ts for read-only broker API calls.
// Write operations (placeMarketOrder, placeBracketOrders) are co-located
// here to limit blast radius of brokerage write access.
// ============================================================================

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.97.0";
import { getSupabaseClientWithAuth } from "../_shared/supabase-client.ts";
import {
  getCorsHeaders,
  handlePreflight,
  corsResponse,
  errorResponse,
} from "../_shared/cors.ts";
import {
  type BrokerToken,
  type AccountBalance,
  type OrderFillResult,
  type CircuitBreakerResult,
  type LiveExecutionError,
  type NormalizedSymbol,
  ensureFreshToken,
  getAccountBalance,
  getOrderStatus,
  getBatchOrderStatus,
  normalizeSymbol,
  validateSymbol,
  validateTimeframe,
  sanitizeBrokerError,
  FUTURES_MULTIPLIERS,
  MAX_FUTURES_CONTRACTS,
} from "../_shared/tradestation-client.ts";
import { roundToTick } from "../_shared/futures-calendar.ts";
import {
  type Bar,
  type Condition,
  IndicatorCache,
  evaluateStrategySignals,
} from "../_shared/condition-evaluator.ts";

// ============================================================================
// TYPE DEFINITIONS
// ============================================================================

interface LiveStrategy {
  id: string;
  user_id: string;
  name: string;
  symbol_id: string;
  timeframe: string;
  config: {
    entry_conditions: Condition[];
    exit_conditions: Condition[];
    parameters: Record<string, unknown>;
  };
  live_trading_enabled: boolean;
  live_risk_pct: number;
  live_daily_loss_limit_pct: number;
  live_max_positions: number;
  live_max_position_pct: number;
  live_trading_paused: boolean;
}

interface LivePosition {
  id: string;
  user_id: string;
  strategy_id: string;
  symbol_id: string;
  timeframe: string;
  entry_price: number;
  current_price: number | null;
  quantity: number;
  direction: "long" | "short";
  stop_loss_price: number;
  take_profit_price: number;
  status: string;
  broker_order_id: string | null;
  broker_sl_order_id: string | null;
  broker_tp_order_id: string | null;
  account_id: string;
  asset_type: string;
  contract_multiplier: number;
}

type ExecutionResult =
  | {
    success: true;
    action:
      | "entry_created"
      | "position_closed"
      | "no_action"
      | "bracket_fill_detected";
    positionId?: string;
  }
  | { success: false; error: LiveExecutionError };

// ============================================================================
// CONSTANTS
// ============================================================================

const CONCURRENCY_LIMIT = 5;
const POLL_TIMEOUT_MS = 15_000; // 15s max poll (P1 #087: 60s edge function limit)
const POLL_INTERVAL_MS = 1_000; // 1s between poll attempts
const RATE_LIMIT_WINDOW_MS = 60_000;
const RATE_LIMIT_MAX_REQUESTS = 10;

// ============================================================================
// RATE LIMITER (DB-BACKED, P1 #090)
// ============================================================================

async function checkRateLimit(
  supabase: any,
  userId: string,
): Promise<boolean> {
  const windowStart = new Date(
    Math.floor(Date.now() / RATE_LIMIT_WINDOW_MS) * RATE_LIMIT_WINDOW_MS,
  ).toISOString();

  // Upsert: increment count if window exists, create if not
  const { data, error } = await supabase.rpc("increment_rate_limit", {
    p_user_id: userId,
    p_window_start: windowStart,
    p_max_requests: RATE_LIMIT_MAX_REQUESTS,
  });

  if (error) {
    // If RPC doesn't exist, fall back to manual check
    const { data: existing } = await supabase
      .from("live_order_rate_limits")
      .select("request_count")
      .eq("user_id", userId)
      .eq("window_start", windowStart)
      .maybeSingle();

    if (existing && existing.request_count >= RATE_LIMIT_MAX_REQUESTS) {
      return false;
    }

    // Upsert manually
    await supabase
      .from("live_order_rate_limits")
      .upsert({
        user_id: userId,
        window_start: windowStart,
        request_count: (existing?.request_count ?? 0) + 1,
      });

    return true;
  }

  return data === true;
}

// ============================================================================
// WRITE OPERATIONS (co-located with executor, P3 #107)
// ============================================================================

const getBaseUrl = (): string =>
  Deno.env.get("TRADESTATION_USE_SIM") === "true"
    ? "https://sim-api.tradestation.com/v3"
    : "https://api.tradestation.com/v3";

/**
 * Place a market entry order.
 */
async function placeMarketOrder(
  accessToken: string,
  accountId: string,
  symbol: string,
  quantity: number,
  tradeAction: "BUY" | "SELL" | "BUYTOCOVER" | "SELLSHORT",
): Promise<string> {
  const url = `${getBaseUrl()}/orderexecution/orders`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${accessToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      AccountID: accountId,
      Symbol: symbol,
      Quantity: String(quantity),
      OrderType: "Market",
      TradeAction: tradeAction,
      TimeInForce: { Duration: "DAY" },
      Route: "Intelligent",
    }),
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Order placement failed: ${sanitizeBrokerError(body)}`);
  }

  const data = await response.json();
  const orderId = data.Orders?.[0]?.OrderID ?? data.OrderID;
  if (!orderId) throw new Error("No OrderID in response");
  return orderId;
}

/**
 * Place bracket orders (SL + TP) as an order group.
 */
async function placeBracketOrders(
  accessToken: string,
  accountId: string,
  symbol: string,
  quantity: number,
  closeAction: "SELL" | "BUYTOCOVER",
  stopLossPrice: number,
  takeProfitPrice: number,
): Promise<{ slOrderId: string; tpOrderId: string }> {
  const url = `${getBaseUrl()}/orderexecution/ordergroups`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${accessToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      Type: "BRK",
      Orders: [
        {
          AccountID: accountId,
          Symbol: symbol,
          Quantity: String(quantity),
          OrderType: "StopMarket",
          TradeAction: closeAction,
          StopPrice: String(stopLossPrice),
          TimeInForce: { Duration: "GTC" },
          Route: "Intelligent",
        },
        {
          AccountID: accountId,
          Symbol: symbol,
          Quantity: String(quantity),
          OrderType: "Limit",
          TradeAction: closeAction,
          LimitPrice: String(takeProfitPrice),
          TimeInForce: { Duration: "GTC" },
          Route: "Intelligent",
        },
      ],
    }),
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Bracket placement failed: ${sanitizeBrokerError(body)}`);
  }

  const data = await response.json();
  const orders = data.Orders ?? [];
  if (orders.length < 2) throw new Error("Expected 2 bracket orders");

  return {
    slOrderId: orders[0].OrderID,
    tpOrderId: orders[1].OrderID,
  };
}

/**
 * Cancel a pending order.
 */
async function cancelOrder(
  accessToken: string,
  orderId: string,
): Promise<void> {
  const url = `${getBaseUrl()}/orderexecution/orders/${encodeURIComponent(orderId)}`;
  await fetch(url, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}

/**
 * Poll for order fill status (max POLL_TIMEOUT_MS).
 */
async function pollOrderFill(
  accessToken: string,
  accountId: string,
  orderId: string,
): Promise<OrderFillResult> {
  const deadline = Date.now() + POLL_TIMEOUT_MS;
  let lastResult: OrderFillResult = {
    filledQuantity: 0,
    fillPrice: 0,
    status: "PENDING",
  };

  while (Date.now() < deadline) {
    const result = await getOrderStatus(accessToken, accountId, orderId);
    lastResult = result;

    // FLL = Filled, FPR = Partially Filled (still alive)
    if (result.status === "FLL" || result.status === "Filled") {
      return result;
    }
    if (result.status === "FPR" || result.status === "Partial Fill") {
      return result; // Accept partial fill
    }
    if (
      result.status === "REJ" || result.status === "Rejected" ||
      result.status === "CAN" || result.status === "Canceled"
    ) {
      return result; // Order was rejected/cancelled
    }

    await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
  }

  return lastResult; // Return whatever status we last saw
}

// ============================================================================
// CIRCUIT BREAKERS
// ============================================================================

/**
 * Check if US equity market is open (9:30am–4:00pm ET, Mon–Fri).
 */
function checkMarketHours(): CircuitBreakerResult {
  const now = new Date();
  const etTime = new Date(
    now.toLocaleString("en-US", { timeZone: "America/New_York" }),
  );
  const day = etTime.getDay();
  const hours = etTime.getHours();
  const minutes = etTime.getMinutes();
  const timeMinutes = hours * 60 + minutes;

  if (day === 0 || day === 6) {
    return { allowed: false, reason: "Weekend", rule: "market_hours" };
  }

  // 9:30 = 570, 16:00 = 960
  if (timeMinutes < 570 || timeMinutes >= 960) {
    return {
      allowed: false,
      reason: "Outside market hours (9:30-16:00 ET)",
      rule: "market_hours",
    };
  }

  return { allowed: true };
}

/**
 * Check daily realized loss against limit.
 */
async function checkDailyLossLimit(
  supabase: any,
  userId: string,
  currentEquity: number,
  dailyLossLimitPct: number,
): Promise<CircuitBreakerResult> {
  // Get today's start in ET
  const now = new Date();
  const etDateStr = now.toLocaleDateString("en-US", {
    timeZone: "America/New_York",
  });
  const todayStartET = new Date(`${etDateStr} 00:00:00`);

  const { data: trades } = await supabase
    .from("live_trading_trades")
    .select("pnl")
    .eq("user_id", userId)
    .gte("exit_time", todayStartET.toISOString());

  const dailyPnl = (trades ?? []).reduce(
    (sum: number, t: { pnl: number }) => sum + t.pnl,
    0,
  );

  const maxLoss = -(currentEquity * dailyLossLimitPct);
  if (dailyPnl < maxLoss) {
    return {
      allowed: false,
      reason: `Daily loss limit hit (${dailyPnl.toFixed(2)} < ${maxLoss.toFixed(2)})`,
      rule: "daily_loss",
    };
  }

  return { allowed: true };
}

/**
 * Check max concurrent open positions.
 */
async function checkMaxPositions(
  supabase: any,
  userId: string,
  maxPositions: number,
): Promise<CircuitBreakerResult> {
  const { count } = await supabase
    .from("live_trading_positions")
    .select("id", { count: "exact", head: true })
    .eq("user_id", userId)
    .in("status", ["pending_entry", "pending_bracket", "open"]);

  if ((count ?? 0) >= maxPositions) {
    return {
      allowed: false,
      reason: `Max positions reached (${count}/${maxPositions})`,
      rule: "max_positions",
    };
  }

  return { allowed: true };
}

/**
 * Check per-trade position size cap.
 */
function checkPositionSizeCap(
  tradeValue: number,
  equity: number,
  maxPct: number,
): CircuitBreakerResult {
  const maxValue = equity * maxPct;
  if (tradeValue > maxValue) {
    return {
      allowed: false,
      reason: `Trade value ${tradeValue.toFixed(0)} exceeds cap ${maxValue.toFixed(0)}`,
      rule: "position_size_cap",
    };
  }
  return { allowed: true };
}

// ============================================================================
// POSITION SIZING
// ============================================================================

function calculateQuantity(
  equity: number,
  riskPct: number,
  entryPrice: number,
  stopLossPrice: number,
  contractMultiplier: number,
  isFutures: boolean,
  tsSymbol: string,
): number {
  if (contractMultiplier <= 0) throw new Error("Invalid multiplier");

  const stopDistance = Math.abs(entryPrice - stopLossPrice);
  if (stopDistance === 0) return 1;

  const riskDollars = equity * riskPct;
  const rawQty = riskDollars / (stopDistance * contractMultiplier);

  // Apply max contracts cap for futures (P3 #106)
  const maxQty = isFutures
    ? (MAX_FUTURES_CONTRACTS[tsSymbol] ?? 10)
    : 10000;

  return Math.min(maxQty, Math.max(1, Math.floor(rawQty)));
}

// ============================================================================
// MAIN EXECUTION CYCLE
// ============================================================================

async function executeLiveTradingCycle(
  supabase: any,
  authSupabase: any,
  userId: string,
  symbol: string,
  timeframe: string,
): Promise<ExecutionResult[]> {
  const results: ExecutionResult[] = [];

  // 1. Get fresh broker token (via auth client — RLS enforced)
  let token: BrokerToken;
  try {
    token = await ensureFreshToken(authSupabase, userId);
  } catch (err: any) {
    if (err.status === 401) {
      return [
        {
          success: false,
          error: {
            type: "broker_auth_failed",
            reason: "broker_not_connected",
          },
        },
      ];
    }
    throw err;
  }

  // 2. Normalize symbol
  const { tsSymbol, isFutures, multiplier } = normalizeSymbol(symbol);
  const accountId = isFutures
    ? token.futures_account_id
    : token.account_id;

  if (!accountId) {
    return [
      {
        success: false,
        error: {
          type: "validation_error",
          reason: isFutures
            ? "No futures account configured"
            : "No account configured",
        },
      },
    ];
  }

  // 3. Get account balance
  let balance: AccountBalance;
  try {
    balance = await getAccountBalance(token.access_token, accountId);
  } catch (err: any) {
    return [
      {
        success: false,
        error: { type: "broker_unavailable", statusCode: err.status ?? 500 },
      },
    ];
  }

  // 4. Fetch strategies with live trading enabled for this symbol/timeframe
  const { data: strategies, error: stratError } = await supabase
    .from("strategy_user_strategies")
    .select(
      "id, name, config, is_active, live_trading_enabled, live_risk_pct, live_daily_loss_limit_pct, live_max_positions, live_max_position_pct, live_trading_paused, symbol_id, timeframe, user_id",
    )
    .eq("user_id", userId)
    .eq("symbol_id", symbol)
    .eq("timeframe", timeframe)
    .eq("live_trading_enabled", true);

  if (stratError || !strategies?.length) {
    return [{ success: true, action: "no_action" }];
  }

  // 5. Fetch market data (once — shared across strategies)
  const { data: bars, error: barError } = await supabase
    .from("ohlc_bars_v2")
    .select("ts, open, high, low, close, volume")
    .eq("symbol_id", symbol)
    .eq("timeframe", timeframe)
    .order("ts", { ascending: false })
    .limit(100);

  if (barError || !bars?.length) {
    return [
      {
        success: false,
        error: {
          type: "validation_error",
          reason: barError?.message ?? "No market data",
        },
      },
    ];
  }

  const sortedBars: Bar[] = bars.reverse().map((b: any) => ({
    time: b.ts,
    open: b.open,
    high: b.high,
    low: b.low,
    close: b.close,
    volume: b.volume,
  }));

  // 6. Update current_price on all open live positions for this symbol
  const latestClose = sortedBars[sortedBars.length - 1].close;
  await supabase
    .from("live_trading_positions")
    .update({ current_price: latestClose, updated_at: new Date().toISOString() })
    .eq("user_id", userId)
    .eq("symbol_id", symbol)
    .in("status", ["open", "pending_bracket"]);

  // 7. Check bracket fills for all open positions (batch, P1 #096)
  await checkBracketFills(supabase, token.access_token, accountId, userId);

  // 8. Execute each strategy
  for (const strategy of strategies as LiveStrategy[]) {
    if (strategy.live_trading_paused) {
      // P1 #094: paused strategy surfaces warning, doesn't silently skip
      console.warn(
        `[live-executor] Strategy ${strategy.id} is paused — skipping`,
      );
      results.push({ success: true, action: "no_action" });
      continue;
    }

    const result = await executeStrategy(
      supabase,
      token,
      accountId,
      balance,
      strategy,
      sortedBars,
      tsSymbol,
      isFutures,
      multiplier,
    );
    results.push(result);
  }

  return results;
}

// ============================================================================
// STRATEGY EXECUTION
// ============================================================================

async function executeStrategy(
  supabase: any,
  token: BrokerToken,
  accountId: string,
  balance: AccountBalance,
  strategy: LiveStrategy,
  bars: Bar[],
  tsSymbol: string,
  isFutures: boolean,
  multiplier: number,
): Promise<ExecutionResult> {
  const userId = strategy.user_id;
  const latestPrice = bars[bars.length - 1].close;

  // Check for existing open position
  const { data: openPosition } = await supabase
    .from("live_trading_positions")
    .select("*")
    .eq("strategy_id", strategy.id)
    .eq("symbol_id", strategy.symbol_id)
    .in("status", ["pending_entry", "pending_bracket", "open"])
    .maybeSingle();

  if (openPosition) {
    // Position exists — check for exit signal
    if (openPosition.status === "pending_entry" || openPosition.status === "pending_bracket") {
      // Still waiting on previous cycle — skip
      return { success: true, action: "no_action" };
    }

    const { exit } = evaluateStrategySignals(
      strategy.config.entry_conditions ?? [],
      strategy.config.exit_conditions ?? [],
      bars,
    );

    if (exit) {
      return await closeLivePosition(
        supabase,
        token.access_token,
        accountId,
        openPosition,
        latestPrice,
        "EXIT_SIGNAL",
        tsSymbol,
      );
    }

    return { success: true, action: "no_action" };
  }

  // No open position — check for entry signal
  const { entry } = evaluateStrategySignals(
    strategy.config.entry_conditions ?? [],
    strategy.config.exit_conditions ?? [],
    bars,
  );

  if (!entry) {
    return { success: true, action: "no_action" };
  }

  // Run circuit breakers
  const marketCheck = checkMarketHours();
  if (!marketCheck.allowed) {
    return { success: false, error: { type: "circuit_breaker", rule: "market_hours" } };
  }

  const lossCheck = await checkDailyLossLimit(
    supabase,
    userId,
    balance.equity,
    strategy.live_daily_loss_limit_pct,
  );
  if (!lossCheck.allowed) {
    return { success: false, error: { type: "circuit_breaker", rule: "daily_loss" } };
  }

  const posCheck = await checkMaxPositions(
    supabase,
    userId,
    strategy.live_max_positions,
  );
  if (!posCheck.allowed) {
    return { success: false, error: { type: "circuit_breaker", rule: "max_positions" } };
  }

  // Determine direction (default long, short if config specifies)
  const direction: "long" | "short" =
    (strategy.config.parameters?.direction as string) === "short"
      ? "short"
      : "long";

  const tradeAction = direction === "long" ? "BUY" : "SELLSHORT";
  const closeAction = direction === "long" ? "SELL" : "BUYTOCOVER";

  // Compute SL/TP
  const slPct = (strategy.config.parameters?.stop_loss_pct as number) ?? 2;
  const tpPct = (strategy.config.parameters?.take_profit_pct as number) ?? 5;

  let sl: number, tp: number;
  if (direction === "long") {
    sl = latestPrice * (1 - slPct / 100);
    tp = latestPrice * (1 + tpPct / 100);
  } else {
    sl = latestPrice * (1 + slPct / 100);
    tp = latestPrice * (1 - tpPct / 100);
  }

  // Round SL/TP to tick boundaries for futures
  if (isFutures) {
    sl = roundToTick(sl, tsSymbol);
    tp = roundToTick(tp, tsSymbol);
  }

  // Calculate quantity
  const qty = calculateQuantity(
    balance.equity,
    strategy.live_risk_pct,
    latestPrice,
    sl,
    multiplier,
    isFutures,
    tsSymbol,
  );

  // Position size cap check
  const tradeValue = latestPrice * qty * multiplier;
  const capCheck = checkPositionSizeCap(
    tradeValue,
    balance.equity,
    strategy.live_max_position_pct,
  );
  if (!capCheck.allowed) {
    return { success: false, error: { type: "circuit_breaker", rule: "position_size_cap" } };
  }

  // Place entry market order
  const orderSubmittedAt = new Date().toISOString();
  let entryOrderId: string;
  try {
    entryOrderId = await placeMarketOrder(
      token.access_token,
      accountId,
      tsSymbol,
      qty,
      tradeAction as "BUY" | "SELL" | "BUYTOCOVER" | "SELLSHORT",
    );
  } catch (err: any) {
    return {
      success: false,
      error: { type: "order_rejected", code: sanitizeBrokerError(err.message) },
    };
  }

  // Insert position as pending_entry
  const { data: newPosition, error: insertError } = await supabase
    .from("live_trading_positions")
    .insert({
      user_id: userId,
      strategy_id: strategy.id,
      symbol_id: strategy.symbol_id,
      timeframe: strategy.timeframe,
      entry_price: latestPrice,
      quantity: qty,
      direction,
      stop_loss_price: sl,
      take_profit_price: tp,
      status: "pending_entry",
      broker_order_id: entryOrderId,
      account_id: accountId,
      asset_type: isFutures ? "FUTURE" : "STOCK",
      contract_multiplier: multiplier,
      entry_time: new Date().toISOString(),
      order_submitted_at: orderSubmittedAt,
      execution_venue: "tradestation",
      order_type: "market",
    })
    .select()
    .single();

  if (insertError) {
    // Unique constraint violation = another invocation already entered
    if (insertError.code === "23505") {
      await cancelOrder(token.access_token, entryOrderId);
      return {
        success: false,
        error: { type: "position_locked", reason: "concurrent_close_detected" },
      };
    }
    return {
      success: false,
      error: { type: "database_error", reason: insertError.message },
    };
  }

  // Poll for fill (15s max, P1 #087)
  const fill = await pollOrderFill(token.access_token, accountId, entryOrderId);

  if (fill.filledQuantity === 0) {
    // Not filled — cancel and clean up
    await cancelOrder(token.access_token, entryOrderId);
    await supabase
      .from("live_trading_positions")
      .update({ status: "cancelled", close_reason: "PARTIAL_FILL_CANCELLED" })
      .eq("id", newPosition.id);
    return {
      success: false,
      error: { type: "order_not_filled", orderId: entryOrderId },
    };
  }

  // Handle partial fill
  const filledQty = fill.filledQuantity;
  if (fill.status === "FPR" || fill.status === "Partial Fill") {
    await cancelOrder(token.access_token, entryOrderId);
  }

  // Transition to pending_bracket (P1 #085)
  await supabase
    .from("live_trading_positions")
    .update({
      status: "pending_bracket",
      entry_price: fill.fillPrice,
      broker_fill_price: fill.fillPrice,
      quantity: filledQty,
    })
    .eq("id", newPosition.id);

  // Place bracket orders (SL + TP)
  try {
    const bracket = await placeBracketOrders(
      token.access_token,
      accountId,
      tsSymbol,
      filledQty,
      closeAction as "SELL" | "BUYTOCOVER",
      sl,
      tp,
    );

    // Success — transition to open
    await supabase
      .from("live_trading_positions")
      .update({
        status: "open",
        broker_sl_order_id: bracket.slOrderId,
        broker_tp_order_id: bracket.tpOrderId,
        updated_at: new Date().toISOString(),
      })
      .eq("id", newPosition.id);

    return { success: true, action: "entry_created", positionId: newPosition.id };
  } catch (bracketErr: any) {
    // Bracket failed — IMMEDIATELY close the unprotected position (P1 #085)
    console.error(
      `[live-executor] Bracket failed for position ${newPosition.id}, closing immediately`,
      bracketErr.message,
    );

    const oppositeAction = direction === "long" ? "SELL" : "BUYTOCOVER";
    try {
      await placeMarketOrder(
        token.access_token,
        accountId,
        tsSymbol,
        filledQty,
        oppositeAction as "BUY" | "SELL" | "BUYTOCOVER" | "SELLSHORT",
      );
    } catch {
      console.error(
        `[live-executor] CRITICAL: Failed to close unprotected position ${newPosition.id}`,
      );
    }

    await supabase
      .from("live_trading_positions")
      .update({
        status: "cancelled",
        close_reason: "BRACKET_PLACEMENT_FAILED",
        exit_time: new Date().toISOString(),
        exit_price: fill.fillPrice,
      })
      .eq("id", newPosition.id);

    return {
      success: false,
      error: {
        type: "bracket_placement_failed",
        orderId: entryOrderId,
        reason: sanitizeBrokerError(bracketErr.message),
      },
    };
  }
}

// ============================================================================
// BRACKET FILL MONITORING
// ============================================================================

async function checkBracketFills(
  supabase: any,
  accessToken: string,
  accountId: string,
  userId: string,
): Promise<void> {
  // Fetch all open and pending_bracket positions
  const { data: positions } = await supabase
    .from("live_trading_positions")
    .select("*")
    .eq("user_id", userId)
    .in("status", ["open", "pending_bracket"])
    .not("broker_sl_order_id", "is", null);

  if (!positions?.length) return;

  // Collect all bracket order IDs for batch fetch
  const orderIds: string[] = [];
  for (const pos of positions) {
    if (pos.broker_sl_order_id) orderIds.push(pos.broker_sl_order_id);
    if (pos.broker_tp_order_id) orderIds.push(pos.broker_tp_order_id);
  }

  if (!orderIds.length) return;

  // Batch fetch order statuses
  const statusMap = await getBatchOrderStatus(accessToken, accountId, orderIds);

  for (const pos of positions) {
    const slStatus = pos.broker_sl_order_id
      ? statusMap.get(pos.broker_sl_order_id)
      : undefined;
    const tpStatus = pos.broker_tp_order_id
      ? statusMap.get(pos.broker_tp_order_id)
      : undefined;

    if (
      slStatus &&
      (slStatus.status === "FLL" || slStatus.status === "Filled")
    ) {
      await closeLivePositionFromBracket(
        supabase,
        pos,
        slStatus.fillPrice,
        "SL_HIT",
      );
    } else if (
      tpStatus &&
      (tpStatus.status === "FLL" || tpStatus.status === "Filled")
    ) {
      await closeLivePositionFromBracket(
        supabase,
        pos,
        tpStatus.fillPrice,
        "TP_HIT",
      );
    }
  }
}

/**
 * Close a live position when a bracket leg fills.
 * Uses optimistic locking (WHERE status='open').
 */
async function closeLivePositionFromBracket(
  supabase: any,
  position: LivePosition,
  exitPrice: number,
  closeReason: string,
): Promise<void> {
  const pnl = position.direction === "long"
    ? (exitPrice - position.entry_price) * position.quantity *
      position.contract_multiplier
    : (position.entry_price - exitPrice) * position.quantity *
      position.contract_multiplier;

  const pnlPct = position.direction === "long"
    ? ((exitPrice - position.entry_price) / position.entry_price) * 100
    : ((position.entry_price - exitPrice) / position.entry_price) * 100;

  // Optimistic lock: only close if still open
  const { data, error } = await supabase
    .from("live_trading_positions")
    .update({
      status: "closed",
      exit_price: exitPrice,
      exit_time: new Date().toISOString(),
      pnl,
      close_reason: closeReason,
      updated_at: new Date().toISOString(),
    })
    .eq("id", position.id)
    .eq("status", "open")
    .select()
    .maybeSingle();

  if (!data) {
    console.log(
      `[live-executor] Concurrent close detected for position ${position.id}`,
    );
    return;
  }

  // Insert immutable trade record
  await supabase.from("live_trading_trades").insert({
    user_id: position.user_id,
    strategy_id: position.strategy_id,
    position_id: position.id,
    symbol: position.symbol_id,
    direction: position.direction,
    entry_price: position.entry_price,
    exit_price: exitPrice,
    quantity: position.quantity,
    pnl,
    pnl_pct: pnlPct,
    close_reason: closeReason,
    broker_order_id: position.broker_order_id,
    entry_time: position.entry_time,
    exit_time: new Date().toISOString(),
    contract_multiplier: position.contract_multiplier,
    asset_type: position.asset_type,
    execution_venue: "tradestation",
  });
}

/**
 * Manually close a live position (cancel brackets, place market close).
 */
async function closeLivePosition(
  supabase: any,
  accessToken: string,
  accountId: string,
  position: LivePosition,
  exitPrice: number,
  closeReason: string,
  tsSymbol: string,
): Promise<ExecutionResult> {
  // Cancel existing bracket orders
  if (position.broker_sl_order_id) {
    await cancelOrder(accessToken, position.broker_sl_order_id).catch(() => {});
  }
  if (position.broker_tp_order_id) {
    await cancelOrder(accessToken, position.broker_tp_order_id).catch(() => {});
  }

  // Place close market order
  const closeAction = position.direction === "long" ? "SELL" : "BUYTOCOVER";
  try {
    await placeMarketOrder(
      accessToken,
      accountId,
      tsSymbol,
      position.quantity,
      closeAction as "BUY" | "SELL" | "BUYTOCOVER" | "SELLSHORT",
    );
  } catch (err: any) {
    return {
      success: false,
      error: { type: "order_rejected", code: sanitizeBrokerError(err.message) },
    };
  }

  // Close in DB with optimistic lock
  await closeLivePositionFromBracket(
    supabase,
    position,
    exitPrice,
    closeReason,
  );

  return { success: true, action: "position_closed", positionId: position.id };
}

// ============================================================================
// EDGE FUNCTION HANDLER
// ============================================================================

Deno.serve(async (req) => {
  const origin = req.headers.get("origin");

  if (req.method === "OPTIONS") {
    return handlePreflight(origin);
  }

  // Service-role client for writes
  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
  );

  // Auth client for RLS-protected reads (broker_tokens)
  const authHeader = req.headers.get("Authorization") ?? "";
  const authSupabase = getSupabaseClientWithAuth(authHeader);
  const {
    data: { user },
    error: authError,
  } = await authSupabase.auth.getUser();

  if (authError || !user) {
    return errorResponse("Authentication required", 401, origin);
  }

  const url = new URL(req.url);

  try {
    // ========================================================================
    // GET — Read endpoints
    // ========================================================================
    if (req.method === "GET") {
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
        const { data: positions } = await supabase
          .from("live_trading_positions")
          .select(
            "id, strategy_id, symbol_id, direction, entry_price, current_price, quantity, status, stop_loss_price, take_profit_price, entry_time, broker_order_id, broker_sl_order_id, broker_tp_order_id, asset_type, contract_multiplier, pnl, close_reason, exit_price, exit_time, created_at",
          )
          .eq("user_id", user.id)
          .order("created_at", { ascending: false })
          .range(offset, offset + limit - 1);

        return corsResponse(
          { positions: positions ?? [], total: positions?.length ?? 0, offset, limit },
          200,
          origin,
        );
      }

      if (action === "trades") {
        const { data: trades } = await supabase
          .from("live_trading_trades")
          .select(
            "id, strategy_id, position_id, symbol, direction, entry_price, exit_price, quantity, pnl, pnl_pct, close_reason, broker_order_id, entry_time, exit_time, contract_multiplier, asset_type, created_at",
          )
          .eq("user_id", user.id)
          .order("created_at", { ascending: false })
          .range(offset, offset + limit - 1);

        return corsResponse(
          { trades: trades ?? [], total: trades?.length ?? 0, offset, limit },
          200,
          origin,
        );
      }

      if (action === "summary") {
        const { data: trades } = await supabase
          .from("live_trading_trades")
          .select("pnl, pnl_pct")
          .eq("user_id", user.id);

        const all = trades ?? [];
        const totalTrades = all.length;
        const wins = all.filter((t: any) => (t.pnl ?? 0) > 0).length;
        const totalPnl = all.reduce(
          (s: number, t: any) => s + (t.pnl ?? 0),
          0,
        );

        return corsResponse({
          total_trades: totalTrades,
          win_rate: totalTrades > 0 ? wins / totalTrades : 0,
          total_pnl: totalPnl,
          winning_trades: wins,
          losing_trades: totalTrades - wins,
        }, 200, origin);
      }

      if (action === "broker_status") {
        // Check if user has a connected broker
        const { data: token } = await authSupabase
          .from("broker_tokens")
          .select("id, provider, expires_at, account_id, futures_account_id, revoked_at")
          .eq("user_id", user.id)
          .is("revoked_at", null)
          .maybeSingle();

        return corsResponse({
          connected: !!token,
          provider: token?.provider ?? null,
          has_futures: !!token?.futures_account_id,
          expires_at: token?.expires_at ?? null,
        }, 200, origin);
      }

      return errorResponse(
        "Unknown action. Use: positions, trades, summary, broker_status",
        400,
        origin,
      );
    }

    // ========================================================================
    // POST — Write endpoints (rate-limited)
    // ========================================================================
    if (req.method !== "POST") {
      return errorResponse("Method not allowed", 405, origin);
    }

    const rateLimitOk = await checkRateLimit(supabase, user.id);
    if (!rateLimitOk) {
      return errorResponse(
        "Rate limit exceeded. Max 10 requests per minute.",
        429,
        origin,
      );
    }

    const body = await req.json();
    const { action } = body;

    // --- Manual close position (P1 #095) ---
    if (action === "close_position") {
      const { position_id } = body;
      if (!position_id) {
        return errorResponse("position_id is required", 400, origin);
      }

      const { data: pos } = await supabase
        .from("live_trading_positions")
        .select("*")
        .eq("id", position_id)
        .eq("user_id", user.id)
        .eq("status", "open")
        .single();

      if (!pos) {
        return errorResponse("Position not found or already closed", 404, origin);
      }

      let token: BrokerToken;
      try {
        token = await ensureFreshToken(authSupabase, user.id);
      } catch {
        return errorResponse("Broker not connected", 401, origin);
      }

      const { tsSymbol } = normalizeSymbol(pos.symbol_id);
      const acctId = pos.account_id;
      const latestPrice = pos.current_price ?? pos.entry_price;

      const result = await closeLivePosition(
        supabase,
        token.access_token,
        acctId,
        pos,
        latestPrice,
        "MANUAL_CLOSE",
        tsSymbol,
      );

      return corsResponse(result, 200, origin);
    }

    // --- OAuth callback / token write (P1 #093) ---
    if (action === "save_broker_token") {
      const {
        access_token,
        refresh_token,
        expires_in,
        account_id,
        futures_account_id,
      } = body;

      if (!access_token || !refresh_token || !expires_in || !account_id) {
        return errorResponse(
          "access_token, refresh_token, expires_in, and account_id are required",
          400,
          origin,
        );
      }

      // Validate account_id format
      if (!/^[A-Z0-9]{4,15}$/.test(account_id)) {
        return errorResponse("Invalid account_id format", 400, origin);
      }
      if (
        futures_account_id &&
        !/^[A-Z0-9]{4,15}$/.test(futures_account_id)
      ) {
        return errorResponse("Invalid futures_account_id format", 400, origin);
      }

      const expiresAt = new Date(
        Date.now() + expires_in * 1000,
      ).toISOString();

      const { error: upsertError } = await authSupabase
        .from("broker_tokens")
        .upsert(
          {
            user_id: user.id,
            provider: "tradestation",
            access_token,
            refresh_token,
            expires_at: expiresAt,
            account_id,
            futures_account_id: futures_account_id ?? null,
            revoked_at: null,
            updated_at: new Date().toISOString(),
          },
          { onConflict: "user_id,provider" },
        );

      if (upsertError) {
        return errorResponse("Failed to save broker token", 500, origin);
      }

      return corsResponse({ success: true }, 200, origin);
    }

    // --- Disconnect broker ---
    if (action === "disconnect_broker") {
      await authSupabase
        .from("broker_tokens")
        .update({ revoked_at: new Date().toISOString() })
        .eq("user_id", user.id)
        .eq("provider", "tradestation");

      return corsResponse({ success: true }, 200, origin);
    }

    // --- Execute trading cycle ---
    const { symbol, timeframe } = body;

    if (!symbol || !timeframe) {
      return errorResponse("symbol and timeframe are required", 400, origin);
    }

    // Validate symbol and timeframe against allowlist (P1 #091)
    if (!validateSymbol(symbol)) {
      return errorResponse("Invalid symbol", 400, origin);
    }
    if (!validateTimeframe(timeframe)) {
      return errorResponse("Invalid timeframe", 400, origin);
    }

    const results = await executeLiveTradingCycle(
      supabase,
      authSupabase,
      user.id,
      symbol,
      timeframe,
    );

    const successCount = results.filter((r) => r.success).length;
    return corsResponse({
      success: true,
      execution_time: new Date().toISOString(),
      symbol,
      timeframe,
      strategies_processed: results.length,
      successful: successCount,
      failed: results.length - successCount,
      results,
    }, 200, origin);
  } catch (error: unknown) {
    console.error("[live-trading-executor] Edge function error:", error);
    return corsResponse(
      { success: false, error: "An internal error occurred" },
      500,
      origin,
    );
  }
});
