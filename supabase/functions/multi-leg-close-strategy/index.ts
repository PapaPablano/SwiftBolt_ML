// multi-leg-close-strategy: Close all legs in a strategy at once
// POST /multi-leg-close-strategy
//
// Closes all open legs with provided exit prices.
// Calculates total realized P&L and marks strategy as closed.

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
  type CloseStrategyRequest,
  type LegRow,
  legRowToModel,
  type StrategyRow,
  strategyRowToModel,
} from "../_shared/types/multileg.ts";
import { validateStrategyClosure } from "../_shared/services/strategy-validator.ts";

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
    const body: CloseStrategyRequest = await req.json();

    if (!body.strategyId) {
      return errorResponse("strategyId is required", 400);
    }

    if (!body.exitPrices || body.exitPrices.length === 0) {
      return errorResponse("exitPrices are required", 400);
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
        "[multi-leg-close-strategy] No authenticated user, using service role client",
      );
      supabase = getSupabaseClient();
      userId = "00000000-0000-0000-0000-000000000000";
    } else {
      userId = user.id;
      supabase = authSupabase;
    }

    // Fetch strategy with legs
    const { data: strategyData, error: strategyError } = await supabase
      .from("options_strategies")
      .select("*")
      .eq("id", body.strategyId)
      .eq("user_id", userId) // Filter by user ID
      .single();

    if (strategyError) {
      if (strategyError.code === "PGRST116") {
        return errorResponse("Strategy not found", 404);
      }
      console.error(
        "[multi-leg-close-strategy] Strategy fetch error:",
        strategyError,
      );
      return errorResponse(
        `Failed to fetch strategy: ${strategyError.message}`,
        500,
      );
    }

    if ((strategyData as StrategyRow).status === "closed") {
      return errorResponse("Strategy is already closed", 400);
    }

    // Fetch all legs
    const { data: legsData, error: legsError } = await supabase
      .from("options_legs")
      .select("*")
      .eq("strategy_id", body.strategyId);

    if (legsError) {
      console.error("[multi-leg-close-strategy] Legs fetch error:", legsError);
      return errorResponse(`Failed to fetch legs: ${legsError.message}`, 500);
    }

    const legs = (legsData as LegRow[]).map(legRowToModel);

    // Validate closure
    const validation = validateStrategyClosure(legs, body.exitPrices);
    if (!validation.isValid) {
      return jsonResponse({
        error: "Validation failed",
        errors: validation.errors,
      }, 400);
    }

    // Create exit price map
    const exitPriceMap = new Map(
      body.exitPrices.map((p) => [p.legId, p.exitPrice]),
    );

    // Close each open leg
    let totalRealizedPL = 0;
    const closedLegs: any[] = [];

    for (const leg of legs) {
      if (leg.isClosed) {
        // Already closed, add its realized P&L
        totalRealizedPL += leg.realizedPL ?? 0;
        continue;
      }

      const exitPrice = exitPriceMap.get(leg.id);
      if (exitPrice === undefined) {
        continue; // Shouldn't happen after validation
      }

      // Calculate realized P&L
      const entryCost = leg.entryPrice * leg.contracts * 100;
      const exitValue = exitPrice * leg.contracts * 100;

      let realizedPL: number;
      if (leg.positionType === "long") {
        realizedPL = exitValue - entryCost;
      } else {
        realizedPL = entryCost - exitValue;
      }

      totalRealizedPL += realizedPL;

      // Update leg
      const { data: updatedLeg, error: updateError } = await supabase
        .from("options_legs")
        .update({
          is_closed: true,
          exit_price: exitPrice,
          exit_timestamp: new Date().toISOString(),
          realized_pl: realizedPL,
          updated_at: new Date().toISOString(),
        })
        .eq("id", leg.id)
        .select()
        .single();

      if (updateError) {
        console.error(
          `[multi-leg-close-strategy] Failed to close leg ${leg.id}:`,
          updateError,
        );
        // Continue with other legs
      } else {
        closedLegs.push(legRowToModel(updatedLeg as LegRow));
      }
    }

    // Update strategy to closed
    const { data: updatedStrategy, error: strategyUpdateError } = await supabase
      .from("options_strategies")
      .update({
        status: "closed",
        closed_at: new Date().toISOString(),
        realized_pl: totalRealizedPL,
        notes: body.notes
          ? `${
            (strategyData as StrategyRow).notes ?? ""
          }\n\nClosed: ${body.notes}`.trim()
          : (strategyData as StrategyRow).notes,
        updated_at: new Date().toISOString(),
      })
      .eq("id", body.strategyId)
      .select()
      .single();

    if (strategyUpdateError) {
      console.error(
        "[multi-leg-close-strategy] Strategy update error:",
        strategyUpdateError,
      );
      return errorResponse(
        `Failed to close strategy: ${strategyUpdateError.message}`,
        500,
      );
    }

    const strategy = strategyRowToModel(updatedStrategy as StrategyRow);
    strategy.legs = closedLegs;

    return jsonResponse({
      strategy,
      totalRealizedPL,
      legsClosed: closedLegs.length,
    });
  } catch (error) {
    console.error("[multi-leg-close-strategy] Error:", error);
    return errorResponse(
      error instanceof Error ? error.message : "Internal server error",
      500,
    );
  }
});
