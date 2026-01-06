// intraday-update: Fetch and update intraday OHLCV data from Tradier
// POST /intraday-update { symbol: "AAPL" }
// POST /intraday-update { symbols: ["AAPL", "SPY"] }
// POST /intraday-update { all_watchlist: true }
//
// This function fetches intraday bars and updates the daily view during market hours.
// Can also be used to backfill intraday data for analysis.

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
};

interface UpdateRequest {
  symbol?: string;
  symbols?: string[];
  all_watchlist?: boolean;
  interval?: string; // 1min, 5min, 15min (default: 15min for chart compatibility)
  include_extended?: boolean; // Include pre/post market
  backfill_days?: number; // Number of days to backfill (max 20 for Tradier)
}

interface IntradayBar {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  vwap?: number;
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

async function getMarketClock(apiKey: string): Promise<{ state: string; description: string }> {
  const data = await tradierFetch("/markets/clock", apiKey);
  return data?.clock || { state: "unknown", description: "" };
}

async function getQuote(symbol: string, apiKey: string): Promise<any> {
  const data = await tradierFetch(`/markets/quotes?symbols=${symbol}`, apiKey);
  const quote = data?.quotes?.quote;
  return Array.isArray(quote) ? quote[0] : quote;
}

async function getIntradayBars(
  symbol: string,
  apiKey: string,
  interval: string = "15min",
  sessionFilter: string = "open",
  startDate?: string,
  endDate?: string
): Promise<IntradayBar[]> {
  const today = new Date().toISOString().split("T")[0];
  const start = startDate || today;
  const end = endDate || today;

  const data = await tradierFetch(
    `/markets/timesales?symbol=${symbol}&interval=${interval}&start=${start}&end=${end}&session_filter=${sessionFilter}`,
    apiKey
  );

  const series = data?.series;
  if (!series) return [];

  const bars = series?.data;
  if (!bars) return [];

  return (Array.isArray(bars) ? bars : [bars]).map((bar: any) => ({
    time: bar.time,
    open: parseFloat(bar.open) || 0,
    high: parseFloat(bar.high) || 0,
    low: parseFloat(bar.low) || 0,
    close: parseFloat(bar.close) || parseFloat(bar.price) || 0,
    volume: parseInt(bar.volume) || 0,
    vwap: parseFloat(bar.vwap) || undefined,
  }));
}

function aggregateToDailyBar(bars: IntradayBar[]): {
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  vwap: number;
} {
  if (bars.length === 0) {
    return { open: 0, high: 0, low: 0, close: 0, volume: 0, vwap: 0 };
  }

  const open = bars[0].open;
  const close = bars[bars.length - 1].close;
  const high = Math.max(...bars.map((b) => b.high));
  const low = Math.min(...bars.map((b) => b.low));
  const volume = bars.reduce((sum, b) => sum + b.volume, 0);

  // Calculate VWAP
  const volumePrice = bars.reduce((sum, b) => sum + b.close * b.volume, 0);
  const vwap = volume > 0 ? volumePrice / volume : close;

  return { open, high, low, close, volume, vwap };
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

    const body: UpdateRequest = await req.json();
    const interval = body.interval || "15min"; // Default to 15min for chart compatibility
    const sessionFilter = body.include_extended ? "all" : "open";
    const backfillDays = Math.min(body.backfill_days || 0, 20); // Tradier limits to ~20 days

    // Check market status
    const clock = await getMarketClock(tradierApiKey);
    const isMarketOpen = clock.state === "open";
    console.log(`[intraday-update] Market state: ${clock.state} (${clock.description})`);

    // Determine which symbols to update
    let symbolsToUpdate: string[] = [];

    if (body.all_watchlist) {
      const { data: watchlistItems } = await supabase
        .from("watchlist_items")
        .select("symbols!inner(ticker)");

      symbolsToUpdate = [
        ...new Set(watchlistItems?.map((item: any) => item.symbols.ticker) || []),
      ];
    } else if (body.symbols) {
      symbolsToUpdate = body.symbols.map((s) => s.toUpperCase());
    } else if (body.symbol) {
      symbolsToUpdate = [body.symbol.toUpperCase()];
    }

    if (symbolsToUpdate.length === 0) {
      return new Response(
        JSON.stringify({ error: "No symbols specified" }),
        {
          status: 400,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        }
      );
    }

    console.log(`[intraday-update] Updating ${symbolsToUpdate.length} symbols:`, symbolsToUpdate);

    const results: Record<string, any> = {};
    const errors: string[] = [];
    const today = new Date().toISOString().split("T")[0];

    for (const symbol of symbolsToUpdate) {
      try {
        console.log(`[intraday-update] Processing ${symbol}...`);

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

        // Check if backfill is needed
        const { data: needsBackfill } = await supabase
          .rpc('needs_intraday_backfill', { p_symbol_id: symbolRecord.id });

        if (!needsBackfill && backfillDays > 0) {
          console.log(`[intraday-update] ${symbol} already has recent intraday data, skipping backfill`);
          results[symbol] = { skipped: true, reason: 'Already backfilled recently' };
          continue;
        }

        // Mark backfill as started
        await supabase.rpc('mark_backfill_started', { p_symbol_id: symbolRecord.id });

        // Calculate date range for backfill
        const endDate = new Date().toISOString().split("T")[0];
        let startDate = endDate;
        if (backfillDays > 0) {
          const start = new Date();
          start.setDate(start.getDate() - backfillDays);
          startDate = start.toISOString().split("T")[0];
        }

        // Fetch intraday bars
        const intradayBars = await getIntradayBars(symbol, tradierApiKey, interval, sessionFilter, startDate, endDate);

        // Get current quote for most recent price
        const quote = await getQuote(symbol, tradierApiKey);

        if (intradayBars.length === 0 && !quote) {
          errors.push(`No intraday data available for ${symbol}`);
          continue;
        }

        // Aggregate to daily bar
        const dailyAgg = aggregateToDailyBar(intradayBars);

        // Use quote for most current values if available
        const currentPrice = quote?.last || quote?.close || dailyAgg.close;
        const currentVolume = quote?.volume || dailyAgg.volume;

        // Store raw intraday bars in intraday_bars table for 15m/1h/4h chart views
        if (intradayBars.length > 0) {
          // Map interval to timeframe format
          const timeframeMap: Record<string, string> = {
            "1min": "1m",
            "5min": "5m",
            "15min": "15m",
          };
          const tfValue = timeframeMap[interval] || "5m";

          // Prepare bars for upsert
          const intradayRows = intradayBars.map((bar) => ({
            symbol_id: symbolRecord.id,
            timeframe: tfValue,
            ts: bar.time,
            open: bar.open,
            high: bar.high,
            low: bar.low,
            close: bar.close,
            volume: bar.volume,
            vwap: bar.vwap || null,
          }));

          // Batch upsert intraday bars
          const { error: intradayError } = await supabase
            .from("intraday_bars")
            .upsert(intradayRows, { onConflict: "symbol_id,timeframe,ts" });

          if (intradayError) {
            console.warn(`[intraday-update] Failed to store intraday bars for ${symbol}: ${intradayError.message}`);
          } else {
            console.log(`[intraday-update] Stored ${intradayRows.length} intraday bars for ${symbol} (${tfValue})`);
          }
        }

        // Update or insert today's daily bar
        const { error: upsertError } = await supabase
          .from("ohlc_bars")
          .upsert(
            {
              symbol_id: symbolRecord.id,
              timeframe: "d1",
              ts: today,
              open: dailyAgg.open || currentPrice,
              high: Math.max(dailyAgg.high, currentPrice),
              low: dailyAgg.low > 0 ? Math.min(dailyAgg.low, currentPrice) : currentPrice,
              close: currentPrice,
              volume: currentVolume,
              provider: "tradier",
            },
            { onConflict: "symbol_id,timeframe,ts" }
          );

        if (upsertError) {
          errors.push(`Failed to update ${symbol}: ${upsertError.message}`);
          continue;
        }

        results[symbol] = {
          bars_fetched: intradayBars.length,
          current_price: currentPrice,
          daily_volume: currentVolume,
          daily_high: Math.max(dailyAgg.high, currentPrice),
          daily_low: dailyAgg.low > 0 ? Math.min(dailyAgg.low, currentPrice) : currentPrice,
          vwap: dailyAgg.vwap,
          market_open: isMarketOpen,
        };

        // Mark backfill as completed
        await supabase.rpc('mark_backfill_completed', {
          p_symbol_id: symbolRecord.id,
          p_bar_count: intradayBars.length,
          p_backfill_days: backfillDays
        });

        console.log(`[intraday-update] Updated ${symbol}: ${intradayBars.length} bars, price=${currentPrice}`);

        // Small delay to avoid rate limiting
        await new Promise((resolve) => setTimeout(resolve, 200));
      } catch (err) {
        const errMsg = err instanceof Error ? err.message : String(err);
        errors.push(`Error updating ${symbol}: ${errMsg}`);
        console.error(`[intraday-update] Error for ${symbol}:`, err);
        
        // Mark backfill as failed
        const { data: symbolData } = await supabase
          .from("symbols")
          .select("id")
          .eq("ticker", symbol)
          .single();
        
        if (symbolData) {
          await supabase.rpc('mark_backfill_failed', {
            p_symbol_id: symbolData.id,
            p_error_message: errMsg
          });
        }
      }
    }

    console.log(`[intraday-update] Complete: ${Object.keys(results).length} symbols updated`);

    return new Response(
      JSON.stringify({
        success: true,
        market_state: clock.state,
        symbols_updated: Object.keys(results).length,
        results,
        errors: errors.length > 0 ? errors : undefined,
      }),
      {
        status: 200,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  } catch (error) {
    console.error("[intraday-update] Error:", error);
    return new Response(
      JSON.stringify({ error: error.message || "Internal server error" }),
      {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  }
});
