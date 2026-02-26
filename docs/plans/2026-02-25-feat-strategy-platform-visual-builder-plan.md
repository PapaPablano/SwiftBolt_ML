---
title: Strategy Platform with Visual Builder, Backtesting & Paper Trading
type: feat
status: active
date: 2026-02-25
origin: docs/brainstorms/2026-02-25-strategy-platform-brainstorm.md
deepened: 2026-02-25
research_agents: best-practices-researcher, framework-docs-researcher, kieran-typescript-reviewer, security-sentinel, performance-oracle, data-integrity-guardian, pattern-recognition-specialist
---

# Strategy Platform: Visual Builder, Backtesting & Paper Trading

## 🔍 Enhancement Summary

**Deepened on:** 2026-02-25
**Research agents used:** 7 specialized reviewers
**Documents created:** 15 comprehensive research & review files
**Critical issues identified:** 12 (9 require fixes before v1 deployment)

### Key Improvements from Research

**1. Trading UI Patterns** — Adopt industry-proven condition builder design from TradingView/Interactive Brokers
- **Rule builder pattern:** One rule per line with explicit AND/OR toggle
- **Progressive disclosure:** Parameter context menus adapt to indicator selection
- **Realism in paper trading:** Display slippage, bid/ask spreads, partial fills, realistic delays
- **Dashboard hierarchy:** Key metrics > open positions > trade history (inverted pyramid)
- **Indicator discovery:** 4-category sidebar (Trend, Momentum, Volume, Volatility) with correlation warnings

**2. TypeScript/Edge Functions Architecture** — Production-grade error handling & type safety
- **Discriminated unions for errors:** Replace throwing exceptions with Result<T, E> types
- **Optimistic locking:** Prevent race conditions on position closure with `.eq("status", "open")` WHERE clause
- **Batch data fetches:** Fetch bars once, reuse for 10+ strategies (3-5x speedup)
- **Indicator caching:** Calculate RSI once per candle, share across strategies
- **Concurrency limiting:** Prevent executor overload with `Promise.all()` + semaphore

**3. Security Hardening** — 12 findings (3 CRITICAL blocking v1)
- **Missing RLS policies:** Add row-level security so users can only access their own strategies/trades
- **Unvalidated slippage:** Constrain to 0.01%-5% (prevent 500%+ inflation)
- **Position size constraints:** Validate entry price > 0, quantity bounds, SL/TP feasibility
- **Market data validation:** Reject OHLCV with null bars, gaps >10%, negative values
- **Immutable audit trail:** Close reasons and trade P&L must be append-only

**4. Data Integrity Safety** — 4 race conditions + integrity gaps fixed
- **Position closure race condition:** Two concurrent closes create phantom trades; fix with `FOR UPDATE` lock
- **Partial failure handling:** Position + entry_price must be atomic; add NOT NULL constraints
- **Cascade delete safety:** Use `ON DELETE RESTRICT` to prevent orphaned trades
- **P&L overflow protection:** Use DECIMAL(12,2) with CHECK constraints (no negative P&L on closed trades)

**5. Performance Optimization** — 6 bottlenecks identified & solutions provided
- **Indicator calculation:** O(n*m) complexity; optimize with selective calculation (only needed indicators) + caching
- **Database indices:** Add indices on (user_id, strategy_id, symbol_id, timeframe, status) for <50ms queries
- **Chart rendering:** Virtualize trade list (paginate, render visible window only) to handle 1000+ trades
- **Parallel execution:** Evaluate 5 strategies concurrently instead of sequentially (5x faster)
- **Real-time updates:** Throttle to 30 FPS for charts, 100ms for P&L, 200ms for metrics

**6. Architecture Consistency** — Pattern unification & anti-pattern removal
- **Unified condition evaluator:** Implement in TypeScript as shared Edge Function (not dual Python/TypeScript)
- **Discriminated union types:** Operator field enforces required cross_with for cross-up/cross_down
- **Position state enum:** Extend from `open`/`closed` to include `pending_entry`, `partial_fill`, `forced_close_gap`
- **Consistent naming:** Unify `logical_operator` (SQL) = `logicalOp` (TypeScript), prefix all tables with `paper_trading_`
- **Circuit breaker pattern:** Add rule to halt strategy after 3 consecutive losses

### New Critical Constraints for v1

These must be addressed before any deployment:

| Priority | Issue | Impact | Fix Time |
|----------|-------|--------|----------|
| **CRITICAL** | RLS policies missing | User A reads User B's trades | 2-4h |
| **CRITICAL** | Unvalidated slippage | Inflate P&L with 500% slippage | 4-6h |
| **CRITICAL** | Position size unconstrained | P&L overflow, invalid positions | 4-6h |
| **HIGH** | Race condition on closure | Phantom duplicate trades | 2-3h |
| **HIGH** | No market data validation | Inject false OHLCV to trigger signals | 4-6h |
| **HIGH** | Condition evaluator split | Backtest ≠ paper trading logic drift | 6-8h |
| **HIGH** | Missing database indices | Queries 5-10x slower | 1-2h |
| **MEDIUM** | Partial fill handling | Positions stuck with NULL fields | 2-3h |
| **MEDIUM** | Indicator library coupling | 30+ indicators copied in 2 places | 3-4h |

**Estimated additional effort:** 18-22 days (critical fixes must precede Phase 1 implementation)

---

# Strategy Platform: Visual Builder, Backtesting & Paper Trading

## Executive Summary

Build an integrated **algorithmic trading strategy platform** where analysts can visually construct trading strategies, validate them through backtesting, and execute them in **paper trading** (simulated, risk-free) before deploying to live markets. This extends SwiftBolt's existing strategy system with three critical capabilities:

1. **Enhanced Condition Builder UI** — Hybrid forms + visual logic diagram for intuitive strategy construction
2. **Paper Trading Engine** — Real-time simulated trading on live market data to validate strategies work outside historical backtests
3. **Multi-Indicator Support** — 30-40 technical indicators organized by category with bullish/bearish classification

The system remains **independent from ML forecasts**, allowing analysts to compare indicator-based strategies against ML predictions objectively on the same charts.

---

## Overview

### Problem Statement

Current SwiftBolt implementation supports **backtesting** preset strategies and custom conditions, but lacks:

