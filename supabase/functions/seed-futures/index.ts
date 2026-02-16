// Temporary seed function - run once then delete
import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { corsResponse } from "../_shared/cors.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

serve(async (req: Request): Promise<Response> => {
  try {
    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const supabaseServiceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const supabase = createClient(supabaseUrl, supabaseServiceKey);

    // Insert futures roots
    const roots = [
      { symbol: 'ES', name: 'E-mini S&P 500', exchange: 'CME', sector: 'indices', tick_size: 0.25, point_value: 50.00, currency: 'USD', session_template: 'CME_US_Index' },
      { symbol: 'NQ', name: 'E-mini NASDAQ-100', exchange: 'CME', sector: 'indices', tick_size: 0.25, point_value: 20.00, currency: 'USD', session_template: 'CME_US_Index' },
      { symbol: 'RTY', name: 'E-mini Russell 2000', exchange: 'CME', sector: 'indices', tick_size: 0.10, point_value: 50.00, currency: 'USD', session_template: 'CME_US_Index' },
      { symbol: 'YM', name: 'E-mini Dow ($5)', exchange: 'CBOT', sector: 'indices', tick_size: 1.00, point_value: 5.00, currency: 'USD', session_template: 'CBOT_Index' },
      { symbol: 'EMD', name: 'E-mini S&P MidCap 400', exchange: 'CME', sector: 'indices', tick_size: 0.10, point_value: 100.00, currency: 'USD', session_template: 'CME_US_Index' },
      { symbol: 'GC', name: 'Gold', exchange: 'COMEX', sector: 'metals', tick_size: 0.10, point_value: 100.00, currency: 'USD', session_template: 'COMEX_Metals' },
      { symbol: 'SI', name: 'Silver', exchange: 'COMEX', sector: 'metals', tick_size: 0.005, point_value: 5000.00, currency: 'USD', session_template: 'COMEX_Metals' },
      { symbol: 'HG', name: 'Copper', exchange: 'COMEX', sector: 'metals', tick_size: 0.0005, point_value: 25000.00, currency: 'USD', session_template: 'COMEX_Metals' },
    ];

    const { data: insertedRoots, error: rootsError } = await supabase
      .from("futures_roots")
      .upsert(roots, { onConflict: "symbol" })
      .select();

    if (rootsError) {
      return corsResponse({ error: "Failed to insert roots", details: rootsError.message }, 500, null);
    }

    // Insert roll configs
    const { data: rootData } = await supabase
      .from("futures_roots")
      .select("id");

    if (rootData && rootData.length > 0) {
      const rollConfigs = rootData.map((r: any) => ({
        root_id: r.id,
        roll_method: "volume",
        adjustment_method: "none",
        auto_roll_enabled: true,
      }));

      const { error: configError } = await supabase
        .from("futures_roll_config")
        .upsert(rollConfigs, { onConflict: "root_id" });

      if (configError) {
        console.error("Roll config error:", configError);
      }
    }

    return corsResponse({
      success: true,
      message: `Seeded ${insertedRoots?.length || 0} futures roots`,
      roots: insertedRoots?.map((r: any) => r.symbol),
    }, 200, null);

  } catch (error) {
    console.error("Seed error:", error);
    return corsResponse({ error: "Internal error", details: String(error) }, 500, null);
  }
});
