// SPEC-8: Unified Market Data Orchestrator
// Central scheduler and dispatcher for all data jobs

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.3";
import { corsHeaders } from "../_shared/cors.ts";

interface JobDefinition {
  id: string;
  job_type: 'fetch_intraday' | 'fetch_historical' | 'run_forecast';
  symbol: string;
  timeframe: string;
  window_days: number;
  priority: number;
  enabled: boolean;
}

interface JobRun {
  id: string;
  job_def_id: string;
  symbol: string;
  timeframe: string;
  job_type: string;
  slice_from: string | null;
  slice_to: string | null;
  status: 'queued' | 'running' | 'success' | 'failed' | 'cancelled';
  progress_percent: number;
  rows_written: number;
  provider: string | null;
  attempt: number;
  error_message: string | null;
  error_code: string | null;
}

interface CoverageGap {
  gap_from: string;
  gap_to: string;
  gap_hours: number;
}

const SLICE_CONFIGS = {
  fetch_intraday: {
    sliceHours: 2, // 2-hour slices for intraday
    maxSlicesPerTick: 10,
  },
  fetch_historical: {
    sliceHours: 24 * 30, // 30-day slices for historical
    maxSlicesPerTick: 10, // Increased from 3 to 10 for faster backfill
  },
  run_forecast: {
    sliceHours: 24 * 90, // Full 90-day window for forecast
    maxSlicesPerTick: 2,
  },
};

const MAX_CONCURRENT_JOBS = 5;
const MAX_RETRY_ATTEMPTS = 5;

