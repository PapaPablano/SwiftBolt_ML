// GET /futures/continuous?root=GC&depth=1
// Returns continuous contract mapping (e.g., GC1!, GC2!) for a root

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { getCorsHeaders, handlePreflight, corsResponse } from "../_shared/cors.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

interface ContinuousContract {
  alias: string;
  depth: number;
  contract: {
    id: string;
    symbol: string;
    expiry_month: number;
    expiry_year: number;
    last_trade_date: string | null;
    days_to_expiry: number;
  };
  valid_from: string;
  valid_until: string | null;
}

interface FuturesContinuousResponse {
  success: boolean;
  root: string;
  depth: number;
  as_of: string;
  contracts: ContinuousContract[];
}

serve(async (req: Request): Promise<Response> => {
  const origin = req.headers.get("origin");

  if (req.method === "OPTIONS") {
    return handlePreflight(origin);
  }

  if (req.method !== "GET") {
    return corsResponse({ error: "Method not allowed" }, 405, origin);
  }

  try {
    const url = new URL(req.url);
    const root = url.searchParams.get("root");
    const depthParam = url.searchParams.get("depth");
    const asOf = url.searchParams.get("asOf") || new Date().toISOString().split("T")[0];

    if (!root) {
      return corsResponse(
        { error: "Missing required parameter: root" },
        400,
        origin
      );
    }

    const depth = depthParam ? parseInt(depthParam, 10) : undefined;
    if (depthParam && (isNaN(depth!) || depth! < 1 || depth! > 12)) {
      return corsResponse(
        { error: "Invalid depth parameter. Must be between 1 and 12" },
        400,
        origin
      );
    }

    const supabaseUrl = Deno.env.get("SUPABASE_URL");
    const supabaseServiceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");

    if (!supabaseUrl || !supabaseServiceKey) {
      console.error("[futures-continuous] Missing Supabase credentials");
      return corsResponse(
        { error: "Server configuration error" },
        500,
        origin
      );
    }

    const supabase = createClient(supabaseUrl, supabaseServiceKey);

    // Get root info
    const { data: rootData, error: rootError } = await supabase
      .from("futures_roots")
      .select("id, symbol")
      .eq("symbol", root.toUpperCase())
      .single();

    if (rootError || !rootData) {
      return corsResponse(
        { error: `Futures root not found: ${root}` },
        404,
        origin
      );
    }

    // Build query for continuous mappings
    let query = supabase
      .from("futures_continuous_map")
      .select(`
        continuous_alias,
        depth,
        valid_from,
        valid_until,
        futures_contracts!futures_continuous_map_contract_id_fkey (
          id,
          symbol,
          expiry_month,
          expiry_year,
          last_trade_date
        )
      `)
      .eq("root_id", rootData.id)
      .lte("valid_from", asOf)
      .or(`valid_until.is.null,valid_until.gte.${asOf}`)
      .order("depth");

    if (depth) {
      query = query.eq("depth", depth);
    }

    const { data, error } = await query;

    if (error) {
      console.error("[futures-continuous] Database error:", error);
      return corsResponse(
        { error: "Database error", details: error.message },
        500,
        origin
      );
    }

    if (!data || data.length === 0) {
      return corsResponse(
        { error: `No continuous contracts found for ${root}` },
        404,
        origin
      );
    }

    // Transform response
    const contracts: ContinuousContract[] = data.map((row: any) => {
      const contract = row.futures_contracts;
      const daysToExpiry = contract.last_trade_date
        ? Math.ceil((new Date(contract.last_trade_date).getTime() - new Date(asOf).getTime()) / (1000 * 60 * 60 * 24))
        : 0;

      return {
        alias: row.continuous_alias,
        depth: row.depth,
        contract: {
          id: contract.id,
          symbol: contract.symbol,
          expiry_month: contract.expiry_month,
          expiry_year: contract.expiry_year,
          last_trade_date: contract.last_trade_date,
          days_to_expiry: daysToExpiry,
        },
        valid_from: row.valid_from,
        valid_until: row.valid_until,
      };
    });

    const response: FuturesContinuousResponse = {
      success: true,
      root: rootData.symbol,
      depth: depth || contracts.length,
      as_of: asOf,
      contracts,
    };

    return corsResponse(response, 200, origin);
  } catch (error) {
    console.error("[futures-continuous] Error:", error);
    return corsResponse(
      { error: "Internal server error" },
      500,
      origin
    );
  }
});
