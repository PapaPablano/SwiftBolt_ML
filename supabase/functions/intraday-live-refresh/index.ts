// Proactive intraday live refresh
// Called by pg_cron every 15 min during market hours.
// Fetches today's m15/h1/h4 bars from Alpaca for all watchlist symbols.

import { serve } from "https://deno.land/std@0.224.0/http/server.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";
import { AlpacaClient } from "../_shared/providers/alpaca-client.ts";
import { TokenBucketRateLimiter } from "../_shared/rate-limiter/token-bucket.ts";
import { MemoryCache } from "../_shared/cache/memory-cache.ts";

const TIMEFRAMES_TO_REFRESH = ["m15", "h1", "h4"] as const;
const MULTI_SYMBOL_BATCH_SIZE = 50; // Alpaca supports up to 100 per request

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type, x-sb-gateway-key",
};

// Supabase FK join returns symbols as array for non-unique FKs
interface WatchlistRow {
  ticker: string;
  symbols: { id: string }[] | { id: string } | null;
}

interface ResolvedSymbol {
  ticker: string;
  symbolId: string;
}

function isResolvedSymbol(
  s: { ticker: string; symbolId: string | undefined },
): s is ResolvedSymbol {
  return typeof s.ticker === "string" && typeof s.symbolId === "string";
}

// Market hours: 9:30 AM – 4:00 PM ET = 13:30 – 21:00 UTC
function getMarketOpenUTCToday(): Date {
  const d = new Date();
  d.setUTCHours(13, 30, 0, 0);
  return d;
}

