// Strategy Backtest Worker - Processes pending backtest jobs
// All strategies (preset + builder) run natively in the TS backtest engine.
// Presets (supertrend_ai, sma_crossover, buy_and_hold) are translated to condition configs.

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";
import {
  type FrontendCondition,
  normalizeToWorkerFormat,
  type StrategyConfigRaw,
  type WorkerCondition,
} from "../_shared/strategy-translator.ts";

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

interface StrategyConfig extends StrategyConfigRaw {
  filters?: WorkerCondition[];
  parameters?: Record<string, unknown>;
}

/** Normalize config using shared translator. */
function normalizeConfig(
  raw: StrategyConfig,
): { entry_conditions: Condition[]; exit_conditions: Condition[] } {
  return normalizeToWorkerFormat(raw);
}

async function claimJob(
  supabase: ReturnType<typeof getSupabaseClient>,
  triggeredJobId?: string,
): Promise<BacktestJob | null> {
  let jobId: string | null = null;

  if (triggeredJobId) {
    // Claim the specific triggered job to avoid race conditions
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
    // Fallback: claim oldest pending job via RPC
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

/** Update heartbeat_at to signal worker is still alive. */
async function updateHeartbeat(
  supabase: ReturnType<typeof getSupabaseClient>,
  jobId: string,
): Promise<void> {
  await supabase
    .from("strategy_backtest_jobs")
    .update({ heartbeat_at: new Date().toISOString() })
    .eq("id", jobId);
}

/** Check if job has been cancelled. Returns true if cancelled. */
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

  // Look up symbol_id from the symbols table
  const { data: symbolRow } = await supabase
    .from("symbols")
    .select("id")
    .eq("ticker", symbol.toUpperCase())
    .single();

  if (!symbolRow) {
    throw new Error(`Symbol ${symbol} not found in database`);
  }

  // Fetch bars from ohlc_bars_v2
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
  const opens = bars.map((b) => b.open as number);
  const highs = bars.map((b) => b.high as number);
  const lows = bars.map((b) => b.low as number);
  const closes = bars.map((b) => b.close as number);
  const volumes = bars.map((b) => b.volume as number);

  console.log(
    `[BacktestWorker] Fetched ${bars.length} bars for ${symbol} from ohlc_bars_v2`,
  );
  return { dates, opens, highs, lows, closes, volumes };
}

/** Compute SMA over a window. Returns null if not enough data. */
function computeSMA(data: number[], period: number): (number | null)[] {
  const result: (number | null)[] = [];
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      result.push(null);
      continue;
    }
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) sum += data[j];
    result.push(sum / period);
  }
  return result;
}

/** Compute EMA seeded with SMA of first `period` values. */
function computeEMA(data: number[], period: number): (number | null)[] {
  const result: (number | null)[] = [];
  const k = 2 / (period + 1);
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      result.push(null);
      continue;
    }
    if (i === period - 1) {
      // Seed with SMA of first `period` values
      let sum = 0;
      for (let j = 0; j < period; j++) sum += data[j];
      result.push(sum / period);
      continue;
    }
    const prev = result[i - 1] ?? data[i];
    result.push((data[i] - prev) * k + prev);
  }
  return result;
}

