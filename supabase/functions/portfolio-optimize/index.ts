// portfolio-optimize: Optimize portfolio allocation
// POST /portfolio-optimize { symbols, method, parameters }
//
// Calls Python script to optimize portfolio and returns allocation weights and metrics.

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { corsResponse, handlePreflight } from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";
import { callFastApi } from "../_shared/fastapi-client.ts";

interface PortfolioOptimizeRequest {
  symbols: string[];
  method: string;
  timeframe?: string;
  lookbackDays?: number;
  riskFreeRate?: number;
  targetReturn?: number;
  minWeight?: number;
  maxWeight?: number;
}

interface PortfolioOptimizeResponse {
  symbols: string[];
  method: string;
  timeframe: string;
  lookbackDays: number;
  allocation: {
    weights: Record<string, number>;
    expectedReturn: number;
    volatility: number;
    sharpeRatio: number;
  };
  parameters: {
    riskFreeRate: number;
    minWeight: number;
    maxWeight: number;
    targetReturn: number | null;
  };
  error?: string;
}

/**
 * Call FastAPI to optimize portfolio
 */
async function optimizePortfolio(request: PortfolioOptimizeRequest): Promise<PortfolioOptimizeResponse> {
  return await callFastApi<PortfolioOptimizeResponse>(
    "/api/v1/portfolio-optimize",
    {
      method: "POST",
      body: JSON.stringify({
        symbols: request.symbols,
        method: request.method,
        lookbackDays: request.lookbackDays,
        riskFreeRate: request.riskFreeRate,
        targetReturn: request.targetReturn,
        minWeight: request.minWeight,
        maxWeight: request.maxWeight,
      }),
    },
    60000 // 60 second timeout for portfolio optimization
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
    const body = await req.json() as PortfolioOptimizeRequest;

    // Validate required fields
    if (!body.symbols || !Array.isArray(body.symbols) || body.symbols.length === 0) {
      return corsResponse(
        {
          error: "Missing or invalid symbols array",
        },
        400,
        origin
      );
    }

    if (!body.method) {
      return corsResponse(
        {
          error: "Missing required field: method",
        },
        400,
        origin
      );
    }

    // Validate method
    const validMethods = ["max_sharpe", "min_variance", "risk_parity", "efficient"];
    if (!validMethods.includes(body.method)) {
      return corsResponse(
        {
          error: `Invalid method: ${body.method}. Valid: ${validMethods.join(", ")}`,
        },
        400,
        origin
      );
    }

    // Validate efficient portfolio requires target return
    if (body.method === "efficient" && body.targetReturn === undefined) {
      return corsResponse(
        {
          error: "targetReturn required for efficient portfolio method",
        },
        400,
        origin
      );
    }

    console.log(
      `[PortfolioOptimize] Optimizing ${body.symbols.length} symbols using ${body.method}`
    );

    // Optimize portfolio
    const result = await optimizePortfolio(body);

    if (result.error) {
      return corsResponse(
        { error: result.error, symbols: body.symbols, method: body.method },
        500,
        origin
      );
    }

    console.log(
      `[PortfolioOptimize] Complete: ${result.allocation.sharpeRatio.toFixed(2)} Sharpe, ${result.allocation.expectedReturn.toFixed(2)}% return`
    );

    return corsResponse(result, 200, origin);
  } catch (error) {
    console.error("[PortfolioOptimize] Error:", error);
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
