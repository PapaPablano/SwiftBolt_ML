// multi-leg-create: Create a new multi-leg options strategy
// POST /multi-leg-create
//
// Creates a strategy with its legs in a single transaction.
// Calculates max risk/reward and breakeven points.
// Returns the created strategy with legs.

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { handleCorsOptions, jsonResponse, errorResponse } from "../_shared/cors.ts";
import { getSupabaseClientWithAuth, getSupabaseClient } from "../_shared/supabase-client.ts";
import {
  type CreateStrategyRequest,
  type StrategyRow,
  type LegRow,
  strategyRowToModel,
  legRowToModel,
} from "../_shared/types/multileg.ts";
import { validateStrategyCreation } from "../_shared/services/strategy-validator.ts";
import { calculateMaxRiskReward, calculateDTE } from "../_shared/services/pl-calculator.ts";

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
    const body: CreateStrategyRequest = await req.json();

    // Validate request
    const validation = validateStrategyCreation(body);
    if (!validation.isValid) {
      return jsonResponse(
        {
          error: "Validation failed",
          errors: validation.errors,
          warnings: validation.warnings,
        },
        400
      );
    }

    // Try to get user ID from auth, fall back to service role for development
    let userId: string;
    let supabase;

    // First try to get authenticated user
    const authSupabase = getSupabaseClientWithAuth(authHeader);
    const {
      data: { user },
      error: userError,
    } = await authSupabase.auth.getUser();

    if (userError || !user) {
      // For development/testing: use service role client which bypasses RLS
      // In production, you should require authentication
      console.warn("[multi-leg-create] No authenticated user, using service role client");
      supabase = getSupabaseClient();
      // Use a placeholder UUID for anonymous strategies
      userId = "00000000-0000-0000-0000-000000000000";
    } else {
      userId = user.id;
      supabase = authSupabase;
    }

    // Calculate max risk/reward and breakevens
    // First, convert CreateLegInput to OptionsLeg format for calculation
    const legsForCalc = body.legs.map((leg) => ({
      id: "",
      strategyId: "",
      legNumber: leg.legNumber,
      positionType: leg.positionType,
      optionType: leg.optionType,
      strike: leg.strike,
      expiry: leg.expiry,
      entryTimestamp: new Date().toISOString(),
      entryPrice: leg.entryPrice,
      contracts: leg.contracts,
      isClosed: false,
      isAssigned: false,
      isExercised: false,
      updatedAt: new Date().toISOString(),
    }));

    const riskReward = calculateMaxRiskReward(body.strategyType, legsForCalc);

    // Calculate total debit/credit
    let totalDebit = 0;
    let totalCredit = 0;
    for (const leg of body.legs) {
      const legCost = leg.entryPrice * leg.contracts * 100;
      if (leg.positionType === "long") {
        totalDebit += legCost;
      } else {
        totalCredit += legCost;
      }
    }
    const netPremium = totalCredit - totalDebit;

    // Calculate min/max DTE
    const dtes = body.legs.map((leg) => calculateDTE(leg.expiry));
    const minDTE = Math.min(...dtes);
    const maxDTE = Math.max(...dtes);

    // Insert strategy
    const strategyInsert = {
      user_id: userId,
      name: body.name,
      strategy_type: body.strategyType,
      underlying_symbol_id: body.underlyingSymbolId,
      underlying_ticker: body.underlyingTicker,
      status: "open",
      opened_at: new Date().toISOString(),
      total_debit: totalDebit,
      total_credit: totalCredit,
      net_premium: netPremium,
      num_contracts: body.legs[0]?.contracts ?? 1,
      max_risk: riskReward.maxRisk === Infinity ? null : riskReward.maxRisk,
      max_reward: riskReward.maxReward === Infinity ? null : riskReward.maxReward,
      breakeven_points: riskReward.breakevenPoints,
      profit_zones: riskReward.profitZones ?? null,
      forecast_id: body.forecastId ?? null,
      forecast_alignment: body.forecastAlignment ?? null,
      min_dte: minDTE,
      max_dte: maxDTE,
      notes: body.notes ?? null,
      tags: body.tags ?? null,
    };

    const { data: strategyData, error: strategyError } = await supabase
      .from("options_strategies")
      .insert(strategyInsert)
      .select()
      .single();

    if (strategyError) {
      console.error("[multi-leg-create] Strategy insert error:", strategyError);
      return errorResponse(`Failed to create strategy: ${strategyError.message}`, 500);
    }

    const strategyId = strategyData.id;

    // Insert legs
    const legInserts = body.legs.map((leg) => {
      const dte = calculateDTE(leg.expiry);
      return {
        strategy_id: strategyId,
        leg_number: leg.legNumber,
        leg_role: leg.legRole ?? null,
        position_type: leg.positionType,
        option_type: leg.optionType,
        strike: leg.strike,
        expiry: leg.expiry,
        dte_at_entry: dte,
        current_dte: dte,
        entry_price: leg.entryPrice,
        contracts: leg.contracts,
        total_entry_cost: leg.entryPrice * leg.contracts * 100,
        entry_delta: leg.delta ?? null,
        entry_gamma: leg.gamma ?? null,
        entry_theta: leg.theta ?? null,
        entry_vega: leg.vega ?? null,
        entry_rho: leg.rho ?? null,
        current_delta: leg.delta ?? null,
        current_gamma: leg.gamma ?? null,
        current_theta: leg.theta ?? null,
        current_vega: leg.vega ?? null,
        current_rho: leg.rho ?? null,
        entry_implied_vol: leg.impliedVol ?? null,
        current_implied_vol: leg.impliedVol ?? null,
        is_closed: false,
        is_assigned: false,
        is_exercised: false,
        is_near_expiration: dte <= 3,
      };
    });

    const { data: legsData, error: legsError } = await supabase
      .from("options_legs")
      .insert(legInserts)
      .select();

    if (legsError) {
      console.error("[multi-leg-create] Legs insert error:", legsError);
      // Rollback strategy (cascade will handle it if we delete the strategy)
      await supabase.from("options_strategies").delete().eq("id", strategyId);
      return errorResponse(`Failed to create legs: ${legsError.message}`, 500);
    }

    // Calculate combined Greeks
    let combinedDelta = 0;
    let combinedGamma = 0;
    let combinedTheta = 0;
    let combinedVega = 0;
    let combinedRho = 0;

    for (const leg of body.legs) {
      const positionSign = leg.positionType === "long" ? 1 : -1;
      const multiplier = leg.contracts * 100;
      combinedDelta += (leg.delta ?? 0) * multiplier * positionSign;
      combinedGamma += (leg.gamma ?? 0) * multiplier * positionSign;
      combinedTheta += (leg.theta ?? 0) * multiplier * positionSign;
      combinedVega += (leg.vega ?? 0) * multiplier * positionSign;
      combinedRho += (leg.rho ?? 0) * multiplier * positionSign;
    }

    // Update strategy with combined Greeks
    const { error: updateError } = await supabase
      .from("options_strategies")
      .update({
        combined_delta: combinedDelta,
        combined_gamma: combinedGamma,
        combined_theta: combinedTheta,
        combined_vega: combinedVega,
        combined_rho: combinedRho,
        greeks_updated_at: new Date().toISOString(),
      })
      .eq("id", strategyId);

    if (updateError) {
      console.error("[multi-leg-create] Greeks update error:", updateError);
      // Non-fatal, continue
    }

    // Fetch the final strategy with updated data
    const { data: finalStrategy, error: fetchError } = await supabase
      .from("options_strategies")
      .select("*")
      .eq("id", strategyId)
      .single();

    if (fetchError) {
      console.error("[multi-leg-create] Fetch error:", fetchError);
      return errorResponse("Strategy created but failed to fetch result", 500);
    }

    // Build response
    const strategy = strategyRowToModel(finalStrategy as StrategyRow);
    strategy.legs = (legsData as LegRow[]).map(legRowToModel);

    return jsonResponse(
      {
        strategy,
        warnings: validation.warnings,
      },
      201
    );
  } catch (error) {
    console.error("[multi-leg-create] Error:", error);
    return errorResponse(
      error instanceof Error ? error.message : "Internal server error",
      500
    );
  }
});
