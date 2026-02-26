// Strategy Backtest Worker - Processes pending backtest jobs
// Preset strategies (supertrend_ai, sma_crossover, buy_and_hold): calls FastAPI
// Builder strategies (strategy_id): uses local TS backtest with strategy_user_strategies config

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";
import { callFastApi } from "../_shared/fastapi-client.ts";
import { YFinanceClient } from "../_shared/providers/yfinance-client.ts";

interface BacktestJob {
  id: string;
  user_id: string;
  strategy_id: string | null;
  symbol: string;
  start_date: string;
  end_date: string;
  parameters: Record<string, unknown>;
}

interface StrategyConfig {
  entry_conditions?: Condition[];
  exit_conditions?: Condition[];
  entryConditions?: FrontendCondition[];
  exitConditions?: FrontendCondition[];
  filters?: Condition[];
  parameters?: Record<string, unknown>;
}

interface Condition {
  type: string;
  name: string;
  operator?: string;
  value?: number;
  params?: Record<string, unknown>;
}

/** Frontend builder format (camelCase, type = indicator id) */
interface FrontendCondition {
  type: string;
  operator?: string;
  value?: number;
  params?: Record<string, unknown>;
}

function normalizeConfig(
  raw: StrategyConfig,
): { entry_conditions: Condition[]; exit_conditions: Condition[] } {
  const entry = raw.entry_conditions ?? [];
  const exit = raw.exit_conditions ?? [];
  if (entry.length > 0 || exit.length > 0) {
    return { entry_conditions: entry, exit_conditions: exit };
  }
  const mapOne = (c: FrontendCondition): Condition => ({
    type: "indicator",
    name: c.type,
    operator: c.operator === ">" || c.operator === ">="
      ? "above"
      : c.operator === "=="
      ? "equals"
      : "below",
    value: c.value ?? 0,
  });
  return {
    entry_conditions: (raw.entryConditions ?? []).map(mapOne),
    exit_conditions: (raw.exitConditions ?? []).map(mapOne),
  };
}

async function claimJob(
  supabase: ReturnType<typeof getSupabaseClient>,
): Promise<BacktestJob | null> {
  const { data, error } = await supabase.rpc("claim_pending_backtest_job");

  if (error || !data) {
    console.log("No pending jobs or error:", error?.message);
    return null;
  }

  const { data: job } = await supabase
    .from("strategy_backtest_jobs")
    .select("*")
    .eq("id", data)
    .single();

  return job as BacktestJob;
}

const yfinance = new YFinanceClient();

async function fetchMarketData(
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
  const start = Math.floor(new Date(startDate).getTime() / 1000);
  const end = Math.floor(new Date(endDate).getTime() / 1000);
  const tf = timeframe && timeframe !== "" ? timeframe : "d1";

  try {
    const bars = await yfinance.getHistoricalBars({
      symbol: symbol.toUpperCase(),
      timeframe: tf,
      start,
      end,
    });

    if (!bars || bars.length === 0) {
      console.warn(
        `[BacktestWorker] No Yahoo Finance data for ${symbol} ${tf}; using mock fallback`,
      );
      return generateMockData(startDate, endDate);
    }

    const isIntraday = ["m1", "m5", "m15", "m30", "h1", "h4"].includes(tf);
    const dates = bars.map((b) =>
      isIntraday
        ? new Date(b.timestamp * 1000).toISOString()
        : new Date(b.timestamp * 1000).toISOString().split("T")[0]
    );
    const opens = bars.map((b) => b.open);
    const highs = bars.map((b) => b.high);
    const lows = bars.map((b) => b.low);
    const closes = bars.map((b) => b.close);
    const volumes = bars.map((b) => b.volume);

    console.log(
      `[BacktestWorker] Fetched ${bars.length} bars for ${symbol} from Yahoo Finance`,
    );
    return { dates, opens, highs, lows, closes, volumes };
  } catch (e) {
    console.error(
      `[BacktestWorker] Yahoo Finance fetch failed for ${symbol}:`,
      e,
    );
    return generateMockData(startDate, endDate);
  }
}

