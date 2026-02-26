// forecast-quality: Get forecast quality metrics for a symbol
// POST /forecast-quality { symbol, horizon?, timeframe? }
//
// Calls FastAPI to get forecast quality metrics and returns quality score, confidence, and issues.

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { corsResponse, handlePreflight } from "../_shared/cors.ts";
import { callFastApi } from "../_shared/fastapi-client.ts";

interface ForecastQualityRequest {
  symbol: string;
  horizon?: string;
  timeframe?: string;
}

interface QualityIssue {
  level: string;
  type: string;
  message: string;
  action: string;
}

interface ForecastQualityResponse {
  symbol: string;
  horizon: string;
  timeframe: string;
  qualityScore: number;
  confidence: number;
  modelAgreement: number;
  issues: QualityIssue[];
  timestamp: string;
}

serve(async (req) => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return handlePreflight();
  }

  try {
    const request: ForecastQualityRequest = await req.json();

    if (!request.symbol) {
      return corsResponse(
        { error: "symbol is required" },
        { status: 400 },
      );
    }

    // Call FastAPI endpoint
    const response = await callFastApi<ForecastQualityResponse>(
      "/api/v1/forecast-quality",
      {
        method: "POST",
        body: JSON.stringify({
          symbol: request.symbol.toUpperCase(),
          horizon: request.horizon || "1D",
          timeframe: request.timeframe || "d1",
        }),
      },
    );

    return corsResponse(response);
  } catch (error) {
    console.error("Error getting forecast quality:", error);
    return corsResponse(
      {
        error: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 },
    );
  }
});
