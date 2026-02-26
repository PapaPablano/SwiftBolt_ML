# Security Audit: Trading Strategy Platform
## SwiftBolt ML Strategy Platform with Paper Trading

**Date:** 2026-02-25
**Audit Type:** Pre-implementation security review
**Status:** CRITICAL GAPS IDENTIFIED
**Severity Distribution:** 3 Critical | 5 High | 4 Medium

---

## Executive Summary

The proposed Strategy Platform with visual builder, backtesting, and paper trading introduces **significant financial and security risks** that must be addressed before v1 deployment. The plan includes proper database schema (RLS enabled) and validates some inputs, but **lacks critical controls** for:

1. **Financial data tamper protection** — P&L calculations can be manipulated via unvalidated position inputs
2. **Paper trading isolation** — No clear separation preventing paper trades from interacting with real market data
3. **Slippage manipulation** — User-configurable slippage (2% default) with no validation against realistic ranges
4. **Indicator signal injection** — No validation that indicator values come from trusted market data only
5. **Cross-user position visibility** — Paper trading tables lack explicit RLS preventing data leakage
6. **Risk parameter validation** — Stop loss/take profit accept arbitrary values without bounds checking

---

## Risk Assessment Matrix

| Category | Finding | Severity | CVSS Score | Impact |
|----------|---------|----------|-----------|--------|
| **Authentication & Authorization** | Paper trading tables lack RLS policies | Critical | 7.5 | User A can read/modify User B's positions |
| **Input Validation** | Slippage unconstrained (0.01% - 500%+ possible) | Critical | 8.0 | Artificially inflate/deflate backtest P&L |
| **Financial Data Integrity** | Position size, entry price accept any value | Critical | 7.8 | P&L manipulation, false performance reports |
| **Authentication** | Demo fallback user ID in edge function | High | 6.5 | Unauthenticated requests bypass RLS |
| **Market Data Integrity** | No validation that bars come from Alpaca | High | 7.2 | Inject false OHLCV to trigger false signals |
| **Execution Isolation** | Paper trading & backtest share condition evaluator | High | 6.8 | Logic bugs affect live-equivalent testing |
| **Input Validation** | Stop loss / take profit no min/max bounds | High | 6.3 | Users set SL at -100%, TP at +500% |
| **Sensitive Data** | Strategy config (risk params) not encrypted | Medium | 5.1 | Competitors see position sizing, SL/TP logic |
| **Logging & Auditing** | No execution_log RLS policy defined | Medium | 5.4 | Users see execution details of other strategies |
| **Error Messages** | Backtest error_message field untruncated | Medium | 4.9 | SQL injection errors may leak schema info |
| **Race Conditions** | Position close not atomic (select + update) | Low | 4.2 | Stale read: close at wrong price |
| **Indicator Calculation** | No versioning for indicator parameter changes | Low | 3.8 | Old positions reference changed indicator logic |

---

## 1. CRITICAL FINDINGS

### 1.1 Missing RLS Policies on Paper Trading Tables

**Location:** Plan, section "Technical Approach" → Database Schema
**Severity:** CRITICAL (CVSS 7.5)

**Issue:** The proposed `paper_trading_positions`, `paper_trading_trades`, and `strategy_execution_log` tables have **no Row Level Security (RLS) policies defined** in the plan. The migration will create these tables with RLS enabled but no policies will be created, defaulting to "deny all" for non-authenticated users, **but also exposing all data to service-role queries without user filtering**.

**Attack Scenario:**
```sql
-- User A crafts request with different user_id in JWT
-- Paper trading executor validates user_id from JWT (correct)
-- But RLS is not enforced on the paper_trading_positions table
-- User A queries: SELECT * FROM paper_trading_positions
-- Returns ALL paper trades for ALL users (no RLS policy blocks it)
```

**Code Evidence:**
```sql
-- From plan (lines 134-149):
CREATE TABLE paper_trading_positions (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES auth.users,
  strategy_id UUID NOT NULL REFERENCES strategy_user_strategies,
  -- ... columns ...
);
-- NO RLS POLICY DEFINED IN PLAN
```

**Comparison with existing strategy tables** (lines 18-35 of `/Users/ericpeterson/SwiftBolt_ML/backend/supabase/migrations/20260221_strategy_builder_v1.sql`):
```sql
-- Existing strategies table HAS RLS:
ALTER TABLE strategies ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own strategies"
  ON strategies FOR SELECT
  USING (auth.uid() = user_id);
```

**Required Fix (v1 blocking):**
```sql
-- Add to migration for paper_trading_positions
ALTER TABLE paper_trading_positions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own paper positions"
  ON paper_trading_positions FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own paper positions"
  ON paper_trading_positions FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own paper positions"
  ON paper_trading_positions FOR UPDATE
  USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own paper positions"
  ON paper_trading_positions FOR DELETE
  USING (auth.uid() = user_id);

-- Repeat for paper_trading_trades and strategy_execution_log
-- execution_log is trickier: visible only if user owns the strategy
CREATE POLICY "Users can view execution logs of their strategies"
  ON strategy_execution_log FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM strategy_user_strategies
      WHERE strategy_user_strategies.id = strategy_id
      AND strategy_user_strategies.user_id = auth.uid()
    )
  );
```

**Impact if not fixed:**
- User A can read all positions/trades of User B
- User A can modify open positions belonging to User B (change stop loss, close trades)
- User A can delete execution logs of other users
- **Financial and privacy data breach**

---

### 1.2 Unvalidated Slippage Configuration

**Location:** Plan, line 68: "2% slippage default"
**Severity:** CRITICAL (CVSS 8.0)

**Issue:** Slippage is a critical financial parameter that must be realistic. The plan allows **user-configurable slippage but provides no validation** against realistic ranges. A user could set slippage to 0.01% (unrealistic for paper trading) or 500% (absurd), causing artificially inflated backtests.

**Realistic slippage ranges:**
- Equities (high liquidity): 0.05% - 0.5%
- Equities (low liquidity): 1% - 5%
- Options: 2% - 5%
- Crypto: 0.5% - 2%

