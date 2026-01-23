// backtest-strategy: Run backtest for a trading strategy
// POST /backtest-strategy { symbol, strategy, startDate, endDate, params }
//
// Calls Python script to run backtest and returns performance metrics and trade history.

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { corsResponse, handlePreflight } from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";
import { callFastApi } from "../_shared/fastapi-client.ts";

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
 * Call FastAPI to run backtest
 */
async function runBacktest(request: BacktestRequest): Promise<BacktestResponse> {
  return await callFastApi<BacktestResponse>(
    "/api/v1/backtest-strategy",
    {
      method: "POST",
      body: JSON.stringify({
        symbol: request.symbol,
        strategy: request.strategy,
        startDate: request.startDate,
        endDate: request.endDate,
        timeframe: request.timeframe,
        initialCapital: request.initialCapital,
        params: request.params,
      }),
    },
    60000 // 60 second timeout for backtests
  );
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
