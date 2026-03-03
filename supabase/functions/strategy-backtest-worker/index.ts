// Strategy Backtest Worker - Processes pending backtest jobs
// All strategies (preset + builder) run natively in the TS backtest engine.
// Presets (supertrend_ai, sma_crossover, buy_and_hold) are translated to condition configs.

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";
import {
  type ConditionGroup,
  normalizeToWorkerFormat,
  normalizeToWorkerGroups,
  type StrategyConfigRaw,
  type WorkerCondition,
} from "../_shared/strategy-translator.ts";
import {
  annualizationFactor,
  type BarData,
  buildIndicatorCache,
  getIndicatorValue,
  isKnownIndicator,
} from "./indicators.ts";

interface BacktestJob {
  id: string;
  user_id: string;
  strategy_id: string | null;
  symbol: string;
  start_date: string;
  end_date: string;
  parameters: Record<string, unknown>;
}

/** Worker-local alias using shared types. */
type Condition = WorkerCondition;

interface PositionSizingConfig {
  type: "percent_of_equity" | "fixed_dollar" | "half_kelly";
  value: number;
}

interface StrategyConfig extends StrategyConfigRaw {
  filters?: WorkerCondition[];
  parameters?: Record<string, unknown>;
  direction?: string;
  positionSizing?: PositionSizingConfig;
  position_sizing?: PositionSizingConfig;
  riskManagement?: {
    stopLoss?: { type: string; value: number };
    takeProfit?: { type: string; value: number };
  };
  risk_management?: {
    stop_loss?: { type: string; value: number };
    take_profit?: { type: string; value: number };
  };
  stop_loss_pct?: number;
  take_profit_pct?: number;
}

/** Normalize config using shared translator. Returns both flat conditions (backward compat) and groups. */
function normalizeConfig(raw: StrategyConfig): {
  entry_conditions: Condition[];
  exit_conditions: Condition[];
  entry_condition_groups: ConditionGroup[];
  exit_condition_groups: ConditionGroup[];
} {
  const flat = normalizeToWorkerFormat(raw);
  const groups = normalizeToWorkerGroups(raw);
  return { ...flat, ...groups };
}

// ─── Job management ───────────────────────────────────────────────────────────

async function claimJob(
  supabase: ReturnType<typeof getSupabaseClient>,
  triggeredJobId?: string,
): Promise<BacktestJob | null> {
  let jobId: string | null = null;

  if (triggeredJobId) {
    const { data, error } = await supabase
      .from("strategy_backtest_jobs")
      .update({ status: "running", started_at: new Date().toISOString() })
      .eq("id", triggeredJobId)
      .eq("status", "pending")
      .select("id")
      .single();

    if (error || !data) {
      console.log(
        `Triggered job ${triggeredJobId} not claimable:`,
        error?.message,
      );
      return null;
    }
    jobId = data.id;
  } else {
    const { data, error } = await supabase.rpc("claim_pending_backtest_job");
    if (error || !data) {
      console.log("No pending jobs or error:", error?.message);
      return null;
    }
    jobId = data;
  }

  const { data: job } = await supabase
    .from("strategy_backtest_jobs")
    .select("*")
    .eq("id", jobId)
    .single();

  return job as BacktestJob;
}

async function updateHeartbeat(
  supabase: ReturnType<typeof getSupabaseClient>,
  jobId: string,
): Promise<void> {
  await supabase
    .from("strategy_backtest_jobs")
    .update({ heartbeat_at: new Date().toISOString() })
    .eq("id", jobId);
}

async function isJobCancelled(
  supabase: ReturnType<typeof getSupabaseClient>,
  jobId: string,
): Promise<boolean> {
  const { data } = await supabase
    .from("strategy_backtest_jobs")
    .select("status")
    .eq("id", jobId)
    .single();
  return data?.status === "cancelled";
}

// ─── Market data ──────────────────────────────────────────────────────────────