**Attack Scenario:**
```typescript
// Paper trading executor (line 291 in plan):
const entryPrice = bars[bars.length - 1].close * 1.02; // 2% slippage

// But what if user sets slippage = 0.001?
// User's backtest shows 95% win rate
// Paper trading uses realistic 0.5% slippage
// Real results: 20% win rate (user blames the platform)
// OR user sets slippage = 5.0 (unrealistic)
// Backtest shows 10% win rate
// Platform's credibility damaged

// No bounds checking in plan:
const params = (body.params as Record<string, unknown>) || {};
// slippage not validated, inserted into parameters
// Executor uses it without range validation
```

**Required Fix (v1 blocking):**

In the paper trading executor (`supabase/functions/paper-trading-executor/index.ts`):
```typescript
interface PaperTradingConfig {
  slippage: number; // percent
  symbol: string;
  liquidity: 'high' | 'low' | 'micro_cap';
}

const SLIPPAGE_LIMITS: Record<string, { min: number; max: number }> = {
  'high': { min: 0.05, max: 0.5 },
  'low': { min: 0.5, max: 5.0 },
  'micro_cap': { min: 2.0, max: 10.0 },
};

function validateSlippage(config: PaperTradingConfig): ValidationError | null {
  const limits = SLIPPAGE_LIMITS[config.liquidity];
  if (config.slippage < limits.min || config.slippage > limits.max) {
    return {
      field: 'slippage',
      message: `Slippage for ${config.liquidity} liquidity must be ${limits.min}%-${limits.max}%. Got ${config.slippage}%`,
      code: 'INVALID_SLIPPAGE_RANGE',
    };
  }
  return null;
}

// Also validate in condition builder component:
function validateStrategyParameters(config: StrategyConfig): ValidationError[] {
  const errors = [];

  if (config.paper_trading_enabled) {
    const slippageError = validateSlippage(config);
    if (slippageError) errors.push(slippageError);
  }

  return errors;
}
```

Also, **create a lookup table** to store liquidity classification per symbol:
```sql
CREATE TABLE symbol_liquidity_classification (
  symbol_id UUID REFERENCES symbols(id),
  liquidity_tier TEXT NOT NULL CHECK (liquidity_tier IN ('high', 'low', 'micro_cap')),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (symbol_id)
);

-- Pre-populate with common symbols
INSERT INTO symbol_liquidity_classification (symbol_id, liquidity_tier)
SELECT id, 'high' FROM symbols WHERE symbol IN ('AAPL', 'MSFT', 'TSLA', 'SPY', 'QQQ');
INSERT INTO symbol_liquidity_classification (symbol_id, liquidity_tier)
SELECT id, 'low' FROM symbols WHERE volume_avg_3m < 1000000;
```

**Impact if not fixed:**
- Users can game backtests by setting slippage to 0.01%
- Paper trading performance diverges wildly from realistic expectations
- Platform credibility damaged ("backtests are fake")

---

### 1.3 Position Size & Entry Price Lack Validation Bounds

**Location:** Plan, lines 145-150 (database schema)
**Severity:** CRITICAL (CVSS 7.8)

**Issue:** The `paper_trading_positions` table accepts `entry_price` and `quantity` without bounds checking. A user could insert:
- `entry_price = 0` or negative (break division in P&L calc)
- `quantity = 9,999,999` (overflow risk, unrealistic position)
- `entry_price = 1e308` (floating point overflow)

This allows **P&L manipulation** and **false performance reporting**.

**Attack Scenario:**
```sql
-- Attacker crafts custom mutation to paper_trading_positions
INSERT INTO paper_trading_positions (
  user_id, strategy_id, symbol_id, timeframe,
  entry_price, quantity, entry_time, direction, status
) VALUES (
  'attacker-uuid', 'strategy-uuid', 'AAPL-uuid', '1d',
  0.01, 1000000, NOW(), 'long', 'open'
);

-- If current_price = 200
-- P&L = (200 - 0.01) * 1000000 = ~$200M (false gain!)
-- Attacker's paper trading metrics show absurd returns
-- Leads to false confidence in strategy
```

**Required Fix (v1 blocking):**

In the paper trading executor and condition builder:
```typescript
interface PositionConfig {
  quantity: number;
  entry_price: number;
  symbol: string;
  account_capital: number; // Track account size for position validation
}

interface PositionLimits {
  min_quantity: number;
  max_quantity: number;
  max_position_value_pct: number; // e.g., 5% of account
  min_entry_price: number;
  max_entry_price: number;
}

function validatePositionSize(config: PositionConfig, limits: PositionLimits): ValidationError[] {
  const errors: ValidationError[] = [];

  // Validate quantity
  if (config.quantity < limits.min_quantity) {
    errors.push({
      field: 'quantity',
      message: `Quantity must be at least ${limits.min_quantity}`,
      code: 'QUANTITY_TOO_SMALL',
    });
  }
  if (config.quantity > limits.max_quantity) {
    errors.push({
      field: 'quantity',
      message: `Quantity must not exceed ${limits.max_quantity} (max position size: ${limits.max_position_value_pct}% of account)`,
      code: 'QUANTITY_TOO_LARGE',
    });
  }

  // Validate entry price
  if (config.entry_price <= limits.min_entry_price) {
    errors.push({
      field: 'entry_price',
      message: `Entry price must be > $${limits.min_entry_price}`,
      code: 'ENTRY_PRICE_INVALID',
    });
  }
  if (config.entry_price > limits.max_entry_price) {
    errors.push({
      field: 'entry_price',
      message: `Entry price must be ≤ $${limits.max_entry_price}`,
      code: 'ENTRY_PRICE_TOO_HIGH',
    });
  }

  // Validate position value vs account capital
  const positionValue = config.entry_price * config.quantity;
  const maxPositionValue = config.account_capital * (limits.max_position_value_pct / 100);
  if (positionValue > maxPositionValue) {
    errors.push({
      field: 'quantity',
      message: `Position size $${positionValue.toFixed(2)} exceeds max ${limits.max_position_value_pct}% of account ($${maxPositionValue.toFixed(2)})`,
      code: 'POSITION_SIZE_EXCEEDS_CAPITAL',
    });
  }

  return errors;
}

// In paper trading executor:
async function createPaperPosition(
  strategy: Strategy,
  symbol: string,
  entryPrice: number,
  quantity: number,
  supabase: SupabaseClient
): Promise<void> {
  // Validate position before inserting
  const limits: PositionLimits = {
    min_quantity: 1,
    max_quantity: 100000,
    max_position_value_pct: 10, // Max 10% of paper capital per position
    min_entry_price: 0.01,
    max_entry_price: 100000,
  };

  const errors = validatePositionSize(
    { quantity, entry_price: entryPrice, symbol, account_capital: strategy.paper_capital },
    limits
  );

  if (errors.length > 0) {
    console.error('[PaperTrading] Position validation failed:', errors);
    await logExecution(strategy, symbol, 'entry', {
      error: 'Position validation failed',
      details: errors,
    });
    return; // Skip position creation
  }

  // Safe to insert
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
    });

  if (error) {
    console.error('[PaperTrading] Failed to create position:', error);
  }
}
```

