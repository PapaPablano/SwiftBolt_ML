// crypto-data: Fetch cryptocurrency data via Alpaca's Crypto API
// GET /crypto-data?action=quotes&symbols=BTC/USD,ETH/USD
// GET /crypto-data?action=snapshots&symbols=BTC/USD,ETH/USD
// GET /crypto-data?action=bars&symbol=BTC/USD&timeframe=h1&start=1704067200&end=1704153600
// GET /crypto-data?action=assets
//
// Uses Alpaca's v1beta3 Crypto API for real-time and historical crypto data

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
      return errorResponse("Missing required parameter: action (quotes, snapshots, bars, assets)", 400);
    }

    // Get Alpaca client
    const alpaca = getAlpacaClient();
    if (!alpaca) {
      return errorResponse("Alpaca client not configured. Check ALPACA_API_KEY and ALPACA_API_SECRET.", 503);
    }

    switch (action) {
      case "quotes": {
        const symbolsParam = url.searchParams.get("symbols");
        if (!symbolsParam) {
          return errorResponse("Missing required parameter: symbols (e.g., BTC/USD,ETH/USD)", 400);
        }

        const symbols = symbolsParam.split(",").map(s => s.trim());
        console.log(`[crypto-data] Fetching quotes for ${symbols.length} symbols`);

        const quotes = await alpaca.getCryptoQuotes(symbols);

        return jsonResponse({
          success: true,
          count: quotes.length,
          quotes: quotes.map(q => ({
            symbol: q.symbol,
            price: q.price,
            timestamp: q.timestamp,
            timestampISO: new Date(q.timestamp * 1000).toISOString(),
            bidPrice: q.bidPrice,
            bidSize: q.bidSize,
            askPrice: q.askPrice,
            askSize: q.askSize,
          })),
        });
      }

      case "snapshots": {
        const symbolsParam = url.searchParams.get("symbols");
        if (!symbolsParam) {
          return errorResponse("Missing required parameter: symbols (e.g., BTC/USD,ETH/USD)", 400);
        }

        const symbols = symbolsParam.split(",").map(s => s.trim());
        console.log(`[crypto-data] Fetching snapshots for ${symbols.length} symbols`);

        const snapshots = await alpaca.getCryptoSnapshots(symbols);

        return jsonResponse({
          success: true,
          count: snapshots.length,
          snapshots: snapshots.map(s => ({
            symbol: s.symbol,
            latestTrade: {
              price: s.latestTrade.price,
              size: s.latestTrade.size,
              timestamp: s.latestTrade.timestamp,
              timestampISO: new Date(s.latestTrade.timestamp * 1000).toISOString(),
              exchange: s.latestTrade.exchange,
            },
            latestQuote: {
              price: s.latestQuote.price,
              bidPrice: s.latestQuote.bidPrice,
              askPrice: s.latestQuote.askPrice,
              timestamp: s.latestQuote.timestamp,
            },
            dailyBar: s.dailyBar ? {
              open: s.dailyBar.open,
              high: s.dailyBar.high,
              low: s.dailyBar.low,
              close: s.dailyBar.close,
              volume: s.dailyBar.volume,
              vwap: s.dailyBar.vwap,
            } : null,
            prevDailyBar: s.prevDailyBar ? {
              open: s.prevDailyBar.open,
              high: s.prevDailyBar.high,
              low: s.prevDailyBar.low,
              close: s.prevDailyBar.close,
              volume: s.prevDailyBar.volume,
            } : null,
          })),
        });
      }

      case "bars": {
        const symbol = url.searchParams.get("symbol");
        const timeframe = url.searchParams.get("timeframe") || "h1";
        const startParam = url.searchParams.get("start");
        const endParam = url.searchParams.get("end");

        if (!symbol) {
          return errorResponse("Missing required parameter: symbol (e.g., BTC/USD)", 400);
        }

        // Default to last 7 days if no date range specified
        const now = Math.floor(Date.now() / 1000);
        const start = startParam ? parseInt(startParam, 10) : now - (7 * 24 * 3600);
        const end = endParam ? parseInt(endParam, 10) : now;

        if (isNaN(start) || isNaN(end)) {
          return errorResponse("Invalid start or end timestamp", 400);
        }

        console.log(`[crypto-data] Fetching bars for ${symbol} ${timeframe} from ${new Date(start * 1000).toISOString()} to ${new Date(end * 1000).toISOString()}`);

        const bars = await alpaca.getCryptoHistoricalBars({
          symbol,
          timeframe,
          start,
          end,
        });

        return jsonResponse({
          success: true,
          symbol,
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
            tradeCount: b.tradeCount,
          })),
        });
      }

      case "assets": {
        console.log(`[crypto-data] Fetching crypto assets`);

        const assets = await alpaca.getCryptoAssets();

        return jsonResponse({
          success: true,
          count: assets.length,
          assets: assets.map(a => ({
            symbol: a.symbol,
            name: a.name,
            status: a.status,
            tradable: a.tradable,
            minOrderSize: a.min_order_size,
            minTradeIncrement: a.min_trade_increment,
            priceIncrement: a.price_increment,
          })),
        });
      }

      default:
        return errorResponse(`Unknown action: ${action}. Valid actions: quotes, snapshots, bars, assets`, 400);
    }
  } catch (err) {
    console.error("[crypto-data] Error:", err);
    return errorResponse(
      `Error: ${err instanceof Error ? err.message : String(err)}`,
      500
    );
  }
});
