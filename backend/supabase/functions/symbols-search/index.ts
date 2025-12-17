// symbols-search: Search for symbols by ticker or description
// GET /symbols-search?q=AAPL
//
// Hybrid search strategy:
// 1. First search local Postgres 'symbols' table (fast, cached)
// 2. If no results, fallback to Finnhub API (comprehensive, live)
// 3. Auto-save discovered symbols to database for future searches
//
// This ensures both speed (for known symbols) and completeness (for new symbols).

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { corsHeaders, handleCorsOptions, jsonResponse, errorResponse } from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";

interface SymbolResult {
  id: string;
  ticker: string;
  asset_type: string;
  description: string | null;
}

interface FinnhubSearchResult {
  description: string;
  displaySymbol: string;
  symbol: string;
  type: string;
}

interface FinnhubSearchResponse {
  count: number;
  result: FinnhubSearchResult[];
}

async function searchFinnhub(query: string): Promise<FinnhubSearchResult[]> {
  const apiKey = Deno.env.get("FINNHUB_API_KEY");
  if (!apiKey) {
    console.warn("[Symbol Search] FINNHUB_API_KEY not set, skipping API search");
    return [];
  }

  try {
    const url = `https://finnhub.io/api/v1/search?q=${encodeURIComponent(query)}&token=${apiKey}`;
    const response = await fetch(url);

    if (!response.ok) {
      console.error(`[Symbol Search] Finnhub API error: ${response.status}`);
      return [];
    }

    const data: FinnhubSearchResponse = await response.json();
    console.log(`[Symbol Search] Finnhub returned ${data.count} results for "${query}"`);

    return data.result || [];
  } catch (err) {
    console.error("[Symbol Search] Finnhub API request failed:", err);
    return [];
  }
}

async function saveSymbolToDatabase(symbol: FinnhubSearchResult, supabase: any): Promise<string | null> {
  try {
    // Map Finnhub type to our asset_type
    let assetType = "stock"; // default
    const typeLower = symbol.type.toLowerCase();
    if (typeLower.includes("forex") || typeLower.includes("fx")) {
      assetType = "forex";
    } else if (typeLower.includes("crypto")) {
      assetType = "crypto";
    } else if (typeLower.includes("future")) {
      assetType = "future";
    }

    // Insert or update symbol
    const { data, error } = await supabase
      .from("symbols")
      .upsert({
        ticker: symbol.symbol.toUpperCase(),
        asset_type: assetType,
        description: symbol.description,
      }, {
        onConflict: "ticker",
        ignoreDuplicates: false,
      })
      .select("id")
      .single();

    if (error) {
      console.error("[Symbol Search] Failed to save symbol to DB:", error);
      return null;
    }

    return data?.id || null;
  } catch (err) {
    console.error("[Symbol Search] Error saving symbol:", err);
    return null;
  }
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

    const searchTerm = query.trim().toUpperCase();
    console.log(`[Symbol Search] Searching for: "${searchTerm}"`);

    // Get Supabase client
    const supabase = getSupabaseClient();

    // STEP 1: Search local database first (fast)
    // Try exact ticker match first (case-insensitive)
    const { data: exactMatch, error: exactError } = await supabase
      .from("symbols")
      .select("id, ticker, asset_type, description")
      .ilike("ticker", searchTerm)
      .limit(20);

    if (!exactError && exactMatch && exactMatch.length > 0) {
      console.log(`[Symbol Search] Found ${exactMatch.length} exact ticker match(es) in local DB`);
      return jsonResponse(exactMatch);
    }

    // For short queries (1-4 chars), skip partial matching and go straight to API
    // This avoids matching "MU" in "ZIM.MU" or "multinational"
    const shouldSkipPartialMatch = searchTerm.length <= 4;

    if (!shouldSkipPartialMatch) {
      // Try partial matching on ticker and description (only for longer queries)
      const { data: dbResults, error: dbError } = await supabase
        .from("symbols")
        .select("id, ticker, asset_type, description")
        .or(`ticker.ilike.%${searchTerm}%,description.ilike.%${searchTerm}%`)
        .order("ticker", { ascending: true })
        .limit(20);

      if (!dbError && dbResults && dbResults.length > 0) {
        console.log(`[Symbol Search] Found ${dbResults.length} results in local DB (partial match)`);
        return jsonResponse(dbResults);
      }
    } else {
      console.log(`[Symbol Search] Short query detected, skipping partial match`);
    }

    // STEP 2: No local results - fallback to Finnhub API
    console.log(`[Symbol Search] No local results, querying Finnhub API...`);
    const apiResults = await searchFinnhub(searchTerm);

    if (apiResults.length === 0) {
      console.log(`[Symbol Search] No results from Finnhub either`);
      return jsonResponse([]);
    }

    // STEP 3: Save discovered symbols to database for future searches
    const savedSymbols: SymbolResult[] = [];

    for (const apiSymbol of apiResults.slice(0, 20)) { // Limit to 20 results
      const symbolId = await saveSymbolToDatabase(apiSymbol, supabase);

      if (symbolId) {
        savedSymbols.push({
          id: symbolId,
          ticker: apiSymbol.symbol.toUpperCase(),
          asset_type: apiSymbol.type.toLowerCase().includes("forex") ? "forex" :
                     apiSymbol.type.toLowerCase().includes("crypto") ? "crypto" :
                     apiSymbol.type.toLowerCase().includes("future") ? "future" : "stock",
          description: apiSymbol.description,
        });
      } else {
        // Even if save failed, return the result
        savedSymbols.push({
          id: crypto.randomUUID(), // Temporary ID
          ticker: apiSymbol.symbol.toUpperCase(),
          asset_type: "stock",
          description: apiSymbol.description,
        });
      }
    }

    console.log(`[Symbol Search] Returning ${savedSymbols.length} results from Finnhub`);
    return jsonResponse(savedSymbols);
  } catch (err) {
    console.error("[Symbol Search] Unexpected error:", err);
    return errorResponse("Internal server error", 500);
  }
});