function generateMockData(startDate: string, endDate: string) {
  const dates: string[] = [];
  const closes: number[] = [];
  const highs: number[] = [];
  const lows: number[] = [];
  const volumes: number[] = [];

  let price = 100;
  const currentDate = new Date(startDate);
  const end = new Date(endDate);

  while (currentDate <= end) {
    if (currentDate.getDay() !== 0 && currentDate.getDay() !== 6) {
      dates.push(currentDate.toISOString().split("T")[0]);
      const change = (Math.random() - 0.48) * 0.03;
      price = price * (1 + change);
      closes.push(price);
      highs.push(price * 1.02);
      lows.push(price * 0.98);
      volumes.push(Math.floor(5000000 + Math.random() * 10000000));
    }
    currentDate.setDate(currentDate.getDate() + 1);
  }

  return { dates, opens: closes, highs, lows, closes, volumes };
}

function calculateIndicators(
  closes: number[],
  highs: number[],
  lows: number[],
  volumes: number[],
) {
  const sma20: (number | null)[] = [];
  const ema12: (number | null)[] = [];
  const ema26: (number | null)[] = [];
  const rsi: number[] = [];
  const macd: (number | null)[] = [];
  const macdSignal: (number | null)[] = [];
  const atr: (number | null)[] = [];
  const stochasticK: (number | null)[] = [];
  const adx: (number | null)[] = [];

  for (let i = 0; i < closes.length; i++) {
    // SMA 20
    if (i < 19) {
      sma20.push(null);
    } else {
      let sum = 0;
      for (let j = i - 19; j <= i; j++) sum += closes[j];
      sma20.push(sum / 20);
    }

    // EMA 12
    if (i === 0) {
      ema12.push(closes[0]);
    } else {
      const prev = ema12[i - 1] ?? closes[0];
      ema12.push((closes[i] - prev) * (2 / 13) + prev);
    }

    // EMA 26
    if (i === 0) {
      ema26.push(closes[0]);
    } else {
      const prev = ema26[i - 1] ?? closes[0];
      ema26.push((closes[i] - prev) * (2 / 27) + prev);
    }

    // MACD
    const ema12Val = ema12[i];
    const ema26Val = ema26[i];
    if (ema12Val !== null && ema26Val !== null) {
      macd.push(ema12Val - ema26Val);
    } else {
      macd.push(null);
    }

    // MACD Signal (9-period EMA of MACD)
    if (i === 0 || macd[i] === null) {
      macdSignal.push(null);
    } else {
      const prev = macdSignal[i - 1] ?? macd[i];
      macdSignal.push((macd[i]! - prev) * (2 / 10) + prev);
    }

    // RSI 14
    if (i < 14) {
      rsi.push(50);
    } else {
      let gains = 0, losses = 0;
      for (let j = i - 13; j <= i; j++) {
        const diff = closes[j] - closes[j - 1];
        if (diff > 0) gains += diff;
        else losses -= diff;
      }
      const avgGain = gains / 14;
      const avgLoss = losses / 14;
      const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
      rsi.push(100 - (100 / (1 + rs)));
    }

    // ATR 14
    if (i < 14) {
      atr.push(null);
    } else {
      let trSum = 0;
      for (let j = i - 13; j <= i; j++) {
        const tr = Math.max(
          highs[j] - lows[j],
          Math.abs(highs[j] - closes[j - 1]),
          Math.abs(lows[j] - closes[j - 1]),
        );
        trSum += tr;
      }
      atr.push(trSum / 14);
    }

    // Stochastic
    if (i < 13) {
      stochasticK.push(null);
    } else {
      const low14 = Math.min(...lows.slice(i - 13, i + 1));
      const high14 = Math.max(...highs.slice(i - 13, i + 1));
      stochasticK.push(100 * (closes[i] - low14) / (high14 - low14));
    }

    // ADX (simplified)
    adx.push(25);
  }

  return { sma20, ema12, ema26, macd, macdSignal, rsi, atr, stochasticK, adx };
}

