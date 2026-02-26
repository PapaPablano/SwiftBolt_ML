// Strategy Validator Service for Multi-Leg Options
// Validates strategy creation and update requests

import {
  type CreateLegInput,
  type CreateStrategyRequest,
  getExpectedLegCount,
  type OptionsLeg,
  type StrategyType,
} from "../types/multileg.ts";

// ============================================================================
// VALIDATION RESULT TYPES
// ============================================================================

export interface ValidationResult {
  isValid: boolean;
  errors: ValidationError[];
  warnings: ValidationWarning[];
}

export interface ValidationError {
  field: string;
  message: string;
  code: string;
}

export interface ValidationWarning {
  field: string;
  message: string;
  code: string;
}

// ============================================================================
// STRATEGY VALIDATION
// ============================================================================

/**
 * Validate a strategy creation request
 */
export function validateStrategyCreation(
  request: CreateStrategyRequest,
): ValidationResult {
  const errors: ValidationError[] = [];
  const warnings: ValidationWarning[] = [];

  // Required fields
  if (!request.name || request.name.trim().length === 0) {
    errors.push({
      field: "name",
      message: "Strategy name is required",
      code: "REQUIRED_FIELD",
    });
  }

  if (!request.strategyType) {
    errors.push({
      field: "strategyType",
      message: "Strategy type is required",
      code: "REQUIRED_FIELD",
    });
  }

  if (!request.underlyingSymbolId) {
    errors.push({
      field: "underlyingSymbolId",
      message: "Underlying symbol is required",
      code: "REQUIRED_FIELD",
    });
  }

  if (!request.underlyingTicker) {
    errors.push({
      field: "underlyingTicker",
      message: "Underlying ticker is required",
      code: "REQUIRED_FIELD",
    });
  }

  if (!request.legs || request.legs.length === 0) {
    errors.push({
      field: "legs",
      message: "At least one leg is required",
      code: "REQUIRED_FIELD",
    });
    return { isValid: false, errors, warnings };
  }

  // Leg count validation
  const expectedLegCount = getExpectedLegCount(request.strategyType);
  if (expectedLegCount !== null && request.legs.length !== expectedLegCount) {
    errors.push({
      field: "legs",
      message:
        `Strategy type ${request.strategyType} requires ${expectedLegCount} legs, got ${request.legs.length}`,
      code: "INVALID_LEG_COUNT",
    });
  }

  // Validate individual legs
  const legErrors = validateLegs(request.legs, request.strategyType);
  errors.push(...legErrors);

  // Strategy-specific validation
  const strategyErrors = validateStrategyStructure(request);
  errors.push(...strategyErrors);

  // Warnings
  const strategyWarnings = generateWarnings(request);
  warnings.push(...strategyWarnings);

  return {
    isValid: errors.length === 0,
    errors,
    warnings,
  };
}

/**
 * Validate individual legs
 */
