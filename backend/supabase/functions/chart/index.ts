// chart: Fetch OHLC candle data for a symbol via ProviderRouter
// GET /chart?symbol=AAPL&timeframe=d1
//
// Uses the unified ProviderRouter with rate limiting, caching, and fallback logic.
// DB persistence is used for long-term storage; ProviderRouter handles live fetching.

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { handleCorsOptions, jsonResponse, errorResponse } from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";
import { getProviderRouter } from "../_shared/providers/factory.ts";
import type { Timeframe } from "../_shared/providers/types.ts";

// Cache staleness threshold - varies by timeframe
// For daily/weekly/monthly, we need to be smarter about market hours
function getCacheTTL(timeframe: Timeframe): number {
  const ttls: Record<Timeframe, number> = {
    m1: 1 * 60 * 1000,        // 1 minute
    m5: 5 * 60 * 1000,        // 5 minutes
    m15: 15 * 60 * 1000,      // 15 minutes
    m30: 30 * 60 * 1000,      // 30 minutes
    h1: 60 * 60 * 1000,       // 1 hour
    h4: 4 * 60 * 60 * 1000,   // 4 hours
    d1: 4 * 60 * 60 * 1000,   // 4 hours - check more frequently for daily
    w1: 24 * 60 * 60 * 1000,  // 24 hours for weekly
    mn1: 7 * 24 * 60 * 60 * 1000, // 7 days for monthly
  };
  return ttls[timeframe];
}

// Check if we're within US market hours (9:30 AM - 4:00 PM ET)
function isMarketOpen(): boolean {
  const now = new Date();
  const day = now.getUTCDay(); // 0 = Sunday, 6 = Saturday
  
  // Weekend - market closed
  if (day === 0 || day === 6) return false;
  
  const utcHours = now.getUTCHours();
  const utcMinutes = now.getUTCMinutes();
  
  // Determine DST (approximate: March-November)
  const month = now.getUTCMonth();
  const isDST = month >= 2 && month <= 10;
  const offset = isDST ? 4 : 5;
  
  const etHours = (utcHours - offset + 24) % 24;
  const etTotalMinutes = etHours * 60 + utcMinutes;
  
  // Market hours: 9:30 AM (570 min) to 4:00 PM (960 min) ET
  return etTotalMinutes >= 570 && etTotalMinutes < 960;
}

// Get the last expected trading day timestamp
function getLastTradingDayClose(): Date {
  const now = new Date();
  const day = now.getUTCDay();
  const utcHours = now.getUTCHours();
  
  // Determine DST offset
  const month = now.getUTCMonth();
  const isDST = month >= 2 && month <= 10;
  const offset = isDST ? 4 : 5;
  const etHours = (utcHours - offset + 24) % 24;
  
  let daysBack = 0;
  
  // If it's weekend, go back to Friday
  if (day === 0) daysBack = 2; // Sunday -> Friday
  else if (day === 6) daysBack = 1; // Saturday -> Friday
  // If it's a weekday before market close (4 PM ET), use previous day
  else if (etHours < 16) daysBack = 1;
  
  const lastTradingDay = new Date(now);
  lastTradingDay.setUTCDate(lastTradingDay.getUTCDate() - daysBack);
  lastTradingDay.setUTCHours(isDST ? 20 : 21, 0, 0, 0); // 4 PM ET in UTC
  
  return lastTradingDay;
}

const VALID_TIMEFRAMES: Timeframe[] = ["m1", "m5", "m15", "m30", "h1", "h4", "d1", "w1", "mn1"];

function isValidTimeframe(value: string): value is Timeframe {
  return VALID_TIMEFRAMES.includes(value as Timeframe);
}

interface ForecastPoint {
  ts: number;
  value: number;
  lower: number;
  upper: number;
}

interface ForecastSeries {
  horizon: string;
  points: ForecastPoint[];
}

