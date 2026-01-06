// SPEC-8: Ops Jobs Endpoint
// Observability endpoint for job status and health

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.3";
import { corsHeaders } from "../_shared/cors.ts";

interface JobStats {
  total: number;
  queued: number;
  running: number;
  success: number;
  failed: number;
  success_rate: number;
}

interface ProviderStats {
  provider: string;
  total_runs: number;
  success_runs: number;
  failed_runs: number;
  total_rows: number;
  avg_duration_ms: number;
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

    const url = new URL(req.url);
    const symbol = url.searchParams.get("symbol");
    const timeframe = url.searchParams.get("timeframe");
    const hours = parseInt(url.searchParams.get("hours") || "24");

    console.log(`[ops-jobs] Request: symbol=${symbol}, timeframe=${timeframe}, hours=${hours}`);

    // Calculate time window
    const since = new Date(Date.now() - hours * 60 * 60 * 1000).toISOString();

    // Build base query
    let query = supabase
      .from("job_runs")
      .select("*")
      .gte("created_at", since);

    if (symbol) {
      query = query.eq("symbol", symbol);
    }
    if (timeframe) {
      query = query.eq("timeframe", timeframe);
    }

    const { data: jobs, error: jobsError } = await query.order("created_at", { ascending: false });

    if (jobsError) throw jobsError;

    // Calculate statistics
    const stats: JobStats = {
      total: jobs?.length || 0,
      queued: jobs?.filter((j) => j.status === "queued").length || 0,
      running: jobs?.filter((j) => j.status === "running").length || 0,
      success: jobs?.filter((j) => j.status === "success").length || 0,
      failed: jobs?.filter((j) => j.status === "failed").length || 0,
      success_rate: 0,
    };

    if (stats.total > 0) {
      stats.success_rate = Math.round((stats.success / stats.total) * 100);
    }

    // Provider statistics
    const providerMap = new Map<string, any>();
    jobs?.forEach((job) => {
      if (!job.provider) return;
      
      if (!providerMap.has(job.provider)) {
        providerMap.set(job.provider, {
          provider: job.provider,
          total_runs: 0,
          success_runs: 0,
          failed_runs: 0,
          total_rows: 0,
          total_duration_ms: 0,
          run_count: 0,
        });
      }

      const stats = providerMap.get(job.provider);
      stats.total_runs++;
      if (job.status === "success") {
        stats.success_runs++;
        stats.total_rows += job.rows_written || 0;
      }
      if (job.status === "failed") {
        stats.failed_runs++;
      }
      if (job.started_at && job.finished_at) {
        const duration = new Date(job.finished_at).getTime() - new Date(job.started_at).getTime();
        stats.total_duration_ms += duration;
        stats.run_count++;
      }
    });

    const providerStats: ProviderStats[] = Array.from(providerMap.values()).map((s) => ({
      provider: s.provider,
      total_runs: s.total_runs,
      success_runs: s.success_runs,
      failed_runs: s.failed_runs,
      total_rows: s.total_rows,
      avg_duration_ms: s.run_count > 0 ? Math.round(s.total_duration_ms / s.run_count) : 0,
    }));

    // Get coverage status
    let coverageQuery = supabase.from("coverage_status").select("*");
    if (symbol) {
      coverageQuery = coverageQuery.eq("symbol", symbol);
    }
    if (timeframe) {
      coverageQuery = coverageQuery.eq("timeframe", timeframe);
    }

    const { data: coverage } = await coverageQuery.order("updated_at", { ascending: false });

    // Recent errors
    const recentErrors = jobs
      ?.filter((j) => j.status === "failed" && j.error_message)
      .slice(0, 10)
      .map((j) => ({
        job_run_id: j.id,
        symbol: j.symbol,
        timeframe: j.timeframe,
        error_code: j.error_code,
        error_message: j.error_message,
        attempt: j.attempt,
        failed_at: j.finished_at,
      }));

    // Active jobs
    const activeJobs = jobs
      ?.filter((j) => j.status === "running")
      .map((j) => ({
        job_run_id: j.id,
        symbol: j.symbol,
        timeframe: j.timeframe,
        job_type: j.job_type,
        progress_percent: j.progress_percent,
        started_at: j.started_at,
        slice_from: j.slice_from,
        slice_to: j.slice_to,
      }));

    // Queued jobs
    const queuedJobs = jobs
      ?.filter((j) => j.status === "queued")
      .slice(0, 20)
      .map((j) => ({
        job_run_id: j.id,
        symbol: j.symbol,
        timeframe: j.timeframe,
        job_type: j.job_type,
        attempt: j.attempt,
        created_at: j.created_at,
        slice_from: j.slice_from,
        slice_to: j.slice_to,
      }));

    const response = {
      window_hours: hours,
      filters: { symbol, timeframe },
      stats,
      provider_stats: providerStats,
      coverage: coverage || [],
      active_jobs: activeJobs || [],
      queued_jobs: queuedJobs || [],
      recent_errors: recentErrors || [],
      timestamp: new Date().toISOString(),
    };

    return new Response(JSON.stringify(response, null, 2), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (error) {
    console.error("[ops-jobs] Error:", error);
    return new Response(
      JSON.stringify({ error: error.message }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
