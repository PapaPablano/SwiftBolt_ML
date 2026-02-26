// symbols-search: Search for symbols by ticker or description
// GET /symbols-search?q=AAPL
//
// Enhanced with first-class futures support:
// - Returns futures roots (GC, ES) with requires_expiry_picker flag
// - Returns dated contracts (GCJ26) and continuous aliases (GC1!)
// - Shows expiry information for dated contracts
//
// Hybrid search strategy:
// 1. First search local Postgres 'symbols' table (fast, cached)
// 2. Include futures roots, contracts, and continuous aliases
// 3. If no results, fallback to Finnhub API (comprehensive, live)
// 4. Auto-save discovered symbols to database for future searches

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import {
  corsHeaders,
  errorResponse,
  handleCorsOptions,
  jsonResponse,
} from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";

interface SymbolResult {
  id: string;
  ticker: string;
  asset_type: string;
  description: string | null;
  requires_expiry_picker?: boolean;
  root_symbol?: string;
  is_continuous?: boolean;
  expiry_info?: {
    month: number;
    year: number;
    last_trade_date: string | null;
  };
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
    console.warn(
      "[Symbol Search] FINNHUB_API_KEY not set, skipping API search",
    );
    return [];
  }

  try {
    const url = `https://finnhub.io/api/v1/search?q=${
      encodeURIComponent(query)
    }&token=${apiKey}`;
    const response = await fetch(url);

    if (!response.ok) {
      console.error(`[Symbol Search] Finnhub API error: ${response.status}`);
      return [];
    }

    const data: FinnhubSearchResponse = await response.json();
    console.log(
      `[Symbol Search] Finnhub returned ${data.count} results for "${query}"`,
    );

    return data.result || [];
  } catch (err) {
    console.error("[Symbol Search] Finnhub API request failed:", err);
    return [];
  }
}

async function saveSymbolToDatabase(
  symbol: FinnhubSearchResult,
  supabase: any,
): Promise<string | null> {
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

// Check if a query matches a futures root
async function getFuturesRoot(
  query: string,
  supabase: any,
): Promise<SymbolResult | null> {
  try {
    const { data: root, error } = await supabase
      .from("futures_roots")
      .select("id, symbol, name, exchange, sector")
      .eq("symbol", query.toUpperCase())
      .single();

    if (error || !root) {
      return null;
    }

    return {
      id: root.id,
      ticker: root.symbol,
      asset_type: "future",
      description: `${root.name} (${root.exchange}) [Select Expiry →]`,
      requires_expiry_picker: true,
      root_symbol: root.symbol,
      is_continuous: false,
    };
  } catch (err) {
    console.error("[Symbol Search] Error checking futures root:", err);
    return null;
  }
}

// Search for futures contracts and continuous aliases
async function searchFuturesSymbols(
  query: string,
  supabase: any,
): Promise<SymbolResult[]> {
  const results: SymbolResult[] = [];

  try {
    // Check if query matches a futures root exactly
    const rootResult = await getFuturesRoot(query, supabase);
    if (rootResult) {
      results.push(rootResult);
    }

    // Search for dated contracts and continuous aliases
    const { data: symbols, error } = await supabase
      .from("symbols")
      .select(`
        id, 
        ticker, 
        asset_type, 
        description,
        futures_root_id,
        is_continuous,
        expiry_month,
        expiry_year,
        last_trade_date,
        futures_roots!symbols_futures_root_id_fkey (symbol)
      `)
      .eq("asset_type", "future")
      .or(`ticker.ilike.${query}%,ticker.ilike.%${query}%`)
      .limit(20);

    if (error) {
      console.error("[Symbol Search] Error searching futures symbols:", error);
      return results;
    }

    for (const sym of symbols || []) {
      // Skip if we already added the root
      if (
        sym.ticker === query.toUpperCase() &&
        sym.futures_roots?.symbol === sym.ticker
      ) {
        continue;
      }

      const result: SymbolResult = {
        id: sym.id,
        ticker: sym.ticker,
        asset_type: sym.asset_type,
        description: sym.description,
        root_symbol: sym.futures_roots?.symbol,
        is_continuous: sym.is_continuous || false,
      };

      // Add expiry info for dated contracts
      if (!sym.is_continuous && sym.expiry_month && sym.expiry_year) {
        result.expiry_info = {
          month: sym.expiry_month,
          year: sym.expiry_year,
          last_trade_date: sym.last_trade_date,
        };
      }

      results.push(result);
    }

    return results;
  } catch (err) {
    console.error("[Symbol Search] Error in searchFuturesSymbols:", err);
    return results;
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

    // STEP 1: Search for futures symbols (roots, contracts, continuous aliases)
    const futuresResults = await searchFuturesSymbols(searchTerm, supabase);
    if (futuresResults.length > 0) {
      console.log(
        `[Symbol Search] Found ${futuresResults.length} futures results`,
      );
      return jsonResponse(futuresResults);
    }

    // STEP 2: Search local database for stocks/options/crypto
    // Try exact ticker match first (case-insensitive)
    const { data: exactMatch, error: exactError } = await supabase
      .from("symbols")
      .select("id, ticker, asset_type, description")
      .ilike("ticker", searchTerm)
      .limit(20);

    if (!exactError && exactMatch && exactMatch.length > 0) {
      console.log(
        `[Symbol Search] Found ${exactMatch.length} exact ticker match(es) in local DB`,
      );
      return jsonResponse(exactMatch);
    }

    // For short queries (1-4 chars), skip partial matching and go straight to API
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
        console.log(
          `[Symbol Search] Found ${dbResults.length} results in local DB (partial match)`,
        );
        return jsonResponse(dbResults);
      }
    } else {
      console.log(
        `[Symbol Search] Short query detected, skipping partial match`,
      );
    }

    // STEP 3: No local results - fallback to Finnhub API
    console.log(`[Symbol Search] No local results, querying Finnhub API...`);
    const apiResults = await searchFinnhub(searchTerm);

    if (apiResults.length === 0) {
      console.log(`[Symbol Search] No results from Finnhub either`);
      return jsonResponse([]);
    }

    // STEP 4: Save discovered symbols to database for future searches
    const savedSymbols: SymbolResult[] = [];

    for (const apiSymbol of apiResults.slice(0, 20)) { // Limit to 20 results
      const symbolId = await saveSymbolToDatabase(apiSymbol, supabase);

      if (symbolId) {
        savedSymbols.push({
          id: symbolId,
          ticker: apiSymbol.symbol.toUpperCase(),
          asset_type: apiSymbol.type.toLowerCase().includes("forex")
            ? "forex"
            : apiSymbol.type.toLowerCase().includes("crypto")
            ? "crypto"
            : apiSymbol.type.toLowerCase().includes("future")
            ? "future"
            : "stock",
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

    console.log(
      `[Symbol Search] Returning ${savedSymbols.length} results from Finnhub`,
    );
    return jsonResponse(savedSymbols);
  } catch (err) {
    console.error("[Symbol Search] Unexpected error:", err);
    return errorResponse("Internal server error", 500);
  }
});
