// multi-leg-detail: Get detailed information about a multi-leg strategy
// GET /multi-leg-detail?strategyId=<uuid>
//
// Returns the strategy with all legs, alerts, and recent metrics.

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { handleCorsOptions, jsonResponse, errorResponse } from "../_shared/cors.ts";
import { getSupabaseClientWithAuth, getSupabaseClient } from "../_shared/supabase-client.ts";
import {
  type StrategyRow,
  type LegRow,
  type AlertRow,
  strategyRowToModel,
  legRowToModel,
  alertRowToModel,
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
    const strategyId = url.searchParams.get("strategyId");

    if (!strategyId) {
      return errorResponse("strategyId is required", 400);
    }

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
      console.warn("[multi-leg-detail] No authenticated user, using service role client");
      supabase = getSupabaseClient();
      userId = "00000000-0000-0000-0000-000000000000";
    } else {
      userId = user.id;
      supabase = authSupabase;
    }

    // Fetch strategy
    const { data: strategyData, error: strategyError } = await supabase
      .from("options_strategies")
      .select("*")
      .eq("id", strategyId)
      .eq("user_id", userId)  // Filter by user ID (needed when using service role)
      .single();

    if (strategyError) {
      if (strategyError.code === "PGRST116") {
        return errorResponse("Strategy not found", 404);
      }
      console.error("[multi-leg-detail] Strategy fetch error:", strategyError);
      return errorResponse(`Failed to fetch strategy: ${strategyError.message}`, 500);
    }

    // Fetch legs
    const { data: legsData, error: legsError } = await supabase
      .from("options_legs")
      .select("*")
      .eq("strategy_id", strategyId)
      .order("leg_number", { ascending: true });

    if (legsError) {
      console.error("[multi-leg-detail] Legs fetch error:", legsError);
      return errorResponse(`Failed to fetch legs: ${legsError.message}`, 500);
    }

    // Fetch active alerts (unresolved)
    const { data: alertsData, error: alertsError } = await supabase
      .from("options_multi_leg_alerts")
      .select("*")
      .eq("strategy_id", strategyId)
      .is("resolved_at", null)
      .order("created_at", { ascending: false });

    if (alertsError) {
      console.error("[multi-leg-detail] Alerts fetch error:", alertsError);
      // Non-fatal, continue with empty alerts
    }

    // Fetch recent metrics (last 30 days)
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

    const { data: metricsData, error: metricsError } = await supabase
      .from("options_strategy_metrics")
      .select("*")
      .eq("strategy_id", strategyId)
      .gte("recorded_at", thirtyDaysAgo.toISOString().split("T")[0])
      .order("recorded_at", { ascending: true });

    if (metricsError) {
      console.error("[multi-leg-detail] Metrics fetch error:", metricsError);
      // Non-fatal, continue with empty metrics
    }

    // Fetch leg entries for each leg
    const legIds = (legsData as LegRow[]).map((l) => l.id);
    let entriesMap: Record<string, any[]> = {};

    if (legIds.length > 0) {
      const { data: entriesData, error: entriesError } = await supabase
        .from("options_leg_entries")
        .select("*")
        .in("leg_id", legIds)
        .order("entry_timestamp", { ascending: true });

      if (!entriesError && entriesData) {
        for (const entry of entriesData) {
          if (!entriesMap[entry.leg_id]) {
            entriesMap[entry.leg_id] = [];
          }
          entriesMap[entry.leg_id].push({
            id: entry.id,
            legId: entry.leg_id,
            entryPrice: entry.entry_price,
            contracts: entry.contracts,
            entryTimestamp: entry.entry_timestamp,
            notes: entry.notes,
          });
        }
      }
    }

    // Transform to response format
    const strategy = strategyRowToModel(strategyData as StrategyRow);
    const legs = (legsData as LegRow[]).map((row) => {
      const leg = legRowToModel(row);
      leg.entries = entriesMap[row.id] ?? [];
      return leg;
    });
    const alerts = (alertsData as AlertRow[] ?? []).map(alertRowToModel);

    // Transform metrics
    const metrics = (metricsData ?? []).map((m: any) => ({
      id: m.id,
      strategyId: m.strategy_id,
      recordedAt: m.recorded_at,
      recordedTimestamp: m.recorded_timestamp,
      underlyingPrice: m.underlying_price,
      totalValue: m.total_value,
      totalPL: m.total_pl,
      totalPLPct: m.total_pl_pct,
      deltaSnapshot: m.delta_snapshot,
      gammaSnapshot: m.gamma_snapshot,
      thetaSnapshot: m.theta_snapshot,
      vegaSnapshot: m.vega_snapshot,
      minDTE: m.min_dte,
      alertCount: m.alert_count,
      criticalAlertCount: m.critical_alert_count,
    }));

    // Include legs at top level for client compatibility
    strategy.legs = legs;

    return jsonResponse({
      strategy,
      legs,  // Also at top level for client decoding
      alerts,
      metrics,
    });
  } catch (error) {
    console.error("[multi-leg-detail] Error:", error);
    return errorResponse(
      error instanceof Error ? error.message : "Internal server error",
      500
    );
  }
});