async function fetchMarketData(
  supabase: ReturnType<typeof getSupabaseClient>,
  symbol: string,
  startDate: string,
  endDate: string,
  timeframe: string,
): Promise<{
  dates: string[];
  opens: number[];
  highs: number[];
  lows: number[];
  closes: number[];
  volumes: number[];
}> {
  const start = new Date(startDate).toISOString();
  const end = new Date(endDate).toISOString();
  const tf = timeframe && timeframe !== "" ? timeframe : "d1";

  const { data: symbolRow } = await supabase
    .from("symbols")
    .select("id")
    .eq("ticker", symbol.toUpperCase())
    .single();

  if (!symbolRow) {
    throw new Error(`Symbol ${symbol} not found in database`);
  }

  const { data: bars, error: barsError } = await supabase
    .from("ohlc_bars_v2")
    .select("ts, open, high, low, close, volume")
    .eq("symbol_id", symbolRow.id)
    .eq("timeframe", tf)
    .gte("ts", start)
    .lte("ts", end)
    .order("ts", { ascending: true });

  if (barsError || !bars || bars.length === 0) {
    console.warn(
      `[BacktestWorker] No data in ohlc_bars_v2 for ${symbol} ${tf}, range ${start} to ${end}`,
    );
    throw new Error(
      `Insufficient data for ${symbol} ${tf} in range ${start} to ${end}`,
    );
  }

  const isIntraday = ["m1", "m5", "m15", "m30", "h1", "h4"].includes(tf);
  const dates = bars.map((b) =>
    isIntraday
      ? new Date(b.ts).toISOString()
      : new Date(b.ts).toISOString().split("T")[0]
  );

  console.log(
    `[BacktestWorker] Fetched ${bars.length} bars for ${symbol} from ohlc_bars_v2`,
  );

  return {
    dates,
    opens: bars.map((b) => b.open as number),
    highs: bars.map((b) => b.high as number),
    lows: bars.map((b) => b.low as number),
    closes: bars.map((b) => b.close as number),
    volumes: bars.map((b) => b.volume as number),
  };
}

// ─── Config extraction helpers ────────────────────────────────────────────────

function extractInitialCapital(
  params: Record<string, unknown>,
  _config: StrategyConfig,
): number {
  return (
    (params.initialCapital as number) ||
    (params.initial_capital as number) ||
    10000
  );
}

function extractStopLoss(
  params: Record<string, unknown>,
  config: StrategyConfig,
): number {
  // Prefer inline strategy config (user's actual setting), fall back to job params
  const fromConfig = config.riskManagement?.stopLoss?.value ??
    config.risk_management?.stop_loss?.value ??
    config.stop_loss_pct;
  if (fromConfig !== undefined && fromConfig !== null) {
    return Number(fromConfig) / 100;
  }
  return ((params.stop_loss_pct as number) || 2) / 100;
}

function extractTakeProfit(
  params: Record<string, unknown>,
  config: StrategyConfig,
): number {
  const fromConfig = config.riskManagement?.takeProfit?.value ??
    config.risk_management?.take_profit?.value ??
    config.take_profit_pct;
  if (fromConfig !== undefined && fromConfig !== null) {
    return Number(fromConfig) / 100;
  }
  return ((params.take_profit_pct as number) || 4) / 100;
}

function extractPositionSizing(
  _params: Record<string, unknown>,
  config: StrategyConfig,
): PositionSizingConfig {
  const ps = config.positionSizing ?? config.position_sizing;
  if (ps?.type) return { type: ps.type, value: Number(ps.value) || 2 };
  return { type: "percent_of_equity", value: 2 };
}

function extractDirection(config: StrategyConfig): string {
  return config.direction ?? "long_only";
}

// ─── Position sizing ──────────────────────────────────────────────────────────

