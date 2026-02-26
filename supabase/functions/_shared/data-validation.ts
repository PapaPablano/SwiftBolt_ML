/**
 * Data Validation Rules Engine
 * Enforces strict separation between historical, intraday, and forecast data layers
 */

export interface WriteValidationResult {
  valid: boolean;
  reason?: string;
}

export interface OHLCBarWrite {
  symbol_id: string;
  timeframe: string;
  ts: Date;
  open?: number;
  high?: number;
  low?: number;
  close?: number;
  volume?: number;
  provider: "polygon" | "tradier" | "ml_forecast" | "alpaca" | "yfinance";
  is_intraday: boolean;
  is_forecast: boolean;
  data_status?: "verified" | "live" | "provisional";
  confidence_score?: number;
  upper_band?: number;
  lower_band?: number;
}

abstract class WriteValidationRule {
  abstract provider: string;
  abstract validate(bar: OHLCBarWrite): WriteValidationResult;
}

/**
 * Polygon Historical Data Rule
 * - Only writes to dates BEFORE today
 * - Never marked as intraday or forecast
 * - Status: "verified"
 */
class PolygonHistoricalRule extends WriteValidationRule {
  provider = "polygon";

  validate(bar: OHLCBarWrite): WriteValidationResult {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const barDate = new Date(bar.ts);
    barDate.setHours(0, 0, 0, 0);

    // Rule: Polygon writes only for dates BEFORE today
    if (barDate >= today) {
      return {
        valid: false,
        reason:
          `Polygon historical cannot write to today or future. Bar: ${barDate.toISOString()}, Today: ${today.toISOString()}`,
      };
    }

    // Rule: Cannot be marked as intraday
    if (bar.is_intraday) {
      return {
        valid: false,
        reason: "Polygon historical data cannot be marked as intraday",
      };
    }

    // Rule: Cannot be marked as forecast
    if (bar.is_forecast) {
      return {
        valid: false,
        reason: "Polygon historical data cannot be marked as forecast",
      };
    }

    // Rule: Should be verified
    if (bar.data_status && bar.data_status !== "verified") {
      return {
        valid: false,
        reason: 'Polygon historical data must have status "verified"',
      };
    }

    return { valid: true };
  }
}

/**
 * Tradier Intraday Data Rule
 * - Only writes to TODAY
 * - Must be marked as intraday
 * - Locks 5 minutes after market close (4:05 PM ET)
 */
class TradierIntradayRule extends WriteValidationRule {
  provider = "tradier";

  validate(bar: OHLCBarWrite): WriteValidationResult {
    const now = new Date();
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const barDate = new Date(bar.ts);
    barDate.setHours(0, 0, 0, 0);

    // Rule: Tradier writes only to TODAY
    if (barDate.getTime() !== today.getTime()) {
      return {
        valid: false,
        reason:
          `Tradier intraday must be for today only. Bar: ${barDate.toISOString()}, Today: ${today.toISOString()}`,
      };
    }

    // Rule: Must be marked as intraday
    if (!bar.is_intraday) {
      return {
        valid: false,
        reason: "Tradier data must be marked as intraday",
      };
    }

    // Rule: Cannot be marked as forecast
    if (bar.is_forecast) {
      return {
        valid: false,
        reason: "Tradier intraday data cannot be marked as forecast",
      };
    }

    // Rule: Lock writes 5 min after market close (4:05 PM ET)
    const lockTime = this.getMarketCloseLockTime();
    if (now > lockTime) {
      return {
        valid: false,
        reason:
          `Today's data locked after 4:05 PM ET. Current time: ${now.toISOString()}, Lock time: ${lockTime.toISOString()}`,
      };
    }

    // Rule: Status should be "live" during market hours or "verified" after close
    const marketClose = this.getMarketCloseTime();
    const expectedStatus = now > marketClose ? "verified" : "live";
    if (bar.data_status && bar.data_status !== expectedStatus) {
      console.warn(
        `Tradier data status mismatch. Expected: ${expectedStatus}, Got: ${bar.data_status}`,
      );
    }

    return { valid: true };
  }

  private getMarketCloseTime(): Date {
    const now = new Date();
    // Convert to ET (approximate - in production use proper timezone library)
    const etOffset = -5; // ET is UTC-5 (or UTC-4 during DST)
    const marketClose = new Date(now);
    marketClose.setHours(16 + etOffset, 0, 0, 0); // 4:00 PM ET
    return marketClose;
  }

  private getMarketCloseLockTime(): Date {
    const marketClose = this.getMarketCloseTime();
    return new Date(marketClose.getTime() + 5 * 60 * 1000); // +5 minutes
  }
}

/**
 * ML Forecast Data Rule
 * - Only writes to FUTURE dates (t+1 to t+10)
 * - Must be marked as forecast
 * - Must include confidence bands
 */
class MLForecastRule extends WriteValidationRule {
  provider = "ml_forecast";

