// multi-leg-list: List multi-leg options strategies for the current user
// GET /multi-leg-list?status=open&limit=20&offset=0
//
// Returns paginated list of strategies with alert counts.
// Supports filtering by status, underlying, and strategy type.

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import {
  errorResponse,
  handleCorsOptions,
  jsonResponse,
} from "../_shared/cors.ts";
import {
  getSupabaseClient,
  getSupabaseClientWithAuth,
} from "../_shared/supabase-client.ts";
import {
  type StrategyRow,
  strategyRowToModel,
  type StrategyStatus,
  type StrategyType,
} from "../_shared/types/multileg.ts";

serve(async (req: Request): Promise<Response> => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return handleCorsOptions();
  }

  // Only allow GET
  if (req.method !== "GET") {
    return errorResponse("Method not allowed", 405);
  }

  try {
    // Get auth header
    const authHeader = req.headers.get("Authorization");
    if (!authHeader) {
      return errorResponse("Authorization required", 401);
    }

    // Parse query parameters
    const url = new URL(req.url);
    const status = url.searchParams.get("status") as StrategyStatus | null;
    const underlyingSymbolId = url.searchParams.get("underlyingSymbolId");
    const strategyType = url.searchParams.get("strategyType") as
      | StrategyType
      | null;
    const limit = Math.min(
      parseInt(url.searchParams.get("limit") ?? "20"),
      100,
    );
    const offset = parseInt(url.searchParams.get("offset") ?? "0");

    // Try to get user ID from auth, fall back to service role for development
    let userId: string | null = null;
    let supabase;

    // First try to get authenticated user
    const authSupabase = getSupabaseClientWithAuth(authHeader);
    const {
      data: { user },
      error: userError,
    } = await authSupabase.auth.getUser();

    if (userError || !user) {
      // For development/testing: use service role client which bypasses RLS
      console.warn(
        "[multi-leg-list] No authenticated user, using service role client",
      );
      supabase = getSupabaseClient();
      userId = "00000000-0000-0000-0000-000000000000";
    } else {
      userId = user.id;
      supabase = authSupabase;
    }

    // Build query
    let query = supabase
      .from("options_strategies")
      .select("*", { count: "exact" })
      .eq("user_id", userId) // Filter by user ID (needed when using service role)
      .order("created_at", { ascending: false })
      .range(offset, offset + limit - 1);

    // Apply filters
    if (status) {
      query = query.eq("status", status);
    }

    if (underlyingSymbolId) {
      query = query.eq("underlying_symbol_id", underlyingSymbolId);
    }

    if (strategyType) {
      query = query.eq("strategy_type", strategyType);
    }

    const { data, error, count } = await query;

    if (error) {
      console.error("[multi-leg-list] Query error:", error);
      return errorResponse(`Failed to fetch strategies: ${error.message}`, 500);
    }

    // Get alert counts for each strategy
    const strategyIds = (data as StrategyRow[]).map((s) => s.id);

    let alertCounts: Record<string, { total: number; critical: number }> = {};

    if (strategyIds.length > 0) {
      const { data: alertData, error: alertError } = await supabase
        .from("options_multi_leg_alerts")
        .select("strategy_id, severity")
        .in("strategy_id", strategyIds)
        .is("resolved_at", null);

      if (!alertError && alertData) {
        // Count alerts by strategy
        for (const alert of alertData) {
          const sid = alert.strategy_id;
          if (!alertCounts[sid]) {
            alertCounts[sid] = { total: 0, critical: 0 };
          }
          alertCounts[sid].total++;
          if (alert.severity === "critical") {
            alertCounts[sid].critical++;
          }
        }
      }
    }

    // Transform to response format
    const strategies = (data as StrategyRow[]).map((row) => {
      const strategy = strategyRowToModel(row);
      return {
        ...strategy,
        alertCount: alertCounts[row.id]?.total ?? 0,
        criticalAlertCount: alertCounts[row.id]?.critical ?? 0,
      };
    });

    return jsonResponse({
      strategies,
      total: count ?? 0,
      hasMore: (count ?? 0) > offset + limit,
      limit,
      offset,
    });
  } catch (error) {
    console.error("[multi-leg-list] Error:", error);
    return errorResponse(
      error instanceof Error ? error.message : "Internal server error",
      500,
    );
  }
});
