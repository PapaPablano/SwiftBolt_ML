// Check what data is actually in the database
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

const symbolId = symbolData!.id;

// Get count of bars
const { count } = await supabase
  .from("ohlc_bars")
  .select("*", { count: "exact", head: true })
  .eq("symbol_id", symbolId)
  .eq("timeframe", "d1");

console.log(`Total d1 bars for AAPL: ${count}`);

// Get first and last bars
const { data: firstBars } = await supabase
  .from("ohlc_bars")
  .select("ts, open, provider")
  .eq("symbol_id", symbolId)
  .eq("timeframe", "d1")
  .order("ts", { ascending: true })
  .limit(1);

const { data: lastBars } = await supabase
  .from("ohlc_bars")
  .select("ts, close, provider")
  .eq("symbol_id", symbolId)
  .eq("timeframe", "d1")
  .order("ts", { ascending: false })
  .limit(1);

console.log(`First bar: ${JSON.stringify(firstBars?.[0])}`);
console.log(`Last bar: ${JSON.stringify(lastBars?.[0])}`);

// Check if there are any 2025 bars
const { count: count2025 } = await supabase
  .from("ohlc_bars")
  .select("*", { count: "exact", head: true })
  .eq("symbol_id", symbolId)
  .eq("timeframe", "d1")
  .gte("ts", "2025-01-01");

console.log(`Bars in 2025: ${count2025}`);