Deno.serve(async (req) => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const supabase = createClient(supabaseUrl, supabaseKey);

    const url = new URL(req.url);
    const action = url.searchParams.get("action") || "tick";

    console.log(`[Orchestrator] Action: ${action}`);

    switch (action) {
      case "tick":
        return await handleTick(supabase);
      case "status":
        return await handleStatus(supabase);
      case "retry_failed":
        return await handleRetryFailed(supabase);
      default:
        return new Response(
          JSON.stringify({ error: "Invalid action" }),
          { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
    }
  } catch (error) {
    console.error("[Orchestrator] Error:", error);
    return new Response(
      JSON.stringify({ error: error.message }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});

/**
 * Main orchestration tick: scan job definitions, create slices, dispatch work
 */
async function handleTick(supabase: any) {
  const startTime = Date.now();
  const results = {
    scanned: 0,
    slices_created: 0,
    jobs_dispatched: 0,
    errors: [] as string[],
  };

  try {
    // 1. Get all enabled job definitions, ordered by priority
    const { data: jobDefs, error: jobDefsError } = await supabase
      .from("job_definitions")
      .select("*")
      .eq("enabled", true)
      .order("priority", { ascending: false });

    if (jobDefsError) throw jobDefsError;
    if (!jobDefs || jobDefs.length === 0) {
      console.log("[Orchestrator] No enabled job definitions found");
      return new Response(
        JSON.stringify({ message: "No jobs to process", results }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    results.scanned = jobDefs.length;
    console.log(`[Orchestrator] Found ${jobDefs.length} enabled job definitions`);

    // 2. For each job definition, check coverage and create slices
    for (const jobDef of jobDefs as JobDefinition[]) {
      try {
        const slicesCreated = await createSlicesForJob(supabase, jobDef);
        results.slices_created += slicesCreated;
      } catch (error) {
        console.error(`[Orchestrator] Error creating slices for ${jobDef.symbol}/${jobDef.timeframe}:`, error);
        results.errors.push(`${jobDef.symbol}/${jobDef.timeframe}: ${error.message}`);
      }
    }

    // 3. Dispatch queued jobs (up to concurrency limit)
    const dispatched = await dispatchQueuedJobs(supabase, MAX_CONCURRENT_JOBS);
    results.jobs_dispatched = dispatched;

    const duration = Date.now() - startTime;
    console.log(`[Orchestrator] Tick complete in ${duration}ms:`, results);

    return new Response(
      JSON.stringify({ message: "Tick complete", duration, results }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  } catch (error) {
    console.error("[Orchestrator] Tick error:", error);
    return new Response(
      JSON.stringify({ error: error.message, results }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
}

/**
 * Create job slices for a job definition based on coverage gaps
 */
async function createSlicesForJob(supabase: any, jobDef: JobDefinition): Promise<number> {
  const config = SLICE_CONFIGS[jobDef.job_type];
  if (!config) {
    console.warn(`[Orchestrator] No config for job type: ${jobDef.job_type}`);
    return 0;
  }

  // Get coverage gaps
  const { data: gaps, error: gapsError } = await supabase
    .rpc("get_coverage_gaps", {
      p_symbol: jobDef.symbol,
      p_timeframe: jobDef.timeframe,
      p_window_days: jobDef.window_days,
    });

  if (gapsError) {
    console.error(`[Orchestrator] Error getting gaps:`, gapsError);
    return 0;
  }

  if (!gaps || gaps.length === 0) {
    console.log(`[Orchestrator] No gaps for ${jobDef.symbol}/${jobDef.timeframe}`);
    return 0;
  }

  console.log(`[Orchestrator] Found ${gaps.length} gaps for ${jobDef.symbol}/${jobDef.timeframe}`);

  let slicesCreated = 0;

  // Create slices for each gap
  for (const gap of gaps as CoverageGap[]) {
    const gapFrom = new Date(gap.gap_from);
    const gapTo = new Date(gap.gap_to);
    const sliceMs = config.sliceHours * 60 * 60 * 1000;

    let currentFrom = gapFrom;
    let sliceCount = 0;

    while (currentFrom < gapTo && sliceCount < config.maxSlicesPerTick) {
      const currentTo = new Date(Math.min(currentFrom.getTime() + sliceMs, gapTo.getTime()));

      // Router will choose the right provider based on date:
      // - Historical intraday (before today): Polygon/Massive
      // - Today's intraday: Tradier
      // No need to restrict slices here anymore

      // Check if slice already exists (idempotency)
      const { data: exists } = await supabase.rpc("job_slice_exists", {
        p_symbol: jobDef.symbol,
        p_timeframe: jobDef.timeframe,
        p_slice_from: currentFrom.toISOString(),
        p_slice_to: currentTo.toISOString(),
      });

      if (!exists) {
        // Create new job run
        const { error: insertError } = await supabase
          .from("job_runs")
          .insert({
            job_def_id: jobDef.id,
            symbol: jobDef.symbol,
            timeframe: jobDef.timeframe,
            job_type: jobDef.job_type,
            slice_from: currentFrom.toISOString(),
            slice_to: currentTo.toISOString(),
            status: "queued",
            triggered_by: "cron",
          });

        if (insertError) {
          console.error(`[Orchestrator] Error inserting job run:`, insertError);
        } else {
          slicesCreated++;
          sliceCount++;
          console.log(`[Orchestrator] Created slice: ${jobDef.symbol}/${jobDef.timeframe} ${currentFrom.toISOString()} -> ${currentTo.toISOString()}`);
        }
      }

      currentFrom = currentTo;
    }
  }

  return slicesCreated;
}

/**
 * Dispatch queued jobs to workers
 * Updated: 2026-01-08 with defensive logging
 */
async function dispatchQueuedJobs(supabase: any, maxJobs: number): Promise<number> {
  let dispatched = 0;

  for (let i = 0; i < maxJobs; i++) {
    // Claim a queued job
    const { data: claimed, error: claimError } = await supabase
      .rpc("claim_queued_job");

    // Defensive logging: Log claim result
    console.log(`[Orchestrator] claim_queued_job() result:`, {
      claimError: claimError ? JSON.stringify(claimError) : null,
      claimedLength: claimed?.length ?? 0,
      claimedData: claimed ? JSON.stringify(claimed) : null,
    });

    if (claimError) {
      console.error(`[Orchestrator] Error claiming job:`, claimError);
      break;
    }

    if (!claimed || claimed.length === 0) {
      console.log(`[Orchestrator] No more queued jobs to dispatch`);
      break;
    }

    const job = claimed[0];
    
    // Defensive logging: Log claimed job details
    console.log(`[Orchestrator] Claimed job details:`, {
      job_run_id: job.job_run_id,
      symbol: job.symbol,
      timeframe: job.timeframe,
      job_type: job.job_type,
      slice_from: job.slice_from,
      slice_to: job.slice_to,
    });

    // Dispatch to appropriate worker
    try {
      if (job.job_type === "fetch_intraday" || job.job_type === "fetch_historical") {
        await dispatchFetchBars(supabase, job);
        dispatched++;
      } else if (job.job_type === "run_forecast") {
        await dispatchForecast(supabase, job);
        dispatched++;
      }
    } catch (error) {
      console.error(`[Orchestrator] Error dispatching job ${job.job_run_id}:`, error);
      
      // Mark job as failed
      await supabase
        .from("job_runs")
        .update({
          status: "failed",
          error_message: error.message,
          error_code: error.code || "DISPATCH_ERROR",
          finished_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        })
        .eq("id", job.job_run_id);
    }
  }

  return dispatched;
}

/**
 * Dispatch fetch-bars job (internal function call)
 * Phase 2: Detects batch jobs and routes to fetch-bars-batch for 50x speedup
 */
async function dispatchFetchBars(supabase: any, job: any) {
  const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
  const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

  // Check if this is a batch job by looking up the job_definition
  const { data: jobDef } = await supabase
    .from("job_definitions")
    .select("symbols_array, batch_version")
    .eq("id", job.job_def_id)
    .single();

  const isBatchJob = jobDef?.symbols_array && Array.isArray(jobDef.symbols_array) && jobDef.symbols_array.length > 1;

  if (isBatchJob) {
    // Phase 2: Batch processing with fetch-bars-batch
    console.log(`[Orchestrator] Dispatching BATCH job: ${jobDef.symbols_array.length} symbols, ${job.timeframe}`);
    
    const response = await fetch(`${supabaseUrl}/functions/v1/fetch-bars-batch`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${supabaseKey}`,
      },
      body: JSON.stringify({
        job_run_id: job.job_run_id,
        symbols: jobDef.symbols_array,
        timeframe: job.timeframe,
        start: job.slice_from,
        end: job.slice_to,
      }),
    });

    console.log(`[Orchestrator] fetch-bars-batch response:`, {
      status: response.status,
      ok: response.ok,
      job_run_id: job.job_run_id,
      batch_size: jobDef.symbols_array.length,
    });

    if (!response.ok) {
      const errorBody = await response.text();
      console.error(`[Orchestrator] fetch-bars-batch error:`, errorBody);
      throw new Error(`fetch-bars-batch failed (${response.status}): ${errorBody}`);
    }

    const result = await response.json();
    console.log(`[Orchestrator] fetch-bars-batch success:`, {
      job_run_id: job.job_run_id,
      symbols_processed: result.symbols_processed,
      bars_written: result.bars_written,
    });
  } else {
    // Phase 1: Single-symbol processing with fetch-bars
    console.log(`[Orchestrator] Dispatching single-symbol fetch-bars for ${job.symbol}/${job.timeframe}`);

    const response = await fetch(`${supabaseUrl}/functions/v1/fetch-bars`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${supabaseKey}`,
      },
      body: JSON.stringify({
        job_run_id: job.job_run_id,
        symbol: job.symbol,
        timeframe: job.timeframe,
        from: job.slice_from,
        to: job.slice_to,
      }),
    });

    console.log(`[Orchestrator] fetch-bars response status:`, {
      status: response.status,
      statusText: response.statusText,
      ok: response.ok,
      job_run_id: job.job_run_id,
    });

    if (!response.ok) {
      const errorBody = await response.text();
      console.error(`[Orchestrator] fetch-bars error body:`, errorBody);
      throw new Error(`fetch-bars failed (${response.status}): ${errorBody}`);
    }

    const result = await response.json();
    console.log(`[Orchestrator] fetch-bars success:`, {
      job_run_id: job.job_run_id,
      result: JSON.stringify(result),
    });
  }
}

/**
 * Dispatch forecast job (placeholder for phase 2)
 */
async function dispatchForecast(supabase: any, job: any) {
  console.log(`[Orchestrator] Dispatching forecast for ${job.symbol}/${job.timeframe}`);
  
  // TODO: Implement forecast worker dispatch in phase 2
  // For now, mark as success
  await supabase
    .from("job_runs")
    .update({
      status: "success",
      finished_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    })
    .eq("id", job.job_run_id);
}

/**
 * Get orchestrator status
 */
async function handleStatus(supabase: any) {
  const { data: queuedJobs } = await supabase
    .from("job_runs")
    .select("*")
    .eq("status", "queued")
    .order("created_at", { ascending: true })
    .limit(10);

  const { data: runningJobs } = await supabase
    .from("job_runs")
    .select("*")
    .eq("status", "running")
    .order("started_at", { ascending: true });

  const { data: recentJobs } = await supabase
    .from("job_runs")
    .select("*")
    .in("status", ["success", "failed"])
    .order("finished_at", { ascending: false })
    .limit(20);

  return new Response(
    JSON.stringify({
      queued: queuedJobs?.length || 0,
      running: runningJobs?.length || 0,
      queued_jobs: queuedJobs || [],
      running_jobs: runningJobs || [],
      recent_jobs: recentJobs || [],
    }),
    { headers: { ...corsHeaders, "Content-Type": "application/json" } }
  );
}

/**
 * Retry failed jobs
 */
async function handleRetryFailed(supabase: any) {
  const { data: failedJobs, error } = await supabase
    .from("job_runs")
    .select("*")
    .eq("status", "failed")
    .lt("attempt", MAX_RETRY_ATTEMPTS)
    .order("finished_at", { ascending: true })
    .limit(10);

  if (error) throw error;

  let retried = 0;
  for (const job of failedJobs || []) {
    const { error: updateError } = await supabase
      .from("job_runs")
      .update({
        status: "queued",
        attempt: job.attempt + 1,
        error_message: null,
        error_code: null,
        updated_at: new Date().toISOString(),
      })
      .eq("id", job.id);

    if (!updateError) {
      retried++;
      console.log(`[Orchestrator] Retried job ${job.id} (attempt ${job.attempt + 1})`);
    }
  }

  return new Response(
    JSON.stringify({ message: `Retried ${retried} failed jobs` }),
    { headers: { ...corsHeaders, "Content-Type": "application/json" } }
  );
}
