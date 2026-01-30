// SPEC-8: Unified Market Data Orchestrator
// Central scheduler and dispatcher for all data jobs

import { createClient, type SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2.39.3";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
};

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === "string") return error;
  try {
    return JSON.stringify(error);
  } catch {
    return "Unknown error";
  }
}

function getErrorCode(error: unknown): string | null {
  if (error && typeof error === "object" && "code" in error) {
    const code = (error as { code?: unknown }).code;
    return typeof code === "string" ? code : null;
  }
  return null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

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

async function recordHeartbeat(
  supabase: SupabaseClient,
  status: "healthy" | "warning" | "error",
  message: string | null = null
): Promise<void> {
  try {
    const now = new Date().toISOString();
    const { error } = await supabase
      .from("orchestrator_heartbeat")
      .upsert({
        name: "orchestrator",
        last_seen: now,
        status,
        message,
        updated_at: now,
      });

    if (error) {
      console.error("[Orchestrator] Heartbeat error:", error);
    }
  } catch (error) {
    console.error("[Orchestrator] Heartbeat exception:", error);
  }
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
      JSON.stringify({ error: getErrorMessage(error) }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});

/**
 * Main orchestration tick: scan job definitions, create slices, dispatch work
 */
async function handleTick(supabase: SupabaseClient) {
  const startTime = Date.now();
  const results = {
    scanned: 0,
    slices_created: 0,
    jobs_dispatched: 0,
    errors: [] as string[],
  };

  try {
    await recordHeartbeat(supabase, "healthy");
    // 0. Reset stale running jobs so the queue can make forward progress
    const { data: resetResult, error: resetError } = await supabase.rpc("reset_stale_running_jobs", {
      p_max_age_minutes: 60,
      p_max_attempts: 5,
    });

    if (resetError) {
      console.error("[Orchestrator] reset_stale_running_jobs error:", resetError);
      results.errors.push(`reset_stale_running_jobs: ${getErrorMessage(resetError)}`);
    } else {
      const resetCount = Array.isArray(resetResult)
        ? Number(resetResult?.[0]?.reset_count ?? 0)
        : Number((resetResult as { reset_count?: unknown } | null)?.reset_count ?? 0);

      if (resetCount > 0) {
        console.log(`[Orchestrator] Reset stale running jobs: ${resetCount}`);
      }
    }

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
        results.errors.push(`${jobDef.symbol}/${jobDef.timeframe}: ${getErrorMessage(error)}`);
      }
    }

    // 3. Dispatch queued jobs (up to concurrency limit)
    const dispatched = await dispatchQueuedJobs(supabase, MAX_CONCURRENT_JOBS);
    results.jobs_dispatched = dispatched;

    const duration = Date.now() - startTime;
    const heartbeatStatus = results.errors.length > 0 ? "warning" : "healthy";
    const heartbeatMessage = results.errors.length > 0
      ? `errors=${results.errors.slice(0, 3).join("; ")}`
      : null;
    await recordHeartbeat(supabase, heartbeatStatus, heartbeatMessage);
    console.log(`[Orchestrator] Tick complete in ${duration}ms:`, results);

    return new Response(
      JSON.stringify({ message: "Tick complete", duration, results }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  } catch (error) {
    await recordHeartbeat(supabase, "error", getErrorMessage(error));
    console.error("[Orchestrator] Tick error:", error);
    return new Response(
      JSON.stringify({ error: getErrorMessage(error), results }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
}

/**
 * Create job slices for a job definition based on coverage gaps
 */
type JobRunInsert = {
  job_def_id: string;
  symbol: string;
  timeframe: string;
  job_type: JobDefinition["job_type"];
  slice_from: string;
  slice_to: string;
  status: "queued";
  triggered_by: string;
};

async function createSlicesForJob(supabase: SupabaseClient, jobDef: JobDefinition): Promise<number> {
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

    // Router will choose the right provider based on date:
    // - Historical intraday (before today): Polygon/Massive
    // - Today's intraday: Tradier
    // No need to restrict slices here anymore

    const candidates: Array<{ from: Date; to: Date }> = [];
    let currentTo = gapTo;

    while (currentTo > gapFrom && candidates.length < config.maxSlicesPerTick) {
      const currentFrom = new Date(Math.max(currentTo.getTime() - sliceMs, gapFrom.getTime()));
      candidates.push({ from: currentFrom, to: currentTo });
      currentTo = currentFrom;
    }

    candidates.reverse();

    if (candidates.length === 0) continue;

    const rangeFromIso = candidates[0].from.toISOString();
    const rangeToIso = candidates[candidates.length - 1].to.toISOString();

    const slicesPayload = candidates.map((c) => ({
      slice_from: c.from.toISOString(),
      slice_to: c.to.toISOString(),
    }));

    // #region agent log
    const _orchEnqStart = Date.now();
    fetch('http://127.0.0.1:7242/ingest/c38aa5cd-6eb1-473a-b1f0-0fdd8c2a440d',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'orchestrator/index.ts:before-rpc',message:'orchestrator before enqueue_job_slices',data:{symbol:jobDef.symbol,tf:jobDef.timeframe,sliceCount:slicesPayload.length,triggeredBy:'cron'},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'H1,H2,H4'})}).catch(()=>{});
    // #endregion

    const { data: enqueueResult, error: enqueueError } = await supabase.rpc(
      "enqueue_job_slices",
      {
        p_job_def_id: jobDef.id,
        p_symbol: jobDef.symbol,
        p_timeframe: jobDef.timeframe,
        p_job_type: jobDef.job_type,
        p_slices: slicesPayload,
        p_triggered_by: "cron",
      }
    );

    // #region agent log
    const _orchEnqDur = Date.now() - _orchEnqStart;
    fetch('http://127.0.0.1:7242/ingest/c38aa5cd-6eb1-473a-b1f0-0fdd8c2a440d',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'orchestrator/index.ts:after-rpc',message:'orchestrator after enqueue_job_slices',data:{symbol:jobDef.symbol,tf:jobDef.timeframe,durationMs:_orchEnqDur,success:!enqueueError,errorMsg:enqueueError?.message,errorCode:enqueueError?.code},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'H1,H2,H3,H4,H5'})}).catch(()=>{});
    // #endregion

    if (enqueueError) {
      console.error(`[Orchestrator] Error enqueueing job slices:`, enqueueError);
      continue;
    }

    const insertedCount = Array.isArray(enqueueResult)
      ? Number(enqueueResult?.[0]?.inserted_count ?? 0)
      : Number((enqueueResult as { inserted_count?: unknown } | null)?.inserted_count ?? 0);

    if (insertedCount > 0) {
      slicesCreated += insertedCount;
      console.log(
        `[Orchestrator] Created ${insertedCount} slices: ${jobDef.symbol}/${jobDef.timeframe} ${rangeFromIso} -> ${rangeToIso}`
      );
    }
  }

  return slicesCreated;
}

