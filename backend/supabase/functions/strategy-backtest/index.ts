// Strategy Backtest API
// POST /strategy-backtest - Queue a new backtest job
// GET /strategy-backtest?id=xxx - Get job status and results
// GET /strategy-backtest?status=pending - List jobs for user

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { handleCorsOptions, jsonResponse, errorResponse } from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";

function getUserIdFromRequest(req: Request): string | null {
  const authHeader = req.headers.get("Authorization");
  if (!authHeader) return null;
  
  const token = authHeader.replace("Bearer ", "");
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const payload = JSON.parse(atob(parts[1]));
    return payload.sub || null;
  } catch {
    return null;
  }
}

serve(async (req: Request): Promise<Response> => {
  if (req.method === "OPTIONS") {
    return handleCorsOptions();
  }

  const supabase = getSupabaseClient();
  let userId = getUserIdFromRequest(req);
  
  if (!userId) {
    userId = "00000000-0000-0000-0000-000000000001";
  }

  const url = new URL(req.url);
  const jobId = url.searchParams.get("id");

  try {
    if (req.method === "POST") {
      return await handleQueueBacktest(supabase, userId, req);
    }
    
    if (req.method === "GET") {
      if (jobId) {
        return await handleGetJob(supabase, userId, jobId);
      }
      return await handleListJobs(supabase, userId, url);
    }
    
    return errorResponse("Method not allowed", 405);
  } catch (err) {
    console.error("Backtest API error:", err);
    return errorResponse(err instanceof Error ? err.message : "Internal error", 500);
  }
});

async function handleQueueBacktest(
  supabase: ReturnType<typeof getSupabaseClient>,
  userId: string,
  req: Request
) {
  const body = await req.json();
  
  if (!body.strategy_id) {
    return errorResponse("strategy_id is required");
  }
  
  if (!body.start_date || !body.end_date) {
    return errorResponse("start_date and end_date are required (YYYY-MM-DD)");
  }
  
  // Verify strategy exists (allow demo mode strategies with null user_id)
  const { data: strategy, error: strategyError } = await supabase
    .from("strategy_user_strategies")
    .select("id, name, config")
    .eq("id", body.strategy_id)
    .or("user_id.eq." + userId + ",user_id.is.null")
    .single();
  
  if (strategyError || !strategy) {
    return errorResponse("Strategy not found", 404);
  }
  
  const job = {
    user_id: userId,
    strategy_id: body.strategy_id,
    symbol: body.symbol || "AAPL",
    start_date: body.start_date,
    end_date: body.end_date,
    parameters: body.parameters || {},
    status: "pending"
  };
  
  const { data, error } = await supabase
    .from("strategy_backtest_jobs")
    .insert(job)
    .select()
    .single();
  
  if (error) {
    console.error("Failed to queue backtest:", error);
    return errorResponse("Failed to queue backtest job");
  }
  
  return jsonResponse({ 
    job: {
      id: data.id,
      status: data.status,
      created_at: data.created_at
    }
  }, 201);
}

async function handleGetJob(
  supabase: ReturnType<typeof getSupabaseClient>,
  userId: string,
  jobId: string
) {
  const { data: job, error } = await supabase
    .from("strategy_backtest_jobs")
    .select("*")
    .eq("id", jobId)
    .eq("user_id", userId)
    .single();
  
  if (error || !job) {
    return errorResponse("Job not found", 404);
  }
  
  let result = null;
  if (job.status === "completed" && job.result_id) {
    const { data: resultData } = await supabase
      .from("strategy_backtest_results")
      .select("*")
      .eq("id", job.result_id)
      .single();
    result = resultData;
  }
  
  return jsonResponse({
    job: {
      id: job.id,
      strategy_id: job.strategy_id,
      status: job.status,
      error_message: job.error_message,
      started_at: job.started_at,
      completed_at: job.completed_at,
      created_at: job.created_at
    },
    result
  });
}

async function handleListJobs(
  supabase: ReturnType<typeof getSupabaseClient>,
  userId: string,
  url: URL
) {
  const status = url.searchParams.get("status");
  const limit = parseInt(url.searchParams.get("limit") || "20");
  
  let query = supabase
    .from("strategy_backtest_jobs")
    .select("*")
    .eq("user_id", userId)
    .order("created_at", { ascending: false })
    .limit(limit);
  
  if (status) {
    query = query.eq("status", status);
  }
  
  const { data, error } = await query;
  
  if (error) {
    return errorResponse(error.message);
  }
  
  // Get strategy names
  const jobs = data || [];
  const strategyIds = [...new Set(jobs.map(j => j.strategy_id).filter(Boolean))];
  const strategyNames: Record<string, string> = {};
  
  if (strategyIds.length > 0) {
    const { data: strategies } = await supabase
      .from("strategy_user_strategies")
      .select("id, name")
      .in("id", strategyIds);
    
    strategies?.forEach(s => {
      strategyNames[s.id] = s.name;
    });
  }
  
  const jobsWithNames = jobs.map(job => ({
    ...job,
    strategies: { name: strategyNames[job.strategy_id] || 'Strategy' }
  }));
  
  return jsonResponse({ jobs: jobsWithNames });
}
