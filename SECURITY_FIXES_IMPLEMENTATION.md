# Security Fixes: Implementation Guide
## Copy-Paste Ready Code for All Critical Findings

---

## 1. RLS Policies for Paper Trading Tables

**File:** `supabase/migrations/20260226000000_paper_trading_rls_policies.sql`

```sql
-- ==============================================================================
-- FIX 1: ADD RLS POLICIES TO PAPER TRADING TABLES
-- ==============================================================================
-- This migration adds Row Level Security (RLS) policies to paper_trading_positions,
-- paper_trading_trades, and strategy_execution_log tables to prevent cross-user
-- data leakage.

-- Ensure RLS is enabled
ALTER TABLE paper_trading_positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_trading_trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE strategy_execution_log ENABLE ROW LEVEL SECURITY;

-- ==============================================================================
-- PAPER TRADING POSITIONS RLS POLICIES
-- ==============================================================================

-- Allow users to view their own positions
CREATE POLICY "Users can view their own positions"
  ON paper_trading_positions FOR SELECT
  USING (auth.uid() = user_id);

-- Allow users to insert their own positions (service role only in practice)
CREATE POLICY "Users can insert their own positions"
  ON paper_trading_positions FOR INSERT
  WITH CHECK (auth.uid() = user_id);

-- Allow users to update their own positions
CREATE POLICY "Users can update their own positions"
  ON paper_trading_positions FOR UPDATE
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

-- Allow users to delete their own positions
CREATE POLICY "Users can delete their own positions"
  ON paper_trading_positions FOR DELETE
  USING (auth.uid() = user_id);

-- ==============================================================================
-- PAPER TRADING TRADES RLS POLICIES
-- ==============================================================================

-- Allow users to view their own closed trades
CREATE POLICY "Users can view their own trades"
  ON paper_trading_trades FOR SELECT
  USING (auth.uid() = user_id);

-- Only service role can insert trades (executor inserts via service key)
CREATE POLICY "Only service role can insert trades"
  ON paper_trading_trades FOR INSERT
  WITH CHECK (auth.role() = 'service_role');

-- ==============================================================================
-- STRATEGY EXECUTION LOG RLS POLICIES
-- ==============================================================================

-- Allow users to view execution logs only for their own strategies
CREATE POLICY "Users can view execution logs of their strategies"
  ON strategy_execution_log FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM strategy_user_strategies
      WHERE strategy_user_strategies.id = strategy_execution_log.strategy_id
      AND strategy_user_strategies.user_id = auth.uid()
    )
  );

-- Only service role can insert execution logs
CREATE POLICY "Only service role can insert execution logs"
  ON strategy_execution_log FOR INSERT
  WITH CHECK (auth.role() = 'service_role');

-- ==============================================================================
-- PAPER TRADING METRICS RLS POLICIES
-- ==============================================================================

-- Allow users to view metrics for their own strategies
CREATE POLICY "Users can view metrics for their strategies"
  ON paper_trading_metrics FOR SELECT
  USING (auth.uid() = user_id);

-- Only service role can insert/update metrics
CREATE POLICY "Only service role can insert metrics"
  ON paper_trading_metrics FOR INSERT
  WITH CHECK (auth.role() = 'service_role');

CREATE POLICY "Only service role can update metrics"
  ON paper_trading_metrics FOR UPDATE
  WITH CHECK (auth.role() = 'service_role');

-- ==============================================================================
-- VERIFICATION QUERIES
-- ==============================================================================
-- Run these to verify RLS is working correctly:

-- 1. Check all policies are enabled
-- SELECT tablename, rowsecurity FROM pg_tables
-- WHERE schemaname='public' AND tablename LIKE 'paper_trading_%';

-- 2. List all policies
-- SELECT tablename, policyname, qual, with_check
-- FROM pg_policies
-- WHERE tablename LIKE 'paper_trading_%';

-- 3. Test RLS (run as different users):
-- SELECT * FROM paper_trading_positions; -- Should only see own positions
```

