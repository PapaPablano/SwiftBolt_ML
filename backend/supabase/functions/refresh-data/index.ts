// refresh-data: Coordinated data refresh for a symbol
// POST /refresh-data { symbol: "AAPL", refreshML: true, refreshOptions: true }
//
// This function:
// 1. Fetches only NEW bars since last update (incremental)
// 2. Queues ML forecast job if requested
// 3. Queues options ranking job if requested
// 4. Returns status for UI coordination

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
};

interface RefreshRequest {
  symbol: string;
  refreshML?: boolean;      // Queue ML forecast job (default: true)
  refreshOptions?: boolean; // Queue options ranking job (default: false)
  timeframes?: string[];    // Timeframes to refresh (default: ["d1"])
}

interface RefreshResult {
  symbol: string;
  success: boolean;
  dataRefresh: {
    timeframe: string;
    existingBars: number;
    newBars: number;
    latestTimestamp: string | null;
  }[];
  mlJobQueued: boolean;
  optionsJobQueued: boolean;
  errors: string[];
  message: string;
}

// Provider router for fetching fresh data
import { getProviderRouter } from "../_shared/providers/factory.ts";
import type { Timeframe } from "../_shared/providers/types.ts";

serve(async (req: Request): Promise<Response> => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), {
      status: 405,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  try {
    const supabase = createClient(
      Deno.env.get("SUPABASE_URL") ?? "",
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? ""
    );

    const body: RefreshRequest = await req.json();
    const symbol = body.symbol?.toUpperCase();
    const refreshML = body.refreshML !== false; // Default true
    const refreshOptions = body.refreshOptions === true; // Default false
    const timeframes = body.timeframes || ["d1", "h1", "h4", "m15"];

    if (!symbol) {
      return new Response(JSON.stringify({ error: "Symbol required" }), {
        status: 400,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    console.log(`[refresh-data] Starting refresh for ${symbol} (ML=${refreshML}, Options=${refreshOptions})`);

    const result: RefreshResult = {
      symbol,
      success: false,
      dataRefresh: [],
      mlJobQueued: false,
      optionsJobQueued: false,
      errors: [],
      message: "",
    };

    // Step 1: Get symbol record
    const { data: symbolRecord, error: symbolError } = await supabase
      .from("symbols")
      .select("id, ticker, asset_type")
      .eq("ticker", symbol)
      .single();

    if (symbolError || !symbolRecord) {
      result.errors.push(`Symbol not found: ${symbol}`);
      result.message = "Symbol not found in database";
      return new Response(JSON.stringify(result), {
        status: 404,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const symbolId = symbolRecord.id;

    // Step 2: For each timeframe, fetch incremental data
    const router = getProviderRouter();

    for (const timeframe of timeframes) {
      try {
        // Get the latest bar timestamp for this symbol/timeframe
        const { data: latestBar } = await supabase
          .from("ohlc_bars")
          .select("ts")
          .eq("symbol_id", symbolId)
          .eq("timeframe", timeframe)
          .order("ts", { ascending: false })
          .limit(1)
          .single();

        const latestTs = latestBar?.ts ? new Date(latestBar.ts) : null;
        
        // Count existing bars
        const { count: existingCount } = await supabase
          .from("ohlc_bars")
          .select("*", { count: "exact", head: true })
          .eq("symbol_id", symbolId)
          .eq("timeframe", timeframe);

        const tfResult = {
          timeframe,
          existingBars: existingCount || 0,
          newBars: 0,
          latestTimestamp: latestTs?.toISOString() || null,
        };

        // Calculate time range for incremental fetch
        const now = Math.floor(Date.now() / 1000);
        let fromTs: number;

        if (latestTs) {
          // Start from the day after the latest bar (to avoid duplicates)
          fromTs = Math.floor(latestTs.getTime() / 1000) + 1;
          console.log(`[refresh-data] ${symbol}/${timeframe}: Fetching from ${latestTs.toISOString()}`);
        } else {
          // No existing data - fetch last 100 bars worth
          const timeframeSeconds: Record<string, number> = {
            m15: 15 * 60,
            h1: 60 * 60,
            d1: 24 * 60 * 60,
            w1: 7 * 24 * 60 * 60,
          };
          const secondsPerBar = timeframeSeconds[timeframe] || 24 * 60 * 60;
          fromTs = now - (100 * secondsPerBar);
          console.log(`[refresh-data] ${symbol}/${timeframe}: No existing data, fetching last 100 bars`);
        }

        // Only fetch if there's a gap (at least 1 bar worth of time)
        const timeframeSeconds: Record<string, number> = {
          m15: 15 * 60,
          h1: 60 * 60,
          d1: 24 * 60 * 60,
          w1: 7 * 24 * 60 * 60,
        };
        const minGap = timeframeSeconds[timeframe] || 24 * 60 * 60;

        if (now - fromTs < minGap && latestTs) {
          console.log(`[refresh-data] ${symbol}/${timeframe}: Data is current, skipping fetch`);
          result.dataRefresh.push(tfResult);
          continue;
        }

        // Fetch fresh bars from provider
        const freshBars = await router.getHistoricalBars({
          symbol,
          timeframe: timeframe as Timeframe,
          start: fromTs,
          end: now,
        });

        console.log(`[refresh-data] ${symbol}/${timeframe}: Received ${freshBars.length} bars from provider`);

        if (freshBars.length > 0) {
          // Upsert new bars
          const barsToInsert = freshBars.map((bar) => ({
            symbol_id: symbolId,
            timeframe: timeframe,
            ts: new Date(bar.timestamp).toISOString(),
            open: bar.open,
            high: bar.high,
            low: bar.low,
            close: bar.close,
            volume: bar.volume,
            provider: "massive",
          }));

          const { error: upsertError } = await supabase
            .from("ohlc_bars")
            .upsert(barsToInsert, {
              onConflict: "symbol_id,timeframe,ts",
              ignoreDuplicates: false,
            });

          if (upsertError) {
            console.error(`[refresh-data] Upsert error for ${symbol}/${timeframe}:`, upsertError);
            result.errors.push(`Failed to save ${timeframe} bars: ${upsertError.message}`);
          } else {
            tfResult.newBars = freshBars.length;
            tfResult.latestTimestamp = new Date(freshBars[freshBars.length - 1].timestamp).toISOString();
            console.log(`[refresh-data] ${symbol}/${timeframe}: Saved ${freshBars.length} new bars`);
          }
        }

        result.dataRefresh.push(tfResult);

      } catch (tfError) {
        console.error(`[refresh-data] Error fetching ${timeframe} for ${symbol}:`, tfError);
        result.errors.push(`${timeframe} fetch failed: ${tfError.message}`);
        result.dataRefresh.push({
          timeframe,
          existingBars: 0,
          newBars: 0,
          latestTimestamp: null,
        });
      }
    }

    // Step 3: Queue ML forecast job if requested
    if (refreshML) {
      try {
        const { error: mlQueueError } = await supabase.from("job_queue").insert({
          job_type: "forecast",
          symbol: symbol,
          status: "pending",
          priority: 1, // High priority for user-triggered refresh
          payload: {
            symbol_id: symbolId,
            horizons: ["1D", "1W"],
            triggered_by: "refresh-data",
          },
        });

        if (mlQueueError) {
          console.error(`[refresh-data] ML job queue error:`, mlQueueError);
          result.errors.push(`ML job queue failed: ${mlQueueError.message}`);
        } else {
          result.mlJobQueued = true;
          console.log(`[refresh-data] Queued ML forecast job for ${symbol}`);
        }
      } catch (mlError) {
        result.errors.push(`ML job error: ${mlError.message}`);
      }
    }

    // Step 4: Queue options ranking job if requested
    if (refreshOptions) {
      try {
        // Queue options backfill job (worker will fetch chain + write options_ranks)
        const { data: existingOptionsJob, error: optionsCheckError } = await supabase
          .from("options_backfill_jobs")
          .select("id, status, created_at")
          .eq("symbol_id", symbolId)
          .in("status", ["pending", "processing"])
          .order("created_at", { ascending: false })
          .limit(1)
          .maybeSingle();

        if (optionsCheckError) {
          console.error(`[refresh-data] Options job check error:`, optionsCheckError);
          result.errors.push(
            `Options job check failed: ${optionsCheckError.message}`
          );
        } else if (existingOptionsJob) {
          result.optionsJobQueued = true;
          console.log(
            `[refresh-data] Options backfill already queued (${existingOptionsJob.status}) for ${symbol}`
          );
        } else {
          const { error: optionsQueueError } = await supabase
            .from("options_backfill_jobs")
            .insert({
              symbol_id: symbolId,
              ticker: symbol,
              status: "pending",
            });

          if (optionsQueueError) {
            console.error(`[refresh-data] Options job queue error:`, optionsQueueError);
            result.errors.push(
              `Options job queue failed: ${optionsQueueError.message}`
            );
          } else {
            result.optionsJobQueued = true;
            console.log(`[refresh-data] Queued options backfill job for ${symbol}`);
          }
        }
      } catch (optionsError) {
        result.errors.push(`Options job error: ${optionsError.message}`);
      }
    }

    // Build summary message
    const totalNewBars = result.dataRefresh.reduce((sum, tf) => sum + tf.newBars, 0);
    result.success = result.errors.length === 0;
    
    const parts: string[] = [];
    if (totalNewBars > 0) {
      parts.push(`${totalNewBars} new bars`);
    } else {
      parts.push("Data current");
    }
    if (result.mlJobQueued) parts.push("ML job queued");
    if (result.optionsJobQueued) parts.push("Options job queued");
    
    result.message = parts.join(", ");

    console.log(`[refresh-data] Completed for ${symbol}: ${result.message}`);

    return new Response(JSON.stringify(result), {
      status: 200,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });

  } catch (error) {
    console.error("[refresh-data] Error:", error);
    return new Response(
      JSON.stringify({ 
        success: false,
        error: error.message || "Internal server error",
        errors: [error.message || "Internal server error"],
      }),
      {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  }
});
