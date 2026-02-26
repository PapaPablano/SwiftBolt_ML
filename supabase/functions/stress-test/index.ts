// stress-test: Run stress test on portfolio
// POST /stress-test { positions, prices, scenario?, customShocks?, varLevel? }
//
// Calls Python script to run stress test and returns portfolio impact.

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { corsResponse, handlePreflight } from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";
import { callFastApi } from "../_shared/fastapi-client.ts";

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
 * Call FastAPI to run stress test
 */
async function runStressTest(
  request: StressTestRequest,
): Promise<StressTestResponse> {
  return await callFastApi<StressTestResponse>(
    "/api/v1/stress-test",
    {
      method: "POST",
      body: JSON.stringify({
        positions: request.positions,
        prices: request.prices,
        scenario: request.scenario,
        customShocks: request.customShocks,
        varLevel: request.varLevel,
      }),
    },
    30000, // 30 second timeout for stress tests
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
      origin,
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
        origin,
      );
    }

    if (!body.prices || Object.keys(body.prices).length === 0) {
      return corsResponse(
        {
          error: "Missing or empty prices dictionary",
        },
        400,
        origin,
      );
    }

    // Validate that all positions have prices
    const missingPrices = Object.keys(body.positions).filter(
      (symbol) => !(symbol in body.prices),
    );
    if (missingPrices.length > 0) {
      return corsResponse(
        {
          error: `Missing prices for symbols: ${missingPrices.join(", ")}`,
        },
        400,
        origin,
      );
    }

    // Validate scenario or custom shocks provided
    if (!body.scenario && !body.customShocks) {
      return corsResponse(
        {
          error: "Either scenario or customShocks must be provided",
        },
        400,
        origin,
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
          error: `Invalid scenario: ${body.scenario}. Valid: ${
            validScenarios.join(", ")
          }`,
        },
        400,
        origin,
      );
    }

    const scenarioName = body.scenario || "custom";
    console.log(
      `[StressTest] Running ${scenarioName} scenario for ${
        Object.keys(body.positions).length
      } positions`,
    );

    // Run stress test
    const result = await runStressTest(body);

    if (result.error) {
      return corsResponse(
        { error: result.error, scenario: scenarioName },
        500,
        origin,
      );
    }

    console.log(
      `[StressTest] Complete: ${
        result.portfolio.changePercent.toFixed(2)
      }% impact, ${result.risk.severity} severity`,
    );

    return corsResponse(result, 200, origin);
  } catch (error) {
    console.error("[StressTest] Error:", error);
    return corsResponse(
      {
        error: error instanceof Error ? error.message : "Internal server error",
      },
      500,
      origin,
    );
  }
});
