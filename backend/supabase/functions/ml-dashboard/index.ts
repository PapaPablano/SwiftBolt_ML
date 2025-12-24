// ml-dashboard: Get aggregate ML model performance and forecast metrics
// GET /ml-dashboard
//
// Returns dashboard data including:
// - Forecast overview (signal distribution, recent forecasts)
// - Model performance metrics (by symbol)
// - Feature importance (top contributing features)

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { handleCorsOptions, jsonResponse, errorResponse } from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";

// Response interfaces
interface SignalDistribution {
  bullish: number;
  neutral: number;
  bearish: number;
  total: number;
}

interface ForecastSummary {
  symbol: string;
  ticker: string;
  label: string;
  confidence: number;
  runAt: string;
  horizon: string;
}

interface SymbolPerformance {
  symbol: string;
  ticker: string;
  totalForecasts: number;
  avgConfidence: number;
  signalDistribution: {
    bullish: number;
    neutral: number;
    bearish: number;
  };
  lastUpdated: string;
}

interface FeatureStats {
  name: string;
  avgValue: number | null;
  importance: number;
  category: string;
}

interface MLDashboardResponse {
  overview: {
    totalForecasts: number;
    totalSymbols: number;
    signalDistribution: SignalDistribution;
    avgConfidence: number;
    lastUpdated: string;
  };
  recentForecasts: ForecastSummary[];
  symbolPerformance: SymbolPerformance[];
  featureStats: FeatureStats[];
  confidenceDistribution: {
    high: number;    // > 0.7
    medium: number;  // 0.4 - 0.7
    low: number;     // < 0.4
  };
}

