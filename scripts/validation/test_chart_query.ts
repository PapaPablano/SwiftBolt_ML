// Test the exact query used by the chart function
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
const supabaseKey = Deno.env.get("SUPABASE_SERVICE_KEY")!;

const supabase = createClient(supabaseUrl, supabaseKey);

// Get symbol ID for AAPL
const { data: symbolData } = await supabase
  .from("symbols")
  .select("id")
  .eq("ticker", "AAPL")
  .single();

if (!symbolData) {
  console.error("Symbol not found");
  Deno.exit(1);
}

const symbolId = symbolData.id;
const timeframe = "d1";
const cacheLimit = 1000;

console.log(`Querying for symbol_id=${symbolId}, timeframe=${timeframe}`);

// Execute the same query as the chart function
const { data: cachedBars, error: cacheError } = await supabase
  .from("ohlc_bars")
  .select("ts, open, high, low, close, volume")
  .eq("symbol_id", symbolId)
  .eq("timeframe", timeframe)
  .order("ts", { ascending: false }) // Get most recent first
  .limit(cacheLimit);

if (cacheError) {
  console.error("Query error:", cacheError);
} else {
  console.log(`Returned ${cachedBars?.length || 0} bars`);
  if (cachedBars && cachedBars.length > 0) {
    console.log(`First (most recent) bar: ${JSON.stringify(cachedBars[0])}`);
    console.log(`Last (oldest) bar: ${JSON.stringify(cachedBars[cachedBars.length - 1])}`);
  }
}
