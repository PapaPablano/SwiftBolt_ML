// volatility-surface: Get 3D volatility surface data for visualization
// POST /volatility-surface { symbol, slices, ... }
//
// Calls FastAPI to fit and return volatility surface data.

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { corsResponse, handlePreflight } from "../_shared/cors.ts";
import { callFastApi } from "../_shared/fastapi-client.ts";

interface VolatilitySlice {
  maturityDays: number;
  strikes: number[];
  impliedVols: number[];
  forwardPrice?: number;
}

interface VolatilitySurfaceRequest {
  symbol: string;
  slices: VolatilitySlice[];
  nStrikes?: number;
  nMaturities?: number;
}

interface VolatilitySurfaceResponse {
  symbol: string;
  strikes: number[];
  maturities: number[];
  impliedVols: number[][];
  strikeRange: [number, number];
  maturityRange: [number, number];
}

serve(async (req) => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return handlePreflight();
  }

  try {
    const request: VolatilitySurfaceRequest = await req.json();

    if (!request.symbol || !request.slices || request.slices.length === 0) {
      return corsResponse(
        { error: "symbol and slices are required" },
        { status: 400 },
      );
    }

    // Call FastAPI endpoint
    const response = await callFastApi<VolatilitySurfaceResponse>(
      "/api/v1/volatility-surface",
      {
        method: "POST",
        body: JSON.stringify({
          symbol: request.symbol.toUpperCase(),
          slices: request.slices,
          nStrikes: request.nStrikes || 50,
          nMaturities: request.nMaturities || 30,
        }),
      },
    );

    return corsResponse(response);
  } catch (error) {
    console.error("Error getting volatility surface:", error);
    return corsResponse(
      {
        error: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 },
    );
  }
});