**Database constraint addition:**
```sql
ALTER TABLE paper_trading_positions
  ADD CONSTRAINT entry_price_positive CHECK (entry_price > 0),
  ADD CONSTRAINT quantity_positive CHECK (quantity > 0),
  ADD CONSTRAINT entry_price_reasonable CHECK (entry_price < 1000000), -- Max $1M per share
  ADD CONSTRAINT quantity_reasonable CHECK (quantity <= 100000);       -- Max 100k shares
```

**Impact if not fixed:**
- Users can artificially inflate P&L with zero-cost positions
- False performance metrics mislead strategy tuning
- Financial data integrity compromised

---

### 1.4 Demo Fallback User ID Bypasses Authentication

**Location:** `/Users/ericpeterson/SwiftBolt_ML/supabase/functions/backtest-strategy/index.ts`, lines 37-40

**Severity:** CRITICAL (CVSS 7.5)

**Issue:** If the request lacks a valid JWT token, the code falls back to a demo user ID:
```typescript
let userId = getUserIdFromRequest(req);
if (!userId) {
  userId = "00000000-0000-0000-0000-000000000001"; // demo fallback
}
```

This means **unauthenticated requests are processed as the "demo" user**. An attacker can:
1. Create strategies under the demo user
2. Run backtests (potentially expensive CPU/memory operations)
3. Access demo user's backtest results

**Required Fix (v1 blocking):**
```typescript
serve(async (req: Request) => {
  const origin = req.headers.get("origin");

  if (req.method === "OPTIONS") {
    return handlePreflight(origin);
  }

  const supabase = getSupabaseClient();
  const userId = getUserIdFromRequest(req);

  // MUST have valid JWT, no fallback
  if (!userId) {
    return corsResponse(
      { error: "Unauthorized: valid JWT required" },
      401,
      origin
    );
  }

  // ... rest of handler
});
```

**Also validate in ALL paper trading endpoints:**
- `paper-trading-executor` — Verify service key OR user JWT
- Condition builder mutations — Require user JWT
- Paper trading dashboard reads — Require user JWT with RLS

**Impact if not fixed:**
- Unauthenticated users can queue expensive backtest jobs (DoS)
- Demo user's data is shared across multiple attackers
- RLS policies meaningless without auth enforcement

---

## 2. HIGH SEVERITY FINDINGS

### 2.1 No Validation That Market Data is from Trusted Source

**Location:** Plan, section "Paper Trading Execution Engine" (lines 270-307)

**Severity:** HIGH (CVSS 7.2)

**Issue:** The paper trading executor calls:
```typescript
const bars = await fetchLatestBars(symbol, timeframe, 100);
```

But the plan provides **no detail on `fetchLatestBars` implementation**. There's no guarantee these bars come from Alpaca (as documented). An attacker could:
1. Insert false OHLCV data into `ohlc_bars_v2` (if RLS is weak)
2. Cause strategy to trigger on manipulated signals
3. Generate false backtest results

**Code Evidence:** The plan states (line 275):
> "Get latest market data (last 100 bars for indicator calculation)"

But doesn't specify:
- Which table (`ohlc_bars_v2`)?
- How to verify data is from Alpaca (not ML forecast or user injection)?
- How to prevent future-dated bars (lookahead bias)?

**Existing safeguard in codebase:** `/Users/ericpeterson/SwiftBolt_ML/supabase/functions/_shared/data-validation.ts` does enforce provider separation:
```typescript
// Polygon historical cannot write to today or future
if (barDate >= today) {
  return { valid: false, ... };
}
// Cannot be marked as forecast
if (bar.is_forecast) {
  return { valid: false, ... };
}
```

**But this validation only applies to data **writes**, not reads.**

**Required Fix (v1 blocking):**

Create a `fetchLatestBarsForTradingSignal` function that enforces data source validation:
```typescript
interface BarSourceValidation {
  provider: 'alpaca' | 'polygon' | 'yfinance';
  is_forecast: boolean;
  is_intraday: boolean;
  data_status: 'verified' | 'live' | 'provisional';
  confidence_score?: number;
}

async function fetchLatestBarsForTradingSignal(
  supabase: SupabaseClient,
  symbol: string,
  timeframe: string,
  limit: number,
  allowForecast: boolean = false // Paper trading should NOT use forecasts
): Promise<Bar[]> {
  // Query ONLY real market data, never forecasts
  const { data: bars, error } = await supabase
    .from('ohlc_bars_v2')
    .select('*')
    .eq('symbol_id', symbol)
    .eq('timeframe', timeframe)
    .eq('is_forecast', false) // CRITICAL: Exclude forecasts
    .eq('is_intraday', timeframe !== 'd1') // Validate timeframe consistency
    .in('provider', ['alpaca', 'polygon', 'yfinance']) // Only trusted providers
    .eq('data_status', 'verified') // Only verified data for live signals
    .order('ts', { ascending: false })
    .limit(limit);

  if (error) {
    throw new Error(`Failed to fetch bars: ${error.message}`);
  }

  // Validate no future dates (lookahead bias guard)
  const now = new Date();
  if (bars.some(bar => new Date(bar.ts) > now)) {
    throw new Error('Future-dated bars detected in market data');
  }

  return bars;
}
```

