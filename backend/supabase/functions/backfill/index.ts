// backfill: Progressive historical data backfill with pagination and rate limiting
// POST /backfill { symbol, timeframe, targetMonths }
//
// Intelligently fetches historical data in chunks, respecting API rate limits
// Stores all data in Supabase for future chart queries

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { handleCorsOptions, jsonResponse, errorResponse } from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";
import { YFinanceClient } from "../_shared/providers/yfinance-client.ts";
import type { Timeframe } from "../_shared/providers/types.ts";

const VALID_TIMEFRAMES: Timeframe[] = ["m1", "m5", "m15", "m30", "h1", "h4", "d1", "w1", "mn1"];

function isValidTimeframe(value: string): value is Timeframe {
  return VALID_TIMEFRAMES.includes(value as Timeframe);
}

interface BackfillRequest {
  symbol: string;
  timeframe: Timeframe;
  targetMonths?: number; // How many months to backfill (default: based on timeframe)
}

interface BackfillResponse {
  symbol: string;
  timeframe: string;
  totalBarsInserted: number;
  chunksProcessed: number;
  startDate: string;
  endDate: string;
  durationMs: number;
}

serve(async (req: Request): Promise<Response> => {
  if (req.method === "OPTIONS") {
    return handleCorsOptions();
  }

  if (req.method !== "POST") {
    return errorResponse("Method not allowed", 405);
  }

  const startTime = Date.now();

  try {
    const body: BackfillRequest = await req.json();
    const { symbol, timeframe, targetMonths } = body;

    if (!symbol || !timeframe) {
      return errorResponse("Missing required fields: symbol, timeframe", 400);
    }

    if (!isValidTimeframe(timeframe)) {
      return errorResponse(
        `Invalid timeframe. Must be one of: ${VALID_TIMEFRAMES.join(", ")}`,
        400
      );
    }

    const ticker = symbol.trim().toUpperCase();
    const supabase = getSupabaseClient();

    // 1. Look up or create symbol
    let symbolId: string;
    const { data: symbolData, error: symbolError } = await supabase
      .from("symbols")
      .select("id")
      .eq("ticker", ticker)
      .single();

    if (symbolError || !symbolData) {
      // Symbol doesn't exist, create it
      const { data: newSymbol, error: createError } = await supabase
        .from("symbols")
        .insert({
          ticker: ticker,
          asset_type: "stock", // Default to stock for now
          description: ticker,
        })
        .select("id")
        .single();

      if (createError || !newSymbol) {
        return errorResponse(`Failed to create symbol: ${ticker}`, 500);
      }

      symbolId = newSymbol.id;
      console.log(`[Backfill] Created new symbol: ${ticker} (${symbolId})`);
    } else {
      symbolId = symbolData.id;
    }

    // 2. Determine backfill strategy based on timeframe
    const strategy = getBackfillStrategy(timeframe, targetMonths);
    console.log(`[Backfill] Strategy for ${ticker} ${timeframe}:`, strategy);

    // 3. Check what data we already have
    const { data: existingBars } = await supabase
      .from("ohlc_bars")
      .select("ts")
      .eq("symbol_id", symbolId)
      .eq("timeframe", timeframe)
      .order("ts", { ascending: true })
      .limit(1);

    const oldestBarTs = existingBars && existingBars.length > 0
      ? new Date(existingBars[0].ts).getTime() / 1000
      : null;

    // 4. Execute backfill in chunks using YFinance (free, unlimited historical data)
    const yfinance = new YFinanceClient();
    let totalBarsInserted = 0;
    let chunksProcessed = 0;
    const currentTimestamp = Math.floor(Date.now() / 1000);
    let currentEnd = currentTimestamp;
    const targetStart = currentTimestamp - strategy.totalSeconds;

    // Stop if we already have data that's old enough
    if (oldestBarTs && oldestBarTs <= targetStart) {
      console.log(`[Backfill] Already have sufficient data for ${ticker} ${timeframe}`);
      return jsonResponse({
        symbol: ticker,
        timeframe: timeframe,
        totalBarsInserted: 0,
        chunksProcessed: 0,
        startDate: new Date(oldestBarTs * 1000).toISOString(),
        endDate: new Date(currentTimestamp * 1000).toISOString(),
        durationMs: Date.now() - startTime,
        message: "Sufficient data already exists",
      });
    }

    // Paginate backward in chunks
    while (currentEnd > targetStart && chunksProcessed < strategy.maxChunks) {
      const chunkStart = Math.max(targetStart, currentEnd - strategy.chunkSeconds);

      console.log(
        `[Backfill] Chunk ${chunksProcessed + 1}: ${new Date(chunkStart * 1000).toISOString()} to ${new Date(currentEnd * 1000).toISOString()}`
      );

      try {
        console.log(`[Backfill] Requesting YFinance data: start=${chunkStart} (${new Date(chunkStart * 1000).toISOString()}), end=${currentEnd} (${new Date(currentEnd * 1000).toISOString()})`);

        const bars = await yfinance.getHistoricalBars({
          symbol: ticker,
          timeframe: timeframe,
          start: chunkStart,
          end: currentEnd,
        });

        console.log(`[Backfill] Chunk ${chunksProcessed + 1} returned ${bars.length} bars`);

        if (bars.length > 0) {
          console.log(`[Backfill] Sample bar: timestamp=${bars[0].timestamp}, date=${new Date(bars[0].timestamp * 1000).toISOString()}, open=${bars[0].open}`);
        }

        if (bars.length === 0) {
          console.log(`[Backfill] No data returned for chunk ${chunksProcessed + 1}, stopping`);
          break;
        }

        // Filter to market hours for intraday timeframes
        const isIntraday = ["m1", "m5", "m15", "m30", "h1", "h4"].includes(timeframe);
        let filteredBars = bars;

        if (isIntraday) {
          filteredBars = bars.filter((bar) => {
            const date = new Date(bar.timestamp);
            const utcHours = date.getUTCHours();
            const utcMinutes = date.getUTCMinutes();
            const month = date.getUTCMonth();
            const isDST = month >= 2 && month <= 10;
            const offset = isDST ? 4 : 5;
            const etHours = (utcHours - offset + 24) % 24;
            const etTotalMinutes = etHours * 60 + utcMinutes;
            const marketOpen = 9 * 60 + 30;
            const marketClose = 16 * 60;
            return etTotalMinutes >= marketOpen && etTotalMinutes < marketClose;
          });
        }

        // Insert into database
        const barsToInsert = filteredBars.map((bar) => ({
          symbol_id: symbolId,
          timeframe: timeframe,
          ts: new Date(bar.timestamp * 1000).toISOString(), // Fix: multiply by 1000 for milliseconds
          open: bar.open,
          high: bar.high,
          low: bar.low,
          close: bar.close,
          volume: bar.volume,
          provider: "yfinance",
        }));

        if (barsToInsert.length > 0) {
          console.log(`[Backfill] Attempting to insert ${barsToInsert.length} bars...`);
          console.log(`[Backfill] Sample insert: ${JSON.stringify(barsToInsert[0])}`);

          const { data: upsertData, error: upsertError } = await supabase
            .from("ohlc_bars")
            .upsert(barsToInsert, {
              onConflict: "symbol_id,timeframe,ts",
              ignoreDuplicates: false, // Changed to false to count actual inserts
            })
            .select();

          if (upsertError) {
            console.error(`[Backfill] Upsert error:`, upsertError);
            console.error(`[Backfill] Upsert error details:`, JSON.stringify(upsertError));
          } else {
            const inserted = upsertData?.length || 0;
            totalBarsInserted += inserted;
            console.log(`[Backfill] Upsert returned ${inserted} rows (total: ${totalBarsInserted})`);
            if (inserted > 0) {
              console.log(`[Backfill] Sample upserted row: ${JSON.stringify(upsertData[0])}`);
            }
          }
        }

        chunksProcessed++;
        currentEnd = chunkStart;

        // YFinance is free and has no rate limits, so no delay needed
        // Just a small pause to avoid overwhelming the system
        if (chunksProcessed < strategy.maxChunks && currentEnd > targetStart) {
          await new Promise((resolve) => setTimeout(resolve, 500)); // 0.5 second pause
        }
      } catch (error) {
        console.error(`[Backfill] Error in chunk ${chunksProcessed + 1}:`, error);
        // Continue with next chunk on error
      }
    }

    const response: BackfillResponse = {
      symbol: ticker,
      timeframe: timeframe,
      totalBarsInserted,
      chunksProcessed,
      startDate: new Date(currentEnd * 1000).toISOString(),
      endDate: new Date(currentTimestamp * 1000).toISOString(),
      durationMs: Date.now() - startTime,
    };

    return jsonResponse(response);
  } catch (err) {
    console.error("Backfill error:", err);
    return errorResponse("Internal server error", 500);
  }
});

