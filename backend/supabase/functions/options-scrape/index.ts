// options-scrape: Fetch and store options chain data from Tradier
// POST /options-scrape { symbol: "AAPL" }
// POST /options-scrape { symbols: ["AAPL", "SPY"] }
// POST /options-scrape { all_watchlist: true }
//
// This function fetches options chains from Tradier and stores snapshots in Supabase.
// Called when a symbol is added to watchlist or on daily schedule.

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
};

interface ScrapeRequest {
  symbol?: string;
  symbols?: string[];
  all_watchlist?: boolean;
  max_expirations?: number;
}

interface OptionData {
  symbol: string;
  option_type: string;
  strike: number;
  expiration_date: string;
  bid: number;
  ask: number;
  last: number;
  volume: number;
  open_interest: number;
  greeks?: {
    delta?: number;
    gamma?: number;
    theta?: number;
    vega?: number;
    rho?: number;
    mid_iv?: number;
  };
}

const TRADIER_BASE_URL = "https://api.tradier.com/v1";

async function tradierFetch(endpoint: string, apiKey: string): Promise<any> {
  const response = await fetch(`${TRADIER_BASE_URL}${endpoint}`, {
    headers: {
      Authorization: `Bearer ${apiKey}`,
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Tradier API error: ${response.status} ${await response.text()}`);
  }

  return response.json();
}

async function getExpirations(symbol: string, apiKey: string): Promise<string[]> {
  const data = await tradierFetch(
    `/markets/options/expirations?symbol=${symbol}`,
    apiKey
  );
  const expirations = data?.expirations?.date;
  if (!expirations) return [];
  return Array.isArray(expirations) ? expirations : [expirations];
}

async function getOptionsChain(
  symbol: string,
  expiration: string,
  apiKey: string
): Promise<OptionData[]> {
  const data = await tradierFetch(
    `/markets/options/chains?symbol=${symbol}&expiration=${expiration}&greeks=true`,
    apiKey
  );

  const options = data?.options?.option;
  if (!options) return [];
  return Array.isArray(options) ? options : [options];
}

async function getQuote(symbol: string, apiKey: string): Promise<number> {
  const data = await tradierFetch(`/markets/quotes?symbols=${symbol}`, apiKey);
  const quote = data?.quotes?.quote;
  if (Array.isArray(quote)) {
    return quote[0]?.last || quote[0]?.close || 0;
  }
  return quote?.last || quote?.close || 0;
}

function safeFloat(val: any, defaultVal = 0): number {
  if (val === null || val === undefined || val === "") return defaultVal;
  const num = parseFloat(val);
  return isNaN(num) ? defaultVal : num;
}

function safeInt(val: any, defaultVal = 0): number {
  if (val === null || val === undefined || val === "") return defaultVal;
  const num = parseInt(val, 10);
  return isNaN(num) ? defaultVal : num;
}

serve(async (req: Request): Promise<Response> => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), {
      status: 405,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  try {
    const supabase = createClient(
      Deno.env.get("SUPABASE_URL") ?? "",
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? ""
    );

    const tradierApiKey = Deno.env.get("TRADIER_API_KEY");
    if (!tradierApiKey) {
      return new Response(
        JSON.stringify({ error: "TRADIER_API_KEY not configured" }),
        {
          status: 500,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        }
      );
    }

    const body: ScrapeRequest = await req.json();
    const maxExpirations = body.max_expirations || 4;

    // Determine which symbols to scrape
    let symbolsToScrape: string[] = [];

    if (body.all_watchlist) {
      // Get all unique symbols from watchlists
      const { data: watchlistItems } = await supabase
        .from("watchlist_items")
        .select("symbols!inner(ticker)");

      symbolsToScrape = [
        ...new Set(watchlistItems?.map((item: any) => item.symbols.ticker) || []),
      ];
    } else if (body.symbols) {
      symbolsToScrape = body.symbols.map((s) => s.toUpperCase());
    } else if (body.symbol) {
      symbolsToScrape = [body.symbol.toUpperCase()];
    }

    if (symbolsToScrape.length === 0) {
      return new Response(
        JSON.stringify({ error: "No symbols specified" }),
        {
          status: 400,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        }
      );
    }

    console.log(`[options-scrape] Scraping ${symbolsToScrape.length} symbols:`, symbolsToScrape);

    const results: Record<string, number> = {};
    const errors: string[] = [];
    const snapshotTime = new Date().toISOString();

    for (const symbol of symbolsToScrape) {
      try {
        console.log(`[options-scrape] Processing ${symbol}...`);

        // Get symbol ID
        const { data: symbolRecord } = await supabase
          .from("symbols")
          .select("id")
          .eq("ticker", symbol)
          .single();

        if (!symbolRecord) {
          errors.push(`Symbol ${symbol} not found in database`);
          continue;
        }

        // Get underlying price
        const underlyingPrice = await getQuote(symbol, tradierApiKey);

        // Get expirations
        const expirations = await getExpirations(symbol, tradierApiKey);
        const expirationsToFetch = expirations.slice(0, maxExpirations);

        let totalOptions = 0;

        for (const expiration of expirationsToFetch) {
          const chain = await getOptionsChain(symbol, expiration, tradierApiKey);

          const records = chain.map((opt) => ({
            underlying_symbol_id: symbolRecord.id,
            contract_symbol: opt.symbol || "",
            option_type: opt.option_type || "",
            strike: safeFloat(opt.strike),
            expiration: expiration,
            bid: safeFloat(opt.bid),
            ask: safeFloat(opt.ask),
            last: safeFloat(opt.last),
            volume: safeInt(opt.volume),
            open_interest: safeInt(opt.open_interest),
            underlying_price: underlyingPrice,
            snapshot_time: snapshotTime,
            delta: safeFloat(opt.greeks?.delta),
            gamma: safeFloat(opt.greeks?.gamma),
            theta: safeFloat(opt.greeks?.theta),
            vega: safeFloat(opt.greeks?.vega),
            rho: safeFloat(opt.greeks?.rho),
            iv: safeFloat(opt.greeks?.mid_iv),
          }));

          if (records.length > 0) {
            const { error: upsertError } = await supabase
              .from("options_snapshots")
              .upsert(records, { onConflict: "contract_symbol,snapshot_time" });

            if (upsertError) {
              errors.push(`Failed to save ${symbol} ${expiration}: ${upsertError.message}`);
            } else {
              totalOptions += records.length;
            }
          }

          // Small delay to avoid rate limiting
          await new Promise((resolve) => setTimeout(resolve, 200));
        }

        results[symbol] = totalOptions;
        console.log(`[options-scrape] Saved ${totalOptions} options for ${symbol}`);
      } catch (err) {
        const errMsg = err instanceof Error ? err.message : String(err);
        errors.push(`Error scraping ${symbol}: ${errMsg}`);
        console.error(`[options-scrape] Error for ${symbol}:`, err);
      }
    }

    const totalSaved = Object.values(results).reduce((a, b) => a + b, 0);
    console.log(`[options-scrape] Complete: ${totalSaved} total options saved`);

    return new Response(
      JSON.stringify({
        success: true,
        total_options: totalSaved,
        results,
        errors: errors.length > 0 ? errors : undefined,
      }),
      {
        status: 200,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  } catch (error) {
    console.error("[options-scrape] Error:", error);
    return new Response(
      JSON.stringify({ error: error.message || "Internal server error" }),
      {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  }
});
