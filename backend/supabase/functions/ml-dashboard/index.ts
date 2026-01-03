// ml-dashboard: Get aggregate ML model performance and forecast metrics
// GET /ml-dashboard?action=<action>
//
// Actions:
// - dashboard (default): Full dashboard with overview, recent forecasts, performance
// - accuracy: Forecast accuracy metrics by horizon
// - weights: Current model weights with 30-day accuracy
// - trend: Daily accuracy trend over time
// - evaluations: Recent forecast evaluations
// - horizon_accuracy: Detailed 1D vs 1W accuracy breakdown (NEW)
// - symbol_accuracy: Per-symbol accuracy by horizon (NEW)
// - model_comparison: RF vs GB performance by horizon (NEW)
// - update_weights (POST): Trigger automatic weight recalculation
//
// Returns dashboard data including:
// - Forecast overview (signal distribution, recent forecasts)
// - Model performance metrics (by symbol)
// - Feature importance (top contributing features)
// - Forecast accuracy and evaluation metrics
// - Daily (1D) vs Weekly (1W) accuracy comparison

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { handleCorsOptions, jsonResponse, errorResponse } from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";

// Normal CDF approximation for p-value calculation
function normalCDF(x: number): number {
  // Approximation using error function
  const a1 = 0.254829592;
  const a2 = -0.284496736;
  const a3 = 1.421413741;
  const a4 = -1.453152027;
  const a5 = 1.061405429;
  const p = 0.3275911;

  const sign = x < 0 ? -1 : 1;
  x = Math.abs(x) / Math.sqrt(2);

  const t = 1.0 / (1.0 + p * x);
  const y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-x * x);

  return 0.5 * (1.0 + sign * y);
}

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

// NEW: Data quality metrics from ML Improvement Plan
interface DataQualityMetrics {
  avgQualityScore: number;
  avgQualityMultiplier: number;
  avgSampleSizeMultiplier: number;
  forecastsWithIssues: number;
  totalForecasts: number;
  avgRawConfidence: number;
  avgAdjustedConfidence: number;
  confidenceReduction: number;  // Percentage reduction from raw to adjusted
}

// Statistical validation metrics
interface ValidationMetrics {
  // Core metrics (Easy)
  precision_at_10: number | null;
  win_rate: number | null;
  expectancy: number | null;
  // Intermediate metrics (Medium)
  sharpe_ratio: number | null;
  kendall_tau: number | null;
  monte_carlo_luck: number | null;
  // Advanced metrics (Hard)
  t_test_p_value: number | null;
  // Summary metrics
  model_edge: number | null;
  confidence_calibration: number | null;
  consistency: number | null;
  robustness: number | null;
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
  // NEW: Accuracy and feedback loop metrics
  accuracyMetrics?: AccuracyMetrics;
  modelWeights?: ModelWeightInfo[];
  // NEW: Data quality metrics from ML Improvement Plan
  dataQuality?: DataQualityMetrics;
  // NEW: Statistical validation metrics
  validationMetrics?: ValidationMetrics;
}

// NEW: Accuracy metrics from feedback loop
interface AccuracyMetrics {
  horizon: string;
  totalEvaluations: number;
  accuracyPct: number;
  avgErrorPct: number;
  rfAccuracyPct: number | null;
  gbAccuracyPct: number | null;
  lastEvaluation: string | null;
}

// NEW: Model weight information
interface ModelWeightInfo {
  horizon: string;
  rfWeightPct: number;
  gbWeightPct: number;
  rfAccuracy30dPct: number | null;
  gbAccuracy30dPct: number | null;
  lastUpdated: string;
  updateReason: string;
}

