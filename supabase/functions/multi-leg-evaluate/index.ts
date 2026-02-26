// multi-leg-evaluate: Scheduled job to evaluate all open strategies
// POST /multi-leg-evaluate (called by cron or manually)
//
// Evaluates all open strategies against current market data.
// Generates alerts, updates P&L and Greeks, records daily metrics.
// Should be scheduled to run every 15 minutes during market hours.

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import {
  errorResponse,
  handleCorsOptions,
  jsonResponse,
} from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";
import {
  type AlertRow,
  alertRowToModel,
  type LegRow,
  legRowToModel,
  type StrategyRow,
  strategyRowToModel,
} from "../_shared/types/multileg.ts";
import {
  type AlertInput,
  DEFAULT_PREFERENCES,
  evaluateStrategy,
  type EvaluationContext,
  isDuplicateAlert,
} from "../_shared/services/alert-evaluator.ts";
import {
  calculateDTE,
  calculateStrategyPL,
  type LegPriceData,
} from "../_shared/services/pl-calculator.ts";

serve(async (req: Request): Promise<Response> => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return handleCorsOptions();
  }

  // Only allow POST (scheduled jobs use POST)
  if (req.method !== "POST") {
    return errorResponse("Method not allowed", 405);
  }

  const startTime = Date.now();
  console.log(
    `[multi-leg-evaluate] Starting evaluation job at ${
      new Date().toISOString()
    }`,
  );

  try {
    // Get Supabase client with service role (bypasses RLS)
    const supabase = getSupabaseClient();

    // Fetch all open strategies
    const { data: strategiesData, error: strategiesError } = await supabase
      .from("options_strategies")
      .select("*")
      .eq("status", "open");

    if (strategiesError) {
      console.error(
        "[multi-leg-evaluate] Failed to fetch strategies:",
        strategiesError,
      );
      return errorResponse(
        `Failed to fetch strategies: ${strategiesError.message}`,
        500,
      );
    }

    const strategies = (strategiesData as StrategyRow[]).map(
      strategyRowToModel,
    );
    console.log(
      `[multi-leg-evaluate] Found ${strategies.length} open strategies to evaluate`,
    );

    // Track results
    let strategiesEvaluated = 0;
    let alertsGenerated = 0;
    let errors = 0;

    // Evaluate each strategy
    for (const strategy of strategies) {
      try {
        const result = await evaluateSingleStrategy(supabase, strategy);
        strategiesEvaluated++;
        alertsGenerated += result.alertsGenerated;
      } catch (error) {
        console.error(
          `[multi-leg-evaluate] Error evaluating strategy ${strategy.id}:`,
          error,
        );
        errors++;
      }
    }

    const duration = Date.now() - startTime;
    console.log(
      `[multi-leg-evaluate] Completed: ${strategiesEvaluated} strategies, ${alertsGenerated} alerts, ${errors} errors in ${duration}ms`,
    );

    return jsonResponse({
      success: true,
      strategiesEvaluated,
      alertsGenerated,
      errors,
      durationMs: duration,
    });
  } catch (error) {
    console.error("[multi-leg-evaluate] Error:", error);
    return errorResponse(
      error instanceof Error ? error.message : "Internal server error",
      500,
    );
  }
});

interface EvaluationResult {
  alertsGenerated: number;
}

