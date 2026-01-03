// trigger-ranking-job: Compute and save ML rankings for a symbol
// POST /trigger-ranking-job
// Body: { "symbol": "AAPL" }
//
// This function fetches options chain data, computes rankings using
// the Momentum-Value-Greeks framework, and saves results to options_ranks.
// Works synchronously - no external Python worker needed.

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { handleCorsOptions, jsonResponse, errorResponse } from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";
import { getProviderRouter } from "../_shared/providers/factory.ts";

interface TriggerRankingRequest {
  symbol: string;
}

interface OptionContract {
  symbol: string;
  strike: number;
  expiration: number;
  type: "call" | "put";
  bid: number;
  ask: number;
  mark: number;
  last: number;
  volume: number;
  openInterest: number;
  impliedVolatility: number;
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  rho: number;
}

interface RankedOption {
  contract_symbol: string;
  strike: number;
  expiry: string;
  side: "call" | "put";
  ml_score: number;
  composite_rank: number;
  momentum_score: number;
  value_score: number;
  greeks_score: number;
  iv_rank: number;
  spread_pct: number;
  vol_oi_ratio: number;
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  rho: number;
  bid: number;
  ask: number;
  mark: number;
  last_price: number;
  volume: number;
  open_interest: number;
  signal_discount: boolean;
  signal_runner: boolean;
  signal_greeks: boolean;
  signal_buy: boolean;
  signals: string;
}

// Ranking weights (matching Python implementation)
const MOMENTUM_WEIGHT = 0.30;
const VALUE_WEIGHT = 0.35;
const GREEKS_WEIGHT = 0.35;

// Thresholds
const OPTIMAL_DELTA_TARGET = 0.55;
const GAMMA_EXCELLENT_THRESHOLD = 0.04;
const VOLUME_OI_STRONG = 0.20;

// Signal thresholds
const DISCOUNT_IV_RANK_THRESHOLD = 30;
const DISCOUNT_MOMENTUM_THRESHOLD = 50;
const DISCOUNT_SPREAD_THRESHOLD = 2.0;
const RUNNER_MOMENTUM_THRESHOLD = 75;
const RUNNER_VOLUME_THRESHOLD = 100;
const RUNNER_VOL_OI_THRESHOLD = 0.10;
const RUNNER_SPREAD_THRESHOLD = 3.0;
const GREEKS_SPREAD_THRESHOLD = 2.0;
const BUY_COMPOSITE_THRESHOLD = 65;

function calculateSpreadPct(bid: number, ask: number): number {
  const mid = (bid + ask) / 2;
  if (mid <= 0) return 100;
  return ((ask - bid) / mid) * 100;
}

function calculateValueScore(iv: number, ivMin: number, ivMax: number, spreadPct: number): { valueScore: number; ivRank: number } {
  // IV Rank: (current - min) / (max - min) * 100
  const ivRange = ivMax - ivMin;
  const ivRank = ivRange > 0 ? ((iv - ivMin) / ivRange) * 100 : 50;

  // IV value score (lower IV = better for buyer)
  const ivValueScore = 100 - ivRank;

  // Spread score: penalty = min(spread% * 2, 50), score = 100 - penalty
  const spreadPenalty = Math.min(spreadPct * 2, 50);
  const spreadScore = 100 - spreadPenalty;

  // Combined: 60% IV, 40% spread
  const valueScore = ivValueScore * 0.60 + spreadScore * 0.40;

  return { valueScore, ivRank };
}

function calculateMomentumScore(volume: number, openInterest: number, price: number): { momentumScore: number; volOiRatio: number; liquidityConfidence: number } {
  // Volume/OI ratio
  const volOiRatio = openInterest > 0 ? volume / openInterest : 0;
  const volOiScore = Math.min((volOiRatio / VOLUME_OI_STRONG) * 100, 100);

  // Liquidity confidence (0.1 to 1.0)
  const minConf = 0.1;
  const volConf = Math.min(minConf + (1 - minConf) * volume / 100, 1.0);
  const oiConf = Math.min(minConf + (1 - minConf) * openInterest / 500, 1.0);
  const priceConf = Math.min(minConf + (1 - minConf) * price / 5.0, 1.0);
  const liquidityConfidence = Math.pow(volConf * oiConf * priceConf, 1/3);

  // Without historical data, use volume-based proxy
  const volumeNormalized = Math.min(volume / 1000, 1.0);
  const priceMomentumScore = volumeNormalized * 20 + 40; // Range 40-60

  // Combined momentum (simplified without history)
  const rawMomentum = priceMomentumScore * 0.50 + volOiScore * 0.50;

  // Apply liquidity dampening
  const momentumScore = 50 + (rawMomentum - 50) * liquidityConfidence;

  return { momentumScore: Math.max(0, Math.min(100, momentumScore)), volOiRatio, liquidityConfidence };
}