---

## 2. Slippage Validation

**File:** `supabase/functions/_shared/validators/slippage-validator.ts`

```typescript
/**
 * Slippage Validator
 * Prevents unrealistic slippage values (0.01% - 500%+)
 * Realistic ranges: 0.05% - 5% depending on liquidity
 */

export interface SlippageConfig {
  value: number; // percentage
  symbol: string;
  liquidity_tier?: 'high' | 'low' | 'micro_cap';
}

export interface ValidationResult {
  valid: boolean;
  error?: string;
  min?: number;
  max?: number;
}

// Slippage limits by liquidity tier (in percentage)
const SLIPPAGE_LIMITS: Record<string, { min: number; max: number }> = {
  high: { min: 0.05, max: 0.5 },        // AAPL, MSFT, SPY, QQQ
  low: { min: 0.5, max: 5.0 },          // Mid-cap stocks, less liquid
  micro_cap: { min: 2.0, max: 10.0 },   // Penny stocks, very low liquidity
};

/**
 * Get liquidity tier for symbol
 * Default to 'low' if not found in classification table
 */
export async function getLiquidityTier(
  supabase: any,
  symbolId: string
): Promise<'high' | 'low' | 'micro_cap'> {
  try {
    const { data, error } = await supabase
      .from('symbol_liquidity_classification')
      .select('liquidity_tier')
      .eq('symbol_id', symbolId)
      .single();

    if (error || !data) {
      return 'low'; // Conservative default
    }

    return data.liquidity_tier;
  } catch {
    return 'low';
  }
}

/**
 * Validate slippage value
 */
export function validateSlippage(config: SlippageConfig): ValidationResult {
  // Use provided tier or default to 'low'
  const tier = config.liquidity_tier || 'low';
  const limits = SLIPPAGE_LIMITS[tier];

  if (!limits) {
    return {
      valid: false,
      error: `Unknown liquidity tier: ${tier}`,
    };
  }

  // Check if value is within range
  if (config.value < limits.min) {
    return {
      valid: false,
      error: `Slippage ${config.value}% is too low for ${tier}-liquidity symbols. Minimum: ${limits.min}%`,
      min: limits.min,
      max: limits.max,
    };
  }

  if (config.value > limits.max) {
    return {
      valid: false,
      error: `Slippage ${config.value}% is too high for ${tier}-liquidity symbols. Maximum: ${limits.max}%`,
      min: limits.min,
      max: limits.max,
    };
  }

  // Check for obviously wrong values (negative, NaN, Infinity)
  if (!Number.isFinite(config.value) || config.value <= 0) {
    return {
      valid: false,
      error: `Slippage must be a positive number, got: ${config.value}`,
    };
  }

  return { valid: true, min: limits.min, max: limits.max };
}

/**
 * Apply slippage to entry price
 * Used in paper trading executor
 */
export function applySlippage(
  basePrice: number,
  slippagePct: number,
  direction: 'long' | 'short'
): number {
  // Validate input
  const validation = validateSlippage({
    value: slippagePct,
    symbol: 'unknown', // Could pass symbol if needed
    liquidity_tier: 'low', // Conservative default
  });

  if (!validation.valid) {
    throw new Error(`Invalid slippage: ${validation.error}`);
  }

  const slippageMultiplier = 1 + slippagePct / 100;

  if (direction === 'long') {
    // For long entries, slippage moves price up (worse fill)
    return basePrice * slippageMultiplier;
  } else {
    // For short entries, slippage moves price down (better, more to cover)
    return basePrice / slippageMultiplier;
  }
}

/**
 * Get default slippage for a symbol
 */
export async function getDefaultSlippage(
  supabase: any,
  symbolId: string
): Promise<number> {
  const tier = await getLiquidityTier(supabase, symbolId);
  const limits = SLIPPAGE_LIMITS[tier];
  // Return midpoint of range
  return (limits.min + limits.max) / 2;
}
```

