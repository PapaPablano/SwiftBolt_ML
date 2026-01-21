// P&L Calculator Service for Multi-Leg Options Strategies
// Calculates P&L, Greeks, max risk/reward for various strategy types

import {
  type MultiLegStrategy,
  type OptionsLeg,
  type PLSnapshot,
  type LegPLSnapshot,
  type MaxRiskReward,
  type ProfitZone,
  type StrategyType,
  type PositionType,
} from "../types/multileg.ts";

// ============================================================================
// P&L CALCULATION
// ============================================================================

export interface LegPriceData {
  legId: string;
  price: number;
  delta?: number;
  gamma?: number;
  theta?: number;
  vega?: number;
  rho?: number;
}

/**
 * Calculate P&L snapshot for a multi-leg strategy
 */
export function calculateStrategyPL(
  strategy: MultiLegStrategy,
  legs: OptionsLeg[],
  underlyingPrice: number,
  currentPrices: LegPriceData[]
): PLSnapshot {
  const timestamp = new Date().toISOString();
  const priceMap = new Map(currentPrices.map((p) => [p.legId, p]));

  const legSnapshots: LegPLSnapshot[] = [];
  let totalEntryCost = 0;
  let totalCurrentValue = 0;
  let totalDelta = 0;
  let totalGamma = 0;
  let totalTheta = 0;
  let totalVega = 0;
  let totalRho = 0;

  for (const leg of legs) {
    if (leg.isClosed) continue;

    const priceData = priceMap.get(leg.id);
    const currentPrice = priceData?.price ?? leg.currentPrice ?? 0;

    const legSnapshot = calculateLegPL(leg, underlyingPrice, currentPrice, priceData);
    legSnapshots.push(legSnapshot);

    // Sum costs and values
    totalEntryCost += legSnapshot.entryCost;
    totalCurrentValue += legSnapshot.currentValue;

    // Sum Greeks with position sign
    const positionSign = leg.positionType === "long" ? 1 : -1;
    totalDelta += legSnapshot.delta * positionSign;
    totalGamma += legSnapshot.gamma * positionSign;
    totalTheta += legSnapshot.theta * positionSign;
    totalVega += legSnapshot.vega * positionSign;
    totalRho += legSnapshot.rho * positionSign;
  }

  // Calculate net P&L
  const totalUnrealizedPL = totalCurrentValue - totalEntryCost;
  const totalUnrealizedPLPct =
    totalEntryCost !== 0 ? totalUnrealizedPL / Math.abs(totalEntryCost) : 0;

  return {
    underlyingPrice,
    timestamp,
    totalEntryCost,
    totalCurrentValue,
    totalUnrealizedPL,
    totalUnrealizedPLPct,
    legSnapshots,
    delta: totalDelta,
    gamma: totalGamma,
    theta: totalTheta,
    vega: totalVega,
    rho: totalRho,
  };
}

/**
 * Calculate P&L for a single leg
 */