function computeShareCount(
  equity: number,
  execPrice: number,
  sizing: PositionSizingConfig,
  completedTrades: Record<string, unknown>[],
): number {
  if (execPrice <= 0) return 0;

  let notional: number;

  switch (sizing.type) {
    case "fixed_dollar":
      notional = sizing.value;
      break;

    case "half_kelly": {
      // Require at least 10 completed trades for Kelly to activate
      if (completedTrades.length >= 10) {
        const wins = completedTrades.filter((t) => (t.pnl as number) > 0);
        const losses = completedTrades.filter((t) => (t.pnl as number) <= 0);
        const winRate = wins.length / completedTrades.length;
        const avgWin = wins.length
          ? wins.reduce((s, t) => s + (t.pnl as number), 0) / wins.length
          : 0;
        const avgLoss = losses.length
          ? Math.abs(
            losses.reduce((s, t) => s + (t.pnl as number), 0) / losses.length,
          )
          : 1;
        const ratio = avgLoss > 0 ? avgWin / avgLoss : 1;
        const kelly = winRate - (1 - winRate) / ratio;
        const halfKelly = Math.max(0, Math.min(0.5, kelly * 0.5));
        notional = equity * halfKelly;
      } else {
        // Fall back to 2% until enough trades
        notional = equity * 0.02;
      }
      break;
    }

    case "percent_of_equity":
    default:
      notional = equity * (sizing.value / 100);
      break;
  }

  return Math.max(1, Math.floor(notional / execPrice));
}

// ─── Core backtest engine ─────────────────────────────────────────────────────

