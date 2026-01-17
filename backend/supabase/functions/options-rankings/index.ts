// options-rankings: Return ML-ranked option contracts for a symbol
// GET /options-rankings?symbol=AAPL&expiry=2024-01-19&side=call
//
// Returns top-ranked options from options_ranks table, sorted by ml_score.
// Optionally filter by expiry date and/or side (call/put).

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { handleCorsOptions, jsonResponse, errorResponse } from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";

// Response interface uses snake_case to match Swift CodingKeys
interface OptionRank {
  id: string;
  contract_symbol: string;
  expiry: string;
  strike: number;
  side: "call" | "put";
  ml_score: number;
  // Momentum Framework Scores (0-100)
  composite_rank?: number;
  momentum_score?: number;
  value_score?: number;
  greeks_score?: number;
  relative_value_score?: number;
  entry_difficulty_score?: number;
  ranking_stability_score?: number;
  ranking_mode?: string;
  // IV Metrics
  implied_vol?: number;
  iv_rank?: number;
  spread_pct?: number;
  // Greeks
  delta?: number;
  gamma?: number;
  theta?: number;
  vega?: number;
  rho?: number;
  // Volume/Liquidity
  open_interest?: number;
  volume?: number;
  vol_oi_ratio?: number;
  liquidity_confidence?: number;
  // Pricing
  bid?: number;
  ask?: number;
  mark?: number;
  last_price?: number;
  // Providers/history
  price_provider?: string;
  oi_provider?: string;
  history_samples?: number;
  history_avg_mark?: number;
  history_window_days?: number;
  // Signals
  signal_discount?: boolean;
  signal_runner?: boolean;
  signal_greeks?: boolean;
  signal_buy?: boolean;
  signals?: string;
  // 7-Day Underlying Metrics
  underlying_ret_7d?: number;
  underlying_vol_7d?: number;
  underlying_drawdown_7d?: number;
  underlying_gap_count?: number;
  // Meta
  run_at: string;
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

interface PriceHistoryRow {
  contract_symbol: string;
  mark: number | null;
}

type OptionRankRow = {
  id: string;
  contract_symbol: string | null;
  expiry: string;
  strike: number;
  side: "call" | "put";
  ml_score: number;
  composite_rank: number | null;
  momentum_score: number | null;
  value_score: number | null;
  greeks_score: number | null;
  relative_value_score: number | null;
  entry_difficulty_score: number | null;
  ranking_stability_score: number | null;
  ranking_mode: string | null;
  implied_vol: number | null;
  iv_rank: number | null;
  spread_pct: number | null;
  delta: number | null;
  gamma: number | null;
  theta: number | null;
  vega: number | null;
  rho: number | null;
  open_interest: number | null;
  volume: number | null;
  vol_oi_ratio: number | null;
  liquidity_confidence: number | null;
  bid: number | null;
  ask: number | null;
  mark: number | null;
  last_price: number | null;
  signal_discount: boolean | null;
  signal_runner: boolean | null;
  signal_greeks: boolean | null;
  signal_buy: boolean | null;
  signals: string | null;
  price_provider: string | null;
  oi_provider: string | null;
  // 7-Day Underlying Metrics
  underlying_ret_7d: number | null;
  underlying_vol_7d: number | null;
  underlying_drawdown_7d: number | null;
  underlying_gap_count: number | null;
  run_at: string;
};

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

    const { data: ranksData, error: ranksError } = await query.returns<OptionRankRow[]>();

    if (ranksError) {
      console.error("[Options Rankings] Database error:", ranksError);
      return errorResponse("Failed to fetch options rankings", 500);
    }

    // Build history lookup map for average mark over recent window
    const historyMap = new Map<string, { count: number; sum: number }>();
    const contractSymbols = (ranksData ?? [])
      .map((row) => row.contract_symbol)
      .filter((sym): sym is string => typeof sym === "string" && sym.length > 0);

