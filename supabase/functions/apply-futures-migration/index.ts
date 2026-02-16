// POST /apply-futures-migration
// Applies the futures columns migration to symbols table

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { corsResponse } from "../_shared/cors.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

serve(async (req: Request): Promise<Response> => {
  const origin = req.headers.get("origin");

  if (req.method !== "POST") {
    return corsResponse({ error: "Method not allowed" }, 405, origin);
  }

  try {
    const supabaseUrl = Deno.env.get("SUPABASE_URL");
    const supabaseServiceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");

    if (!supabaseUrl || !supabaseServiceKey) {
      return corsResponse({ error: "Missing credentials" }, 500, origin);
    }

    const supabase = createClient(supabaseUrl, supabaseServiceKey);

    // Step 1: Add columns
    const { error: alterError } = await supabase.rpc('exec_sql', { 
      sql: `
        ALTER TABLE symbols 
        ADD COLUMN IF NOT EXISTS futures_root_id UUID REFERENCES futures_roots(id),
        ADD COLUMN IF NOT EXISTS is_continuous BOOLEAN DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS expiry_month INTEGER,
        ADD COLUMN IF NOT EXISTS expiry_year INTEGER,
        ADD COLUMN IF NOT EXISTS last_trade_date DATE;
        
        CREATE INDEX IF NOT EXISTS idx_symbols_futures_root ON symbols(futures_root_id);
        CREATE INDEX IF NOT EXISTS idx_symbols_is_continuous ON symbols(is_continuous) WHERE is_continuous = TRUE;
      `
    });

    if (alterError) {
      console.log("Alter error (may be ok if columns exist):", alterError);
    }

    // Step 2: Insert futures contracts into symbols
    const { error: insertError } = await supabase.rpc('insert_futures_contracts_into_symbols', {});

    if (insertError) {
      console.log("Insert error:", insertError);
      
      // Try manual insert
      const { data: contracts, error: contractsError } = await supabase
        .from("futures_contracts")
        .select("symbol, contract_code, expiry_month, expiry_year, last_trade_date, futures_roots(symbol)")
        .limit(20);

      if (!contractsError && contracts) {
        for (const c of contracts) {
          // Get root ID
          const rootSymbol = c.futures_roots?.symbol;
          if (!rootSymbol) continue;

          const { data: rootData } = await supabase
            .from("futures_roots")
            .select("id")
            .eq("symbol", rootSymbol)
            .single();

          if (!rootData) continue;

          // Insert or update symbol
          await supabase
            .from("symbols")
            .upsert({
              ticker: c.symbol,
              asset_type: "future",
              description: `${rootSymbol} ${c.contract_code} (Futures)`,
              futures_root_id: rootData.id,
              is_continuous: false,
              expiry_month: c.expiry_month,
              expiry_year: c.expiry_year,
              last_trade_date: c.last_trade_date,
            }, {
              onConflict: "ticker",
              ignoreDuplicates: false,
            });
        }
      }
    }

    return corsResponse({
      success: true,
      message: "Futures migration applied",
    }, 200, origin);

  } catch (error) {
    console.error("[apply-futures-migration] Error:", error);
    return corsResponse(
      { error: error instanceof Error ? error.message : "Unknown error" },
      500,
      origin
    );
  }
});