**Usage in paper trading executor:**

```typescript
// In supabase/functions/paper-trading-executor/index.ts

import { validateSlippage, getLiquidityTier, applySlippage } from '../_shared/validators/slippage-validator.ts';

async function executePaperTradingCycle(
  supabase: any,
  symbol: string,
  symbolId: string,
  timeframe: string
) {
  // ... get bars ...

  for (const strategy of strategies) {
    // Get symbol's liquidity tier
    const liquidityTier = await getLiquidityTier(supabase, symbolId);

    // Validate user's slippage setting
    const slippageValidation = validateSlippage({
      value: strategy.paper_trading_slippage || 0.2,
      symbol,
      liquidity_tier: liquidityTier,
    });

    if (!slippageValidation.valid) {
      console.error(`[PaperTrading] Invalid slippage for ${symbol}: ${slippageValidation.error}`);
      await logExecution(strategy, symbol, 'error', {
        error: 'Invalid slippage configuration',
        details: slippageValidation,
      });
      continue; // Skip this strategy
    }

    // Apply validated slippage to entry price
    const lastBarClose = bars[bars.length - 1].close;
    const entryPriceWithSlippage = applySlippage(
      lastBarClose,
      slippageValidation.max!, // Use validated upper bound
      'long'
    );

    if (entrySignal && !openPosition) {
      await createPaperPosition(strategy, symbol, entryPriceWithSlippage, quantity);
    }
  }
}
```

---

## 3. Position Size Validation

**File:** `supabase/functions/_shared/validators/position-validator.ts`

```typescript
/**
 * Position Size Validator
 * Prevents unrealistic position sizes that could cause P&L manipulation
 */

export interface PositionInput {
  entry_price: number;
  quantity: number;
  symbol: string;
  account_capital: number;
}

export interface PositionLimits {
  min_quantity: number;
  max_quantity: number;
  min_entry_price: number;
  max_entry_price: number;
  max_position_pct: number; // Maximum position size as % of account
}

export interface ValidationError {
  field: string;
  message: string;
  code: string;
}

// Default limits (can be configured per strategy)
export const DEFAULT_POSITION_LIMITS: PositionLimits = {
  min_quantity: 1,
  max_quantity: 100000,
  min_entry_price: 0.01,      // Penny stocks minimum
  max_entry_price: 1000000,   // $1M per share maximum
  max_position_pct: 10,       // Max 10% of account per position
};

/**
 * Validate position size and entry price
 */
export function validatePosition(
  position: PositionInput,
  limits: PositionLimits = DEFAULT_POSITION_LIMITS
): ValidationError[] {
  const errors: ValidationError[] = [];

  // Validate entry price
  if (!Number.isFinite(position.entry_price) || position.entry_price <= 0) {
    errors.push({
      field: 'entry_price',
      message: `Entry price must be a positive number, got: ${position.entry_price}`,
      code: 'INVALID_ENTRY_PRICE',
    });
  } else if (position.entry_price < limits.min_entry_price) {
    errors.push({
      field: 'entry_price',
      message: `Entry price must be at least $${limits.min_entry_price}, got: $${position.entry_price}`,
      code: 'ENTRY_PRICE_TOO_LOW',
    });
  } else if (position.entry_price > limits.max_entry_price) {
    errors.push({
      field: 'entry_price',
      message: `Entry price must not exceed $${limits.max_entry_price}, got: $${position.entry_price}`,
      code: 'ENTRY_PRICE_TOO_HIGH',
    });
  }

  // Validate quantity
  if (!Number.isInteger(position.quantity) || position.quantity <= 0) {
    errors.push({
      field: 'quantity',
      message: `Quantity must be a positive integer, got: ${position.quantity}`,
      code: 'INVALID_QUANTITY',
    });
  } else if (position.quantity < limits.min_quantity) {
    errors.push({
      field: 'quantity',
      message: `Quantity must be at least ${limits.min_quantity}, got: ${position.quantity}`,
      code: 'QUANTITY_TOO_SMALL',
    });
  } else if (position.quantity > limits.max_quantity) {
    errors.push({
      field: 'quantity',
      message: `Quantity must not exceed ${limits.max_quantity}, got: ${position.quantity}`,
      code: 'QUANTITY_TOO_LARGE',
    });
  }

  // Validate position size vs account capital
  const positionValue = position.entry_price * position.quantity;
  const maxPositionValue = position.account_capital * (limits.max_position_pct / 100);

  if (positionValue > maxPositionValue) {
    errors.push({
      field: 'quantity',
      message: `Position size $${positionValue.toFixed(2)} exceeds max ${limits.max_position_pct}% of account ` +
               `($${maxPositionValue.toFixed(2)}). Reduce quantity or increase account capital.`,
      code: 'POSITION_SIZE_EXCEEDS_CAPITAL',
    });
  }

  // Validate account capital itself
  if (!Number.isFinite(position.account_capital) || position.account_capital <= 0) {
    errors.push({
      field: 'account_capital',
      message: `Account capital must be positive, got: ${position.account_capital}`,
      code: 'INVALID_ACCOUNT_CAPITAL',
    });
  }

  return errors;
}

/**
 * Calculate maximum quantity for a given entry price and account capital
 */
export function calculateMaxQuantity(
  entryPrice: number,
  accountCapital: number,
  limits: PositionLimits = DEFAULT_POSITION_LIMITS
): number {
  const maxValue = accountCapital * (limits.max_position_pct / 100);
  const maxQty = Math.floor(maxValue / entryPrice);
  return Math.min(maxQty, limits.max_quantity);
}

/**
 * Calculate position value
 */
export function calculatePositionValue(
  entryPrice: number,
  quantity: number
): number {
  return entryPrice * quantity;
}
```

