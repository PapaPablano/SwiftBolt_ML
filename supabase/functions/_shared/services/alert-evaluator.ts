// Alert Evaluator Service for Multi-Leg Options Strategies
// Evaluates strategies against market conditions and generates alerts

import {
  type MultiLegStrategy,
  type OptionsLeg,
  type MultiLegAlert,
  type AlertType,
  type AlertSeverity,
  type UserAlertPreferences,
} from "../types/multileg.ts";
import { calculateDTE, isLegITM, isLegDeepITM, isBreachingStrike } from "./pl-calculator.ts";

// ============================================================================
// ALERT GENERATION TYPES
// ============================================================================

export interface AlertInput {
  alertType: AlertType;
  severity: AlertSeverity;
  title: string;
  reason?: string;
  details?: Record<string, unknown>;
  suggestedAction?: string;
  legId?: string;
}

export interface EvaluationContext {
  strategy: MultiLegStrategy;
  legs: OptionsLeg[];
  underlyingPrice: number;
  forecast?: {
    label: "bullish" | "neutral" | "bearish";
    confidence: number;
    horizon: string;
  };
  preferences: UserAlertPreferences;
  currentIV?: number;
  historicalIVMean?: number;
  historicalIVStd?: number;
}

// Default preferences
export const DEFAULT_PREFERENCES: UserAlertPreferences = {
  id: "",
  userId: "",
  enableExpirationAlerts: true,
  expirationAlertDTE: 3,
  enableStrikeAlerts: true,
  strikeBreachThreshold: 0.01,
  enableAssignmentAlerts: true,
  enableProfitTargetAlerts: true,
  profitTargetPct: 0.5,
  enableStopLossAlerts: true,
  stopLossPct: -0.3,
  enableForecastAlerts: true,
  minForecastConfidence: 0.7,
  enableThetaAlerts: true,
  minDailyTheta: 50,
  enableGammaAlerts: true,
  gammaAlertThreshold: 0.15,
  enableVegaAlerts: true,
  maxAlertsPerHour: 10,
  alertBatchWindowMinutes: 15,
  createdAt: "",
  updatedAt: "",
};

// ============================================================================
// MAIN EVALUATION FUNCTION
// ============================================================================

/**
 * Evaluate a strategy and generate all applicable alerts
 */
export function evaluateStrategy(context: EvaluationContext): AlertInput[] {
  const alerts: AlertInput[] = [];
  const prefs = context.preferences;

  // 1. Expiration Soon
  if (prefs.enableExpirationAlerts) {
    alerts.push(...checkExpirationAlerts(context));
  }

  // 2. Strike Breached
  if (prefs.enableStrikeAlerts) {
    alerts.push(...checkStrikeBreachedAlerts(context));
  }

  // 3. Assignment Risk
  if (prefs.enableAssignmentAlerts) {
    alerts.push(...checkAssignmentRiskAlerts(context));
  }

  // 4. Forecast Flip
  if (prefs.enableForecastAlerts && context.forecast) {
    alerts.push(...checkForecastFlipAlerts(context));
  }

  // 5. Profit Target Hit
  if (prefs.enableProfitTargetAlerts) {
    alerts.push(...checkProfitTargetAlerts(context));
  }

  // 6. Stop Loss Hit
  if (prefs.enableStopLossAlerts) {
    alerts.push(...checkStopLossAlerts(context));
  }

  // 7. Volatility Spike
  if (prefs.enableVegaAlerts && context.currentIV !== undefined) {
    alerts.push(...checkVolatilityAlerts(context));
  }

  // 8. Theta Decay Benefit
  if (prefs.enableThetaAlerts) {
    alerts.push(...checkThetaBenefitAlerts(context));
  }

  // 9. Gamma Risk
  if (prefs.enableGammaAlerts) {
    alerts.push(...checkGammaRiskAlerts(context));
  }

  return alerts;
}

// ============================================================================
// INDIVIDUAL ALERT CHECKERS
// ============================================================================

/**
 * Check for expiration alerts (DTE <= threshold)
 */
function checkExpirationAlerts(context: EvaluationContext): AlertInput[] {
  const alerts: AlertInput[] = [];
  const threshold = context.preferences.expirationAlertDTE;

  for (const leg of context.legs) {
    if (leg.isClosed) continue;

    const dte = calculateDTE(leg.expiry);
    if (dte <= threshold) {
      alerts.push({
        alertType: "expiration_soon",
        severity: dte <= 1 ? "critical" : "warning",
        title: `Leg ${leg.legNumber} expires in ${dte} day(s)`,
        reason: `${leg.optionType.toUpperCase()} @ $${leg.strike} expires on ${leg.expiry}`,
        details: {
          legNumber: leg.legNumber,
          optionType: leg.optionType,
          strike: leg.strike,
          expiry: leg.expiry,
          dte,
        },
        suggestedAction: "Close leg or roll to next expiration",
        legId: leg.id,
      });
    }
  }

  return alerts;
}

/**
 * Check for strike breach alerts (underlying near strike)
 */
