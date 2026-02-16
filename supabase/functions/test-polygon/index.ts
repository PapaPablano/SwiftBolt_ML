// POST /test-polygon
// Simple test endpoint to verify Polygon API works

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { corsResponse } from "../_shared/cors.ts";

serve(async (req: Request): Promise<Response> => {
  const origin = req.headers.get("origin");

  if (req.method !== "POST") {
    return corsResponse({ error: "Method not allowed" }, 405, origin);
  }

  try {
    const body = await req.json().catch(() => ({}));
    const ticker = body.ticker || "AAPL";
    const apiKey = Deno.env.get("MASSIVE_API_KEY");
    
    if (!apiKey) {
      return corsResponse({ error: "No API key" }, 500, origin);
    }

    // Test with requested ticker
    const url = `https://api.polygon.io/v2/aggs/ticker/${ticker}/range/1/day/2024-01-01/2026-02-15?adjusted=false&sort=asc&limit=5&apiKey=${apiKey}`;
    
    const response = await fetch(url);
    const data = await response.json();

    return corsResponse({
      ticker,
      apiKeyPresent: !!apiKey,
      response: data,
    }, 200, origin);

  } catch (error) {
    return corsResponse(
      { error: error instanceof Error ? error.message : "Unknown error" },
      500,
      origin
    );
  }
});