export function calculateLegPL(
  leg: OptionsLeg,
  underlyingPrice: number,
  currentPrice: number,
  priceData?: LegPriceData
): LegPLSnapshot {
  const contracts = leg.contracts;
  const entryPrice = leg.entryPrice;

  // Calculate costs (100 shares per contract)
  const entryCost = entryPrice * contracts * 100;
  const currentValue = currentPrice * contracts * 100;

  // Calculate P&L (unsigned first)
  const unrealizedPL = currentValue - entryCost;
  const unrealizedPLPct = entryCost !== 0 ? unrealizedPL / Math.abs(entryCost) : 0;

  // Apply position sign
  const positionSign = leg.positionType === "long" ? 1 : -1;
  const unrealizedPLSigned = unrealizedPL * positionSign;

  // Get Greeks (multiply by 100 for contract, then by contracts)
  const delta = (priceData?.delta ?? leg.currentDelta ?? 0) * 100 * contracts;
  const gamma = (priceData?.gamma ?? leg.currentGamma ?? 0) * 100 * contracts;
  const theta = (priceData?.theta ?? leg.currentTheta ?? 0) * 100 * contracts;
  const vega = (priceData?.vega ?? leg.currentVega ?? 0) * 100 * contracts;
  const rho = (priceData?.rho ?? leg.currentRho ?? 0) * 100 * contracts;

  // Determine ITM status
  const strike = leg.strike;
  const isITM =
    (leg.optionType === "call" && underlyingPrice > strike) ||
    (leg.optionType === "put" && underlyingPrice < strike);

  const isDeepITM =
    (leg.optionType === "call" && underlyingPrice > strike + 2) ||
    (leg.optionType === "put" && underlyingPrice < strike - 2);

  // Breaching = within 0.5% of strike
  const breachThreshold = Math.abs(strike) * 0.005;
  const isBreachingStrike = Math.abs(underlyingPrice - strike) <= breachThreshold;

  return {
    legId: leg.id,
    legNumber: leg.legNumber,
    entryPrice,
    currentPrice,
    entryCost,
    currentValue,
    unrealizedPL,
    unrealizedPLSigned,
    unrealizedPLPct,
    delta,
    gamma,
    theta,
    vega,
    rho,
    isITM,
    isDeepITM,
    isBreachingStrike,
  };
}

// ============================================================================
// MAX RISK / REWARD CALCULATIONS
// ============================================================================

/**
 * Calculate max risk, max reward, and breakeven points for a strategy
 */
export function calculateMaxRiskReward(
  strategyType: StrategyType,
  legs: OptionsLeg[]
): MaxRiskReward {
  switch (strategyType) {
    case "bull_call_spread":
      return calcBullCallSpread(legs);
    case "bear_call_spread":
      return calcBearCallSpread(legs);
    case "bull_put_spread":
      return calcBullPutSpread(legs);
    case "bear_put_spread":
      return calcBearPutSpread(legs);
    case "long_straddle":
      return calcLongStraddle(legs);
    case "short_straddle":
      return calcShortStraddle(legs);
    case "long_strangle":
      return calcLongStrangle(legs);
    case "short_strangle":
      return calcShortStrangle(legs);
    case "iron_condor":
      return calcIronCondor(legs);
    case "iron_butterfly":
      return calcIronButterfly(legs);
    case "butterfly_spread":
      return calcButterflySpread(legs);
    case "call_ratio_backspread":
    case "put_ratio_backspread":
      return calcRatioBackspread(legs, strategyType);
    case "calendar_spread":
    case "diagonal_spread":
      return calcCalendarOrDiagonal(legs);
    case "custom":
    default:
      return calcCustomStrategy(legs);
  }
}

/**
 * Bull Call Spread: Long Call K1 + Short Call K2 (K2 > K1)
 * Max Loss = Net Debit
 * Max Gain = Width - Net Debit
 * Breakeven = K1 + Net Debit
 */
function calcBullCallSpread(legs: OptionsLeg[]): MaxRiskReward {
  const longLeg = legs.find((l) => l.positionType === "long" && l.optionType === "call");
  const shortLeg = legs.find((l) => l.positionType === "short" && l.optionType === "call");

  if (!longLeg || !shortLeg) {
    return { maxRisk: 0, maxReward: 0, breakevenPoints: [] };
  }

  const k1 = longLeg.strike;
  const k2 = shortLeg.strike;
  const p1 = longLeg.entryPrice;
  const p2 = shortLeg.entryPrice;
  const contracts = longLeg.contracts;

  const netDebit = (p1 - p2) * 100 * contracts;
  const width = (k2 - k1) * 100 * contracts;

  const maxRisk = netDebit;
  const maxReward = width - netDebit;
  const breakeven = k1 + (netDebit / (100 * contracts));

  return { maxRisk, maxReward, breakevenPoints: [breakeven] };
}

/**
 * Bear Call Spread: Short Call K1 + Long Call K2 (K2 > K1)
 * Max Profit = Net Credit
 * Max Loss = Width - Net Credit
 * Breakeven = K1 + Net Credit
 */
