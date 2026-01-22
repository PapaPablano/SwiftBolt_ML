import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { getCorsHeaders, handlePreflight, corsResponse } from "../_shared/cors.ts";

declare const Deno: {
  env: {
    get(key: string): string | undefined;
  };
};

function jsonResponse(data: unknown, status = 200, origin: string | null = null): Response {
  const corsHeaders = getCorsHeaders(origin);
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      ...corsHeaders,
      "Content-Type": "application/json",
      "Cache-Control": "no-cache, no-store, must-revalidate",
      "Pragma": "no-cache",
      "Expires": "0",
    },
  });
}

function errorResponse(message: string, status = 400, origin: string | null = null): Response {
  return jsonResponse({ error: message }, status, origin);
}

const ALPACA_DATA_BASE = "https://data.alpaca.markets/v2";
const ALPACA_TRADING_BASE = "https://api.alpaca.markets/v2";

type AlpacaSnapshotsResponse = Record<
  string,
  {
    latestTrade?: { t: string; p: number };
    latestQuote?: { bp: number; ap: number };
    minuteBar?: { t: string; o: number; h: number; l: number; c: number; v: number };
    dailyBar?: { t: string; o: number; h: number; l: number; c: number; v: number };
    prevDailyBar?: { t: string; o: number; h: number; l: number; c: number; v: number };
  }
>;

async function fetchAlpacaJson<T>(
  url: string,
  apiKey: string,
  apiSecret: string
): Promise<T> {
  const res = await fetch(url, {
    headers: {
      "APCA-API-KEY-ID": apiKey,
      "APCA-API-SECRET-KEY": apiSecret,
      Accept: "application/json",
    },
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Alpaca API error: ${res.status} ${body}`);
  }

  return (await res.json()) as T;
}

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

function buildMarketState(isOpen: boolean): { market_state: string; market_description: string } {
  if (isOpen) {
    return { market_state: "open", market_description: "Market is open" };
  }
  return { market_state: "closed", market_description: "Market is closed" };
}

serve(async (req: Request): Promise<Response> => {
  const origin = req.headers.get("origin");
  
  if (req.method === "OPTIONS") {
    return handlePreflight(origin);
  }

  if (req.method !== "GET" && req.method !== "POST") {
    return errorResponse("Method not allowed", 405);
  }

  try {
    const alpacaApiKey = Deno.env.get("ALPACA_API_KEY");
    const alpacaApiSecret = Deno.env.get("ALPACA_API_SECRET");

    if (!alpacaApiKey || !alpacaApiSecret) {
      return errorResponse("ALPACA_API_KEY/ALPACA_API_SECRET not configured", 500, origin);
    }

    let symbolsToFetch: string[] = [];

    if (req.method === "GET") {
      const url = new URL(req.url);
      const symbolsParam = url.searchParams.get("symbols");
      if (symbolsParam) {
        symbolsToFetch = symbolsParam
          .split(",")
          .map((s) => s.trim().toUpperCase())
          .filter((s) => s.length > 0);
      }
    } else {
      let body: unknown;
      try {
        body = await req.json();
      } catch (_err) {
        return errorResponse("Invalid JSON body", 400, origin);
      }

      const bodyObj: Record<string, unknown> =
        typeof body === "object" && body !== null ? (body as Record<string, unknown>) : {};

      if (Array.isArray(bodyObj.symbols)) {
        symbolsToFetch = bodyObj.symbols
          .map((s) => String(s).trim().toUpperCase())
          .filter((s) => s.length > 0);
      } else if (typeof bodyObj.symbol === "string") {
        symbolsToFetch = [bodyObj.symbol.trim().toUpperCase()].filter((s) => s.length > 0);
      }
    }

    if (symbolsToFetch.length === 0) {
      return errorResponse("No symbols specified", 400, origin);
    }

    const MAX_BATCH_SIZE = 50;
    if (symbolsToFetch.length > MAX_BATCH_SIZE) {
      symbolsToFetch = symbolsToFetch.slice(0, MAX_BATCH_SIZE);
    }

    const symbolsParam = symbolsToFetch.join(",");
    const snapshotsUrl = `${ALPACA_DATA_BASE}/stocks/snapshots?symbols=${encodeURIComponent(symbolsParam)}&feed=iex`;
    const clockUrl = `${ALPACA_TRADING_BASE}/clock`;

    const [snapshots, clock] = await Promise.all([
      fetchAlpacaJson<AlpacaSnapshotsResponse>(snapshotsUrl, alpacaApiKey, alpacaApiSecret),
      fetchAlpacaJson<{ is_open: boolean }>(clockUrl, alpacaApiKey, alpacaApiSecret),
    ]);

    const market = buildMarketState(!!clock.is_open);

    const quoteData: QuoteData[] = symbolsToFetch
      .map((symbol) => {
        const snapshot = snapshots[symbol];
        if (!snapshot?.latestTrade?.p) {
          return null;
        }

        const last = snapshot.latestTrade.p;
        const bid = snapshot.latestQuote?.bp ?? 0;
        const ask = snapshot.latestQuote?.ap ?? 0;
        const open = snapshot.dailyBar?.o ?? 0;
        const high = snapshot.dailyBar?.h ?? 0;
        const low = snapshot.dailyBar?.l ?? 0;
        const prevClose = snapshot.prevDailyBar?.c;
        const close = (typeof prevClose === "number" && prevClose > 0) ? prevClose : last;
        const volume = snapshot.dailyBar?.v ?? 0;
        const change = last - close;
        const changePct = close ? (change / close) * 100 : 0;
        const lastTradeTime = snapshot.latestTrade.t;

        return {
          symbol,
          last,
          bid,
          ask,
          open,
          high,
          low,
          close,
          volume,
          change,
          change_percentage: changePct,
          average_volume: 0,
          week_52_high: 0,
          week_52_low: 0,
          last_trade_time: typeof lastTradeTime === "string" ? lastTradeTime : new Date().toISOString(),
        };
      })
      .filter((q): q is QuoteData => q !== null);

    return jsonResponse({
      success: true,
      ...market,
      timestamp: new Date().toISOString(),
      count: quoteData.length,
      quotes: quoteData,
    }, 200, origin);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error("[quotes] Error:", error);
    return errorResponse(message || "Internal server error", 500, origin);
  }
});