Also, add database constraints:
```sql
-- Ensure paper trading only uses verified market data
CREATE OR REPLACE FUNCTION validate_paper_trading_bars()
RETURNS TRIGGER AS $$
BEGIN
  -- Prevent paper trading from using forecasts or unverified data
  -- This is enforced at application layer, but database constraint adds safety
  IF NEW.is_forecast = true THEN
    RAISE EXCEPTION 'Paper trading must use verified market data, not forecasts';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

**Impact if not fixed:**
- User injects false OHLCV data into `ohlc_bars_v2` (if RLS weak)
- Strategy triggers on fake signals
- Paper trading results meaningless

---

### 2.2 Stop Loss & Take Profit Accept Unconstrained Values

**Location:** Plan, lines 150-155 (backtest-strategy function)

**Severity:** HIGH (CVSS 6.3)

**Issue:** The code accepts `stop_loss_pct` and `take_profit_pct` with no validation:
```typescript
if (sl?.type === "percent" && typeof sl.value === "number") {
  parameters.stop_loss_pct = sl.value;  // No bounds check!
}
```

Realistic ranges:
- Stop loss: 0.5% - 50% (typically 1-10%)
- Take profit: 0.5% - 500% (typically 5-100%)

An attacker could set:
- `stop_loss_pct = -100` (never triggers, position runs indefinitely)
- `stop_loss_pct = 500` (triggers immediately on any +500% move, impossible)
- `take_profit_pct = 0.01` (triggers on tiny moves, unrealistic)

**Required Fix (v1 blocking):**

```typescript
interface RiskParameters {
  stop_loss_pct: number;
  take_profit_pct: number;
}

const RISK_LIMITS = {
  stop_loss_pct: { min: 0.5, max: 50 },    // 0.5% to 50%
  take_profit_pct: { min: 0.5, max: 500 }, // 0.5% to 500%
};

function validateRiskParameters(params: RiskParameters): ValidationError[] {
  const errors: ValidationError[] = [];

  if (params.stop_loss_pct < RISK_LIMITS.stop_loss_pct.min ||
      params.stop_loss_pct > RISK_LIMITS.stop_loss_pct.max) {
    errors.push({
      field: 'stop_loss_pct',
      message: `Stop loss must be ${RISK_LIMITS.stop_loss_pct.min}% to ${RISK_LIMITS.stop_loss_pct.max}%`,
      code: 'INVALID_STOP_LOSS',
    });
  }

  if (params.take_profit_pct < RISK_LIMITS.take_profit_pct.min ||
      params.take_profit_pct > RISK_LIMITS.take_profit_pct.max) {
    errors.push({
      field: 'take_profit_pct',
      message: `Take profit must be ${RISK_LIMITS.take_profit_pct.min}% to ${RISK_LIMITS.take_profit_pct.max}%`,
      code: 'INVALID_TAKE_PROFIT',
    });
  }

  if (params.stop_loss_pct >= params.take_profit_pct) {
    errors.push({
      field: 'risk_ratio',
      message: `Take profit (${params.take_profit_pct}%) must be greater than stop loss (${params.stop_loss_pct}%)`,
      code: 'INVALID_RISK_RATIO',
    });
  }

  return errors;
}

// In backtest-strategy endpoint:
if (strategyId && strategyConfig?.riskManagement) {
  const rm = strategyConfig.riskManagement as Record<string, { type?: string; value?: number }>;
  const sl = rm?.stopLoss?.value;
  const tp = rm?.takeProfit?.value;

  const errors = validateRiskParameters({
    stop_loss_pct: sl ?? 2,
    take_profit_pct: tp ?? 10,
  });

  if (errors.length > 0) {
    return corsResponse(
      { error: 'Invalid risk parameters', details: errors },
      400,
      origin
    );
  }

  parameters.stop_loss_pct = sl ?? 2;
  parameters.take_profit_pct = tp ?? 10;
}
```

**Also add database constraints:**
```sql
ALTER TABLE paper_trading_positions
  ADD CONSTRAINT sl_tp_reasonable CHECK (
    stop_loss_price IS NULL OR (stop_loss_price > 0 AND stop_loss_price < entry_price * 0.5)
  ),
  ADD CONSTRAINT tp_gt_sl CHECK (
    take_profit_price IS NULL OR stop_loss_price IS NULL OR
    take_profit_price > stop_loss_price
  );
```

**Impact if not fixed:**
- Users set unrealistic SL/TP (e.g., SL at -100%, TP at +1000%)
- Backtest results don't reflect realistic trading mechanics
- Paper trading fails validation checks

---

### 2.3 Execution Isolation: Paper Trading & Backtest Share Condition Evaluator

**Location:** Plan, section "Multi-Condition AND/OR Logic" (lines 366-402)

**Severity:** HIGH (CVSS 6.8)

**Issue:** The plan proposes a **shared condition evaluator** used by both backtesting and paper trading:

> "Both use same evaluator for consistency" (line 618-619)

While consistency is good, **any bug in the evaluator affects both systems simultaneously**. Additionally, the paper trading executor must handle **real-time signal evaluation** differently from historical backtests:

**Backtest concerns:**
- Must evaluate on closed bars (known values)
- Can evaluate multiple periods in parallel
- Can afford to be slow (CPU-bound)

**Paper trading concerns:**
- Must evaluate on live tick data (partial bars)
- Must be fast (<100ms) to not miss signals
- Cannot be parallelized (must be sequential on candle close)

If the shared evaluator has **race conditions** or **timing bugs**, they manifest differently:
- Backtest: Overfitting, false precision
- Paper trading: Missed entries, wrong fills

**Required Fix (v1 blocking):**

1. **Create separate evaluators with shared logic:**

```typescript
// File: supabase/functions/_shared/condition-evaluator-base.ts
export abstract class ConditionEvaluatorBase {
  protected conditions: Condition[];
  protected bars: Bar[];

  abstract validateContext(): void;

  evaluate(): boolean {
    this.validateContext();
    return this.evaluateTree(this.conditions[0]);
  }

  protected evaluateTree(node: Condition): boolean {
    const indicatorValue = this.calculateIndicator(node.indicator, this.bars);
    const conditionMet = this.evaluateOperator(indicatorValue, node.operator, node.value);

    if (!node.children || node.children.length === 0) {
      return conditionMet;
    }

    const childResults = node.children.map(child => this.evaluateTree(child));

    if (node.logicalOp === "AND") {
      return conditionMet && childResults.every(r => r);
    } else {
      return conditionMet || childResults.some(r => r);
    }
  }

  protected abstract calculateIndicator(name: string, bars: Bar[]): number;
  protected abstract evaluateOperator(value: number, op: string, threshold: number): boolean;
}