function validateLegs(
  legs: CreateLegInput[],
  strategyType: StrategyType,
): ValidationError[] {
  const errors: ValidationError[] = [];

  for (let i = 0; i < legs.length; i++) {
    const leg = legs[i];
    const prefix = `legs[${i}]`;

    // Required fields
    if (leg.legNumber === undefined || leg.legNumber < 1) {
      errors.push({
        field: `${prefix}.legNumber`,
        message: "Leg number must be a positive integer",
        code: "INVALID_LEG_NUMBER",
      });
    }

    if (!leg.positionType || !["long", "short"].includes(leg.positionType)) {
      errors.push({
        field: `${prefix}.positionType`,
        message: 'Position type must be "long" or "short"',
        code: "INVALID_POSITION_TYPE",
      });
    }

    if (!leg.optionType || !["call", "put"].includes(leg.optionType)) {
      errors.push({
        field: `${prefix}.optionType`,
        message: 'Option type must be "call" or "put"',
        code: "INVALID_OPTION_TYPE",
      });
    }

    if (!leg.strike || leg.strike <= 0) {
      errors.push({
        field: `${prefix}.strike`,
        message: "Strike must be a positive number",
        code: "INVALID_STRIKE",
      });
    }

    if (!leg.expiry) {
      errors.push({
        field: `${prefix}.expiry`,
        message: "Expiry date is required",
        code: "REQUIRED_FIELD",
      });
    } else {
      // Validate expiry is in the future
      const expiryDate = new Date(leg.expiry);
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      if (expiryDate < today) {
        errors.push({
          field: `${prefix}.expiry`,
          message: "Expiry date must be in the future",
          code: "EXPIRED_CONTRACT",
        });
      }
    }

    if (!leg.entryPrice || leg.entryPrice <= 0) {
      errors.push({
        field: `${prefix}.entryPrice`,
        message: "Entry price must be a positive number",
        code: "INVALID_ENTRY_PRICE",
      });
    }

    if (
      !leg.contracts || leg.contracts < 1 || !Number.isInteger(leg.contracts)
    ) {
      errors.push({
        field: `${prefix}.contracts`,
        message: "Contracts must be a positive integer",
        code: "INVALID_CONTRACTS",
      });
    }
  }

  // Check for duplicate leg numbers
  const legNumbers = legs.map((l) => l.legNumber);
  const uniqueNumbers = new Set(legNumbers);
  if (legNumbers.length !== uniqueNumbers.size) {
    errors.push({
      field: "legs",
      message: "Duplicate leg numbers found",
      code: "DUPLICATE_LEG_NUMBERS",
    });
  }

  return errors;
}

/**
 * Validate strategy-specific structure
 */
function validateStrategyStructure(
  request: CreateStrategyRequest,
): ValidationError[] {
  const errors: ValidationError[] = [];
  const legs = request.legs;

  switch (request.strategyType) {
    // Single-leg strategies
    case "long_call":
      errors.push(...validateSingleLeg(legs, "long", "call"));
      break;
    case "long_put":
      errors.push(...validateSingleLeg(legs, "long", "put"));
      break;
    case "short_call":
      errors.push(...validateSingleLeg(legs, "short", "call"));
      break;
    case "short_put":
      errors.push(...validateSingleLeg(legs, "short", "put"));
      break;
    case "covered_call":
      errors.push(...validateSingleLeg(legs, "short", "call"));
      break;
    case "cash_secured_put":
      errors.push(...validateSingleLeg(legs, "short", "put"));
      break;
    // Two-leg strategies
    case "bull_call_spread":
      errors.push(...validateBullCallSpread(legs));
      break;
    case "bear_call_spread":
      errors.push(...validateBearCallSpread(legs));
      break;
    case "bull_put_spread":
      errors.push(...validateBullPutSpread(legs));
      break;
    case "bear_put_spread":
      errors.push(...validateBearPutSpread(legs));
      break;
    case "long_straddle":
    case "short_straddle":
      errors.push(...validateStraddle(legs, request.strategyType));
      break;
    case "long_strangle":
    case "short_strangle":
      errors.push(...validateStrangle(legs, request.strategyType));
      break;
    case "iron_condor":
      errors.push(...validateIronCondor(legs));
      break;
    case "iron_butterfly":
      errors.push(...validateIronButterfly(legs));
      break;
    case "calendar_spread":
    case "diagonal_spread":
      errors.push(...validateCalendarOrDiagonal(legs, request.strategyType));
      break;
      // Custom and other types don't have specific validation
  }

  return errors;
}

// ============================================================================
// STRATEGY-SPECIFIC VALIDATORS
// ============================================================================