/** SuperTrend (TradingView-style): period=7, multiplier=2.0 to align with ML pipeline. */
function calculateSuperTrend(
  highs: number[],
  lows: number[],
  closes: number[],
  period: number = 7,
  multiplier: number = 2.0,
): { trend: number[]; signal: number[] } {
  const n = closes.length;
  const trend: number[] = [];
  const signal: number[] = [];

  if (n === 0) return { trend, signal };

  // True Range
  const tr: number[] = [];
  for (let i = 0; i < n; i++) {
    if (i === 0) {
      tr.push(highs[0] - lows[0]);
    } else {
      tr.push(
        Math.max(
          highs[i] - lows[i],
          Math.abs(highs[i] - closes[i - 1]),
          Math.abs(lows[i] - closes[i - 1]),
        ),
      );
    }
  }

  // ATR with Wilder smoothing (EMA alpha = 1/period): ATR[0]=TR[0], ATR[i] = (1/period)*TR[i] + (1-1/period)*ATR[i-1]
  const atr: number[] = [];
  const alpha = 1 / period;
  for (let i = 0; i < n; i++) {
    if (i === 0) atr.push(tr[0]);
    else atr.push(alpha * tr[i] + (1 - alpha) * atr[i - 1]!);
  }

  // Basic bands: HL2 +/- (multiplier * ATR)
  const hl2 = highs.map((h, i) => (h + lows[i]) / 2);
  const basicUpper = hl2.map((v, i) => v + multiplier * (atr[i] ?? 0));
  const basicLower = hl2.map((v, i) => v - multiplier * (atr[i] ?? 0));

  // Final bands and SuperTrend (TradingView iterative logic)
  const finalUpper: number[] = [];
  const finalLower: number[] = [];
  const supertrend: number[] = [];

  finalUpper[0] = basicUpper[0];
  finalLower[0] = basicLower[0];
  supertrend[0] = basicLower[0];
  trend[0] = 1; // 1 = bullish
  signal[0] = 0;

  for (let i = 1; i < n; i++) {
    let fu: number, fl: number;
    // Adjust lower band (TradingView: basic_lower vs prev close vs prev final_lower)
    if (
      basicLower[i] > basicLower[i - 1]! || closes[i - 1] < finalLower[i - 1]!
    ) {
      fl = basicLower[i];
    } else {
      fl = finalLower[i - 1]!;
    }
    // Adjust upper band
    if (
      basicUpper[i] < basicUpper[i - 1]! || closes[i - 1] > finalUpper[i - 1]!
    ) {
      fu = basicUpper[i];
    } else {
      fu = finalUpper[i - 1]!;
    }
    finalLower[i] = fl;
    finalUpper[i] = fu;

    let st: number;
    let inUptrend: number;
    if (closes[i] > fu) {
      st = fl;
      inUptrend = 1;
    } else if (closes[i] < fl) {
      st = fu;
      inUptrend = 0;
    } else {
      if (trend[i - 1] === 1) {
        st = fl;
        inUptrend = 1;
      } else {
        st = fu;
        inUptrend = 0;
      }
    }
    supertrend.push(st);
    trend.push(inUptrend);
    signal.push(st !== 0 ? ((closes[i] - st) / st) * 100 : 0);
  }

  return { trend, signal };
}