/**
 * Dispatch queued jobs to workers
 * Updated: 2026-01-08 with defensive logging
 */
type ClaimedJob = {
  job_run_id: string;
  job_def_id?: string;
  symbol: string;
  timeframe: string;
  job_type: JobDefinition["job_type"];
  slice_from: string | null;
  slice_to: string | null;
};

function isClaimedJob(value: unknown): value is ClaimedJob {
  if (!isRecord(value)) return false;
  return (
    typeof value.job_run_id === "string" &&
    typeof value.symbol === "string" &&
    typeof value.timeframe === "string" &&
    typeof value.job_type === "string"
  );
}

async function dispatchQueuedJobs(supabase: SupabaseClient, maxJobs: number): Promise<number> {
  console.log(`[Orchestrator] Attempting to dispatch up to ${maxJobs} jobs`);
  
  const claimedJobs: ClaimedJob[] = [];

  for (let i = 0; i < maxJobs; i++) {
    try {
      // Claim a queued job
      const { data, error } = await supabase.rpc("claim_queued_job");

      // Enhanced debug logging
      console.log(`[Orchestrator] RPC response:`, {
        hasData: !!data,
        dataType: typeof data,
        isArray: Array.isArray(data),
        dataLength: Array.isArray(data) ? data.length : 'N/A',
        firstItem: data?.[0] || data,
        error: error
      });

      if (error) {
        console.error(`[Orchestrator] RPC error:`, error);
        break;
      }

      // Handle different response formats
      let jobUnknown: unknown;
      if (Array.isArray(data) && data.length > 0) {
        jobUnknown = data[0];
      } else if (data && typeof data === "object") {
        jobUnknown = data;
      } else {
        console.log("[Orchestrator] No jobs in queue");
        break;
      }

      if (!isClaimedJob(jobUnknown)) {
        console.error("[Orchestrator] Unexpected claim_queued_job payload:", jobUnknown);
        break;
      }

      const job: ClaimedJob = jobUnknown;
      claimedJobs.push(job);
    } catch (error) {
      console.error(`[Orchestrator] Error while claiming job:`, error);
      break;
    }
  }

  if (claimedJobs.length === 0) {
    console.log(`[Orchestrator] Total dispatched: 0`);
    return 0;
  }

  console.log(`[Orchestrator] Claimed ${claimedJobs.length} jobs; grouping for dispatch`);

  const fetchJobs = claimedJobs.filter((j) => j.job_type === "fetch_intraday" || j.job_type === "fetch_historical");
  const forecastJobs = claimedJobs.filter((j) => j.job_type === "run_forecast");

  // Group fetch jobs by compatible windows so we can batch them.
  // Compatibility rule: same job_type + timeframe + slice_from + slice_to
  const groups = new Map<string, ClaimedJob[]>();
  for (const job of fetchJobs) {
    const key = `${job.job_type}|${job.timeframe}|${job.slice_from ?? ""}|${job.slice_to ?? ""}`;
    const list = groups.get(key);
    if (list) list.push(job);
    else groups.set(key, [job]);
  }

  let dispatched = 0;

  for (const [, group] of groups) {
    if (group.length === 1) {
      const job = group[0];
      try {
        console.log(`[Orchestrator] Dispatching single-symbol fetch-bars for ${job.symbol}/${job.timeframe}`);
        await dispatchFetchBarsSingle(job);
        dispatched += 1;
      } catch (error) {
        console.error(`[Orchestrator] Single dispatch error:`, error);
        await markJobRunsFailed(supabase, [job.job_run_id], error, "DISPATCH_ERROR");
      }
      continue;
    }

    // Batch dispatch (split into <=50 symbol chunks)
    try {
      await dispatchFetchBarsBatch(supabase, group);
      dispatched += group.length;
    } catch (error) {
      console.error(`[Orchestrator] Batch dispatch error:`, error);
      await markJobRunsFailed(supabase, group.map((j) => j.job_run_id), error, "BATCH_DISPATCH_ERROR");
    }
  }

  for (const job of forecastJobs) {
    try {
      await dispatchForecast(supabase, job);
      dispatched += 1;
    } catch (error) {
      console.error(`[Orchestrator] Forecast dispatch error:`, error);
      await markJobRunsFailed(supabase, [job.job_run_id], error, "FORECAST_DISPATCH_ERROR");
    }
  }

  console.log(`[Orchestrator] Total dispatched: ${dispatched}`);
  return dispatched;
}