function calcBearCallSpread(legs: OptionsLeg[]): MaxRiskReward {
  const shortLeg = legs.find((l) => l.positionType === "short" && l.optionType === "call");
  const longLeg = legs.find((l) => l.positionType === "long" && l.optionType === "call");

  if (!shortLeg || !longLeg) {
    return { maxRisk: 0, maxReward: 0, breakevenPoints: [] };
  }

  const k1 = shortLeg.strike;
  const k2 = longLeg.strike;
  const p1 = shortLeg.entryPrice;
  const p2 = longLeg.entryPrice;
  const contracts = shortLeg.contracts;

  const netCredit = (p1 - p2) * 100 * contracts;
  const width = (k2 - k1) * 100 * contracts;

  const maxReward = netCredit;
  const maxRisk = width - netCredit;
  const breakeven = k1 + (netCredit / (100 * contracts));

  return { maxRisk, maxReward, breakevenPoints: [breakeven] };
}

/**
 * Bull Put Spread: Short Put K2 + Long Put K1 (K2 > K1)
 * Max Profit = Net Credit
 * Max Loss = Width - Net Credit
 * Breakeven = K2 - Net Credit
 */
function calcBullPutSpread(legs: OptionsLeg[]): MaxRiskReward {
  const shortLeg = legs.find((l) => l.positionType === "short" && l.optionType === "put");
  const longLeg = legs.find((l) => l.positionType === "long" && l.optionType === "put");

  if (!shortLeg || !longLeg) {
    return { maxRisk: 0, maxReward: 0, breakevenPoints: [] };
  }

  const k2 = shortLeg.strike; // Higher strike
  const k1 = longLeg.strike; // Lower strike
  const p2 = shortLeg.entryPrice;
  const p1 = longLeg.entryPrice;
  const contracts = shortLeg.contracts;

  const netCredit = (p2 - p1) * 100 * contracts;
  const width = (k2 - k1) * 100 * contracts;

  const maxReward = netCredit;
  const maxRisk = width - netCredit;
  const breakeven = k2 - (netCredit / (100 * contracts));

  return { maxRisk, maxReward, breakevenPoints: [breakeven] };
}

/**
 * Bear Put Spread: Long Put K2 + Short Put K1 (K2 > K1)
 * Max Loss = Net Debit
 * Max Profit = Width - Net Debit
 * Breakeven = K2 - Net Debit
 */
function calcBearPutSpread(legs: OptionsLeg[]): MaxRiskReward {
  const longLeg = legs.find((l) => l.positionType === "long" && l.optionType === "put");
  const shortLeg = legs.find((l) => l.positionType === "short" && l.optionType === "put");

  if (!longLeg || !shortLeg) {
    return { maxRisk: 0, maxReward: 0, breakevenPoints: [] };
  }

  const k2 = longLeg.strike; // Higher strike
  const k1 = shortLeg.strike; // Lower strike
  const p2 = longLeg.entryPrice;
  const p1 = shortLeg.entryPrice;
  const contracts = longLeg.contracts;

  const netDebit = (p2 - p1) * 100 * contracts;
  const width = (k2 - k1) * 100 * contracts;

  const maxRisk = netDebit;
  const maxReward = width - netDebit;
  const breakeven = k2 - (netDebit / (100 * contracts));

  return { maxRisk, maxReward, breakevenPoints: [breakeven] };
}

/**
 * Long Straddle: Long Call + Long Put (same strike K)
 * Max Loss = Total Premium Paid
 * Max Gain = Unlimited
 * Breakevens = K ± Premium
 */
function calcLongStraddle(legs: OptionsLeg[]): MaxRiskReward {
  const callLeg = legs.find((l) => l.optionType === "call");
  const putLeg = legs.find((l) => l.optionType === "put");

  if (!callLeg || !putLeg) {
    return { maxRisk: 0, maxReward: 0, breakevenPoints: [] };
  }

  const strike = callLeg.strike;
  const contracts = callLeg.contracts;
  const totalPremium = (callLeg.entryPrice + putLeg.entryPrice) * 100 * contracts;

  const maxRisk = totalPremium;
  const maxReward = Infinity; // Unlimited upside
  const beUp = strike + (totalPremium / (100 * contracts));
  const beDown = strike - (totalPremium / (100 * contracts));

  return { maxRisk, maxReward, breakevenPoints: [beDown, beUp] };
}