function validateSingleLeg(
  legs: CreateLegInput[],
  expectedPosition: "long" | "short",
  expectedOptionType: "call" | "put",
): ValidationError[] {
  const errors: ValidationError[] = [];

  if (legs.length !== 1) {
    errors.push({
      field: "legs",
      message:
        `Single-option strategy requires exactly 1 leg, got ${legs.length}`,
      code: "INVALID_LEG_COUNT",
    });
    return errors;
  }

  const leg = legs[0];

  if (leg.positionType !== expectedPosition) {
    errors.push({
      field: "legs[0].positionType",
      message: `Expected ${expectedPosition} position for this strategy type`,
      code: "INVALID_POSITION_TYPE",
    });
  }

  if (leg.optionType !== expectedOptionType) {
    errors.push({
      field: "legs[0].optionType",
      message: `Expected ${expectedOptionType} option for this strategy type`,
      code: "INVALID_OPTION_TYPE",
    });
  }

  return errors;
}

function validateBullCallSpread(legs: CreateLegInput[]): ValidationError[] {
  const errors: ValidationError[] = [];

  const longLeg = legs.find((l) => l.positionType === "long");
  const shortLeg = legs.find((l) => l.positionType === "short");

  if (!longLeg || !shortLeg) {
    errors.push({
      field: "legs",
      message: "Bull call spread requires one long and one short leg",
      code: "INVALID_SPREAD_STRUCTURE",
    });
    return errors;
  }

  // Both must be calls
  if (longLeg.optionType !== "call" || shortLeg.optionType !== "call") {
    errors.push({
      field: "legs",
      message: "Bull call spread requires both legs to be calls",
      code: "INVALID_OPTION_TYPE",
    });
  }

  // Long strike should be lower
  if (longLeg.strike >= shortLeg.strike) {
    errors.push({
      field: "legs",
      message: "Bull call spread: long strike must be lower than short strike",
      code: "INVALID_STRIKE_ORDER",
    });
  }

  // Same expiry
  if (longLeg.expiry !== shortLeg.expiry) {
    errors.push({
      field: "legs",
      message: "Bull call spread: both legs must have the same expiry",
      code: "EXPIRY_MISMATCH",
    });
  }

  return errors;
}

function validateBearCallSpread(legs: CreateLegInput[]): ValidationError[] {
  const errors: ValidationError[] = [];

  const longLeg = legs.find((l) => l.positionType === "long");
  const shortLeg = legs.find((l) => l.positionType === "short");

  if (!longLeg || !shortLeg) {
    errors.push({
      field: "legs",
      message: "Bear call spread requires one long and one short leg",
      code: "INVALID_SPREAD_STRUCTURE",
    });
    return errors;
  }

  // Both must be calls
  if (longLeg.optionType !== "call" || shortLeg.optionType !== "call") {
    errors.push({
      field: "legs",
      message: "Bear call spread requires both legs to be calls",
      code: "INVALID_OPTION_TYPE",
    });
  }

  // Short strike should be lower
  if (shortLeg.strike >= longLeg.strike) {
    errors.push({
      field: "legs",
      message: "Bear call spread: short strike must be lower than long strike",
      code: "INVALID_STRIKE_ORDER",
    });
  }

  // Same expiry
  if (longLeg.expiry !== shortLeg.expiry) {
    errors.push({
      field: "legs",
      message: "Bear call spread: both legs must have the same expiry",
      code: "EXPIRY_MISMATCH",
    });
  }

  return errors;
}

function validateBullPutSpread(legs: CreateLegInput[]): ValidationError[] {
  const errors: ValidationError[] = [];

  const longLeg = legs.find((l) => l.positionType === "long");
  const shortLeg = legs.find((l) => l.positionType === "short");

  if (!longLeg || !shortLeg) {
    errors.push({
      field: "legs",
      message: "Bull put spread requires one long and one short leg",
      code: "INVALID_SPREAD_STRUCTURE",
    });
    return errors;
  }

  // Both must be puts
  if (longLeg.optionType !== "put" || shortLeg.optionType !== "put") {
    errors.push({
      field: "legs",
      message: "Bull put spread requires both legs to be puts",
      code: "INVALID_OPTION_TYPE",
    });
  }

  // Short strike should be higher (sell higher put, buy lower put)
  if (shortLeg.strike <= longLeg.strike) {
    errors.push({
      field: "legs",
      message: "Bull put spread: short strike must be higher than long strike",
      code: "INVALID_STRIKE_ORDER",
    });
  }

  // Same expiry
  if (longLeg.expiry !== shortLeg.expiry) {
    errors.push({
      field: "legs",
      message: "Bull put spread: both legs must have the same expiry",
      code: "EXPIRY_MISMATCH",
    });
  }

  return errors;
}