async function markJobRunsFailed(
  supabase: SupabaseClient,
  jobRunIds: string[],
  error: unknown,
  code: string
): Promise<void> {
  const now = new Date().toISOString();
  const message = getErrorMessage(error);
  const errorCode = getErrorCode(error) || code;

  for (const id of jobRunIds) {
    await supabase
      .from("job_runs")
      .update({
        status: "failed",
        error_message: message,
        error_code: errorCode,
        finished_at: now,
        updated_at: now,
      })
      .eq("id", id);
  }
}

async function dispatchFetchBarsSingle(job: ClaimedJob): Promise<void> {
  const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
  const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const gatewayKey =
    Deno.env.get("SB_GATEWAY_KEY") ??
    Deno.env.get("ANON_KEY") ??
    Deno.env.get("SUPABASE_ANON_KEY") ??
    supabaseKey;

  const response = await fetch(`${supabaseUrl}/functions/v1/fetch-bars`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${gatewayKey}`,
      "apikey": gatewayKey,
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
}

async function dispatchFetchBarsBatch(supabase: SupabaseClient, jobs: ClaimedJob[]): Promise<void> {
  if (jobs.length === 0) return;

  const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
  const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const gatewayKey =
    Deno.env.get("SB_GATEWAY_KEY") ??
    Deno.env.get("ANON_KEY") ??
    Deno.env.get("SUPABASE_ANON_KEY") ??
    supabaseKey;

  const timeframe = jobs[0].timeframe;
  const from = jobs[0].slice_from;
  const to = jobs[0].slice_to;

  // Split into chunks of 50 to satisfy fetch-bars-batch constraints
  const chunkSize = 50;
  for (let i = 0; i < jobs.length; i += chunkSize) {
    const chunk = jobs.slice(i, i + chunkSize);
    const symbols = chunk.map((j) => j.symbol);
    const jobRunIds = chunk.map((j) => j.job_run_id);

    console.log(`[Orchestrator] BATCH GROUP: Calling fetch-bars-batch with ${symbols.length} symbols`, {
      timeframe,
      from,
      to,
    });

    const response = await fetch(`${supabaseUrl}/functions/v1/fetch-bars-batch`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${gatewayKey}`,
        "apikey": gatewayKey,
      },
      body: JSON.stringify({
        job_run_ids: jobRunIds,
        symbols,
        timeframe,
        from,
        to,
      }),
    });

    console.log(`[Orchestrator] fetch-bars-batch response:`, {
      status: response.status,
      ok: response.ok,
      batch_size: symbols.length,
    });

    if (!response.ok) {
      const errorBody = await response.text();
      console.error(`[Orchestrator] fetch-bars-batch error:`, errorBody);
      await markJobRunsFailed(supabase, jobRunIds, new Error(errorBody), "FETCH_BARS_BATCH_HTTP_ERROR");
      throw new Error(`fetch-bars-batch failed (${response.status}): ${errorBody}`);
    }
  }
}

/**
 * Dispatch forecast job (placeholder for phase 2)
 */
async function dispatchForecast(supabase: SupabaseClient, job: ClaimedJob) {
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
async function handleStatus(supabase: SupabaseClient) {
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
async function handleRetryFailed(supabase: SupabaseClient) {
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