/**
 * Short Straddle: Short Call + Short Put (same strike K)
 * Max Gain = Total Premium Collected
 * Max Loss = Unlimited
 * Breakevens = K ± Premium
 */
function calcShortStraddle(legs: OptionsLeg[]): MaxRiskReward {
  const callLeg = legs.find((l) => l.optionType === "call");
  const putLeg = legs.find((l) => l.optionType === "put");

  if (!callLeg || !putLeg) {
    return { maxRisk: 0, maxReward: 0, breakevenPoints: [] };
  }

  const strike = callLeg.strike;
  const contracts = callLeg.contracts;
  const totalPremium = (callLeg.entryPrice + putLeg.entryPrice) * 100 * contracts;

  const maxReward = totalPremium;
  const maxRisk = Infinity; // Unlimited risk
  const beUp = strike + (totalPremium / (100 * contracts));
  const beDown = strike - (totalPremium / (100 * contracts));

  return { maxRisk, maxReward, breakevenPoints: [beDown, beUp] };
}

/**
 * Long Strangle: Long OTM Call + Long OTM Put (different strikes)
 * Max Loss = Total Premium Paid
 * Max Gain = Unlimited
 * Breakevens = Call Strike + Premium, Put Strike - Premium
 */
function calcLongStrangle(legs: OptionsLeg[]): MaxRiskReward {
  const callLeg = legs.find((l) => l.optionType === "call");
  const putLeg = legs.find((l) => l.optionType === "put");

  if (!callLeg || !putLeg) {
    return { maxRisk: 0, maxReward: 0, breakevenPoints: [] };
  }

  const contracts = callLeg.contracts;
  const totalPremium = (callLeg.entryPrice + putLeg.entryPrice) * 100 * contracts;

  const maxRisk = totalPremium;
  const maxReward = Infinity;
  const beUp = callLeg.strike + (totalPremium / (100 * contracts));
  const beDown = putLeg.strike - (totalPremium / (100 * contracts));

  return { maxRisk, maxReward, breakevenPoints: [beDown, beUp] };
}

/**
 * Short Strangle: Short OTM Call + Short OTM Put
 * Max Gain = Total Premium Collected
 * Max Loss = Unlimited
 */
function calcShortStrangle(legs: OptionsLeg[]): MaxRiskReward {
  const callLeg = legs.find((l) => l.optionType === "call");
  const putLeg = legs.find((l) => l.optionType === "put");

  if (!callLeg || !putLeg) {
    return { maxRisk: 0, maxReward: 0, breakevenPoints: [] };
  }

  const contracts = callLeg.contracts;
  const totalPremium = (callLeg.entryPrice + putLeg.entryPrice) * 100 * contracts;

  const maxReward = totalPremium;
  const maxRisk = Infinity;
  const beUp = callLeg.strike + (totalPremium / (100 * contracts));
  const beDown = putLeg.strike - (totalPremium / (100 * contracts));

  return {
    maxRisk,
    maxReward,
    breakevenPoints: [beDown, beUp],
    profitZones: [{ min: putLeg.strike, max: callLeg.strike }],
  };
}

/**
 * Iron Condor: Bull Put Spread + Bear Call Spread
 * Max Profit = Net Credit
 * Max Loss = Width of one spread - Net Credit
 */
