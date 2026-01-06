// SPEC-8: Ensure Coverage
// Client-triggered function to ensure data coverage for a symbol/timeframe

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.3";
import { corsHeaders } from "../_shared/cors.ts";

interface EnsureCoverageRequest {
  symbol: string;
  timeframe: string;
  window_days?: number;
  priority?: number;
}

interface EnsureCoverageResponse {
  job_def_id: string;
  symbol: string;
  timeframe: string;
  status: string;
  coverage_status: {
    from_ts: string | null;
    to_ts: string | null;
    last_success_at: string | null;
    gaps_found: number;
  };
}

Deno.serve(async (req) => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const supabase = createClient(supabaseUrl, supabaseKey);

    // Parse request
    const request: EnsureCoverageRequest = await req.json();
    const { symbol, timeframe, window_days = 7, priority = 150 } = request;

    console.log(`[ensure-coverage] Request: ${symbol}/${timeframe} (${window_days} days)`);

    // Validate inputs
    if (!symbol || !timeframe) {
      return new Response(
        JSON.stringify({ error: "Missing required parameters: symbol, timeframe" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // Determine job type based on timeframe
    const isIntraday = ["15m", "1h", "4h"].includes(timeframe);
    const jobType = isIntraday ? "fetch_intraday" : "fetch_historical";

    // 1. Upsert job definition
    const { data: jobDef, error: jobDefError } = await supabase
      .from("job_definitions")
      .upsert(
        {
          symbol,
          timeframe,
          job_type: jobType,
          window_days,
          priority,
          enabled: true,
        },
        {
          onConflict: "symbol,timeframe,job_type",
          ignoreDuplicates: false,
        }
      )
      .select()
      .single();

    if (jobDefError) {
      console.error(`[ensure-coverage] Error upserting job definition:`, jobDefError);
      throw jobDefError;
    }

    console.log(`[ensure-coverage] Job definition upserted: ${jobDef.id}`);

    // 2. Check current coverage
    const { data: coverage } = await supabase
      .from("coverage_status")
      .select("*")
      .eq("symbol", symbol)
      .eq("timeframe", timeframe)
      .single();

    console.log(`[ensure-coverage] Current coverage:`, coverage);

    // 3. Check for gaps
    const { data: gaps, error: gapsError } = await supabase.rpc("get_coverage_gaps", {
      p_symbol: symbol,
      p_timeframe: timeframe,
      p_window_days: window_days,
    });

    if (gapsError) {
      console.error(`[ensure-coverage] Error getting gaps:`, gapsError);
      throw gapsError;
    }

    const gapsFound = gaps?.length || 0;
    console.log(`[ensure-coverage] Found ${gapsFound} gaps`);

    // 4. If gaps exist, create job runs (orchestrator will pick them up)
    if (gapsFound > 0) {
      // The orchestrator will create slices on next tick
      // We just need to ensure the job definition is enabled
      console.log(`[ensure-coverage] Gaps detected, orchestrator will create slices`);
    }

    // 5. Return response
    const response: EnsureCoverageResponse = {
      job_def_id: jobDef.id,
      symbol,
      timeframe,
      status: gapsFound > 0 ? "gaps_detected" : "coverage_complete",
      coverage_status: {
        from_ts: coverage?.from_ts || null,
        to_ts: coverage?.to_ts || null,
        last_success_at: coverage?.last_success_at || null,
        gaps_found: gapsFound,
      },
    };

    console.log(`[ensure-coverage] Response:`, response);

    return new Response(JSON.stringify(response), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (error) {
    console.error("[ensure-coverage] Error:", error);
    return new Response(
      JSON.stringify({ error: error.message }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