**Database constraints to add:**

```sql
-- File: supabase/migrations/20260226000001_position_constraints.sql

-- Add constraints to paper_trading_positions table
ALTER TABLE paper_trading_positions
  ADD CONSTRAINT entry_price_positive CHECK (entry_price > 0),
  ADD CONSTRAINT entry_price_reasonable CHECK (entry_price <= 1000000),
  ADD CONSTRAINT quantity_positive CHECK (quantity > 0),
  ADD CONSTRAINT quantity_reasonable CHECK (quantity <= 100000),
  ADD CONSTRAINT tp_gt_entry CHECK (take_profit_price IS NULL OR take_profit_price > entry_price),
  ADD CONSTRAINT sl_lt_entry CHECK (stop_loss_price IS NULL OR stop_loss_price < entry_price);

-- Add constraints to paper_trading_trades table
ALTER TABLE paper_trading_trades
  ADD CONSTRAINT entry_price_positive CHECK (entry_price > 0),
  ADD CONSTRAINT exit_price_positive CHECK (exit_price > 0),
  ADD CONSTRAINT quantity_positive CHECK (quantity > 0);
```

**Usage in executor:**

```typescript
// In paper-trading-executor/index.ts

import { validatePosition, DEFAULT_POSITION_LIMITS, calculateMaxQuantity } from '../_shared/validators/position-validator.ts';

async function createPaperPosition(
  strategy: any,
  symbol: string,
  entryPrice: number,
  quantity: number,
  supabase: any
): Promise<void> {
  // Validate position before creating
  const errors = validatePosition(
    {
      entry_price: entryPrice,
      quantity,
      symbol,
      account_capital: strategy.paper_capital,
    },
    DEFAULT_POSITION_LIMITS
  );

  if (errors.length > 0) {
    console.error(`[PaperTrading] Position validation failed:`, errors);
    await logExecution(strategy, symbol, 'error', {
      error: 'Position validation failed',
      details: errors,
    });
    return; // Skip position creation
  }

  // Safe to create position
  const { error } = await supabase
    .from('paper_trading_positions')
    .insert({
      user_id: strategy.user_id,
      strategy_id: strategy.id,
      symbol_id: symbol,
      entry_price: entryPrice,
      quantity,
      entry_time: new Date().toISOString(),
      direction: 'long',
      status: 'open',
      current_price: entryPrice, // Start with entry price
    });

  if (error) {
    console.error(`[PaperTrading] Failed to insert position:`, error);
    await logExecution(strategy, symbol, 'error', {
      error: 'Failed to create position',
      details: error,
    });
  }
}
```