async function runBacktest(
  supabase: ReturnType<typeof getSupabaseClient>,
  job: BacktestJob,
  config: StrategyConfig,
): Promise<{
  metrics: Record<string, unknown>;
  trades: Record<string, unknown>[];
  equity_curve: Record<string, unknown>[];
}> {
  const params = job.parameters as Record<string, unknown>;
  const initialCapital = extractInitialCapital(params, config);
  const stopLoss = extractStopLoss(params, config);
  const takeProfit = extractTakeProfit(params, config);
  const timeframe = (params.timeframe as string) || "d1";
  const direction = extractDirection(config);
  const positionSizing = extractPositionSizing(params, config);

  const { dates, opens, highs, lows, closes, volumes } = await fetchMarketData(
    supabase,
    job.symbol,
    job.start_date,
    job.end_date,
    timeframe,
  );

  if (closes.length === 0) {
    return {
      metrics: {
        total_trades: 0,
        winning_trades: 0,
        losing_trades: 0,
        win_rate: 0,
        total_return_pct: 0,
        final_value: initialCapital,
        max_drawdown_pct: 0,
        sharpe_ratio: 0,
        avg_win: 0,
        avg_loss: 0,
        profit_factor: 0,
      },
      trades: [],
      equity_curve: [],
    };
  }

  const bars: BarData = { closes, highs, lows, volumes, opens };

  // Get grouped conditions (OR logic: each group is AND'd internally, groups are OR'd)
  const entryGroups: ConditionGroup[] = config.entry_condition_groups ||
    (config.entry_conditions?.length
      ? [{ conditions: config.entry_conditions }]
      : []);
  const exitGroups: ConditionGroup[] = config.exit_condition_groups ||
    (config.exit_conditions?.length
      ? [{ conditions: config.exit_conditions }]
      : []);

  // Flatten all conditions from all groups for cache building
  const allConditions = [
    ...entryGroups.flatMap((g) => g.conditions),
    ...exitGroups.flatMap((g) => g.conditions),
  ];
  const cache = buildIndicatorCache(allConditions, bars);

  console.log(
    `[BacktestWorker] Entry groups (${entryGroups.length}):`,
    JSON.stringify(
      entryGroups.map((g) => ({
        conditions: g.conditions.map((c) => ({
          name: c.name,
          op: c.operator,
          val: c.value,
          params: c.params,
        })),
      })),
    ),
  );
  console.log(
    `[BacktestWorker] Exit groups (${exitGroups.length}):`,
    JSON.stringify(
      exitGroups.map((g) => ({
        conditions: g.conditions.map((c) => ({
          name: c.name,
          op: c.operator,
          val: c.value,
        })),
      })),
    ),
  );
  console.log(
    `[BacktestWorker] direction=${direction}, SL=${
      (stopLoss * 100).toFixed(1)
    }%, TP=${
      (takeProfit * 100).toFixed(1)
    }%, sizing=${positionSizing.type}(${positionSizing.value})`,
  );

  const warnedIndicators = new Set<string>();

  /**
   * Evaluate all conditions at bar i (AND logic within a single group).
   * Crossover operators compare bar[i] vs bar[i-1].
   * Unknown indicators are skipped with a warning (condition passes).
   */
  function evaluateConditions(
    conditions: Condition[] | undefined,
    i: number,
  ): boolean {
    if (!conditions || conditions.length === 0) return true;

    for (const cond of conditions) {
      if (cond.type !== "indicator") continue;

      const name = cond.name;
      const op = cond.operator ?? "above";
      const val = Number(cond.value ?? 0);
      const condParams = (cond.params as Record<string, unknown>) ?? {};

      if (!isKnownIndicator(name)) {
        if (!warnedIndicators.has(name)) {
          console.warn(
            `[BacktestWorker] Unknown indicator "${name}" — condition skipped`,
          );
          warnedIndicators.add(name);
        }
        continue; // treat as passing (existing behavior)
      }

      const cur = getIndicatorValue(name, condParams, i, cache);
      if (cur === null) continue; // not enough warmup data — skip

      // Crossover operators need the previous bar's value
      if (op === "cross_up") {
        if (i === 0) return false;
        const prev = getIndicatorValue(name, condParams, i - 1, cache);
        if (prev === null) return false;
        if (!(cur > val && prev <= val)) return false;
        continue;
      }
      if (op === "cross_down") {
        if (i === 0) return false;
        const prev = getIndicatorValue(name, condParams, i - 1, cache);
        if (prev === null) return false;
        if (!(cur < val && prev >= val)) return false;
        continue;
      }

      // Threshold operators
      if (op === "below" || op === "<") {
        if (!(cur < val)) return false;
      } else if (op === "below_equal" || op === "<=") {
        if (!(cur <= val)) return false;
      } else if (op === "above" || op === ">") {
        if (!(cur > val)) return false;
      } else if (op === "above_equal" || op === ">=") {
        if (!(cur >= val)) return false;
      } else if (op === "equals" || op === "==") {
        if (Math.abs(cur - val) >= 0.0001) return false;
      } else if (op === "not_equals" || op === "!=") {
        if (Math.abs(cur - val) < 0.0001) return false;
      }
    }
    return true;
  }

  /**
   * Evaluate condition groups at bar i (OR logic across groups).
   * Returns true if ANY group fully passes (all conditions within that group are met).
   * An empty groups array returns true (no conditions = always entry/exit signal).
   */
  function evaluateConditionGroups(
    groups: ConditionGroup[],
    i: number,
  ): boolean {
    if (!groups || groups.length === 0) return true;
    return groups.some((group) => evaluateConditions(group.conditions, i));
  }

  // ─── Position loop ──────────────────────────────────────────────────────────

  const slippagePct = 0.0005; // 5 bps per side (realistic for liquid equities)
  const isShortOnly = direction === "short_only";

  let cash = initialCapital;
  let shares = 0; // positive = long, negative = short (signed-shares model)
  let entryPrice = 0;
  let entryBar = 0;

  const trades: Record<string, unknown>[] = [];
  const equityCurve: { date: string; value: number }[] = [];

  for (let i = 30; i < closes.length; i++) {
    if (shares === 0) {
      // ── Entry logic ──
      const entrySignal = evaluateConditionGroups(entryGroups, i);

      if (entrySignal) {
        const posDir = isShortOnly ? -1 : 1; // +1 long, -1 short
        // Slippage: pay more to buy, receive less to short
        const execPrice = closes[i] * (1 + posDir * slippagePct);
        const shareCount = computeShareCount(
          cash,
          execPrice,
          positionSizing,
          trades,
        );
        if (shareCount > 0) {
          shares = posDir * shareCount; // signed
          // Entry cash: cash -= shares * execPrice (works for both directions)
          cash -= shares * execPrice;
          entryPrice = execPrice;
          entryBar = i;
        }
      }
    } else {
      // ── Exit logic ──
      const posDir = shares > 0 ? 1 : -1;
      const absShares = Math.abs(shares);

      // Intrabar SL/TP check using high/low prices
      const highRet = (highs[i] - entryPrice) / entryPrice;
      const lowRet = (lows[i] - entryPrice) / entryPrice;

      // SL triggers when price moves against position by stopLoss
      const hitSL = posDir === 1 ? lowRet <= -stopLoss : highRet >= stopLoss;
      // TP triggers when price moves with position by takeProfit
      const hitTP = posDir === 1
        ? highRet >= takeProfit
        : lowRet <= -takeProfit;

      const exitByCondition = evaluateConditionGroups(exitGroups, i);

      if (exitByCondition || hitSL || hitTP) {
        let rawExitPrice: number;
        let closeReason: string;

        if (hitSL) {
          // Exit at the stop level
          rawExitPrice = entryPrice * (1 - posDir * stopLoss);
          closeReason = "stop_loss";
        } else if (hitTP) {
          rawExitPrice = entryPrice * (1 + posDir * takeProfit);
          closeReason = "take_profit";
        } else {
          rawExitPrice = closes[i];
          closeReason = "exit_condition";
        }

        // Slippage on exit: receive less when selling, pay more when covering
        const exitPrice = rawExitPrice * (1 - posDir * slippagePct);

        // Exit: cash += shares * exitPrice (unified for long + short)
        cash += shares * exitPrice;
        const pnl = shares * (exitPrice - entryPrice);
        const pnlPct = posDir * (exitPrice - entryPrice) / entryPrice;

        trades.push({
          entry_date: dates[entryBar],
          exit_date: dates[i],
          entry_price: entryPrice,
          exit_price: exitPrice,
          quantity: absShares,
          direction: posDir === 1 ? "long" : "short",
          close_reason: closeReason,
          pnl,
          pnl_pct: pnlPct * 100,
        });

        shares = 0;
      }
    }

    // Equity = cash + unrealized position value (signed-shares: works for both)
    equityCurve.push({ date: dates[i], value: cash + shares * closes[i] });
  }

  // ─── Metrics ────────────────────────────────────────────────────────────────

  const lastClose = closes.length > 0 ? closes[closes.length - 1] : 0;
  const finalValue = cash + shares * lastClose;

  const winning = trades.filter((t) => (t.pnl as number) > 0);
  const losing = trades.filter((t) => (t.pnl as number) <= 0);
  const totalReturn = ((finalValue - initialCapital) / initialCapital) * 100;

  let peak = initialCapital;
  let maxDrawdown = 0;
  for (const eq of equityCurve) {
    if (eq.value > peak) peak = eq.value;
    const dd = peak > 0 ? (peak - eq.value) / peak : 0;
    if (dd > maxDrawdown) maxDrawdown = dd;
  }

  const avgWin = winning.length
    ? winning.reduce((s, t) => s + (t.pnl as number), 0) / winning.length
    : 0;
  const avgLoss = losing.length
    ? Math.abs(
      losing.reduce((s, t) => s + (t.pnl as number), 0) / losing.length,
    )
    : 0;

  const totalGrossProfit = winning.reduce(
    (s, t) => s + (t.pnl as number),
    0,
  );
  const totalGrossLoss = Math.abs(
    losing.reduce((s, t) => s + (t.pnl as number), 0),
  );
  const profitFactor = totalGrossLoss > 0
    ? totalGrossProfit / totalGrossLoss
    : 0;

  // Sharpe ratio — timeframe-aware annualization
  let sharpeRatio = 0;
  if (equityCurve.length > 2) {
    const returns: number[] = [];
    for (let i = 1; i < equityCurve.length; i++) {
      const prev = equityCurve[i - 1].value;
      if (prev > 0) returns.push((equityCurve[i].value - prev) / prev);
    }
    if (returns.length > 1) {
      const meanReturn = returns.reduce((a, b) => a + b, 0) / returns.length;
      const variance = returns.reduce((a, r) => a + (r - meanReturn) ** 2, 0) /
        (returns.length - 1);
      const stdDev = Math.sqrt(variance);
      if (stdDev > 0) {
        sharpeRatio = (meanReturn / stdDev) *
          Math.sqrt(annualizationFactor(timeframe));
      }
    }
  }

  const avgTrade = trades.length > 0
    ? ((finalValue - initialCapital) / initialCapital / trades.length) * 100
    : null;
  const years =
    (new Date(job.end_date).getTime() - new Date(job.start_date).getTime()) /
    (365.25 * 24 * 60 * 60 * 1000);
  const cagr = years > 0 && initialCapital > 0
    ? (Math.pow(finalValue / initialCapital, 1 / years) - 1) * 100
    : null;

  return {
    metrics: {
      total_trades: trades.length,
      winning_trades: winning.length,
      losing_trades: losing.length,
      win_rate: trades.length ? (winning.length / trades.length) * 100 : 0,
      total_return_pct: totalReturn,
      final_value: finalValue,
      max_drawdown_pct: maxDrawdown * 100,
      sharpe_ratio: sharpeRatio,
      avg_win: avgWin,
      avg_loss: avgLoss,
      profit_factor: profitFactor,
      average_trade: avgTrade,
      cagr,
    },
    trades,
    equity_curve: equityCurve,
  };
}

