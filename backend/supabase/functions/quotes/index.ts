// quotes: Get real-time quotes from Tradier
// GET /quotes?symbols=AAPL,MSFT,SPY
// POST /quotes { symbols: ["AAPL", "MSFT"] }
// POST /quotes { all_watchlist: true }
//
// Lightweight endpoint for fetching current prices without full intraday data.

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
};

interface QuoteData {
  symbol: string;
  last: number;
  bid: number;
  ask: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  change: number;
  change_percentage: number;
  average_volume: number;
  week_52_high: number;
  week_52_low: number;
  last_trade_time: string;
}

const TRADIER_BASE_URL = "https://api.tradier.com/v1";

function safeFloat(val: any, defaultVal = 0): number {
  if (val === null || val === undefined || val === "") return defaultVal;
  const num = parseFloat(val);
  return isNaN(num) ? defaultVal : num;
}

async function getQuotes(symbols: string[], apiKey: string): Promise<QuoteData[]> {
  const symbolsStr = symbols.join(",");

  const response = await fetch(`${TRADIER_BASE_URL}/markets/quotes?symbols=${symbolsStr}`, {
    headers: {
      Authorization: `Bearer ${apiKey}`,
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Tradier API error: ${response.status} ${await response.text()}`);
  }

  const data = await response.json();
  const quotes = data?.quotes?.quote;

  if (!quotes) return [];

  const quotesArray = Array.isArray(quotes) ? quotes : [quotes];

  return quotesArray.map((q: any) => ({
    symbol: q.symbol,
    last: safeFloat(q.last),
    bid: safeFloat(q.bid),
    ask: safeFloat(q.ask),
    open: safeFloat(q.open),
    high: safeFloat(q.high),
    low: safeFloat(q.low),
    close: safeFloat(q.close || q.prevclose),
    volume: safeFloat(q.volume),
    change: safeFloat(q.change),
    change_percentage: safeFloat(q.change_percentage),
    average_volume: safeFloat(q.average_volume),
    week_52_high: safeFloat(q.week_52_high),
    week_52_low: safeFloat(q.week_52_low),
    last_trade_time: q.trade_date || new Date().toISOString(),
  }));
}

async function getMarketClock(apiKey: string): Promise<any> {
  const response = await fetch(`${TRADIER_BASE_URL}/markets/clock`, {
    headers: {
      Authorization: `Bearer ${apiKey}`,
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    return { state: "unknown" };
  }

  const data = await response.json();
  return data?.clock || { state: "unknown" };
}

serve(async (req: Request): Promise<Response> => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
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

    let symbolsToFetch: string[] = [];

    // Handle GET request
    if (req.method === "GET") {
      const url = new URL(req.url);
      const symbolsParam = url.searchParams.get("symbols");
      if (symbolsParam) {
        symbolsToFetch = symbolsParam.split(",").map((s) => s.trim().toUpperCase());
      }
    }

    // Handle POST request
    if (req.method === "POST") {
      const body = await req.json();

      if (body.all_watchlist) {
        const { data: watchlistItems } = await supabase
          .from("watchlist_items")
          .select("symbols!inner(ticker)");

        symbolsToFetch = [
          ...new Set(watchlistItems?.map((item: any) => item.symbols.ticker) || []),
        ];
      } else if (body.symbols) {
        symbolsToFetch = body.symbols.map((s: string) => s.toUpperCase());
      } else if (body.symbol) {
        symbolsToFetch = [body.symbol.toUpperCase()];
      }
    }

    if (symbolsToFetch.length === 0) {
      return new Response(
        JSON.stringify({ error: "No symbols specified" }),
        {
          status: 400,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        }
      );
    }

    // Limit batch size to avoid API issues
    const MAX_BATCH_SIZE = 50;
    if (symbolsToFetch.length > MAX_BATCH_SIZE) {
      symbolsToFetch = symbolsToFetch.slice(0, MAX_BATCH_SIZE);
    }

    console.log(`[quotes] Fetching ${symbolsToFetch.length} quotes:`, symbolsToFetch);

    // Fetch quotes and market status in parallel
    const [quotes, clock] = await Promise.all([
      getQuotes(symbolsToFetch, tradierApiKey),
      getMarketClock(tradierApiKey),
    ]);

    console.log(`[quotes] Fetched ${quotes.length} quotes, market: ${clock.state}`);

    return new Response(
      JSON.stringify({
        success: true,
        market_state: clock.state,
        market_description: clock.description,
        timestamp: new Date().toISOString(),
        count: quotes.length,
        quotes,
      }),
      {
        status: 200,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  } catch (error) {
    console.error("[quotes] Error:", error);
    return new Response(
      JSON.stringify({ error: error.message || "Internal server error" }),
      {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  }
});
