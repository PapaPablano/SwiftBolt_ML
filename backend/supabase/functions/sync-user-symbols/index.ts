import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.3";
import { corsHeaders, errorResponse, jsonResponse } from "../_shared/cors.ts";

interface SyncRequest {
  symbols: string[];
  source: 'watchlist' | 'recent_search' | 'chart_view';
  timeframes?: string[];
}

const DEFAULT_TIMEFRAMES = ['m15', 'h1', 'h4', 'd1', 'w1'];

Deno.serve(async (req) => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
    );

    const body: SyncRequest = await req.json();
    const { symbols, source, timeframes = DEFAULT_TIMEFRAMES } = body;

    if (!symbols || symbols.length === 0) {
      return errorResponse("No symbols provided", 400);
    }

    if (!['watchlist', 'recent_search', 'chart_view'].includes(source)) {
      return errorResponse("Invalid source. Must be: watchlist, recent_search, or chart_view", 400);
    }

    console.log(`[sync-user-symbols] Syncing ${symbols.length} symbols (${source})`);

    // Get or create symbol IDs from database
    console.log(`[sync-user-symbols] Looking up symbols:`, symbols);
    const symbolData: Array<{ id: string; ticker: string }> = [];
    
    for (const ticker of symbols) {
      // Try to find existing symbol
      const { data: existing, error: lookupError } = await supabase
        .from("symbols")
        .select("id, ticker")
        .eq("ticker", ticker)
        .single();

      if (lookupError && lookupError.code !== 'PGRST116') {
        // PGRST116 = not found, which is fine - we'll create it
        console.error(`[sync-user-symbols] Error looking up ${ticker}:`, lookupError);
        continue;
      }

      if (existing) {
        symbolData.push(existing);
        console.log(`[sync-user-symbols] Found existing symbol: ${ticker}`);
      } else {
        // Create new symbol
        const { data: newSymbol, error: createError } = await supabase
          .from("symbols")
          .insert({
            ticker: ticker,
            asset_type: 'stock',
            description: ticker
          })
          .select("id, ticker")
          .single();

        if (createError) {
          console.error(`[sync-user-symbols] Error creating symbol ${ticker}:`, createError);
          continue;
        }

        symbolData.push(newSymbol);
        console.log(`[sync-user-symbols] Created new symbol: ${ticker}`);
      }
    }

    console.log(`[sync-user-symbols] Symbol lookup/create result: ${symbolData.length} symbols ready`);

    if (symbolData.length === 0) {
      console.error("[sync-user-symbols] No symbols could be found or created for:", symbols);
      return errorResponse(`Failed to lookup or create symbols: ${symbols.join(', ')}`, 500);
    }

    // Determine priority based on source
    const priority = source === 'watchlist' ? 300 : source === 'chart_view' ? 200 : 100;

    let trackedCount = 0;
    let jobsCreated = 0;

    // Create job definitions directly (skip user_symbol_tracking for now - table may not exist)
    for (const symbol of symbolData) {
      trackedCount++;

      // Create/enable job definitions for these symbols across all timeframes
      for (const timeframe of timeframes) {
        const isIntraday = ['m15', 'h1', 'h4'].includes(timeframe);
        const jobType = isIntraday ? 'fetch_intraday' : 'fetch_historical';
        const windowDays = isIntraday
          ? (timeframe === 'm15' ? 30 : timeframe === 'h1' ? 90 : 365)
          : 730;

        const { error: upsertError } = await supabase
          .from("job_definitions")
          .upsert(
            {
              symbol: symbol.ticker,
              timeframe: timeframe,
              job_type: jobType,
              batch_version: 1,
              enabled: true,
              priority: priority,
              window_days: windowDays,
              updated_at: new Date().toISOString(),
            },
            {
              onConflict: 'symbol,timeframe,job_type,batch_version',
              ignoreDuplicates: false,
            }
          );

        if (upsertError) {
          console.error(`[sync-user-symbols] Error creating/updating job for ${symbol.ticker} ${timeframe}:`, upsertError);
          continue;
        }

        jobsCreated++;
      }
    }

    console.log(`[sync-user-symbols] Tracked ${trackedCount} symbols, created/updated ${jobsCreated} jobs`);

    return jsonResponse({
      success: true,
      symbols_tracked: trackedCount,
      symbols_requested: symbols.length,
      timeframes: timeframes.length,
      jobs_updated: jobsCreated,
      priority: priority,
      source: source
    });

  } catch (error) {
    console.error("[sync-user-symbols] Error:", error);
    const message = error instanceof Error ? error.message : String(error);
    return errorResponse(message || "Internal server error", 500);
  }
});
