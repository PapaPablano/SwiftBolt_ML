import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

const SEED_SYMBOLS = [
  // Core trading symbols
  { ticker: "AAPL", asset_type: "stock", description: "Apple Inc. - Consumer electronics, software, and services", primary_source: "finnhub" },
  { ticker: "MSFT", asset_type: "stock", description: "Microsoft Corporation - Software, cloud computing, and hardware", primary_source: "finnhub" },
  { ticker: "GOOGL", asset_type: "stock", description: "Alphabet Inc. Class A - Search, advertising, and cloud services", primary_source: "finnhub" },
  { ticker: "AMZN", asset_type: "stock", description: "Amazon.com Inc. - E-commerce, cloud computing, and AI", primary_source: "finnhub" },
  { ticker: "TSLA", asset_type: "stock", description: "Tesla Inc. - Electric vehicles and clean energy", primary_source: "finnhub" },
  { ticker: "NVDA", asset_type: "stock", description: "NVIDIA Corporation - Graphics processing and AI computing", primary_source: "finnhub" },
  { ticker: "META", asset_type: "stock", description: "Meta Platforms Inc. - Social media and virtual reality", primary_source: "finnhub" },
  { ticker: "AMD", asset_type: "stock", description: "Advanced Micro Devices, Inc. - Semiconductors and processors", primary_source: "finnhub" },
  { ticker: "CRWD", asset_type: "stock", description: "CrowdStrike Holdings, Inc. - Cybersecurity technology", primary_source: "finnhub" },
  // ETFs
  { ticker: "SPY", asset_type: "stock", description: "SPDR S&P 500 ETF Trust - Tracks the S&P 500 index", primary_source: "finnhub" },
  { ticker: "QQQ", asset_type: "stock", description: "Invesco QQQ Trust - Tracks the NASDAQ-100 index", primary_source: "finnhub" },
];

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const supabaseClient = createClient(
      Deno.env.get("SUPABASE_URL") ?? "",
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "",
    );

    const results = [];

    for (const symbol of SEED_SYMBOLS) {
      const { data, error } = await supabaseClient
        .from("symbols")
        .upsert(symbol, { onConflict: "ticker" })
        .select();

      if (error) {
        console.error(`Error seeding ${symbol.ticker}:`, error);
        results.push({ ticker: symbol.ticker, status: "error", error: error.message });
      } else {
        results.push({ ticker: symbol.ticker, status: "success" });
      }
    }

    return new Response(
      JSON.stringify({
        success: true,
        message: "Symbols seeded",
        results,
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