function validateBearPutSpread(legs: CreateLegInput[]): ValidationError[] {
  const errors: ValidationError[] = [];

  const longLeg = legs.find((l) => l.positionType === "long");
  const shortLeg = legs.find((l) => l.positionType === "short");

  if (!longLeg || !shortLeg) {
    errors.push({
      field: "legs",
      message: "Bear put spread requires one long and one short leg",
      code: "INVALID_SPREAD_STRUCTURE",
    });
    return errors;
  }

  // Both must be puts
  if (longLeg.optionType !== "put" || shortLeg.optionType !== "put") {
    errors.push({
      field: "legs",
      message: "Bear put spread requires both legs to be puts",
      code: "INVALID_OPTION_TYPE",
    });
  }

  // Long strike should be higher (buy higher put)
  if (longLeg.strike <= shortLeg.strike) {
    errors.push({
      field: "legs",
      message: "Bear put spread: long strike must be higher than short strike",
      code: "INVALID_STRIKE_ORDER",
    });
  }

  // Same expiry
  if (longLeg.expiry !== shortLeg.expiry) {
    errors.push({
      field: "legs",
      message: "Bear put spread: both legs must have the same expiry",
      code: "EXPIRY_MISMATCH",
    });
  }

  return errors;
}

function validateStraddle(
  legs: CreateLegInput[],
  strategyType: "long_straddle" | "short_straddle",
): ValidationError[] {
  const errors: ValidationError[] = [];

  const callLeg = legs.find((l) => l.optionType === "call");
  const putLeg = legs.find((l) => l.optionType === "put");

  if (!callLeg || !putLeg) {
    errors.push({
      field: "legs",
      message: "Straddle requires one call and one put",
      code: "INVALID_STRADDLE_STRUCTURE",
    });
    return errors;
  }

  // Check position types match strategy
  const expectedPosition = strategyType === "long_straddle" ? "long" : "short";
  if (
    callLeg.positionType !== expectedPosition ||
    putLeg.positionType !== expectedPosition
  ) {
    errors.push({
      field: "legs",
      message: `${strategyType} requires both legs to be ${expectedPosition}`,
      code: "INVALID_POSITION_TYPE",
    });
  }

  // Same strike
  if (callLeg.strike !== putLeg.strike) {
    errors.push({
      field: "legs",
      message: "Straddle requires both legs to have the same strike",
      code: "STRIKE_MISMATCH",
    });
  }

  // Same expiry
  if (callLeg.expiry !== putLeg.expiry) {
    errors.push({
      field: "legs",
      message: "Straddle requires both legs to have the same expiry",
      code: "EXPIRY_MISMATCH",
    });
  }

  return errors;
}