async function evaluateSingleStrategy(
  supabase: any,
  strategy: ReturnType<typeof strategyRowToModel>,
): Promise<EvaluationResult> {
  // Fetch legs
  const { data: legsData, error: legsError } = await supabase
    .from("options_legs")
    .select("*")
    .eq("strategy_id", strategy.id);

  if (legsError) {
    throw new Error(`Failed to fetch legs: ${legsError.message}`);
  }

  const legs = (legsData as LegRow[]).map(legRowToModel);

  // Fetch current option prices from options_ranks
  const legPrices = await fetchCurrentPrices(supabase, strategy, legs);

  // Fetch underlying price from quotes
  const { data: quoteData } = await supabase
    .from("quotes")
    .select("last")
    .eq("symbol_id", strategy.underlyingSymbolId)
    .single();

  const underlyingPrice = quoteData?.last ?? 0;

  // Note: We continue even if underlyingPrice is 0 to update Greeks
  // P&L calculations will be skipped but leg Greeks will still be updated
  if (underlyingPrice === 0) {
    console.log(
      `[multi-leg-evaluate] No quote for ${strategy.underlyingTicker}, will update Greeks only`,
    );
  }

  // Fetch forecast if linked
  let forecast: EvaluationContext["forecast"] | undefined;
  if (strategy.forecastId) {
    const { data: forecastData } = await supabase
      .from("ml_forecasts")
      .select("overall_label, confidence, horizon")
      .eq("id", strategy.forecastId)
      .single();

    if (forecastData) {
      forecast = {
        label: forecastData.overall_label,
        confidence: forecastData.confidence,
        horizon: forecastData.horizon,
      };
    }
  }

  // Fetch user preferences
  const { data: prefsData } = await supabase
    .from("user_alert_preferences")
    .select("*")
    .eq("user_id", strategy.userId)
    .single();

  const preferences = prefsData
    ? {
      ...DEFAULT_PREFERENCES,
      ...transformPrefsRow(prefsData),
    }
    : DEFAULT_PREFERENCES;

  // Calculate P&L
  const plSnapshot = calculateStrategyPL(
    strategy,
    legs,
    underlyingPrice,
    legPrices,
  );

  // Update legs with current prices and DTE
  for (const leg of legs) {
    const priceData = legPrices.find((p) => p.legId === leg.id);
    const dte = calculateDTE(leg.expiry);

    await supabase
      .from("options_legs")
      .update({
        current_price: priceData?.price ?? null,
        current_value: priceData ? priceData.price * leg.contracts * 100 : null,
        current_delta: priceData?.delta ?? null,
        current_gamma: priceData?.gamma ?? null,
        current_theta: priceData?.theta ?? null,
        current_vega: priceData?.vega ?? null,
        current_rho: priceData?.rho ?? null,
        greeks_updated_at: new Date().toISOString(),
        current_dte: dte,
        is_near_expiration: dte <= 3,
        is_itm: priceData ? isITM(leg, underlyingPrice) : null,
        is_deep_itm: priceData ? isDeepITM(leg, underlyingPrice) : null,
        is_breaching_strike: priceData
          ? isBreaching(leg.strike, underlyingPrice)
          : null,
        updated_at: new Date().toISOString(),
      })
      .eq("id", leg.id);
  }

  // Update strategy P&L and Greeks
  await supabase
    .from("options_strategies")
    .update({
      current_value: plSnapshot.totalCurrentValue,
      total_pl: plSnapshot.totalUnrealizedPL,
      total_pl_pct: plSnapshot.totalUnrealizedPLPct,
      combined_delta: plSnapshot.delta,
      combined_gamma: plSnapshot.gamma,
      combined_theta: plSnapshot.theta,
      combined_vega: plSnapshot.vega,
      combined_rho: plSnapshot.rho,
      greeks_updated_at: new Date().toISOString(),
      min_dte: Math.min(
        ...legs.filter((l) => !l.isClosed).map((l) => calculateDTE(l.expiry)),
      ),
      updated_at: new Date().toISOString(),
    })
    .eq("id", strategy.id);

  // Evaluate alerts
  const context: EvaluationContext = {
    strategy: {
      ...strategy,
      totalPL: plSnapshot.totalUnrealizedPL,
      totalPLPct: plSnapshot.totalUnrealizedPLPct,
      combinedDelta: plSnapshot.delta,
      combinedGamma: plSnapshot.gamma,
      combinedTheta: plSnapshot.theta,
      combinedVega: plSnapshot.vega,
      combinedRho: plSnapshot.rho,
    },
    legs: legs.map((leg) => {
      const snapshot = plSnapshot.legSnapshots.find((s) => s.legId === leg.id);
      return {
        ...leg,
        currentDelta: snapshot?.delta ?? leg.currentDelta,
        currentGamma: snapshot?.gamma ?? leg.currentGamma,
        currentTheta: snapshot?.theta ?? leg.currentTheta,
        currentVega: snapshot?.vega ?? leg.currentVega,
        currentRho: snapshot?.rho ?? leg.currentRho,
      };
    }),
    underlyingPrice,
    forecast,
    preferences,
  };

  const alerts = evaluateStrategy(context);

  // Fetch existing unresolved alerts for deduplication
  const { data: existingAlerts } = await supabase
    .from("options_multi_leg_alerts")
    .select("*")
    .eq("strategy_id", strategy.id)
    .is("resolved_at", null);

  const existingAlertModels = (existingAlerts as AlertRow[] ?? []).map(
    alertRowToModel,
  );

  // Write new alerts (deduplicated)
  let alertsGenerated = 0;
  for (const alert of alerts) {
    if (!isDuplicateAlert(alert, existingAlertModels)) {
      const { error: alertError } = await supabase
        .from("options_multi_leg_alerts")
        .insert({
          strategy_id: strategy.id,
          leg_id: alert.legId ?? null,
          alert_type: alert.alertType,
          severity: alert.severity,
          title: alert.title,
          reason: alert.reason ?? null,
          details: alert.details ?? null,
          suggested_action: alert.suggestedAction ?? null,
          action_required: true,
        });

      if (!alertError) {
        alertsGenerated++;
      }
    }
  }

  // Update last_alert_at if alerts were generated
  if (alertsGenerated > 0) {
    await supabase
      .from("options_strategies")
      .update({ last_alert_at: new Date().toISOString() })
      .eq("id", strategy.id);
  }

  // Record daily metric snapshot (once per day)
  const today = new Date().toISOString().split("T")[0];
  const { data: existingMetric } = await supabase
    .from("options_strategy_metrics")
    .select("id")
    .eq("strategy_id", strategy.id)
    .eq("recorded_at", today)
    .single();

  if (!existingMetric) {
    // Count alerts
    const { count: alertCount } = await supabase
      .from("options_multi_leg_alerts")
      .select("*", { count: "exact", head: true })
      .eq("strategy_id", strategy.id)
      .is("resolved_at", null);

    const { count: criticalCount } = await supabase
      .from("options_multi_leg_alerts")
      .select("*", { count: "exact", head: true })
      .eq("strategy_id", strategy.id)
      .eq("severity", "critical")
      .is("resolved_at", null);

    await supabase.from("options_strategy_metrics").insert({
      strategy_id: strategy.id,
      recorded_at: today,
      underlying_price: underlyingPrice,
      total_value: plSnapshot.totalCurrentValue,
      total_pl: plSnapshot.totalUnrealizedPL,
      total_pl_pct: plSnapshot.totalUnrealizedPLPct,
      delta_snapshot: plSnapshot.delta,
      gamma_snapshot: plSnapshot.gamma,
      theta_snapshot: plSnapshot.theta,
      vega_snapshot: plSnapshot.vega,
      min_dte: context.strategy.minDTE,
      alert_count: alertCount ?? 0,
      critical_alert_count: criticalCount ?? 0,
    });
  }

  return { alertsGenerated };
}