async function runBacktest(job: BacktestJob, config: StrategyConfig): Promise<{
  metrics: Record<string, unknown>;
  trades: Record<string, unknown>[];
  equity_curve: Record<string, unknown>[];
}> {
  const params = job.parameters as Record<string, unknown>;
  const initialCapital = (params.initial_capital as number) || 10000;
  const positionSize = (params.position_size as number) || 100;
  const stopLoss = ((params.stop_loss_pct as number) || 2) / 100;
  const takeProfit = ((params.take_profit_pct as number) || 4) / 100;
  const timeframe = (params.timeframe as string) || "d1";

  const { dates, opens, highs, lows, closes, volumes } = await fetchMarketData(
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
        avg_win: 0,
        avg_loss: 0,
        profit_factor: 0,
      },
      trades: [],
      equity_curve: [],
    };
  }

  // Calculate indicators
  const { sma20, ema12, ema26, macd, macdSignal, rsi, atr, stochasticK, adx } =
    calculateIndicators(closes, highs, lows, volumes);
  const { trend: supertrendTrend, signal: supertrendSignal } =
    calculateSuperTrend(highs, lows, closes, 7, 2.0);

  function evaluateConditions(
    conditions: Condition[] | undefined,
    i: number,
  ): boolean {
    if (!conditions || conditions.length === 0) return true;

    for (const cond of conditions) {
      if (cond.type !== "indicator") continue;

      const name = cond.name;
      const op = cond.operator;
      const val = cond.value ?? 0;

      let indicatorValue: number | null = null;

      if (name === "rsi") indicatorValue = rsi[i] ?? 50;
      else if (name === "sma") indicatorValue = sma20[i] ?? 0;
      else if (name === "ema") indicatorValue = ema12[i] ?? 0;
      else if (name === "price_above_sma") {
        indicatorValue = (sma20[i] !== null && closes[i] > sma20[i]!) ? 1 : 0;
      } else if (name === "price_above_ema") {
        indicatorValue = (ema12[i] !== null && closes[i] > ema12[i]!) ? 1 : 0;
      } else if (name === "macd") indicatorValue = macd[i] ?? 0;
      else if (name === "macd_signal") indicatorValue = macdSignal[i] ?? 0;
      else if (name === "stochastic" || name === "stochastic_k") {
        indicatorValue = stochasticK[i] ?? 50;
      } else if (name === "adx") indicatorValue = adx[i] ?? 25;
      else if (name === "atr") indicatorValue = atr[i] ?? 0;
      else if (name === "close" || name === "price") indicatorValue = closes[i];
      else if (name === "high") indicatorValue = highs[i];
      else if (name === "low") indicatorValue = lows[i];
      else if (name === "volume") indicatorValue = volumes[i];
      else if (name === "supertrend_trend") {
        indicatorValue = supertrendTrend[i] ?? 1;
      } else if (name === "supertrend_signal") {
        indicatorValue = supertrendSignal[i] ?? 0;
      } else if (name === "supertrend_factor") indicatorValue = 2.0;

      if (indicatorValue === null) continue;

      if (op === "below") { if (!(indicatorValue < val)) return false; }
      else if (op === "above") { if (!(indicatorValue > val)) return false; }
      else if (op === "equals") { if (indicatorValue !== val) return false; }
    }
    return true;
  }

  // Run backtest
  let cash = initialCapital;
  let shares = 0;
  let entryPrice = 0;
  const trades: Record<string, unknown>[] = [];
  const equityCurve: Record<string, number>[] = [];

  for (let i = 30; i < closes.length; i++) {
    const entryConds = config.entry_conditions || [];
    const exitConds = config.exit_conditions || [];

    if (shares === 0 && evaluateConditions(entryConds, i)) {
      shares = Math.min(positionSize, Math.floor(cash / closes[i]));
      cash -= shares * closes[i];
      entryPrice = closes[i];
    } else if (shares > 0) {
      const pnlPct = (closes[i] - entryPrice) / entryPrice;
      const exitByCondition = evaluateConditions(exitConds, i);
      const exitByRisk = pnlPct >= takeProfit || pnlPct <= -stopLoss;

      if (exitByCondition || exitByRisk) {
        cash += shares * closes[i];
        trades.push({
          entry_date: dates[i - 1],
          exit_date: dates[i],
          entry_price: entryPrice,
          exit_price: closes[i],
          pnl: (closes[i] - entryPrice) * shares,
          pnl_pct: pnlPct * 100,
        });
        shares = 0;
      }
    }

    equityCurve.push({ date: dates[i], value: cash + (shares * closes[i]) });
  }

  // Calculate metrics
  const winning = trades.filter((t: Record<string, unknown>) =>
    (t.pnl as number) > 0
  );
  const losing = trades.filter((t: Record<string, unknown>) =>
    (t.pnl as number) <= 0
  );
  const finalValue = cash;
  const totalReturn = ((finalValue - initialCapital) / initialCapital) * 100;

  let peak = initialCapital;
  let maxDrawdown = 0;
  for (const eq of equityCurve) {
    if (eq.value > peak) peak = eq.value;
    const dd = (peak - eq.value) / peak;
    if (dd > maxDrawdown) maxDrawdown = dd;
  }

  const avgWin = winning.length
    ? winning.reduce(
      (s: number, t: Record<string, unknown>) => s + (t.pnl as number),
      0,
    ) / winning.length
    : 0;
  const avgLoss = losing.length
    ? Math.abs(
      losing.reduce(
        (s: number, t: Record<string, unknown>) => s + (t.pnl as number),
        0,
      ) / losing.length,
    )
    : 0;
  const profitFactor = avgLoss !== 0 ? avgWin / avgLoss : 0;

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

