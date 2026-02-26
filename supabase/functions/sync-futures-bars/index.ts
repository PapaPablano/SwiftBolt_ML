// POST /sync-futures-bars
// Backfills OHLC bars for futures contracts using Polygon API directly

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { corsResponse } from "../_shared/cors.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

interface SyncBarsRequest {
  root: string;
  timeframe?: string;
  years_back?: number;
  days_back?: number;
  contracts?: string[];
}

interface SyncResult {
  root: string;
  contract: string;
  bars_fetched: number;
  bars_inserted: number;
  errors: string[];
}

serve(async (req: Request): Promise<Response> => {
  const origin = req.headers.get("origin");

  if (req.method === "OPTIONS") {
    return new Response(null, {
      status: 204,
      headers: { "Access-Control-Allow-Origin": origin || "*" },
    });
  }

  if (req.method !== "POST") {
    return corsResponse({ error: "Method not allowed" }, 405, origin);
  }

  try {
    const body: SyncBarsRequest = await req.json().catch(() => ({}));
    const {
      root,
      timeframe = "d1",
      years_back = 2,
      days_back = 90,
      contracts,
    } = body;

    if (!root) {
      return corsResponse(
        { error: "Missing required parameter: root" },
        400,
        origin,
      );
    }

    const supabaseUrl = Deno.env.get("SUPABASE_URL");
    const supabaseServiceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
    const polygonApiKey = Deno.env.get("MASSIVE_API_KEY");

    if (!supabaseUrl || !supabaseServiceKey) {
      return corsResponse(
        { error: "Missing Supabase credentials" },
        500,
        origin,
      );
    }

    if (!polygonApiKey) {
      return corsResponse({ error: "Missing MASSIVE_API_KEY" }, 500, origin);
    }

    const supabase = createClient(supabaseUrl, supabaseServiceKey);

    // Determine which contracts to sync
    let contractsToSync: string[] = [];

    if (contracts && contracts.length > 0) {
      contractsToSync = contracts.map((c) => c.toUpperCase());
    } else {
      const { data: rootData } = await supabase
        .from("futures_roots")
        .select("id")
        .eq("symbol", root.toUpperCase())
        .single();

      if (!rootData) {
        return corsResponse({ error: `Root not found: ${root}` }, 404, origin);
      }

      const { data: contractData } = await supabase
        .from("futures_contracts")
        .select("symbol, is_spot, expiry_year, expiry_month")
        .eq("root_id", rootData.id)
        .eq("is_active", true)
        .order("expiry_year", { ascending: false })
        .order("expiry_month", { ascending: false })
        .limit(10);

      if (!contractData || contractData.length === 0) {
        return corsResponse(
          { error: `No active contracts for root: ${root}` },
          404,
          origin,
        );
      }

      contractData.sort((a, b) => {
        if (a.is_spot && !b.is_spot) return -1;
        if (!a.is_spot && b.is_spot) return 1;
        return (b.expiry_year * 12 + b.expiry_month) -
          (a.expiry_year * 12 + a.expiry_month);
      });

      contractsToSync = contractData.slice(0, 4).map((c) => c.symbol);
    }

    // Calculate date range
    const now = new Date();
    let startDate: Date;
    if (["m15", "m30", "h1", "h4"].includes(timeframe)) {
      startDate = new Date(now.getTime() - days_back * 24 * 60 * 60 * 1000);
    } else {
      startDate = new Date(
        now.getTime() - years_back * 365 * 24 * 60 * 60 * 1000,
      );
    }

    const startStr = startDate.toISOString().split("T")[0];
    const endStr = now.toISOString().split("T")[0];

    // Get symbol_id for the root
    const { data: symbolData } = await supabase
      .from("symbols")
      .select("id")
      .eq("ticker", root.toUpperCase())
      .single();

    if (!symbolData) {
      return corsResponse(
        { error: `Root symbol not found: ${root}` },
        404,
        origin,
      );
    }

    const symbolId = symbolData.id;
    const results: SyncResult[] = [];

    for (const contractSymbol of contractsToSync) {
      const result: SyncResult = {
        root,
        contract: contractSymbol,
        bars_fetched: 0,
        bars_inserted: 0,
        errors: [],
      };

      try {
        // Try different ticker formats for futures
        const tickerFormats = [
          contractSymbol,
          `${contractSymbol}:XCME`,
        ];

        let bars: any[] = [];

        for (const ticker of tickerFormats) {
          try {
            const url =
              `https://api.polygon.io/v2/aggs/ticker/${ticker}/range/1/day/${startStr}/${endStr}?adjusted=false&sort=asc&limit=50000&apiKey=${polygonApiKey}`;
            const response = await fetch(url);
            const data = await response.json();

            if (data.results && data.results.length > 0) {
              bars = data.results;
              break;
            }
          } catch (e) {
            // Try next format
          }
        }

        result.bars_fetched = bars.length;

        if (bars.length === 0) {
          result.errors.push(`No data available`);
          results.push(result);
          continue;
        }

        // Transform and upsert bars
        const rows = bars.map((bar) => ({
          symbol_id: symbolId,
          timeframe,
          ts: new Date(bar.t).toISOString(),
          open: bar.o,
          high: bar.h,
          low: bar.l,
          close: bar.c,
          volume: bar.v,
          provider: "massive" as const,
          data_status: "raw" as const,
          is_forecast: false,
          fetched_at: new Date().toISOString(),
        }));

        const { error: upsertError } = await supabase
          .from("ohlc_bars_v2")
          .upsert(rows, {
            onConflict: "symbol_id,timeframe,ts,provider,is_forecast",
            ignoreDuplicates: false,
          });

        if (upsertError) {
          result.errors.push(`Upsert error: ${upsertError.message}`);
        } else {
          result.bars_inserted = rows.length;
        }
      } catch (error) {
        result.errors.push(
          error instanceof Error ? error.message : String(error),
        );
      }

      results.push(result);
    }

    return corsResponse(
      {
        success: true,
        timestamp: new Date().toISOString(),
        root,
        timeframe,
        contracts_processed: contractsToSync.length,
        total_bars_fetched: results.reduce((sum, r) => sum + r.bars_fetched, 0),
        total_bars_inserted: results.reduce(
          (sum, r) => sum + r.bars_inserted,
          0,
        ),
        results,
      },
      200,
      origin,
    );
  } catch (error) {
    return corsResponse(
      { error: error instanceof Error ? error.message : "Unknown error" },
      500,
      origin,
    );
  }
});