function calcIronCondor(legs: OptionsLeg[]): MaxRiskReward {
  // Sort legs by strike
  const sortedLegs = [...legs].sort((a, b) => a.strike - b.strike);

  if (sortedLegs.length !== 4) {
    return { maxRisk: 0, maxReward: 0, breakevenPoints: [] };
  }

  const contracts = sortedLegs[0].contracts;

  // Calculate total credit (short legs) - total debit (long legs)
  const totalCredit = sortedLegs
    .filter((l) => l.positionType === "short")
    .reduce((sum, l) => sum + l.entryPrice, 0);
  const totalDebit = sortedLegs
    .filter((l) => l.positionType === "long")
    .reduce((sum, l) => sum + l.entryPrice, 0);

  const netCredit = (totalCredit - totalDebit) * 100 * contracts;

  // Width is typically the same for both spreads
  const putSpreadWidth = (sortedLegs[1].strike - sortedLegs[0].strike) * 100 * contracts;

  const maxReward = netCredit;
  const maxRisk = putSpreadWidth - netCredit;

  // Breakevens at short strikes ± credit
  const shortPutStrike = sortedLegs[1].strike;
  const shortCallStrike = sortedLegs[2].strike;

  const beDown = shortPutStrike - (netCredit / (100 * contracts));
  const beUp = shortCallStrike + (netCredit / (100 * contracts));

  return {
    maxRisk,
    maxReward,
    breakevenPoints: [beDown, beUp],
    profitZones: [{ min: shortPutStrike, max: shortCallStrike }],
  };
}

/**
 * Iron Butterfly: ATM Straddle + OTM Wings
 */
function calcIronButterfly(legs: OptionsLeg[]): MaxRiskReward {
  // Similar to iron condor but with same short strikes
  const sortedLegs = [...legs].sort((a, b) => a.strike - b.strike);

  if (sortedLegs.length !== 4) {
    return { maxRisk: 0, maxReward: 0, breakevenPoints: [] };
  }

  const contracts = sortedLegs[0].contracts;

  const totalCredit = sortedLegs
    .filter((l) => l.positionType === "short")
    .reduce((sum, l) => sum + l.entryPrice, 0);
  const totalDebit = sortedLegs
    .filter((l) => l.positionType === "long")
    .reduce((sum, l) => sum + l.entryPrice, 0);

  const netCredit = (totalCredit - totalDebit) * 100 * contracts;
  const width = (sortedLegs[1].strike - sortedLegs[0].strike) * 100 * contracts;

  const maxReward = netCredit;
  const maxRisk = width - netCredit;

  // Short strikes should be the same
  const shortStrike = sortedLegs[1].strike;
  const beDown = shortStrike - (netCredit / (100 * contracts));
  const beUp = shortStrike + (netCredit / (100 * contracts));

  return { maxRisk, maxReward, breakevenPoints: [beDown, beUp] };
}

/**
 * Butterfly Spread: 1 Long + 2 Short + 1 Long (same type)
 */
function calcButterflySpread(legs: OptionsLeg[]): MaxRiskReward {
  const sortedLegs = [...legs].sort((a, b) => a.strike - b.strike);

  if (sortedLegs.length < 3) {
    return { maxRisk: 0, maxReward: 0, breakevenPoints: [] };
  }

  const contracts = sortedLegs[0].contracts;

  // Net debit/credit
  let netCost = 0;
  for (const leg of sortedLegs) {
    const legCost = leg.entryPrice * leg.contracts * 100;
    netCost += leg.positionType === "long" ? legCost : -legCost;
  }

  const width = sortedLegs[1].strike - sortedLegs[0].strike;
  const maxReward = width * 100 * contracts - Math.abs(netCost);
  const maxRisk = Math.abs(netCost);

  const middleStrike = sortedLegs[1].strike;
  const beDown = sortedLegs[0].strike + (maxRisk / (100 * contracts));
  const beUp = sortedLegs[sortedLegs.length - 1].strike - (maxRisk / (100 * contracts));

  return { maxRisk, maxReward, breakevenPoints: [beDown, beUp] };
}

/**
 * Ratio Backspread: Sell 1, Buy 2 (or similar ratio)
 */
