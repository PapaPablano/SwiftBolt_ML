// forex-data: Fetch forex/currency data via Alpaca's Forex API
// GET /forex-data?action=quotes&pairs=EUR/USD,GBP/USD
// GET /forex-data?action=snapshots&pairs=EUR/USD,GBP/USD
// GET /forex-data?action=bars&pair=EUR/USD&timeframe=h1&start=1704067200&end=1704153600
// GET /forex-data?action=pairs
//
// Uses Alpaca's v1beta1 Forex API for real-time and historical forex data

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { handleCorsOptions, jsonResponse, errorResponse } from "../_shared/cors.ts";
import { getAlpacaClient } from "../_shared/providers/factory.ts";

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
    const action = url.searchParams.get("action");

    if (!action) {
      return errorResponse("Missing required parameter: action (quotes, snapshots, bars, pairs)", 400);
    }

    // Get Alpaca client
    const alpaca = getAlpacaClient();
    if (!alpaca) {
      return errorResponse("Alpaca client not configured. Check ALPACA_API_KEY and ALPACA_API_SECRET.", 503);
    }

    switch (action) {
      case "quotes": {
        const pairsParam = url.searchParams.get("pairs");
        if (!pairsParam) {
          return errorResponse("Missing required parameter: pairs (e.g., EUR/USD,GBP/USD)", 400);
        }

        const pairs = pairsParam.split(",").map(s => s.trim());
        console.log(`[forex-data] Fetching quotes for ${pairs.length} pairs`);

        const quotes = await alpaca.getForexQuotes(pairs);

        return jsonResponse({
          success: true,
          count: quotes.length,
          quotes: quotes.map(q => ({
            symbol: q.symbol,
            bidPrice: q.bidPrice,
            askPrice: q.askPrice,
            midPrice: q.midPrice,
            spread: q.askPrice - q.bidPrice,
            spreadPips: ((q.askPrice - q.bidPrice) * 10000).toFixed(1),
            timestamp: q.timestamp,
            timestampISO: new Date(q.timestamp * 1000).toISOString(),
          })),
        });
      }

      case "snapshots": {
        const pairsParam = url.searchParams.get("pairs");
        if (!pairsParam) {
          return errorResponse("Missing required parameter: pairs (e.g., EUR/USD,GBP/USD)", 400);
        }

        const pairs = pairsParam.split(",").map(s => s.trim());
        console.log(`[forex-data] Fetching snapshots for ${pairs.length} pairs`);

        const snapshots = await alpaca.getForexSnapshots(pairs);

        return jsonResponse({
          success: true,
          count: snapshots.length,
          snapshots: snapshots.map(s => ({
            symbol: s.symbol,
            latestQuote: {
              bidPrice: s.latestQuote.bidPrice,
              askPrice: s.latestQuote.askPrice,
              midPrice: s.latestQuote.midPrice,
              spread: s.latestQuote.askPrice - s.latestQuote.bidPrice,
              timestamp: s.latestQuote.timestamp,
              timestampISO: new Date(s.latestQuote.timestamp * 1000).toISOString(),
            },
            dailyBar: s.dailyBar ? {
              open: s.dailyBar.open,
              high: s.dailyBar.high,
              low: s.dailyBar.low,
              close: s.dailyBar.close,
              change: s.dailyBar.close - s.dailyBar.open,
              changePercent: ((s.dailyBar.close - s.dailyBar.open) / s.dailyBar.open * 100).toFixed(4),
            } : null,
            prevDailyBar: s.prevDailyBar ? {
              open: s.prevDailyBar.open,
              high: s.prevDailyBar.high,
              low: s.prevDailyBar.low,
              close: s.prevDailyBar.close,
            } : null,
          })),
        });
      }

      case "bars": {
        const pair = url.searchParams.get("pair");
        const timeframe = url.searchParams.get("timeframe") || "h1";
        const startParam = url.searchParams.get("start");
        const endParam = url.searchParams.get("end");

        if (!pair) {
          return errorResponse("Missing required parameter: pair (e.g., EUR/USD)", 400);
        }

        // Default to last 7 days if no date range specified
        const now = Math.floor(Date.now() / 1000);
        const start = startParam ? parseInt(startParam, 10) : now - (7 * 24 * 3600);
        const end = endParam ? parseInt(endParam, 10) : now;

        if (isNaN(start) || isNaN(end)) {
          return errorResponse("Invalid start or end timestamp", 400);
        }

        console.log(`[forex-data] Fetching bars for ${pair} ${timeframe} from ${new Date(start * 1000).toISOString()} to ${new Date(end * 1000).toISOString()}`);

        const bars = await alpaca.getForexHistoricalBars({
          pair,
          timeframe,
          start,
          end,
        });

        return jsonResponse({
          success: true,
          pair,
          timeframe,
          count: bars.length,
          bars: bars.map(b => ({
            timestamp: b.timestamp,
            timestampISO: new Date(b.timestamp * 1000).toISOString(),
            open: b.open,
            high: b.high,
            low: b.low,
            close: b.close,
            volume: b.volume,
            vwap: b.vwap,
          })),
        });
      }

      case "pairs": {
        console.log(`[forex-data] Fetching available forex pairs`);

        const pairs = await alpaca.getForexPairs();

        // Group pairs by base currency
        const grouped: Record<string, string[]> = {};
        for (const pair of pairs) {
          const base = pair.split("/")[0];
          if (!grouped[base]) {
            grouped[base] = [];
          }
          grouped[base].push(pair);
        }

        return jsonResponse({
          success: true,
          count: pairs.length,
          pairs,
          grouped,
        });
      }

      default:
        return errorResponse(`Unknown action: ${action}. Valid actions: quotes, snapshots, bars, pairs`, 400);
    }
  } catch (err) {
    console.error("[forex-data] Error:", err);

    const errorMessage = err instanceof Error ? err.message : String(err);

    // Check if this is a subscription/access issue
    if (errorMessage.includes("Not Found") || errorMessage.includes("404")) {
      return errorResponse(
        "Forex data not available. This may require an Alpaca premium data subscription. " +
        "Check your Alpaca account settings at https://alpaca.markets/docs/market-data/",
        403
      );
    }

    return errorResponse(`Error: ${errorMessage}`, 500);
  }
});