function calculateGreeksScore(
  delta: number,
  gamma: number,
  theta: number,
  vega: number,
  side: "call" | "put",
  midPrice: number
): number {
  // Delta score: target 0.55 for calls, -0.55 for puts
  const target = side === "call" ? OPTIMAL_DELTA_TARGET : -OPTIMAL_DELTA_TARGET;
  const deltaDeviation = Math.abs(delta - target);
  const deltaScore = Math.max(0, 100 - 100 * deltaDeviation);

  // Gamma score: higher gamma = better (more acceleration)
  const gammaScore = Math.min((gamma / GAMMA_EXCELLENT_THRESHOLD) * 100, 100);

  // Vega score: higher vega = better (for low IV buying)
  const vegaScore = Math.min((vega / 0.30) * 100, 100);

  // Theta penalty: |theta/mid| * 10, capped at 40
  const thetaPct = midPrice > 0 ? (Math.abs(theta) / midPrice) * 100 : 10;
  const thetaPenalty = Math.min(thetaPct * 10, 40);

  // Combined: 50% delta, 35% gamma, 10% vega, minus theta penalty
  const greeksScore = deltaScore * 0.50 + gammaScore * 0.35 + vegaScore * 0.10 - thetaPenalty;

  return Math.max(0, Math.min(100, greeksScore));
}

function rankOptions(calls: OptionContract[], puts: OptionContract[]): RankedOption[] {
  const allContracts = [
    ...calls.map(c => ({ ...c, side: "call" as const })),
    ...puts.map(p => ({ ...p, side: "put" as const })),
  ];

  if (allContracts.length === 0) return [];

  // Calculate IV range for IV Rank
  const allIVs = allContracts.map(c => c.impliedVolatility).filter(iv => iv > 0);
  const ivMin = allIVs.length > 0 ? Math.min(...allIVs) : 0.2;
  const ivMax = allIVs.length > 0 ? Math.max(...allIVs) : 0.5;

  const ranked: RankedOption[] = allContracts.map(contract => {
    const spreadPct = calculateSpreadPct(contract.bid, contract.ask);
    const { valueScore, ivRank } = calculateValueScore(
      contract.impliedVolatility, ivMin, ivMax, spreadPct
    );
    const { momentumScore, volOiRatio, liquidityConfidence } = calculateMomentumScore(
      contract.volume, contract.openInterest, contract.mark
    );
    const greeksScore = calculateGreeksScore(
      contract.delta, contract.gamma, contract.theta, contract.vega,
      contract.side, contract.mark
    );

    // Composite rank
    const compositeRank =
      momentumScore * MOMENTUM_WEIGHT +
      valueScore * VALUE_WEIGHT +
      greeksScore * GREEKS_WEIGHT;

    // Generate signals
    const signalDiscount =
      ivRank < DISCOUNT_IV_RANK_THRESHOLD &&
      momentumScore > DISCOUNT_MOMENTUM_THRESHOLD &&
      spreadPct < DISCOUNT_SPREAD_THRESHOLD;

    const signalRunner =
      momentumScore > RUNNER_MOMENTUM_THRESHOLD &&
      contract.volume > RUNNER_VOLUME_THRESHOLD &&
      volOiRatio > RUNNER_VOL_OI_THRESHOLD &&
      spreadPct < RUNNER_SPREAD_THRESHOLD;

    const signalGreeks =
      Math.abs(contract.delta) >= 0.40 &&
      Math.abs(contract.delta) <= 0.70 &&
      contract.gamma > 0.02 &&
      spreadPct < GREEKS_SPREAD_THRESHOLD;

    const signalBuy =
      compositeRank > BUY_COMPOSITE_THRESHOLD &&
      (signalDiscount || signalRunner || signalGreeks);

    const signals: string[] = [];
    if (signalDiscount) signals.push("DISCOUNT");
    if (signalRunner) signals.push("RUNNER");
    if (signalGreeks) signals.push("GREEKS");
    if (signalBuy) signals.push("BUY");

    // Convert expiration timestamp to date string
    const expiryDate = new Date(contract.expiration * 1000).toISOString().split('T')[0];

    return {
      contract_symbol: contract.symbol,
      strike: contract.strike,
      expiry: expiryDate,
      side: contract.side,
      ml_score: compositeRank / 100, // Normalized 0-1
      composite_rank: compositeRank,
      momentum_score: momentumScore,
      value_score: valueScore,
      greeks_score: greeksScore,
      iv_rank: ivRank,
      spread_pct: spreadPct,
      vol_oi_ratio: volOiRatio,
      delta: contract.delta,
      gamma: contract.gamma,
      theta: contract.theta,
      vega: contract.vega,
      rho: contract.rho,
      bid: contract.bid,
      ask: contract.ask,
      mark: contract.mark,
      last_price: contract.last,
      volume: contract.volume,
      open_interest: contract.openInterest,
      signal_discount: signalDiscount,
      signal_runner: signalRunner,
      signal_greeks: signalGreeks,
      signal_buy: signalBuy,
      signals: signals.join(","),
    };
  });

  // Sort by composite rank descending
  ranked.sort((a, b) => b.composite_rank - a.composite_rank);

  // Return top 100 (balanced across expiries would be better, but keeping simple for now)
  return ranked.slice(0, 100);
}

