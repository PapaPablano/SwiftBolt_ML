/**
 * Futures Calendar & Multipliers
 *
 * Standalone module for futures contract metadata:
 * - Contract multipliers (point value per contract)
 * - Tick sizes (minimum price increment)
 * - Front-month roll detection
 * - Symbol normalization (user-input → TradeStation format)
 */

// ============================================================================
// CONTRACT MULTIPLIERS
// ============================================================================

/** Point value per contract for supported futures symbols */
export const FUTURES_MULTIPLIERS: Record<string, number> = {
  "@ES": 50, // E-mini S&P 500
  "@NQ": 20, // E-mini Nasdaq-100
  "@RTY": 50, // E-mini Russell 2000
  "@YM": 5, // E-mini Dow
  "@CL": 1000, // Crude Oil
  "@GC": 100, // Gold
  "@SI": 5000, // Silver
  "@ZB": 1000, // 30-Year T-Bond
};

export type FuturesMultiplier = 50 | 20 | 5 | 1000 | 100 | 5000;

// ============================================================================
// TICK SIZES
// ============================================================================

/** Minimum price increment for SL/TP rounding */
export const FUTURES_TICK_SIZES: Record<string, number> = {
  "@ES": 0.25,
  "@NQ": 0.25,
  "@RTY": 0.10,
  "@YM": 1.0,
  "@CL": 0.01,
  "@GC": 0.10,
  "@SI": 0.005,
  "@ZB": 1 / 32, // 30-Year T-Bond (1/32 of a point)
};

// ============================================================================
// MAX CONTRACTS PER SYMBOL
// ============================================================================

/** Upper bound on contract quantity to prevent runaway sizing */
export const MAX_FUTURES_CONTRACTS: Record<string, number> = {
  "@ES": 100,
  "@NQ": 100,
  "@RTY": 100,
  "@YM": 100,
  "@CL": 50,
  "@GC": 50,
  "@SI": 50,
  "@ZB": 50,
};

// ============================================================================
// ROLL DETECTION
// ============================================================================

/**
 * Number of trading days before expiry to roll to the next contract month.
 * Standard practice: 5 trading days before first notice date (financials)
 * or last trading day (commodities).
 */
export const ROLL_DAYS_BEFORE_EXPIRY = 5;

/** Quarterly expiry months for financial futures (@ES, @NQ, @RTY, @YM) */
const QUARTERLY_MONTHS = [2, 5, 8, 11]; // March, June, September, December (0-indexed)

/** Monthly month codes for futures */
const MONTH_CODES: Record<number, string> = {
  0: "F", // January
  1: "G", // February
  2: "H", // March
  3: "J", // April
  4: "K", // May
  5: "M", // June
  6: "N", // July
  7: "Q", // August
  8: "U", // September
  9: "V", // October
  10: "X", // November
  11: "Z", // December
};

/**
 * Get the third Friday of a given month/year (options/futures expiry).
 */
function getThirdFriday(year: number, month: number): Date {
  const d = new Date(year, month, 1);
  // Find first Friday
  const dayOfWeek = d.getDay();
  const firstFriday = dayOfWeek <= 5 ? (5 - dayOfWeek + 1) : (5 + 7 - dayOfWeek + 1);
  // Third Friday = first Friday + 14
  return new Date(year, month, firstFriday + 14);
}

/**
 * Subtract N business days from a date (Mon–Fri only).
 */
function subtractBusinessDays(date: Date, days: number): Date {
  const result = new Date(date);
  let remaining = days;
  while (remaining > 0) {
    result.setDate(result.getDate() - 1);
    const dow = result.getDay();
    if (dow !== 0 && dow !== 6) remaining--;
  }
  return result;
}

export interface FuturesExpiry {
  symbol: string;
  frontMonth: string;
  nextMonth: string;
  expiryDate: Date;
  rollDate: Date;
}

/**
 * Get the nearest quarterly expiry for a futures symbol.
 * Returns front-month and next-month contract codes.
 */
export function getNearestExpiry(symbol: string): FuturesExpiry {
  const baseSymbol = symbol.replace("@", "");
  const now = new Date();
  const year = now.getFullYear();
  const yearCode = String(year).slice(-2);

  // Find the next quarterly expiry
  for (let monthOffset = 0; monthOffset < 12; monthOffset++) {
    const checkMonth = (now.getMonth() + monthOffset) % 12;
    const checkYear = year + Math.floor((now.getMonth() + monthOffset) / 12);
    const checkYearCode = String(checkYear).slice(-2);

    if (!QUARTERLY_MONTHS.includes(checkMonth)) continue;

    const expiryDate = getThirdFriday(checkYear, checkMonth);
    const rollDate = subtractBusinessDays(expiryDate, ROLL_DAYS_BEFORE_EXPIRY);

    if (now <= rollDate) {
      // This is the front month
      const frontMonthCode = MONTH_CODES[checkMonth];
      // Find next quarter
      const nextIdx = (QUARTERLY_MONTHS.indexOf(checkMonth) + 1) % 4;
      const nextMonth = QUARTERLY_MONTHS[nextIdx];
      const nextYear = nextIdx === 0 ? checkYear + 1 : checkYear;
      const nextYearCode = String(nextYear).slice(-2);
      const nextMonthCode = MONTH_CODES[nextMonth];

      return {
        symbol,
        frontMonth: `${baseSymbol}${frontMonthCode}${checkYearCode}`,
        nextMonth: `${baseSymbol}${nextMonthCode}${nextYearCode}`,
        expiryDate,
        rollDate,
      };
    }
  }

  // Fallback: should not reach here
  const fallbackMonth = QUARTERLY_MONTHS[0];
  const nextYear = year + 1;
  return {
    symbol,
    frontMonth: `${baseSymbol}${MONTH_CODES[fallbackMonth]}${String(nextYear).slice(-2)}`,
    nextMonth: `${baseSymbol}${MONTH_CODES[QUARTERLY_MONTHS[1]]}${String(nextYear).slice(-2)}`,
    expiryDate: getThirdFriday(nextYear, fallbackMonth),
    rollDate: subtractBusinessDays(getThirdFriday(nextYear, fallbackMonth), ROLL_DAYS_BEFORE_EXPIRY),
  };
}

/**
 * Check if a futures symbol should roll to the next contract month.
 * Returns true if within ROLL_DAYS_BEFORE_EXPIRY business days of expiry.
 */
export function shouldRoll(symbol: string): boolean {
  const expiry = getNearestExpiry(symbol);
  return new Date() > expiry.rollDate;
}

/**
 * Get the front-month contract symbol (e.g., @ES → ESH26).
 * If within roll window, returns the next month instead.
 */
export function getFrontMonthSymbol(symbol: string): string {
  const expiry = getNearestExpiry(symbol);
  return shouldRoll(symbol) ? expiry.nextMonth : expiry.frontMonth;
}

/**
 * Round a price to the nearest valid tick boundary for a futures symbol.
 * SL/TP prices must be rounded to prevent TradeStation rejection.
 */
export function roundToTick(price: number, symbol: string): number {
  const tick = FUTURES_TICK_SIZES[symbol] ?? 0.01;
  return Math.round(price / tick) * tick;
}
