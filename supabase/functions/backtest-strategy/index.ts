// backtest-strategy: Run backtest for a trading strategy
// POST /backtest-strategy { symbol, strategy, startDate, endDate, params }
//
// Calls Python script to run backtest and returns performance metrics and trade history.

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { corsResponse, handlePreflight } from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";

const PYTHON_SCRIPT_PATH = "/Users/ericpeterson/SwiftBolt_ML/ml/scripts/run_backtest.py";

interface BacktestRequest {
  symbol: string;
  strategy: string;
  startDate: string;
  endDate: string;
  timeframe?: string;
  initialCapital?: number;
  params?: Record<string, any>;
}

interface BacktestResponse {
  symbol: string;
  strategy: string;
  period: {
    start: string;
    end: string;
  };
  initialCapital: number;
  finalValue: number;
  totalReturn: number;
  metrics: {
    sharpeRatio: number | null;
    maxDrawdown: number | null;
    winRate: number | null;
    totalTrades: number;
  };
  equityCurve: Array<{
    date: string;
    value: number;
  }>;
  trades: Array<{
    date: string;
    symbol: string;
    action: string;
    quantity: number;
    price: number;
    pnl: number | null;
  }>;
  barsUsed: number;
  error?: string;
}

/**
 * Get Python script path from environment or use default
 */
function getPythonScriptPath(): string {
  return (
    Deno.env.get("BACKTEST_SCRIPT_PATH") ||
    PYTHON_SCRIPT_PATH
  );
}

/**
 * Call Python script to run backtest
 */
async function runBacktest(request: BacktestRequest): Promise<BacktestResponse> {
  const scriptPath = getPythonScriptPath();
  
  // Build command arguments
  const args = [
    scriptPath,
    "--symbol",
    request.symbol,
    "--strategy",
    request.strategy,
    "--start",
    request.startDate,
    "--end",
    request.endDate,
    "--timeframe",
    request.timeframe || "d1",
    "--capital",
    String(request.initialCapital || 10000),
  ];
  
  // Add strategy parameters if provided
  if (request.params && Object.keys(request.params).length > 0) {
    args.push("--params", JSON.stringify(request.params));
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
    const result = JSON.parse(output) as BacktestResponse;

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
    const body = await req.json() as BacktestRequest;

    // Validate required fields
    if (!body.symbol || !body.strategy || !body.startDate || !body.endDate) {
      return corsResponse(
        {
          error:
            "Missing required fields: symbol, strategy, startDate, endDate",
        },
        400,
        origin
      );
    }

    // Validate strategy
    const validStrategies = ["supertrend_ai", "sma_crossover", "buy_and_hold"];
    if (!validStrategies.includes(body.strategy)) {
      return corsResponse(
        {
          error: `Invalid strategy: ${body.strategy}. Valid: ${validStrategies.join(", ")}`,
        },
        400,
        origin
      );
    }

    // Validate dates
    const startDate = new Date(body.startDate);
    const endDate = new Date(body.endDate);
    if (isNaN(startDate.getTime()) || isNaN(endDate.getTime())) {
      return corsResponse(
        { error: "Invalid date format. Use YYYY-MM-DD" },
        400,
        origin
      );
    }

    if (startDate >= endDate) {
      return corsResponse(
        { error: "Start date must be before end date" },
        400,
        origin
      );
    }

    console.log(
      `[BacktestStrategy] Running ${body.strategy} for ${body.symbol} from ${body.startDate} to ${body.endDate}`
    );

    // Run backtest
    const result = await runBacktest(body);

    if (result.error) {
      return corsResponse(
        { error: result.error, symbol: body.symbol, strategy: body.strategy },
        500,
        origin
      );
    }

    console.log(
      `[BacktestStrategy] Backtest complete: ${result.totalReturn.toFixed(2)}% return, ${result.metrics.totalTrades} trades`
    );

    return corsResponse(result, 200, origin);
  } catch (error) {
    console.error("[BacktestStrategy] Error:", error);
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