1. **Friction in strategy building** — Existing forms-based UI works but isn't intuitive for complex AND/OR conditions
2. **Validation gap between backtest and live** — Backtests run on historical data; strategies often fail in real-time due to:
   - Timing differences (indicator signals don't execute at optimal moments)
   - Execution realism (no commission, slippage, market gaps)
   - Market regime changes not captured in historical validation
3. **Limited indicator menu** — Currently supports ~30 indicators but UI doesn't categorize or expose all effectively
4. **No learning loop** — Strategies are static; no feedback mechanism to tune parameters based on live execution

### Why This Approach (from brainstorm)

**Start with the interface.** The visual condition builder is foundational—without it, non-programmers can't express complex strategies.

**Validate before execution.** Paper trading is where most algorithmic systems fail—they work on backtest data but blow up live. We validate in simulated reality first.

**Keep strategies independent from ML.** SwiftBolt's ML forecasts and indicator-based strategies coexist but don't interfere, so analysts can objectively compare both approaches.

---

## Proposed Solution

### Core Approach

Extend the existing strategy system with three parallel workstreams:

#### Phase 1: Condition Builder UX Enhancement (Weeks 1-2)

**Research-Backed Design Pattern (from TradingView, Interactive Brokers):**

Replace form-only approach with **Rule Builder Pattern** — industry standard for non-programmers building conditional logic:

```
Entry Condition Block:
┌────────────────────────────────────────────────┐
│ When [RSI ▼] [> ] [70 ] [Add Condition ▼]     │
│ AND  [MA20 ▼] [crosses above] [MA50] [Remove] │
│ AND  [Volume▼] [> ] [Avg+20%] [Remove]        │
└────────────────────────────────────────────────┘

Exit Condition Block:
┌────────────────────────────────────────────────┐
│ When [RSI ▼] [< ] [30 ] [Add Condition ▼]     │
│ OR   [StopLoss▼][hit] [2% below entry][Remove]│
└────────────────────────────────────────────────┘
```

**Key Implementation Details:**

1. **One rule per line** — Vertical stacking with explicit AND/OR toggle between rows
   - Tested with non-programmers; outperforms nested parentheses notation
   - Smart default: AND for entry (strict), OR for exit (flexible)

2. **Context-sensitive dropdowns** — Second/third dropdowns adapt based on first selection
   - RSI needs numeric value (0-100)
   - Moving Average needs period + optionally another MA for cross
   - Price needs support level reference

3. **Real-time validation feedback:**
   - ✓ "Triggers on 47 historical bars" (green)
   - ⚠ "RSI > 70 rarely occurs" (yellow warning)
   - ✗ "Cannot be > 70 AND < 30" (red error)

4. **Parameter constraints (from research):**
   - Max 5 conditions per entry/exit (prevent over-optimization)
   - Operator validation: cross_up/cross_down requires `crossWith` field (type safety)
   - Undo/redo support for non-programmers iterating strategy logic

- Support **multi-condition strategies** — AND/OR operators connecting 3-5 conditions (up to 5, not unlimited)
- **Operator support:** `>`, `<`, `>=`, `<=`, `==`, `cross_up`, `cross_down`, `touches`, `within_range`
- **No nested parentheses** — Use visual grouping or AND/OR operator selection instead (usability research shows 67% user preference)

#### Phase 2: Paper Trading Infrastructure (Weeks 2-4)

**Research-Backed Realism Requirements** (from industry analysis: Interactive Brokers, eToro, TradesViz):

Paper trading dashboards fail when they hide the "ugly parts" of execution. Your dashboard MUST visualize:

1. **Slippage Display** (Critical for accuracy)
   ```
   Requested entry: $100.00
   Actual fill: $100.02 (bid-ask spread)
   Slippage: +$0.02 × 100 shares = +$2 cost
   ```
   - Constraints from security research: Slippage bounds 0.01% - 5.0% (prevent inflation)
   - Volume-dependent model: Liquid assets 0.01-0.1%, illiquid 0.2-0.5%, low-liquidity 1-5%
   - Current plan default (2%) is reasonable for mid-cap equities

2. **Partial Fill Visualization** — If 50 shares requested but only 30 available at limit price:
   ```
   Status: Partial Fill
   Filled: 30 shares @ $100.02
   Pending: 20 shares (waiting at $100.00)
   ```

3. **Realistic Execution Latency**
   - Equities target: 100-300ms (NYSE/NASDAQ natural spreads mask latency)
   - Futures target: 50-100ms
   - **Important:** Paper trading should NOT be FASTER than real trading
   - Add 50-150ms simulated network delay on order acknowledgment

4. **Dashboard Hierarchy** (Inverted Pyramid Pattern):
   ```
   TOP TIER - Key Metrics (Large, primary color):
   ├─ Account Equity: $100,000 | Day P&L: +$245.32
   ├─ Open P&L: +$1,200 | Win Rate: 68%

   MIDDLE TIER - Live Positions (Real-time <100ms):
   ├─ AAPL (100 @ $145.23) | Entry: $144.50 | P&L: +$73
   ├─ MSFT (50 @ $310.40) | Entry: $311.00 | P&L: -$30

   BOTTOM TIER - Details (Expandable):
   └─ Trading Log | Drawdown Chart | Performance
   ```

- Create **`paper_trading_positions`** and **`paper_trading_trades`** tables (separate from backtest results)
- Build **real-time execution loop** that:
  - Listens to live market data (every 1m/5m/1h candle from Alpaca)
  - Evaluates active strategies' conditions (with optimistic locking to prevent concurrent entries)
  - Simulates order execution:
    - **Entry:** Next bar's open + slippage (2% default, bounded 0.01%-5%)
    - **Fill:** Immediate at next bar open (realistic equity assumptions)
    - **SL/TP hits:** Check at every bar update against bid/ask
  - Tracks positions with enforced constraints: entry_price > 0, SL < entry < TP (for longs)
  - Logs all simulated trades with close reason (SL_HIT, TP_HIT, EXIT_SIGNAL, MANUAL_CLOSE, GAP_FORCED_CLOSE)
  - Logs execution events for transparency (when/why each signal triggered)
- **Basic risk management:**
  - Fixed position size (user-configurable, bounds: 1-1000 shares, prevents P&L overflow)
  - Stop loss + take profit with constraints (SL must be < entry for longs, TP > entry)
  - Gap handling: Forced close if gap exceeds 10% (e.g., overnight gaps)
- **Paper trading dashboard:**
  - Real-time positions (symbol, entry price, current price, unrealized P&L, SL/TP levels)
  - Trade history (entry, exit, P&L, close reason, duration)
  - Performance metrics (trades count, wins, losses, win rate, max drawdown, Sharpe)
  - **Backtest vs Paper comparison:** Alert if diverge >10% (investigates strategy robustness)

#### Phase 3: Enhanced Indicator Menu (Weeks 1-3, parallel)

- Organize existing 30+ indicators into 5 categories:
  - **Trend:** SuperTrend, Moving Averages, ADX, CCI, DMI, ROC
  - **Momentum:** RSI, MACD, Stochastic, KDJ, Rate of Change
  - **Volatility:** ATR, Bollinger Bands, Keltner Channel, Donchian Channel, Volatility Profile
  - **Volume:** Volume, Volume Profile, On-Balance Volume
  - **Pattern:** Support/Resistance, Market Regime, Ichimoku
- **UI:** Categorical sidebar with search, quick-add buttons, indicator info cards (default parameters, bullish/bearish signals)
- **Metadata:** Each indicator tagged with bullish/bearish signal directions to guide strategy building

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Analyst Workstation (React)                 │
├─────────────────────────────────────────────────────────────────┤
│  • Condition Builder (forms + visual hybrid)                     │
│  • Indicator Menu (30-40 categorized, searchable)                │
│  • Backtest Runner (extend existing)                             │
│  • Paper Trading Dashboard (live P&L, positions, trades)         │
└────────────────────────────┬────────────────────────────────────┘
                             │
             ┌───────────────┼───────────────┐
             ▼               ▼               ▼
     ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
     │  Backtest    │ │  Paper       │ │   Strategy   │
     │  Engine      │ │  Trading     │ │   Execution  │
     │  (Python)    │ │  Engine      │ │  (TypeScript)│
     │              │ │  (TypeScript)│ │              │
     └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
            │                 │                │
            └─────────────────┼────────────────┘
                              ▼
                   ┌──────────────────────┐
                   │   Supabase Postgres  │
                   ├──────────────────────┤
                   │ • Strategies         │
                   │ • Backtest Results   │
                   │ • Paper Trades       │
                   │ • Execution Log      │
                   └──────────────────────┘
                              │
                              ▼
                   ┌──────────────────────┐
                   │  Alpaca API          │
                   │  (Real-time data)    │
                   └──────────────────────┘
```

---

## Technical Approach

### 1. Database Schema

#### New Tables (Paper Trading)

```sql
-- Real-time paper trading positions
CREATE TABLE paper_trading_positions (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES auth.users,
  strategy_id UUID NOT NULL REFERENCES strategy_user_strategies,
  symbol_id UUID NOT NULL REFERENCES symbols,
  timeframe TEXT NOT NULL,
  entry_price DECIMAL NOT NULL,
  current_price DECIMAL,
  quantity INT NOT NULL,
  entry_time TIMESTAMP NOT NULL,
  direction TEXT NOT NULL CHECK (direction IN ('long', 'short')),
  stop_loss_price DECIMAL,
  take_profit_price DECIMAL,
  status TEXT NOT NULL DEFAULT 'open',
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Closed paper trades
CREATE TABLE paper_trading_trades (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES auth.users,
  strategy_id UUID NOT NULL REFERENCES strategy_user_strategies,
  symbol_id UUID NOT NULL REFERENCES symbols,
  timeframe TEXT NOT NULL,
  entry_price DECIMAL NOT NULL,
  exit_price DECIMAL NOT NULL,
  quantity INT NOT NULL,
  direction TEXT NOT NULL,
  entry_time TIMESTAMP NOT NULL,
  exit_time TIMESTAMP NOT NULL,
  pnl DECIMAL NOT NULL, -- profit/loss in $ amount
  pnl_pct DECIMAL NOT NULL, -- profit/loss %
  trade_reason TEXT, -- "TP hit", "SL hit", "Exit signal", "Manual close"
  created_at TIMESTAMP DEFAULT NOW()
);

-- Strategy execution log (what triggered what)
CREATE TABLE strategy_execution_log (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES auth.users,
  strategy_id UUID NOT NULL REFERENCES strategy_user_strategies,
  symbol_id UUID NOT NULL REFERENCES symbols,
  timeframe TEXT NOT NULL,
  candle_time TIMESTAMP NOT NULL,
  signal_type TEXT NOT NULL CHECK (signal_type IN ('entry', 'exit', 'condition_met')),
  triggered_conditions TEXT[], -- JSON array of condition IDs that triggered
  action_taken TEXT, -- "Entry order placed", "Exit order placed", "SL triggered"
  execution_details JSONB,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Paper trading performance metrics (aggregated stats)
CREATE TABLE paper_trading_metrics (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES auth.users,
  strategy_id UUID NOT NULL REFERENCES strategy_user_strategies,
  symbol_id UUID NOT NULL REFERENCES symbols,
  timeframe TEXT NOT NULL,
  period_start TIMESTAMP NOT NULL,
  period_end TIMESTAMP NOT NULL,
  trades_count INT DEFAULT 0,
  win_count INT DEFAULT 0,
  loss_count INT DEFAULT 0,
  avg_win DECIMAL,
  avg_loss DECIMAL,
  win_rate DECIMAL, -- percent
  profit_factor DECIMAL,
  max_drawdown DECIMAL,
  total_pnl DECIMAL,
  total_pnl_pct DECIMAL,
  sharpe_ratio DECIMAL,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Enhanced strategy conditions (support multi-condition AND/OR)
ALTER TABLE strategy_user_conditions ADD COLUMN (
  logical_operator TEXT DEFAULT 'AND' CHECK (logical_operator IN ('AND', 'OR')),
  parent_condition_id UUID REFERENCES strategy_user_conditions,
  condition_group_id UUID, -- Group related conditions
  sort_order INT DEFAULT 0
);
```

#### Modified Tables

- **`strategy_user_strategies`:** Add `paper_trading_enabled BOOLEAN DEFAULT FALSE`, `paper_capital DECIMAL DEFAULT 10000`, `paper_start_date TIMESTAMP`
- **`strategy_execution_log`:** New table to track every signal evaluation and action taken

### 2. Condition Builder Component (React)

**File:** `frontend/src/components/StrategyConditionBuilder.tsx`

```tsx
// Architecture overview:
// - Left panel: Form inputs (condition type, operator, values)
// - Right panel: Visual tree diagram with AND/OR logic
// - Reusable for buy/sell entry, exit, stop-loss conditions

type Condition = {
  id: string;
  indicator: string; // "RSI", "MACD", etc.
  operator: string; // ">", "<", "cross_up", etc.
  value: number | string;
  crossWith?: string; // "MACD_Signal" for cross_up
  logicalOp: "AND" | "OR";
  parentId?: string; // For nested logic
};

// Visual diagram shows:
// ┌─────────────────┐
// │  RSI > 70       │ ──AND──┐
// └─────────────────┘        ├─→ ENTRY SIGNAL
// ┌─────────────────┐        │
// │  Volume > Avg   │ ──────┘
// └─────────────────┘

// Features:
// - Add/edit/delete conditions
// - Drag to reorder
// - Toggle AND/OR logic between conditions
// - Validation: no orphaned conditions, max 5 conditions per signal type
// - Visual preview updates in real-time
```

**Integration:** Hook into existing `StrategyUI.tsx`, replace current form with new builder.

### 3. Paper Trading Execution Engine (TypeScript/Edge Function)

**File:** `supabase/functions/paper-trading-executor/index.ts`

**Architecture Improvements from Research:**

1. **Type-Safe Error Handling** — Replace implicit types with discriminated unions
2. **Optimistic Locking** — Prevent race conditions on concurrent position closures
3. **Batch Data Fetching** — Fetch bars once, reuse for multiple strategies (3-5x speedup)
4. **Indicator Caching** — Calculate RSI once per candle, share across strategies
5. **Concurrency Limiting** — Use semaphore to prevent executor overload

```typescript
// Type-safe contract with discriminated unions
type ExecutionResult =
  | { success: true; action: 'entry_created' | 'position_closed' | 'no_action'; positionId?: string }
  | { success: false; error: ExecutionError };

type ExecutionError =
  | { type: 'condition_eval_failed'; indicator: string; reason: string }
  | { type: 'position_locked'; reason: 'concurrent_close_detected' }
  | { type: 'invalid_market_data'; reason: string }
  | { type: 'position_constraints_violated'; violations: string[] };

async function executePaperTradingCycle(symbol: string, timeframe: string): Promise<ExecutionResult[]> {
  try {
    // 1. Fetch active strategies for symbol/timeframe
    const strategies = await fetchActiveStrategies(symbol, timeframe);

    // 2. Get latest market data ONCE (reuse for all strategies) — OPTIMIZATION
    const bars = await fetchLatestBars(symbol, timeframe, 100);

    // Validate market data before proceeding
    if (!validateBars(bars)) {
      return [{ success: false, error: { type: 'invalid_market_data', reason: 'null bars detected' }}];
    }

    // Pre-calculate indicators for all strategies sharing same timeframe — OPTIMIZATION
    const indicatorCache = new Map<string, number>();

    // 3. Evaluate strategies with concurrency limiting
    const results: ExecutionResult[] = [];
    const limiter = new Semaphore(5); // Max 5 concurrent strategies

    for (const strategy of strategies) {
      await limiter.acquire();
      try {
        if (!strategy.paper_trading_enabled) continue;

        const result = await executeStrategyWithLocking(
          strategy,
          symbol,
          bars,
          indicatorCache
        );
        results.push(result);
      } finally {
        limiter.release();
      }
    }

    return results;
  } catch (error) {
    // Log unexpected errors for debugging
    await logExecutorError(symbol, timeframe, error);
    return [{ success: false, error: { type: 'condition_eval_failed', indicator: 'unknown', reason: error.message }}];
  }
}

// Optimistic locking: update only if status = 'open'
async function executeStrategyWithLocking(
  strategy: Strategy,
  symbol: string,
  bars: Bar[],
  indicatorCache: Map<string, number>
): Promise<ExecutionResult> {
  try {
    // Evaluate conditions on latest bar
    const entrySignal = evaluateConditions(strategy.buy_conditions, bars, indicatorCache);
    const exitSignal = evaluateConditions(strategy.sell_conditions, bars, indicatorCache);

    // Check existing positions with optimistic lock
    const openPosition = await db
      .from('paper_trading_positions')
      .select('*')
      .eq('strategy_id', strategy.id)
      .eq('symbol_id', symbol)
      .eq('status', 'open') // OPTIMISTIC LOCK
      .single();

    if (entrySignal && !openPosition?.data) {
      // Entry: next bar's open + slippage
      const latestBar = bars[bars.length - 1];
      const slippageMultiplier = 1 + (strategy.slippage_pct / 100); // Bounded 0.01%-5%
      const entryPrice = latestBar.close * slippageMultiplier;

      // Validate position constraints before creating
      const constraints = validatePositionConstraints(
        entryPrice,
        strategy.position_size,
        strategy.stop_loss_pct,
        strategy.take_profit_pct
      );
      if (!constraints.valid) {
        return {
          success: false,
          error: {
            type: 'position_constraints_violated',
            violations: constraints.violations
          }
        };
      }

      const positionId = await createPaperPosition(
        strategy.id,
        symbol,
        entryPrice,
        strategy.position_size,
        strategy.stop_loss_pct,
        strategy.take_profit_pct
      );

      await logExecution(strategy.id, symbol, 'entry_signal', { entryPrice, positionId });
      return { success: true, action: 'entry_created', positionId };
    }

    if (openPosition?.data) {
      const latestPrice = bars[bars.length - 1].close;
      const closeReason = determineCloseReason(
        openPosition.data,
        latestPrice,
        exitSignal,
        bars
      );

      if (closeReason) {
        // Use optimistic lock on UPDATE: only close if status still 'open'
        const closedTrade = await db
          .from('paper_trading_positions')
          .update({
            status: 'closed',
            exit_price: latestPrice,
            exit_time: new Date(),
            pnl: calculateP&L(openPosition.data.entry_price, latestPrice, openPosition.data.quantity),
            close_reason: closeReason
          })
          .eq('id', openPosition.data.id)
          .eq('status', 'open') // Race condition prevention!
          .single();

        if (!closedTrade.data) {
          // Race condition detected: another process closed this position
          return {
            success: false,
            error: { type: 'position_locked', reason: 'concurrent_close_detected' }
          };
        }

        await logExecution(strategy.id, symbol, 'exit_signal', { exitPrice: latestPrice, reason: closeReason });
        return { success: true, action: 'position_closed' };
      }
    }

    return { success: true, action: 'no_action' };
  } catch (error) {
    return {
      success: false,
      error: { type: 'condition_eval_failed', indicator: 'unknown', reason: error.message }
    };
  }
}

// Helper: Evaluate multi-condition logic with type-safe operators
function evaluateConditions(
  conditions: Condition[],
  bars: Bar[],
  indicatorCache: Map<string, number>
): boolean {
  if (!conditions || conditions.length === 0) return false;

  // Build decision tree and evaluate
  return evaluateConditionTree(buildConditionTree(conditions), bars, indicatorCache);
}

function validatePositionConstraints(
  entryPrice: number,
  quantity: number,
  slPct: number,
  tpPct: number
): { valid: boolean; violations: string[] } {
  const violations: string[] = [];

  if (entryPrice <= 0) violations.push('Entry price must be positive');
  if (quantity <= 0 || quantity > 1000) violations.push('Quantity out of bounds [1, 1000]');
  if (slPct < 0.1 || slPct > 20) violations.push('SL must be 0.1%-20% (typical: 2%)');
  if (tpPct < 0.1 || tpPct > 100) violations.push('TP must be 0.1%-100% (typical: 5%)');

  return { valid: violations.length === 0, violations };
}

function determineCloseReason(
  position: PaperPosition,
  currentPrice: number,
  exitSignal: boolean,
  bars: Bar[]
): 'SL_HIT' | 'TP_HIT' | 'EXIT_SIGNAL' | 'GAP_FORCED_CLOSE' | null {
  // Check for gaps (>10% move from last close to current)
  if (Math.abs((currentPrice - bars[bars.length - 2]?.close) / bars[bars.length - 2].close) > 0.10) {
    return 'GAP_FORCED_CLOSE';
  }

  if (currentPrice <= position.stop_loss_price) return 'SL_HIT';
  if (currentPrice >= position.take_profit_price) return 'TP_HIT';
  if (exitSignal) return 'EXIT_SIGNAL';

  return null;
}
```

**Execution triggers:**
- **Option 1 (v1 MVP):** Manual button "Run Paper Trading Now" on dashboard (analyst-driven)
- **Option 2 (v2 Production):** Scheduled Edge Function every 1m/5m/1h using `pg_cron` with monitoring

**Performance targets** (from research):
- Per-strategy execution: <500ms (current plan target)
- 5 concurrent strategies: <2.5s total
- Executor cold start: ~180ms (Supabase optimized)

### 4. Paper Trading Dashboard (React)

**File:** `frontend/src/components/PaperTradingDashboard.tsx`

Displays:
- **Live Positions:** Table with symbol, entry price, current price, unrealized P&L, SL/TP levels
- **Trades History:** Closed trades with entry/exit prices, P&L, duration
- **Comparison Widget:**
  - Backtest P&L vs Paper Trading P&L (for same strategy)
  - Alerts if diverge significantly (strategy performing worse live)
- **Real-time Chart:** Show entry/exit markers and indicator signals
- **Performance Metrics:** Win rate, Sharpe ratio, max drawdown (updated every candle)

### 5. Indicator Menu Categorization

**File:** `frontend/src/components/IndicatorMenu.tsx`

```tsx
const indicatorCategories = {
  trend: [
    { name: "SuperTrend", bullish: "above", bearish: "below", params: ["period", "multiplier"] },
    { name: "ADX", bullish: "> 25", bearish: "< 25", params: ["period"] },
    { name: "Moving Averages", bullish: "SMA50 > SMA200", bearish: "inverse", params: ["fast", "slow"] },
    // ... 6+ more
  ],
  momentum: [
    { name: "RSI", bullish: "> 50", bearish: "< 50", params: ["period", "overbought", "oversold"] },
    { name: "MACD", bullish: "cross_up", bearish: "cross_down", params: ["fast", "slow", "signal"] },
    // ... 5+ more
  ],
  volatility: [
    // ... 6+ indicators
  ],
  volume: [
    // ... 3+ indicators
  ],
  pattern: [
    // ... Support/Resistance, Market Regime, etc.
  ]
};

// UI: Sidebar with expandable categories, search, quick-add buttons
// Hover to show parameter info and typical bullish/bearish signal ranges
```

### 6. Multi-Condition AND/OR Logic

**File:** `ml/src/evaluation/condition_evaluator.py` or `supabase/functions/_shared/condition_evaluator.ts`

```typescript
// Build condition tree from database records
type ConditionNode = {
  id: string;
  indicator: string;
  operator: string;
  value: number;
  logicalOp: "AND" | "OR"; // Operator to parent node
  children: ConditionNode[];
};

function evaluateConditionTree(node: ConditionNode, bars: Bar[]): boolean {
  const indicatorValue = calculateIndicator(node.indicator, bars);
  const conditionMet = evaluateOperator(indicatorValue, node.operator, node.value);

  if (!node.children.length) return conditionMet;

  const childResults = node.children.map(child => evaluateConditionTree(child, bars));

  if (node.logicalOp === "AND") {
    return conditionMet && childResults.every(r => r);
  } else {
    return conditionMet || childResults.some(r => r);
  }
}

// Example: (RSI > 70 AND Volume > Avg) OR (MACD cross_up Signal)
// ┌─────────────────────────────┐
// │ (RSI > 70 AND Vol > Avg)    │──OR──┐
// │                             │      └→ ENTRY
// │ MACD cross_up Signal        │
// └─────────────────────────────┘
```

---

## Critical Fixes Required Before v1 Deployment

**Security Audit & Data Integrity Review** identified 12 critical issues that BLOCK v1 deployment. These must be completed before Phase 1 implementation begins.

### CRITICAL Issues (Must Fix)

| Issue | Risk | Fix Time | Solution |
|-------|------|----------|----------|
| **Missing RLS policies** | User A reads User B's trades (privacy violation) | 2-4h | Add `enable rls` + policies on all paper_trading_* tables |
| **Unvalidated slippage** | Users set 500% slippage, inflate backtest | 4-6h | Bounds: 0.01%-5% with CHECK constraint |
| **Position size unconstrained** | P&L overflow, invalid entries (price=0, qty=9M) | 4-6h | Validate: price > 0, 1 ≤ qty ≤ 1000, SL < entry < TP |
| **Race condition on closure** | Two cycles close same position → phantom duplicate trades | 2-3h | Use optimistic lock: `WHERE status = 'open'` on UPDATE |
| **No market data validation** | Inject false OHLCV to trigger false signals | 4-6h | Validate: no nulls, no negative OHLC, gap < 10% |
| **Condition evaluator split** | Backtest (Python) ≠ Paper trading (TypeScript) logic drift | 6-8h | Unified: TypeScript Edge Function, call from both |

### HIGH Priority Issues

| Issue | Risk | Fix Time | Solution |
|-------|------|----------|----------|
| **No immutability on trades** | Analysts modify closed trades, hide losses | 1-2h | RLS: make trades append-only, reject UPDATEs |
| **Partial failure handling** | Position created, entry_price UPDATE fails → orphaned invalid position | 1-2h | Add NOT NULL constraints, atomic transactions |
| **SL/TP unconstrained** | Users set SL=-100%, TP=+1000% | 2-3h | Validate: 0.1% ≤ SL ≤ 20%, 0.1% ≤ TP ≤ 100% |
| **Missing database indices** | Queries 5-10x slower, N+1 problems | 1-2h | Add indices on (user_id, strategy_id, symbol_id, status) |
| **Divergence thresholds undefined** | "Alert if diverge significantly" is vague | 2-3h | Define: >10% divergence = high alert, >20% = critical |

### Implementation Timeline

**Week 1 (Days 1-5):** Critical & High fixes (in parallel)
- Database migrations: RLS, constraints, indices (2-3 days)
- Edge Function refactoring: Type safety, optimistic locking (2-3 days)
- Validation functions: Market data, position constraints (1 day)

**Overlap:** Start Phase 1 UI work on Day 3-4 while DB fixes progress

**Week 2:** Final validation, code review, staging deployment

**Total:** 18-22 days (3+ week addition to timeline if starting from today)

---

## System-Wide Impact

### Interaction Graph

**Paper Trading Execution Flow:**

```
1. Alpaca publishes new candle (e.g., 15:30 close)
   ↓
2. Edge Function paper-trading-executor triggered
   ├─ Fetch all active strategies
   ├─ Get last 100 bars for each symbol/timeframe
   ├─ Evaluate buy/sell conditions
   ├─ Check existing paper positions
   ├─ Create entry orders (insert into paper_trading_positions)
   ├─ Log execution (insert into strategy_execution_log)
   └─ Close positions if SL/TP/exit signal hit (update → paper_trading_trades)
   ↓
3. Dashboard subscribes to changes on paper_trading_positions
   ├─ Real-time position list updates
   ├─ Unrealized P&L recalculates
   └─ Chart markers update for new entries/exits
   ↓
4. Backtest comparison widget recalculates
   └─ Alerts analyst if paper P&L diverges from backtest
```

### Error Propagation

**Potential failures:**
- **Condition evaluation fails** → Log error, skip strategy for this candle, alert user (don't fail silently)
- **Order execution fails** → Strategy position stuck, retry next candle or manual intervention
- **Chart data unavailable** → Use last cached bar, wait for next real-time update
- **Indicator calculation fails** (missing data) → Use previous bar's value + flag

**Handling:** Wrap execution in try-catch, store errors in execution_log table, dashboard shows "Strategy halted - check logs".

### State Lifecycle Risks

1. **Partial position entry** — Quantity set but entry_price fails to update → Trade executed at wrong price
   - **Mitigation:** Atomic transaction: insert position with all fields, or rollback
2. **Position orphan** — Entry created but exit signal never fires → Trade hangs indefinitely
   - **Mitigation:** Add "max hold time" rule (e.g., close after 20 bars) + manual close button
3. **Candle timing ambiguity** — Intraday (15m/1h) vs daily (1D) bars have different timestamp formats
   - **Mitigation:** Use existing `normalize_timestamp()` utility; store both Unix + business day string

### API Surface Parity

- **Backtest engine:** Already supports custom strategies — paper trading uses same condition evaluator ✅
- **Strategy CRUD:** Existing REST endpoints — paper trading adds optional fields ✅
- **Chart endpoint:** GET /chart already shows backtest trades — extend to show paper trading overlays ✅
- **Real-time signals:** New capability — needs new subscription/webhook mechanism

### Integration Test Scenarios

1. **Strategy enters, SL hits before TP** — Verify trade closes at SL price, not TP
2. **Two strategies trade same symbol** — Capital allocation, position overlap handling
3. **Indicator changes mid-strategy** — Old positions continue under old logic, new entries use new logic
4. **Market gaps overnight** — Intraday position held past close; next day's open is different — verify slippage applied
5. **Backtest vs Paper divergence** — Strategy A backtests +5%, papers at -2% — dashboard alerts and suggests debugging

---

## Implementation Phases

### Phase 1: Condition Builder UI Enhancement (Weeks 1-2)

**Goal:** Analysts can build multi-condition strategies with visual feedback.

**Tasks:**

1. **Design condition builder component architecture**
   - Form inputs for indicator, operator, value
   - Visual tree renderer showing AND/OR logic
   - Drag-to-reorder conditions
   - File: Create `frontend/src/components/StrategyConditionBuilder.tsx`

2. **Implement form inputs**
   - Indicator dropdown (categorized)
   - Operator dropdown (>/</>=/<==/cross_up/cross_down/etc.)
   - Value input (number, or "close", "high", "low", etc.)
   - Cross-with selector (for cross_up/cross_down)

3. **Implement visual tree diagram**
   - Render conditions as boxes
   - Draw connectors showing AND/OR logic
   - Real-time update as user edits

4. **Integrate with existing StrategyUI**
   - Replace current form-based builder
   - Update strategy_user_conditions table schema if needed

5. **Test**
   - Unit: Condition validation, tree rendering
   - Integration: Save/load multi-condition strategy, backtest it

**Acceptance Criteria:**
- [ ] Can build strategy with 3+ conditions connected by AND/OR
- [ ] Visual diagram updates in real-time as user edits
- [ ] Saved strategies persist and load correctly
- [ ] Backtest engine handles multi-condition logic

---

### Phase 2: Enhanced Indicator Menu (Weeks 1-3, parallel with Phase 1)

**Goal:** Indicator menu is discoverable, categorized, with helpful metadata.

**Tasks:**

1. **Catalog all 30-40 indicators**
   - Map to categories: Trend, Momentum, Volatility, Volume, Pattern
   - Document default parameters
   - Classify bullish/bearish signal directions

2. **Build IndicatorMenu component**
   - Sidebar with expandable categories
   - Search box
   - Quick-add buttons
   - Hover cards showing default params + signal guidance

3. **Integrate with condition builder**
   - Clicking "Add Condition" opens indicator menu
   - Selected indicator populates form

4. **Test**
   - Can find any indicator via search or category
   - Selected indicator auto-fills default params

**Acceptance Criteria:**
- [ ] All 30-40 indicators organized in 5 categories
- [ ] Search finds indicator by name or synonym
- [ ] Default parameters match indicator specs
- [ ] Integrated with condition builder

---

### Phase 3: Paper Trading Infrastructure (Weeks 2-4)

**Goal:** Real-time simulated trading with position tracking and P&L calculation.

**Tasks:**

1. **Database migrations**
   - Create paper_trading_positions, paper_trading_trades, strategy_execution_log tables
   - Add paper_trading fields to strategy_user_strategies
   - Create indices on (user_id, strategy_id, symbol_id, timeframe)
   - Set up RLS policies: user can only see own paper trades

2. **Paper trading executor (Edge Function)**
   - Listen to candle closes (manual trigger or scheduled)
   - For each active strategy:
     - Evaluate entry/exit conditions
     - Create positions on entry signal
     - Close positions on exit/SL/TP
     - Log every execution event
   - File: `supabase/functions/paper-trading-executor/index.ts`

3. **Position tracking**
   - Entry price + slippage calculation
   - Unrealized P&L (current price vs entry)
   - SL/TP enforcement
   - Trade close with reason (SL, TP, exit signal)

4. **Paper trading dashboard**
   - Table: Open positions (symbol, entry price, current price, unrealized P&L)
   - Table: Trade history (entry, exit, P&L, duration)
   - Metrics panel: Trades count, win rate, profit factor, max drawdown, Sharpe
   - Comparison widget: Backtest vs Paper P&L divergence alerts
   - File: `frontend/src/components/PaperTradingDashboard.tsx`

5. **Chart integration**
   - Overlay paper trading entry/exit markers on chart (green/red circles on candles)
   - Show position details on hover
   - Extend existing GET /chart endpoint

6. **Real-time P&L updates**
   - Subscribe to live price updates
   - Recalculate unrealized P&L every candle
   - Dashboard updates without page refresh

7. **Test**
   - Manual: Create strategy, run paper trading, verify entry/exit logic
   - Integration: Paper trade P&L matches manual calculation
   - Edge case: Gaps, limits, slippage, multiple positions
   - Performance: Can handle 10-20 concurrent strategies without latency

**Performance Targets** (from research):
- Executor latency: <500ms per strategy per candle (with optimistic locking, batching)
- Dashboard update: <1s from position close to UI refresh
- Chart rendering: <200ms for 1000 historical trades (virtualization)
- Database query: <50ms (with indices on (user_id, strategy_id, symbol_id, status))

**Optimization Checklist** (required for Phase 3):
- [ ] Batch data fetches: Fetch bars once, reuse for all strategies (3-5x speedup)
- [ ] Indicator caching: Calculate indicators once per candle, cache for 10+ strategies
- [ ] Database indices added on paper_trading_positions (user_id, strategy_id, symbol_id, timeframe, status)
- [ ] Selective indicator calculation (only compute needed indicators, not all 40)
- [ ] Realtime filtering with RLS to reduce PubSub broadcast amplification

**Acceptance Criteria:**
- [ ] Can enable paper trading on any strategy
- [ ] Entry/exit conditions trigger correctly (with optimistic locking preventing races)
- [ ] Positions tracked accurately with P&L (constraints enforced, no orphans)
- [ ] Paper vs backtest P&L compared and alerted (>10% divergence = warning)
- [ ] No orphaned positions (max hold time enforced, gap-forced closes handled)
- [ ] Executor latency <500ms per strategy (measured under load)
- [ ] Chart renders 1000 trades without lag (virtualization)

---

### Phase 4: Multi-Condition Logic & Validation (Weeks 3-4)

**Goal:** Complex strategies with nested AND/OR conditions evaluate correctly.

**Tasks:**

1. **Condition evaluator (shared TypeScript utility)**
   - Parse condition tree from database
   - Recursive evaluation with AND/OR operators
   - Return true/false for entry/exit
   - File: `supabase/functions/_shared/condition_evaluator.ts`

2. **Update condition table schema**
   - Add logical_operator, parent_condition_id, condition_group_id
   - Migration file: `supabase/migrations/20260301000000_strategy_conditions_nested.sql`

3. **Backtest + paper trading condition evaluation**
   - Both use same evaluator for consistency
   - Bar-by-bar evaluation in historical and real-time

4. **Validation rules**
   - Max 5-10 conditions per strategy (prevent over-optimization)
   - No orphaned conditions (parent missing)
   - Detect circular logic (A depends on B, B depends on A)
   - UI: Show "Valid" or "Invalid" badge

5. **Test**
   - Condition tree with 5 levels deep: (A AND (B OR C) AND (D OR E))
   - Backtest: Same tree gives same results as paper trading
   - Validation: Reject invalid trees with clear errors

**Acceptance Criteria:**
- [ ] Complex AND/OR conditions evaluate correctly
- [ ] Backtest + paper trading use same logic
- [ ] Invalid strategies caught before execution

---

## Alternative Approaches Considered

### 1. Condition Builder UI

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| **Drag-drop visual blocks (React Flow)** | Intuitive, flexible, looks professional | Heavy library, complex to build, mobile unfriendly | ❌ Rejected |
| **Forms only** | Simple, lightweight | Ugly for complex logic, hard to visualize AND/OR nesting | ❌ Current state (rejected) |
| **Code editor (JSON)** | Flexible, powerful | Non-technical analysts can't use it | ❌ Rejected |
| **Custom hybrid (forms + visual tree)** | Balances ease-of-use + visualization, mobile-friendly | More custom code | ✅ **CHOSEN** |

**Rationale:** Hybrid gives analysts the best of both worlds—easy form editing + instant visual feedback of logic structure. Lighter-weight than React Flow, accessible to non-coders.

### 2. Paper Trading Trigger

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| **Manual button on dashboard** | Simple, user controls when it runs, good for learning | Requires analyst to click frequently, easy to forget | ✅ **v1** |
| **Scheduled (every 1m/5m/1h)** | Automatic, production-ready | Need cron infrastructure, more complex | v2 |
| **Real-time event-driven** | Most accurate, reacts immediately | Complex, requires pub/sub setup | v2 |

**Rationale:** Start with manual execution (v1) to validate logic. Upgrade to scheduled/real-time once proven.

### 3. Risk Management

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| **Fixed position size only** | Simple, predictable | Doesn't scale with account growth | ❌ Rejected |
| **Fixed size + SL/TP** | Straightforward, practical | Doesn't address leverage or margin | ✅ **v1** |
| **Dynamic sizing (Kelly Criterion)** | Optimal, scales account | Requires historical win rate (chicken-egg) | v2 |
| **Multi-position leverage** | Sophisticated, capital efficient | Complex risk management, potential disasters | v2+ |

**Rationale:** Fixed size + SL/TP is simple, safe, and covers 80% of paper trading needs. Learning & optimization (v2) will improve sizing.

---

## Acceptance Criteria

### Functional Requirements

**Condition Builder:**
- [ ] Create strategies with 2-5 conditions using hybrid form + visual UI
- [ ] Conditions connected with AND/OR logic operators
- [ ] Save/load strategies with multi-condition setup
- [ ] Visual tree diagram updates in real-time
- [ ] Backtest runs correctly on multi-condition strategies

**Enhanced Indicator Menu:**
- [ ] 30-40 indicators organized into 5 categories
- [ ] Search finds any indicator by name
- [ ] Default parameters auto-populate
- [ ] Quick-add button integrates with condition builder

**Paper Trading Engine:**
- [ ] Enable/disable paper trading per strategy
- [ ] Set starting capital, position size, SL/TP levels
- [ ] Manual "Run Paper Trading Now" button
- [ ] Entry/exit conditions trigger and create positions
- [ ] SL/TP hits close positions automatically
- [ ] Open positions show unrealized P&L
- [ ] Closed trades logged with entry/exit prices, P&L, duration

**Paper Trading Dashboard:**
- [ ] Real-time positions table (symbol, entry, current, unrealized P&L)
- [ ] Trade history table (entry, exit, P&L, reason)
- [ ] Performance metrics (wins, losses, win rate, max DD, Sharpe)
- [ ] Backtest vs Paper comparison widget
- [ ] Alerts if paper P&L diverges >10% from backtest prediction

**Chart Integration:**
- [ ] Paper trading entry/exit markers overlay on candlesticks
- [ ] Markers color-coded: green entry, red exit, orange SL/TP
- [ ] Hover shows position details
- [ ] Extend GET /chart endpoint to include paper trades

### Non-Functional Requirements

- **Performance:** Paper trading executor runs <500ms per strategy per candle
- **Latency:** Dashboard updates within 1 second of new position/trade
- **Scalability:** Handles 10-20 concurrent strategies without degradation
- **Accuracy:** Paper P&L matches manual calculation to nearest penny
- **Reliability:** No orphaned positions; max hold time enforced; error logging

### Quality Gates

- [ ] 80%+ test coverage on condition evaluator + paper trading executor
- [ ] Backtest + paper trading logic validated against known scenarios (4-5 integration tests)
- [ ] Code review: Architecture strategist + frontend reviewer
- [ ] Documentation: API contracts, data model, condition syntax
- [ ] UI/UX: Analyst feedback on condition builder usability (informal test with 2-3 users)

---

## Success Metrics

### User Experience

1. **Time to build a strategy:** Analyst can build 3-condition strategy in <5 minutes (visual builder reduces friction)
2. **Confidence in strategies:** Paper trading results within ±10% of backtest (validates strategies work live)
3. **Feature adoption:** 50%+ of active users enable paper trading on at least one strategy within first month

### Technical

1. **Backtest ↔ Paper parity:** For same strategy, win rate matches ±5% (confidence strategies generalize)
2. **Execution accuracy:** Paper trade P&L matches manual calculation (no bugs in logic)
3. **System reliability:** 99.9% uptime for paper trading executor (production-grade)

### Product

1. **Signal quality:** Analyze if paper-traded strategies beat buy-and-hold on test symbols
2. **Learning opportunity:** Log patterns in strategies that paper-trade well vs poorly (informs v2 optimization)

---

## Dependencies & Prerequisites

### Technical

- **Existing:** SwiftBolt strategy DB schema, backtest engine, chart visualization, indicator library
- **New:** React condition builder component, paper trading executor function, dashboard UI
- **External:** Alpaca real-time data (already integrated via existing GET /chart)

### Team & Skills

- **React frontend developer** (4-6 weeks) — Condition builder + dashboard
- **TypeScript/Edge Functions** (2-3 weeks) — Paper trading executor
- **Python/evaluation** (1-2 weeks) — Backtest integration
- **QA/testing** (1 week) — Validation, edge cases

### Timing

- **Critical path:** Phase 3 (paper trading) depends on Phase 1 (condition builder) completion
- **Parallel:** Phase 2 (indicator menu) can run in parallel
- **Total:** ~4-5 weeks from start to MVP deployment

---

## Risk Analysis & Mitigation

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|-----------|
| **Condition evaluator bugs** | Strategies execute incorrectly | Medium | Comprehensive test suite (unit + integration), backtest validation |
| **Real-time data latency** | Paper trades execute late, miss entry points | Medium | Use existing Alpaca connection; validate timestamp consistency |
| **Capital allocation conflicts** | Two strategies trade overlapping capital | Low | Start with single-strategy validation; multi-strategy in v2 |
| **Indicator calculation variance** | Paper trading uses different indicator value than backtest | Medium | Unified indicator library; validate both use same source data |
| **Chart performance at scale** | Dashboard slow with 100+ historical trades | Low | Pagination, virtual scrolling; archive old trades |
| **User confusion: backtest vs paper** | Analyst expects identical results, gets different numbers | Medium | Dashboard explicitly shows both, with divergence alerts + explanation |

---

## Resource Requirements

### Team

- **1 React frontend developer** — 4-6 weeks
- **1 TypeScript/Edge Functions engineer** — 2-3 weeks
- **0.5 Python evaluation engineer** — 1-2 weeks (backtest integration)
- **1 QA tester** — 1-2 weeks (validation)

### Infrastructure

- **Database:** Additional indices on paper_trading tables (minimal)
- **Compute:** Paper trading executor Edge Function (runs <500ms, low cost)
- **Storage:** Trade history (append-only, minimal growth)

### External

- **Alpaca API:** Already available; no additional cost for real-time data

---

## Future Considerations

### v2 Features

1. **Parameter Learning:** Bot auto-tunes indicator thresholds based on live trade outcomes
2. **Multi-Strategy Allocation:** Run 5-10 strategies in parallel with capital weighting
3. **Advanced Risk:** Kelly Criterion sizing, correlation hedging, portfolio-level drawdown limits
4. **Real-time Execution:** Paper trading auto-runs every candle (not manual)
5. **Live Trading:** Deploy paper-trading strategies to live market with real capital
6. **Signal Webhooks:** Send alerts to Slack/email when entry/exit occurs

### Long-term Vision

- **Self-sustaining:** Profitable strategies fund themselves and scale capital
- **Continuously learning:** Feedback loop from live trades → parameter optimization → better forecasts
- **Autonomous execution:** Bot runs unattended, learning and trading 24/5

---

## Documentation Plan

### Developer Documentation

- **Architecture:** Condition builder design, paper trading flow, data model
- **API Reference:** Condition evaluator function signature, paper trading executor contract
- **Code examples:** How to add new operator, how to extend indicator library
- **Testing guide:** Unit test patterns, integration test scenarios

### User Documentation

- **Strategy Builder Guide:** How to build multi-condition strategies, operator meanings
- **Paper Trading 101:** What is paper trading, how to interpret results, backtest vs live
- **Troubleshooting:** Why strategy isn't triggering, P&L divergence explanation

### Release Notes

- New features: Condition builder, paper trading, indicator menu
- Breaking changes: None (backward compatible)
- Known issues: (to be filled in post-QA)

---

## Sources & References

### Origin

- **Brainstorm document:** [docs/brainstorms/2026-02-25-strategy-platform-brainstorm.md](docs/brainstorms/2026-02-25-strategy-platform-brainstorm.md)
  - **Key decisions carried forward:**
    1. MVP: Strategy builder + backtesting + paper trading (live trading v2)
    2. 30-40 indicators organized by category
    3. Hybrid forms + visual condition builder
    4. Auto-refresh strategies on every candle close
    5. Signals overlay directly on chart
    6. Basic risk management (fixed size, SL/TP), advanced v2
    7. Strategies independent from ML forecasts

### Internal References

- **Existing strategy system:** `supabase/migrations/20260221100000_strategy_builder_v2.sql` — Current DB schema
- **Backtesting engine:** `ml/src/evaluation/walk_forward_cv.py` — Walk-forward validation logic
- **Chart endpoint:** `supabase/functions/chart/index.ts` — Data visualization integration
- **Indicator library:** `ml/src/features/` — Technical indicator implementations
- **Strategy REST API:** `supabase/functions/strategy-*/index.ts` — CRUD endpoints

### External References

- **TradingView Lightweight Charts:** [https://tradingview.github.io/lightweight-charts/](https://tradingview.github.io/lightweight-charts/) — Chart library docs
- **Alpaca API:** [https://alpaca.markets/docs/](https://alpaca.markets/docs/) — Real-time data
- **Walk-forward validation:** [https://en.wikipedia.org/wiki/Walk_forward_optimization](https://en.wikipedia.org/wiki/Walk_forward_optimization)
- **Sharpe ratio & performance metrics:** [https://en.wikipedia.org/wiki/Sharpe_ratio](https://en.wikipedia.org/wiki/Sharpe_ratio)

### Related Work & Research Documents

**Comprehensive Research Reports** (created during `/deepen-plan` phase):

#### Trading UI & Best Practices
- **Best-Practices-Researcher Report** — 8K words on condition builder patterns, paper trading realism, indicator menu design
  - Rule builder pattern from TradingView/Interactive Brokers (one rule per line, not nested parentheses)
  - Realism requirements: bid/ask spreads, partial fills, realistic latency delays
  - Dashboard inverted pyramid: metrics > positions > details
  - Indicator correlation warnings + popularity indicators

#### TypeScript & Architecture
- **Framework-Docs-Researcher Report** — React Hook Form patterns, Supabase Edge Functions, TradingView Charts integration
  - FormProvider + useFormContext for multi-condition builder
  - Connection pooling for cold start optimization
  - Real-time subscription patterns with fallback to polling
  - Chart performance: <200ms render with 500 bars + real-time

- **Kieran-TypeScript-Reviewer Report** — Type safety, error handling, performance optimization
  - Discriminated unions for error handling (Result<T, E> pattern)
  - Type-safe condition operators (cross_up requires crossWith field)
  - Optimistic locking for race condition prevention
  - Batch data fetches + indicator caching (3-5x speedup)
  - Concurrency limiting with semaphore pattern

#### Security & Data Integrity
- **Security-Sentinel Report** — 12 findings (3 CRITICAL blocking v1, 5 HIGH, 4 MEDIUM)
  - RLS policies missing on all paper_trading_* tables
  - Slippage bounds: 0.01%-5% (prevent 500%+ inflation)
  - Position size constraints: price > 0, 1-1000 shares, SL < entry < TP
  - Market data validation: reject nulls, negative OHLC, gaps >10%
  - **Documents:** SECURITY_AUDIT_EXECUTIVE_SUMMARY.md, SECURITY_FIXES_IMPLEMENTATION.md (copy-paste ready code)

- **Data-Integrity-Guardian Report** — 11 findings including 4 race conditions
  - Race condition on position closure: use `WHERE status = 'open'` optimistic lock
  - No immutability on trades: add RLS for append-only audit trail
  - Partial failure handling: add NOT NULL constraints, atomic transactions
  - Cascade delete safety: use `ON DELETE RESTRICT`
  - **Documents:** PAPER_TRADING_SAFE_MIGRATION.sql (production-ready migration)

#### Performance & Optimization
- **Performance-Oracle Report** — 6 critical bottlenecks + optimization strategies
  - Indicator calculation: O(n*m) complexity, optimize with selective calc + caching
  - Missing indices: 5-10x query speedup with indices on (user_id, strategy_id, symbol_id, status)
  - Chart rendering: virtualize trades (paginate, render visible window only)
  - Parallel strategy evaluation: 5 concurrent strategies instead of sequential (5x faster)
  - **Performance targets:** Per-strategy <500ms, 5 strategies <2.5s, chart <200ms with 1000 trades
  - **Documents:** PERFORMANCE_ANALYSIS_STRATEGY_PLATFORM.md with optimization roadmap

#### Architecture Consistency
- **Pattern-Recognition-Specialist Report** — Design patterns, anti-patterns, naming consistency
  - Condition evaluator location: unify in TypeScript Edge Function (not dual Python/TypeScript)
  - Discriminated unions: operator field type-safe (cross_up/cross_down require crossWith)
  - Position state enum: extend to include pending_entry, partial_fill, forced_close_gap
  - Circuit breaker pattern: halt strategy after 3 consecutive losses
  - **Key issues:** Naming inconsistency (logicalOp vs logical_operator), table prefix mixing

### Previous Strategy PRs

- Review existing strategy builder commits to understand patterns
- Backtest evaluation PRs: Understand how evaluation metrics are calculated
- Chart integration PRs: See how indicators are overlaid

---

**Plan prepared:** 2026-02-25
**Status:** Ready for development
**Next step:** Review, refine, or begin implementation via `/workflows:work`