async function fetchCurrentPrices(
  supabase: any,
  strategy: ReturnType<typeof strategyRowToModel>,
  legs: ReturnType<typeof legRowToModel>[],
): Promise<LegPriceData[]> {
  const prices: LegPriceData[] = [];

  for (const leg of legs) {
    if (leg.isClosed) continue;

    // Query options_ranks for the most recent price
    const { data: rankData } = await supabase
      .from("options_ranks")
      .select("mark, delta, gamma, theta, vega, rho")
      .eq("underlying_symbol_id", strategy.underlyingSymbolId)
      .eq("expiry", leg.expiry)
      .eq("strike", leg.strike)
      .eq("side", leg.optionType)
      .order("run_at", { ascending: false })
      .limit(1)
      .single();

    if (rankData) {
      prices.push({
        legId: leg.id,
        price: rankData.mark ?? 0,
        delta: rankData.delta ?? undefined,
        gamma: rankData.gamma ?? undefined,
        theta: rankData.theta ?? undefined,
        vega: rankData.vega ?? undefined,
        rho: rankData.rho ?? undefined,
      });
    }
  }

  return prices;
}

function transformPrefsRow(
  row: any,
): Partial<ReturnType<typeof DEFAULT_PREFERENCES>> {
  return {
    enableExpirationAlerts: row.enable_expiration_alerts,
    expirationAlertDTE: row.expiration_alert_dte,
    enableStrikeAlerts: row.enable_strike_alerts,
    strikeBreachThreshold: row.strike_breach_threshold,
    enableAssignmentAlerts: row.enable_assignment_alerts,
    enableProfitTargetAlerts: row.enable_profit_target_alerts,
    profitTargetPct: row.profit_target_pct,
    enableStopLossAlerts: row.enable_stop_loss_alerts,
    stopLossPct: row.stop_loss_pct,
    enableForecastAlerts: row.enable_forecast_alerts,
    minForecastConfidence: row.min_forecast_confidence,
    enableThetaAlerts: row.enable_theta_alerts,
    minDailyTheta: row.min_daily_theta,
    enableGammaAlerts: row.enable_gamma_alerts,
    gammaAlertThreshold: row.gamma_alert_threshold,
    enableVegaAlerts: row.enable_vega_alerts,
    maxAlertsPerHour: row.max_alerts_per_hour,
    alertBatchWindowMinutes: row.alert_batch_window_minutes,
  };
}

function isITM(
  leg: { optionType: string; strike: number },
  underlyingPrice: number,
): boolean {
  return (
    (leg.optionType === "call" && underlyingPrice > leg.strike) ||
    (leg.optionType === "put" && underlyingPrice < leg.strike)
  );
}

function isDeepITM(
  leg: { optionType: string; strike: number },
  underlyingPrice: number,
): boolean {
  return (
    (leg.optionType === "call" && underlyingPrice > leg.strike + 2) ||
    (leg.optionType === "put" && underlyingPrice < leg.strike - 2)
  );
}

function isBreaching(strike: number, underlyingPrice: number): boolean {
  const threshold = Math.abs(strike) * 0.005;
  return Math.abs(underlyingPrice - strike) <= threshold;
}
