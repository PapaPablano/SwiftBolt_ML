// options-chain: Fetch options chain data for a symbol via ProviderRouter
// GET /options-chain?underlying=AAPL&expiration=1737072000 (optional expiration)
//
// Uses the unified ProviderRouter with rate limiting, caching, and fallback logic.
// DB persistence is used for long-term storage; ProviderRouter handles live fetching.

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import {
  errorResponse,
  handleCorsOptions,
  jsonResponse,
} from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";
import { getProviderRouter } from "../_shared/providers/factory.ts";

// Cache staleness threshold (15 minutes)
const CACHE_TTL_MS = 15 * 60 * 1000;

interface OptionsChainResponse {
  underlying: string;
  timestamp: number;
  expirations: number[];
  calls: OptionContractResponse[];
  puts: OptionContractResponse[];
}

interface OptionContractResponse {
  symbol: string;
  underlying: string;
  strike: number;
  expiration: number;
  type: "call" | "put";
  bid: number;
  ask: number;
  last: number;
  mark: number;
  volume: number;
  openInterest: number;
  delta?: number;
  gamma?: number;
  theta?: number;
  vega?: number;
  rho?: number;
  impliedVolatility?: number;
  lastTradeTime?: number;
  changePercent?: number;
  change?: number;
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
    const underlying = url.searchParams.get("underlying")?.trim().toUpperCase();
    const expirationParam = url.searchParams.get("expiration");

    if (!underlying) {
      return errorResponse("Missing required parameter: underlying", 400);
    }

    const supabase = getSupabaseClient();
    let expiration: number | undefined;

    if (expirationParam) {
      expiration = parseInt(expirationParam, 10);
      if (isNaN(expiration)) {
        return errorResponse("Invalid expiration timestamp", 400);
      }
    }

    // Look up symbol to get symbol_id for caching
    const { data: symbolData } = await supabase
      .from("symbols")
      .select("id")
      .eq("ticker", underlying)
      .single();

    const symbolId = symbolData?.id || null;

    // Check cache if we have a symbol_id
    if (symbolId) {
      const _cacheThreshold = new Date(Date.now() - CACHE_TTL_MS).toISOString();
      const _cacheKey = `${underlying}:${expiration || "all"}`;

      // For now, skip DB caching and fetch live data
      // In production, you'd want to cache options chain data in a table
    }

    const persistParam = url.searchParams.get("persist");
    const persistChains = persistParam !== "0" &&
      Deno.env.get("OPTIONS_CHAIN_PERSIST") !== "0";

    // Fetch fresh options chain via ProviderRouter
    console.log(
      `Fetching options chain for ${underlying}, expiration: ${
        expiration || "all"
      }`,
    );
    try {
      console.log("[Options Chain] Initializing provider router...");
      const router = getProviderRouter();
      console.log("[Options Chain] Router initialized successfully");
      console.log("[Options Chain] Calling router.getOptionsChain...");

      const optionsChain = await router.getOptionsChain({
        underlying,
        expiration,
      });

      console.log(
        `[Options Chain] Successfully fetched ${optionsChain.calls.length} calls and ${optionsChain.puts.length} puts`,
      );

      const response: OptionsChainResponse = {
        underlying: optionsChain.underlying,
        timestamp: optionsChain.timestamp,
        expirations: optionsChain.expirations,
        calls: optionsChain.calls.map((contract) => ({
          symbol: contract.symbol,
          underlying: contract.underlying,
          strike: contract.strike,
          expiration: contract.expiration,
          type: contract.type,
          bid: contract.bid,
          ask: contract.ask,
          last: contract.last,
          mark: contract.mark,
          volume: contract.volume,
          openInterest: contract.openInterest,
          delta: contract.delta,
          gamma: contract.gamma,
          theta: contract.theta,
          vega: contract.vega,
          rho: contract.rho,
          impliedVolatility: contract.impliedVolatility,
          lastTradeTime: contract.lastTradeTime,
          changePercent: contract.changePercent,
          change: contract.change,
        })),
        puts: optionsChain.puts.map((contract) => ({
          symbol: contract.symbol,
          underlying: contract.underlying,
          strike: contract.strike,
          expiration: contract.expiration,
          type: contract.type,
          bid: contract.bid,
          ask: contract.ask,
          last: contract.last,
          mark: contract.mark,
          volume: contract.volume,
          openInterest: contract.openInterest,
          delta: contract.delta,
          gamma: contract.gamma,
          theta: contract.theta,
          vega: contract.vega,
          rho: contract.rho,
          impliedVolatility: contract.impliedVolatility,
          lastTradeTime: contract.lastTradeTime,
          changePercent: contract.changePercent,
          change: contract.change,
        })),
      };

      if (persistChains && symbolId) {
        const snapshotDate = new Date().toISOString().split("T")[0];
        const toDate = (exp: number) =>
          new Date(exp * 1000).toISOString().split("T")[0];
        const buildRecord = (contract: OptionContractResponse) => ({
          underlying_symbol_id: symbolId,
          expiry: toDate(contract.expiration),
          strike: contract.strike,
          side: contract.type,
          bid: contract.bid,
          ask: contract.ask,
          mark: contract.mark,
          last_price: contract.last,
          volume: contract.volume,
          open_interest: contract.openInterest,
          implied_vol: contract.impliedVolatility,
          delta: contract.delta,
          gamma: contract.gamma,
          theta: contract.theta,
          vega: contract.vega,
          rho: contract.rho,
          snapshot_date: snapshotDate,
        });

        const records = [
          ...response.calls.map(buildRecord),
          ...response.puts.map(buildRecord),
        ];

        for (let i = 0; i < records.length; i += 500) {
          const chunk = records.slice(i, i + 500);
          const { error } = await supabase
            .from("options_chain_snapshots")
            .upsert(chunk, {
              onConflict:
                "underlying_symbol_id,expiry,strike,side,snapshot_date",
            });
          if (error) {
            console.error("[Options Chain] Snapshot upsert error:", error);
            break;
          }
        }
      }

      return jsonResponse(response);
    } catch (fetchError) {
      console.error("[Options Chain] Provider router fetch error:", fetchError);
      console.error(
        "[Options Chain] Error stack:",
        fetchError instanceof Error ? fetchError.stack : "No stack trace",
      );
      console.error(
        "[Options Chain] Error message:",
        fetchError instanceof Error ? fetchError.message : String(fetchError),
      );
      return errorResponse(
        `Failed to fetch options chain: ${
          fetchError instanceof Error ? fetchError.message : String(fetchError)
        }`,
        502,
      );
    }
  } catch (err) {
    console.error("[Options Chain] Unexpected error:", err);
    console.error(
      "[Options Chain] Error stack:",
      err instanceof Error ? err.stack : "No stack trace",
    );
    return errorResponse(
      `Internal server error: ${
        err instanceof Error ? err.message : String(err)
      }`,
      500,
    );
  }
});
