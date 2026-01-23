// greeks-surface: Get 3D Greeks surface data for visualization
// POST /greeks-surface { symbol, underlyingPrice, riskFreeRate, volatility, ... }
//
// Calls FastAPI to calculate Greeks surface and returns 3D surface data.

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { corsResponse, handlePreflight } from "../_shared/cors.ts";
import { callFastApi } from "../_shared/fastapi-client.ts";

interface GreeksSurfaceRequest {
  symbol: string;
  underlyingPrice: number;
  riskFreeRate?: number;
  volatility: number;
  optionType?: string;
  strikeRange?: [number, number];
  timeRange?: [number, number];
  nStrikes?: number;
  nTimes?: number;
  greek?: string;
}

interface GreeksSurfaceResponse {
  symbol: string;
  underlyingPrice: number;
  riskFreeRate: number;
  volatility: number;
  optionType: string;
  strikes: number[];
  times: number[];
  delta: number[][];
  gamma: number[][];
  theta: number[][];
  vega: number[][];
  rho: number[][];
}

serve(async (req) => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return handlePreflight();
  }

  try {
    const request: GreeksSurfaceRequest = await req.json();

    if (!request.symbol || !request.underlyingPrice || !request.volatility) {
      return corsResponse(
        { error: "symbol, underlyingPrice, and volatility are required" },
        { status: 400 }
      );
    }

    // Call FastAPI endpoint
    const response = await callFastApi<GreeksSurfaceResponse>(
      "/api/v1/greeks-surface",
      {
        method: "POST",
        body: JSON.stringify({
          symbol: request.symbol.toUpperCase(),
          underlyingPrice: request.underlyingPrice,
          riskFreeRate: request.riskFreeRate || 0.05,
          volatility: request.volatility,
          optionType: request.optionType || "call",
          strikeRange: request.strikeRange || [0.7, 1.3],
          timeRange: request.timeRange || [0.01, 1.0],
          nStrikes: request.nStrikes || 50,
          nTimes: request.nTimes || 50,
          greek: request.greek,
        }),
      }
    );

    return corsResponse(response);
  } catch (error) {
    console.error("Error getting Greeks surface:", error);
    return corsResponse(
      {
        error: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 }
    );
  }
});
