import { serve } from "https://deno.land/std@0.208.0/http/server.ts";

import { handleCorsOptions, jsonResponse, errorResponse } from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";

type HealthRow = {
  timeframe: string;
  newest_ts: string | null;
  age_seconds: number | null;
  bar_count: number;
};

const TIMEFRAMES = ["m15", "h1", "h4", "d1", "w1"] as const;

type Timeframe = typeof TIMEFRAMES[number];

function isTimeframe(value: string): value is Timeframe {
  return (TIMEFRAMES as readonly string[]).includes(value);
}

serve(async (req: Request): Promise<Response> => {
  if (req.method === "OPTIONS") {
    return handleCorsOptions();
  }

  if (req.method !== "GET") {
    return errorResponse("Method not allowed", 405);
  }

  try {
    const url = new URL(req.url);
    const symbol = (url.searchParams.get("symbol") ?? "").trim().toUpperCase();

    if (!symbol) {
      return errorResponse("symbol is required", 400);
    }

    const supabase = getSupabaseClient();

    const { data: symbolData, error: symbolError } = await supabase
      .from("symbols")
      .select("id")
      .eq("ticker", symbol)
      .single();

    if (symbolError || !symbolData) {
      return jsonResponse({ error: `Symbol ${symbol} not found` }, 404);
    }

    const symbolId = symbolData.id as string;

    const env = {
      alpaca_api_key_present: Boolean(Deno.env.get("ALPACA_API_KEY")),
      alpaca_api_secret_present: Boolean(Deno.env.get("ALPACA_API_SECRET")),
      alpaca_data_feed_present: Boolean(Deno.env.get("ALPACA_DATA_FEED")),
      supabase_url_present: Boolean(Deno.env.get("SUPABASE_URL")),
      service_role_present: Boolean(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")),
    };

    const rows: HealthRow[] = [];

    for (const tf of TIMEFRAMES) {
      const { data: newest } = await supabase
        .from("ohlc_bars_v2")
        .select("ts")
        .eq("symbol_id", symbolId)
        .eq("timeframe", tf)
        .eq("is_forecast", false)
        .order("ts", { ascending: false })
        .limit(1)
        .maybeSingle();

      const newestTs = (newest as { ts?: string } | null)?.ts ?? null;
      const ageSeconds = newestTs ? Math.floor((Date.now() - new Date(newestTs).getTime()) / 1000) : null;

      const { count } = await supabase
        .from("ohlc_bars_v2")
        .select("id", { count: "exact", head: true })
        .eq("symbol_id", symbolId)
        .eq("timeframe", tf)
        .eq("is_forecast", false);

      rows.push({
        timeframe: tf,
        newest_ts: newestTs,
        age_seconds: ageSeconds,
        bar_count: count ?? 0,
      });
    }

    const byTimeframe: Record<string, HealthRow> = {};
    for (const row of rows) {
      if (isTimeframe(row.timeframe)) {
        byTimeframe[row.timeframe] = row;
      }
    }

    return jsonResponse({
      symbol,
      symbol_id: symbolId,
      timeframes: TIMEFRAMES,
      by_timeframe: byTimeframe,
      env,
      checked_at: new Date().toISOString(),
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return jsonResponse({ error: "Internal server error", details: message }, 500);
  }
});