// File: supabase/functions/_shared/condition-evaluator-backtest.ts
export class BacktestConditionEvaluator extends ConditionEvaluatorBase {
  constructor(conditions: Condition[], bars: Bar[]) {
    super();
    this.conditions = conditions;
    this.bars = bars;
  }

  validateContext(): void {
    // Backtest: bars are complete, no live data
    if (this.bars.some(b => b.volume === 0)) {
      throw new Error('Backtest evaluator requires complete bars with volume');
    }
  }

  // Implementation for indicators from historical data
  protected calculateIndicator(name: string, bars: Bar[]): number {
    // Use batched indicator calculation (can be slow)
    return calculateIndicatorHistorical(name, bars);
  }
}

// File: supabase/functions/_shared/condition-evaluator-paper-trading.ts
export class PaperTradingConditionEvaluator extends ConditionEvaluatorBase {
  private evaluationTimeMs: number = 0;

  constructor(conditions: Condition[], bars: Bar[]) {
    super();
    this.conditions = conditions;
    this.bars = bars;
  }

  validateContext(): void {
    // Paper trading: must have real-time data, enforce timing
    const startTime = performance.now();

    if (this.bars.length < 2) {
      throw new Error('Paper trading requires at least 2 bars for signal validation');
    }

    // Warn if evaluation takes too long
    this.evaluationTimeMs = performance.now() - startTime;
    if (this.evaluationTimeMs > 100) {
      console.warn(`[PaperTrading] Evaluation took ${this.evaluationTimeMs}ms (target: <100ms)`);
    }
  }

  // Implementation for indicators from live feed (cached, fast)
  protected calculateIndicator(name: string, bars: Bar[]): number {
    // Use cached indicator values (must be pre-computed before signal eval)
    return getIndicatorValueCached(name, bars);
  }
}
```

2. **Use context-appropriate evaluator in each system:**

```typescript
// backtest-strategy-worker:
const evaluator = new BacktestConditionEvaluator(conditions, historicalBars);
const entrySignal = evaluator.evaluate();

// paper-trading-executor:
const evaluator = new PaperTradingConditionEvaluator(conditions, liveBars);
const entrySignal = evaluator.evaluate();
```

3. **Add integration test to verify both systems agree on signal timing:**

```typescript
// Test: Same strategy on same data produces same signals in backtest and paper
async function testConsistency(strategy: Strategy, testData: Bar[]) {
  const conditions = strategy.buy_conditions;

  const backestEval = new BacktestConditionEvaluator(conditions, testData);
  const paperEval = new PaperTradingConditionEvaluator(conditions, testData);

  const backestSignal = backtestEval.evaluate();
  const paperSignal = paperEval.evaluate();

  if (backestSignal !== paperSignal) {
    throw new Error(
      `Signal mismatch: backtest=${backestSignal}, paper=${paperSignal}. ` +
      `This indicates a logic bug in the evaluator.`
    );
  }
}
```

**Impact if not fixed:**
- Bug in shared evaluator affects both systems (cascading failure)
- Paper trading may use stale indicator values (timing mismatch)
- Backtest results inconsistent with paper trading

---

### 2.4 No Audit Logging of User Actions in strategy_execution_log

**Location:** Plan, lines 171-184 (strategy_execution_log table definition)

**Severity:** HIGH (CVSS 5.4)

**Issue:** The `strategy_execution_log` table has no RLS policy. Users can read **execution details of other users' strategies**, revealing:
- When strategies trade
- What indicators triggered
- P&L details

**Required Fix (v1 blocking):**
```sql
ALTER TABLE strategy_execution_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view execution logs of their strategies"
  ON strategy_execution_log FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM strategy_user_strategies
      WHERE strategy_user_strategies.id = strategy_id
      AND strategy_user_strategies.user_id = auth.uid()
    )
  );

CREATE POLICY "Only service role can insert execution logs"
  ON strategy_execution_log FOR INSERT
  WITH CHECK (auth.role() = 'service_role');
```

---

## 3. MEDIUM SEVERITY FINDINGS

### 3.1 Strategy Config Not Encrypted (Sensitive Reveal)

**Location:** Plan, lines 6-14 (strategy_user_strategies table)

**Severity:** MEDIUM (CVSS 5.1)

**Issue:** `strategy_user_strategies.config` is stored as unencrypted JSONB. Competitors can observe:
- Position sizing logic
- Stop loss / take profit thresholds
- Indicator parameters

While RLS prevents access to other users' strategies, **a compromised database or backup** exposes all strategy configs.

**Required Fix (post-v1, but recommended):**
```sql
-- Add encrypted_config column
ALTER TABLE strategy_user_strategies
  ADD COLUMN encrypted_config BYTEA;

-- Migrate existing data
UPDATE strategy_user_strategies
  SET encrypted_config = pgp_sym_encrypt(config::text, 'encryption-key-from-vault')
  WHERE encrypted_config IS NULL;

-- Drop old column after verification
-- ALTER TABLE strategy_user_strategies DROP COLUMN config;
```

In application layer, decrypt on read:
```typescript
const { data: strategy } = await supabase
  .from('strategy_user_strategies')
  .select('id, name, encrypted_config')
  .eq('id', strategyId)
  .single();

// Decrypt config in application (pgp_sym_decrypt in SQL or app-side)
const config = decryptStrategyConfig(strategy.encrypted_config);
```

---

### 3.2 Error Messages May Leak Schema Info

**Location:** `/Users/ericpeterson/SwiftBolt_ML/supabase/functions/backtest-strategy/index.ts`, line 174

**Severity:** MEDIUM (CVSS 4.9)

**Issue:**
```typescript
if (error) {
  console.error("[BacktestStrategy] Failed to queue job:", error);
  return corsResponse({ error: "Failed to queue backtest job" }, 500, origin);
}
```

If `error` contains SQL details (e.g., constraint violation), it's logged to console. If error messages are returned to client, they may leak schema info.

**Required Fix (v1 blocking):**
```typescript
if (error) {
  console.error("[BacktestStrategy] Database error:", JSON.stringify(error, null, 2));
  // Never return raw DB error to client
  return corsResponse(
    {
      error: "Failed to create backtest job",
      // Only return generic message + error code, not SQL details
      code: error.code || 'DB_ERROR',
    },
    500,
    origin
  );
}
```

---

### 3.3 Backtest Results Comparison Needs Divergence Threshold

**Location:** Plan, lines 327-330 (Paper Trading Dashboard)

**Severity:** MEDIUM (CVSS 4.8)

**Issue:** The dashboard compares backtest P&L vs paper P&L and "alerts if diverge significantly (strategy performing worse live)". But the plan doesn't define **what counts as significant divergence**.

Example: Strategy backtests at +5% over 100 trades, but papers at +3%. Is this:
- Expected variance (±2% is normal)? No alert.
- Signal of overfitting (±5-10% is concerning)? Yellow alert.
- Model failure (±20%+ divergence)? Red alert, halt strategy.

**Required Fix (v1 blocking):**
```typescript
interface DivergenceThreshold {
  yellow_alert_pct: number;   // 5% divergence = yellow
  red_alert_pct: number;      // 15% divergence = red
  min_trades_required: number; // At least 10 trades to alert
}

