// supabase/functions/ingest-live/index.ts
// Ingest m1 + m15 bars for all watchlist symbols during market hours.
// Called by pg_cron every minute on weekdays 9:30–16:00 ET.
// m1 bars: stored for partial-candle synthesis.
// m15 bars: stored for chart display (replaces unreliable GH Actions cron).

import { serve } from "https://deno.land/std@0.224.0/http/server.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";
import { AlpacaClient } from "../_shared/providers/alpaca-client.ts";
import { TokenBucketRateLimiter } from "../_shared/rate-limiter/token-bucket.ts";
import { MemoryCache } from "../_shared/cache/memory-cache.ts";

const MULTI_SYMBOL_BATCH_SIZE = 100; // Alpaca supports up to 100 per multi-bar request

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

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  // ── Auth: gateway key (fail-closed) ─────────────────────────────────────
  const expectedKey = Deno.env.get("SB_GATEWAY_KEY");
  if (!expectedKey || expectedKey.length === 0) {
    console.error("[ingest-live] SB_GATEWAY_KEY is not set");
    return new Response(
      JSON.stringify({ error: "Gateway key not configured" }),
      {
        status: 503,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      },
    );
  }
  const providedKey = req.headers.get("x-sb-gateway-key") ??
    req.headers.get("X-SB-Gateway-Key") ??
    "";
  if (providedKey !== expectedKey) {
    console.warn("[ingest-live] Invalid or missing X-SB-Gateway-Key");
    return new Response(JSON.stringify({ error: "Unauthorized" }), {
      status: 401,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  const supabase = getSupabaseClient();

  // ── Market hours check (fail-open: proceed if RPC unavailable) ───────────
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
    // Fall through — use UTC time check as last-resort backup.
    // NOTE: This fallback assumes EDT (13:30-21:00 UTC). During EST (Nov-Mar),
    // market opens at 14:30 UTC. The is_market_open() RPC handles DST correctly.
    const msg = err instanceof Error ? err.message : String(err);
    console.warn(
      "[ingest-live] is_market_open RPC failed, using UTC check:",
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

  // ── Fetch watchlist symbols ──────────────────────────────────────────────
  const { data: watchlistRows, error: watchlistError } = await supabase
    .from("watchlist_items")
    .select("ticker, symbols(id)")
    .not("ticker", "is", null);

  if (watchlistError) {
    console.error("[ingest-live] Watchlist query failed:", watchlistError);
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

  // ── Initialize Alpaca client ─────────────────────────────────────────────
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

  // Fetch the last 5 minutes of m1 bars to ensure we don't miss the latest
  // completed minute (Alpaca data is typically available within ~15s of close).
  const now = new Date();
  const windowStart = new Date(now.getTime() - 5 * 60 * 1000);
  const startTs = Math.floor(windowStart.getTime() / 1000);
  const endTs = Math.floor(now.getTime() / 1000);

  // ── Batch upsert m1 bars ─────────────────────────────────────────────────
  const DEADLINE_MS = 25_000; // pg_cron fires every minute; bail at 25s
  const functionStart = Date.now();
  const errors: Array<{ ticker: string; error: string }> = [];
  let totalUpserted = 0;
  let hitDeadline = false;

  for (let i = 0; i < symbols.length; i += MULTI_SYMBOL_BATCH_SIZE) {
    if (Date.now() - functionStart > DEADLINE_MS) {
      console.warn("[ingest-live] Approaching deadline, stopping");
      hitDeadline = true;
      break;
    }

    const batch = symbols.slice(i, i + MULTI_SYMBOL_BATCH_SIZE);

    try {
      const tickers = batch.map((s) => s.ticker);
      const barsBySymbol = await alpaca.getMultiSymbolBars({
        symbols: tickers,
        timeframe: "m1",
        start: startTs,
        end: endTs,
      });

      const allRows: Array<Record<string, unknown>> = [];
      for (const { ticker, symbolId } of batch) {
        const bars = barsBySymbol[ticker] ?? [];
        for (const b of bars) {
          allRows.push({
            symbol_id: symbolId,
            timeframe: "m1",
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
        console.error("[ingest-live] Batch upsert error:", upsertError);
        for (const { ticker } of batch) {
          errors.push({ ticker, error: upsertError.message });
        }
      } else {
        totalUpserted += allRows.length;
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error("[ingest-live] Batch fetch error:", msg);
      for (const { ticker } of batch) {
        errors.push({ ticker, error: msg });
      }
    }
  }

  // ── Second pass: m15 bars (every run, same symbols) ──────────────────────
  // This ensures m15 chart data stays fresh via reliable pg_cron instead of
  // depending on unreliable GitHub Actions scheduled workflows.
  let m15Upserted = 0;
  if (!hitDeadline) {
    const m15Window = new Date(now.getTime() - 20 * 60 * 1000); // last 20 min
    const m15Start = Math.floor(m15Window.getTime() / 1000);

    for (let i = 0; i < symbols.length; i += MULTI_SYMBOL_BATCH_SIZE) {
      if (Date.now() - functionStart > DEADLINE_MS) {
        console.warn("[ingest-live] Approaching deadline during m15 pass");
        hitDeadline = true;
        break;
      }

      const batch = symbols.slice(i, i + MULTI_SYMBOL_BATCH_SIZE);

      try {
        const tickers = batch.map((s) => s.ticker);
        const barsBySymbol = await alpaca.getMultiSymbolBars({
          symbols: tickers,
          timeframe: "m15",
          start: m15Start,
          end: endTs,
        });

        const m15Rows: Array<Record<string, unknown>> = [];
        for (const { ticker, symbolId } of batch) {
          const bars = barsBySymbol[ticker] ?? [];
          for (const b of bars) {
            m15Rows.push({
              symbol_id: symbolId,
              timeframe: "m15",
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

        if (m15Rows.length === 0) continue;

        const { error: m15Error } = await supabase
          .from("ohlc_bars_v2")
          .upsert(m15Rows, {
            onConflict: "symbol_id,timeframe,ts,provider,is_forecast",
            ignoreDuplicates: false,
          });

        if (m15Error) {
          console.error("[ingest-live] m15 upsert error:", m15Error);
        } else {
          m15Upserted += m15Rows.length;
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        console.error("[ingest-live] m15 batch error:", msg);
      }
    }
  }

  // ── Third pass: Kalman forecast adjustment ───────────────────────────────
  // Adjusts cached intraday forecast target_prices based on actual price
  // movement since the forecast was generated. Keeps forecasts fresh between
  // weekly full-ensemble training runs.
  const KALMAN_GAIN = 0.15; // matches ml/src/intraday_forecast_job.py kalman_weight
  const ADJUSTMENT_HORIZONS = ["15m", "1h", "4h"];
  let forecastsAdjusted = 0;

  if (!hitDeadline) {
    for (const { ticker, symbolId } of symbols) {
      if (Date.now() - functionStart > DEADLINE_MS) {
        console.warn("[ingest-live] Deadline during forecast adjustment");
        hitDeadline = true;
        break;
      }

      try {
        // Get the latest m15 close price for this symbol (just written above)
        const { data: latestBar } = await supabase
          .from("ohlc_bars_v2")
          .select("close")
          .eq("symbol_id", symbolId)
          .eq("timeframe", "m15")
          .eq("is_forecast", false)
          .order("ts", { ascending: false })
          .limit(1)
          .single();

        if (!latestBar?.close) continue;
        const actualClose = Number(latestBar.close);

        // For each intraday horizon, adjust the latest non-expired forecast
        for (const horizon of ADJUSTMENT_HORIZONS) {
          const { data: forecast } = await supabase
            .from("ml_forecasts_intraday")
            .select("id, target_price, current_price")
            .eq("symbol_id", symbolId)
            .eq("horizon", horizon)
            .gte("expires_at", new Date().toISOString())
            .order("created_at", { ascending: false })
            .limit(1)
            .single();

          if (!forecast?.target_price || !forecast?.current_price) continue;

          const targetPrice = Number(forecast.target_price);
          const forecastBasePrice = Number(forecast.current_price);

          // Kalman adjustment: shift target by gain * (actual movement since forecast)
          const priceMovement = actualClose - forecastBasePrice;
          const adjustedTarget = targetPrice + KALMAN_GAIN * priceMovement;

          const { error: updateError } = await supabase
            .from("ml_forecasts_intraday")
            .update({
              target_price: adjustedTarget,
              current_price: actualClose,
            })
            .eq("id", forecast.id);

          if (!updateError) forecastsAdjusted++;
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        console.error(`[ingest-live] Forecast adjust error for ${ticker}:`, msg);
      }
    }
  }

  const result = {
    processed: symbols.length,
    totalUpserted,
    m15Upserted,
    forecastsAdjusted,
    errors: errors.length,
    errorDetails: errors.slice(0, 10),
    errorsTruncated: errors.length > 10,
    hitDeadline,
  };

  console.log("[ingest-live] Complete:", JSON.stringify(result));

  return new Response(JSON.stringify(result), {
    status: 200,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
});
