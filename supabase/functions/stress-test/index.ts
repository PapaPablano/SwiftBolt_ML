// stress-test: Run stress test on portfolio
// POST /stress-test { positions, prices, scenario?, customShocks?, varLevel? }
//
// Calls Python script to run stress test and returns portfolio impact.

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { corsResponse, handlePreflight } from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";

const PYTHON_SCRIPT_PATH = "/Users/ericpeterson/SwiftBolt_ML/ml/scripts/run_stress_test.py";

interface StressTestRequest {
  positions: Record<string, number>;
  prices: Record<string, number>;
  scenario?: string;
  customShocks?: Record<string, number>;
  varLevel?: number;
}

interface StressTestResponse {
  scenario: string;
  portfolio: {
    currentValue: number;
    change: number;
    changePercent: number;
  };
  risk: {
    varLevel: number;
    varBreached: boolean;
    severity: string;
  };
  positionChanges: Record<string, number>;
  positions: Record<string, number>;
  prices: Record<string, number>;
  error?: string;
}

/**
 * Get Python script path from environment or use default
 */
function getPythonScriptPath(): string {
  return (
    Deno.env.get("STRESS_TEST_SCRIPT_PATH") ||
    PYTHON_SCRIPT_PATH
  );
}

/**
 * Call Python script to run stress test
 */
async function runStressTest(request: StressTestRequest): Promise<StressTestResponse> {
  const scriptPath = getPythonScriptPath();
  
  // Build command arguments
  const args = [
    scriptPath,
    "--positions",
    JSON.stringify(request.positions),
    "--prices",
    JSON.stringify(request.prices),
    "--var-level",
    String(request.varLevel || 0.05),
  ];
  
  // Add scenario or custom shocks
  if (request.scenario) {
    args.push("--scenario", request.scenario);
  } else if (request.customShocks) {
    args.push("--custom-shocks", JSON.stringify(request.customShocks));
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
    const result = JSON.parse(output) as StressTestResponse;

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
    const body = await req.json() as StressTestRequest;

    // Validate required fields
    if (!body.positions || Object.keys(body.positions).length === 0) {
      return corsResponse(
        {
          error: "Missing or empty positions dictionary",
        },
        400,
        origin
      );
    }

    if (!body.prices || Object.keys(body.prices).length === 0) {
      return corsResponse(
        {
          error: "Missing or empty prices dictionary",
        },
        400,
        origin
      );
    }

    // Validate that all positions have prices
    const missingPrices = Object.keys(body.positions).filter(
      (symbol) => !(symbol in body.prices)
    );
    if (missingPrices.length > 0) {
      return corsResponse(
        {
          error: `Missing prices for symbols: ${missingPrices.join(", ")}`,
        },
        400,
        origin
      );
    }

    // Validate scenario or custom shocks provided
    if (!body.scenario && !body.customShocks) {
      return corsResponse(
        {
          error: "Either scenario or customShocks must be provided",
        },
        400,
        origin
      );
    }

    // Validate historical scenarios
    const validScenarios = [
      "2008_financial_crisis",
      "2020_covid_crash",
      "2011_eu_debt_crisis",
      "1987_black_monday",
      "2015_china_devaluation",
    ];
    if (body.scenario && !validScenarios.includes(body.scenario)) {
      return corsResponse(
        {
          error: `Invalid scenario: ${body.scenario}. Valid: ${validScenarios.join(", ")}`,
        },
        400,
        origin
      );
    }

    const scenarioName = body.scenario || "custom";
    console.log(
      `[StressTest] Running ${scenarioName} scenario for ${Object.keys(body.positions).length} positions`
    );

    // Run stress test
    const result = await runStressTest(body);

    if (result.error) {
      return corsResponse(
        { error: result.error, scenario: scenarioName },
        500,
        origin
      );
    }

    console.log(
      `[StressTest] Complete: ${result.portfolio.changePercent.toFixed(2)}% impact, ${result.risk.severity} severity`
    );

    return corsResponse(result, 200, origin);
  } catch (error) {
    console.error("[StressTest] Error:", error);
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