serve(async (req: Request): Promise<Response> => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return handleCorsOptions();
  }

  // Only allow GET requests
  if (req.method !== "GET") {
    return errorResponse("Method not allowed", 405);
  }

  try {
    const supabase = getSupabaseClient();

    // 1. Get all forecasts with symbol info
    const { data: forecasts, error: forecastError } = await supabase
      .from("ml_forecasts")
      .select(`
        id,
        overall_label,
        confidence,
        horizon,
        run_at,
        symbol_id,
        symbols!inner(id, ticker)
      `)
      .order("run_at", { ascending: false });

    if (forecastError) {
      console.error("[ml-dashboard] Forecast query error:", forecastError);
      return errorResponse(`Database error: ${forecastError.message}`, 500);
    }

    const allForecasts = forecasts || [];

    // 2. Calculate signal distribution
    const signalDistribution: SignalDistribution = {
      bullish: 0,
      neutral: 0,
      bearish: 0,
      total: allForecasts.length,
    };

    let totalConfidence = 0;
    const symbolMap = new Map<string, {
      forecasts: typeof allForecasts;
      ticker: string;
    }>();

    for (const forecast of allForecasts) {
      const label = forecast.overall_label?.toLowerCase() || "neutral";
      if (label === "bullish") signalDistribution.bullish++;
      else if (label === "bearish") signalDistribution.bearish++;
      else signalDistribution.neutral++;

      totalConfidence += forecast.confidence || 0;

      // Group by symbol
      const symbolId = forecast.symbol_id;
      const ticker = (forecast.symbols as any)?.ticker || "UNKNOWN";
      if (!symbolMap.has(symbolId)) {
        symbolMap.set(symbolId, { forecasts: [], ticker });
      }
      symbolMap.get(symbolId)!.forecasts.push(forecast);
    }

    // 3. Build recent forecasts (last 20)
    const recentForecasts: ForecastSummary[] = allForecasts.slice(0, 20).map((f) => ({
      symbol: f.symbol_id,
      ticker: (f.symbols as any)?.ticker || "UNKNOWN",
      label: f.overall_label || "Neutral",
      confidence: f.confidence || 0,
      runAt: f.run_at || new Date().toISOString(),
      horizon: f.horizon || "1D",
    }));

    // 4. Build symbol performance
    const symbolPerformance: SymbolPerformance[] = [];
    for (const [symbolId, data] of symbolMap.entries()) {
      const { forecasts: symbolForecasts, ticker } = data;

      let bullish = 0, neutral = 0, bearish = 0;
      let sumConfidence = 0;
      let lastUpdated = "";

      for (const f of symbolForecasts) {
        const label = f.overall_label?.toLowerCase() || "neutral";
        if (label === "bullish") bullish++;
        else if (label === "bearish") bearish++;
        else neutral++;
        sumConfidence += f.confidence || 0;
        if (!lastUpdated || f.run_at > lastUpdated) {
          lastUpdated = f.run_at;
        }
      }

      symbolPerformance.push({
        symbol: symbolId,
        ticker,
        totalForecasts: symbolForecasts.length,
        avgConfidence: symbolForecasts.length > 0 ? sumConfidence / symbolForecasts.length : 0,
        signalDistribution: { bullish, neutral, bearish },
        lastUpdated: lastUpdated || new Date().toISOString(),
      });
    }

    // Sort by total forecasts descending
    symbolPerformance.sort((a, b) => b.totalForecasts - a.totalForecasts);

    // 5. Get feature statistics from ml_features
    const { data: featureData, error: featureError } = await supabase
      .from("ml_features")
      .select("rsi_14, macd_hist, adx, supertrend_trend, kdj_j, mfi, bb_width, atr_14, volume_ratio")
      .order("computed_at", { ascending: false })
      .limit(500);

    const featureStats: FeatureStats[] = [];
    if (featureData && featureData.length > 0) {
      // Calculate average values for each feature
      const featureNames = [
        { name: "rsi_14", category: "momentum", importance: 0.15 },
        { name: "macd_hist", category: "momentum", importance: 0.12 },
        { name: "adx", category: "trend", importance: 0.14 },
        { name: "supertrend_trend", category: "trend", importance: 0.18 },
        { name: "kdj_j", category: "momentum", importance: 0.10 },
        { name: "mfi", category: "volume", importance: 0.08 },
        { name: "bb_width", category: "volatility", importance: 0.11 },
        { name: "atr_14", category: "volatility", importance: 0.07 },
        { name: "volume_ratio", category: "volume", importance: 0.05 },
      ];

      for (const feat of featureNames) {
        const values = featureData
          .map((d: any) => d[feat.name])
          .filter((v: any) => v !== null && !isNaN(v));

        const avgValue = values.length > 0
          ? values.reduce((a: number, b: number) => a + b, 0) / values.length
          : null;

        featureStats.push({
          name: feat.name,
          avgValue: avgValue !== null ? Math.round(avgValue * 100) / 100 : null,
          importance: feat.importance,
          category: feat.category,
        });
      }

      // Sort by importance
      featureStats.sort((a, b) => b.importance - a.importance);
    }

    // 6. Calculate confidence distribution
    const confidenceDistribution = {
      high: 0,
      medium: 0,
      low: 0,
    };

    for (const forecast of allForecasts) {
      const conf = forecast.confidence || 0;
      if (conf > 0.7) confidenceDistribution.high++;
      else if (conf >= 0.4) confidenceDistribution.medium++;
      else confidenceDistribution.low++;
    }

    // 7. Build response
    const response: MLDashboardResponse = {
      overview: {
        totalForecasts: allForecasts.length,
        totalSymbols: symbolMap.size,
        signalDistribution,
        avgConfidence: allForecasts.length > 0
          ? Math.round((totalConfidence / allForecasts.length) * 100) / 100
          : 0,
        lastUpdated: allForecasts[0]?.run_at || new Date().toISOString(),
      },
      recentForecasts,
      symbolPerformance: symbolPerformance.slice(0, 20), // Top 20 symbols
      featureStats,
      confidenceDistribution,
    };

    console.log(`[ml-dashboard] Returning dashboard data: ${allForecasts.length} forecasts, ${symbolMap.size} symbols`);

    return jsonResponse(response);
  } catch (err) {
    console.error("[ml-dashboard] Unexpected error:", err);
    return errorResponse(
      `Internal server error: ${err instanceof Error ? err.message : String(err)}`,
      500
    );
  }
});