---

## 4. Remove Demo User Fallback

**File:** `supabase/functions/backtest-strategy/index.ts`

**BEFORE:**
```typescript
let userId = getUserIdFromRequest(req);
if (!userId) {
  userId = "00000000-0000-0000-0000-000000000001"; // demo fallback ❌ WRONG
}
```

**AFTER:**
```typescript
const userId = getUserIdFromRequest(req);
if (!userId) {
  return corsResponse(
    { error: "Unauthorized: valid JWT required" },
    401,
    origin
  );
}
// Continue with authenticated userId
```

Apply this pattern to **all** paper trading endpoints:
- `paper-trading-executor/index.ts`
- `paper-trading-dashboard/index.ts`
- `strategy-condition-builder/index.ts`
- Any other user-specific endpoints

---

## 5. Market Data Source Validation

**File:** `supabase/functions/_shared/validators/market-data-validator.ts`

```typescript
/**
 * Market Data Validator
 * Ensures paper trading only uses verified market data, not forecasts
 */

export interface MarketBar {
  symbol_id: string;
  timeframe: string;
  ts: Date;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  provider: string;
  is_forecast: boolean;
  is_intraday: boolean;
  data_status: string;
  confidence_score?: number;
}

/**
 * Validate market bar for use in trading signals
 */
export function validateMarketBarForSignal(bar: MarketBar): { valid: boolean; error?: string } {
  // CRITICAL: Cannot use forecasts for live signals
  if (bar.is_forecast) {
    return {
      valid: false,
      error: `Cannot use forecast data for trading signals. Bar from ${bar.provider} is marked as forecast.`,
    };
  }

  // Must be verified or live market data
  if (bar.data_status && !['verified', 'live'].includes(bar.data_status)) {
    return {
      valid: false,
      error: `Data status "${bar.data_status}" not suitable for signals. Require "verified" or "live".`,
    };
  }

  // Validate OHLC values
  if (!Number.isFinite(bar.open) || bar.open <= 0) {
    return { valid: false, error: `Invalid open price: ${bar.open}` };
  }

  if (!Number.isFinite(bar.high) || bar.high <= 0) {
    return { valid: false, error: `Invalid high price: ${bar.high}` };
  }

  if (!Number.isFinite(bar.low) || bar.low <= 0) {
    return { valid: false, error: `Invalid low price: ${bar.low}` };
  }

  if (!Number.isFinite(bar.close) || bar.close <= 0) {
    return { valid: false, error: `Invalid close price: ${bar.close}` };
  }

  // High should be >= low
  if (bar.high < bar.low) {
    return { valid: false, error: `High (${bar.high}) < Low (${bar.low})` };
  }

  // Volume should be non-negative
  if (typeof bar.volume === 'number' && bar.volume < 0) {
    return { valid: false, error: `Invalid volume: ${bar.volume}` };
  }

  // Check for future dates (lookahead bias)
  const barTime = new Date(bar.ts);
  const now = new Date();
  if (barTime > now) {
    return { valid: false, error: `Future-dated bar detected: ${bar.ts}` };
  }

  return { valid: true };
}

/**
 * Fetch latest bars for trading signals (safe version)
 * Only returns verified market data, never forecasts
 */
export async function fetchBarsForSignalEvaluation(
  supabase: any,
  symbolId: string,
  timeframe: string,
  limit: number = 100
): Promise<MarketBar[]> {
  const { data: bars, error } = await supabase
    .from('ohlc_bars_v2')
    .select('*')
    .eq('symbol_id', symbolId)
    .eq('timeframe', timeframe)
    .eq('is_forecast', false)           // CRITICAL: Exclude all forecasts
    .in('data_status', ['verified', 'live']) // Only verified/live data
    .in('provider', ['alpaca', 'polygon', 'yfinance', 'tradier']) // Trusted providers
    .order('ts', { ascending: false })
    .limit(limit);

  if (error) {
    throw new Error(`Failed to fetch market data: ${error.message}`);
  }

  if (!bars || bars.length === 0) {
    throw new Error(`No market data available for ${symbolId}:${timeframe}`);
  }

  // Validate each bar
  for (const bar of bars) {
    const validation = validateMarketBarForSignal(bar);
    if (!validation.valid) {
      throw new Error(`Invalid market bar: ${validation.error}`);
    }
  }

  // Return in chronological order (oldest first)
  return bars.reverse();
}
```