function validateStrangle(
  legs: CreateLegInput[],
  strategyType: "long_strangle" | "short_strangle",
): ValidationError[] {
  const errors: ValidationError[] = [];

  const callLeg = legs.find((l) => l.optionType === "call");
  const putLeg = legs.find((l) => l.optionType === "put");

  if (!callLeg || !putLeg) {
    errors.push({
      field: "legs",
      message: "Strangle requires one call and one put",
      code: "INVALID_STRANGLE_STRUCTURE",
    });
    return errors;
  }

  // Check position types match strategy
  const expectedPosition = strategyType === "long_strangle" ? "long" : "short";
  if (
    callLeg.positionType !== expectedPosition ||
    putLeg.positionType !== expectedPosition
  ) {
    errors.push({
      field: "legs",
      message: `${strategyType} requires both legs to be ${expectedPosition}`,
      code: "INVALID_POSITION_TYPE",
    });
  }

  // Strangle: call strike > put strike
  if (callLeg.strike <= putLeg.strike) {
    errors.push({
      field: "legs",
      message: "Strangle: call strike should be higher than put strike",
      code: "INVALID_STRIKE_ORDER",
    });
  }

  // Same expiry
  if (callLeg.expiry !== putLeg.expiry) {
    errors.push({
      field: "legs",
      message: "Strangle requires both legs to have the same expiry",
      code: "EXPIRY_MISMATCH",
    });
  }

  return errors;
}

function validateIronCondor(legs: CreateLegInput[]): ValidationError[] {
  const errors: ValidationError[] = [];

  if (legs.length !== 4) {
    errors.push({
      field: "legs",
      message: "Iron condor requires exactly 4 legs",
      code: "INVALID_LEG_COUNT",
    });
    return errors;
  }

  // Should have 2 puts and 2 calls
  const calls = legs.filter((l) => l.optionType === "call");
  const puts = legs.filter((l) => l.optionType === "put");

  if (calls.length !== 2 || puts.length !== 2) {
    errors.push({
      field: "legs",
      message: "Iron condor requires 2 calls and 2 puts",
      code: "INVALID_IRON_CONDOR_STRUCTURE",
    });
    return errors;
  }

  // Should have 2 long and 2 short
  const longLegs = legs.filter((l) => l.positionType === "long");
  const shortLegs = legs.filter((l) => l.positionType === "short");

  if (longLegs.length !== 2 || shortLegs.length !== 2) {
    errors.push({
      field: "legs",
      message: "Iron condor requires 2 long and 2 short legs",
      code: "INVALID_IRON_CONDOR_STRUCTURE",
    });
  }

  // All same expiry
  const expiries = new Set(legs.map((l) => l.expiry));
  if (expiries.size > 1) {
    errors.push({
      field: "legs",
      message: "Iron condor requires all legs to have the same expiry",
      code: "EXPIRY_MISMATCH",
    });
  }

  return errors;
}

function validateIronButterfly(legs: CreateLegInput[]): ValidationError[] {
  const errors: ValidationError[] = [];

  if (legs.length !== 4) {
    errors.push({
      field: "legs",
      message: "Iron butterfly requires exactly 4 legs",
      code: "INVALID_LEG_COUNT",
    });
    return errors;
  }

  // Should have 2 puts and 2 calls
  const calls = legs.filter((l) => l.optionType === "call");
  const puts = legs.filter((l) => l.optionType === "put");

  if (calls.length !== 2 || puts.length !== 2) {
    errors.push({
      field: "legs",
      message: "Iron butterfly requires 2 calls and 2 puts",
      code: "INVALID_IRON_BUTTERFLY_STRUCTURE",
    });
  }

  // All same expiry
  const expiries = new Set(legs.map((l) => l.expiry));
  if (expiries.size > 1) {
    errors.push({
      field: "legs",
      message: "Iron butterfly requires all legs to have the same expiry",
      code: "EXPIRY_MISMATCH",
    });
  }

  return errors;
}