interface MLSummary {
  overallLabel: string;
  confidence: number;
  horizons: ForecastSeries[];
  srLevels?: Record<string, unknown> | null;
  srDensity?: number | null;
}

interface ForecastRow {
  horizon: string;
  overall_label: string | null;
  confidence: number;
  points: ForecastPoint[];
  run_at: string;
  sr_levels: Record<string, unknown> | null;
  sr_density: number | null;
}

interface IndicatorSnapshot {
  ts: string;
  rsi_14?: number | null;
  macd?: number | null;
  macd_signal?: number | null;
  macd_hist?: number | null;
  supertrend_value?: number | null;
  supertrend_trend?: number | null;
  nearest_support?: number | null;
  nearest_resistance?: number | null;
  support_distance_pct?: number | null;
  resistance_distance_pct?: number | null;
  adx?: number | null;
  bb_upper?: number | null;
  bb_lower?: number | null;
}

interface ChartResponse {
  symbol: string;
  assetType: string;
  timeframe: string;
  bars: {
    ts: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
  }[];
  mlSummary?: MLSummary;
  indicators?: {
    latest: IndicatorSnapshot | null;
    history: IndicatorSnapshot[];
  };
}

interface SymbolRecord {
  id: string;
  ticker: string;
  asset_type: string;
}

