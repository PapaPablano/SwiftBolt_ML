// GET /futures/roots?sector=indices|metals
// Returns list of futures roots (ES, NQ, GC, etc.) with metadata

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { getCorsHeaders, handlePreflight, corsResponse } from "../_shared/cors.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

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
    const sector = url.searchParams.get("sector") || undefined;

    // Initialize Supabase client
    const supabaseUrl = Deno.env.get("SUPABASE_URL");
    const supabaseServiceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");

    if (!supabaseUrl || !supabaseServiceKey) {
      console.error("[futures-roots] Missing Supabase credentials");
      return corsResponse(
        { error: "Server configuration error" },
        500,
        origin
      );
    }

    const supabase = createClient(supabaseUrl, supabaseServiceKey);

    // Build query
    let query = supabase
      .from("futures_roots")
      .select("id, symbol, name, exchange, sector, tick_size, point_value, currency, session_template")
      .order("symbol");

    if (sector) {
      query = query.eq("sector", sector);
    }

    const { data, error } = await query;

    if (error) {
      console.error("[futures-roots] Database error:", error);
      return corsResponse(
        { error: "Database error", details: error.message },
        500,
        origin
      );
    }

    const response: FuturesRootsResponse = {
      success: true,
      count: data?.length || 0,
      ...(sector && { sector }),
      roots: data || [],
    };

    return corsResponse(response, 200, origin);
  } catch (error) {
    console.error("[futures-roots] Error:", error);
    return corsResponse(
      { error: "Internal server error" },
      500,
      origin
    );
  }
});
