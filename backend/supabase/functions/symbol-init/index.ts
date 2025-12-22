// symbol-init: Initialize a symbol with OHLC data and ML forecasts
// POST /symbol-init { symbol: "AAPL" }
//
// This function is called when a symbol is added to a watchlist.
// It ensures the symbol has sufficient OHLC data and generates ML forecasts.

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
};

interface InitRequest {
  symbol: string;
  forceRefresh?: boolean;
}

interface InitResult {
  symbol: string;
  ohlcBars: number;
  forecastsGenerated: string[];
  errors: string[];
}

// Minimum bars needed for ML forecasting
const MIN_BARS_FOR_FORECAST = 50;

serve(async (req: Request): Promise<Response> => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), {
      status: 405,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  try {
    const supabase = createClient(
      Deno.env.get("SUPABASE_URL") ?? "",
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? ""
    );

    const body: InitRequest = await req.json();
    const symbol = body.symbol?.toUpperCase();

    if (!symbol) {
      return new Response(JSON.stringify({ error: "Symbol required" }), {
        status: 400,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    console.log(`[symbol-init] Initializing ${symbol}...`);

    const result: InitResult = {
      symbol,
      ohlcBars: 0,
      forecastsGenerated: [],
      errors: [],
    };

    // Step 1: Get or create symbol record
    let { data: symbolRecord, error: symbolError } = await supabase
      .from("symbols")
      .select("id, ticker, asset_type")
      .eq("ticker", symbol)
      .single();

    if (symbolError || !symbolRecord) {
      // Create symbol if doesn't exist
      const { data: newSymbol, error: createError } = await supabase
        .from("symbols")
        .insert({ ticker: symbol, asset_type: "stock" })
        .select("id, ticker, asset_type")
        .single();

      if (createError) {
        result.errors.push(`Failed to create symbol: ${createError.message}`);
        return new Response(JSON.stringify(result), {
          status: 500,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        });
      }
      symbolRecord = newSymbol;
    }

    // Step 2: Check existing OHLC bar count
    const { count: existingBars } = await supabase
      .from("ohlc_bars")
      .select("*", { count: "exact", head: true })
      .eq("symbol_id", symbolRecord.id)
      .eq("timeframe", "d1");

    result.ohlcBars = existingBars || 0;
    console.log(`[symbol-init] ${symbol} has ${result.ohlcBars} existing d1 bars`);

    // Step 3: If insufficient bars, fetch and store OHLC data
    if (result.ohlcBars < MIN_BARS_FOR_FORECAST || body.forceRefresh) {
      console.log(`[symbol-init] Fetching OHLC data for ${symbol}...`);

      try {
        // Call the chart endpoint to fetch and persist OHLC data
        const chartUrl = `${Deno.env.get("SUPABASE_URL")}/functions/v1/chart?symbol=${symbol}&timeframe=d1`;
        const chartResponse = await fetch(chartUrl, {
          headers: {
            Authorization: `Bearer ${Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")}`,
          },
        });

        if (chartResponse.ok) {
          const chartData = await chartResponse.json();
          result.ohlcBars = chartData.bars?.length || result.ohlcBars;
          console.log(`[symbol-init] Chart API returned ${result.ohlcBars} bars for ${symbol}`);
        } else {
          const errorText = await chartResponse.text();
          result.errors.push(`Chart fetch failed: ${errorText}`);
        }
      } catch (chartError) {
        result.errors.push(`Chart fetch error: ${chartError.message}`);
      }
    }

    // Step 4: Check if we have enough data for ML forecasting
    if (result.ohlcBars < MIN_BARS_FOR_FORECAST) {
      result.errors.push(
        `Insufficient data for ML forecast: ${result.ohlcBars} bars (need ${MIN_BARS_FOR_FORECAST})`
      );
      return new Response(JSON.stringify(result), {
        status: 200,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    // Step 5: Check existing ML forecasts
    const { data: existingForecasts } = await supabase
      .from("ml_forecasts")
      .select("horizon, created_at")
      .eq("symbol_id", symbolRecord.id);

    const existingHorizons = new Set(
      existingForecasts?.map((f) => f.horizon) || []
    );
    const requiredHorizons = ["1D", "1W"];
    const missingHorizons = requiredHorizons.filter(
      (h) => !existingHorizons.has(h)
    );

    // Step 6: Generate missing ML forecasts
    if (missingHorizons.length > 0 || body.forceRefresh) {
      console.log(
        `[symbol-init] Generating ML forecasts for ${symbol}: ${missingHorizons.join(", ") || "all (forced)"}`
      );

      // Queue forecast job by inserting into job_queue table
      const { error: queueError } = await supabase.from("job_queue").insert({
        job_type: "forecast",
        symbol: symbol,
        status: "pending",
        priority: 1,
        payload: {
          symbol_id: symbolRecord.id,
          horizons: body.forceRefresh ? requiredHorizons : missingHorizons,
        },
      });

      if (queueError) {
        // Job queue might not exist, try direct forecast generation
        console.log(`[symbol-init] Job queue insert failed, trying direct generation...`);
        
        // For now, we'll just mark that forecasts need to be generated
        // The ML forecast job should be run separately (via cron or manual trigger)
        result.errors.push(
          `Forecast job queued but may need manual trigger. Run: python -m src.forecast_job --symbol ${symbol}`
        );
      } else {
        result.forecastsGenerated = body.forceRefresh
          ? requiredHorizons
          : missingHorizons;
      }
    } else {
      console.log(`[symbol-init] ${symbol} already has all required forecasts`);
      result.forecastsGenerated = [];
    }

    console.log(`[symbol-init] Completed initialization for ${symbol}`);

    return new Response(JSON.stringify(result), {
      status: 200,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (error) {
    console.error("[symbol-init] Error:", error);
    return new Response(
      JSON.stringify({ error: error.message || "Internal server error" }),
      {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  }
});
