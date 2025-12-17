import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

interface StrikeAnalysisRequest {
  symbol: string;
  strike: number;
  side: "call" | "put";
  lookbackDays?: number;
}

interface StrikeExpiryData {
  expiry: string;
  currentMark: number | null;
  avgMark: number | null;
  pctDiffFromAvg: number | null;
  sampleCount: number;
  minMark: number | null;
  maxMark: number | null;
  currentIv: number | null;
  avgIv: number | null;
  isDiscount: boolean;
  discountPct: number | null;
}

serve(async (req) => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const supabaseClient = createClient(
      Deno.env.get("SUPABASE_URL") ?? "",
      Deno.env.get("SUPABASE_ANON_KEY") ?? "",
      {
        global: {
          headers: { Authorization: req.headers.get("Authorization")! },
        },
      }
    );

    const url = new URL(req.url);
    const symbol = url.searchParams.get("symbol");
    const strike = url.searchParams.get("strike");
    const side = url.searchParams.get("side");
    const lookbackDays = parseInt(url.searchParams.get("lookbackDays") || "30");

    if (!symbol || !strike || !side) {
      return new Response(
        JSON.stringify({ error: "Missing required parameters: symbol, strike, side" }),
        {
          status: 400,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        }
      );
    }

    if (side !== "call" && side !== "put") {
      return new Response(
        JSON.stringify({ error: "Side must be 'call' or 'put'" }),
        {
          status: 400,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        }
      );
    }

    // Get symbol ID
    const { data: symbolData, error: symbolError } = await supabaseClient
      .from("symbols")
      .select("id")
      .eq("ticker", symbol.toUpperCase())
      .single();

    if (symbolError || !symbolData) {
      return new Response(
        JSON.stringify({ error: "Symbol not found" }),
        {
          status: 404,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        }
      );
    }

    // Get strike price comparison across expirations
    const { data: comparison, error: comparisonError } = await supabaseClient.rpc(
      "get_strike_price_comparison",
      {
        p_symbol_id: symbolData.id,
        p_strike: parseFloat(strike),
        p_side: side,
        p_lookback_days: lookbackDays,
      }
    );

    if (comparisonError) throw comparisonError;

    // Process data to add discount indicators
    const processedData: StrikeExpiryData[] = (comparison || []).map((item: any) => {
      const isDiscount = item.current_mark !== null &&
        item.avg_mark !== null &&
        item.current_mark < item.avg_mark;

      const discountPct = item.pct_diff_from_avg !== null
        ? -item.pct_diff_from_avg // Negative means discount
        : null;

      return {
        expiry: item.expiry,
        currentMark: item.current_mark,
        avgMark: item.avg_mark,
        pctDiffFromAvg: item.pct_diff_from_avg,
        sampleCount: item.sample_count || 0,
        minMark: item.min_mark,
        maxMark: item.max_mark,
        currentIv: item.current_iv,
        avgIv: item.avg_iv,
        isDiscount,
        discountPct,
      };
    });

    // Get historical price chart for this strike
    const { data: priceHistory, error: historyError } = await supabaseClient
      .from("options_price_history")
      .select("snapshot_at, mark, implied_vol")
      .eq("underlying_symbol_id", symbolData.id)
      .eq("strike", parseFloat(strike))
      .eq("side", side)
      .gte("snapshot_at", `now() - interval '${lookbackDays} days'`)
      .order("snapshot_at", { ascending: true });

    if (historyError) throw historyError;

    // Calculate overall statistics
    const allMarks = (priceHistory || [])
      .map((h: any) => h.mark)
      .filter((m: number | null) => m !== null);

    const overallStats = {
      avgMark: allMarks.length > 0
        ? allMarks.reduce((a: number, b: number) => a + b, 0) / allMarks.length
        : null,
      minMark: allMarks.length > 0 ? Math.min(...allMarks) : null,
      maxMark: allMarks.length > 0 ? Math.max(...allMarks) : null,
      sampleCount: allMarks.length,
    };

    return new Response(
      JSON.stringify({
        symbol: symbol.toUpperCase(),
        strike: parseFloat(strike),
        side,
        lookbackDays,
        expirations: processedData,
        priceHistory: priceHistory || [],
        overallStats,
        metadata: {
          queriedAt: new Date().toISOString(),
          expirationsFound: processedData.length,
          hasHistoricalData: (priceHistory?.length || 0) > 0,
        },
      }),
      {
        status: 200,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  } catch (error) {
    console.error("Error:", error);
    return new Response(
      JSON.stringify({ error: error.message || "Internal server error" }),
      {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  }
});