// ─── Preset strategy configs ──────────────────────────────────────────────────

function getPresetConfig(presetName: string): StrategyConfig {
  switch (presetName) {
    case "supertrend_ai":
      return {
        entry_conditions: [
          {
            type: "indicator",
            name: "supertrend_trend",
            operator: "above",
            value: 0,
          },
        ],
        exit_conditions: [
          {
            type: "indicator",
            name: "supertrend_trend",
            operator: "below",
            value: 1,
          },
        ],
      };
    case "sma_crossover":
      return {
        entry_conditions: [
          {
            type: "indicator",
            name: "price_above_sma",
            operator: "above",
            value: 0,
          },
        ],
        exit_conditions: [
          {
            type: "indicator",
            name: "price_above_sma",
            operator: "below",
            value: 1,
          },
        ],
      };
    case "buy_and_hold":
      return {
        entry_conditions: [],
        exit_conditions: [
          { type: "indicator", name: "rsi", operator: "below", value: -999 },
        ],
      };
    default:
      throw new Error(`Unknown preset strategy: ${presetName}`);
  }
}

// ─── Request handler ──────────────────────────────────────────────────────────

serve(async (req: Request): Promise<Response> => {
  if (req.method === "OPTIONS") {
    return new Response(null, {
      status: 204,
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, X-SB-Gateway-Key",
      },
    });
  }

  const gatewayKey = Deno.env.get("SB_GATEWAY_KEY");
  if (!gatewayKey) {
    console.error("[strategy-backtest-worker] SB_GATEWAY_KEY not configured");
    return new Response("Server misconfiguration", { status: 500 });
  }
  const callerKey = req.headers.get("X-SB-Gateway-Key");
  if (callerKey !== gatewayKey) {
    return new Response("Unauthorized", { status: 401 });
  }

  const supabase = getSupabaseClient();

  let triggeredJobId: string | undefined;
  try {
    const body = await req.json();
    triggeredJobId = body?.triggered_job_id;
  } catch {
    // No body or invalid JSON — fall back to claiming oldest pending
  }

  console.log(
    "Backtest worker started",
    triggeredJobId ? `for job ${triggeredJobId}` : "(no triggered_job_id)",
  );

  try {
    {
      const job = await claimJob(supabase, triggeredJobId);

      if (!job) {
        console.log("No job to process");
        return new Response(
          JSON.stringify({ success: true, message: "No job to process" }),
          { headers: { "Content-Type": "application/json" } },
        );
      }

      console.log(`Processing job ${job.id} for ${job.symbol}`);

      try {
        if (await isJobCancelled(supabase, job.id)) {
          console.log(`Job ${job.id} was cancelled before processing`);
          return new Response(
            JSON.stringify({ success: true, message: "Job cancelled" }),
            { headers: { "Content-Type": "application/json" } },
          );
        }

        let result: {
          metrics: Record<string, unknown>;
          trades: Record<string, unknown>[];
          equity_curve: Record<string, unknown>[];
        };

        const inlineConfig = job.parameters?.strategy_config as
          | StrategyConfig
          | undefined;

        if (inlineConfig) {
          console.log(`Job ${job.id}: using inline strategy_config`);
          const {
            entry_conditions,
            exit_conditions,
            entry_condition_groups,
            exit_condition_groups,
          } = normalizeConfig(inlineConfig);
          const config: StrategyConfig = {
            ...inlineConfig,
            entry_conditions,
            exit_conditions,
            entry_condition_groups,
            exit_condition_groups,
          };

          await updateHeartbeat(supabase, job.id);
          if (await isJobCancelled(supabase, job.id)) {
            console.log(`Job ${job.id} cancelled before backtest computation`);
            return new Response(
              JSON.stringify({ success: true, message: "Job cancelled" }),
              { headers: { "Content-Type": "application/json" } },
            );
          }

          result = await runBacktest(supabase, job, config);
          await updateHeartbeat(supabase, job.id);
        } else if (!job.strategy_id && job.parameters?.strategy) {
          const presetName = job.parameters.strategy as string;
          console.log(
            `Job ${job.id}: running preset strategy "${presetName}" natively`,
          );
          const presetConfig = getPresetConfig(presetName);

          if (presetName === "buy_and_hold") {
            job.parameters.stop_loss_pct = 99999;
            job.parameters.take_profit_pct = 99999;
          }

          await updateHeartbeat(supabase, job.id);
          if (await isJobCancelled(supabase, job.id)) {
            console.log(`Job ${job.id} cancelled before backtest computation`);
            return new Response(
              JSON.stringify({ success: true, message: "Job cancelled" }),
              { headers: { "Content-Type": "application/json" } },
            );
          }

          result = await runBacktest(supabase, job, presetConfig);
          await updateHeartbeat(supabase, job.id);
        } else if (job.strategy_id) {
          console.log(
            `Job ${job.id}: reading config from DB for strategy ${job.strategy_id}`,
          );
          const { data: strategy } = await supabase
            .from("strategy_user_strategies")
            .select("config")
            .eq("id", job.strategy_id)
            .single();

          const rawConfig = (strategy?.config || {}) as StrategyConfig;
          const {
            entry_conditions,
            exit_conditions,
            entry_condition_groups,
            exit_condition_groups,
          } = normalizeConfig(rawConfig);
          const config: StrategyConfig = {
            ...rawConfig,
            entry_conditions,
            exit_conditions,
            entry_condition_groups,
            exit_condition_groups,
          };

          await updateHeartbeat(supabase, job.id);
          if (await isJobCancelled(supabase, job.id)) {
            console.log(`Job ${job.id} cancelled before backtest computation`);
            return new Response(
              JSON.stringify({ success: true, message: "Job cancelled" }),
              { headers: { "Content-Type": "application/json" } },
            );
          }

          result = await runBacktest(supabase, job, config);
          await updateHeartbeat(supabase, job.id);
        } else {
          throw new Error(
            "Job must have strategy_config, strategy_id, or parameters.strategy",
          );
        }

        if (await isJobCancelled(supabase, job.id)) {
          console.log(`Job ${job.id} cancelled before saving results`);
          return new Response(
            JSON.stringify({ success: true, message: "Job cancelled" }),
            { headers: { "Content-Type": "application/json" } },
          );
        }

        const { data: resultRecord, error: resultError } = await supabase
          .from("strategy_backtest_results")
          .insert({
            job_id: job.id,
            metrics: result.metrics,
            trades: result.trades,
            equity_curve: result.equity_curve,
          })
          .select()
          .single();

        if (resultError) throw resultError;

        await supabase
          .from("strategy_backtest_jobs")
          .update({
            status: "completed",
            result_id: resultRecord.id,
            completed_at: new Date().toISOString(),
          })
          .eq("id", job.id);

        console.log(
          `Job ${job.id} completed with ${
            (result.metrics.total_trades as number) ?? 0
          } trades`,
        );
      } catch (err) {
        console.error(`Job ${job.id} failed:`, err);

        await supabase
          .from("strategy_backtest_jobs")
          .update({
            status: "failed",
            error_message: err instanceof Error ? err.message : "Unknown error",
            completed_at: new Date().toISOString(),
          })
          .eq("id", job.id);
      }
    }

    return new Response(JSON.stringify({ success: true }), {
      headers: { "Content-Type": "application/json" },
    });
  } catch (err) {
    console.error("Worker error:", err);
    return new Response(
      JSON.stringify({
        error: err instanceof Error ? err.message : "Worker failed",
      }),
      {
        status: 500,
        headers: { "Content-Type": "application/json" },
      },
    );
  }
});