// Determine optimal backfill strategy based on timeframe
function getBackfillStrategy(timeframe: Timeframe, targetMonths?: number) {
  const secondsPerBar: Record<Timeframe, number> = {
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

  // Default target periods (how far back to go)
  // Note: For full historical data, make multiple sequential backfill requests
  // to avoid Supabase Edge Function timeout limits (~60 seconds)
  const defaultMonths: Record<Timeframe, number> = {
    m1: 1,    // 1 minute: 1 month (too much data otherwise)
    m5: 2,    // 5 minute: 2 months
    m15: 3,   // 15 minute: 3 months
    m30: 3,   // 30 minute: 3 months (reduced to fit timeout)
    h1: 3,    // 1 hour: 3 months (reduced to fit timeout, call 4x for full year)
    h4: 6,    // 4 hour: 6 months (reduced to fit timeout, call 4x for 2 years)
    d1: 24,   // Daily: 2 years (fits in timeout with 6-month chunks)
    w1: 24,   // Weekly: 2 years
    mn1: 24,  // Monthly: 2 years
  };

  const months = targetMonths || defaultMonths[timeframe];
  const totalSeconds = months * 30 * 24 * 60 * 60; // Approximate months to seconds

  // Chunk size (how much data per request)
  // For intraday, use 1 month chunks to stay within Finnhub limits
  // For daily+, can use larger chunks
  const chunkMonths = timeframe === "d1" || timeframe === "w1" || timeframe === "mn1" ? 6 : 1;
  const chunkSeconds = chunkMonths * 30 * 24 * 60 * 60;

  // Maximum chunks to process (safety limit)
  const maxChunks = Math.ceil(totalSeconds / chunkSeconds);

  // Delay between chunks (respect rate limits)
  // Massive: 5 req/min = 12 second delay
  // Finnhub: 60 req/min = 1 second delay
  const delayMs = 12000; // Use Massive's more restrictive limit

  return {
    totalSeconds,
    chunkSeconds,
    maxChunks,
    delayMs,
    estimatedDurationMs: maxChunks * delayMs,
  };
}
