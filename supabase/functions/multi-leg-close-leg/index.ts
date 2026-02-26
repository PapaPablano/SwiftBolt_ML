// multi-leg-close-leg: Close a single leg in a strategy
// POST /multi-leg-close-leg
//
// Closes a leg with an exit price, calculates realized P&L.
// If all legs are closed, marks the strategy as closed.

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
  type CloseLegRequest,
  type LegRow,
  legRowToModel,
} from "../_shared/types/multileg.ts";
import { validateLegClosure } from "../_shared/services/strategy-validator.ts";

serve(async (req: Request): Promise<Response> => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return handleCorsOptions();
  }

  // Only allow POST
  if (req.method !== "POST") {
    return errorResponse("Method not allowed", 405);
  }

  try {
    // Get auth header
    const authHeader = req.headers.get("Authorization");
    if (!authHeader) {
      return errorResponse("Authorization required", 401);
    }

    // Parse request body
    const body: CloseLegRequest = await req.json();

    if (!body.legId) {
      return errorResponse("legId is required", 400);
    }

    if (body.exitPrice === undefined || body.exitPrice <= 0) {
      return errorResponse("exitPrice must be a positive number", 400);
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
      console.warn(
        "[multi-leg-close-leg] No authenticated user, using service role client",
      );
      supabase = getSupabaseClient();
      userId = "00000000-0000-0000-0000-000000000000";
    } else {
      userId = user.id;
      supabase = authSupabase;
    }

    // Fetch the leg to validate and get strategy info
    const { data: legData, error: legError } = await supabase
      .from("options_legs")
      .select("*, options_strategies!inner(id, user_id, status)")
      .eq("id", body.legId)
      .eq("options_strategies.user_id", userId) // Filter by user ID
      .single();

    if (legError) {
      if (legError.code === "PGRST116") {
        return errorResponse("Leg not found", 404);
      }
      console.error("[multi-leg-close-leg] Leg fetch error:", legError);
      return errorResponse(`Failed to fetch leg: ${legError.message}`, 500);
    }

    const leg = legRowToModel(legData as LegRow);

    // Validate closure
    const validation = validateLegClosure(leg, body.exitPrice);
    if (!validation.isValid) {
      return jsonResponse({
        error: "Validation failed",
        errors: validation.errors,
      }, 400);
    }

    // Calculate realized P&L
    const entryCost = leg.entryPrice * leg.contracts * 100;
    const exitValue = body.exitPrice * leg.contracts * 100;

    let realizedPL: number;
    if (leg.positionType === "long") {
      // Long: profit if exit > entry
      realizedPL = exitValue - entryCost;
    } else {
      // Short: profit if exit < entry (we receive premium at entry, pay to close)
      realizedPL = entryCost - exitValue;
    }

    // Update leg
    const { error: updateError } = await supabase
      .from("options_legs")
      .update({
        is_closed: true,
        exit_price: body.exitPrice,
        exit_timestamp: new Date().toISOString(),
        realized_pl: realizedPL,
        notes: body.notes
          ? `${leg.notes ?? ""}\n${body.notes}`.trim()
          : leg.notes,
        updated_at: new Date().toISOString(),
      })
      .eq("id", body.legId);

    if (updateError) {
      console.error("[multi-leg-close-leg] Update error:", updateError);
      return errorResponse(`Failed to close leg: ${updateError.message}`, 500);
    }

    // Check if all legs are now closed
    const { data: remainingLegs, error: remainingError } = await supabase
      .from("options_legs")
      .select("id")
      .eq("strategy_id", leg.strategyId)
      .eq("is_closed", false);

    if (!remainingError && remainingLegs && remainingLegs.length === 0) {
      // All legs closed - close the strategy
      const { data: allLegs } = await supabase
        .from("options_legs")
        .select("realized_pl")
        .eq("strategy_id", leg.strategyId);

      const totalRealizedPL = (allLegs ?? []).reduce(
        (sum, l) => sum + (l.realized_pl ?? 0),
        0,
      );

      await supabase
        .from("options_strategies")
        .update({
          status: "closed",
          closed_at: new Date().toISOString(),
          realized_pl: totalRealizedPL,
          updated_at: new Date().toISOString(),
        })
        .eq("id", leg.strategyId);
    }

    // Fetch updated leg
    const { data: updatedLeg, error: fetchError } = await supabase
      .from("options_legs")
      .select("*")
      .eq("id", body.legId)
      .single();

    if (fetchError) {
      console.error("[multi-leg-close-leg] Fetch error:", fetchError);
      return errorResponse("Leg closed but failed to fetch result", 500);
    }

    return jsonResponse({
      leg: legRowToModel(updatedLeg as LegRow),
      realizedPL,
      allLegsClosed: !remainingError && remainingLegs &&
        remainingLegs.length === 0,
    });
  } catch (error) {
    console.error("[multi-leg-close-leg] Error:", error);
    return errorResponse(
      error instanceof Error ? error.message : "Internal server error",
      500,
    );
  }
});
