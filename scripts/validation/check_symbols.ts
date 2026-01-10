import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const supabase = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_KEY")!);

// Get all symbols
const { data: symbols } = await supabase.from("symbols").select("*").eq("ticker", "AAPL");
console.log("AAPL symbols:", JSON.stringify(symbols, null, 2));

// Count bars for each
for (const sym of symbols || []) {
  const { count } = await supabase
    .from("ohlc_bars")
    .select("*", { count: "exact", head: true })
    .eq("symbol_id", sym.id);

  const { data: sample } = await supabase
    .from("ohlc_bars")
    .select("ts, provider")
    .eq("symbol_id", sym.id)
    .order("ts", { ascending: false })
    .limit(1);

  console.log(`Symbol ${sym.id}: ${count} bars, latest: ${JSON.stringify(sample?.[0])}`);
}
