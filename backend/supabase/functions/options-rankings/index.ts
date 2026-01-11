// options-rankings: Return ML-ranked option contracts for a symbol
// GET /options-rankings?symbol=AAPL&expiry=2024-01-19&side=call
//
// Returns top-ranked options from options_ranks table, sorted by ml_score.
// Optionally filter by expiry date and/or side (call/put).

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { handleCorsOptions, jsonResponse, errorResponse } from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";

interface OptionRank {
  id: string;
  contractSymbol: string;
  expiry: string;
  strike: number;
  side: "call" | "put";
  mlScore: number;
  // Momentum Framework Scores (0-100)
  compositeRank?: number;
  momentumScore?: number;
  valueScore?: number;
  greeksScore?: number;
  relativeValueScore?: number;
  entryDifficultyScore?: number;
  rankingStabilityScore?: number;
  rankingMode?: string;
  // IV Metrics
  impliedVol?: number;
  ivRank?: number;
  spreadPct?: number;
  // Greeks
  delta?: number;
  gamma?: number;
  theta?: number;
  vega?: number;
  rho?: number;
  // Volume/Liquidity
  openInterest?: number;
  volume?: number;
  volOiRatio?: number;
  // Pricing
  bid?: number;
  ask?: number;
  mark?: number;
  lastPrice?: number;
  liquidityConfidence?: number;
  // Providers/history
  priceProvider?: string;
  oiProvider?: string;
  historySamples?: number;
  historyAvgMark?: number;
  historyWindowDays?: number;
  // Signals
  signalDiscount?: boolean;
  signalRunner?: boolean;
  signalGreeks?: boolean;
  signalBuy?: boolean;
  signals?: string;
  // Meta
  runAt: string;
}

interface OptionsRankingsResponse {
  symbol: string;
  totalRanks: number;
  ranks: OptionRank[];
  filters: {
    expiry?: string;
    side?: "call" | "put";
  };
}

