import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { MarketIntelligence } from "../_shared/services/market-intelligence.ts";
import { AlpacaClient } from "../_shared/providers/alpaca-client.ts";
import { TokenBucketRateLimiter } from "../_shared/rate-limiter/token-bucket.ts";
import { MemoryCache } from "../_shared/cache/memory-cache.ts";

serve(async (req) => {
  try {
    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    );

    // Initialize Alpaca client
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

    const marketIntel = new MarketIntelligence(alpaca);

    // Sync next 30 days of calendar
    const start = new Date();
    const end = new Date();
    end.setDate(end.getDate() + 30);

    const calendar = await marketIntel.getMarketCalendar(
      start.toISOString().split("T")[0],
      end.toISOString().split("T")[0],
    );

    // Transform calendar data for database
    const calendarRecords = calendar.map((day) => ({
      date: day.date,
      is_open: true, // If it's in the calendar, market is open
      session_open: day.sessionOpen,
      session_close: day.sessionClose,
      market_open: day.open,
      market_close: day.close,
      updated_at: new Date().toISOString(),
    }));

    // Upsert to database
    const { data, error } = await supabase
      .from("market_calendar")
      .upsert(calendarRecords, { onConflict: "date" });

    if (error) throw error;

    console.log(
      `[sync-market-calendar] Synced ${calendar.length} trading days`,
    );

    return new Response(
      JSON.stringify({
        success: true,
        days_synced: calendar.length,
        range: {
          start: start.toISOString().split("T")[0],
          end: end.toISOString().split("T")[0],
        },
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
  } catch (error) {
    console.error("[sync-market-calendar] Error:", error);
    return new Response(
      JSON.stringify({ error: error.message }),
      { status: 500, headers: { "Content-Type": "application/json" } },
    );
  }
});