function validateCalendarOrDiagonal(
  legs: CreateLegInput[],
  strategyType: "calendar_spread" | "diagonal_spread",
): ValidationError[] {
  const errors: ValidationError[] = [];

  if (legs.length !== 2) {
    errors.push({
      field: "legs",
      message: `${strategyType} requires exactly 2 legs`,
      code: "INVALID_LEG_COUNT",
    });
    return errors;
  }

  // Should have different expiries
  const expiries = new Set(legs.map((l) => l.expiry));
  if (expiries.size === 1) {
    errors.push({
      field: "legs",
      message: `${strategyType} requires different expiration dates`,
      code: "SAME_EXPIRY",
    });
  }

  // Should have same option type (both calls or both puts)
  const optionTypes = new Set(legs.map((l) => l.optionType));
  if (optionTypes.size > 1) {
    errors.push({
      field: "legs",
      message: `${strategyType} requires same option type for both legs`,
      code: "OPTION_TYPE_MISMATCH",
    });
  }

  // Calendar spread: same strike; Diagonal: different strikes
  if (strategyType === "calendar_spread") {
    const strikes = new Set(legs.map((l) => l.strike));
    if (strikes.size > 1) {
      errors.push({
        field: "legs",
        message: "Calendar spread requires same strike for both legs",
        code: "STRIKE_MISMATCH",
      });
    }
  }

  return errors;
}

// ============================================================================
// WARNINGS GENERATION
// ============================================================================

function generateWarnings(request: CreateStrategyRequest): ValidationWarning[] {
  const warnings: ValidationWarning[] = [];

  // Check for near-term expiration
  for (const leg of request.legs) {
    const dte = calculateDTE(leg.expiry);
    if (dte <= 7) {
      warnings.push({
        field: `legs`,
        message:
          `Leg ${leg.legNumber} expires in ${dte} days - consider longer-dated contracts`,
        code: "NEAR_EXPIRATION",
      });
    }
  }

  // Check for unusual contract sizes
  const contracts = request.legs.map((l) => l.contracts);
  const maxContracts = Math.max(...contracts);
  const minContracts = Math.min(...contracts);
  if (maxContracts !== minContracts) {
    warnings.push({
      field: "legs",
      message:
        "Legs have different contract quantities - verify this is intentional",
      code: "UNEQUAL_CONTRACTS",
    });
  }

  // Check for wide bid-ask spreads (if Greeks provided)
  // This would require market data, so skip for now

  return warnings;
}

function calculateDTE(expiryDate: string): number {
  const expiry = new Date(expiryDate);
  const now = new Date();
  const diffTime = expiry.getTime() - now.getTime();
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  return Math.max(0, diffDays);
}

// ============================================================================
// LEG CLOSURE VALIDATION
// ============================================================================

export interface CloseLegValidation {
  isValid: boolean;
  errors: ValidationError[];
}

/**
 * Validate a leg closure request
 */
export function validateLegClosure(
  leg: OptionsLeg,
  exitPrice: number,
): CloseLegValidation {
  const errors: ValidationError[] = [];

  if (leg.isClosed) {
    errors.push({
      field: "legId",
      message: "Leg is already closed",
      code: "ALREADY_CLOSED",
    });
  }

  if (exitPrice <= 0) {
    errors.push({
      field: "exitPrice",
      message: "Exit price must be a positive number",
      code: "INVALID_EXIT_PRICE",
    });
  }

  return {
    isValid: errors.length === 0,
    errors,
  };
}

/**
 * Validate closing an entire strategy
 */
export function validateStrategyClosure(
  legs: OptionsLeg[],
  exitPrices: { legId: string; exitPrice: number }[],
): CloseLegValidation {
  const errors: ValidationError[] = [];

  // Check all open legs have exit prices
  const openLegs = legs.filter((l) => !l.isClosed);
  const exitPriceMap = new Map(exitPrices.map((p) => [p.legId, p.exitPrice]));

  for (const leg of openLegs) {
    const exitPrice = exitPriceMap.get(leg.id);
    if (exitPrice === undefined) {
      errors.push({
        field: "exitPrices",
        message: `Missing exit price for leg ${leg.legNumber}`,
        code: "MISSING_EXIT_PRICE",
      });
    } else if (exitPrice <= 0) {
      errors.push({
        field: "exitPrices",
        message: `Exit price for leg ${leg.legNumber} must be positive`,
        code: "INVALID_EXIT_PRICE",
      });
    }
  }

  return {
    isValid: errors.length === 0,
    errors,
  };
}
