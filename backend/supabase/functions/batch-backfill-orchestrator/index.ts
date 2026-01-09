// Phase 2: Batch Backfill Orchestrator
// Creates batch jobs with 50 symbols per job for efficient Alpaca API usage
// Reduces API calls from 5000+ to ~100 while staying under 200 req/min limit

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.3";
import { corsHeaders } from "../_shared/cors.ts";

const BATCH_SIZE = 50; // Alpaca supports up to 50 symbols per request
const TIMEFRAMES = ["m15", "h1", "h4", "d1"]; // Standard timeframes for backfill

interface BatchJobConfig {
  symbols: string[];
  timeframes: string[];
  startDate: string;
  endDate: string;
  sliceType: "historical" | "intraday";
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  const startTime = Date.now();

  try {
    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const supabase = createClient(supabaseUrl, supabaseKey);

    // Parse request or use defaults
    const body = await req.json().catch(() => ({}));
    const config: BatchJobConfig = {
      symbols: body.symbols || await getWatchlistSymbols(supabase),
      timeframes: body.timeframes || TIMEFRAMES,
      startDate: body.startDate || getDefaultStartDate(),
      endDate: body.endDate || new Date().toISOString(),
      sliceType: body.sliceType || "historical",
    };

    console.log(`[BatchOrchestrator] Starting batch job creation:`);
    console.log(`  - Symbols: ${config.symbols.length}`);
    console.log(`  - Timeframes: ${config.timeframes.join(", ")}`);
    console.log(`  - Date range: ${config.startDate} to ${config.endDate}`);
    console.log(`  - Slice type: ${config.sliceType}`);

    // Create batch jobs
    const jobsCreated = await createBatchJobs(supabase, config);

    const duration = Date.now() - startTime;
    const response = {
      success: true,
      jobs_created: jobsCreated,
      total_symbols: config.symbols.length,
      batches: Math.ceil(config.symbols.length / BATCH_SIZE),
      timeframes: config.timeframes.length,
      duration_ms: duration,
      estimated_api_calls: jobsCreated, // 1 API call per batch job
      efficiency_gain: `${Math.floor((config.symbols.length * config.timeframes.length) / jobsCreated)}x`,
    };

    console.log(`[BatchOrchestrator] Complete:`, response);

    return new Response(
      JSON.stringify(response),
      { headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  } catch (error) {
    console.error("[BatchOrchestrator] Error:", error);
    return new Response(
      JSON.stringify({
        error: error.message,
        duration_ms: Date.now() - startTime,
      }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});

/**
 * Create batch jobs with 50 symbols per job
 */
async function createBatchJobs(
  supabase: any,
  config: BatchJobConfig
): Promise<number> {
  let jobsCreated = 0;
  const startTs = new Date(config.startDate).getTime();
  const endTs = new Date(config.endDate).getTime();

  console.log(`[BatchOrchestrator] Creating batch jobs for ${config.symbols.length} symbols...`);

  // Batch symbols into groups of 50
  for (let i = 0; i < config.symbols.length; i += BATCH_SIZE) {
    const batch = config.symbols.slice(i, i + BATCH_SIZE);
    const batchNum = Math.floor(i / BATCH_SIZE) + 1;
    const totalBatches = Math.ceil(config.symbols.length / BATCH_SIZE);

    console.log(`[BatchOrchestrator] Processing batch ${batchNum}/${totalBatches}: ${batch.length} symbols`);

    // Create one job per timeframe for this batch
    for (const timeframe of config.timeframes) {
      try {
        // For batch jobs, use first symbol as primary + store full array
        const primarySymbol = batch[0];
        
        const jobData = {
          // NEW: Store array of symbols for batch processing
          symbols_array: batch,
          batch_number: batchNum,
          total_batches: totalBatches,
          // Required fields for job_definitions schema
          symbol: primarySymbol, // Use first symbol as primary identifier
          timeframe,
          job_type: config.sliceType === "historical" ? "fetch_historical" : "fetch_intraday",
          window_days: Math.ceil((endTs - startTs) / (1000 * 60 * 60 * 24)),
          priority: 100,
          enabled: true,
        };
        
        console.log(`[BatchOrchestrator] Attempting to insert job:`, JSON.stringify(jobData));
        
        const { data, error } = await supabase
          .from("job_definitions")
          .insert(jobData)
          .select();

        if (error) {
          console.error(
            `[BatchOrchestrator] Failed batch ${batchNum}/${totalBatches}, ${timeframe}:`,
            JSON.stringify(error)
          );
        } else {
          jobsCreated++;
          console.log(
            `[BatchOrchestrator] ✓ Batch ${batchNum}/${totalBatches}: ${batch.length} symbols, ${timeframe}, inserted:`,
            JSON.stringify(data)
          );
        }
      } catch (error) {
        console.error(`[BatchOrchestrator] Exception creating batch job:`, error);
      }
    }
  }

  console.log(`[BatchOrchestrator] Created ${jobsCreated} batch jobs`);
  return jobsCreated;
}

/**
 * Get all watchlist symbols
 */
async function getWatchlistSymbols(supabase: any): Promise<string[]> {
  const { data, error } = await supabase
    .from("symbols")
    .select("ticker")
    .eq("asset_type", "stock")
    .order("ticker");

  if (error) {
    console.error("[BatchOrchestrator] Error fetching symbols:", error);
    throw error;
  }

  const symbols = data?.map((s: any) => s.ticker) || [];
  console.log(`[BatchOrchestrator] Found ${symbols.length} symbols`);
  return symbols;
}

/**
 * Get default start date (1 year ago for historical backfill)
 */
function getDefaultStartDate(): string {
  const date = new Date();
  date.setFullYear(date.getFullYear() - 1);
  return date.toISOString();
}