interface OHLCBar {
  ts: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface OHLCRecord {
  ts: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
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
    // Parse query parameters
    const url = new URL(req.url);
    const symbol = url.searchParams.get("symbol");
    const timeframe = url.searchParams.get("timeframe") || "d1";

    if (!symbol || symbol.trim().length === 0) {
      return errorResponse("Missing required parameter: symbol", 400);
    }

    if (!isValidTimeframe(timeframe)) {
      return errorResponse(
        `Invalid timeframe. Must be one of: ${VALID_TIMEFRAMES.join(", ")}`,
        400
      );
    }

    const ticker = symbol.trim().toUpperCase();
    const supabase = getSupabaseClient();

    // 1. Look up symbol in database
    const { data: symbolData, error: symbolError } = await supabase
      .from("symbols")
      .select("id, ticker, asset_type")
      .eq("ticker", ticker)
      .single();

    if (symbolError || !symbolData) {
      return errorResponse(`Symbol not found: ${ticker}`, 404);
    }

    const symbolRecord = symbolData as SymbolRecord;
    const symbolId = symbolRecord.id;
    const assetType = symbolRecord.asset_type;

    // 2. Query ML forecasts for this symbol
    let mlSummary: MLSummary | undefined;
    try {
      const { data: forecasts, error: forecastError } = await supabase
        .from("ml_forecasts")
        .select("horizon, overall_label, confidence, points, run_at, sr_levels, sr_density")
        .eq("symbol_id", symbolId)
        .in("horizon", ["1D", "1W"])
        .order("run_at", { ascending: false });

      if (!forecastError && forecasts && forecasts.length > 0) {
        // Use the most recent forecast with highest confidence as overall
        const sortedByConfidence = forecasts.sort((a, b) => b.confidence - a.confidence);
        const primary = sortedByConfidence[0];

        // Derive label from confidence if overall_label is null
        // High confidence (>0.6) with positive trend = bullish, negative = bearish
        // Otherwise neutral
        let derivedLabel = primary.overall_label;
        if (!derivedLabel) {
          const confidence = primary.confidence || 0.5;
          if (confidence > 0.6) {
            derivedLabel = "bullish";
          } else if (confidence < 0.4) {
            derivedLabel = "bearish";
          } else {
            derivedLabel = "neutral";
          }
        }

        // Find S/R data from any forecast that has it (prefer most recent)
        const forecastWithSR = forecasts.find((f: ForecastRow) => f.sr_levels != null);

        mlSummary = {
          overallLabel: derivedLabel,
          confidence: primary.confidence,
          horizons: forecasts.map((f) => ({
            horizon: f.horizon,
            points: f.points as ForecastPoint[],
          })),
          srLevels: forecastWithSR?.sr_levels || primary.sr_levels || null,
          srDensity: forecastWithSR?.sr_density || primary.sr_density || null,
        };

        console.log(`[Chart] Loaded ${forecasts.length} ML forecasts for ${ticker}, label=${derivedLabel}`);
      }
    } catch (forecastError) {
      console.error("Error loading ML forecasts:", forecastError);
      // Continue without forecasts if query fails
    }

    // 2b. Query indicator values for this symbol (optional enhancement)
    let indicatorData: { latest: IndicatorSnapshot | null; history: IndicatorSnapshot[] } | undefined;
    try {
      const { data: indicators, error: indicatorError } = await supabase
        .from("indicator_values")
        .select(`
          ts, rsi_14, macd, macd_signal, macd_hist,
          supertrend_value, supertrend_trend,
          nearest_support, nearest_resistance,
          support_distance_pct, resistance_distance_pct,
          adx, bb_upper, bb_lower
        `)
        .eq("symbol_id", symbolId)
        .eq("timeframe", timeframe)
        .order("ts", { ascending: false })
        .limit(100);

      if (!indicatorError && indicators && indicators.length > 0) {
        const typedIndicators = indicators as IndicatorSnapshot[];
        indicatorData = {
          latest: typedIndicators[0],
          history: typedIndicators.slice().reverse(), // Chronological order
        };
        console.log(`[Chart] Loaded ${indicators.length} indicator values for ${ticker}`);
      }
    } catch (indicatorQueryError) {
      console.error("Error loading indicator values:", indicatorQueryError);
      // Continue without indicators if query fails
    }

    // 3. Check for cached data
    // Return much more data from cache (up to 1000 bars) for rich charting
    // Backfill system will ensure we have deep historical data
    const cacheLimit = 1000;

    const { data: cachedBars, error: cacheError } = await supabase
      .from("ohlc_bars_v2")
      .select("ts, open, high, low, close, volume")
      .eq("symbol_id", symbolId)
      .eq("timeframe", timeframe)
      .eq("is_forecast", false)
      .order("ts", { ascending: false }) // Get most recent first
      .limit(cacheLimit);

    if (cacheError) {
      console.error("Cache query error:", cacheError);
    }

    // 4. Always use database data first (refresh-data populates it)
    // This ensures consistency - no more cache freshness logic causing issues
    let bars: OHLCBar[] = [];
    let needsFetch = true;

    if (cachedBars && cachedBars.length > 0) {
      const latestBar = cachedBars[0] as OHLCRecord;
      console.log(`[Chart] DB has ${cachedBars.length} bars, latest=${latestBar.ts}`);
      
      // Always use DB data - it's the source of truth
      // cachedBars is ordered by ts descending, so reverse for ascending order
      bars = cachedBars
        .map((bar) => ({
          ts: bar.ts,
          open: Number(bar.open),
          high: Number(bar.high),
          low: Number(bar.low),
          close: Number(bar.close),
          volume: Number(bar.volume),
        }))
        .reverse(); // Reverse to get ascending order (oldest first)
      
      // Check if we need to fetch more data
      // For daily: check if latest bar is from last trading day
      // For intraday: check TTL
      const latestTs = new Date(latestBar.ts).getTime();
      const now = Date.now();
      const cacheTTL = getCacheTTL(timeframe);
      const cacheAge = now - latestTs;
      
      if (timeframe === "d1") {
        const lastTradingClose = getLastTradingDayClose();
        const latestBarDay = new Date(new Date(latestBar.ts).toISOString().split('T')[0]);
        const lastTradingDay = new Date(lastTradingClose.toISOString().split('T')[0]);
        needsFetch = latestBarDay < lastTradingDay;
        console.log(`[Chart] D1: latestBar=${latestBarDay.toISOString()}, lastTradingDay=${lastTradingDay.toISOString()}, needsFetch=${needsFetch}`);
      } else {
        needsFetch = cacheAge > cacheTTL;
        console.log(`[Chart] ${timeframe}: age=${Math.round(cacheAge/1000/60)}min, TTL=${Math.round(cacheTTL/1000/60)}min, needsFetch=${needsFetch}`);
      }
    }

    // 5. If we need fresh data, fetch via ProviderRouter
    if (needsFetch) {
      console.log(`[Chart] Fetching fresh data for ${ticker} ${timeframe} via ProviderRouter`);

      try {
        const router = getProviderRouter();

        // Calculate time range based on timeframe
        // For intraday: request more data to account for market hours filtering
        // Market hours = 6.5 hours/day, so we need ~3.7x more calendar time to get same number of bars
        const now = Math.floor(Date.now() / 1000);
        const timeframeSeconds: Record<Timeframe, number> = {
          m1: 60,
          m5: 5 * 60,
          m15: 15 * 60,
          m30: 30 * 60,
          h1: 60 * 60,
          h4: 4 * 60 * 60,
          d1: 24 * 60 * 60,
          w1: 7 * 24 * 60 * 60,
          mn1: 30 * 24 * 60 * 60,
        };
        const secondsPerBar = timeframeSeconds[timeframe];

        // For intraday timeframes, request more bars to compensate for filtering
        // For daily+, request 2 years of data (500+ trading days)
        const isIntraday = ["m1", "m5", "m15", "m30", "h1", "h4"].includes(timeframe);
        const barsToRequest = isIntraday ? 500 : 750; // 500 intraday, 750 daily (~3 years)
        const from = now - (barsToRequest * secondsPerBar);

        const freshBars = await router.getHistoricalBars({
          symbol: ticker,
          timeframe: timeframe,
          start: from,
          end: now,
        });

        console.log(`[Chart] Received ${freshBars.length} bars from provider`);

        // Filter to regular market hours for intraday timeframes (9:30 AM - 4:00 PM ET)
        let marketHoursBars = freshBars;
        if (isIntraday) {
          marketHoursBars = freshBars.filter((bar) => {
            const date = new Date(bar.timestamp);

            // Get ET time components
            // Note: This is a simplified approach. For production, consider using a proper timezone library
            // EST is UTC-5, EDT is UTC-4. The market uses ET year-round.
            const utcHours = date.getUTCHours();
            const utcMinutes = date.getUTCMinutes();

            // Determine if we're in EDT (roughly March-November) or EST
            const month = date.getUTCMonth(); // 0-11
            const isDST = month >= 2 && month <= 10; // Approximate DST months (March-November)
            const offset = isDST ? 4 : 5; // EDT = UTC-4, EST = UTC-5

            // Convert to ET
            const etHours = (utcHours - offset + 24) % 24;
            const etMinutes = utcMinutes;
            const etTotalMinutes = etHours * 60 + etMinutes;

            // Market hours: 9:30 AM (570 minutes) to 4:00 PM (960 minutes) ET
            const marketOpen = 9 * 60 + 30;  // 9:30 AM
            const marketClose = 16 * 60;     // 4:00 PM

            return etTotalMinutes >= marketOpen && etTotalMinutes < marketClose;
          });

          console.log(`[Chart] Filtered to ${marketHoursBars.length} market-hours bars (from ${freshBars.length} total)`);
        }

        if (freshBars.length > 0) {
          // 6. Upsert bars into database
          const barsToInsert = freshBars.map((bar) => ({
            symbol_id: symbolId,
            timeframe: timeframe,
            ts: new Date(bar.timestamp).toISOString(),
            open: bar.open,
            high: bar.high,
            low: bar.low,
            close: bar.close,
            volume: bar.volume,
            provider: "alpaca",
            is_forecast: false,
            data_status: "provisional",
          }));

          const { error: upsertError } = await supabase
            .from("ohlc_bars_v2")
            .upsert(barsToInsert, {
              onConflict: "symbol_id,timeframe,ts,provider,is_forecast",
              ignoreDuplicates: false,
            });

          if (upsertError) {
            console.error("Upsert error:", upsertError);
          } else {
            console.log(`[Chart] Upserted ${freshBars.length} bars for ${ticker} ${timeframe}`);
          }

          // Re-query DB to get complete, consistent data after upsert
          const { data: updatedBars } = await supabase
            .from("ohlc_bars_v2")
            .select("ts, open, high, low, close, volume")
            .eq("symbol_id", symbolId)
            .eq("timeframe", timeframe)
            .eq("is_forecast", false)
            .order("ts", { ascending: true }) // Ascending order for chart
            .limit(cacheLimit);

          if (updatedBars && updatedBars.length > 0) {
            bars = updatedBars.map((bar) => ({
              ts: bar.ts,
              open: Number(bar.open),
              high: Number(bar.high),
              low: Number(bar.low),
              close: Number(bar.close),
              volume: Number(bar.volume),
            }));
            console.log(`[Chart] Returning ${bars.length} bars from DB after upsert`);
          }
        }
      } catch (fetchError) {
        console.error("[Chart] Provider router error:", fetchError);
        // bars already contains DB data from earlier, so we can continue
        console.log(`[Chart] Using existing ${bars.length} bars from DB`);
      }
    }

    // 7. Filter ML forecast points to only show FUTURE predictions
    // Forecasts should NOT overlay on historical price data
    if (mlSummary && bars.length > 0) {
      const latestBarTs = new Date(bars[bars.length - 1].ts).getTime();
      
      // Filter each horizon's points to only include future timestamps
      mlSummary.horizons = mlSummary.horizons.map(horizon => ({
        ...horizon,
        points: horizon.points.filter((point) => {
          const pointTs = typeof point.ts === 'number' 
            ? point.ts * 1000  // Unix timestamp in seconds -> milliseconds
            : new Date(point.ts).getTime();
          return pointTs > latestBarTs;
        }),
      }));

      // Validate ML forecast label against current price direction
      const currentPrice = bars[bars.length - 1].close;
      const forecast1D = mlSummary.horizons.find(h => h.horizon === "1D");

      if (forecast1D && forecast1D.points.length > 0) {
        const targetPrice = forecast1D.points[forecast1D.points.length - 1].value;
        const priceChange = (targetPrice - currentPrice) / currentPrice;
        const storedLabel = mlSummary.overallLabel?.toLowerCase();

        // Detect label/price mismatch (stale forecast)
        const isBearishWithHigherTarget = storedLabel === "bearish" && priceChange > 0.005; // >0.5% up
        const isBullishWithLowerTarget = storedLabel === "bullish" && priceChange < -0.005; // >0.5% down

        if (isBearishWithHigherTarget || isBullishWithLowerTarget) {
          // Correct the label to match actual price direction
          const correctedLabel = priceChange > 0 ? "bullish" : priceChange < 0 ? "bearish" : "neutral";
          console.log(`[Chart] Stale forecast detected for ${ticker}: stored=${storedLabel}, target=${targetPrice.toFixed(2)}, current=${currentPrice.toFixed(2)}, change=${(priceChange*100).toFixed(2)}%, correcting to ${correctedLabel}`);

          mlSummary = {
            ...mlSummary,
            overallLabel: correctedLabel,
            // Reduce confidence for corrected forecasts (signal that data is stale)
            confidence: Math.max(0.35, mlSummary.confidence * 0.7),
          };
        }
      }

      console.log(`[Chart] Filtered ML forecasts to future-only for ${ticker}`);
    }

    // 8. Return response with ML forecasts and indicators
    const response: ChartResponse = {
      symbol: ticker,
      assetType: assetType,
      timeframe: timeframe,
      bars: bars,
      mlSummary: mlSummary,
      indicators: indicatorData,
    };

    return jsonResponse(response);
  } catch (err) {
    console.error("Unexpected error:", err);
    return errorResponse("Internal server error", 500);
  }
});
