// backtest-strategy: UNIFIED backtest API
// POST - Queue a backtest job (returns job_id)
// GET ?id=xxx - Get job status and results when completed
//
// Supports both preset strategies (supertrend_ai, sma_crossover, buy_and_hold)
// and builder strategies (strategy_id UUID from strategy_user_strategies).
// Worker processes jobs and writes to strategy_backtest_jobs + strategy_backtest_results.

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { corsResponse, handlePreflight } from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";

const VALID_PRESET_STRATEGIES = [
  "supertrend_ai",
  "sma_crossover",
  "buy_and_hold",
];

function getUserIdFromRequest(req: Request): string | null {
  const authHeader = req.headers.get("Authorization");
  if (!authHeader) return null;
  const token = authHeader.replace("Bearer ", "");
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const payload = JSON.parse(atob(parts[1]));
    return payload.sub || null;
  } catch {
    return null;
  }
}

serve(async (req: Request) => {
  const origin = req.headers.get("origin");

  if (req.method === "OPTIONS") {
    return handlePreflight(origin);
  }

  const supabase = getSupabaseClient();
  let userId = getUserIdFromRequest(req);
  if (!userId) {
    userId = "00000000-0000-0000-0000-000000000001"; // demo fallback
  }

  const url = new URL(req.url);
  const jobId = url.searchParams.get("id");

  try {
    if (req.method === "POST") {
      return await handleQueueBacktest(supabase, userId, req, origin);
    }
    if (req.method === "GET" && jobId) {
      return await handleGetJobStatus(supabase, userId, jobId, origin);
    }
    if (req.method === "GET") {
      return corsResponse(
        { error: "Missing query param: id (job_id)" },
        400,
        origin,
      );
    }
    return corsResponse({ error: "Method not allowed" }, 405, origin);
  } catch (err) {
    console.error("[BacktestStrategy] Error:", err);
    return corsResponse(
      {
        error: err instanceof Error ? err.message : "Internal server error",
      },
      500,
      origin,
    );
  }
});

async function handleQueueBacktest(
  supabase: ReturnType<typeof getSupabaseClient>,
  userId: string,
  req: Request,
  origin: string | null,
): Promise<Response> {
  const body = (await req.json()) as Record<string, unknown>;

  const symbol = (body.symbol as string) || "AAPL";
  const startDate = (body.startDate as string) || (body.start_date as string);
  const endDate = (body.endDate as string) || (body.end_date as string);
  const strategyId = body.strategy_id as string | undefined;
  const strategyPreset = body.strategy as string | undefined;
  const timeframe = (body.timeframe as string) || "d1";
  const initialCapital = (body.initialCapital as number) ?? 10000;
  const params = (body.params as Record<string, unknown>) ||
    (body.parameters as Record<string, unknown>) || {};

  if (!startDate || !endDate) {
    return corsResponse(
      { error: "Missing required fields: startDate and endDate (YYYY-MM-DD)" },
      400,
      origin,
    );
  }

  let strategyConfig: Record<string, unknown> | null = null;
  if (strategyId) {
    const { data: strategy, error } = await supabase
      .from("strategy_user_strategies")
      .select("id, config")
      .eq("id", strategyId)
      .or(`user_id.eq.${userId},user_id.is.null`)
      .single();

    if (error || !strategy) {
      return corsResponse({ error: "Strategy not found" }, 404, origin);
    }
    strategyConfig = (strategy.config as Record<string, unknown>) || null;
  } else if (strategyPreset) {
    if (!VALID_PRESET_STRATEGIES.includes(strategyPreset)) {
      return corsResponse(
        {
          error: `Invalid strategy: ${strategyPreset}. Valid: ${
            VALID_PRESET_STRATEGIES.join(", ")
          }`,
        },
        400,
        origin,
      );
    }
  } else {
    return corsResponse(
      { error: "Provide either strategy_id (UUID) or strategy (preset name)" },
      400,
      origin,
    );
  }

  const start = new Date(startDate);
  const end = new Date(endDate);
  if (isNaN(start.getTime()) || isNaN(end.getTime())) {
    return corsResponse(
      { error: "Invalid date format. Use YYYY-MM-DD" },
      400,
      origin,
    );
  }
  if (start >= end) {
    return corsResponse(
      { error: "Start date must be before end date" },
      400,
      origin,
    );
  }

  const parameters: Record<string, unknown> = {
    ...params,
    initialCapital,
    timeframe,
  };
  if (strategyPreset) {
    parameters.strategy = strategyPreset;
  }
  // Builder strategy: merge riskManagement from config so worker uses your stop loss / take profit
  if (strategyId && strategyConfig?.riskManagement) {
    const rm = strategyConfig.riskManagement as Record<
      string,
      { type?: string; value?: number }
    >;
    const sl = rm?.stopLoss;
    const tp = rm?.takeProfit;
    if (sl?.type === "percent" && typeof sl.value === "number") {
      parameters.stop_loss_pct = sl.value;
    }
    if (tp?.type === "percent" && typeof tp.value === "number") {
      parameters.take_profit_pct = tp.value;
    }
  }

  const { data: job, error } = await supabase
    .from("strategy_backtest_jobs")
    .insert({
      user_id: userId,
      strategy_id: strategyId || null,
      symbol,
      start_date: startDate,
      end_date: endDate,
      parameters,
      status: "pending",
    })
    .select("id, status, created_at")
    .single();

  if (error) {
    console.error("[BacktestStrategy] Failed to queue job:", error);
    return corsResponse({ error: "Failed to queue backtest job" }, 500, origin);
  }

  console.log(
    `[BacktestStrategy] Queued job ${job.id} for ${symbol} (${
      strategyPreset || strategyId
    })`,
  );

  // Trigger the worker immediately (fire-and-forget) so the job is processed
  // without requiring an external cron. Uses the service-role key so the worker
  // can update job status even with RLS enabled.
  const workerUrl = `${
    Deno.env.get("SUPABASE_URL")
  }/functions/v1/strategy-backtest-worker`;
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
  if (workerUrl && serviceKey) {
    fetch(workerUrl, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${serviceKey}`,
        "Content-Type": "application/json",
        "x-trigger-source": "backtest-strategy",
      },
      body: JSON.stringify({ triggered_job_id: job.id }),
    }).catch((e) =>
      console.warn("[BacktestStrategy] Worker trigger warning:", e)
    );
  } else {
    console.warn(
      "[BacktestStrategy] SUPABASE_SERVICE_ROLE_KEY not set — worker not triggered automatically",
    );
  }

  return corsResponse(
    {
      job_id: job.id,
      status: job.status,
      created_at: job.created_at,
    },
    201,
    origin,
  );
}

async function handleGetJobStatus(
  supabase: ReturnType<typeof getSupabaseClient>,
  userId: string,
  jobId: string,
  origin: string | null,
): Promise<Response> {
  const { data: job, error } = await supabase
    .from("strategy_backtest_jobs")
    .select("*")
    .eq("id", jobId)
    .eq("user_id", userId)
    .single();

  if (error || !job) {
    return corsResponse({ error: "Job not found" }, 404, origin);
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

  return corsResponse(
    {
      job_id: job.id,
      status: job.status,
      created_at: job.created_at,
      started_at: job.started_at,
      completed_at: job.completed_at,
      error: job.error_message,
      result,
    },
    200,
    origin,
  );
}
