/**
 * Production-grade validators for paper trading
 * Prevents invalid states: null bars, negative prices, position out-of-bounds
 */

export interface Bar {
  time: number | string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface ValidationResult<T = void> {
  valid: boolean;
  errors: string[];
  data?: T;
}

// ============================================================================
// MARKET DATA VALIDATORS
// ============================================================================

/**
 * Validates OHLCV bar data before using in strategy evaluation
 * Checks for: null values, negative prices, data integrity
 */
export function validateMarketData(
  bars: Bar[] | null | undefined
): ValidationResult {
  const errors: string[] = [];

  // Check if bars exist
  if (!bars || !Array.isArray(bars)) {
    return { valid: false, errors: ['No market data provided'] };
  }

  if (bars.length === 0) {
    return { valid: false, errors: ['Market data is empty'] };
  }

  if (bars.length < 2) {
    return { valid: false, errors: ['Need at least 2 bars for indicator calculation'] };
  }

  // Validate each bar
  for (let i = 0; i < bars.length; i++) {
    const bar = bars[i];
    const barIndex = i + 1;

    // Check required fields
    if (!bar || typeof bar !== 'object') {
      errors.push(`Bar ${barIndex}: Invalid structure`);
      continue;
    }

    // Check OHLCV values
    const { open, high, low, close, volume } = bar;

    if (open === null || open === undefined || open === 0) {
      errors.push(`Bar ${barIndex}: Open price is null or zero`);
    } else if (open < 0) {
      errors.push(`Bar ${barIndex}: Open price is negative (${open})`);
    }

    if (high === null || high === undefined || high === 0) {
      errors.push(`Bar ${barIndex}: High price is null or zero`);
    } else if (high < 0) {
      errors.push(`Bar ${barIndex}: High price is negative (${high})`);
    }

    if (low === null || low === undefined || low === 0) {
      errors.push(`Bar ${barIndex}: Low price is null or zero`);
    } else if (low < 0) {
      errors.push(`Bar ${barIndex}: Low price is negative (${low})`);
    }

    if (close === null || close === undefined || close === 0) {
      errors.push(`Bar ${barIndex}: Close price is null or zero`);
    } else if (close < 0) {
      errors.push(`Bar ${barIndex}: Close price is negative (${close})`);
    }

    if (volume === null || volume === undefined) {
      errors.push(`Bar ${barIndex}: Volume is null`);
    } else if (volume < 0) {
      errors.push(`Bar ${barIndex}: Volume is negative (${volume})`);
    }

    // Check logical consistency: low <= close <= high <= high
    if (low > high) {
      errors.push(`Bar ${barIndex}: Low (${low}) > High (${high})`);
    }

    if (close < low || close > high) {
      errors.push(`Bar ${barIndex}: Close (${close}) outside [Low=${low}, High=${high}]`);
    }

    // Check for extreme gaps (>10% move from previous close)
    if (i > 0) {
      const prevClose = bars[i - 1].close;
      const gapPct = Math.abs((bar.open - prevClose) / prevClose) * 100;

      if (gapPct > 15) {
        errors.push(
          `Bar ${barIndex}: Gap detected (${gapPct.toFixed(1)}%) - may trigger forced closes`
        );
      }
    }
  }

  return {
    valid: errors.length === 0,
    errors,
  };
}

// ============================================================================
// POSITION CONSTRAINT VALIDATORS
// ============================================================================

export interface PositionConstraints {
  entryPrice: number;
  quantity: number;
  slPct: number;
  tpPct: number;
  direction: 'long' | 'short';
}

/**
 * Validates position constraints before entering a trade
 * Ensures entry price > 0, qty bounds, SL < entry < TP
 */
export function validatePositionConstraints(
  constraints: PositionConstraints
): ValidationResult {
  const errors: string[] = [];
  const {
    entryPrice,
    quantity,
    slPct,
    tpPct,
    direction,
  } = constraints;

  // Validate entry price
  if (!entryPrice || entryPrice <= 0) {
    errors.push(`Entry price must be positive (got: ${entryPrice})`);
  }

  if (!Number.isFinite(entryPrice)) {
    errors.push(`Entry price is not a valid number (got: ${entryPrice})`);
  }

  // Validate quantity bounds [1, 1000]
  if (!Number.isInteger(quantity) || quantity < 1 || quantity > 1000) {
    errors.push(
      `Quantity out of bounds [1, 1000] (got: ${quantity}). ` +
      `Common mistake: Don't set qty > 1000 (causes P&L overflow)`
    );
  }

  // Validate SL percentage [0.1%, 20%]
  if (slPct < 0.1 || slPct > 20) {
    errors.push(
      `Stop loss must be 0.1%-20% (got: ${slPct}%). ` +
      `Typical: 2%. Too small = whipsawed, Too large = unlimited risk`
    );
  }

  // Validate TP percentage [0.1%, 100%]
  if (tpPct < 0.1 || tpPct > 100) {
    errors.push(
      `Take profit must be 0.1%-100% (got: ${tpPct}%). ` +
      `Typical: 5-10%. Too large = unrealistic targets`
    );
  }

  // Calculate actual SL and TP prices based on direction
  let slPrice: number;
  let tpPrice: number;

  if (direction === 'long') {
    slPrice = entryPrice * (1 - slPct / 100);
    tpPrice = entryPrice * (1 + tpPct / 100);
  } else {
    // short: SL is above entry, TP is below entry
    slPrice = entryPrice * (1 + slPct / 100);
    tpPrice = entryPrice * (1 - tpPct / 100);
  }

  // Validate SL < entry < TP (for longs) or entry < SL, TP < entry (for shorts)
  if (direction === 'long') {
    if (slPrice >= entryPrice) {
      errors.push(`Long SL price (${slPrice.toFixed(2)}) >= entry (${entryPrice.toFixed(2)})`);
    }
    if (tpPrice <= entryPrice) {
      errors.push(`Long TP price (${tpPrice.toFixed(2)}) <= entry (${entryPrice.toFixed(2)})`);
    }
  } else {
    if (slPrice <= entryPrice) {
      errors.push(`Short SL price (${slPrice.toFixed(2)}) <= entry (${entryPrice.toFixed(2)})`);
    }
    if (tpPrice >= entryPrice) {
      errors.push(`Short TP price (${tpPrice.toFixed(2)}) >= entry (${entryPrice.toFixed(2)})`);
    }
  }

  return {
    valid: errors.length === 0,
    errors,
  };
}

// ============================================================================
// SLIPPAGE VALIDATORS
// ============================================================================

/**
 * Validates slippage percentage is within realistic bounds
 * Prevents inflation: 500% slippage doesn't exist in markets
 */
export function validateSlippage(slippagePct: number): ValidationResult {
  const errors: string[] = [];

  if (!Number.isFinite(slippagePct)) {
    return {
      valid: false,
      errors: [`Slippage must be a valid number (got: ${slippagePct})`],
    };
  }

  if (slippagePct < 0.01) {
    errors.push(
      `Slippage too small: ${slippagePct}%. Minimum realistic: 0.01% ` +
      `(liquid assets like SPY have 0.01-0.1% spreads)`
    );
  }

  if (slippagePct > 5.0) {
    errors.push(
      `Slippage too large: ${slippagePct}%. Maximum allowed: 5%. ` +
      `Prevent P&L inflation: 5% is extreme even for illiquid stocks`
    );
  }

  // Warn about unrealistic values (but allow)
  if (slippagePct < 0.05) {
    console.warn(
      `[BACKTEST WARNING] Slippage ${slippagePct}% is very tight. ` +
      `Markets don't have spreads this narrow. Consider 0.1-0.2% for equities`
    );
  }

  if (slippagePct > 2.0) {
    console.warn(
      `[BACKTEST WARNING] Slippage ${slippagePct}% is very wide. ` +
      `Most equities have spreads <1%. Only junk stocks/microcaps >2%`
    );
  }

  return {
    valid: errors.length === 0,
    errors,
  };
}

// ============================================================================
// SL/TP BOUNDS VALIDATORS
// ============================================================================

export interface SLTPBounds {
  slPct: number;
  tpPct: number;
}

/**
 * Validates stop loss and take profit percentages
 */
export function validateSLTPBounds(bounds: SLTPBounds): ValidationResult {
  const errors: string[] = [];
  const { slPct, tpPct } = bounds;

  // SL bounds: 0.1% to 20%
  if (slPct < 0.1) {
    errors.push(`SL too small: ${slPct}%. Minimum: 0.1% (prevents whipsaws)`);
  }
  if (slPct > 20) {
    errors.push(`SL too large: ${slPct}%. Maximum: 20% (prevents unlimited risk)`);
  }

  // TP bounds: 0.1% to 100%
  if (tpPct < 0.1) {
    errors.push(`TP too small: ${tpPct}%. Minimum: 0.1% (unrealistic targets)`);
  }
  if (tpPct > 100) {
    errors.push(`TP too large: ${tpPct}%. Maximum: 100% (unrealistic targets)`);
  }

  // Cross-check: TP should be > SL
  if (tpPct <= slPct) {
    errors.push(
      `TP (${tpPct}%) must be > SL (${slPct}%) ` +
      `(profit target should be larger than loss limit)`
    );
  }

  return {
    valid: errors.length === 0,
    errors,
  };
}

// ============================================================================
// OPERATOR VALIDATORS
// ============================================================================

export type ConditionOperator =
  | '>'
  | '<'
  | '>='
  | '<='
  | '=='
  | 'cross_up'
  | 'cross_down'
  | 'touches'
  | 'within_range';

/**
 * Validates condition operator and required fields
 * Discriminated union: cross_up/cross_down require 'crossWith' field
 */
export function validateOperator(
  operator: ConditionOperator,
  value: number | string,
  crossWith?: string
): ValidationResult {
  const errors: string[] = [];

  const validOperators: ConditionOperator[] = [
    '>',
    '<',
    '>=',
    '<=',
    '==',
    'cross_up',
    'cross_down',
    'touches',
    'within_range',
  ];

  if (!validOperators.includes(operator)) {
    errors.push(`Invalid operator: ${operator}`);
    return { valid: false, errors };
  }

  // Discriminated union: cross_up/cross_down require crossWith
  if ((operator === 'cross_up' || operator === 'cross_down') && !crossWith) {
    errors.push(
      `Operator '${operator}' requires 'crossWith' field (e.g., 'cross_up' with MA50)`
    );
  }

  // Validate value
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) {
      errors.push(`Value must be a valid number (got: ${value})`);
    }
  }

  return {
    valid: errors.length === 0,
    errors,
  };
}

// ============================================================================
// BATCH VALIDATORS
// ============================================================================

/**
 * Comprehensive validation before executing paper trading
 */
export function validateBeforeExecution(
  bars: Bar[],
  positionConstraints: PositionConstraints,
  slippage: number
): ValidationResult {
  const errors: string[] = [];

  // Validate market data
  const marketDataResult = validateMarketData(bars);
  if (!marketDataResult.valid) {
    errors.push(...marketDataResult.errors);
  }

  // Validate position constraints
  const positionResult = validatePositionConstraints(positionConstraints);
  if (!positionResult.valid) {
    errors.push(...positionResult.errors);
  }

  // Validate slippage
  const slippageResult = validateSlippage(slippage);
  if (!slippageResult.valid) {
    errors.push(...slippageResult.errors);
  }

  return {
    valid: errors.length === 0,
    errors,
  };
}