function calcRatioBackspread(
  legs: OptionsLeg[],
  type: "call_ratio_backspread" | "put_ratio_backspread"
): MaxRiskReward {
  const shortLegs = legs.filter((l) => l.positionType === "short");
  const longLegs = legs.filter((l) => l.positionType === "long");

  if (shortLegs.length === 0 || longLegs.length === 0) {
    return { maxRisk: 0, maxReward: 0, breakevenPoints: [] };
  }

  const shortContracts = shortLegs.reduce((sum, l) => sum + l.contracts, 0);
  const longContracts = longLegs.reduce((sum, l) => sum + l.contracts, 0);

  const shortPremium = shortLegs.reduce((sum, l) => sum + l.entryPrice * l.contracts * 100, 0);
  const longPremium = longLegs.reduce((sum, l) => sum + l.entryPrice * l.contracts * 100, 0);

  const netCredit = shortPremium - longPremium;

  // Max risk is typically at the short strike
  const shortStrike = shortLegs[0].strike;
  const longStrike = longLegs[0].strike;

  const maxRisk =
    type === "call_ratio_backspread"
      ? Math.abs(longStrike - shortStrike) * 100 * shortContracts - netCredit
      : Math.abs(shortStrike - longStrike) * 100 * shortContracts - netCredit;

  // Unlimited profit potential
  const maxReward = Infinity;

  return {
    maxRisk: Math.max(0, maxRisk),
    maxReward,
    breakevenPoints: [shortStrike],
  };
}

/**
 * Calendar/Diagonal Spread: Different expirations, complex P&L profile
 */
function calcCalendarOrDiagonal(legs: OptionsLeg[]): MaxRiskReward {
  // Calendar spreads have complex P&L that depends on IV and time
  // For simplicity, we'll use net debit as max risk

  const netCost = legs.reduce((sum, leg) => {
    const cost = leg.entryPrice * leg.contracts * 100;
    return leg.positionType === "long" ? sum + cost : sum - cost;
  }, 0);

  return {
    maxRisk: Math.max(0, netCost),
    maxReward: Infinity, // Time-dependent
    breakevenPoints: [], // Too complex without modeling
  };
}

/**
 * Custom strategy: Calculate based on actual legs
 */
function calcCustomStrategy(legs: OptionsLeg[]): MaxRiskReward {
  // For custom strategies, we calculate based on position sizing
  const netCost = legs.reduce((sum, leg) => {
    const cost = leg.entryPrice * leg.contracts * 100;
    return leg.positionType === "long" ? sum + cost : sum - cost;
  }, 0);

  // If net debit, max risk is the debit
  // If net credit, risk is harder to calculate without knowing strategy structure
  const hasShortLegs = legs.some((l) => l.positionType === "short");
  const maxRisk = hasShortLegs ? Infinity : Math.max(0, netCost);
  const maxReward = netCost < 0 ? Infinity : Math.abs(netCost);

  return { maxRisk, maxReward, breakevenPoints: [] };
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

/**
 * Calculate days to expiration
 */
export function calculateDTE(expiryDate: string): number {
  const expiry = new Date(expiryDate);
  const now = new Date();
  const diffTime = expiry.getTime() - now.getTime();
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  return Math.max(0, diffDays);
}

/**
 * Update DTE for all legs in a strategy
 */
export function updateAllDTE(legs: OptionsLeg[]): OptionsLeg[] {
  return legs.map((leg) => ({
    ...leg,
    currentDTE: calculateDTE(leg.expiry),
    isNearExpiration: calculateDTE(leg.expiry) <= 3,
  }));
}

/**
 * Determine if underlying is in the money for a leg
 */
export function isLegITM(
  leg: OptionsLeg,
  underlyingPrice: number
): boolean {
  return (
    (leg.optionType === "call" && underlyingPrice > leg.strike) ||
    (leg.optionType === "put" && underlyingPrice < leg.strike)
  );
}

/**
 * Determine if underlying is deep in the money (>2 strikes)
 */
export function isLegDeepITM(
  leg: OptionsLeg,
  underlyingPrice: number
): boolean {
  return (
    (leg.optionType === "call" && underlyingPrice > leg.strike + 2) ||
    (leg.optionType === "put" && underlyingPrice < leg.strike - 2)
  );
}

/**
 * Check if underlying is breaching a strike (within 0.5%)
 */
export function isBreachingStrike(
  strike: number,
  underlyingPrice: number
): boolean {
  const threshold = Math.abs(strike) * 0.005;
  return Math.abs(underlyingPrice - strike) <= threshold;
}
