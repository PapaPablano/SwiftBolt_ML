// multi-leg-delete: Delete a multi-leg options strategy
// DELETE /multi-leg-delete?strategyId=<uuid>
//
// Permanently deletes a strategy and all associated legs.
// Use with caution - this cannot be undone.

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { handleCorsOptions, jsonResponse, errorResponse } from "../_shared/cors.ts";
import { getSupabaseClientWithAuth, getSupabaseClient } from "../_shared/supabase-client.ts";

serve(async (req: Request): Promise<Response> => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return handleCorsOptions();
  }

  // Allow DELETE or POST (for clients that don't support DELETE)
  if (req.method !== "DELETE" && req.method !== "POST") {
    return errorResponse("Method not allowed", 405);
  }

  try {
    // Get auth header
    const authHeader = req.headers.get("Authorization");
    if (!authHeader) {
      return errorResponse("Authorization required", 401);
    }

    // Parse strategyId from query string or body
    let strategyId: string | null = null;

    const url = new URL(req.url);
    strategyId = url.searchParams.get("strategyId");

    // Also check body for POST requests
    if (!strategyId && req.method === "POST") {
      try {
        const body = await req.json();
        strategyId = body.strategyId;
      } catch {
        // Body parsing failed, continue with null
      }
    }

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
      console.warn("[multi-leg-delete] No authenticated user, using service role client");
      supabase = getSupabaseClient();
      userId = "00000000-0000-0000-0000-000000000000";
    } else {
      userId = user.id;
      supabase = authSupabase;
    }

    // First verify the strategy exists and belongs to the user
    const { data: strategyData, error: fetchError } = await supabase
      .from("options_strategies")
      .select("id, name, user_id")
      .eq("id", strategyId)
      .eq("user_id", userId)
      .single();

    if (fetchError) {
      if (fetchError.code === "PGRST116") {
        return errorResponse("Strategy not found", 404);
      }
      console.error("[multi-leg-delete] Fetch error:", fetchError);
      return errorResponse(`Failed to fetch strategy: ${fetchError.message}`, 500);
    }

    // Delete associated legs first (if no CASCADE constraint)
    const { error: legsDeleteError } = await supabase
      .from("options_legs")
      .delete()
      .eq("strategy_id", strategyId);

    if (legsDeleteError) {
      console.error("[multi-leg-delete] Legs delete error:", legsDeleteError);
      // Continue anyway - cascade might handle it
    }

    // Delete associated alerts
    const { error: alertsDeleteError } = await supabase
      .from("options_multi_leg_alerts")
      .delete()
      .eq("strategy_id", strategyId);

    if (alertsDeleteError) {
      console.error("[multi-leg-delete] Alerts delete error:", alertsDeleteError);
      // Continue anyway
    }

    // Delete associated metrics
    const { error: metricsDeleteError } = await supabase
      .from("options_strategy_metrics")
      .delete()
      .eq("strategy_id", strategyId);

    if (metricsDeleteError) {
      console.error("[multi-leg-delete] Metrics delete error:", metricsDeleteError);
      // Continue anyway
    }

    // Delete the strategy itself
    const { error: deleteError } = await supabase
      .from("options_strategies")
      .delete()
      .eq("id", strategyId)
      .eq("user_id", userId);

    if (deleteError) {
      console.error("[multi-leg-delete] Strategy delete error:", deleteError);
      return errorResponse(`Failed to delete strategy: ${deleteError.message}`, 500);
    }

    console.log(`[multi-leg-delete] Successfully deleted strategy ${strategyId} (${strategyData.name})`);

    return jsonResponse({
      success: true,
      deletedId: strategyId,
      deletedName: strategyData.name,
    });
  } catch (error) {
    console.error("[multi-leg-delete] Error:", error);
    return errorResponse(
      error instanceof Error ? error.message : "Internal server error",
      500
    );
  }
});