const DIVERGENCE_RULES: DivergenceThreshold = {
  yellow_alert_pct: 5,
  red_alert_pct: 15,
  min_trades_required: 10,
};

function comparePaperVsBacktest(
  backtest: { win_rate: number; profit_factor: number },
  paper: { win_rate: number; profit_factor: number }
): AlertLevel {
  // Only compare if sufficient trades
  if (paper.trades_count < DIVERGENCE_RULES.min_trades_required) {
    return 'insufficient_data';
  }

  const divergence_pct = Math.abs(paper.profit_factor - backtest.profit_factor) /
                         Math.abs(backtest.profit_factor) * 100;

  if (divergence_pct > DIVERGENCE_RULES.red_alert_pct) {
    return 'critical'; // Pause strategy, investigate
  }

  if (divergence_pct > DIVERGENCE_RULES.yellow_alert_pct) {
    return 'warning'; // Show alert, allow continued trading
  }

  return 'normal';
}
```

---

## 4. LOW SEVERITY FINDINGS

### 4.1 Position Close Not Atomic (Race Condition Risk)

**Location:** Plan, lines 299-305 (paper trading executor)

**Severity:** LOW (CVSS 4.2)

**Issue:**
```typescript
const openPosition = await getOpenPosition(strategy.id, symbol);

if (openPosition) {
  const latestPrice = bars[bars.length - 1].close;
  if (latestPrice <= openPosition.stop_loss_price) {
    await closeTrade(openPosition, latestPrice, 'SL_HIT');
  }
}
```

If **two candles close simultaneously** or the executor runs twice in parallel, both threads could call `closeTrade` on the same position, creating duplicate exit records.

**Required Fix (v1 blocking):**
```typescript
async function closeTrade(
  position: PaperTradingPosition,
  exitPrice: number,
  reason: string,
  supabase: SupabaseClient
): Promise<void> {
  // Use atomic transaction to prevent double-close
  const { data, error } = await supabase
    .from('paper_trading_positions')
    .update({ status: 'closed', updated_at: new Date().toISOString() })
    .eq('id', position.id)
    .eq('status', 'open') // Only close if still open (atomic check)
    .select('id')
    .single();

  if (error || !data) {
    // Position already closed by another process
    console.warn(`[PaperTrading] Position ${position.id} already closed`);
    return;
  }

  // Safe to insert trade record
  const pnl = (exitPrice - position.entry_price) * position.quantity;
  const pnl_pct = (pnl / (position.entry_price * position.quantity)) * 100;

  await supabase
    .from('paper_trading_trades')
    .insert({
      user_id: position.user_id,
      strategy_id: position.strategy_id,
      symbol_id: position.symbol_id,
      entry_price: position.entry_price,
      exit_price: exitPrice,
      quantity: position.quantity,
      direction: position.direction,
      entry_time: position.entry_time,
      exit_time: new Date().toISOString(),
      pnl,
      pnl_pct,
      trade_reason: reason,
    });
}
```

---

### 4.2 Indicator Parameter Changes Not Versioned

**Location:** Plan, section "Enhanced Indicator Menu" (lines 336-365)

**Severity:** LOW (CVSS 3.8)

**Issue:** If an analyst changes an indicator's default parameters, **old positions and trades reference the old logic**. Example:
- Strategy uses RSI(14) for backtests
- Analyst changes default RSI to RSI(21)
- Old backtest results now use mismatched indicator

**Required Fix (v1 blocking):**
```typescript
interface IndicatorConfig {
  name: string;
  period: number;
  version: number; // NEW: Track parameter version
  hash: string;    // NEW: Hash of {name, period} for change detection
}

function getIndicatorConfig(name: string): IndicatorConfig {
  const config = INDICATORS[name];
  return {
    name: config.name,
    period: config.period,
    version: 1, // Increment when parameters change
    hash: md5(`${name}:${config.period}`), // Detect changes
  };
}

// Store indicator config with each strategy run
interface BacktestJob {
  indicator_configs: IndicatorConfig[]; // Store which versions were used
}

// On indicator parameter change, alert user
function onIndicatorParameterChange(name: string, newVersion: number) {
  // Query all backtest_jobs that used old version
  // Alert user: "RSI parameter changed; old backtests may be inconsistent"
}
```

---

## 5. IMPLEMENTATION RECOMMENDATIONS

### Pre-v1 Checklist (Blocking)

- [ ] **Add RLS policies to all paper trading tables** (critical)
- [ ] **Validate slippage against realistic ranges** (critical)
- [ ] **Add position size & entry price bounds** (critical)
- [ ] **Remove demo user fallback** (critical)
- [ ] **Enforce market data source validation** (high)
- [ ] **Validate stop loss / take profit bounds** (high)
- [ ] **Create separate condition evaluators** (high)
- [ ] **Define divergence thresholds** (medium)
- [ ] **Implement atomic position close** (low)
- [ ] **Add indicator versioning** (low)

### v1 Quality Gates

**Code Review Checklist:**
- [ ] All input parameters validated with clear bounds
- [ ] All table mutations enforce RLS via Supabase ACL
- [ ] All user-controlled numbers (slippage, SL/TP, qty) have min/max checks
- [ ] All financial calculations (P&L, returns) have overflow guards
- [ ] All error messages are generic (no schema leak)
- [ ] Paper trading executor has <100ms latency SLA with timing metrics
- [ ] Integration test: Backtest vs paper trading on same data produce same signals

**Security Testing:**
- [ ] Attempt to access another user's paper trading positions (should fail)
- [ ] Attempt to insert position with entry_price = 0 (should fail)
- [ ] Attempt to set slippage = 500% (should fail)
- [ ] Query paper_trading_trades without auth header (should fail)
- [ ] Unauthenticated request to backtest endpoint (should fail)

**Performance Testing:**
- [ ] Paper trading executor handles 10 strategies × 100 bars = <500ms total
- [ ] Dashboard renders 500 trades without lag
- [ ] RLS policy evaluation doesn't add >10ms latency per query

---

## 6. DATABASE SCHEMA FIXES SUMMARY

**Full migration to add security controls:**

```sql
-- File: supabase/migrations/20260225000000_strategy_platform_security.sql

