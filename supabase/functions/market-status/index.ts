import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { MarketIntelligence } from "../_shared/services/market-intelligence.ts";
import { AlpacaClient } from "../_shared/providers/alpaca-client.ts";
import { TokenBucketRateLimiter } from "../_shared/rate-limiter/token-bucket.ts";
import { MemoryCache } from "../_shared/cache/memory-cache.ts";

serve(async (req) => {
  try {
    const url = new URL(req.url);
    const symbol = url.searchParams.get("symbol");

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

    // Get market status
    const marketStatus = await marketIntel.getMarketStatus();

    // Get pending corporate actions if symbol provided
    let pendingActions = [];
    if (symbol) {
      const { data: actions } = await supabase
        .from("corporate_actions")
        .select("*")
        .eq("symbol", symbol)
        .eq("bars_adjusted", false)
        .order("ex_date", { ascending: true });

      pendingActions = actions || [];
    }

    return new Response(
      JSON.stringify({
        market: {
          isOpen: marketStatus.isOpen,
          nextOpen: marketStatus.nextOpen,
          nextClose: marketStatus.nextClose,
          timestamp: marketStatus.timestamp,
        },
        pendingActions: pendingActions.map((action) => ({
          symbol: action.symbol,
          type: action.action_type,
          exDate: action.ex_date,
          ratio: action.ratio,
          cashAmount: action.cash_amount,
        })),
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
  } catch (error) {
    console.error("[market-status] Error:", error);
    return new Response(
      JSON.stringify({
        error: error instanceof Error ? error.message : "Unknown error",
      }),
      { status: 500, headers: { "Content-Type": "application/json" } },
    );
  }
});
