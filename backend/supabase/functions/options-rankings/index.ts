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
  impliedVol?: number;
  delta?: number;
  gamma?: number;
  theta?: number;
  vega?: number;
  rho?: number;
  openInterest?: number;
  volume?: number;
  bid?: number;
  ask?: number;
  mark?: number;
  lastPrice?: number;
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
    const limit = parseInt(url.searchParams.get("limit") || "50", 10);

    if (!symbol) {
      return errorResponse("Missing required parameter: symbol", 400);
    }

    // Validate side parameter
    if (sideParam && sideParam !== "call" && sideParam !== "put") {
      return errorResponse("Invalid side parameter (must be 'call' or 'put')", 400);
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

    // Build query for options_ranks
    let query = supabase
      .from("options_ranks")
      .select("*")
      .eq("underlying_symbol_id", symbolId)
      .order("ml_score", { ascending: false })
      .limit(limit);

    // Apply filters
    if (expiryParam) {
      query = query.eq("expiry", expiryParam);
    }

    if (sideParam) {
      query = query.eq("side", sideParam);
    }

    const { data: ranksData, error: ranksError } = await query;

    if (ranksError) {
      console.error("[Options Rankings] Database error:", ranksError);
      return errorResponse("Failed to fetch options rankings", 500);
    }

    // Transform database rows to response format
    const ranks: OptionRank[] = (ranksData || []).map((row: any) => ({
      id: row.id,
      contractSymbol: row.contract_symbol || `${symbol}${new Date(row.expiry).toISOString().slice(2, 10).replace(/-/g, '')}${row.side === 'call' ? 'C' : 'P'}${(row.strike * 1000).toString().padStart(8, '0')}`,
      expiry: row.expiry,
      strike: row.strike,
      side: row.side,
      mlScore: row.ml_score,
      impliedVol: row.implied_vol,
      delta: row.delta,
      gamma: row.gamma,
      theta: row.theta,
      vega: row.vega,
      rho: row.rho,
      openInterest: row.open_interest,
      volume: row.volume,
      bid: row.bid,
      ask: row.ask,
      mark: row.mark,
      lastPrice: row.last_price,
      runAt: row.run_at,
    }));

    const response: OptionsRankingsResponse = {
      symbol,
      totalRanks: ranks.length,
      ranks,
      filters: {
        ...(expiryParam && { expiry: expiryParam }),
        ...(sideParam && { side: sideParam as "call" | "put" }),
      },
    };

    logger.info(
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
