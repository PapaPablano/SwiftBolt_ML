// GET /futures/chain?root=GC&asOf=YYYY-MM-DD
// Returns full contract chain for a futures root with all expiries

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { getCorsHeaders, handlePreflight, corsResponse } from "../_shared/cors.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

interface FuturesContract {
  id: string;
  symbol: string;
  contract_code: string;
  expiry_month: number;
  expiry_year: number;
  last_trade_date: string | null;
  first_notice_date: string | null;
  is_active: boolean;
  is_spot: boolean;
  volume_30d: number | null;
  open_interest: number | null;
  continuous_alias?: string;
  continuous_depth?: number;
}

interface FuturesChainResponse {
  success: boolean;
  root: {
    symbol: string;
    name: string;
    exchange: string;
    sector: string;
    tick_size: number;
    point_value: number;
  };
  as_of: string;
  contracts: FuturesContract[];
  continuous_aliases: {
    alias: string;
    depth: number;
    contract_symbol: string;
  }[];
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
    const asOf = url.searchParams.get("asOf") || new Date().toISOString().split("T")[0];

    if (!root) {
      return corsResponse(
        { error: "Missing required parameter: root" },
        400,
        origin
      );
    }

    const supabaseUrl = Deno.env.get("SUPABASE_URL");
    const supabaseServiceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");

    if (!supabaseUrl || !supabaseServiceKey) {
      console.error("[futures-chain] Missing Supabase credentials");
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
      .select("id, symbol, name, exchange, sector, tick_size, point_value")
      .eq("symbol", root.toUpperCase())
      .single();

    if (rootError || !rootData) {
      return corsResponse(
        { error: `Futures root not found: ${root}` },
        404,
        origin
      );
    }

    // Get contracts
    const { data: contractsData, error: contractsError } = await supabase
      .from("futures_contracts")
      .select(`
        id,
        symbol,
        contract_code,
        expiry_month,
        expiry_year,
        last_trade_date,
        first_notice_date,
        is_active,
        is_spot,
        volume_30d,
        open_interest,
        futures_continuous_map!futures_contracts_id_fkey (
          continuous_alias,
          depth
        )
      `)
      .eq("root_id", rootData.id)
      .order("expiry_year", { ascending: true })
      .order("expiry_month", { ascending: true });

    if (contractsError) {
      console.error("[futures-chain] Contracts error:", contractsError);
      return corsResponse(
        { error: "Database error", details: contractsError.message },
        500,
        origin
      );
    }

    // Get continuous mappings
    const { data: continuousData, error: continuousError } = await supabase
      .from("futures_continuous_map")
      .select("continuous_alias, depth, contract_id")
      .eq("root_id", rootData.id)
      .eq("is_active", true)
      .order("depth");

    if (continuousError) {
      console.error("[futures-chain] Continuous error:", continuousError);
    }

    // Build continuous aliases list
    const continuousAliases = (continuousData || []).map((c: any) => ({
      alias: c.continuous_alias,
      depth: c.depth,
      contract_symbol: contractsData?.find((contract: any) => contract.id === c.contract_id)?.symbol || "",
    }));

    // Transform contracts
    const contracts = (contractsData || []).map((c: any) => {
      const mapping = continuousData?.find((m: any) => m.contract_id === c.id);
      return {
        id: c.id,
        symbol: c.symbol,
        contract_code: c.contract_code,
        expiry_month: c.expiry_month,
        expiry_year: c.expiry_year,
        last_trade_date: c.last_trade_date,
        first_notice_date: c.first_notice_date,
        is_active: c.is_active,
        is_spot: c.is_spot,
        volume_30d: c.volume_30d,
        open_interest: c.open_interest,
        ...(mapping && {
          continuous_alias: mapping.continuous_alias,
          continuous_depth: mapping.depth,
        }),
      };
    });

    const response: FuturesChainResponse = {
      success: true,
      root: {
        symbol: rootData.symbol,
        name: rootData.name,
        exchange: rootData.exchange,
        sector: rootData.sector,
        tick_size: rootData.tick_size,
        point_value: rootData.point_value,
      },
      as_of: asOf,
      contracts,
      continuous_aliases: continuousAliases,
    };

    return corsResponse(response, 200, origin);
  } catch (error) {
    console.error("[futures-chain] Error:", error);
    return corsResponse(
      { error: "Internal server error" },
      500,
      origin
    );
  }
});
