// GET /futures?type=roots|chain|continuous
// Consolidated futures endpoint merging futures-roots, futures-chain, and futures-continuous.
//
// Auto-detection when `type` is omitted:
//   - `sector` param present  -> roots
//   - `asOf` param present    -> chain
//   - `depth` param present   -> continuous
//   - none of the above       -> 400 with usage hint

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import {
  corsResponse,
  handlePreflight,
} from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";

// ─── Shared types ──────────────────────────────────────────────────────────

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

interface FuturesRoot {
  id: string;
  symbol: string;
  name: string;
  exchange: string;
  sector: string;
  tick_size: number;
  point_value: number;
  currency: string;
  session_template?: string;
}

interface FuturesRootsResponse {
  success: boolean;
  count: number;
  sector?: string;
  roots: FuturesRoot[];
}

// ─── Type detection ────────────────────────────────────────────────────────

type FuturesType = "roots" | "chain" | "continuous";

function detectType(url: URL): FuturesType | null {
  const explicit = url.searchParams.get("type");
  if (explicit) {
    const lower = explicit.toLowerCase();
    if (lower === "roots" || lower === "chain" || lower === "continuous") {
      return lower;
    }
    return null; // invalid explicit type
  }

  // Auto-detect based on distinguishing params
  if (url.searchParams.has("sector")) return "roots";
  if (url.searchParams.has("asOf")) return "chain";
  if (url.searchParams.has("depth")) return "continuous";

  // If `root` param is present but no distinguishing param, default to chain
  if (url.searchParams.has("root")) return "chain";

  // No params at all -> list roots
  return "roots";
}

// ─── Handlers ──────────────────────────────────────────────────────────────

async function handleRoots(
  url: URL,
  origin: string | null,
): Promise<Response> {
  const sector = url.searchParams.get("sector") || undefined;

  const supabase = getSupabaseClient();

  let query = supabase
    .from("futures_roots")
    .select(
      "id, symbol, name, exchange, sector, tick_size, point_value, currency, session_template",
    )
    .order("symbol");

  if (sector) {
    query = query.eq("sector", sector);
  }

  const { data, error } = await query;

  if (error) {
    console.error("[futures] roots database error:", error);
    return corsResponse(
      { error: "Database error", details: error.message },
      500,
      origin,
    );
  }

  const response: FuturesRootsResponse = {
    success: true,
    count: data?.length || 0,
    ...(sector && { sector }),
    roots: data || [],
  };

  return corsResponse(response, 200, origin);
}

async function handleChain(
  url: URL,
  origin: string | null,
): Promise<Response> {
  const root = url.searchParams.get("root");
  const asOf = url.searchParams.get("asOf") ||
    new Date().toISOString().split("T")[0];

  if (!root) {
    return corsResponse(
      { error: "Missing required parameter: root" },
      400,
      origin,
    );
  }

  const supabase = getSupabaseClient();

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
      origin,
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
    console.error("[futures] chain contracts error:", contractsError);
    return corsResponse(
      { error: "Database error", details: contractsError.message },
      500,
      origin,
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
    console.error("[futures] chain continuous error:", continuousError);
  }

  // Build continuous aliases list
  const continuousAliases = (continuousData || []).map((c: any) => ({
    alias: c.continuous_alias,
    depth: c.depth,
    contract_symbol: contractsData?.find((contract: any) =>
      contract.id === c.contract_id
    )?.symbol || "",
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
}

async function handleContinuous(
  url: URL,
  origin: string | null,
): Promise<Response> {
  const root = url.searchParams.get("root");
  const depthParam = url.searchParams.get("depth");
  const asOf = url.searchParams.get("asOf") ||
    new Date().toISOString().split("T")[0];

  if (!root) {
    return corsResponse(
      { error: "Missing required parameter: root" },
      400,
      origin,
    );
  }

  const depth = depthParam ? parseInt(depthParam, 10) : undefined;
  if (depthParam && (isNaN(depth!) || depth! < 1 || depth! > 12)) {
    return corsResponse(
      { error: "Invalid depth parameter. Must be between 1 and 12" },
      400,
      origin,
    );
  }

  const supabase = getSupabaseClient();

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
      origin,
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
    console.error("[futures] continuous database error:", error);
    return corsResponse(
      { error: "Database error", details: error.message },
      500,
      origin,
    );
  }

  if (!data || data.length === 0) {
    return corsResponse(
      { error: `No continuous contracts found for ${root}` },
      404,
      origin,
    );
  }

  // Transform response
  const contracts: ContinuousContract[] = data.map((row: any) => {
    const contract = row.futures_contracts;
    const daysToExpiry = contract.last_trade_date
      ? Math.ceil(
        (new Date(contract.last_trade_date).getTime() -
          new Date(asOf).getTime()) / (1000 * 60 * 60 * 24),
      )
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
}

// ─── Main handler ──────────────────────────────────────────────────────────

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
    const type = detectType(url);

    if (!type) {
      return corsResponse(
        {
          error:
            "Invalid or undetectable type. Use ?type=roots|chain|continuous, or provide distinguishing params (sector, asOf, depth, root).",
        },
        400,
        origin,
      );
    }

    switch (type) {
      case "roots":
        return await handleRoots(url, origin);
      case "chain":
        return await handleChain(url, origin);
      case "continuous":
        return await handleContinuous(url, origin);
    }
  } catch (error) {
    console.error("[futures] Error:", error);
    return corsResponse(
      { error: "Internal server error" },
      500,
      origin,
    );
  }
});