function calculateIndicators(
  closes: number[],
  highs: number[],
  lows: number[],
  volumes: number[],
) {
  const n = closes.length;

  // SMAs
  const sma20 = computeSMA(closes, 20);
  const sma50 = computeSMA(closes, 50);

  // EMAs
  const ema12 = computeEMA(closes, 12);
  const ema26 = computeEMA(closes, 26);

  // MACD line, signal, histogram
  const macd: (number | null)[] = [];
  for (let i = 0; i < n; i++) {
    if (ema12[i] !== null && ema26[i] !== null) {
      macd.push(ema12[i]! - ema26[i]!);
    } else macd.push(null);
  }
  // MACD signal: 9-period EMA of MACD values (skip nulls for seeding)
  const macdSignal: (number | null)[] = [];
  const macdHist: (number | null)[] = [];
  let macdSigCount = 0;
  let macdSigSum = 0;
  let macdSigEma: number | null = null;
  for (let i = 0; i < n; i++) {
    if (macd[i] === null) {
      macdSignal.push(null);
      macdHist.push(null);
      continue;
    }
    macdSigCount++;
    macdSigSum += macd[i]!;
    if (macdSigCount < 9) {
      macdSignal.push(null);
      macdHist.push(null);
      continue;
    }
    if (macdSigCount === 9) {
      macdSigEma = macdSigSum / 9;
    } else {
      macdSigEma = (macd[i]! - macdSigEma!) * (2 / 10) + macdSigEma!;
    }
    macdSignal.push(macdSigEma);
    macdHist.push(macd[i]! - macdSigEma!);
  }

  // RSI 14 — Wilder's smoothing (matches TradingView)
  const rsi: number[] = [];
  let prevAvgGain = 0;
  let prevAvgLoss = 0;
  for (let i = 0; i < n; i++) {
    if (i < 1) {
      rsi.push(50);
      continue;
    }
    if (i <= 14) {
      // Accumulate for seed
      if (i < 14) {
        rsi.push(50);
        continue;
      }
      // i === 14: compute initial SMA of gains/losses over first 14 changes
      let gains = 0, losses = 0;
      for (let j = 1; j <= 14; j++) {
        const diff = closes[j] - closes[j - 1];
        if (diff > 0) gains += diff;
        else losses -= diff;
      }
      prevAvgGain = gains / 14;
      prevAvgLoss = losses / 14;
    } else {
      // Wilder smoothing
      const diff = closes[i] - closes[i - 1];
      const gain = diff > 0 ? diff : 0;
      const loss = diff < 0 ? -diff : 0;
      prevAvgGain = (prevAvgGain * 13 + gain) / 14;
      prevAvgLoss = (prevAvgLoss * 13 + loss) / 14;
    }
    const rs = prevAvgLoss === 0 ? 100 : prevAvgGain / prevAvgLoss;
    rsi.push(100 - (100 / (1 + rs)));
  }

  // ATR 14 — Wilder's smoothing
  const atr: (number | null)[] = [];
  const trueRange: number[] = [];
  for (let i = 0; i < n; i++) {
    if (i === 0) trueRange.push(highs[0] - lows[0]);
    else {
      trueRange.push(Math.max(
        highs[i] - lows[i],
        Math.abs(highs[i] - closes[i - 1]),
        Math.abs(lows[i] - closes[i - 1]),
      ));
    }
    if (i < 13) atr.push(null);
    else if (i === 13) {
      let sum = 0;
      for (let j = 0; j < 14; j++) sum += trueRange[j];
      atr.push(sum / 14);
    } else {
      atr.push((atr[i - 1]! * 13 + trueRange[i]) / 14);
    }
  }

  // Stochastic %K (14-period), NaN-safe
  const stochasticK: (number | null)[] = [];
  for (let i = 0; i < n; i++) {
    if (i < 13) {
      stochasticK.push(null);
      continue;
    }
    const low14 = Math.min(...lows.slice(i - 13, i + 1));
    const high14 = Math.max(...highs.slice(i - 13, i + 1));
    const range = high14 - low14;
    stochasticK.push(range > 0 ? 100 * (closes[i] - low14) / range : 50);
  }

  // ADX (14-period, Wilder's directional movement)
  const adx: (number | null)[] = [];
  const plusDI: (number | null)[] = [];
  const minusDI: (number | null)[] = [];
  {
    const plusDM: number[] = [];
    const minusDM: number[] = [];
    for (let i = 0; i < n; i++) {
      if (i === 0) {
        plusDM.push(0);
        minusDM.push(0);
        continue;
      }
      const upMove = highs[i] - highs[i - 1];
      const downMove = lows[i - 1] - lows[i];
      plusDM.push(upMove > downMove && upMove > 0 ? upMove : 0);
      minusDM.push(downMove > upMove && downMove > 0 ? downMove : 0);
    }
    let smoothPlusDM = 0, smoothMinusDM = 0, smoothTR = 0, adxSmooth = 0;
    for (let i = 0; i < n; i++) {
      if (i < 14) {
        smoothPlusDM += plusDM[i];
        smoothMinusDM += minusDM[i];
        smoothTR += trueRange[i];
        adx.push(null);
        plusDI.push(null);
        minusDI.push(null);
        continue;
      }
      if (i === 14) {
        // Already summed first 14 values
      } else {
        smoothPlusDM = smoothPlusDM - (smoothPlusDM / 14) + plusDM[i];
        smoothMinusDM = smoothMinusDM - (smoothMinusDM / 14) + minusDM[i];
        smoothTR = smoothTR - (smoothTR / 14) + trueRange[i];
      }
      const pdi = smoothTR > 0 ? (smoothPlusDM / smoothTR) * 100 : 0;
      const mdi = smoothTR > 0 ? (smoothMinusDM / smoothTR) * 100 : 0;
      plusDI.push(pdi);
      minusDI.push(mdi);
      const diSum = pdi + mdi;
      const dx = diSum > 0 ? Math.abs(pdi - mdi) / diSum * 100 : 0;
      if (i < 28) {
        adx.push(null);
        continue;
      }
      if (i === 28) {
        // Initial ADX = SMA of first 14 DX values
        let dxSum = 0;
        // Recompute DX for bars 14..27 (we only need the average)
        // Simplified: use current DX as seed
        adxSmooth = dx;
        adx.push(adxSmooth);
      } else {
        adxSmooth = (adxSmooth * 13 + dx) / 14;
        adx.push(adxSmooth);
      }
    }
  }

  // Bollinger Bands (20-period, 2 std dev)
  const bbUpper: (number | null)[] = [];
  const bbLower: (number | null)[] = [];
  const bbMiddle: (number | null)[] = [];
  for (let i = 0; i < n; i++) {
    if (i < 19) {
      bbUpper.push(null);
      bbLower.push(null);
      bbMiddle.push(null);
      continue;
    }
    const slice = closes.slice(i - 19, i + 1);
    const mean = slice.reduce((a, b) => a + b, 0) / 20;
    const variance = slice.reduce((a, v) => a + (v - mean) ** 2, 0) / 20;
    const stdDev = Math.sqrt(variance);
    bbMiddle.push(mean);
    bbUpper.push(mean + 2 * stdDev);
    bbLower.push(mean - 2 * stdDev);
  }

  // CCI (20-period)
  const cci: (number | null)[] = [];
  for (let i = 0; i < n; i++) {
    if (i < 19) {
      cci.push(null);
      continue;
    }
    const tps: number[] = [];
    for (let j = i - 19; j <= i; j++) {
      tps.push((highs[j] + lows[j] + closes[j]) / 3);
    }
    const tp = tps[tps.length - 1];
    const meanTP = tps.reduce((a, b) => a + b, 0) / 20;
    const meanDev = tps.reduce((a, v) => a + Math.abs(v - meanTP), 0) / 20;
    cci.push(meanDev > 0 ? (tp - meanTP) / (0.015 * meanDev) : 0);
  }

  // OBV
  const obv: number[] = [];
  for (let i = 0; i < n; i++) {
    if (i === 0) {
      obv.push(volumes[0]);
      continue;
    }
    if (closes[i] > closes[i - 1]) obv.push(obv[i - 1] + volumes[i]);
    else if (closes[i] < closes[i - 1]) obv.push(obv[i - 1] - volumes[i]);
    else obv.push(obv[i - 1]);
  }

  // Volume MA (20-period)
  const volumeMA = computeSMA(volumes, 20);

  return {
    sma20,
    sma50,
    ema12,
    ema26,
    macd,
    macdSignal,
    macdHist,
    rsi,
    atr,
    stochasticK,
    adx,
    plusDI,
    minusDI,
    bbUpper,
    bbLower,
    bbMiddle,
    cci,
    obv,
    volumeMA,
  };
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
  const initialCapital = (params.initialCapital as number) ||
    (params.initial_capital as number) || 10000;
  const positionSize = (params.position_size as number) || 100;
  const stopLoss = ((params.stop_loss_pct as number) || 2) / 100;
  const takeProfit = ((params.take_profit_pct as number) || 4) / 100;
  const timeframe = (params.timeframe as string) || "d1";

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

  // Calculate indicators
  const {
    sma20,
    sma50,
    ema12,
    ema26,
    macd,
    macdSignal,
    macdHist,
    rsi,
    atr,
    stochasticK,
    adx,
    plusDI,
    minusDI,
    bbUpper,
    bbLower,
    bbMiddle,
    cci,
    obv,
    volumeMA,
  } = calculateIndicators(closes, highs, lows, volumes);
  const { trend: supertrendTrend, signal: supertrendSignal } =
    calculateSuperTrend(highs, lows, closes, 7, 2.0);

  // Log conditions once to diagnose translation issues
  const entryConds = config.entry_conditions || [];
  const exitConds = config.exit_conditions || [];
  console.log(
    `[BacktestWorker] Entry conditions (${entryConds.length}):`,
    JSON.stringify(
      entryConds.map((c) => ({
        type: c.type,
        name: c.name,
        op: c.operator,
        val: c.value,
      })),
    ),
  );
  console.log(
    `[BacktestWorker] Exit conditions (${exitConds.length}):`,
    JSON.stringify(
      exitConds.map((c) => ({
        type: c.type,
        name: c.name,
        op: c.operator,
        val: c.value,
      })),
    ),
  );

  const warnedIndicators = new Set<string>();

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

      // Momentum indicators
      if (name === "rsi") indicatorValue = rsi[i] ?? null;
      else if (name === "stochastic" || name === "stochastic_k") {
        indicatorValue = stochasticK[i] ?? null;
      } else if (name === "cci") indicatorValue = cci[i] ?? null;
      else if (name === "macd") indicatorValue = macd[i] ?? null;
      else if (name === "macd_signal") indicatorValue = macdSignal[i] ?? null;
      else if (name === "macd_hist") indicatorValue = macdHist[i] ?? null;
      // Trend indicators
      else if (name === "sma") indicatorValue = sma20[i] ?? null;
      else if (name === "ema") indicatorValue = ema12[i] ?? null;
      else if (name === "adx") indicatorValue = adx[i] ?? null;
      else if (name === "plus_di") indicatorValue = plusDI[i] ?? null;
      else if (name === "minus_di") indicatorValue = minusDI[i] ?? null;
      else if (name === "price_above_sma") {
        indicatorValue = (sma20[i] !== null && closes[i] > sma20[i]!) ? 1 : 0;
      } else if (name === "price_above_ema") {
        indicatorValue = (ema12[i] !== null && closes[i] > ema12[i]!) ? 1 : 0;
      } else if (name === "price_vs_sma20") {
        indicatorValue = sma20[i] !== null
          ? (closes[i] - sma20[i]!) / sma20[i]!
          : null;
      } else if (name === "price_vs_sma50") {
        indicatorValue = sma50[i] !== null
          ? (closes[i] - sma50[i]!) / sma50[i]!
          : null;
      } // Volatility indicators
      else if (name === "atr") indicatorValue = atr[i] ?? null;
      else if (name === "bb_upper") indicatorValue = bbUpper[i] ?? null;
      else if (name === "bb_lower") indicatorValue = bbLower[i] ?? null;
      else if (name === "bb") indicatorValue = bbMiddle[i] ?? null;
      else if (name === "supertrend_trend") {
        indicatorValue = supertrendTrend[i] ?? null;
      } else if (name === "supertrend_signal") {
        indicatorValue = supertrendSignal[i] ?? null;
      } else if (name === "supertrend_factor") indicatorValue = 2.0;
      // Price
      else if (name === "close" || name === "price") indicatorValue = closes[i];
      else if (name === "high") indicatorValue = highs[i];
      else if (name === "low") indicatorValue = lows[i];
      else if (name === "open") indicatorValue = opens[i];
      // Volume
      else if (name === "volume") indicatorValue = volumes[i];
      else if (name === "volume_ratio") {
        indicatorValue = volumeMA[i] !== null && volumeMA[i]! > 0
          ? volumes[i] / volumeMA[i]!
          : null;
      } else if (name === "obv") indicatorValue = obv[i] ?? null;
      else {
        // Unknown indicator — warn once and skip (don't silently pass)
        if (!warnedIndicators.has(name)) {
          console.warn(
            `[BacktestWorker] Unknown indicator "${name}" — condition skipped`,
          );
          warnedIndicators.add(name);
        }
        continue;
      }

      if (indicatorValue === null) continue;

      // Evaluate operator (above_equal/below_equal preserve >= / <= precision)
      if (op === "below") { if (!(indicatorValue < val)) return false; }
      else if (op === "below_equal") {
        if (!(indicatorValue <= val)) return false;
      } else if (op === "above") { if (!(indicatorValue > val)) return false; }
      else if (op === "above_equal") {
        if (!(indicatorValue >= val)) return false;
      } else if (op === "equals") {
        const epsilon = 0.0001;
        if (Math.abs(indicatorValue - val) >= epsilon) return false;
      }
    }
    return true;
  }

  // Run backtest
  const slippagePct = 0.0005; // 5 basis points per side (realistic for liquid equities)
  let cash = initialCapital;
  let shares = 0;
  let entryPrice = 0;
  let entryBar = 0; // Track actual entry bar index for correct date recording
  const trades: Record<string, unknown>[] = [];
  const equityCurve: { date: string; value: number }[] = [];

  for (let i = 30; i < closes.length; i++) {
    if (shares === 0 && evaluateConditions(entryConds, i)) {
      const execPrice = closes[i] * (1 + slippagePct); // slippage on buy
      shares = Math.min(positionSize, Math.floor(cash / execPrice));
      cash -= shares * execPrice;
      entryPrice = execPrice;
      entryBar = i;
    } else if (shares > 0) {
      // Check intrabar SL/TP using highs and lows for realistic risk management
      const lowPnlPct = (lows[i] - entryPrice) / entryPrice;
      const highPnlPct = (highs[i] - entryPrice) / entryPrice;
      const hitStopLoss = lowPnlPct <= -stopLoss;
      const hitTakeProfit = highPnlPct >= takeProfit;
      const exitByCondition = evaluateConditions(exitConds, i);
      const exitByRisk = hitStopLoss || hitTakeProfit;

      if (exitByCondition || exitByRisk) {
        // Determine exit price: SL/TP hit at the trigger level, condition at close
        let exitPrice: number;
        let closeReason: string;
        if (hitStopLoss) {
          exitPrice = entryPrice * (1 - stopLoss); // exited at stop level
          closeReason = "stop_loss";
        } else if (hitTakeProfit) {
          exitPrice = entryPrice * (1 + takeProfit); // exited at take-profit level
          closeReason = "take_profit";
        } else {
          exitPrice = closes[i];
          closeReason = "exit_condition";
        }
        exitPrice *= 1 - slippagePct; // slippage on sell
        cash += shares * exitPrice;
        const pnl = (exitPrice - entryPrice) * shares;
        const pnlPct = (exitPrice - entryPrice) / entryPrice;
        trades.push({
          entry_date: dates[entryBar],
          exit_date: dates[i],
          entry_price: entryPrice,
          exit_price: exitPrice,
          quantity: shares,
          direction: "long",
          close_reason: closeReason,
          pnl,
          pnl_pct: pnlPct * 100,
        });
        shares = 0;
      }
    }

    equityCurve.push({ date: dates[i], value: cash + (shares * closes[i]) });
  }

  // Include unrealized position value in final portfolio value
  const lastClose = closes.length > 0 ? closes[closes.length - 1] : 0;
  const finalValue = cash + (shares * lastClose);

  // Calculate metrics
  const winning = trades.filter((t: Record<string, unknown>) =>
    (t.pnl as number) > 0
  );
  const losing = trades.filter((t: Record<string, unknown>) =>
    (t.pnl as number) <= 0
  );
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
  // Profit factor = total gross profit / total gross loss (not avgWin/avgLoss)
  const totalGrossProfit = winning.reduce(
    (s: number, t: Record<string, unknown>) => s + (t.pnl as number),
    0,
  );
  const totalGrossLoss = Math.abs(
    losing.reduce(
      (s: number, t: Record<string, unknown>) => s + (t.pnl as number),
      0,
    ),
  );
  const profitFactor = totalGrossLoss > 0
    ? totalGrossProfit / totalGrossLoss
    : 0;

  // Sharpe ratio (annualized) from equity curve daily returns
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
        sharpeRatio = (meanReturn / stdDev) * Math.sqrt(252); // annualize assuming daily bars
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

