// Test database insertion
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
const supabaseKey = Deno.env.get("SUPABASE_SERVICE_KEY")!;

const supabase = createClient(supabaseUrl, supabaseKey);

// Get symbol ID for AAPL
const { data: symbolData, error: symbolError } = await supabase
  .from("symbols")
  .select("id")
  .eq("ticker", "AAPL")
  .single();

if (symbolError || !symbolData) {
  console.error("Failed to get symbol:", symbolError);
  Deno.exit(1);
}

const symbolId = symbolData.id;
console.log(`Symbol ID: ${symbolId}`);

// Try to insert a test bar from Nov 14, 2024
const testBar = {
  symbol_id: symbolId,
  timeframe: "d1",
  ts: new Date(1731594600 * 1000).toISOString(), // Nov 14, 2024 14:30 UTC
  open: 225.02,
  high: 228.87,
  low: 225.00,
  close: 228.22,
  volume: 44923900,
  provider: "yfinance",
};

console.log("Attempting to insert test bar:", testBar);

const { data: upsertData, error: upsertError } = await supabase
  .from("ohlc_bars")
  .upsert([testBar], {
    onConflict: "symbol_id,timeframe,ts",
    ignoreDuplicates: false,
  })
  .select();

if (upsertError) {
  console.error("Upsert error:", upsertError);
} else {
  console.log(`Upsert successful! Returned ${upsertData?.length} rows`);
  console.log("Upserted data:", upsertData);
}

// Check total count
const { count, error: countError } = await supabase
  .from("ohlc_bars")
  .select("*", { count: "exact", head: true })
  .eq("timeframe", "d1");

if (countError) {
  console.error("Count error:", countError);
} else {
  console.log(`Total d1 bars in database: ${count}`);
}