function checkStrikeBreachedAlerts(context: EvaluationContext): AlertInput[] {
  const alerts: AlertInput[] = [];
  const threshold = context.preferences.strikeBreachThreshold;
  const underlyingPrice = context.underlyingPrice;

  for (const leg of context.legs) {
    if (leg.isClosed) continue;

    const distance = Math.abs(underlyingPrice - leg.strike);
    const distancePct = distance / leg.strike;

    if (distancePct <= threshold) {
      const isITM = isLegITM(leg, underlyingPrice);

      alerts.push({
        alertType: "strike_breached",
        severity: leg.positionType === "short" && isITM ? "critical" : "warning",
        title: `${leg.positionType.toUpperCase()} ${leg.optionType.toUpperCase()} strike $${leg.strike} ${isITM ? "breached" : "approaching"}`,
        reason: `Underlying at $${underlyingPrice.toFixed(2)} is ${(distancePct * 100).toFixed(1)}% from strike`,
        details: {
          legNumber: leg.legNumber,
          strike: leg.strike,
          underlyingPrice,
          distanceToStrike: distance,
          distancePct,
          isITM,
          positionType: leg.positionType,
        },
        suggestedAction: isITM && leg.positionType === "short"
          ? "Monitor for assignment or close position"
          : "Monitor position closely",
        legId: leg.id,
      });
    }
  }

  return alerts;
}

/**
 * Check for assignment risk (short leg deep ITM)
 */
function checkAssignmentRiskAlerts(context: EvaluationContext): AlertInput[] {
  const alerts: AlertInput[] = [];
  const underlyingPrice = context.underlyingPrice;

  for (const leg of context.legs) {
    if (leg.isClosed || leg.positionType !== "short") continue;

    const isDeep = isLegDeepITM(leg, underlyingPrice);
    const dte = calculateDTE(leg.expiry);

    // Assignment risk: deep ITM + near expiration
    if (isDeep && dte <= 3) {
      alerts.push({
        alertType: "assignment_risk",
        severity: "critical",
        title: `Assignment risk: $${leg.strike} short ${leg.optionType}`,
        reason: `Contract is deep ITM ($${underlyingPrice.toFixed(2)} vs $${leg.strike}) with ${dte} DTE`,
        details: {
          legNumber: leg.legNumber,
          strike: leg.strike,
          underlyingPrice,
          isDeepITM: isDeep,
          dte,
          optionType: leg.optionType,
        },
        suggestedAction: "Close position immediately or prepare for assignment",
        legId: leg.id,
      });
    }
  }

  return alerts;
}

/**
 * Check for forecast misalignment
 */
function checkForecastFlipAlerts(context: EvaluationContext): AlertInput[] {
  const alerts: AlertInput[] = [];

  if (!context.forecast || !context.strategy.forecastAlignment) {
    return alerts;
  }

  const strategyThesis = context.strategy.forecastAlignment;
  const forecastLabel = context.forecast.label;
  const confidence = context.forecast.confidence;

  if (confidence < context.preferences.minForecastConfidence) {
    return alerts; // Forecast not confident enough
  }

  // Check alignment
  const isAligned =
    (strategyThesis === "bullish" && (forecastLabel === "bullish" || forecastLabel === "neutral")) ||
    (strategyThesis === "bearish" && (forecastLabel === "bearish" || forecastLabel === "neutral")) ||
    (strategyThesis === "neutral" && forecastLabel === "neutral");

  if (!isAligned) {
    alerts.push({
      alertType: "forecast_flip",
      severity: "critical",
      title: `Forecast misalignment: ${strategyThesis} strategy vs ${forecastLabel} forecast`,
      reason: `Strategy assumes ${strategyThesis} outlook, but forecast shows ${forecastLabel} with ${(confidence * 100).toFixed(0)}% confidence`,
      details: {
        strategyThesis,
        forecastLabel,
        forecastConfidence: confidence,
        forecastHorizon: context.forecast.horizon,
      },
      suggestedAction: "Review thesis or close position if conviction is lost",
    });
  }

  return alerts;
}

/**
 * Check for profit target hit
 */
function checkProfitTargetAlerts(context: EvaluationContext): AlertInput[] {
  const alerts: AlertInput[] = [];
  const targetPct = context.preferences.profitTargetPct;

  const totalPLPct = context.strategy.totalPLPct ?? 0;

  if (totalPLPct >= targetPct) {
    alerts.push({
      alertType: "profit_target_hit",
      severity: "warning",
      title: `Profit target reached: ${(totalPLPct * 100).toFixed(1)}%`,
      reason: `Position has gained ${(totalPLPct * 100).toFixed(1)}% (target ${(targetPct * 100).toFixed(0)}%)`,
      details: {
        totalPL: context.strategy.totalPL,
        totalPLPct,
        targetPct,
      },
      suggestedAction: "Consider taking profits or scaling out",
    });
  }

  return alerts;
}

/**
 * Check for stop loss hit
 */