-- ==============================================================================
-- PAPER TRADING TABLES WITH RLS
-- ==============================================================================

CREATE TABLE IF NOT EXISTS paper_trading_positions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  strategy_id UUID NOT NULL REFERENCES strategy_user_strategies(id) ON DELETE CASCADE,
  symbol_id UUID NOT NULL REFERENCES symbols(id),
  timeframe TEXT NOT NULL CHECK (timeframe IN ('1m', '5m', '15m', '1h', 'd1', 'w', 'm')),
  entry_price DECIMAL NOT NULL CHECK (entry_price > 0 AND entry_price < 1000000),
  current_price DECIMAL,
  quantity INT NOT NULL CHECK (quantity > 0 AND quantity <= 100000),
  entry_time TIMESTAMPTZ NOT NULL,
  direction TEXT NOT NULL CHECK (direction IN ('long', 'short')),
  stop_loss_price DECIMAL CHECK (stop_loss_price IS NULL OR stop_loss_price > 0),
  take_profit_price DECIMAL CHECK (take_profit_price IS NULL OR take_profit_price > 0),
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT tp_gt_sl CHECK (
    take_profit_price IS NULL OR stop_loss_price IS NULL OR
    take_profit_price > stop_loss_price
  )
);

CREATE INDEX idx_paper_positions_user_strategy
  ON paper_trading_positions(user_id, strategy_id, status);

ALTER TABLE paper_trading_positions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own positions"
  ON paper_trading_positions FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own positions"
  ON paper_trading_positions FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own positions"
  ON paper_trading_positions FOR UPDATE
  USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own positions"
  ON paper_trading_positions FOR DELETE
  USING (auth.uid() = user_id);

-- Paper trades (closed positions)
CREATE TABLE IF NOT EXISTS paper_trading_trades (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  strategy_id UUID NOT NULL REFERENCES strategy_user_strategies(id) ON DELETE CASCADE,
  symbol_id UUID NOT NULL REFERENCES symbols(id),
  timeframe TEXT NOT NULL,
  entry_price DECIMAL NOT NULL CHECK (entry_price > 0),
  exit_price DECIMAL NOT NULL CHECK (exit_price > 0),
  quantity INT NOT NULL CHECK (quantity > 0),
  direction TEXT NOT NULL CHECK (direction IN ('long', 'short')),
  entry_time TIMESTAMPTZ NOT NULL,
  exit_time TIMESTAMPTZ NOT NULL,
  pnl DECIMAL NOT NULL,
  pnl_pct DECIMAL NOT NULL,
  trade_reason TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT exit_after_entry CHECK (exit_time > entry_time)
);

CREATE INDEX idx_paper_trades_user_strategy
  ON paper_trading_trades(user_id, strategy_id, created_at DESC);

ALTER TABLE paper_trading_trades ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own trades"
  ON paper_trading_trades FOR SELECT
  USING (auth.uid() = user_id);

-- Execution log
CREATE TABLE IF NOT EXISTS strategy_execution_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  strategy_id UUID NOT NULL REFERENCES strategy_user_strategies(id) ON DELETE CASCADE,
  symbol_id UUID NOT NULL REFERENCES symbols(id),
  timeframe TEXT NOT NULL,
  candle_time TIMESTAMPTZ NOT NULL,
  signal_type TEXT NOT NULL CHECK (signal_type IN ('entry', 'exit', 'condition_met', 'error')),
  triggered_conditions TEXT[],
  action_taken TEXT,
  execution_details JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_execution_log_strategy
  ON strategy_execution_log(strategy_id, created_at DESC);

ALTER TABLE strategy_execution_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view execution logs of their strategies"
  ON strategy_execution_log FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM strategy_user_strategies
      WHERE strategy_user_strategies.id = strategy_id
      AND strategy_user_strategies.user_id = auth.uid()
    )
  );

CREATE POLICY "Only service role can insert logs"
  ON strategy_execution_log FOR INSERT
  WITH CHECK (auth.role() = 'service_role');

-- ==============================================================================
-- SYMBOL LIQUIDITY CLASSIFICATION
-- ==============================================================================

CREATE TABLE IF NOT EXISTS symbol_liquidity_classification (
  symbol_id UUID PRIMARY KEY REFERENCES symbols(id) ON DELETE CASCADE,
  liquidity_tier TEXT NOT NULL CHECK (liquidity_tier IN ('high', 'low', 'micro_cap')),
  last_updated TIMESTAMPTZ DEFAULT NOW(),
  updated_by TEXT DEFAULT 'system'
);

CREATE INDEX idx_liquidity_tier ON symbol_liquidity_classification(liquidity_tier);

-- Pre-populate with common symbols (update as needed)
INSERT INTO symbol_liquidity_classification (symbol_id, liquidity_tier)
SELECT id, 'high' FROM symbols WHERE symbol IN ('AAPL', 'MSFT', 'TSLA', 'GOOGL', 'AMZN', 'SPY', 'QQQ')
ON CONFLICT DO NOTHING;

-- ==============================================================================
-- ENHANCE STRATEGY TABLE
-- ==============================================================================

ALTER TABLE strategy_user_strategies
  ADD COLUMN IF NOT EXISTS paper_trading_enabled BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS paper_capital DECIMAL DEFAULT 10000 CHECK (paper_capital > 0),
  ADD COLUMN IF NOT EXISTS paper_start_date TIMESTAMPTZ;

