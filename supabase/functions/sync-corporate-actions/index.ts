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
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
    );
    
    // Initialize Alpaca client
    const rateLimiter = new TokenBucketRateLimiter({
      alpaca: { maxPerSecond: 200, maxPerMinute: 10000 },
      finnhub: { maxPerSecond: 10, maxPerMinute: 600 },
      massive: { maxPerSecond: 10, maxPerMinute: 600 },
      yahoo: { maxPerSecond: 10, maxPerMinute: 600 },
      tradier: { maxPerSecond: 10, maxPerMinute: 600 }
    });
    const cache = new MemoryCache(1000);
    const alpaca = new AlpacaClient(
      Deno.env.get("ALPACA_API_KEY")!,
      Deno.env.get("ALPACA_API_SECRET")!,
      rateLimiter,
      cache
    );
    
    const marketIntel = new MarketIntelligence(alpaca);
    
    // Get watchlist symbols
    const { data: symbols, error: symbolsError } = await supabase
      .from('symbols')
      .select('ticker, id');
    
    if (symbolsError) throw symbolsError;
    
    if (!symbols || symbols.length === 0) {
      console.log('[sync-corporate-actions] No active symbols found');
      return new Response(
        JSON.stringify({ success: true, actions_synced: 0, message: 'No active symbols' }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    }
    
    const tickers = symbols.map(s => s.ticker);
    console.log(`[sync-corporate-actions] Checking ${tickers.length} symbols`);
    
    // Fetch corporate actions from Alpaca
    const actions = await marketIntel.getCorporateActions(tickers);
    console.log(`[sync-corporate-actions] Found ${actions.length} corporate actions`);
    
    // Upsert to database
    let syncedCount = 0;
    for (const action of actions) {
      const symbolData = symbols.find(s => s.ticker === action.symbol);
      if (!symbolData) continue;
      
      const { error: upsertError } = await supabase.from('corporate_actions').upsert({
        symbol_id: symbolData.id,
        symbol: action.symbol,
        action_type: action.type,
        ex_date: action.date,
        old_rate: action.metadata.old_rate,
        new_rate: action.metadata.new_rate,
        cash_amount: action.amount,
        metadata: action.metadata
      }, { onConflict: 'symbol,action_type,ex_date' });
      
      if (!upsertError) {
        syncedCount++;
      } else {
        console.error(`[sync-corporate-actions] Error upserting ${action.symbol}:`, upsertError);
      }
    }
    
    console.log(`[sync-corporate-actions] Synced ${syncedCount} actions`);
    
    // Trigger adjustment job for new splits
    const splits = actions.filter(a => 
      a.type === 'stock_split' || a.type === 'reverse_split'
    );
    
    if (splits.length > 0) {
      console.log(`[sync-corporate-actions] Found ${splits.length} splits, triggering adjustment job`);
      
      // Invoke the adjustment function
      const { error: invokeError } = await supabase.functions.invoke('adjust-bars-for-splits', {
        body: { splits }
      });
      
      if (invokeError) {
        console.error('[sync-corporate-actions] Error invoking adjustment job:', invokeError);
      }
    }
    
    return new Response(
      JSON.stringify({ 
        success: true, 
        actions_synced: syncedCount,
        splits_found: splits.length 
      }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
    
  } catch (error) {
    console.error("[sync-corporate-actions] Error:", error);
    return new Response(
      JSON.stringify({ error: error instanceof Error ? error.message : 'Unknown error' }),
      { status: 500, headers: { "Content-Type": "application/json" } }
    );
  }
});
