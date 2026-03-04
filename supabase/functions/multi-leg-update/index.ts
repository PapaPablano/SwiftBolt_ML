// multi-leg-update: Update a multi-leg strategy's metadata
// PATCH /multi-leg-update
//
// Updates strategy name, notes, tags, forecast linkage.
// Does not update legs directly - use close-leg for that.

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import {
  errorResponse,
  handleCorsOptions,
  jsonResponse,
} from "../_shared/cors.ts";
import { getSupabaseClientWithAuth } from "../_shared/supabase-client.ts";
import {
  type StrategyRow,
  strategyRowToModel,
  type UpdateStrategyRequest,
} from "../_shared/types/multileg.ts";

interface UpdateRequestWithId extends UpdateStrategyRequest {
  strategyId: string;
}

serve(async (req: Request): Promise<Response> => {
  const origin = req.headers.get("Origin");

  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return handleCorsOptions(origin);
  }

  // Only allow PATCH
  if (req.method !== "PATCH") {
    return errorResponse("Method not allowed", 405, origin);
  }

  try {
    // Get auth header
    const authHeader = req.headers.get("Authorization");
    if (!authHeader) {
      return errorResponse("Authorization required", 401, origin);
    }

    // Parse request body
    const body: UpdateRequestWithId = await req.json();

    if (!body.strategyId) {
      return errorResponse("strategyId is required", 400, origin);
    }

    // Build update object (only include non-undefined fields)
    const updates: Record<string, unknown> = {};

    if (body.name !== undefined) {
      if (!body.name || body.name.trim().length === 0) {
        return errorResponse("Strategy name cannot be empty", 400, origin);
      }
      updates.name = body.name.trim();
    }

    if (body.notes !== undefined) {
      updates.notes = body.notes;
    }

    if (body.tags !== undefined) {
      updates.tags = body.tags;
    }

    if (body.forecastId !== undefined) {
      updates.forecast_id = body.forecastId;
    }

    if (body.forecastAlignment !== undefined) {
      updates.forecast_alignment = body.forecastAlignment;
      updates.alignment_check_at = new Date().toISOString();
    }

    // Check if there's anything to update
    if (Object.keys(updates).length === 0) {
      return errorResponse("No fields to update", 400, origin);
    }

    // Add updated_at timestamp
    updates.updated_at = new Date().toISOString();

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

    // Update strategy
    const { data, error } = await supabase
      .from("options_strategies")
      .update(updates)
      .eq("id", body.strategyId)
      .eq("user_id", userId) // Filter by user ID
      .select()
      .single();

    if (error) {
      if (error.code === "PGRST116") {
        return errorResponse("Strategy not found", 404, origin);
      }
      console.error("[multi-leg-update] Update error:", error);
      return errorResponse(
        `Failed to update strategy: ${error.message}`,
        500,
        origin,
      );
    }

    const strategy = strategyRowToModel(data as StrategyRow);

    return jsonResponse({ strategy });
  } catch (error) {
    console.error("[multi-leg-update] Error:", error);
    return errorResponse(
      error instanceof Error ? error.message : "Internal server error",
      500,
      origin,
    );
  }
});
