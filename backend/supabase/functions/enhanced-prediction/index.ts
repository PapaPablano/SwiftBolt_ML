// enhanced-prediction: Get enhanced ML prediction with multi-timeframe consensus,
// forecast explanation, and data quality report
// GET /enhanced-prediction?symbol=AAPL
//
// Returns comprehensive ML insights including:
// - Base prediction (direction, confidence, price target)
// - Multi-timeframe signal consensus
// - Forecast explanation (why the model predicted this)
// - Data quality report

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { handleCorsOptions, jsonResponse, errorResponse } from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";

// Response interfaces
interface TimeframeSignal {
  timeframe: string;
  signal: string;
  rsi: number | null;
}

interface MultiTimeframeConsensus {
  signal: string;
  consensus_confidence: number;
  bullish_count: number;
  bearish_count: number;
  dominant_tf: string | null;
  signal_value: number;
  timeframe_breakdown: TimeframeSignal[];
}

interface FeatureContribution {
  name: string;
  value: number | null;
  direction: string;
  description: string;
}

interface SignalCategory {
  category: string;
  signal: string;
  strength: number;
  description: string;
}

interface ForecastExplanation {
  summary: string;
  top_features: FeatureContribution[];
  signal_breakdown: SignalCategory[];
  risk_factors: string[];
  supporting_evidence: string[];
  contradicting_evidence: string[];
  recommendation: string;
  prediction: string;
}

interface ColumnIssue {
  column: string;
  nan_count: number;
  nan_pct: number;
  severity: string;
}

interface DataQualityReport {
  health_score: number;
  total_rows: number;
  total_columns: number;
  total_nans: number;
  columns_with_issues: number;
  severity: string;
  column_issues: ColumnIssue[];
  warnings: string[];
  is_clean: boolean;
}

interface EnhancedPredictionResponse {
  symbol: string;
  timestamp: string;
  prediction: string;
  confidence: number;
  price_target: number | null;
  multi_timeframe: MultiTimeframeConsensus;
  explanation: ForecastExplanation;
  data_quality: DataQualityReport;
}

// Helper to determine signal from RSI
function getSignalFromRSI(rsi: number | null): string {
  if (rsi === null) return "neutral";
  if (rsi > 60) return "bullish";
  if (rsi < 40) return "bearish";
  return "neutral";
}