-- ==============================================================================
-- METRICS TABLE (for dashboard comparison)
-- ==============================================================================

CREATE TABLE IF NOT EXISTS paper_trading_metrics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  strategy_id UUID NOT NULL REFERENCES strategy_user_strategies(id) ON DELETE CASCADE,
  period_start TIMESTAMPTZ NOT NULL,
  period_end TIMESTAMPTZ NOT NULL,
  trades_count INT DEFAULT 0,
  win_count INT DEFAULT 0,
  loss_count INT DEFAULT 0,
  avg_win DECIMAL,
  avg_loss DECIMAL,
  win_rate DECIMAL,
  profit_factor DECIMAL,
  max_drawdown DECIMAL,
  total_pnl DECIMAL,
  total_pnl_pct DECIMAL,
  sharpe_ratio DECIMAL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (strategy_id, period_start, period_end)
);

CREATE INDEX idx_metrics_user_strategy
  ON paper_trading_metrics(user_id, strategy_id, period_end DESC);

ALTER TABLE paper_trading_metrics ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view metrics for their strategies"
  ON paper_trading_metrics FOR SELECT
  USING (auth.uid() = user_id);
```

---

## 7. TESTING STRATEGY

### Unit Tests (Edge Functions)

```typescript
// Test slippage validation
describe('Slippage Validation', () => {
  test('accepts slippage within realistic range', () => {
    expect(validateSlippage({ symbol: 'AAPL', slippage: 0.2, liquidity: 'high' })).toBeNull();
  });

  test('rejects slippage outside range', () => {
    const error = validateSlippage({ symbol: 'AAPL', slippage: 0.01, liquidity: 'high' });
    expect(error).toBeDefined();
    expect(error?.code).toBe('INVALID_SLIPPAGE_RANGE');
  });
});

// Test position size validation
describe('Position Size Validation', () => {
  test('rejects zero-cost positions', () => {
    const errors = validatePositionSize(
      { entry_price: 0, quantity: 100, symbol: 'AAPL', account_capital: 10000 },
      POSITION_LIMITS
    );
    expect(errors.length).toBeGreaterThan(0);
  });

  test('rejects positions exceeding capital %', () => {
    const errors = validatePositionSize(
      { entry_price: 500, quantity: 1000, symbol: 'AAPL', account_capital: 10000 },
      POSITION_LIMITS
    );
    // 500 * 1000 = $500k > 10% of $10k (too large)
    expect(errors.some(e => e.code === 'POSITION_SIZE_EXCEEDS_CAPITAL')).toBe(true);
  });
});

// Test RLS enforcement
describe('RLS Policies', () => {
  test('user cannot read other user\'s positions', async () => {
    const userAClient = createSupabaseClient(userAToken);
    const userBClient = createSupabaseClient(userBToken);

    // User B creates position
    await userBClient
      .from('paper_trading_positions')
      .insert({ user_id: userBId, strategy_id, ... });

    // User A tries to read
    const { data, error } = await userAClient
      .from('paper_trading_positions')
      .select('*');

    expect(error).toBeDefined(); // Should be forbidden
    expect(data).toBeNull();
  });
});
```

### Integration Tests (End-to-End)

```typescript
describe('Paper Trading E2E', () => {
  test('strategy entry/exit executes with correct P&L', async () => {
    // Create strategy with RSI > 50 entry, RSI < 30 exit
    // Queue paper trading run
    // Verify position created at entry signal
    // Verify trade closed at exit signal
    // Verify P&L = (exit_price - entry_price) * quantity
  });

  test('SL/TP enforcement', async () => {
    // Create position with SL at entry - 2%, TP at entry + 5%
    // Simulate price hitting SL first
    // Verify trade closed at SL price, not TP
  });

  test('backtest vs paper consistency', async () => {
    // Run backtest on AAPL 2025-01-01 to 2025-02-01
    // Run paper trading on same data
    // Verify same entry/exit signals
    // Verify P&L matches (within 0.01%)
  });
});
```

---

## 8. NEXT STEPS

1. **This week:** Review this audit with team, prioritize fixes
2. **Week 1-2:** Implement all CRITICAL and HIGH findings
3. **Week 2:** Write tests, run security test suite
4. **Week 3:** Code review with security focus
5. **Week 4:** Deploy to staging, run chaos testing
6. **Week 5:** Deploy to production with monitoring

---

## 9. APPENDIX: Security Validation Checklist

### Authentication & Authorization
- [ ] All private endpoints require valid JWT (no demo fallback)
- [ ] All user-owned tables have RLS WITH CHECK (auth.uid() = user_id)
- [ ] RLS policy test: User A cannot read/write/delete User B's data
- [ ] Backtest endpoint validates user_id from JWT matches strategy owner

### Input Validation
- [ ] Slippage: 0.05-0.5% (high liquidity), 0.5-5% (low), validated on input
- [ ] Position quantity: 1-100,000 shares, < 10% of account capital
- [ ] Entry price: $0.01-$1M, realistic for equity
- [ ] Stop loss: 0.5-50%, less than take profit
- [ ] Take profit: 0.5-500%, greater than stop loss
- [ ] Initial capital: $100-$1M (min viable, max realistic)
- [ ] Date range: start < end, within 10 years

### Financial Data Integrity
- [ ] P&L calculation: (exit_price - entry_price) * quantity, rounded to cents
- [ ] Position creation: atomic insert with all fields or rollback
- [ ] Position close: check `status = 'open'` before update (prevent double-close)
- [ ] Bar source validation: only use `is_forecast=false`, `provider IN ('alpaca', ...)`
- [ ] No future-dated bars in signal evaluation

### Execution Isolation
- [ ] Paper trading executor timeout: <500ms per strategy per candle
- [ ] Separate condition evaluators for backtest vs paper trading
- [ ] Paper trading bars validated against lookahead bias
- [ ] Backtest uses historical data only, no live feeds

### Sensitive Data Protection
- [ ] Strategy config (RLS enforced, no unencrypted export)
- [ ] Error messages generic (no SQL details)
- [ ] Backtest results include user_id for access control
- [ ] Execution logs only visible to strategy owner

---

**Audit completed:** 2026-02-25
**Auditor:** Security Specialist
**Recommendation:** Address all CRITICAL findings before v1 deployment.
