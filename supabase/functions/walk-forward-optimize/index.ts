// walk-forward-optimize: Run walk-forward optimization for ML forecasters
// POST /walk-forward-optimize { symbol, horizon, forecaster, timeframe, windows? }
//
// Calls Python script to run walk-forward backtest and returns performance metrics.

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { corsResponse, handlePreflight } from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";

const PYTHON_SCRIPT_PATH = "/Users/ericpeterson/SwiftBolt_ML/ml/scripts/run_walk_forward.py";

interface WalkForwardRequest {
  symbol: string;
  horizon: string;
  forecaster?: string;
  timeframe?: string;
  windows?: {
    trainWindow?: number;
    testWindow?: number;
    stepSize?: number;
  };
}

interface WalkForwardResponse {
  symbol: string;
  horizon: string;
  forecaster: string;
  timeframe: string;
  period: {
    start: string;
    end: string;
  };
  windows: {
    trainWindow: number;
    testWindow: number;
    stepSize: number;
    testPeriods: number;
  };
  metrics: {
    accuracy: number;
    precision: number;
    recall: number;
    f1Score: number;
    sharpeRatio: number;
    sortinoRatio: number;
    maxDrawdown: number;
    winRate: number;
    profitFactor: number;
    totalTrades: number;
    winningTrades: number;
    losingTrades: number;
    avgWinSize: number;
    avgLossSize: number;
  };
  barsUsed: number;
  error?: string;
}

/**
 * Get Python script path from environment or use default
 */
function getPythonScriptPath(): string {
  return (
    Deno.env.get("WALK_FORWARD_SCRIPT_PATH") ||
    PYTHON_SCRIPT_PATH
  );
}

/**
 * Call Python script to run walk-forward optimization
 */
async function runWalkForward(request: WalkForwardRequest): Promise<WalkForwardResponse> {
  const scriptPath = getPythonScriptPath();
  
  // Build command arguments
  const args = [
    scriptPath,
    "--symbol",
    request.symbol,
    "--horizon",
    request.horizon,
    "--forecaster",
    request.forecaster || "baseline",
    "--timeframe",
    request.timeframe || "d1",
  ];
  
  // Add window parameters if provided
  if (request.windows?.trainWindow) {
    args.push("--train-window", String(request.windows.trainWindow));
  }
  if (request.windows?.testWindow) {
    args.push("--test-window", String(request.windows.testWindow));
  }
  if (request.windows?.stepSize) {
    args.push("--step-size", String(request.windows.stepSize));
  }
  
  const pythonCmd = new Deno.Command("python3", {
    args,
    stdout: "piped",
    stderr: "piped",
  });

  try {
    const { code, stdout, stderr } = await pythonCmd.output();

    if (code !== 0) {
      const errorText = new TextDecoder().decode(stderr);
      console.error(`Python script error: ${errorText}`);
      throw new Error(`Python script failed: ${errorText}`);
    }

    const output = new TextDecoder().decode(stdout);
    const result = JSON.parse(output) as WalkForwardResponse;

    if (result.error) {
      throw new Error(result.error);
    }

    return result;
  } catch (error) {
    console.error(`Error running Python script: ${error}`);
    throw error;
  }
}

serve(async (req: Request) => {
  const origin = req.headers.get("origin");

  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return handlePreflight(origin);
  }

  if (req.method !== "POST") {
    return corsResponse(
      { error: "Method not allowed. Use POST." },
      405,
      origin
    );
  }

  try {
    const body = await req.json() as WalkForwardRequest;

    // Validate required fields
    if (!body.symbol || !body.horizon) {
      return corsResponse(
        {
          error: "Missing required fields: symbol, horizon",
        },
        400,
        origin
      );
    }

    // Validate horizon
    const validHorizons = ["1D", "1W", "1M", "2M", "3M", "4M", "5M", "6M"];
    if (!validHorizons.includes(body.horizon)) {
      return corsResponse(
        {
          error: `Invalid horizon: ${body.horizon}. Valid: ${validHorizons.join(", ")}`,
        },
        400,
        origin
      );
    }

    // Validate forecaster
    const validForecasters = ["baseline", "enhanced"];
    if (body.forecaster && !validForecasters.includes(body.forecaster)) {
      return corsResponse(
        {
          error: `Invalid forecaster: ${body.forecaster}. Valid: ${validForecasters.join(", ")}`,
        },
        400,
        origin
      );
    }

    console.log(
      `[WalkForwardOptimize] Running ${body.forecaster || "baseline"} for ${body.symbol} with horizon ${body.horizon}`
    );

    // Run walk-forward optimization
    const result = await runWalkForward(body);

    if (result.error) {
      return corsResponse(
        { error: result.error, symbol: body.symbol, horizon: body.horizon },
        500,
        origin
      );
    }

    console.log(
      `[WalkForwardOptimize] Complete: ${(result.metrics.accuracy * 100).toFixed(2)}% accuracy, ${result.metrics.totalTrades} trades`
    );

    return corsResponse(result, 200, origin);
  } catch (error) {
    console.error("[WalkForwardOptimize] Error:", error);
    return corsResponse(
      {
        error:
          error instanceof Error ? error.message : "Internal server error",
      },
      500,
      origin
    );
  }
});
