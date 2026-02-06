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
  ranking_mode?: string;
  // Ranking scores (0-100)
  composite_rank?: number;         // MONITOR mode
  entry_rank?: number;             // ENTRY mode
  exit_rank?: number;              // EXIT mode
  // MONITOR mode component scores
  momentum_score?: number;
  value_score?: number;
  greeks_score?: number;
  // ENTRY mode component scores
  entry_value_score?: number;
  catalyst_score?: number;
  // EXIT mode component scores
  profit_protection_score?: number;
  deterioration_score?: number;
  time_urgency_score?: number;
  // Additional scores
  relative_value_score?: number;
  entry_difficulty_score?: number;
  ranking_stability_score?: number;
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

interface SymbolFeatures {
  expected_move_near_dollar?: number;
  expected_move_near_pct?: number;
  expected_move_far_dollar?: number;
  expected_move_far_pct?: number;
  atm_iv_near?: number;
  atm_iv_far?: number;
  forward_vol?: number;
  term_structure_regime?: string;
  low_confidence?: boolean;
  vrp?: number;
}

interface OptionsRankingsResponse {
  symbol: string;
  totalRanks: number;
  ranks: OptionRank[];
  mode?: string;
  filters: {
    expiry?: string;
    side?: "call" | "put";
  };
  symbolFeatures?: SymbolFeatures;
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
  ranking_mode: string | null;
  composite_rank: number | null;
  entry_rank: number | null;
  exit_rank: number | null;
  momentum_score: number | null;
  value_score: number | null;
  greeks_score: number | null;
  entry_value_score: number | null;
  catalyst_score: number | null;
  profit_protection_score: number | null;
  deterioration_score: number | null;
  time_urgency_score: number | null;
  relative_value_score: number | null;
  entry_difficulty_score: number | null;
  ranking_stability_score: number | null;
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
    const strategyIntentParam = url.searchParams.get("strategy_intent")?.toLowerCase(); // long_premium, short_premium
    const sortBy = url.searchParams.get("sort") || "composite"; // composite, ml, momentum, value, greeks
    const limit = parseInt(url.searchParams.get("limit") || "50", 10);

    if (!symbol) {
      return errorResponse("Missing required parameter: symbol", 400);
    }

    // Validate side parameter
    if (sideParam && sideParam !== "call" && sideParam !== "put") {
      return errorResponse("Invalid side parameter (must be 'call' or 'put')", 400);
    }

    // Validate mode parameter (default to "monitor" for backward compatibility)
    const mode = modeParam || "monitor";
    console.log(`[Options Rankings] Processing request: symbol=${symbol}, mode=${mode}, sortBy=${sortBy}, limit=${limit}`);
    
    if (mode !== "entry" && mode !== "exit" && mode !== "monitor") {
      return errorResponse("Invalid mode parameter (must be 'entry', 'exit', or 'monitor')", 400);
    }

    if (strategyIntentParam && strategyIntentParam !== "long_premium" && strategyIntentParam !== "short_premium") {
      return errorResponse("Invalid strategy_intent parameter (must be 'long_premium' or 'short_premium')", 400);
    }

    // Validate signal parameter
    const validSignals = ["discount", "runner", "greeks", "buy"];
    if (signalParam && !validSignals.includes(signalParam)) {
      return errorResponse(`Invalid signal parameter (must be one of: ${validSignals.join(", ")})`, 400);
    }

    console.log(`[Options Rankings] Creating Supabase client...`);
    const supabase = getSupabaseClient();

    // Look up symbol to get symbol_id
    console.log(`[Options Rankings] Looking up symbol: ${symbol}`);
    const { data: symbolData, error: symbolError} = await supabase
      .from("symbols")
      .select("id")
      .eq("ticker", symbol)
      .single();
    
    console.log(`[Options Rankings] Symbol lookup result:`, { symbolData, symbolError });

    if (symbolError || !symbolData) {
      return errorResponse(`Symbol not found: ${symbol}`, 404);
    }

    const symbolId = symbolData.id;
    console.log(`[Options Rankings] Symbol ID: ${symbolId}`);

    const strategyIntent = strategyIntentParam || "long_premium";
    console.log(`[Options Rankings] Fetching latest run_at for mode=${mode}, strategy_intent=${strategyIntent}...`);
    let latestRunQuery = supabase
      .from("options_ranks")
      .select("run_at")
      .eq("underlying_symbol_id", symbolId)
      .eq("ranking_mode", mode);
    if (strategyIntent === "long_premium") {
      latestRunQuery = latestRunQuery.or("strategy_intent.eq.long_premium,strategy_intent.is.null");
    } else {
      latestRunQuery = latestRunQuery.eq("strategy_intent", strategyIntent);
    }
    const { data: latestRunRows, error: latestRunError } = await latestRunQuery
      .order("run_at", { ascending: false })
      .limit(1)
      .returns<{ run_at: string }[]>();

    if (latestRunError) {
      console.error("[Options Rankings] Failed to fetch latest run_at:", latestRunError);
      return errorResponse(`Database error fetching run_at: ${latestRunError.message}`, 500);
    }
    
