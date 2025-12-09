// symbols-search: Search for symbols by ticker or description
// GET /symbols-search?q=AAPL
//
// NOTE: This function queries the Postgres 'symbols' table directly.
// It does NOT call external APIs (Finnhub/Massive).
// Search uses ILIKE for case-insensitive partial matching on ticker and description.

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { corsHeaders, handleCorsOptions, jsonResponse, errorResponse } from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";

interface SymbolResult {
  id: string;
  ticker: string;
  asset_type: string;
  description: string | null;
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
    // Parse query parameter
    const url = new URL(req.url);
    const query = url.searchParams.get("q");

    if (!query || query.trim().length === 0) {
      return errorResponse("Missing or empty query parameter 'q'", 400);
    }

    const searchTerm = query.trim();

    // Get Supabase client
    const supabase = getSupabaseClient();

    // Search symbols with ILIKE on ticker and description
    // Use % wildcards for partial matching
    const { data, error } = await supabase
      .from("symbols")
      .select("id, ticker, asset_type, description")
      .or(`ticker.ilike.%${searchTerm}%,description.ilike.%${searchTerm}%`)
      .order("ticker", { ascending: true })
      .limit(20);

    if (error) {
      console.error("Database error:", error);
      return errorResponse("Database query failed", 500);
    }

    const results: SymbolResult[] = data || [];

    return jsonResponse(results);
  } catch (err) {
    console.error("Unexpected error:", err);
    return errorResponse("Internal server error", 500);
  }
});
