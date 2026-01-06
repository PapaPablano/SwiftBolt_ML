// SPEC-8: Fetch Bars Worker
// Fetches OHLC bars from providers and upserts into ohlc_bars_v2

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.3";
import { corsHeaders } from "../_shared/cors.ts";
import { getProviderRouter } from "../_shared/providers/factory.ts";
import type { Bar } from "../_shared/providers/types.ts";
import { ProviderError, RateLimitExceededError } from "../_shared/providers/types.ts";

interface FetchBarsRequest {
  job_run_id: string;
  symbol: string;
  timeframe: string;
  from: string;
  to: string;
}

interface FetchBarsResponse {
  job_run_id: string;
  rows_written: number;
  provider: string;
  from: string;
  to: string;
  duration_ms: number;
}

// Timeframe mapping
const TIMEFRAME_MAP: Record<string, string> = {
  "15m": "m15",
  "1h": "h1",
  "4h": "h4",
  "d1": "d1",
  "w1": "w1",
};

Deno.serve(async (req) => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  const startTime = Date.now();

  try {
    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const supabase = createClient(supabaseUrl, supabaseKey);

    // Parse request
    const request: FetchBarsRequest = await req.json();
    const { job_run_id, symbol, timeframe, from, to } = request;

    console.log(`[fetch-bars] Starting job ${job_run_id}: ${symbol}/${timeframe} ${from} -> ${to}`);

    // Validate inputs
    if (!job_run_id || !symbol || !timeframe || !from || !to) {
      throw new Error("Missing required parameters");
    }

    // Update job status to running
    await updateJobStatus(supabase, job_run_id, {
      status: "running",
      started_at: new Date().toISOString(),
    });

    // Initialize provider router
    const router = getProviderRouter();

    // Map timeframe to provider format
    const providerTimeframe = TIMEFRAME_MAP[timeframe] || timeframe;

    // Fetch bars from provider
    const fromDate = new Date(from);
    const toDate = new Date(to);
    
    let bars: Bar[] = [];
    let provider = "unknown";

    try {
      bars = await router.getHistoricalBars({
        symbol,
        timeframe: providerTimeframe as any,
        start: Math.floor(fromDate.getTime() / 1000),
        end: Math.floor(toDate.getTime() / 1000),
      });

      // Determine which provider was used (check router health status)
      const healthStatus = router.getHealthStatus();
      const isIntraday = ["m15", "h1", "h4"].includes(providerTimeframe);
      provider = isIntraday ? "tradier" : "yahoo";

      console.log(`[fetch-bars] Fetched ${bars.length} bars from ${provider}`);
    } catch (error) {
      console.error(`[fetch-bars] Provider error:`, error);
      
      // Handle rate limit errors with exponential backoff
      if (error instanceof RateLimitExceededError) {
        const retryAfter = error.retryAfter || 60;
        await updateJobStatus(supabase, job_run_id, {
          status: "queued", // Requeue for retry
          error_message: `Rate limit exceeded, retry after ${retryAfter}s`,
          error_code: "RATE_LIMIT_EXCEEDED",
        });

        return new Response(
          JSON.stringify({ 
            error: "Rate limit exceeded", 
            retry_after: retryAfter,
            job_run_id,
          }),
          { status: 429, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      // Handle other provider errors
      if (error instanceof ProviderError) {
        await updateJobStatus(supabase, job_run_id, {
          status: "failed",
          error_message: error.message,
          error_code: error.code,
          finished_at: new Date().toISOString(),
        });

        return new Response(
          JSON.stringify({ 
            error: error.message, 
            code: error.code,
            provider: error.provider,
            job_run_id,
          }),
          { status: error.statusCode || 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      throw error;
    }

    // Upsert bars into ohlc_bars_v2
    let rowsWritten = 0;
    if (bars.length > 0) {
      const barsToInsert = bars.map((bar) => ({
        symbol,
        timeframe,
        ts: new Date(bar.timestamp * 1000).toISOString(),
        open: bar.open,
        high: bar.high,
        low: bar.low,
        close: bar.close,
        volume: bar.volume,
        provider,
        is_forecast: false,
      }));

      // Batch upsert (Supabase has a 1000 row limit per request)
      const batchSize = 1000;
      for (let i = 0; i < barsToInsert.length; i += batchSize) {
        const batch = barsToInsert.slice(i, i + batchSize);
        
        const { error: upsertError } = await supabase
          .from("ohlc_bars_v2")
          .upsert(batch, {
            onConflict: "symbol,timeframe,ts",
            ignoreDuplicates: false, // Update existing rows
          });

        if (upsertError) {
          console.error(`[fetch-bars] Upsert error:`, upsertError);
          throw new Error(`Failed to upsert bars: ${upsertError.message}`);
        }

        rowsWritten += batch.length;
        
        // Update progress
        const progress = Math.floor((i + batch.length) / barsToInsert.length * 100);
        await updateJobStatus(supabase, job_run_id, {
          progress_percent: progress,
        });
      }

      console.log(`[fetch-bars] Upserted ${rowsWritten} bars`);
    }

    // Update job status to success
    const duration = Date.now() - startTime;
    await updateJobStatus(supabase, job_run_id, {
      status: "success",
      rows_written: rowsWritten,
      provider,
      progress_percent: 100,
      finished_at: new Date().toISOString(),
    });

    const response: FetchBarsResponse = {
      job_run_id,
      rows_written: rowsWritten,
      provider,
      from,
      to,
      duration_ms: duration,
    };

    console.log(`[fetch-bars] Job complete:`, response);

    return new Response(
      JSON.stringify(response),
      { headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  } catch (error) {
    console.error("[fetch-bars] Error:", error);
    
    const duration = Date.now() - startTime;
    
    return new Response(
      JSON.stringify({ 
        error: error.message,
        duration_ms: duration,
      }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});

/**
 * Update job run status in database
 */
async function updateJobStatus(
  supabase: any,
  jobRunId: string,
  updates: Partial<{
    status: string;
    progress_percent: number;
    rows_written: number;
    provider: string;
    error_message: string;
    error_code: string;
    started_at: string;
    finished_at: string;
  }>
) {
  const { error } = await supabase
    .from("job_runs")
    .update({
      ...updates,
      updated_at: new Date().toISOString(),
    })
    .eq("id", jobRunId);

  if (error) {
    console.error(`[fetch-bars] Error updating job status:`, error);
    throw error;
  }
}