// Helper to interpret RSI value
function interpretRSI(rsi: number | null): { direction: string; description: string } {
  if (rsi === null) return { direction: "neutral", description: "RSI data unavailable" };
  if (rsi > 70) return { direction: "bearish", description: `RSI at ${rsi.toFixed(1)} indicates overbought conditions` };
  if (rsi < 30) return { direction: "bullish", description: `RSI at ${rsi.toFixed(1)} indicates oversold conditions` };
  if (rsi > 60) return { direction: "bullish", description: `RSI at ${rsi.toFixed(1)} shows bullish momentum` };
  if (rsi < 40) return { direction: "bearish", description: `RSI at ${rsi.toFixed(1)} shows bearish momentum` };
  return { direction: "neutral", description: `RSI at ${rsi.toFixed(1)} is in neutral territory` };
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
    const url = new URL(req.url);
    const symbol = url.searchParams.get("symbol")?.toUpperCase();

    if (!symbol) {
      return errorResponse("Missing required parameter: symbol", 400);
    }

    const supabase = getSupabaseClient();

    // Get symbol info
    const { data: symbolData, error: symbolError } = await supabase
      .from("symbols")
      .select("id, ticker, asset_type")
      .eq("ticker", symbol)
      .single();

    if (symbolError || !symbolData) {
      return errorResponse(`Symbol not found: ${symbol}`, 404);
    }

    const symbolId = symbolData.id;

    // Get ML forecast (latest)
    const { data: forecastData } = await supabase
      .from("ml_forecasts")
      .select("overall_label, confidence, horizons, run_at")
      .eq("symbol_id", symbolId)
      .order("run_at", { ascending: false })
      .limit(1)
      .single();

    // Get OHLC data for multiple timeframes to compute indicators
    const timeframes = ["m15", "h1", "d1", "w1"];
    const timeframeData: Record<string, any[]> = {};

    for (const tf of timeframes) {
      const { data: bars } = await supabase
        .from("ohlc_bars")
        .select("ts, open, high, low, close, volume")
        .eq("symbol_id", symbolId)
        .eq("timeframe", tf)
        .order("ts", { ascending: false })
        .limit(50);

      timeframeData[tf] = bars || [];
    }

    // Calculate RSI for each timeframe (simplified 14-period RSI)
    const calculateRSI = (bars: any[]): number | null => {
      if (bars.length < 15) return null;

      let gains = 0;
      let losses = 0;

      // Calculate average gain/loss over 14 periods
      for (let i = 0; i < 14; i++) {
        const change = bars[i].close - bars[i + 1].close;
        if (change > 0) gains += change;
        else losses -= change;
      }

      const avgGain = gains / 14;
      const avgLoss = losses / 14;

      if (avgLoss === 0) return 100;
      const rs = avgGain / avgLoss;
      return 100 - (100 / (1 + rs));
    };

    // Build timeframe breakdown
    const timeframeBreakdown: TimeframeSignal[] = [];
    let bullishCount = 0;
    let bearishCount = 0;
    let dominantTf: string | null = null;
    let maxStrength = 0;

    for (const tf of timeframes) {
      const bars = timeframeData[tf];
      const rsi = calculateRSI(bars);
      const signal = getSignalFromRSI(rsi);

      timeframeBreakdown.push({
        timeframe: tf,
        signal: signal,
        rsi: rsi ? Math.round(rsi * 10) / 10 : null,
      });

      if (signal === "bullish") bullishCount++;
      if (signal === "bearish") bearishCount++;

      // Track dominant timeframe (strongest signal)
      if (rsi !== null) {
        const strength = Math.abs(rsi - 50);
        if (strength > maxStrength) {
          maxStrength = strength;
          dominantTf = tf;
        }
      }
    }

    // Determine consensus signal
    const totalSignals = bullishCount + bearishCount;
    let consensusSignal = "neutral";
    let signalValue = 0;

    if (bullishCount > bearishCount && bullishCount >= 2) {
      consensusSignal = "buy";
      signalValue = bullishCount / timeframes.length;
    } else if (bearishCount > bullishCount && bearishCount >= 2) {
      consensusSignal = "sell";
      signalValue = -bearishCount / timeframes.length;
    }

    const consensusConfidence = totalSignals > 0
      ? Math.max(bullishCount, bearishCount) / timeframes.length
      : 0.5;

    // Build multi-timeframe consensus
    const multiTimeframe: MultiTimeframeConsensus = {
      signal: consensusSignal,
      consensus_confidence: Math.round(consensusConfidence * 100) / 100,
      bullish_count: bullishCount,
      bearish_count: bearishCount,
      dominant_tf: dominantTf,
      signal_value: Math.round(signalValue * 100) / 100,
      timeframe_breakdown: timeframeBreakdown,
    };

    // Build forecast explanation
    const prediction = forecastData?.overall_label?.toLowerCase() || consensusSignal;
    const confidence = forecastData?.confidence || consensusConfidence;

    // Get top features from daily data
    const dailyBars = timeframeData["d1"];
    const dailyRSI = calculateRSI(dailyBars);
    const rsiInterpretation = interpretRSI(dailyRSI);

    const topFeatures: FeatureContribution[] = [];

    if (dailyRSI !== null) {
      topFeatures.push({
        name: "rsi_14_d1",
        value: Math.round(dailyRSI * 10) / 10,
        direction: rsiInterpretation.direction,
        description: rsiInterpretation.description,
      });
    }

    // Add price momentum feature
    if (dailyBars.length >= 5) {
      const priceChange = ((dailyBars[0].close - dailyBars[4].close) / dailyBars[4].close) * 100;
      topFeatures.push({
        name: "price_momentum_5d",
        value: Math.round(priceChange * 100) / 100,
        direction: priceChange > 1 ? "bullish" : priceChange < -1 ? "bearish" : "neutral",
        description: `Price ${priceChange > 0 ? "up" : "down"} ${Math.abs(priceChange).toFixed(1)}% over 5 days`,
      });
    }

    // Add volume feature
    if (dailyBars.length >= 20) {
      const recentVolume = dailyBars.slice(0, 5).reduce((sum, b) => sum + b.volume, 0) / 5;
      const avgVolume = dailyBars.slice(0, 20).reduce((sum, b) => sum + b.volume, 0) / 20;
      const volumeRatio = recentVolume / avgVolume;
      topFeatures.push({
        name: "volume_ratio",
        value: Math.round(volumeRatio * 100) / 100,
        direction: "neutral",
        description: `Volume at ${(volumeRatio * 100).toFixed(0)}% of 20-day average`,
      });
    }

    // Build signal breakdown by category
    const signalBreakdown: SignalCategory[] = [
      {
        category: "trend",
        signal: consensusSignal === "buy" ? "bullish" : consensusSignal === "sell" ? "bearish" : "neutral",
        strength: consensusConfidence,
        description: `${bullishCount}/${timeframes.length} timeframes show bullish trend`,
      },
      {
        category: "momentum",
        signal: dailyRSI && dailyRSI > 50 ? "bullish" : dailyRSI && dailyRSI < 50 ? "bearish" : "neutral",
        strength: dailyRSI ? Math.abs(dailyRSI - 50) / 50 : 0.5,
        description: dailyRSI ? `RSI momentum at ${dailyRSI.toFixed(0)}` : "Momentum data unavailable",
      },
    ];

    // Build risk factors
    const riskFactors: string[] = [];
    if (dailyRSI && dailyRSI > 70) {
      riskFactors.push("RSI overbought (>70) - reversal risk");
    }
    if (dailyRSI && dailyRSI < 30) {
      riskFactors.push("RSI oversold (<30) - reversal risk");
    }
    if (bullishCount > 0 && bearishCount > 0) {
      riskFactors.push("Mixed signals across timeframes");
    }
    if (riskFactors.length === 0) {
      riskFactors.push("No significant risk factors identified");
    }

    // Build evidence
    const supportingEvidence: string[] = [];
    const contradictingEvidence: string[] = [];

    for (const tf of timeframeBreakdown) {
      if (tf.signal === consensusSignal || (consensusSignal === "buy" && tf.signal === "bullish")) {
        supportingEvidence.push(`${tf.timeframe.toUpperCase()}: ${tf.signal} (RSI ${tf.rsi || "N/A"})`);
      } else if (tf.signal !== "neutral") {
        contradictingEvidence.push(`${tf.timeframe.toUpperCase()}: ${tf.signal} (RSI ${tf.rsi || "N/A"})`);
      }
    }

    if (supportingEvidence.length === 0) {
      supportingEvidence.push("Limited supporting evidence from indicators");
    }
    if (contradictingEvidence.length === 0) {
      contradictingEvidence.push("No significant contradicting signals");
    }

    // Generate recommendation
    let recommendation = "Wait for clearer signal before acting";
    if (consensusConfidence > 0.7) {
      if (consensusSignal === "buy") {
        recommendation = "Strong buy signal - consider entering long position";
      } else if (consensusSignal === "sell") {
        recommendation = "Strong sell signal - consider short or exit long";
      }
    } else if (consensusConfidence > 0.5) {
      if (consensusSignal === "buy") {
        recommendation = "Moderate buy signal - consider small position with stops";
      } else if (consensusSignal === "sell") {
        recommendation = "Moderate sell signal - tighten stops on longs";
      }
    }

    // Generate summary
    const confWord = confidence > 0.7 ? "high" : confidence > 0.4 ? "moderate" : "low";
    const summary = `${symbol} shows a ${prediction.toUpperCase()} outlook with ${confWord} confidence (${(confidence * 100).toFixed(0)}%). ${bullishCount}/${timeframes.length} timeframes support bullish view. ${topFeatures[0]?.description || ""}`;

    const explanation: ForecastExplanation = {
      summary,
      top_features: topFeatures,
      signal_breakdown: signalBreakdown,
      risk_factors: riskFactors,
      supporting_evidence: supportingEvidence,
      contradicting_evidence: contradictingEvidence,
      recommendation,
      prediction,
    };

    // Build data quality report
    // Only consider d1 (daily) as the primary data source for health scoring
    // Intraday timeframes (m15, h1) and weekly (w1) are optional/bonus data
    const dailyBarsCount = timeframeData["d1"].length;
    const hasMinimumDailyData = dailyBarsCount >= 20;
    
    // Count timeframes with actual data (not penalizing missing intraday)
    let timeframesWithData = 0;
    let totalBars = 0;
    const columnIssues: ColumnIssue[] = [];

    for (const tf of timeframes) {
      const bars = timeframeData[tf];
      totalBars += bars.length;
      if (bars.length > 0) {
        timeframesWithData++;
      }
      // Only report issues for daily timeframe - intraday is optional
      if (tf === "d1" && bars.length < 20) {
        columnIssues.push({
          column: `ohlc_${tf}`,
          nan_count: 20 - bars.length,
          nan_pct: ((20 - bars.length) / 20) * 100,
          severity: bars.length < 10 ? "high" : "low",
        });
      }
    }

    // Health score based primarily on daily data availability
    // 100% if we have 20+ daily bars, scaled down if less
    const healthScore = hasMinimumDailyData ? 1.0 : Math.min(1.0, dailyBarsCount / 20);
    const isClean = hasMinimumDailyData;

    // Generate warnings only for significant issues
    const warnings: string[] = [];
    if (!hasMinimumDailyData) {
      warnings.push(`Only ${dailyBarsCount} daily bars available (need 20 for full analysis)`);
    }

    const dataQuality: DataQualityReport = {
      health_score: Math.round(healthScore * 100) / 100,
      total_rows: totalBars,
      total_columns: timeframesWithData,
      total_nans: 0, // Not tracking NaNs for optional timeframes
      columns_with_issues: columnIssues.length,
      severity: healthScore >= 1.0 ? "clean" : healthScore > 0.7 ? "low" : "medium",
      column_issues: columnIssues,
      warnings,
      is_clean: isClean,
    };

    // Get price target from forecast if available
    let priceTarget: number | null = null;
    if (forecastData?.horizons && Array.isArray(forecastData.horizons)) {
      const firstHorizon = forecastData.horizons[0];
      if (firstHorizon?.points?.[0]?.value) {
        priceTarget = firstHorizon.points[0].value;
      }
    }

    const response: EnhancedPredictionResponse = {
      symbol,
      timestamp: new Date().toISOString(),
      prediction,
      confidence: Math.round(confidence * 100) / 100,
      price_target: priceTarget,
      multi_timeframe: multiTimeframe,
      explanation,
      data_quality: dataQuality,
    };

    console.log(`[enhanced-prediction] Generated insights for ${symbol}: ${prediction} @ ${(confidence * 100).toFixed(0)}%`);

    return jsonResponse(response);
  } catch (err) {
    console.error("[enhanced-prediction] Unexpected error:", err);
    return errorResponse(
      `Internal server error: ${err instanceof Error ? err.message : String(err)}`,
      500
    );
  }
});
