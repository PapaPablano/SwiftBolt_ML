// portfolio-optimize: Optimize portfolio allocation
// POST /portfolio-optimize { symbols, method, parameters }
//
// Calls Python script to optimize portfolio and returns allocation weights and metrics.

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { corsResponse, handlePreflight } from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";

const PYTHON_SCRIPT_PATH = "/Users/ericpeterson/SwiftBolt_ML/ml/scripts/optimize_portfolio.py";

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
 * Get Python script path from environment or use default
 */
function getPythonScriptPath(): string {
  return (
    Deno.env.get("PORTFOLIO_OPTIMIZE_SCRIPT_PATH") ||
    PYTHON_SCRIPT_PATH
  );
}

/**
 * Call Python script to optimize portfolio
 */
async function optimizePortfolio(request: PortfolioOptimizeRequest): Promise<PortfolioOptimizeResponse> {
  const scriptPath = getPythonScriptPath();
  
  // Build command arguments
  const args = [
    scriptPath,
    "--symbols",
    request.symbols.join(","),
    "--method",
    request.method,
    "--timeframe",
    request.timeframe || "d1",
    "--lookback-days",
    String(request.lookbackDays || 252),
    "--risk-free-rate",
    String(request.riskFreeRate || 0.02),
    "--min-weight",
    String(request.minWeight || 0.0),
    "--max-weight",
    String(request.maxWeight || 1.0),
  ];
  
  // Add target return if provided (for efficient portfolio)
  if (request.targetReturn !== undefined) {
    args.push("--target-return", String(request.targetReturn));
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
    const result = JSON.parse(output) as PortfolioOptimizeResponse;

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
