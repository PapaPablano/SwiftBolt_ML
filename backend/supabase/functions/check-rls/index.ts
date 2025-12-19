// Diagnostic function to check RLS policies
import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { handleCorsOptions, jsonResponse } from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";

serve(async (req: Request): Promise<Response> => {
  if (req.method === "OPTIONS") {
    return handleCorsOptions();
  }

  try {
    const supabase = getSupabaseClient();

    // Try to query symbols table
    const { data: symbolsData, error: symbolsError } = await supabase
      .from("symbols")
      .select("id, ticker")
      .limit(5);

    // Try to query options_ranks table
    const { data: ranksData, error: ranksError } = await supabase
      .from("options_ranks")
      .select("id, contract_symbol")
      .limit(5);

    return jsonResponse({
      symbols: {
        data: symbolsData,
        error: symbolsError?.message,
        count: symbolsData?.length || 0,
      },
      options_ranks: {
        data: ranksData,
        error: ranksError?.message,
        count: ranksData?.length || 0,
      },
    });
  } catch (err) {
    return jsonResponse({
      error: err instanceof Error ? err.message : String(err),
    }, 500);
  }
});
