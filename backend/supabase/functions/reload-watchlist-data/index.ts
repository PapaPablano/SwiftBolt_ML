/**
 * Reload Watchlist Data Edge Function
 * 
 * Triggers fresh data loads for all watchlist symbols using Alpaca-only strategy.
 * This replaces spec8 orchestrator with direct symbol-init calls.
 * 
 * POST /reload-watchlist-data
 * {
 *   "forceRefresh": true,  // Optional: force reload even if data exists
 *   "timeframes": ["d1", "h1", "m15"]  // Optional: specific timeframes
 * }
 */

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

interface ReloadRequest {
  forceRefresh?: boolean;
  timeframes?: string[];  // Default: all 5 timeframes (m15, h1, h4, d1, w1)
  symbols?: string[];     // Optional: reload specific symbols only
}

interface ReloadResult {
  symbol: string;
  status: "success" | "error" | "skipped";
  message?: string;
  barsLoaded?: {
    m15?: number;
    h1?: number;
    h4?: number;
    d1?: number;
    w1?: number;
  };
}

type WatchlistItemRow = {
  symbol_id: string;
  symbols: Array<{
    ticker: string;
    id: string;
  }>;
};

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
    );

    const body: ReloadRequest = await req.json().catch(() => ({}));
    const forceRefresh = body.forceRefresh ?? false;
    // Multi-timeframe rule: Always process all 5 timeframes together
    const timeframes = body.timeframes ?? ["m15", "h1", "h4", "d1", "w1"];
    const specificSymbols = body.symbols;

    console.log(`[reload-watchlist-data] Starting reload...`);
    console.log(`[reload-watchlist-data] Force refresh: ${forceRefresh}`);
    console.log(`[reload-watchlist-data] Timeframes: ${timeframes.join(", ")}`);

    // Get all watchlist symbols
    let query = supabase
      .from("watchlist_items")
      .select(`
        symbol_id,
        symbols!inner(ticker, id)
      `);

    if (specificSymbols && specificSymbols.length > 0) {
      query = query.in("symbols.ticker", specificSymbols.map(s => s.toUpperCase()));
    }

    const { data: watchlistItems, error: watchlistError } = await query;

    if (watchlistError) {
      throw new Error(`Failed to fetch watchlist: ${watchlistError.message}`);
    }

    if (!watchlistItems || watchlistItems.length === 0) {
      return new Response(
        JSON.stringify({
          success: true,
          message: "No symbols in watchlist",
          results: [],
        }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // Get unique symbols
    const symbols = Array.from(
      new Map(
        (watchlistItems as WatchlistItemRow[])
          .map((item) => item.symbols?.[0])
          .filter((s): s is { ticker: string; id: string } => !!s && typeof s.ticker === "string")
          .map((sym) => [sym.ticker, { ticker: sym.ticker, id: sym.id }])
      ).values()
    );

    console.log(`[reload-watchlist-data] Found ${symbols.length} unique symbols`);

    const results: ReloadResult[] = [];
    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const gatewayKey =
      Deno.env.get("SB_GATEWAY_KEY") ??
      Deno.env.get("ANON_KEY") ??
      Deno.env.get("SUPABASE_ANON_KEY") ??
      serviceKey;

    // Process each symbol
    for (const symbol of symbols) {
      console.log(`[reload-watchlist-data] Processing ${symbol.ticker}...`);

      try {
        // Call symbol-init to trigger data load
        const initResponse = await fetch(`${supabaseUrl}/functions/v1/symbol-init`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${serviceKey}`,
            apikey: gatewayKey,
          },
          body: JSON.stringify({
            symbol: symbol.ticker,
            forceRefresh: forceRefresh,
          }),
        });

        if (!initResponse.ok) {
          const errorText = await initResponse.text();
          results.push({
            symbol: symbol.ticker,
            status: "error",
            message: `symbol-init failed: ${errorText}`,
          });
          continue;
        }

        const initResult = await initResponse.json();
        console.log(`[reload-watchlist-data] ${symbol.ticker} init result:`, initResult);

        // Now fetch data for each timeframe using chart-data-v2
        const barsLoaded: { d1?: number; h1?: number; m15?: number } = {};

        for (const timeframe of timeframes) {
          try {
            const chartResponse = await fetch(`${supabaseUrl}/functions/v1/chart-data-v2`, {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${serviceKey}`,
                apikey: gatewayKey,
              },
              body: JSON.stringify({
                symbol: symbol.ticker,
                timeframe: timeframe,
                days: timeframe === "d1" || timeframe === "w1" ? 730 : 60,  // 2 years for daily/weekly, 60 days for intraday
                includeForecast: true,
                forecastDays: 10,
              }),
            });

            if (chartResponse.ok) {
              const chartData = await chartResponse.json();
              const totalBars =
                (chartData.layers?.historical?.count || 0) +
                (chartData.layers?.intraday?.count || 0);
              barsLoaded[timeframe as keyof typeof barsLoaded] = totalBars;
              console.log(`[reload-watchlist-data] ${symbol.ticker} ${timeframe}: ${totalBars} bars`);
            }
          } catch (chartError: unknown) {
            console.error(`[reload-watchlist-data] Chart fetch error for ${symbol.ticker} ${timeframe}:`, chartError);
          }
        }

        results.push({
          symbol: symbol.ticker,
          status: "success",
          message: `Loaded data for ${timeframes.join(", ")}`,
          barsLoaded,
        });
      } catch (error: unknown) {
        console.error(`[reload-watchlist-data] Error processing ${symbol.ticker}:`, error);
        results.push({
          symbol: symbol.ticker,
          status: "error",
          message: getErrorMessage(error),
        });
      }

      // Small delay to avoid overwhelming the system
      await new Promise((resolve) => setTimeout(resolve, 100));
    }

    const successCount = results.filter((r) => r.status === "success").length;
    const errorCount = results.filter((r) => r.status === "error").length;

    console.log(`[reload-watchlist-data] Complete: ${successCount} success, ${errorCount} errors`);

    return new Response(
      JSON.stringify({
        success: true,
        message: `Reloaded ${successCount} of ${symbols.length} symbols`,
        summary: {
          total: symbols.length,
          success: successCount,
          errors: errorCount,
        },
        results,
      }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  } catch (error: unknown) {
    console.error("[reload-watchlist-data] Error:", error);
    return new Response(
      JSON.stringify({
        success: false,
        error: getErrorMessage(error) || "Internal server error",
      }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
