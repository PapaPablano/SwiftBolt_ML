import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.3";
import { corsHeaders, errorResponse, jsonResponse } from "../_shared/cors.ts";

interface SyncRequest {
  symbols: string[];
  source: 'watchlist' | 'recent_search' | 'chart_view';
  timeframes?: string[];
}

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

    // Get user from JWT
    const authHeader = req.headers.get("Authorization");
    const token = authHeader?.replace("Bearer ", "");
    
    if (!token) {
      return errorResponse("Missing authorization token", 401);
    }

    const { data: { user }, error: authError } = await supabase.auth.getUser(token);

    if (authError || !user) {
      console.error("[sync-user-symbols] Auth error:", authError);
      return errorResponse("Unauthorized", 401);
    }

    const body: SyncRequest = await req.json();
    const { symbols, source, timeframes = ['m15', 'h1', 'h4'] } = body;

    if (!symbols || symbols.length === 0) {
      return errorResponse("No symbols provided", 400);
    }

    if (!['watchlist', 'recent_search', 'chart_view'].includes(source)) {
      return errorResponse("Invalid source. Must be: watchlist, recent_search, or chart_view", 400);
    }

    console.log(`[sync-user-symbols] User ${user.id} syncing ${symbols.length} symbols (${source})`);

    // Get symbol IDs from database
    const { data: symbolData, error: symbolError } = await supabase
      .from("symbols")
      .select("id, ticker")
      .in("ticker", symbols);

    if (symbolError) {
      console.error("[sync-user-symbols] Symbol lookup error:", symbolError);
      return errorResponse(`Failed to lookup symbols: ${symbolError.message}`, 500);
    }

    if (!symbolData || symbolData.length === 0) {
      return errorResponse("No valid symbols found", 404);
    }

    // Determine priority based on source
    const priority = source === 'watchlist' ? 300 : source === 'chart_view' ? 200 : 100;

    let trackedCount = 0;
    let jobsCreated = 0;

    // Track user's symbol interest
    for (const symbol of symbolData) {
      const { error: trackError } = await supabase
        .from("user_symbol_tracking")
        .upsert({
          user_id: user.id,
          symbol_id: symbol.id,
          source: source,
          priority: priority,
          updated_at: new Date().toISOString()
        }, {
          onConflict: 'user_id,symbol_id,source'
        });

      if (trackError) {
        console.error(`[sync-user-symbols] Error tracking ${symbol.ticker}:`, trackError);
        continue;
      }

      trackedCount++;

      // Create/enable job definitions for these symbols across all timeframes
      for (const timeframe of timeframes) {
        const windowDays = timeframe === 'm15' ? 30 : timeframe === 'h1' ? 90 : 365;
        
        const { error: jobError } = await supabase
          .from("job_definitions")
          .upsert({
            symbol: symbol.ticker,
            timeframe: timeframe,
            job_type: 'fetch_intraday',
            enabled: true,
            priority: priority,
            window_days: windowDays
          }, {
            onConflict: 'symbol,timeframe,job_type'
          });

        if (jobError) {
          console.error(`[sync-user-symbols] Error creating job for ${symbol.ticker} ${timeframe}:`, jobError);
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
    return errorResponse(error.message || "Internal server error", 500);
  }
});
