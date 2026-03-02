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
import { validateSLTPBounds } from "../_shared/validators.ts";

const VALID_PRESET_STRATEGIES = [
  "supertrend_ai",
  "sma_crossover",
  "buy_and_hold",
];

serve(async (req: Request) => {
  const origin = req.headers.get("origin");

  if (req.method === "OPTIONS") {
    return handlePreflight(origin);
  }

  const supabase = getSupabaseClient();

  // Backtesting is read-only computation — no user data sensitivity.
  // Auth is optional: if a valid JWT is present, tag the job with user_id;
  // otherwise, use null so RLS allows anonymous inserts.
  let userId: string | null = null;
  const authHeader = req.headers.get("Authorization") ?? "";
  if (authHeader && authHeader !== "Bearer " && !authHeader.endsWith("eyJ")) {
    try {
      const { data: { user } } = await supabase.auth.getUser(
        authHeader.replace("Bearer ", ""),
      );
      if (user) userId = user.id;
    } catch {
      // Auth failed — proceed as anonymous
    }
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
    if (req.method === "PATCH") {
      return await handleCancelJob(supabase, userId, req, origin);
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
    console.error("[BacktestStrategy] Unexpected error:", err);
    return corsResponse({ error: "An internal error occurred" }, 500, origin);
  }
});

async function handleQueueBacktest(
  supabase: ReturnType<typeof getSupabaseClient>,
  userId: string | null,
  req: Request,
  origin: string | null,
): Promise<Response> {
  const body = (await req.json()) as Record<string, unknown>;

  const symbol = (body.symbol as string) || "AAPL";
  const startDate = (body.startDate as string) || (body.start_date as string);
  const endDate = (body.endDate as string) || (body.end_date as string);
  const strategyId = body.strategy_id as string | undefined;
  const strategyPreset = body.strategy as string | undefined;
  const inlineConfig = body.strategy_config as
    | Record<string, unknown>
    | undefined;
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

  let strategyConfig: Record<string, unknown> | null = inlineConfig || null;
  if (!strategyConfig && strategyId) {
    // Build filter: if authenticated, match user_id or null; if anonymous, only null
    const strategyFilter = userId
      ? `user_id.eq.${userId},user_id.is.null`
      : `user_id.is.null`;

    const { data: strategy, error } = await supabase
      .from("strategy_user_strategies")
      .select("id, config")
      .eq("id", strategyId)
      .or(strategyFilter)
      .single();

    if (error || !strategy) {
      return corsResponse({ error: "Strategy not found" }, 404, origin);
    }
    strategyConfig = (strategy.config as Record<string, unknown>) || null;
  } else if (!strategyConfig && !strategyId && strategyPreset) {
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
  } else if (!strategyConfig && !strategyId && !strategyPreset) {
    return corsResponse(
      {
        error:
          "Provide strategy_config, strategy_id (UUID), or strategy (preset name)",
      },
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
  // Store inline config in parameters so the worker can use it directly
  if (strategyConfig) {
    parameters.strategy_config = strategyConfig;
  }

  // Builder strategy: merge riskManagement from config so worker uses your stop loss / take profit
  if (strategyConfig?.riskManagement) {
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

    // Validate SL/TP bounds before queuing the job
    const slPct = parameters.stop_loss_pct as number | undefined;
    const tpPct = parameters.take_profit_pct as number | undefined;
    if (slPct != null && tpPct != null) {
      const validation = validateSLTPBounds({ slPct, tpPct });
      if (!validation.valid) {
        return corsResponse(
          { error: `Invalid risk parameters: ${validation.errors.join("; ")}` },
          400,
          origin,
        );
      }
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

  // Trigger the worker and await the response so we know if it started.
  // Uses the service-role key so the worker can update job status even with RLS.
  let workerTriggered = false;
  const workerUrl = `${
    Deno.env.get("SUPABASE_URL")
  }/functions/v1/strategy-backtest-worker`;
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
  const gatewayKey = Deno.env.get("SB_GATEWAY_KEY") ?? "";

  if (workerUrl && serviceKey && gatewayKey) {
    const triggerWorker = async (): Promise<boolean> => {
      try {
        const res = await fetch(workerUrl, {
          method: "POST",
          headers: {
            "Authorization": `Bearer ${serviceKey}`,
            "Content-Type": "application/json",
            "X-SB-Gateway-Key": gatewayKey,
            "x-trigger-source": "backtest-strategy",
          },
          body: JSON.stringify({ triggered_job_id: job.id }),
        });
        if (res.ok) {
          console.log(
            `[BacktestStrategy] Worker triggered for job ${job.id} (status ${res.status})`,
          );
          return true;
        }
        console.warn(
          `[BacktestStrategy] Worker trigger returned ${res.status}`,
        );
        return false;
      } catch (e) {
        console.warn("[BacktestStrategy] Worker trigger failed:", e);
        return false;
      }
    };

    workerTriggered = await triggerWorker();
    if (!workerTriggered) {
      console.warn(
        "[BacktestStrategy] Retrying worker trigger for job",
        job.id,
      );
      workerTriggered = await triggerWorker();
    }
  } else {
    console.warn(
      "[BacktestStrategy] Missing env: SUPABASE_SERVICE_ROLE_KEY or SB_GATEWAY_KEY — worker not triggered",
    );
  }

  return corsResponse(
    {
      job_id: job.id,
      status: job.status,
      created_at: job.created_at,
      worker_triggered: workerTriggered,
    },
    201,
    origin,
  );
}

async function handleCancelJob(
  supabase: ReturnType<typeof getSupabaseClient>,
  userId: string | null,
  req: Request,
  origin: string | null,
): Promise<Response> {
  if (!userId) {
    return corsResponse(
      { error: "Authentication required to cancel jobs" },
      401,
      origin,
    );
  }

  const body = (await req.json()) as Record<string, unknown>;
  const jobId = body.job_id as string;
  if (!jobId) {
    return corsResponse(
      { error: "Missing required field: job_id" },
      400,
      origin,
    );
  }

  // Only cancel jobs owned by this user that are in a cancellable state
  const { data, error } = await supabase
    .from("strategy_backtest_jobs")
    .update({
      status: "cancelled",
      completed_at: new Date().toISOString(),
      error_message: "Cancelled by user",
    })
    .eq("id", jobId)
    .eq("user_id", userId)
    .in("status", ["pending", "running"])
    .select("id, status")
    .single();

  if (error || !data) {
    return corsResponse(
      {
        error:
          "Job not found, not owned by you, or already in a terminal state",
      },
      404,
      origin,
    );
  }

  console.log(`[BacktestStrategy] Job ${jobId} cancelled by user ${userId}`);
  return corsResponse({ job_id: data.id, status: data.status }, 200, origin);
}

async function handleGetJobStatus(
  supabase: ReturnType<typeof getSupabaseClient>,
  userId: string | null,
  jobId: string,
  origin: string | null,
): Promise<Response> {
  // Clean up stale jobs: running for >5 minutes with no recent heartbeat
  const staleQuery = supabase
    .from("strategy_backtest_jobs")
    .update({
      status: "failed",
      error_message: "Worker timed out",
      completed_at: new Date().toISOString(),
    })
    .eq("status", "running")
    .lt("started_at", new Date(Date.now() - 5 * 60 * 1000).toISOString())
    .or(
      `heartbeat_at.is.null,heartbeat_at.lt.${
        new Date(Date.now() - 5 * 60 * 1000).toISOString()
      }`,
    );
  if (userId) {
    staleQuery.eq("user_id", userId);
  } else {
    staleQuery.is("user_id", null);
  }
  await staleQuery;

  let jobQuery = supabase
    .from("strategy_backtest_jobs")
    .select("*")
    .eq("id", jobId);
  if (userId) {
    jobQuery = jobQuery.eq("user_id", userId);
  } else {
    jobQuery = jobQuery.is("user_id", null);
  }
  const { data: job, error } = await jobQuery.single();

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