serve(async (req: Request): Promise<Response> => {
  const HISTORY_LOOKBACK_DAYS = 30;
  const PRICE_PROVIDER = "alpaca";
  const OI_PROVIDER = Deno.env.get("TRADIER_API_KEY") ? "tradier" : "alpaca";
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return handleCorsOptions();
  }

  // Only allow GET requests
  if (req.method !== "GET") {
    return errorResponse("Method not allowed", 405);
  }

  try {
    // Parse query parameters
    const url = new URL(req.url);
    const symbol = url.searchParams.get("symbol")?.trim().toUpperCase();
    const expiryParam = url.searchParams.get("expiry");
    const sideParam = url.searchParams.get("side")?.toLowerCase();
    const signalParam = url.searchParams.get("signal")?.toLowerCase(); // discount, runner, greeks, buy
    const modeParam = url.searchParams.get("mode")?.toLowerCase(); // entry, exit
    const sortBy = url.searchParams.get("sort") || "composite"; // composite, ml, momentum, value, greeks
    const limit = parseInt(url.searchParams.get("limit") || "50", 10);

    if (!symbol) {
      return errorResponse("Missing required parameter: symbol", 400);
    }

    // Validate side parameter
    if (sideParam && sideParam !== "call" && sideParam !== "put") {
      return errorResponse("Invalid side parameter (must be 'call' or 'put')", 400);
    }

    // Validate mode parameter
    if (modeParam && modeParam !== "entry" && modeParam !== "exit") {
      return errorResponse("Invalid mode parameter (must be 'entry' or 'exit')", 400);
    }

    // Validate signal parameter
    const validSignals = ["discount", "runner", "greeks", "buy"];
    if (signalParam && !validSignals.includes(signalParam)) {
      return errorResponse(`Invalid signal parameter (must be one of: ${validSignals.join(", ")})`, 400);
    }

    const supabase = getSupabaseClient();

    // Look up symbol to get symbol_id
    const { data: symbolData, error: symbolError } = await supabase
      .from("symbols")
      .select("id")
      .eq("ticker", symbol)
      .single();

    if (symbolError || !symbolData) {
      return errorResponse(`Symbol not found: ${symbol}`, 404);
    }

    const symbolId = symbolData.id;

    // Get today's date in YYYY-MM-DD format for filtering expired options
    const today = new Date().toISOString().split('T')[0];

    // Determine sort column based on sortBy parameter
    const sortColumnMap: Record<string, string> = {
      composite: "composite_rank",
      ml: "ml_score",
      momentum: "momentum_score",
      value: "value_score",
      greeks: "greeks_score",
    };
    const sortColumn = sortColumnMap[sortBy] || "composite_rank";

    // Build query for options_ranks
    let query = supabase
      .from("options_ranks")
      .select("*")
      .eq("underlying_symbol_id", symbolId)
      .eq("ranking_mode", modeParam || "entry")
      .gte("expiry", today)  // Filter out expired options
      .order(sortColumn, { ascending: false, nullsFirst: false })
      .order("ml_score", { ascending: false, nullsFirst: false })
      .limit(limit);

    // Avoid returning legacy rows with NULL sort values when sorting by framework columns
    if (sortColumn !== "ml_score") {
      query = query.not(sortColumn, "is", null);
    }

    // Apply filters
    if (expiryParam) {
      query = query.eq("expiry", expiryParam);
    }

    if (sideParam) {
      query = query.eq("side", sideParam);
    }

    // Apply signal filter
    if (signalParam) {
      const signalColumnMap: Record<string, string> = {
        discount: "signal_discount",
        runner: "signal_runner",
        greeks: "signal_greeks",
        buy: "signal_buy",
      };
      const signalColumn = signalColumnMap[signalParam];
      if (signalColumn) {
        query = query.eq(signalColumn, true);
      }
    }

    const { data: ranksData, error: ranksError } = await query;

    if (ranksError) {
      console.error("[Options Rankings] Database error:", ranksError);
      return errorResponse("Failed to fetch options rankings", 500);
    }

    // Build history lookup map for average mark over recent window
    const historyMap = new Map<string, { count: number; sum: number }>();
    const contractSymbols = (ranksData || [])
      .map((row: any) => row.contract_symbol)
      .filter((sym: string | null | undefined) => !!sym);

    if (contractSymbols.length > 0) {
      const sinceIso = new Date(Date.now() - HISTORY_LOOKBACK_DAYS * 24 * 60 * 60 * 1000).toISOString();
      const { data: historyRows, error: historyError } = await supabase
        .from("options_price_history")
        .select("contract_symbol, mark")
        .in("contract_symbol", contractSymbols)
        .gte("snapshot_at", sinceIso);

      if (historyError) {
        console.warn("[Options Rankings] History fetch warning:", historyError.message);
      } else {
        for (const row of historyRows || []) {
          const rawSymbol = (row as any).contract_symbol;
          if (typeof rawSymbol !== "string") continue;
          const symbolKey = rawSymbol.toUpperCase();
          const entry = historyMap.get(symbolKey) || { count: 0, sum: 0 };
          const markVal = Number((row as any).mark);
          if (!Number.isNaN(markVal)) {
            entry.sum += markVal;
            entry.count += 1;
          }
          historyMap.set(symbolKey, entry);
        }
      }
    }

    // Transform database rows to response format
    const ranks: OptionRank[] = (ranksData || []).map((row: any) => {
      const computedSymbol = row.contract_symbol || `${symbol}${new Date(row.expiry).toISOString().slice(2, 10).replace(/-/g, '')}${row.side === 'call' ? 'C' : 'P'}${(row.strike * 1000).toString().padStart(8, '0')}`;
      const historyStats = computedSymbol ? historyMap.get(computedSymbol.toUpperCase()) : undefined;
      const historySamples = historyStats?.count ?? 0;

      return {
        id: row.id,
        contractSymbol: computedSymbol,
        expiry: row.expiry,
        strike: row.strike,
        side: row.side,
        mlScore: row.ml_score,
        // Momentum Framework Scores
        compositeRank: row.composite_rank,
        momentumScore: row.momentum_score,
        valueScore: row.value_score,
        greeksScore: row.greeks_score,
        relativeValueScore: row.relative_value_score,
        entryDifficultyScore: row.entry_difficulty_score,
        rankingStabilityScore: row.ranking_stability_score,
        rankingMode: row.ranking_mode,
        // IV Metrics
        impliedVol: row.implied_vol,
        ivRank: row.iv_rank,
        spreadPct: row.spread_pct,
        // Greeks
        delta: row.delta,
        gamma: row.gamma,
        theta: row.theta,
        vega: row.vega,
        rho: row.rho,
        // Volume/Liquidity
        openInterest: row.open_interest,
        volume: row.volume,
        volOiRatio: row.vol_oi_ratio,
        liquidityConfidence: row.liquidity_confidence,
        // Pricing
        bid: row.bid,
        ask: row.ask,
        mark: row.mark,
        lastPrice: row.last_price,
        priceProvider: PRICE_PROVIDER,
        oiProvider: OI_PROVIDER,
        historySamples: historySamples,
        historyAvgMark: historyStats && historyStats.count > 0 ? historyStats.sum / historyStats.count : undefined,
        historyWindowDays: historySamples > 0 ? HISTORY_LOOKBACK_DAYS : undefined,
        // Signals
        signalDiscount: row.signal_discount,
        signalRunner: row.signal_runner,
        signalGreeks: row.signal_greeks,
        signalBuy: row.signal_buy,
        signals: row.signals,
        // Meta
        runAt: row.run_at,
      };
    });

    const response: OptionsRankingsResponse = {
      symbol,
      totalRanks: ranks.length,
      ranks,
      filters: {
        ...(expiryParam && { expiry: expiryParam }),
        ...(sideParam && { side: sideParam as "call" | "put" }),
      },
    };

    console.log(
      `[Options Rankings] Returned ${ranks.length} ranked contracts for ${symbol}` +
        (expiryParam ? ` (expiry: ${expiryParam})` : "") +
        (sideParam ? ` (side: ${sideParam})` : "")
    );

    return jsonResponse(response);
  } catch (err) {
    console.error("[Options Rankings] Unexpected error:", err);
    return errorResponse(
      `Internal server error: ${err instanceof Error ? err.message : String(err)}`,
      500
    );
  }
});