**Usage in executor:**

```typescript
// In paper-trading-executor/index.ts

import { fetchBarsForSignalEvaluation } from '../_shared/validators/market-data-validator.ts';

async function executePaperTradingCycle(
  supabase: any,
  symbol: string,
  symbolId: string,
  timeframe: string
) {
  try {
    // Fetch only verified market data (no forecasts)
    const bars = await fetchBarsForSignalEvaluation(supabase, symbolId, timeframe, 100);

    // Rest of executor logic uses safe bars
    // ...
  } catch (error) {
    console.error(`[PaperTrading] Data validation failed: ${error.message}`);
    // Alert user, don't execute strategy with bad data
  }
}
```

---

## 6. Stop Loss / Take Profit Validation

**File:** `supabase/functions/_shared/validators/risk-validator.ts`

```typescript
/**
 * Risk Parameter Validator
 * Ensures SL/TP values are realistic
 */

export interface RiskParameters {
  stop_loss_pct: number;
  take_profit_pct: number;
}

export interface ValidationError {
  field: string;
  message: string;
  code: string;
}

// Risk limits (in percentage)
export const RISK_LIMITS = {
  stop_loss_pct: { min: 0.5, max: 50 },    // 0.5% to 50%
  take_profit_pct: { min: 0.5, max: 500 }, // 0.5% to 500%
};

/**
 * Validate stop loss and take profit percentages
 */
export function validateRiskParameters(params: RiskParameters): ValidationError[] {
  const errors: ValidationError[] = [];

  // Validate stop loss
  if (!Number.isFinite(params.stop_loss_pct) || params.stop_loss_pct <= 0) {
    errors.push({
      field: 'stop_loss_pct',
      message: `Stop loss must be a positive number, got: ${params.stop_loss_pct}`,
      code: 'INVALID_STOP_LOSS',
    });
  } else if (params.stop_loss_pct < RISK_LIMITS.stop_loss_pct.min) {
    errors.push({
      field: 'stop_loss_pct',
      message: `Stop loss ${params.stop_loss_pct}% is too tight. Minimum: ${RISK_LIMITS.stop_loss_pct.min}%`,
      code: 'STOP_LOSS_TOO_TIGHT',
    });
  } else if (params.stop_loss_pct > RISK_LIMITS.stop_loss_pct.max) {
    errors.push({
      field: 'stop_loss_pct',
      message: `Stop loss ${params.stop_loss_pct}% is too loose. Maximum: ${RISK_LIMITS.stop_loss_pct.max}%`,
      code: 'STOP_LOSS_TOO_LOOSE',
    });
  }

  // Validate take profit
  if (!Number.isFinite(params.take_profit_pct) || params.take_profit_pct <= 0) {
    errors.push({
      field: 'take_profit_pct',
      message: `Take profit must be a positive number, got: ${params.take_profit_pct}`,
      code: 'INVALID_TAKE_PROFIT',
    });
  } else if (params.take_profit_pct < RISK_LIMITS.take_profit_pct.min) {
    errors.push({
      field: 'take_profit_pct',
      message: `Take profit ${params.take_profit_pct}% is too tight. Minimum: ${RISK_LIMITS.take_profit_pct.min}%`,
      code: 'TAKE_PROFIT_TOO_TIGHT',
    });
  } else if (params.take_profit_pct > RISK_LIMITS.take_profit_pct.max) {
    errors.push({
      field: 'take_profit_pct',
      message: `Take profit ${params.take_profit_pct}% is too high. Maximum: ${RISK_LIMITS.take_profit_pct.max}%`,
      code: 'TAKE_PROFIT_TOO_HIGH',
    });
  }

  // Validate ratio: TP must be > SL
  if (params.take_profit_pct <= params.stop_loss_pct) {
    errors.push({
      field: 'risk_ratio',
      message: `Take profit (${params.take_profit_pct}%) must be greater than stop loss (${params.stop_loss_pct}%)`,
      code: 'INVALID_RISK_RATIO',
    });
  }

  return errors;
}

/**
 * Calculate stop loss and take profit prices from percentages
 */
export function calculatePrices(
  entryPrice: number,
  sl_pct: number,
  tp_pct: number,
  direction: 'long' | 'short'
): { stop_loss_price: number; take_profit_price: number } {
  if (direction === 'long') {
    return {
      stop_loss_price: entryPrice * (1 - sl_pct / 100),
      take_profit_price: entryPrice * (1 + tp_pct / 100),
    };
  } else {
    return {
      stop_loss_price: entryPrice * (1 + sl_pct / 100),
      take_profit_price: entryPrice * (1 - tp_pct / 100),
    };
  }
}
```

