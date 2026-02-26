// POST /test-alpaca-futures
// Test Alpaca futures API

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { corsResponse } from "../_shared/cors.ts";

serve(async (req: Request): Promise<Response> => {
  const origin = req.headers.get("origin");

  if (req.method !== "POST") {
    return corsResponse({ error: "Method not allowed" }, 405, origin);
  }

  try {
    const apiKey = Deno.env.get("ALPACA_API_KEY");
    const apiSecret = Deno.env.get("ALPACA_API_SECRET");

    if (!apiKey || !apiSecret) {
      return corsResponse({ error: "Missing Alpaca credentials" }, 500, origin);
    }

    // Test stocks endpoint first (to verify credentials work)
    const stocksUrl =
      "https://data.alpaca.markets/v2/stocks/AAPL/bars?start=2024-01-01&end=2024-01-05&limit=5";
    const stocksResponse = await fetch(stocksUrl, {
      headers: {
        "APCA-API-KEY-ID": apiKey,
        "APCA-API-SECRET-KEY": apiSecret,
      },
    });
    const stocksData = await stocksResponse.json();

    // Test futures/commodities endpoint
    const futuresUrl =
      "https://data.alpaca.markets/v2/futures/CME:GC/bars?start=2024-01-01&end=2024-01-05&limit=5";
    const futuresResponse = await fetch(futuresUrl, {
      headers: {
        "APCA-API-KEY-ID": apiKey,
        "APCA-API-SECRET-KEY": apiSecret,
      },
    });
    const futuresData = await futuresResponse.json();

    return corsResponse(
      {
        stocksStatus: stocksResponse.status,
        stocksData,
        futuresStatus: futuresResponse.status,
        futuresData,
      },
      200,
      origin,
    );
  } catch (error) {
    return corsResponse(
      { error: error instanceof Error ? error.message : "Unknown error" },
      500,
      origin,
    );
  }
});