    console.log(`[Options Rankings] Latest run_at:`, latestRunRows?.[0]);

    const latestRunAt = latestRunRows?.[0]?.run_at;
    const runWindowHours = 72;
    const runWindowStart = latestRunAt
      ? new Date(new Date(latestRunAt).getTime() - runWindowHours * 60 * 60 * 1000).toISOString()
      : undefined;

    // Get today's date in YYYY-MM-DD format for filtering expired options
    const today = new Date().toISOString().split('T')[0];

    // Determine sort column based on sortBy parameter and mode
    let sortColumn: string;
    if (sortBy === "composite" || !sortBy) {
      // Default sorting based on mode
      switch (mode) {
        case "entry":
          sortColumn = "entry_rank";
          break;
        case "exit":
          sortColumn = "exit_rank";
          break;
        default:
          sortColumn = "composite_rank";
      }
    } else {
      // Explicit sort parameter
      const sortColumnMap: Record<string, string> = {
        composite: "composite_rank",
        entry: "entry_rank",
        exit: "exit_rank",
        ml: "ml_score",
        momentum: "momentum_score",
        value: "value_score",
        greeks: "greeks_score",
        catalyst: "catalyst_score",
        profit: "profit_protection_score",
      };
      sortColumn = sortColumnMap[sortBy] || "composite_rank";
    }

    // Build query for options_ranks
    console.log(`[Options Rankings] Building query with sortColumn=${sortColumn}, today=${today}, runWindowStart=${runWindowStart}`);
    
    let query = supabase
      .from("options_ranks")
      .select("*")
      .eq("underlying_symbol_id", symbolId)
      .eq("ranking_mode", mode);
    // Filter by strategy_intent; for long_premium also include legacy NULL rows
    if (strategyIntent === "long_premium") {
      query = query.or("strategy_intent.eq.long_premium,strategy_intent.is.null");
    } else {
      query = query.eq("strategy_intent", strategyIntent);
    }
    query = query
      .gte("expiry", today)  // Filter out expired options
      .order(sortColumn, { ascending: false, nullsFirst: false })
      .order("ml_score", { ascending: false, nullsFirst: false })
      .limit(limit);

    // Avoid returning legacy rows with NULL sort values when sorting by framework columns
    if (sortColumn !== "ml_score") {
      query = query.not(sortColumn, "is", null);
    }

    if (runWindowStart) {
      query = query.gte("run_at", runWindowStart);
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

    console.log(`[Options Rankings] Executing main query...`);
    const { data: ranksData, error: ranksError } = await query.returns<OptionRankRow[]>();

    if (ranksError) {
      console.error("[Options Rankings] Database error:", ranksError);
      return errorResponse(`Database error: ${ranksError.message}`, 500);
    }
    
    console.log(`[Options Rankings] Query returned ${ranksData?.length || 0} rows`);

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

    // Fetch latest symbolFeatures from options_feature_snapshots
    let symbolFeatures: SymbolFeatures | undefined;
    try {
      const { data: snapshotRows } = await supabase
        .from("options_feature_snapshots")
        .select("atm_iv_near, atm_iv_far, forward_vol, term_structure_regime, low_confidence, expected_move_near_pct, expected_move_far_pct, expected_move_near_dollar, expected_move_far_dollar, vrp")
        .eq("symbol", symbol)
        .order("ts_utc", { ascending: false })
        .limit(1)
        .returns<{ atm_iv_near: number | null; atm_iv_far: number | null; forward_vol: number | null; term_structure_regime: string | null; low_confidence: boolean | null; expected_move_near_pct: number | null; expected_move_far_pct: number | null; expected_move_near_dollar: number | null; expected_move_far_dollar: number | null; vrp: number | null }[]>();
      if (snapshotRows && snapshotRows.length > 0) {
        const row = snapshotRows[0];
        symbolFeatures = {
          atm_iv_near: row.atm_iv_near ?? undefined,
          atm_iv_far: row.atm_iv_far ?? undefined,
          forward_vol: row.forward_vol ?? undefined,
          term_structure_regime: row.term_structure_regime ?? undefined,
          low_confidence: row.low_confidence ?? undefined,
          expected_move_near_pct: row.expected_move_near_pct ?? undefined,
          expected_move_far_pct: row.expected_move_far_pct ?? undefined,
          expected_move_near_dollar: row.expected_move_near_dollar ?? undefined,
          expected_move_far_dollar: row.expected_move_far_dollar ?? undefined,
          vrp: row.vrp ?? undefined,
        };
      }
    } catch (snapErr) {
      console.warn("[Options Rankings] Could not fetch symbolFeatures:", snapErr);
    }

    const response: OptionsRankingsResponse = {
      symbol,
      totalRanks: ranks.length,
      ranks,
      mode,
      filters: {
        ...(expiryParam && { expiry: expiryParam }),
        ...(sideParam && { side: sideParam as "call" | "put" }),
      },
      ...(symbolFeatures && { symbolFeatures }),
    };

    console.log(
      `[Options Rankings] Returned ${ranks.length} ranked contracts for ${symbol}` +
        ` (mode: ${mode})` +
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
