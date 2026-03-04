// multi-leg-detail: Get detailed information about a multi-leg strategy
// GET /multi-leg-detail?strategyId=<uuid>
//
// Returns the strategy with all legs, alerts, and recent metrics.

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import {
  errorResponse,
  handleCorsOptions,
  jsonResponse,
} from "../_shared/cors.ts";
import { getSupabaseClientWithAuth } from "../_shared/supabase-client.ts";
import {
  type AlertRow,
  alertRowToModel,
  type LegRow,
  legRowToModel,
  type StrategyRow,
  strategyRowToModel,
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

    // Authenticate user
    const authSupabase = getSupabaseClientWithAuth(authHeader);
    const {
      data: { user },
      error: userError,
    } = await authSupabase.auth.getUser();

    if (userError || !user) {
      return new Response(
        JSON.stringify({ error: "Authentication required" }),
        {
          status: 401,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    const userId: string = user.id;
    const supabase = authSupabase;

    // Fetch strategy first (sequential — strategyId is already known, but we
    // must verify ownership and existence before proceeding)
    const { data: strategyData, error: strategyError } = await supabase
      .from("options_strategies")
      .select(
        "id, user_id, name, strategy_type, underlying_symbol_id, underlying_ticker, " +
          "created_at, opened_at, closed_at, status, " +
          "total_debit, total_credit, net_premium, num_contracts, " +
          "max_risk, max_reward, max_risk_pct, breakeven_points, profit_zones, " +
          "current_value, total_pl, total_pl_pct, realized_pl, " +
          "forecast_id, forecast_alignment, forecast_confidence, alignment_check_at, " +
          "combined_delta, combined_gamma, combined_theta, combined_vega, combined_rho, greeks_updated_at, " +
          "min_dte, max_dte, tags, notes, last_alert_at, version, updated_at",
      )
      .eq("id", strategyId)
      .eq("user_id", userId)
      .single();

    if (strategyError) {
      if (strategyError.code === "PGRST116") {
        return errorResponse("Strategy not found", 404);
      }
      console.error("[multi-leg-detail] Strategy fetch error:", strategyError);
      return errorResponse(
        `Failed to fetch strategy: ${strategyError.message}`,
        500,
      );
    }

    // Fetch legs, alerts, and metrics in parallel
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

    const [legsResult, alertsResult, metricsResult] = await Promise.all([
      supabase
        .from("options_legs")
        .select(
          "id, strategy_id, leg_number, leg_role, position_type, option_type, strike, expiry, " +
            "dte_at_entry, current_dte, entry_timestamp, entry_price, contracts, total_entry_cost, " +
            "current_price, current_value, unrealized_pl, unrealized_pl_pct, " +
            "is_closed, exit_price, exit_timestamp, realized_pl, " +
            "entry_delta, entry_gamma, entry_theta, entry_vega, entry_rho, " +
            "current_delta, current_gamma, current_theta, current_vega, current_rho, greeks_updated_at, " +
            "entry_implied_vol, current_implied_vol, vega_exposure, " +
            "is_assigned, assignment_timestamp, assignment_price, " +
            "is_exercised, exercise_timestamp, exercise_price, " +
            "is_itm, is_deep_itm, is_breaching_strike, is_near_expiration, " +
            "notes, updated_at",
        )
        .eq("strategy_id", strategyId)
        .order("leg_number", { ascending: true }),
      supabase
        .from("options_multi_leg_alerts")
        .select(
          "id, strategy_id, leg_id, alert_type, severity, title, reason, details, " +
            "suggested_action, created_at, acknowledged_at, resolved_at, resolution_action, action_required",
        )
        .eq("strategy_id", strategyId)
        .is("resolved_at", null)
        .order("created_at", { ascending: false }),
      supabase
        .from("options_strategy_metrics")
        .select(
          "id, strategy_id, recorded_at, recorded_timestamp, underlying_price, " +
            "total_value, total_pl, total_pl_pct, " +
            "delta_snapshot, gamma_snapshot, theta_snapshot, vega_snapshot, " +
            "min_dte, alert_count, critical_alert_count",
        )
        .eq("strategy_id", strategyId)
        .gte("recorded_at", thirtyDaysAgo.toISOString().split("T")[0])
        .order("recorded_at", { ascending: true }),
    ]);

    const { data: legsData, error: legsError } = legsResult;
    const { data: alertsData, error: alertsError } = alertsResult;
    const { data: metricsData, error: metricsError } = metricsResult;

    if (legsError) {
      console.error("[multi-leg-detail] Legs fetch error:", legsError);
      return errorResponse(`Failed to fetch legs: ${legsError.message}`, 500);
    }

    if (alertsError) {
      console.error("[multi-leg-detail] Alerts fetch error:", alertsError);
      // Non-fatal, continue with empty alerts
    }

    if (metricsError) {
      console.error("[multi-leg-detail] Metrics fetch error:", metricsError);
      // Non-fatal, continue with empty metrics
    }

    // Fetch leg entries for each leg
    const legIds = (legsData as LegRow[]).map((l) => l.id);
    const entriesMap: Record<string, any[]> = {};

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
      legs, // Also at top level for client decoding
      alerts,
      metrics,
    });
  } catch (error) {
    console.error("[multi-leg-detail] Error:", error);
    return errorResponse(
      error instanceof Error ? error.message : "Internal server error",
      500,
    );
  }
});