---

## 7. Testing Utilities

**File:** `supabase/functions/__tests__/security-validators.test.ts`

```typescript
import { assertEquals, assertThrows } from "https://deno.land/std@0.208.0/assert/mod.ts";

import { validateSlippage } from '../_shared/validators/slippage-validator.ts';
import { validatePosition, calculateMaxQuantity } from '../_shared/validators/position-validator.ts';
import { validateMarketBarForSignal } from '../_shared/validators/market-data-validator.ts';
import { validateRiskParameters } from '../_shared/validators/risk-validator.ts';

Deno.test("Slippage Validator", async (t) => {
  await t.step("accepts valid slippage for high liquidity", () => {
    const result = validateSlippage({
      value: 0.2,
      symbol: 'AAPL',
      liquidity_tier: 'high',
    });
    assertEquals(result.valid, true);
  });

  await t.step("rejects slippage too low", () => {
    const result = validateSlippage({
      value: 0.01,
      symbol: 'AAPL',
      liquidity_tier: 'high',
    });
    assertEquals(result.valid, false);
  });

  await t.step("rejects slippage too high", () => {
    const result = validateSlippage({
      value: 10.0,
      symbol: 'AAPL',
      liquidity_tier: 'high',
    });
    assertEquals(result.valid, false);
  });
});

Deno.test("Position Validator", async (t) => {
  await t.step("accepts valid position", () => {
    const errors = validatePosition({
      entry_price: 150.5,
      quantity: 100,
      symbol: 'AAPL',
      account_capital: 50000,
    });
    assertEquals(errors.length, 0);
  });

  await t.step("rejects zero entry price", () => {
    const errors = validatePosition({
      entry_price: 0,
      quantity: 100,
      symbol: 'AAPL',
      account_capital: 50000,
    });
    assertEquals(errors.length > 0, true);
    assertEquals(errors[0].code, 'INVALID_ENTRY_PRICE');
  });

  await t.step("rejects position exceeding capital limit", () => {
    const errors = validatePosition({
      entry_price: 500,
      quantity: 1000,
      symbol: 'AAPL',
      account_capital: 10000, // $500 * 1000 = $500k > 10% of $10k
    });
    assertEquals(errors.some(e => e.code === 'POSITION_SIZE_EXCEEDS_CAPITAL'), true);
  });

  await t.step("calculates max quantity correctly", () => {
    const maxQty = calculateMaxQuantity(150, 50000);
    // Max = $50,000 * 10% / $150 = $5,000 / $150 = 33 shares
    assertEquals(maxQty, 33);
  });
});

Deno.test("Market Data Validator", async (t) => {
  await t.step("rejects forecast data for signals", () => {
    const result = validateMarketBarForSignal({
      symbol_id: 'AAPL-uuid',
      timeframe: 'd1',
      ts: new Date('2026-02-20'),
      open: 150,
      high: 155,
      low: 149,
      close: 153,
      volume: 1000000,
      provider: 'ml_forecast',
      is_forecast: true,  // ❌ Forecast data
      is_intraday: false,
      data_status: 'verified',
    });
    assertEquals(result.valid, false);
    assertEquals(result.error?.includes('forecast'), true);
  });

  await t.step("rejects future-dated bars", () => {
    const futureDate = new Date();
    futureDate.setDate(futureDate.getDate() + 1); // Tomorrow
    const result = validateMarketBarForSignal({
      symbol_id: 'AAPL-uuid',
      timeframe: 'd1',
      ts: futureDate,
      open: 150,
      high: 155,
      low: 149,
      close: 153,
      volume: 1000000,
      provider: 'alpaca',
      is_forecast: false,
      is_intraday: false,
      data_status: 'live',
    });
    assertEquals(result.valid, false);
    assertEquals(result.error?.includes('Future'), true);
  });

  await t.step("accepts verified Alpaca data", () => {
    const result = validateMarketBarForSignal({
      symbol_id: 'AAPL-uuid',
      timeframe: 'd1',
      ts: new Date('2026-02-20'),
      open: 150,
      high: 155,
      low: 149,
      close: 153,
      volume: 1000000,
      provider: 'alpaca',
      is_forecast: false,
      is_intraday: false,
      data_status: 'verified',
    });
    assertEquals(result.valid, true);
  });
});

Deno.test("Risk Parameter Validator", async (t) => {
  await t.step("accepts valid SL/TP", () => {
    const errors = validateRiskParameters({
      stop_loss_pct: 2,
      take_profit_pct: 5,
    });
    assertEquals(errors.length, 0);
  });

  await t.step("rejects SL >= TP", () => {
    const errors = validateRiskParameters({
      stop_loss_pct: 5,
      take_profit_pct: 2,
    });
    assertEquals(errors.some(e => e.code === 'INVALID_RISK_RATIO'), true);
  });

  await t.step("rejects SL outside limits", () => {
    const errors = validateRiskParameters({
      stop_loss_pct: 0.1, // Too tight
      take_profit_pct: 5,
    });
    assertEquals(errors.some(e => e.code === 'STOP_LOSS_TOO_TIGHT'), true);
  });
});
```

---

## Implementation Checklist

Copy this checklist into your project management tool:

- [ ] Create migration `20260226000000_paper_trading_rls_policies.sql`
- [ ] Create `supabase/functions/_shared/validators/slippage-validator.ts`
- [ ] Create `supabase/functions/_shared/validators/position-validator.ts`
- [ ] Create `supabase/functions/_shared/validators/market-data-validator.ts`
- [ ] Create `supabase/functions/_shared/validators/risk-validator.ts`
- [ ] Update `paper-trading-executor/index.ts` to use validators
- [ ] Update `backtest-strategy/index.ts` to remove demo fallback
- [ ] Create test file `__tests__/security-validators.test.ts`
- [ ] Run `deno test` to verify all validators
- [ ] Code review all validators with security team
- [ ] Deploy migration to production
- [ ] Monitor for validation errors in logs

**Total Implementation Time:** 15-20 hours (2-3 days)

---

## Next Steps

1. **Review:** Share this document with team
2. **Discuss:** Answer the 5 questions in Executive Summary
3. **Implement:** Start with FIX 1 (RLS policies) - fastest win
4. **Test:** Run security test suite
5. **Deploy:** Stage → Production with monitoring