serve(async (req) => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  // ── Auth: gateway key (fail-closed) ──────────────────────────────────────
  const expectedKey = Deno.env.get("SB_GATEWAY_KEY");
  if (!expectedKey || expectedKey.length === 0) {
    console.error("[intraday-live-refresh] SB_GATEWAY_KEY is not set");
    return new Response(
      JSON.stringify({ error: "Gateway key not configured" }),
      {
        status: 503,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      },
    );
  }
  const providedKey = req.headers.get("x-sb-gateway-key") ??
    req.headers.get("X-SB-Gateway-Key") ?? "";
  if (providedKey !== expectedKey) {
    console.warn("[intraday-live-refresh] Invalid or missing X-SB-Gateway-Key");
    return new Response(
      JSON.stringify({ error: "Unauthorized" }),
      {
        status: 401,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      },
    );
  }

  const supabase = getSupabaseClient();

  // ── Market hours check (fail-open: proceed if RPC unavailable) ────────────
  try {
    const { data: isOpen } = await supabase.rpc("is_market_open");
    if (!isOpen) {
      return new Response(
        JSON.stringify({ skipped: true, reason: "market_closed" }),
        {
          status: 200,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        },
      );
    }
  } catch (err: unknown) {
    // Fall through — use UTC time check as backup
    // NOTE: UTC fallback assumes EDT (13:30-21:00). During EST (Nov-Mar),
    // market opens at 14:30 UTC. The is_market_open() RPC handles DST
    // correctly; this is only a last-resort fallback.
    const msg = err instanceof Error ? err.message : String(err);
    console.warn(
      "[intraday-live-refresh] is_market_open RPC failed, using UTC check:",
      msg,
    );
    const now = new Date();
    const nowMinutes = now.getUTCHours() * 60 + now.getUTCMinutes();
    // 13:30 UTC = 810 min, 21:00 UTC = 1260 min (EDT only)
    if (nowMinutes < 810 || nowMinutes > 1260) {
      return new Response(
        JSON.stringify({ skipped: true, reason: "market_closed_utc_check" }),
        {
          status: 200,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        },
      );
    }
  }

  // ── Get all watchlist symbols ─────────────────────────────────────────────
  const { data: watchlistRows, error: watchlistError } = await supabase
    .from("watchlist_items")
    .select("ticker, symbols(id)")
    .not("ticker", "is", null);

  if (watchlistError) {
    console.error(
      "[intraday-live-refresh] Watchlist query failed:",
      watchlistError,
    );
    return new Response(
      JSON.stringify({ error: "Failed to load watchlist" }),
      {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      },
    );
  }

  // Deduplicate by ticker
  const rows = (watchlistRows ?? []) as unknown as WatchlistRow[];
  const symbols = [
    ...new Map(
      rows.map((r) => {
        const sym = Array.isArray(r.symbols) ? r.symbols[0] : r.symbols;
        return [
          r.ticker,
          { ticker: r.ticker, symbolId: sym?.id },
        ] as const;
      }),
    ).values(),
  ].filter(isResolvedSymbol);

  if (symbols.length === 0) {
    return new Response(
      JSON.stringify({ processed: 0, reason: "empty_watchlist" }),
      {
        status: 200,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      },
    );
  }

  // ── Initialize Alpaca client ──────────────────────────────────────────────
  const rateLimiter = new TokenBucketRateLimiter({
    alpaca: { maxPerSecond: 200, maxPerMinute: 10000 },
    finnhub: { maxPerSecond: 10, maxPerMinute: 600 },
    massive: { maxPerSecond: 10, maxPerMinute: 600 },
    yahoo: { maxPerSecond: 10, maxPerMinute: 600 },
    tradier: { maxPerSecond: 10, maxPerMinute: 600 },
  });
  const cache = new MemoryCache(1000);
  const alpaca = new AlpacaClient(
    Deno.env.get("ALPACA_API_KEY")!,
    Deno.env.get("ALPACA_API_SECRET")!,
    rateLimiter,
    cache,
  );

  const startOfSession = getMarketOpenUTCToday();
  const now = new Date();
  const startTs = Math.floor(startOfSession.getTime() / 1000);
  const endTs = Math.floor(now.getTime() / 1000);

  // ── Process all timeframes ────────────────────────────────────────────────
  const DEADLINE_MS = 55_000; // bail at 55s before pg_cron's 58s kill
  const functionStart = Date.now();
  const errors: Array<{ ticker: string; timeframe: string; error: string }> =
    [];
  let totalUpserted = 0;
  let hitDeadline = false;

  for (const tf of TIMEFRAMES_TO_REFRESH) {
    if (hitDeadline) break;
    for (let i = 0; i < symbols.length; i += MULTI_SYMBOL_BATCH_SIZE) {
      if (Date.now() - functionStart > DEADLINE_MS) {
        console.warn("[intraday-live-refresh] Approaching deadline, stopping");
        hitDeadline = true;
        break;
      }
      const batch = symbols.slice(i, i + MULTI_SYMBOL_BATCH_SIZE);

      try {
        const tickers = batch.map((s) => s.ticker);
        const barsBySymbol = await alpaca.getMultiSymbolBars({
          symbols: tickers,
          timeframe: tf,
          start: startTs,
          end: endTs,
        });

        // Build upsert rows for all symbols in batch
        const allRows: Array<Record<string, unknown>> = [];
        for (const { ticker, symbolId } of batch) {
          const bars = barsBySymbol[ticker] ?? [];
          for (const b of bars) {
            allRows.push({
              symbol_id: symbolId,
              timeframe: tf,
              ts: new Date(b.timestamp * 1000).toISOString(),
              open: b.open,
              high: b.high,
              low: b.low,
              close: b.close,
              volume: b.volume,
              provider: "alpaca",
              is_forecast: false,
              is_intraday: true,
              data_status: "live",
            });
          }
        }

        if (allRows.length === 0) continue;

        const { error: upsertError } = await supabase
          .from("ohlc_bars_v2")
          .upsert(allRows, {
            onConflict: "symbol_id,timeframe,ts,provider,is_forecast",
            ignoreDuplicates: false,
          });

        if (upsertError) {
          console.error(
            `[intraday-live-refresh] Batch upsert error ${tf}:`,
            upsertError,
          );
          for (const { ticker } of batch) {
            errors.push({ ticker, timeframe: tf, error: upsertError.message });
          }
        } else {
          totalUpserted += allRows.length;
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        console.error(
          `[intraday-live-refresh] Batch fetch error ${tf}:`,
          msg,
        );
        for (const { ticker } of batch) {
          errors.push({ ticker, timeframe: tf, error: msg });
        }
      }
    }
  }

  const result = {
    processed: symbols.length,
    timeframes: [...TIMEFRAMES_TO_REFRESH],
    totalUpserted,
    errors: errors.length,
    errorDetails: errors.slice(0, 10),
    errorsTruncated: errors.length > 10,
    hitDeadline,
  };

  console.log(
    "[intraday-live-refresh] Complete:",
    JSON.stringify(result),
  );

  return new Response(JSON.stringify(result), {
    status: 200,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
});
