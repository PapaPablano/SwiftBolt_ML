#!/usr/bin/env -S deno run --allow-net --allow-env

// Seed script: Inserts sample stock symbols into the database
// Usage: deno run --allow-net --allow-env seed-symbols.ts
//
// Required environment variables:
//   SUPABASE_URL - Your Supabase project URL
//   SUPABASE_SERVICE_ROLE_KEY - Service role key for bypassing RLS

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

interface SeedSymbol {
  ticker: string;
  asset_type: "stock" | "future" | "option" | "crypto";
  description: string;
  primary_source: "finnhub" | "massive";
}

const SEED_SYMBOLS: SeedSymbol[] = [
  // Large-cap tech stocks
  { ticker: "AAPL", asset_type: "stock", description: "Apple Inc.", primary_source: "finnhub" },
  { ticker: "MSFT", asset_type: "stock", description: "Microsoft Corporation", primary_source: "finnhub" },
  { ticker: "GOOGL", asset_type: "stock", description: "Alphabet Inc. Class A", primary_source: "finnhub" },
  { ticker: "AMZN", asset_type: "stock", description: "Amazon.com Inc.", primary_source: "finnhub" },
  { ticker: "NVDA", asset_type: "stock", description: "NVIDIA Corporation", primary_source: "finnhub" },
  { ticker: "META", asset_type: "stock", description: "Meta Platforms Inc.", primary_source: "finnhub" },
  { ticker: "TSLA", asset_type: "stock", description: "Tesla Inc.", primary_source: "finnhub" },

  // Financials
  { ticker: "JPM", asset_type: "stock", description: "JPMorgan Chase & Co.", primary_source: "finnhub" },
  { ticker: "V", asset_type: "stock", description: "Visa Inc.", primary_source: "finnhub" },
  { ticker: "MA", asset_type: "stock", description: "Mastercard Incorporated", primary_source: "finnhub" },

  // Healthcare
  { ticker: "UNH", asset_type: "stock", description: "UnitedHealth Group Incorporated", primary_source: "finnhub" },
  { ticker: "JNJ", asset_type: "stock", description: "Johnson & Johnson", primary_source: "finnhub" },

  // ETFs
  { ticker: "SPY", asset_type: "stock", description: "SPDR S&P 500 ETF Trust", primary_source: "finnhub" },
  { ticker: "QQQ", asset_type: "stock", description: "Invesco QQQ Trust", primary_source: "finnhub" },
  { ticker: "IWM", asset_type: "stock", description: "iShares Russell 2000 ETF", primary_source: "finnhub" },

  // Futures
  { ticker: "ES", asset_type: "future", description: "E-mini S&P 500 Futures", primary_source: "massive" },
  { ticker: "NQ", asset_type: "future", description: "E-mini NASDAQ-100 Futures", primary_source: "massive" },
  { ticker: "CL", asset_type: "future", description: "Crude Oil Futures", primary_source: "massive" },
  { ticker: "GC", asset_type: "future", description: "Gold Futures", primary_source: "massive" },

  // Crypto
  { ticker: "BTC", asset_type: "crypto", description: "Bitcoin", primary_source: "finnhub" },
];

async function main() {
  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const supabaseServiceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");

  if (!supabaseUrl || !supabaseServiceKey) {
    console.error("Error: Missing required environment variables");
    console.error("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY");
    Deno.exit(1);
  }

  console.log("Connecting to Supabase...");
  const supabase = createClient(supabaseUrl, supabaseServiceKey, {
    auth: {
      autoRefreshToken: false,
      persistSession: false,
    },
  });

  console.log(`Seeding ${SEED_SYMBOLS.length} symbols...`);

  // Use upsert to handle duplicates gracefully
  const { data, error } = await supabase
    .from("symbols")
    .upsert(SEED_SYMBOLS, {
      onConflict: "ticker",
      ignoreDuplicates: false,
    })
    .select("id, ticker");

  if (error) {
    console.error("Error seeding symbols:", error);
    Deno.exit(1);
  }

  console.log("Successfully seeded symbols:");
  for (const symbol of data || []) {
    console.log(`  - ${symbol.ticker} (${symbol.id})`);
  }

  console.log("\nDone!");
}

main();
