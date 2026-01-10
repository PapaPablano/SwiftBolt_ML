// Clean up invalid future data (2025) from database
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
const supabaseKey = Deno.env.get("SUPABASE_SERVICE_KEY")!;

const supabase = createClient(supabaseUrl, supabaseKey);

// Delete all bars with timestamps in 2025 or later
const cutoffDate = "2025-01-01T00:00:00.000Z";

console.log(`Deleting all bars with ts >= ${cutoffDate}...`);

const { data, error } = await supabase
  .from("ohlc_bars_v2")
  .delete()
  .gte("ts", cutoffDate)
  .eq("is_forecast", false)
  .select();

if (error) {
  console.error("Delete error:", error);
} else {
  console.log(`Deleted ${data?.length || 0} invalid future bars`);
  if (data && data.length > 0) {
    console.log(`Sample deleted bar: ${JSON.stringify(data[0])}`);
  }
}

// Check remaining count
const { count, error: countError } = await supabase
  .from("ohlc_bars_v2")
  .select("*", { count: "exact", head: true })
  .eq("is_forecast", false);

if (countError) {
  console.error("Count error:", countError);
} else {
  console.log(`Total bars remaining: ${count}`);
}