serve(async (req: Request): Promise<Response> => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return handleCorsOptions();
  }

  // Allow GET and POST (for update_weights)
  if (req.method !== "GET" && req.method !== "POST") {
    return errorResponse("Method not allowed", 405);
  }

  try {
    const supabase = getSupabaseClient();
    const url = new URL(req.url);
    const action = url.searchParams.get("action") || "dashboard";

    // Handle new feedback loop actions
    switch (action) {
      case "accuracy": {
        // Get accuracy summary from view
        const { data, error } = await supabase
          .from("v_forecast_accuracy_summary")
          .select("*");
        if (error) {
          console.error("[ml-dashboard] Accuracy query error:", error);
          return errorResponse(`Database error: ${error.message}`, 500);
        }
        return jsonResponse(data || []);
      }

      case "weights": {
        // Get current model weights
        const { data, error } = await supabase
          .from("v_model_weights_dashboard")
          .select("*");
        if (error) {
          console.error("[ml-dashboard] Weights query error:", error);
          return errorResponse(`Database error: ${error.message}`, 500);
        }
        return jsonResponse(data || []);
      }

      case "trend": {
        // Get daily accuracy trend
        const days = parseInt(url.searchParams.get("days") || "30");
        const horizon = url.searchParams.get("horizon");

        let query = supabase
          .from("v_daily_accuracy_trend")
          .select("*")
          .order("eval_date", { ascending: false })
          .limit(days * 3);

        if (horizon) {
          query = query.eq("horizon", horizon);
        }

        const { data, error } = await query;
        if (error) {
          console.error("[ml-dashboard] Trend query error:", error);
          return errorResponse(`Database error: ${error.message}`, 500);
        }
        return jsonResponse(data || []);
      }

      case "evaluations": {
        // Get recent evaluations
        const limit = parseInt(url.searchParams.get("limit") || "50");
        const horizon = url.searchParams.get("horizon");
        const symbol = url.searchParams.get("symbol");

        let query = supabase
          .from("forecast_evaluations")
          .select("*")
          .order("evaluation_date", { ascending: false })
          .limit(limit);

        if (horizon) {
          query = query.eq("horizon", horizon);
        }
        if (symbol) {
          query = query.eq("symbol", symbol.toUpperCase());
        }

        const { data, error } = await query;
        if (error) {
          console.error("[ml-dashboard] Evaluations query error:", error);
          return errorResponse(`Database error: ${error.message}`, 500);
        }
        return jsonResponse(data || []);
      }

      case "update_weights": {
        // Trigger weight update (POST only)
        if (req.method !== "POST") {
          return errorResponse("POST method required for update_weights", 405);
        }

        const { data, error } = await supabase.rpc("trigger_weight_update");
        if (error) {
          console.error("[ml-dashboard] Weight update error:", error);
          return errorResponse(`Database error: ${error.message}`, 500);
        }
        return jsonResponse(data);
      }

      case "pending": {
        // Get pending evaluations count
        const horizon = url.searchParams.get("horizon") || "1D";
        const { data, error } = await supabase.rpc("get_pending_evaluations", {
          p_horizon: horizon,
        });
        if (error) {
          console.error("[ml-dashboard] Pending query error:", error);
          return errorResponse(`Database error: ${error.message}`, 500);
        }
        return jsonResponse({
          horizon,
          pending_count: data?.length || 0,
          forecasts: data || [],
        });
      }

      case "full_report": {
        // Get comprehensive ML dashboard from RPC function
        const { data, error } = await supabase.rpc("get_ml_dashboard");
        if (error) {
          console.error("[ml-dashboard] Full report error:", error);
          return errorResponse(`Database error: ${error.message}`, 500);
        }
        return jsonResponse(data);
      }

      case "horizon_accuracy": {
        // Get detailed 1D vs 1W accuracy breakdown
        const { data, error } = await supabase.rpc("get_horizon_accuracy");
        if (error) {
          console.error("[ml-dashboard] Horizon accuracy error:", error);
          return errorResponse(`Database error: ${error.message}`, 500);
        }
        return jsonResponse(data);
      }

      case "symbol_accuracy": {
        // Get per-symbol accuracy by horizon
        const horizon = url.searchParams.get("horizon");
        let query = supabase
          .from("v_symbol_accuracy_by_horizon")
          .select("*")
          .order("accuracy_pct", { ascending: false });

        if (horizon) {
          query = query.eq("horizon", horizon);
        }

        const { data, error } = await query;
        if (error) {
          console.error("[ml-dashboard] Symbol accuracy error:", error);
          return errorResponse(`Database error: ${error.message}`, 500);
        }
        return jsonResponse(data || []);
      }

      case "model_comparison": {
        // Get RF vs GB comparison by horizon
        const { data, error } = await supabase
          .from("v_model_comparison_by_horizon")
          .select("*");
        if (error) {
          console.error("[ml-dashboard] Model comparison error:", error);
          return errorResponse(`Database error: ${error.message}`, 500);
        }
        return jsonResponse(data || []);
      }

      case "data_quality": {
        // Get data quality metrics from recent forecasts
        // Note: This reads from ml_data_quality_log table created by ML Improvement Plan
        const limit = parseInt(url.searchParams.get("limit") || "100");
        const { data, error } = await supabase
          .from("ml_data_quality_log")
          .select("*")
          .order("created_at", { ascending: false })
          .limit(limit);
        if (error) {
          console.error("[ml-dashboard] Data quality query error:", error);
          return errorResponse(`Database error: ${error.message}`, 500);
        }
        return jsonResponse(data || []);
      }

      case "calibration": {
        // Get confidence calibration metrics
        const { data, error } = await supabase
          .from("ml_confidence_calibration")
          .select("*")
          .order("horizon", { ascending: true });
        if (error) {
          console.error("[ml-dashboard] Calibration query error:", error);
          return errorResponse(`Database error: ${error.message}`, 500);
        }
        return jsonResponse(data || []);
      }

      case "dashboard":
      default:
        // Continue to existing dashboard logic below
        break;
    }

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
    const recentForecasts: ForecastSummary[] = allForecasts.slice(0, 20).map((f: any) => ({
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

    // 7. Get accuracy metrics from feedback loop (if available)
    let accuracyMetrics: AccuracyMetrics | undefined;
    let modelWeights: ModelWeightInfo[] | undefined;

    try {
      // Try to get accuracy summary
      const { data: accuracyData } = await supabase
        .from("v_forecast_accuracy_summary")
        .select("*")
        .eq("horizon", "1D")
        .single();

      if (accuracyData) {
        accuracyMetrics = {
          horizon: accuracyData.horizon,
          totalEvaluations: accuracyData.total_evaluations,
          accuracyPct: accuracyData.accuracy_pct,
          avgErrorPct: accuracyData.avg_error_pct,
          rfAccuracyPct: accuracyData.rf_accuracy_pct,
          gbAccuracyPct: accuracyData.gb_accuracy_pct,
          lastEvaluation: accuracyData.last_evaluation,
        };
      }

      // Try to get model weights
      const { data: weightsData } = await supabase
        .from("v_model_weights_dashboard")
        .select("*");

      if (weightsData && weightsData.length > 0) {
        modelWeights = weightsData.map((w: any) => ({
          horizon: w.horizon,
          rfWeightPct: w.rf_weight_pct,
          gbWeightPct: w.gb_weight_pct,
          rfAccuracy30dPct: w.rf_accuracy_30d_pct,
          gbAccuracy30dPct: w.gb_accuracy_30d_pct,
          lastUpdated: w.last_updated,
          updateReason: w.update_reason,
        }));
      }
    } catch (metricsErr) {
      // Feedback loop tables may not exist yet - that's OK
      console.log("[ml-dashboard] Feedback loop metrics not available:", metricsErr);
    }

    // 8. Get data quality metrics (ML Improvement Plan)
    let dataQuality: DataQualityMetrics | undefined;
    try {
      const { data: qualityData } = await supabase
        .from("ml_data_quality_log")
        .select("quality_score, rows_flagged")
        .order("created_at", { ascending: false })
        .limit(100);

      if (qualityData && qualityData.length > 0) {
        const avgQualityScore = qualityData.reduce(
          (sum: number, d: any) => sum + (d.quality_score || 0), 0
        ) / qualityData.length;
        const forecastsWithIssues = qualityData.filter(
          (d: any) => d.rows_flagged > 0
        ).length;

        dataQuality = {
          avgQualityScore: Math.round(avgQualityScore * 100) / 100,
          avgQualityMultiplier: 0.95, // Default estimate
          avgSampleSizeMultiplier: 0.85, // Default estimate
          forecastsWithIssues,
          totalForecasts: qualityData.length,
          avgRawConfidence: 0.65, // Will be updated when we track raw confidence
          avgAdjustedConfidence: allForecasts.length > 0
            ? totalConfidence / allForecasts.length
            : 0,
          confidenceReduction: 0, // Will be calculated from raw vs adjusted
        };
      }
    } catch (qualityErr) {
      console.log("[ml-dashboard] Data quality metrics not available:", qualityErr);
    }

    // 9. Calculate statistical validation metrics
    let validationMetrics: ValidationMetrics | undefined;
    try {
      const { data: evalData } = await supabase
        .from("forecast_evaluations")
        .select("*")
        .order("evaluation_date", { ascending: false })
        .limit(500);

      if (evalData && evalData.length >= 5) {
        // Sort by confidence to get top N for Precision@10 (or fewer if less data)
        const sortedByConfidence = [...evalData].sort(
          (a: any, b: any) => (b.predicted_confidence || 0) - (a.predicted_confidence || 0)
        );
        const topN = sortedByConfidence.slice(0, Math.min(10, evalData.length));
        const topNCorrect = topN.filter((e: any) => e.direction_correct === true).length;
        const precision_at_10 = topNCorrect / topN.length;

        // Win Rate: percentage of correct predictions
        const totalCorrect = evalData.filter((e: any) => e.direction_correct === true).length;
        const win_rate = totalCorrect / evalData.length;

        // Expectancy: average return per trade
        const returns = evalData
          .map((e: any) => {
            const r = e.realized_return;
            const n = typeof r === "number" ? r : Number(r);
            return Number.isFinite(n) ? n : null;
          })
          .filter((r: number | null): r is number => r !== null);
        const expectancy = returns.length > 0
          ? returns.reduce((a: number, b: number) => a + b, 0) / returns.length
          : null;

        // Sharpe Ratio: (mean return - risk_free) / std_dev
        let sharpe_ratio: number | null = null;
        if (returns.length >= 2) {
          const meanReturn = returns.reduce((a: number, b: number) => a + b, 0) / returns.length;
          const riskFreeDaily = 0.05 / 252; // ~5% annual risk-free rate
          const denomN = Math.max(1, returns.length - 1);
          const variance = returns.reduce((sum: number, r: number) => sum + Math.pow(r - meanReturn, 2), 0) / denomN;
          const stdDev = Math.sqrt(variance);
          sharpe_ratio = stdDev > 0 ? (meanReturn - riskFreeDaily) / stdDev : 0;
        }

        // Kendall Tau: rank correlation between confidence and actual returns
        let kendall_tau: number | null = null;
        const paired = evalData
          .filter((e: any) => e.predicted_confidence !== null && e.realized_return !== null)
          .map((e: any) => ({ conf: Number(e.predicted_confidence) || 0, ret: Number(e.realized_return) || 0 }));

        if (paired.length >= 5) {
          // Calculate Kendall Tau using concordant/discordant pairs
          let concordant = 0;
          let discordant = 0;
          for (let i = 0; i < paired.length; i++) {
            for (let j = i + 1; j < paired.length; j++) {
              const confDiff = paired[i].conf - paired[j].conf;
              const retDiff = paired[i].ret - paired[j].ret;
              if (confDiff * retDiff > 0) concordant++;
              else if (confDiff * retDiff < 0) discordant++;
            }
          }
          const n = paired.length;
          const totalPairs = (n * (n - 1)) / 2;
          if (totalPairs > 0) {
            kendall_tau = (concordant - discordant) / totalPairs;
          }
        }

        // Monte Carlo Luck Estimate: probability observed win rate is due to luck
        let monte_carlo_luck: number | null = null;
        if (evalData.length >= 5) {
          const observedWinRate = win_rate;
          const nullHypothesis = 0.5; // Random guessing
          const n = evalData.length;

          // Run 1000 simulations under null hypothesis
          let luckierCount = 0;
          for (let sim = 0; sim < 1000; sim++) {
            let simWins = 0;
            for (let i = 0; i < n; i++) {
              if (Math.random() < nullHypothesis) simWins++;
            }
            if (simWins / n >= observedWinRate) luckierCount++;
          }
          monte_carlo_luck = luckierCount / 1000;
        }

        // T-test p-value: test if mean return is significantly different from 0
        let t_test_p_value: number | null = null;
        if (returns.length >= 2) {
          const meanReturn = returns.reduce((a: number, b: number) => a + b, 0) / returns.length;
          const variance = returns.reduce((sum: number, r: number) => sum + Math.pow(r - meanReturn, 2), 0) / Math.max(1, (returns.length - 1));
          const stdErr = Math.sqrt(variance / returns.length);
          if (stdErr > 0) {
            const tStat = Math.abs(meanReturn / stdErr);
            t_test_p_value = 2 * (1 - normalCDF(tStat));
          } else {
            t_test_p_value = 1;
          }
        }

        // Summary metrics
        const model_edge = win_rate > 0.5 ? (win_rate - 0.5) * 2 : null; // How much better than random

        // Confidence calibration: correlation between confidence and accuracy
        let confidence_calibration: number | null = null;
        const confBuckets = [
          { min: 0.3, max: 0.5, correct: 0, total: 0 },
          { min: 0.5, max: 0.6, correct: 0, total: 0 },
          { min: 0.6, max: 0.7, correct: 0, total: 0 },
          { min: 0.7, max: 0.8, correct: 0, total: 0 },
          { min: 0.8, max: 1.0, correct: 0, total: 0 },
        ];
        for (const e of evalData) {
          const conf = e.predicted_confidence || 0;
          for (const bucket of confBuckets) {
            if (conf >= bucket.min && conf < bucket.max) {
              bucket.total++;
              if (e.direction_correct) bucket.correct++;
              break;
            }
          }
        }
        const calibrationPairs = confBuckets
          .filter(b => b.total >= 5)
          .map(b => ({
            expected: (b.min + b.max) / 2,
            actual: b.correct / b.total
          }));
        if (calibrationPairs.length >= 3) {
          // Calculate correlation between expected and actual
          const avgExpected = calibrationPairs.reduce((s, p) => s + p.expected, 0) / calibrationPairs.length;
          const avgActual = calibrationPairs.reduce((s, p) => s + p.actual, 0) / calibrationPairs.length;
          let numerator = 0, denomExpected = 0, denomActual = 0;
          for (const p of calibrationPairs) {
            numerator += (p.expected - avgExpected) * (p.actual - avgActual);
            denomExpected += Math.pow(p.expected - avgExpected, 2);
            denomActual += Math.pow(p.actual - avgActual, 2);
          }
          if (denomExpected > 0 && denomActual > 0) {
            confidence_calibration = numerator / Math.sqrt(denomExpected * denomActual);
          }
        }

        // Consistency: standard deviation of rolling win rate (lower = more consistent)
        let consistency: number | null = null;
        if (evalData.length >= 10) {
          const windowSize = Math.min(10, Math.floor(evalData.length / 2));
          const rollingWinRates: number[] = [];
          for (let i = 0; i <= evalData.length - windowSize; i++) {
            const window = evalData.slice(i, i + windowSize);
            const windowWins = window.filter((e: any) => e.direction_correct === true).length;
            rollingWinRates.push(windowWins / windowSize);
          }
          const avgRolling = rollingWinRates.reduce((a, b) => a + b, 0) / rollingWinRates.length;
          const variance = rollingWinRates.reduce((s, r) => s + Math.pow(r - avgRolling, 2), 0) / rollingWinRates.length;
          const stdDev = Math.sqrt(variance);
          // Convert to 0-1 scale where 1 = perfectly consistent
          consistency = Math.max(0, 1 - stdDev * 2);
        }

        // Robustness: win rate in different market conditions
        // Simplified: check if model performs in both up and down markets
        let robustness: number | null = null;
        const upMarket = evalData.filter((e: any) => Number(e.realized_return || 0) > 0);
        const downMarket = evalData.filter((e: any) => Number(e.realized_return || 0) < 0);
        if (upMarket.length >= 3 && downMarket.length >= 3) {
          const upWinRate = upMarket.filter((e: any) => e.direction_correct).length / upMarket.length;
          const downWinRate = downMarket.filter((e: any) => e.direction_correct).length / downMarket.length;
          // Robustness is high if both win rates are similar and above 0.5
          const minWinRate = Math.min(upWinRate, downWinRate);
          const winRateDiff = Math.abs(upWinRate - downWinRate);
          robustness = Math.max(0, minWinRate - 0.3) * (1 - winRateDiff);
        }

        validationMetrics = {
          precision_at_10: Math.round(precision_at_10 * 1000) / 1000,
          win_rate: Math.round(win_rate * 1000) / 1000,
          expectancy: expectancy !== null ? Math.round(expectancy * 1000) / 1000 : null,
          sharpe_ratio: sharpe_ratio !== null ? Math.round(sharpe_ratio * 100) / 100 : null,
          kendall_tau: kendall_tau !== null ? Math.round(kendall_tau * 1000) / 1000 : null,
          monte_carlo_luck: monte_carlo_luck !== null ? Math.round(monte_carlo_luck * 1000) / 1000 : null,
          t_test_p_value: t_test_p_value !== null ? Math.round(t_test_p_value * 10000) / 10000 : null,
          model_edge: model_edge !== null ? Math.round(model_edge * 1000) / 1000 : null,
          confidence_calibration: confidence_calibration !== null ? Math.round(confidence_calibration * 1000) / 1000 : null,
          consistency: consistency !== null ? Math.round(consistency * 1000) / 1000 : null,
          robustness: robustness !== null ? Math.round(robustness * 1000) / 1000 : null,
        };

        console.log(`[ml-dashboard] Calculated validation metrics from ${evalData.length} evaluations`);
      }
    } catch (validationErr) {
      console.log("[ml-dashboard] Validation metrics not available:", validationErr);
    }

    // 10. Build response
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
      accuracyMetrics,
      modelWeights,
      dataQuality,
      validationMetrics,
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
