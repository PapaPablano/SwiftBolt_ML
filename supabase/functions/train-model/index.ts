// train-model: Train ML model for a symbol/timeframe
// POST /train-model { symbol, timeframe?, lookbackDays? }
//
// Calls FastAPI to train ensemble model and returns training metrics.

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { corsResponse, handlePreflight } from "../_shared/cors.ts";
import { callFastApi } from "../_shared/fastapi-client.ts";

interface TrainModelRequest {
  symbol: string;
  timeframe?: string;
  lookbackDays?: number;
}

interface TrainingMetrics {
  trainAccuracy: number;
  validationAccuracy: number;
  testAccuracy: number;
  trainSamples: number;
  validationSamples: number;
  testSamples: number;
}

interface ModelInfo {
  modelHash: string;
  featureCount: number;
  trainedAt: string;
}

interface TrainModelResponse {
  symbol: string;
  timeframe: string;
  lookbackDays: number;
  status: string;
  trainingMetrics: TrainingMetrics;
  modelInfo: ModelInfo;
  ensembleWeights: Record<string, number>;
  featureImportance: Record<string, number>;
}

serve(async (req) => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return handlePreflight();
  }

  try {
    const request: TrainModelRequest = await req.json();

    if (!request.symbol) {
      return corsResponse(
        { error: "symbol is required" },
        { status: 400 }
      );
    }

    // Call FastAPI endpoint
    const response = await callFastApi<TrainModelResponse>(
      "/api/v1/train-model",
      {
        method: "POST",
        body: JSON.stringify({
          symbol: request.symbol.toUpperCase(),
          timeframe: request.timeframe || "d1",
          lookbackDays: request.lookbackDays || 90,
        }),
      }
    );

    return corsResponse(response);
  } catch (error) {
    console.error("Error training model:", error);
    return corsResponse(
      {
        error: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 }
    );
  }
});