/** Run preset strategy via FastAPI and return result in worker format */
async function runPresetViaFastApi(job: BacktestJob): Promise<{
  metrics: Record<string, unknown>;
  trades: Record<string, unknown>[];
  equity_curve: Record<string, unknown>[];
}> {
  const strategyPreset = job.parameters?.strategy as string;
  const initialCapital = (job.parameters?.initialCapital as number) ?? 10000;
  const timeframe = (job.parameters?.timeframe as string) || "d1";
  const params = { ...job.parameters } as Record<string, unknown>;
  delete params.strategy;
  delete params.initialCapital;
  delete params.timeframe;

  const apiResult = await callFastApi<{
    symbol: string;
    strategy: string;
    period: { start: string; end: string };
    initialCapital: number;
    finalValue: number;
    totalReturn: number;
    metrics: {
      sharpeRatio?: number | null;
      maxDrawdown?: number | null;
      winRate?: number | null;
      totalTrades: number;
      profitFactor?: number | null;
      averageTrade?: number | null;
      cagr?: number | null;
    };
    equityCurve: Array<{ date: string; value: number }>;
    trades: Array<{
      date: string;
      symbol: string;
      action: string;
      quantity: number;
      price: number;
      pnl: number | null;
      entryPrice?: number | null;
      exitPrice?: number | null;
      duration?: number | null;
      fees?: number | null;
    }>;
    barsUsed: number;
    error?: string;
  }>(
    "/api/v1/backtest-strategy",
    {
      method: "POST",
      body: JSON.stringify({
        symbol: job.symbol,
        strategy: strategyPreset,
        startDate: job.start_date,
        endDate: job.end_date,
        timeframe,
        initialCapital,
        params,
      }),
    },
    90000,
  );

  if (apiResult.error) {
    throw new Error(apiResult.error);
  }

  const winning = apiResult.trades.filter((t) => (t.pnl ?? 0) > 0).length;
  const losing = apiResult.trades.length - winning;

  return {
    metrics: {
      total_trades: apiResult.metrics.totalTrades,
      winning_trades: winning,
      losing_trades: losing,
      win_rate: apiResult.metrics.totalTrades
        ? (winning / apiResult.metrics.totalTrades) * 100
        : 0,
      total_return_pct: apiResult.totalReturn,
      final_value: apiResult.finalValue,
      max_drawdown_pct: apiResult.metrics.maxDrawdown ?? 0,
      sharpe_ratio: apiResult.metrics.sharpeRatio ?? null,
      profit_factor: apiResult.metrics.profitFactor ?? null,
      average_trade: apiResult.metrics.averageTrade ?? null,
      cagr: apiResult.metrics.cagr ?? null,
    },
    trades: apiResult.trades.map((t) => ({
      date: t.date,
      symbol: t.symbol,
      action: t.action,
      quantity: t.quantity,
      price: t.price,
      pnl: t.pnl,
      entryPrice: t.entryPrice ?? null,
      exitPrice: t.exitPrice ?? null,
      duration: t.duration ?? null,
      fees: t.fees ?? null,
    })),
    equity_curve: apiResult.equityCurve.map((p) => ({
      date: p.date,
      value: p.value,
    })),
  };
}

serve(async (): Promise<Response> => {
  const supabase = getSupabaseClient();

  console.log("Backtest worker started");

  try {
    for (let i = 0; i < 3; i++) {
      const job = await claimJob(supabase);

      if (!job) {
        console.log("No more pending jobs");
        break;
      }

      console.log(`Processing job ${job.id} for ${job.symbol}`);

      try {
        let result: {
          metrics: Record<string, unknown>;
          trades: Record<string, unknown>[];
          equity_curve: Record<string, unknown>[];
        };

        if (!job.strategy_id && job.parameters?.strategy) {
          // Preset strategy: call FastAPI
          result = await runPresetViaFastApi(job);
        } else if (job.strategy_id) {
          // Builder strategy: use local TS backtest
          const { data: strategy } = await supabase
            .from("strategy_user_strategies")
            .select("config")
            .eq("id", job.strategy_id)
            .single();

          const rawConfig = (strategy?.config || {}) as StrategyConfig;
          const { entry_conditions, exit_conditions } = normalizeConfig(
            rawConfig,
          );
          const config: StrategyConfig = {
            ...rawConfig,
            entry_conditions,
            exit_conditions,
          };
          result = await runBacktest(job, config);
        } else {
          throw new Error("Job must have strategy_id or parameters.strategy");
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
      JSON.stringify({ error: err?.message || "Worker failed" }),
      {
        status: 500,
        headers: { "Content-Type": "application/json" },
      },
    );
  }
});