  validate(bar: OHLCBarWrite): WriteValidationResult {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const barDate = new Date(bar.ts);
    barDate.setHours(0, 0, 0, 0);

    // Rule: ML writes only for future dates
    if (barDate <= today) {
      return {
        valid: false,
        reason:
          `ML forecasts must be for future dates only. Bar: ${barDate.toISOString()}, Today: ${today.toISOString()}`,
      };
    }

    // Rule: Maximum 10 days ahead
    const maxFuture = new Date(today.getTime() + 10 * 24 * 60 * 60 * 1000);
    if (barDate > maxFuture) {
      return {
        valid: false,
        reason:
          `Forecasts cannot exceed 10 days ahead. Bar: ${barDate.toISOString()}, Max: ${maxFuture.toISOString()}`,
      };
    }

    // Rule: Must be marked as forecast
    if (!bar.is_forecast) {
      return {
        valid: false,
        reason: "ML forecast data must be marked as forecast",
      };
    }

    // Rule: Cannot be marked as intraday
    if (bar.is_intraday) {
      return {
        valid: false,
        reason: "ML forecast data cannot be marked as intraday",
      };
    }

    // Rule: Must include confidence bands
    if (bar.upper_band === undefined || bar.lower_band === undefined) {
      return {
        valid: false,
        reason: "ML forecasts must include upper_band and lower_band",
      };
    }

    // Rule: Confidence score should be between 0 and 1
    if (bar.confidence_score !== undefined) {
      if (bar.confidence_score < 0 || bar.confidence_score > 1) {
        return {
          valid: false,
          reason:
            `Confidence score must be between 0 and 1. Got: ${bar.confidence_score}`,
        };
      }
    }

    // Rule: Status should be "provisional"
    if (bar.data_status && bar.data_status !== "provisional") {
      console.warn(
        `ML forecast status should be "provisional". Got: ${bar.data_status}`,
      );
    }

    return { valid: true };
  }
}

/**
 * Alpaca Historical Data Rule
 * - Can write historical data (before today) or intraday (today)
 * - Status: "verified"
 */
class AlpacaHistoricalRule extends WriteValidationRule {
  provider = "alpaca";

  validate(bar: OHLCBarWrite): WriteValidationResult {
    // Alpaca can write both historical and intraday data
    // No strict date restrictions

    // Rule: Cannot be marked as forecast
    if (bar.is_forecast) {
      return {
        valid: false,
        reason: "Alpaca data cannot be marked as forecast",
      };
    }

    // Rule: Should be verified
    if (bar.data_status && bar.data_status !== "verified") {
      return {
        valid: false,
        reason: 'Alpaca data must have status "verified"',
      };
    }

    return { valid: true };
  }
}

/**
 * YFinance Historical Data Rule
 * - Only writes to dates BEFORE today
 * - Never marked as intraday or forecast
 * - Status: "verified"
 */
class YFinanceHistoricalRule extends WriteValidationRule {
  provider = "yfinance";

  validate(bar: OHLCBarWrite): WriteValidationResult {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const barDate = new Date(bar.ts);
    barDate.setHours(0, 0, 0, 0);

    // Rule: YFinance writes only for dates BEFORE today
    if (barDate >= today) {
      return {
        valid: false,
        reason:
          `YFinance historical cannot write to today or future. Bar: ${barDate.toISOString()}, Today: ${today.toISOString()}`,
      };
    }

    // Rule: Cannot be marked as intraday
    if (bar.is_intraday) {
      return {
        valid: false,
        reason: "YFinance historical data cannot be marked as intraday",
      };
    }

    // Rule: Cannot be marked as forecast
    if (bar.is_forecast) {
      return {
        valid: false,
        reason: "YFinance historical data cannot be marked as forecast",
      };
    }

    // Rule: Should be verified
    if (bar.data_status && bar.data_status !== "verified") {
      return {
        valid: false,
        reason: 'YFinance historical data must have status "verified"',
      };
    }

    return { valid: true };
  }
}

/**
 * Main validation orchestrator
 */
export class DataValidator {
  private rules: Map<string, WriteValidationRule>;

  constructor() {
    this.rules = new Map([
      ["polygon", new PolygonHistoricalRule()],
      ["tradier", new TradierIntradayRule()],
      ["ml_forecast", new MLForecastRule()],
      ["alpaca", new AlpacaHistoricalRule()],
      ["yfinance", new YFinanceHistoricalRule()],
    ]);
  }

  /**
   * Validate a single bar write operation
   */
  validateWrite(bar: OHLCBarWrite): WriteValidationResult {
    const rule = this.rules.get(bar.provider);

    if (!rule) {
      return {
        valid: false,
        reason:
          `Unknown provider: ${bar.provider}. Must be one of: polygon, tradier, ml_forecast, alpaca, yfinance`,
      };
    }

    return rule.validate(bar);
  }

  /**
   * Validate multiple bar writes (batch operation)
   */
  validateBatch(bars: OHLCBarWrite[]): {
    valid: boolean;
    errors: Array<{ index: number; bar: OHLCBarWrite; reason: string }>;
  } {
    const errors: Array<{ index: number; bar: OHLCBarWrite; reason: string }> =
      [];

    bars.forEach((bar, index) => {
      const result = this.validateWrite(bar);
      if (!result.valid) {
        errors.push({
          index,
          bar,
          reason: result.reason || "Unknown validation error",
        });
      }
    });

    return {
      valid: errors.length === 0,
      errors,
    };
  }

  /**
   * Filter valid bars from a batch, logging invalid ones
   */
  filterValidBars(bars: OHLCBarWrite[]): OHLCBarWrite[] {
    const validBars: OHLCBarWrite[] = [];

    bars.forEach((bar, index) => {
      const result = this.validateWrite(bar);
      if (result.valid) {
        validBars.push(bar);
      } else {
        console.warn(
          `[DataValidator] Filtered invalid bar at index ${index}: ${result.reason}`,
          { bar },
        );
      }
    });

    return validBars;
  }
}

// Export singleton instance
export const dataValidator = new DataValidator();

/**
 * Helper: Prepare bar for database insert with validation
 */
export function prepareBarForInsert(
  bar: OHLCBarWrite,
  validate = true,
): OHLCBarWrite | null {
  if (validate) {
    const result = dataValidator.validateWrite(bar);
    if (!result.valid) {
      console.error(`[DataValidator] Invalid bar: ${result.reason}`, { bar });
      return null;
    }
  }

  // Ensure timestamps are properly formatted
  return {
    ...bar,
    ts: new Date(bar.ts),
    fetched_at: new Date(),
  } as OHLCBarWrite;
}