    if (contractSymbols.length > 0) {
      const sinceIso = new Date(Date.now() - HISTORY_LOOKBACK_DAYS * 24 * 60 * 60 * 1000).toISOString();
      const { data: historyRows, error: historyError } = await supabase
        .from("options_price_history")
        .select("contract_symbol, mark")
        .in("contract_symbol", contractSymbols)
        .gte("snapshot_at", sinceIso)
        .returns<PriceHistoryRow[]>();

      if (historyError) {
        console.warn("[Options Rankings] History fetch warning:", historyError.message);
      } else {
        for (const row of historyRows ?? []) {
          const rawSymbol = row.contract_symbol;
          if (typeof rawSymbol !== "string") continue;
          const symbolKey = rawSymbol.toUpperCase();

          if (!historyMap.has(symbolKey)) {
            historyMap.set(symbolKey, { count: 0, sum: 0 });
          }

          const entry = historyMap.get(symbolKey)!;
          const markVal = row.mark;
          if (typeof markVal === "number" && !Number.isNaN(markVal)) {
            entry.sum += markVal;
            entry.count += 1;
          }
        }
      }
    }

    // Transform database rows to response format (snake_case for Swift CodingKeys)
    const ranks: OptionRank[] = (ranksData ?? []).map((row) => {
      const computedSymbol = row.contract_symbol || `${symbol}${new Date(row.expiry).toISOString().slice(2, 10).replace(/-/g, "")}${row.side === "call" ? "C" : "P"}${(row.strike * 1000).toString().padStart(8, "0")}`;
      const historyStats = computedSymbol ? historyMap.get(computedSymbol.toUpperCase()) : undefined;
      const historySamples = historyStats?.count ?? 0;

      return {
        id: row.id,
        contract_symbol: computedSymbol,
        expiry: row.expiry,
        strike: row.strike,
        side: row.side,
        ml_score: row.ml_score,
        // Momentum Framework Scores
        composite_rank: row.composite_rank ?? undefined,
        momentum_score: row.momentum_score ?? undefined,
        value_score: row.value_score ?? undefined,
        greeks_score: row.greeks_score ?? undefined,
        relative_value_score: row.relative_value_score ?? undefined,
        entry_difficulty_score: row.entry_difficulty_score ?? undefined,
        ranking_stability_score: row.ranking_stability_score ?? undefined,
        ranking_mode: row.ranking_mode ?? undefined,
        // IV Metrics
        implied_vol: row.implied_vol ?? undefined,
        iv_rank: row.iv_rank ?? undefined,
        spread_pct: row.spread_pct ?? undefined,
        // Greeks
        delta: row.delta ?? undefined,
        gamma: row.gamma ?? undefined,
        theta: row.theta ?? undefined,
        vega: row.vega ?? undefined,
        rho: row.rho ?? undefined,
        // Volume/Liquidity
        open_interest: row.open_interest ?? undefined,
        volume: row.volume ?? undefined,
        vol_oi_ratio: row.vol_oi_ratio ?? undefined,
        liquidity_confidence: row.liquidity_confidence ?? undefined,
        // Pricing
        bid: row.bid ?? undefined,
        ask: row.ask ?? undefined,
        mark: row.mark ?? undefined,
        last_price: row.last_price ?? undefined,
        price_provider: row.price_provider ?? PRICE_PROVIDER,
        oi_provider: row.oi_provider ?? OI_PROVIDER,
        history_samples: historySamples,
        history_avg_mark: historyStats && historyStats.count > 0 ? historyStats.sum / historyStats.count : undefined,
        history_window_days: historySamples > 0 ? HISTORY_LOOKBACK_DAYS : undefined,
        // Signals
        signal_discount: row.signal_discount ?? undefined,
        signal_runner: row.signal_runner ?? undefined,
        signal_greeks: row.signal_greeks ?? undefined,
        signal_buy: row.signal_buy ?? undefined,
        signals: row.signals ?? undefined,
        // 7-Day Underlying Metrics
        underlying_ret_7d: row.underlying_ret_7d ?? undefined,
        underlying_vol_7d: row.underlying_vol_7d ?? undefined,
        underlying_drawdown_7d: row.underlying_drawdown_7d ?? undefined,
        underlying_gap_count: row.underlying_gap_count ?? undefined,
        // Meta
        run_at: row.run_at,
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