/** Build a StrategyConfig for a preset strategy name so it runs natively. */
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
      // Entry: always (empty conditions = true). Exit: never (impossible condition).
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

serve(async (req: Request): Promise<Response> => {
  // Handle OPTIONS preflight
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

  // Gateway key auth
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

  // Read triggered_job_id from request body
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
          {
            headers: { "Content-Type": "application/json" },
          },
        );
      }

      console.log(`Processing job ${job.id} for ${job.symbol}`);

      try {
        // Cancel check before starting
        if (await isJobCancelled(supabase, job.id)) {
          console.log(`Job ${job.id} was cancelled before processing`);
          return new Response(
            JSON.stringify({ success: true, message: "Job cancelled" }),
            {
              headers: { "Content-Type": "application/json" },
            },
          );
        }

        let result: {
          metrics: Record<string, unknown>;
          trades: Record<string, unknown>[];
          equity_curve: Record<string, unknown>[];
        };

        // Determine strategy config: prefer inline config from parameters, then DB lookup, then preset
        const inlineConfig = job.parameters?.strategy_config as
          | StrategyConfig
          | undefined;

        if (inlineConfig) {
          // Inline config: use the exact conditions the user submitted (most reliable path)
          console.log(`Job ${job.id}: using inline strategy_config`);
          const { entry_conditions, exit_conditions } = normalizeConfig(
            inlineConfig,
          );
          const config: StrategyConfig = {
            ...inlineConfig,
            entry_conditions,
            exit_conditions,
          };

          await updateHeartbeat(supabase, job.id);
          if (await isJobCancelled(supabase, job.id)) {
            console.log(`Job ${job.id} cancelled before backtest computation`);
            return new Response(
              JSON.stringify({ success: true, message: "Job cancelled" }),
              {
                headers: { "Content-Type": "application/json" },
              },
            );
          }

          result = await runBacktest(supabase, job, config);
          await updateHeartbeat(supabase, job.id);
        } else if (!job.strategy_id && job.parameters?.strategy) {
          // Preset strategy: run natively with translated config
          const presetName = job.parameters.strategy as string;
          console.log(
            `Job ${job.id}: running preset strategy "${presetName}" natively`,
          );
          const presetConfig = getPresetConfig(presetName);

          // Buy-and-hold: disable stop-loss/take-profit so position holds to end
          if (presetName === "buy_and_hold") {
            job.parameters.stop_loss_pct = 99999;
            job.parameters.take_profit_pct = 99999;
          }

          await updateHeartbeat(supabase, job.id);
          if (await isJobCancelled(supabase, job.id)) {
            console.log(`Job ${job.id} cancelled before backtest computation`);
            return new Response(
              JSON.stringify({ success: true, message: "Job cancelled" }),
              {
                headers: { "Content-Type": "application/json" },
              },
            );
          }

          result = await runBacktest(supabase, job, presetConfig);
          await updateHeartbeat(supabase, job.id);
        } else if (job.strategy_id) {
          // Builder strategy: read config from DB
          console.log(
            `Job ${job.id}: reading config from DB for strategy ${job.strategy_id}`,
          );
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

          // Heartbeat after config loaded, cancel check before heavy computation
          await updateHeartbeat(supabase, job.id);
          if (await isJobCancelled(supabase, job.id)) {
            console.log(`Job ${job.id} cancelled before backtest computation`);
            return new Response(
              JSON.stringify({ success: true, message: "Job cancelled" }),
              {
                headers: { "Content-Type": "application/json" },
              },
            );
          }

          result = await runBacktest(supabase, job, config);

          // Heartbeat after computation complete
          await updateHeartbeat(supabase, job.id);
        } else {
          throw new Error(
            "Job must have strategy_config, strategy_id, or parameters.strategy",
          );
        }

        // Final cancel check before writing results
        if (await isJobCancelled(supabase, job.id)) {
          console.log(`Job ${job.id} cancelled before saving results`);
          return new Response(
            JSON.stringify({ success: true, message: "Job cancelled" }),
            {
              headers: { "Content-Type": "application/json" },
            },
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