function checkStopLossAlerts(context: EvaluationContext): AlertInput[] {
  const alerts: AlertInput[] = [];
  const stopPct = context.preferences.stopLossPct;

  const totalPLPct = context.strategy.totalPLPct ?? 0;

  if (totalPLPct <= stopPct) {
    alerts.push({
      alertType: "stop_loss_hit",
      severity: "critical",
      title: `Stop loss triggered: ${(totalPLPct * 100).toFixed(1)}%`,
      reason: `Position has lost ${Math.abs(totalPLPct * 100).toFixed(1)}% (stop ${Math.abs(stopPct * 100).toFixed(0)}%)`,
      details: {
        totalPL: context.strategy.totalPL,
        totalPLPct,
        stopLossPct: stopPct,
      },
      suggestedAction: "Close position per stop loss rule",
    });
  }

  return alerts;
}

/**
 * Check for volatility spike
 */
function checkVolatilityAlerts(context: EvaluationContext): AlertInput[] {
  const alerts: AlertInput[] = [];

  if (
    context.currentIV === undefined ||
    context.historicalIVMean === undefined ||
    context.historicalIVStd === undefined
  ) {
    return alerts;
  }

  const ivZScore = Math.abs(
    (context.currentIV - context.historicalIVMean) /
    (context.historicalIVStd || 0.01)
  );

  if (ivZScore > 2.0) {
    // Calculate vega exposure
    const shortVega = context.legs
      .filter((l) => l.positionType === "short" && !l.isClosed)
      .reduce((sum, l) => sum + (l.currentVega ?? 0), 0);

    const isShortVega = shortVega > 0;

    alerts.push({
      alertType: isShortVega ? "vega_squeeze" : "volatility_spike",
      severity: isShortVega ? "warning" : "info",
      title: `Implied volatility spike (${ivZScore.toFixed(1)} std dev)`,
      reason: `IV is ${(context.currentIV * 100).toFixed(1)}%, historical mean ${(context.historicalIVMean * 100).toFixed(1)}%`,
      details: {
        currentIV: context.currentIV,
        historicalMean: context.historicalIVMean,
        zscore: ivZScore,
        shortVegaExposure: shortVega,
      },
      suggestedAction: isShortVega
        ? "Short vega strategies may profit; monitor for exit"
        : "Review vega exposure; consider hedging",
    });
  }

  return alerts;
}

/**
 * Check for theta decay benefit
 */
function checkThetaBenefitAlerts(context: EvaluationContext): AlertInput[] {
  const alerts: AlertInput[] = [];
  const minTheta = context.preferences.minDailyTheta;

  const dailyTheta = context.strategy.combinedTheta ?? 0;

  // Positive theta means earning from time decay (short positions)
  if (dailyTheta >= minTheta) {
    alerts.push({
      alertType: "theta_decay_benefit",
      severity: "info",
      title: `Strong theta decay benefit: $${dailyTheta.toFixed(2)}/day`,
      reason: `Short premium strategy collecting ~$${dailyTheta.toFixed(2)} per day from time decay`,
      details: {
        dailyTheta,
        totalTheta: context.strategy.combinedTheta,
        minDTE: context.strategy.minDTE,
      },
      suggestedAction: "Monitor strategy; let theta work in your favor",
    });
  }

  return alerts;
}

/**
 * Check for gamma risk
 */
function checkGammaRiskAlerts(context: EvaluationContext): AlertInput[] {
  const alerts: AlertInput[] = [];
  const threshold = context.preferences.gammaAlertThreshold;

  const combinedGamma = context.strategy.combinedGamma ?? 0;

  // Calculate potential delta swing from a 1% underlying move
  const underlyingMove = context.underlyingPrice * 0.01;
  const gammaImpact = Math.abs(combinedGamma * underlyingMove);

  if (gammaImpact > threshold) {
    alerts.push({
      alertType: "gamma_risk",
      severity: "warning",
      title: `High gamma risk: delta could swing ${(gammaImpact * 100).toFixed(0)}%`,
      reason: `Combined gamma of ${combinedGamma.toFixed(4)} suggests significant delta change on underlying moves`,
      details: {
        gamma: combinedGamma,
        underlyingMove,
        deltaImpact: gammaImpact,
        threshold,
      },
      suggestedAction: "Monitor delta closely; rehedge if needed",
    });
  }

  return alerts;
}

// ============================================================================
// ALERT DEDUPLICATION
// ============================================================================

/**
 * Check if a similar alert already exists (for deduplication)
 */
export function isDuplicateAlert(
  newAlert: AlertInput,
  existingAlerts: MultiLegAlert[]
): boolean {
  return existingAlerts.some(
    (existing) =>
      existing.alertType === newAlert.alertType &&
      existing.legId === newAlert.legId &&
      !existing.resolvedAt &&
      isWithinDedupWindow(existing.createdAt)
  );
}

function isWithinDedupWindow(createdAt: string, windowHours = 24): boolean {
  const alertTime = new Date(createdAt).getTime();
  const now = Date.now();
  const windowMs = windowHours * 60 * 60 * 1000;
  return now - alertTime < windowMs;
}