serve(async (req: Request): Promise<Response> => {
  if (req.method === "OPTIONS") {
    return handleCorsOptions();
  }

  if (req.method !== "POST") {
    return errorResponse("Method not allowed", 405);
  }

  try {
    const body: TriggerRankingRequest = await req.json();
    const symbol = body.symbol?.toUpperCase().trim();

    if (!symbol) {
      return errorResponse("Missing 'symbol' in request body", 400);
    }

    console.log(`[Ranking Job] Starting inline ranking for ${symbol}`);
    const startTime = Date.now();

    const supabase = getSupabaseClient();

    // Get symbol_id
    const { data: symbolData, error: symbolError } = await supabase
      .from("symbols")
      .select("id")
      .eq("ticker", symbol)
      .single();

    if (symbolError || !symbolData) {
      return errorResponse(`Symbol not found: ${symbol}`, 404);
    }

    const symbolId = symbolData.id;

    // Fetch options chain directly via ProviderRouter
    console.log(`[Ranking Job] Fetching options chain for ${symbol} via ProviderRouter`);
    const router = getProviderRouter();

    let optionsData;
    try {
      optionsData = await router.getOptionsChain({ underlying: symbol });
    } catch (err) {
      console.error(`[Ranking Job] Failed to fetch options chain:`, err);
      return errorResponse(`Failed to fetch options chain: ${err instanceof Error ? err.message : String(err)}`, 500);
    }

    const calls: OptionContract[] = (optionsData.calls || []).map((c: any) => ({
      symbol: c.symbol,
      strike: c.strike,
      expiration: c.expiration,
      type: "call" as const,
      bid: c.bid || 0,
      ask: c.ask || 0,
      mark: c.mark || ((c.bid || 0) + (c.ask || 0)) / 2,
      last: c.last || 0,
      volume: c.volume || 0,
      openInterest: c.openInterest || 0,
      impliedVolatility: c.impliedVolatility || 0,
      delta: c.delta || 0,
      gamma: c.gamma || 0,
      theta: c.theta || 0,
      vega: c.vega || 0,
      rho: c.rho || 0,
    }));

    const puts: OptionContract[] = (optionsData.puts || []).map((p: any) => ({
      symbol: p.symbol,
      strike: p.strike,
      expiration: p.expiration,
      type: "put" as const,
      bid: p.bid || 0,
      ask: p.ask || 0,
      mark: p.mark || ((p.bid || 0) + (p.ask || 0)) / 2,
      last: p.last || 0,
      volume: p.volume || 0,
      openInterest: p.openInterest || 0,
      impliedVolatility: p.impliedVolatility || 0,
      delta: p.delta || 0,
      gamma: p.gamma || 0,
      theta: p.theta || 0,
      vega: p.vega || 0,
      rho: p.rho || 0,
    }));

    console.log(`[Ranking Job] Fetched ${calls.length} calls, ${puts.length} puts for ${symbol}`);

    if (calls.length === 0 && puts.length === 0) {
      return errorResponse(`No options data found for ${symbol}`, 404);
    }

    // Save options snapshots for historical tracking (non-blocking)
    const snapshotTime = new Date().toISOString();
    const allContracts = [...calls, ...puts];
    const snapshotRecords = allContracts.map(c => ({
      underlying_symbol_id: symbolId,
      contract_symbol: c.symbol,
      option_type: c.type === "call" ? "call" : "put",
      strike: c.strike,
      expiration: new Date(c.expiration * 1000).toISOString().split('T')[0],
      bid: c.bid,
      ask: c.ask,
      last: c.last,
      underlying_price: null, // Not available from Yahoo options endpoint
      volume: c.volume,
      open_interest: c.openInterest,
      delta: c.delta,
      gamma: c.gamma,
      theta: c.theta,
      vega: c.vega,
      rho: c.rho,
      iv: c.impliedVolatility,
      snapshot_time: snapshotTime,
    }));

    // Upsert snapshots in batches (don't fail ranking if this errors)
    const BATCH_SIZE = 500;
    let snapshotsSaved = 0;
    try {
      for (let i = 0; i < snapshotRecords.length; i += BATCH_SIZE) {
        const batch = snapshotRecords.slice(i, i + BATCH_SIZE);
        const { error: snapshotError } = await supabase
          .from("options_snapshots")
          .upsert(batch, {
            onConflict: "contract_symbol,snapshot_time",
          });

        if (snapshotError) {
          console.warn(`[Ranking Job] Snapshot batch ${i / BATCH_SIZE + 1} warning:`, snapshotError.message);
        } else {
          snapshotsSaved += batch.length;
        }
      }
      console.log(`[Ranking Job] Saved ${snapshotsSaved} snapshots for ${symbol}`);
    } catch (snapErr) {
      console.warn(`[Ranking Job] Snapshot save failed (non-fatal):`, snapErr);
    }

    // Rank the options
    const rankedOptions = rankOptions(calls, puts);
    console.log(`[Ranking Job] Ranked ${rankedOptions.length} options for ${symbol}`);

    if (rankedOptions.length === 0) {
      return jsonResponse({
        message: `No rankable options for ${symbol}`,
        symbol,
        ranksInserted: 0,
        durationMs: Date.now() - startTime,
      });
    }

    // Build records for upsert
    const runAt = new Date().toISOString();
    const records = rankedOptions.map(opt => ({
      underlying_symbol_id: symbolId,
      ranking_mode: "entry",
      contract_symbol: opt.contract_symbol,
      expiry: opt.expiry,
      strike: opt.strike,
      side: opt.side,
      ml_score: opt.ml_score,
      composite_rank: opt.composite_rank,
      momentum_score: opt.momentum_score,
      value_score: opt.value_score,
      greeks_score: opt.greeks_score,
      iv_rank: opt.iv_rank,
      spread_pct: opt.spread_pct,
      vol_oi_ratio: opt.vol_oi_ratio,
      delta: opt.delta,
      gamma: opt.gamma,
      theta: opt.theta,
      vega: opt.vega,
      rho: opt.rho,
      bid: opt.bid,
      ask: opt.ask,
      mark: opt.mark,
      last_price: opt.last_price,
      volume: opt.volume,
      open_interest: opt.open_interest,
      signal_discount: opt.signal_discount,
      signal_runner: opt.signal_runner,
      signal_greeks: opt.signal_greeks,
      signal_buy: opt.signal_buy,
      signals: opt.signals,
      run_at: runAt,
      liquidity_confidence: 1.0,
      implied_vol: null,
      relative_value_score: null,
      entry_difficulty_score: null,
      ranking_stability_score: null,
    }));

    // Upsert to options_ranks
    const { error: upsertError } = await supabase
      .from("options_ranks")
      .upsert(records, {
        onConflict: "underlying_symbol_id,ranking_mode,expiry,strike,side",
      });

    if (upsertError) {
      console.error(`[Ranking Job] Upsert error:`, upsertError);
      return errorResponse(`Failed to save rankings: ${upsertError.message}`, 500);
    }

    const durationMs = Date.now() - startTime;
    console.log(`[Ranking Job] Saved ${records.length} ranks for ${symbol} in ${durationMs}ms`);

    // Log top 3
    const top3 = rankedOptions.slice(0, 3);
    for (const opt of top3) {
      console.log(`  ${opt.contract_symbol}: rank=${opt.composite_rank.toFixed(1)}, signals=[${opt.signals}]`);
    }

    // Return response matching iOS TriggerRankingResponse struct
    return jsonResponse({
      message: `Ranking completed for ${symbol}`,
      symbol,
      jobId: `inline-${Date.now()}`, // No actual job ID since done inline
      estimatedCompletionSeconds: 0, // Already complete - no need to wait
      queuePosition: 0,
      ranksInserted: records.length,
      snapshotsSaved,
      durationMs,
      topRanks: top3.map(o => ({
        contract: o.contract_symbol,
        rank: Math.round(o.composite_rank * 10) / 10,
        signals: o.signals,
      })),
    });

  } catch (err) {
    console.error("[Ranking Job] Unexpected error:", err);
    return errorResponse(
      `Internal server error: ${err instanceof Error ? err.message : String(err)}`,
      500
    );
  }
});
