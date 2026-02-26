# Architecture & Design Pattern Analysis: Strategy Platform Visual Builder Plan

**Date:** 2026-02-25
**Scope:** Strategy Platform with Visual Builder, Backtesting & Paper Trading
**Codebase:** SwiftBolt ML (7,745 Python files, 1,323 TypeScript/React files, 7+ React components)

---

## Executive Summary

The proposed strategy platform plan demonstrates **solid architectural intent** with clear separation of concerns (backtest, paper trading, condition evaluation). However, the plan contains several **architectural inconsistencies, potential duplication patterns, and missing abstractions** that could emerge during implementation. This analysis identifies 6 critical patterns, 4 anti-patterns, 3 naming convention gaps, and 2 missing pattern opportunities.

**Overall Assessment:** **MEDIUM RISK** — Plan requires refinement in execution patterns and shared abstractions before implementation.

---

## 1. CONDITION BUILDER PATTERN ANALYSIS

### Design Approach (from plan)

The plan proposes a **hybrid UI pattern:**
- **Left panel:** Forms-based condition input (indicator, operator, value)
- **Right panel:** Visual tree diagram showing AND/OR logic
- **State:** Nested condition tree with `parent_condition_id` and `condition_group_id`

### Pattern Quality Assessment

#### Strengths
1. **Recursive tree model** — Schema supports arbitrary nesting depth (good for complex logic)
2. **Visual + forms balance** — Not over-engineered (avoids React Flow complexity)
3. **Database normalization** — Conditions normalized in `strategy_user_conditions` table

#### Architectural Issues Found

**Issue #1: Missing Condition Type Abstraction**

The plan defines conditions as:
```typescript
type Condition = {
  id: string;
  indicator: string;      // "RSI", "MACD"
  operator: string;       // ">", "<", "cross_up"
  value: number | string;
  crossWith?: string;     // Only for cross operations
  logicalOp: "AND" | "OR";
  parentId?: string;
};
```

**Problem:** No discriminated union for operator-specific fields. A `cross_up` condition requires `crossWith`, but this isn't type-safe. A `>` operator shouldn't accept `crossWith`.

**Recommendation:**
```typescript
// Use discriminated union to enforce type safety
type ComparisonCondition = {
  type: "comparison";
  indicator: string;
  operator: ">" | "<" | ">=" | "<=" | "==";
  value: number;
};

type CrossCondition = {
  type: "cross";
  indicator: string;
  operator: "cross_up" | "cross_down";
  crossWith: string;
};

type RangeCondition = {
  type: "range";
  indicator: string;
  operator: "within_range";
  min: number;
  max: number;
};

type Condition = ComparisonCondition | CrossCondition | RangeCondition;
```

**Issue #2: Validation Logic Scattered Across Layers**

The plan mentions validation ("max 5 conditions per signal type, no orphaned conditions, circular dependency detection") but **does not specify where this lives:**
- UI validation? (React component)
- Database constraint? (SQL CHECK)
- Service layer? (Edge Function)

**Current pattern in codebase:** Looking at `StrategyUI.tsx`, validation happens in-component (state checks on parameter changes). **This duplicates validation logic** and makes testing difficult.

**Recommendation:**
Create a shared validation service (`supabase/functions/_shared/services/condition-validator.ts`):
```typescript
export function validateConditionTree(conditions: Condition[]): ValidationResult {
  // 1. Check max depth (5 levels)
  // 2. Check no orphaned parentIds
  // 3. Check no circular references (BFS)
  // 4. Check operator-field consistency
  // Return { valid: boolean, errors: string[] }
}
```

**Issue #3: Condition Evaluator Code Path Not Unified**

The plan mentions:
> "Both use same evaluator for consistency" (Backtest + Paper Trading)

But specifies the evaluator location as **either** `ml/src/evaluation/condition_evaluator.py` **or** `supabase/functions/_shared/condition_evaluator.ts`.

**Problem:** This is a **critical decision left unresolved.** If backtest runs in Python and paper trading runs in TypeScript (Edge Function), **you need TWO implementations** of the evaluator logic. This violates DRY principle and creates **synchronization risk** — conditions evaluate differently in backtest vs paper trading.

**Current backtest architecture:** Looking at `backtest-strategy/index.ts`, it queues a job that's processed asynchronously. The actual evaluation logic isn't in the plan.

**Recommendation:**
1. **Option A (Preferred):** Implement condition evaluator in **TypeScript only** in `supabase/functions/_shared/condition_evaluator.ts`. Call it from both backtest Edge Function AND paper trading executor.
   - **Pro:** Single source of truth, portable
   - **Con:** Requires Python backtest engine to call Edge Function for evaluation

2. **Option B:** Implement in **Python** (`ml/src/evaluation/condition_evaluator.py`), expose via REST endpoint, call from both backtest and paper trading.
   - **Pro:** Backtest stays in Python (familiar), evaluator centralized
   - **Con:** Adds network latency to paper trading (sub-optimal for real-time)

**Recommendation:** Choose **Option A** (TypeScript) because:
- Edge Functions are already called from both systems
- No additional network round trips
- JSON serialization is standard for both

---

## 2. REAL-TIME EXECUTION PATTERN ANALYSIS

### Design Approach (from plan)

**Paper Trading Execution Loop:**
1. Fetch active strategies
2. Get latest 100 bars
3. For each strategy:
   - Evaluate entry/exit conditions
   - Check existing positions
   - Execute entry/exit logic
   - Log execution

**Trigger:** Manual button (v1) or scheduled Edge Function (v2)

### Pattern Quality Assessment

#### Strengths
1. **Clear state machine** — Entry → Check SL/TP → Exit (well-defined)
2. **Atomic operations** — Transactions on position creation/closing
3. **Logging** — Execution log table for debugging

#### Architectural Issues Found

**Issue #4: Concurrent Strategy Execution (Race Condition Risk)**

The plan states:
> "Handle concurrent strategies" but provides no details.

**Current pseudocode:**
```typescript
for (const strategy of strategies) {
  const entrySignal = evaluateConditions(strategy.buy_conditions, bars);
  if (entrySignal && !openPosition) {
    await createPaperPosition(strategy, symbol, entryPrice, quantity);
  }
}
```

**Problem:** Multiple strategies on the **same symbol/timeframe** can race:
1. Strategy A reads "no open position" → True
2. Strategy B reads "no open position" → True
3. Both try to enter → Two positions created (expected: one)

**Also:** If paper trading runs on schedule (every 1m), and a new candle arrives during execution, **time inconsistency** occurs — conditions evaluated on stale data.

**Recommendation:**
Implement **distributed lock** pattern:
```typescript
async function executePaperTradingCycle(symbol: string, timeframe: string) {
  const lockKey = `paper-trading-lock:${symbol}:${timeframe}`;
  const acquired = await acquireLock(lockKey, 60000); // 60s timeout

  if (!acquired) {
    console.log("Skipping cycle (lock held by another process)");
    return;
  }

  try {
    // Execute strategy logic
  } finally {
    await releaseLock(lockKey);
  }
}
```

Uses Redis or Postgres advisory locks (preferable: Postgres native `pg_advisory_lock`).

**Issue #5: Missing State Consistency Guarantees**

The plan describes a **3-step execution process** but doesn't address **partial failure scenarios:**

1. ✅ Entry signal fires → Create position (INSERT)
2. ✅ Position created in DB
3. ❌ Log execution fails (network error)

**Result:** Position exists but **no record in `strategy_execution_log`** — incomplete audit trail.

**Recommendation:**
Use **database-centric saga pattern** (no distributed transactions):
1. Insert position + execution log in **single transaction** (preferred)
2. If transaction fails, entire operation rolls back
3. On retry, check if position already exists (idempotent)

```typescript
async function createPaperPosition(strategy: Strategy, symbol: string, entryPrice: number) {
  const { data, error } = await supabase
    .from("paper_trading_positions")
    .insert([{ /* position data */ }])
    .select();

  if (error) throw error;

  // Log in same transaction
  const { error: logError } = await supabase
    .from("strategy_execution_log")
    .insert([{
      strategy_id: strategy.id,
      signal_type: "entry",
      action_taken: `Entry order placed at $${entryPrice}`
    }]);

  if (logError) {
    // Delete position (rollback simulation)
    await supabase.from("paper_trading_positions").delete().match({ id: data[0].id });
    throw logError;
  }
}
```

**Issue #6: Slippage Model Too Simplistic**

Current model:
```typescript
const entryPrice = bars[bars.length - 1].close * 1.02; // 2% fixed slippage
```

**Problems:**
1. **Asymmetric** — Always applies 2% slippage regardless of direction
2. **Fixed** — Doesn't account for volume, volatility, or market conditions
3. **Unrealistic** — 2% is extreme for liquid equities (typical: 0.05-0.2%)

**Real-world impact:** Strategies may be profitable on backtest (lower slippage assumption) but unprofitable in paper trading (actual slippage).

**Recommendation:**
```typescript
function calculateSlippage(
  direction: "long" | "short",
  symbol: string,
  quantity: number,
  volatility: number // ATR/close ratio
): number {
  // Base slippage: 0.1% for liquid symbols, 0.3% for illiquid
  const baseSlippage = isLiquidSymbol(symbol) ? 0.001 : 0.003;

  // Volume impact: larger orders slip more
  const volumeImpact = quantity > 10000 ? 0.0015 : 0;

  // Volatility impact: high volatility = higher slippage
  const volImpact = volatility > 0.02 ? 0.005 : 0;

  const totalSlippage = baseSlippage + volumeImpact + volImpact;
  return direction === "long" ? totalSlippage : -totalSlippage;
}
```

---

## 3. DATA FLOW CONSISTENCY ANALYSIS

### Three Execution Paths

The plan defines three execution paths:
1. **Backtest Engine** (Python, historical data)
2. **Paper Trading** (TypeScript, live data)
3. **Strategy Execution** (future: live trading)

### Consistency Checkpoints

#### Checkpoint 1: Bar Data Source

| Path | Source | Format | Validation |
|------|--------|--------|-----------|
| Backtest | `ohlc_bars_v2` table | OHLCV dict | ✅ Addressed in `ml/src/data/supabase_db.py` |
| Paper Trading | Last 100 bars via `fetchLatestBars()` | Same as backtest? | ⚠️ **NOT SPECIFIED** |
| Chart | GET /chart endpoint | TradingView format | ✅ Exists |

**Issue #7: Bar Normalization Inconsistency**

Plan mentions:
> "Intraday (15m/1h) vs daily (1D) bars have different timestamp formats... Use existing `normalize_timestamp()` utility"

**Problem:** Only mentioned for risk mitigation, **not integrated into the technical approach.** Paper trading executor must call `normalize_timestamp()` but this isn't in the pseudocode.

**Current pattern in codebase:** `CLAUDE.md` mentions `ml/src/features/lookahead_checks.py` for temporal discipline, but paper trading doesn't reference it.

**Recommendation:**
Add explicit bar normalization step:
```typescript
const bars = await fetchLatestBars(symbol, timeframe, 100);
const normalizedBars = bars.map(bar => ({
  ...bar,
  ts: normalizeTimestamp(bar.ts, timeframe)
}));
const conditions = evaluateConditions(strategy.buy_conditions, normalizedBars);
```

#### Checkpoint 2: Indicator Calculation Consistency

**Issue #8: Indicator Library Coupling**

Backtest uses Python indicators (likely TA-Lib or pandas_ta).
Paper Trading uses... **not specified.**

The plan assumes the evaluator can "calculate indicator values" but doesn't specify the library or API.

**Current codebase:** `ml/src/features/` contains technical indicators. Are these exposed via REST?

**Recommendation:**
Create a **shared indicator abstraction**:

**Option A:** Duplicate indicator library in TypeScript (jsc.ts, tulind)
- Pro: No network calls
- Con: Maintenance burden, different implementations

**Option B:** Expose indicator service via REST (new Edge Function)
```typescript
// supabase/functions/indicator-calculator/index.ts
async function calculateIndicators(symbol: string, timeframe: string, bars: Bar[]) {
  // Call Python ML backend or compute in TypeScript
  return {
    rsi: [...],
    macd: [...],
    // ...
  };
}
```

---

## 4. COMPONENT COMPOSITION ANALYSIS

### Proposed Components

The plan mentions three main components:
1. **StrategyConditionBuilder.tsx**
2. **IndicatorMenu.tsx**
3. **PaperTradingDashboard.tsx**

### Component Architecture Review

#### Current State (StrategyUI.tsx)

```
StrategyUI (monolithic)
├── Strategy list (sidebar)
├── Strategy details (center)
│   ├── Parameter editor
│   ├── Indicator selector
│   └── Backtest results
└── New strategy form
```

**Problems:**
1. **Single 450-line component** — Hard to test, reuse, maintain
2. **No composition** — Parameter editor is inline render function
3. **Mixed concerns** — State management, rendering, API calls all mixed

#### Proposed Decomposition

**Strength:** Plan correctly identifies need for separation.

**Issue #9: Missing ConditionTree Component**

The plan proposes "visual tree diagram showing AND/OR logic" but **doesn't define a reusable component.**

**Implication:** Code will likely be written inline in StrategyConditionBuilder, causing tight coupling.

**Recommendation:**
Create atomic components:

```
StrategyConditionBuilder
├── ConditionForm (single condition input)
│   ├── IndicatorSelect
│   ├── OperatorSelect
│   └── ValueInput
├── ConditionTree (visual hierarchy)
│   ├── ConditionNode (recursive)
│   └── LogicalOperatorToggle
└── ConditionValidator (status badges)
```

#### Issue #10: No Shared State Management Layer

Current pattern: React `useState` for all state (see StrategyUI.tsx lines 70-81).

**Problem for complex forms:**
- Condition tree state is nested
- Changes to parent affect children
- No undo/redo
- Hard to persist mid-edit

**Recommendation:**
Use **form library** (React Hook Form) or **state machine** (XState):

```typescript
import { useForm } from "react-hook-form";

const { control, watch, formState: { errors } } = useForm<ConditionBuilderFormData>({
  defaultValues: strategy.conditions,
  resolver: yupResolver(conditionSchema)
});

// Automatic validation, change tracking, nested forms
```

---

## 5. STATE MANAGEMENT ANALYSIS

### Three Distinct State Domains

#### Domain 1: Strategy State (Read/Write)
- Current strategy (selected)
- Unsaved changes
- Validation errors
- **Location:** React component state? Database?
- **Consistency:** No clear pattern

#### Domain 2: Paper Trading Execution State
- Open positions (real-time)
- Recent trades
- Performance metrics
- **Location:** Postgres tables
- **Consistency:** Reactive (Supabase subscriptions)

#### Domain 3: Backtest Results State
- Job status (queued/running/done)
- Results when available
- **Location:** Database + memory (cache?)
- **Consistency:** Polling via GET request

### State Lifecycle Management

**Issue #11: Position State Ambiguity**

A position can be in states: `open`, `closing`, `closed`. But schema only defines:
```sql
status TEXT NOT NULL DEFAULT 'open'  -- Later becomes 'closed'
```

**Missing states:**
- `pending_entry` — Order placed, awaiting fill
- `pending_exit` — Exit signal fired, awaiting fill
- `closed_sl` — Closed via stop loss
- `closed_tp` — Closed via take profit
- `closed_signal` — Closed via exit signal

**Impact:** Dashboard can't distinguish why a position closed, making analysis difficult.

**Recommendation:**
Expand status enum:
```sql
CREATE TYPE paper_trade_status AS ENUM (
  'pending_entry',    -- Entry signal fired, awaiting open price
  'open',             -- Position open at entry price
  'pending_exit',     -- Exit signal fired, awaiting exit price
  'closed_tp',        -- Closed at take profit
  'closed_sl',        -- Closed at stop loss
  'closed_exit',      -- Closed at exit signal
  'closed_manual'     -- Closed manually by user
);
```

---

## 6. ERROR HANDLING PATTERNS

### Current Error Handling (Plan)

The plan mentions:
> "Wrap execution in try-catch, store errors in execution_log table, dashboard shows 'Strategy halted - check logs'"

**Issues:**

**Issue #12: Silent Degradation**

```typescript
try {
  // execution logic
} catch (err) {
  console.error("Condition evaluation failed:", err);
  // Continue to next strategy
}
```

**Problem:** Strategy silently fails. Position not created. Log entry added. **But dashboard doesn't highlight the error.**

**Recommendation:**
```typescript
interface ExecutionError {
  severity: "critical" | "warning" | "info";
  code: string;
  message: string;
  timestamp: Date;
  strategyId: string;
  suggestedAction: string;
}

async function executeStrategyWithErrorHandling(strategy: Strategy) {
  const errors: ExecutionError[] = [];

  try {
    await executeStrategy(strategy);
  } catch (err) {
    errors.push({
      severity: err.code === "CONDITION_EVAL_FAILED" ? "warning" : "critical",
      code: err.code,
      message: err.message,
      timestamp: new Date(),
      strategyId: strategy.id,
      suggestedAction: "Check indicator data; review condition logic"
    });

    // Store in DB for dashboard alerting
    await supabase.from("strategy_errors").insert(errors);
  }

  return { success: errors.length === 0, errors };
}
```

---

## 7. ANTI-PATTERN ANALYSIS

### Anti-Pattern #1: YAGNI Violation in State Management

**Finding:** The plan includes **two separate evaluator phases:**
1. Condition evaluator (universal)
2. Multi-condition AND/OR evaluator (Phase 4)

**Question:** Why are these separate? The condition evaluator should **inherently support AND/OR.**

**Implication:** Suggests the initial design (Phase 1-3) doesn't account for nested logic, then Phase 4 retrofits it.

**Recommendation:** Merge Phases 1 and 4. Design condition builder + evaluator together from the start.

### Anti-Pattern #2: Duplication of Evaluation Logic

**Finding:** The plan mentions backtest engine and paper trading executor both evaluate conditions.

**Current state:** Backtest logic exists (`backtest-strategy/index.ts`), but actual condition evaluation code isn't specified in plan.

**Risk:** Two implementations will diverge. Example:

**Backtest (hypothetical Python):**
```python
def evaluate_rsi(bars, period=14):
  # Uses pandas rolling window
  return ta.RSI(bars['close'], period)[-1]  # Get last value
```

**Paper Trading (TypeScript):**
```typescript
function evaluateRsi(bars: Bar[], period: number = 14): number {
  // Uses different algorithm
  return calculateRSI(bars.map(b => b.close), period);
}
```

**Result:** Same strategy, different RSI values, different execution.

**Recommendation:** Implement evaluator **once** in TypeScript, called from both paths.

### Anti-Pattern #3: Over-Engineering Dashboard

**Finding:** Plan includes multiple dashboard widgets:
- Live positions table
- Trade history table
- Metrics panel (5+ metrics)
- Comparison widget (backtest vs paper)
- Chart integration (entry/exit markers)

**Problem:** This is **5 separate components** tackling **2 concerns:**
1. Position/trade tracking
2. Performance analysis

**YAGNI concern:** Start with positions + trades (MVP). Comparison and metrics can be v2.

**Recommendation:** MVP dashboard should show:
- Live positions (symbol, entry, current price, P&L)
- Trade history (recent 10-20 closed trades)

Defer:
- Detailed metrics
- Backtest comparison widget
- Chart overlays

### Anti-Pattern #4: Missing Operational Constraints

**Finding:** Plan specifies "max 5 conditions per signal type" as validation rule.

**Issue:** No rationale provided. Is this:
- Performance constraint? (Evaluation takes O(n) time)
- Usability constraint? (Complex strategies are hard to understand)
- Hardware constraint? (Memory limit)

**Without rationale**, the constraint may be arbitrary or insufficient.

**Recommendation:** Document:
```
Max 5 conditions per signal = consensus UX guideline
- Beyond 5, strategy becomes hard to reason about
- Prevents over-optimization
- Keeps evaluation time < 100ms per condition set
```

---

## 8. NAMING CONSISTENCY ANALYSIS

### Current Naming Patterns

**React Components:**
- `StrategyUI.tsx` (descriptor + suffix)
- `IndicatorPanel.tsx` (descriptor + suffix)
- `PaperTradingDashboard.tsx` (descriptor + suffix)
- `StrategyBacktestPanel.tsx` (descriptor + suffix)

**Consistency:** ✅ Consistent (PascalCase, descriptive)

**Database Tables:**
- `strategy_user_strategies` (snake_case, redundant "strategy")
- `paper_trading_positions` (snake_case, clear)
- `strategy_execution_log` (snake_case, clear)
- `paper_trading_metrics` (inconsistent: "metrics" vs "positions")

**Consistency:** ⚠️ Inconsistent

### Issue #13: Naming Inconsistency in Proposed Tables

**Finding:** Proposed table naming is mixed:
- `paper_trading_positions` ✅
- `paper_trading_trades` ✅
- `strategy_execution_log` (should be `paper_trading_execution_log`?)
- `paper_trading_metrics` ✅

**Problem:** `strategy_execution_log` doesn't include "paper_trading" prefix. Is it also used for backtest execution? Unclear.

**Recommendation:**
Option A (Preferred):
- `paper_trading_positions`
- `paper_trading_trades` → `paper_trading_closed_trades` (clarify)
- `paper_trading_execution_log`
- `paper_trading_metrics`

Or Option B (Generic):
- `strategy_execution_positions`
- `strategy_execution_trades`
- `strategy_execution_log`
- `strategy_execution_metrics`

Choose one and apply consistently.

### Issue #14: Parameter Naming Ambiguity

From database schema:
```sql
logical_operator TEXT DEFAULT 'AND' CHECK (logical_operator IN ('AND', 'OR'))
```

**Inconsistency:** Condition has `logicalOp` (camelCase, TypeScript) but table has `logical_operator` (snake_case, SQL).

**Also ambiguous:** Does `logical_operator` apply to **this condition** or to **this condition vs parent?**

From plan:
```typescript
type ConditionNode = {
  id: string;
  logicalOp: "AND" | "OR"; // Operator to parent node
};
```

**Clarification needed:** Rename to `operator_to_parent` or document clearly.

**Recommendation:**
```typescript
type ConditionNode = {
  id: string;
  indicatorName: string;        // Not "indicator" (too generic)
  operator: ComparisonOperator;
  value: number | string;
  logicalOperatorToParent: "AND" | "OR";  // Explicit
  parentId?: string;
};
```

---

## 9. CODE DUPLICATION DETECTION

### Potential Duplication Patterns

#### Pattern 1: Backtest Evaluator ↔ Paper Trading Evaluator

**Status:** Not implemented yet, but plan explicitly duplicates logic.

**Lines of code:** ~100-200 per evaluator (estimate)
**Risk:** High — any logic changes must happen in two places.

**Mitigation:** Implement once in TypeScript, reuse.

#### Pattern 2: Position Closing Logic

**Finding:** Positions can close via:
1. `take_profit_price` hit
2. `stop_loss_price` hit
3. `exit_signal` (condition evaluation)
4. Manual close (user action)

**Plan code (lines 296-305):**
```typescript
if (latestPrice <= openPosition.stop_loss_price) {
  await closeTrade(openPosition, latestPrice, 'SL_HIT');
} else if (latestPrice >= openPosition.take_profit_price) {
  await closeTrade(openPosition, latestPrice, 'TP_HIT');
} else if (exitSignal) {
  await closeTrade(openPosition, latestPrice, 'EXIT_SIGNAL');
}
```

**Problem:** This logic likely repeats in:
- Paper trading executor
- Live execution engine (future)
- Manual close handler (future)

**Recommendation:**
Create shared service:
```typescript
// supabase/functions/_shared/services/position-closing-service.ts
export async function evaluatePositionClose(
  position: PaperTradingPosition,
  currentPrice: number,
  exitSignalFired: boolean
): Promise<CloseAction | null> {
  if (currentPrice <= position.stop_loss_price) {
    return { reason: "SL_HIT", exitPrice: currentPrice };
  }
  if (currentPrice >= position.take_profit_price) {
    return { reason: "TP_HIT", exitPrice: currentPrice };
  }
  if (exitSignalFired) {
    return { reason: "EXIT_SIGNAL", exitPrice: currentPrice };
  }
  return null;
}
```

### Code Duplication Estimate

| Component | Estimated LOC | Duplication Risk |
|-----------|---------------|------------------|
| Condition evaluator | 100-150 | HIGH (if separate implementations) |
| Position close logic | 30-50 | HIGH (appears in 3+ places) |
| Error handling | 50-100 | MEDIUM (generic try-catch) |
| Bar normalization | 20-30 | MEDIUM (if duplicated in backtest) |
| Indicator calculation | 300+ | HIGH (indicator library) |

**Total duplication risk:** HIGH if indicator library isn't shared.

---

## 10. MISSING PATTERNS ANALYSIS

### Missing Pattern #1: Circuit Breaker

**Finding:** No mention of circuit breaker for strategy execution.

**Scenario:** A strategy enters 5 consecutive losing trades within 1 hour. Should it:
- Continue trading? (Risk: large drawdown)
- Pause automatically? (Risk: miss profitable trades)
- Alert user? (User might not respond)

**Recommendation:**
```typescript
interface CircuitBreakerRule {
  maxLossesInRow: number;       // Stop after 3 losses
  maxDrawdownPct: number;       // Stop at -10% drawdown
  cooldownMinutes: number;      // Wait 30 min before resuming
}

async function checkCircuitBreaker(
  strategy: Strategy,
  metrics: PerformanceMetrics
): Promise<boolean> {
  if (metrics.consecutiveLosses >= strategy.circuitBreaker.maxLossesInRow) {
    return false;  // Halt strategy
  }
  if (metrics.maxDrawdownPct <= -strategy.circuitBreaker.maxDrawdownPct) {
    return false;  // Halt strategy
  }
  return true;
}
```

### Missing Pattern #2: Strategy Versioning

**Finding:** No mention of versioning strategies when conditions change.

**Scenario:** User edits a strategy's conditions. Do:
- Old positions close? (Problem: incomplete backtest comparison)
- New positions open under new conditions? (Problem: creates two versions)
- No new trades until manual override? (Problem: blocks the user)

**Recommendation:**
Add strategy versioning:
```sql
ALTER TABLE strategy_user_strategies ADD COLUMN (
  version INT DEFAULT 1,
  parent_version_id UUID REFERENCES strategy_user_strategies(id),
  created_from_version_at TIMESTAMP
);
```

Allow user to:
1. "Snapshot" current strategy (creates v2)
2. Edit v2 conditions without affecting live v1 trades
3. Compare performance v1 vs v2

### Missing Pattern #3: Indicator Parameter Sensitivity

**Finding:** No discussion of how indicator parameters affect strategy.

**Scenario:** User builds strategy with "RSI > 70" (oversold threshold). Plan mentions "default parameters auto-populate" but:
- What if user changes period from 14 to 7?
- Does backtest re-run automatically?
- Is there a sensitivity analysis?

**Recommendation:**
Add parameter sensitivity feature (v2):
```typescript
interface ParameterSensitivity {
  parameter: string;        // "rsi_period"
  rangeMin: number;
  rangeMax: number;
  testedValues: number[];
  results: { value: number, winRate: number, sharpe: number }[];
}

// Generate sensitivity table: RSI period 7..21, test each, show results
```

---

## 11. ARCHITECTURAL CONSISTENCY CHECKLIST

| Consistency Area | Status | Severity | Comment |
|------------------|--------|----------|---------|
| Condition evaluation (backtest vs paper) | ⚠️ Unresolved | HIGH | Must choose single implementation path |
| Bar data normalization | ⚠️ Mentioned, not integrated | MEDIUM | Add to pseudocode |
| Indicator library | ⚠️ Unspecified | HIGH | Must define shared interface |
| Error handling | ⚠️ Basic try-catch | MEDIUM | Add error tracking to DB |
| State consistency | ⚠️ Scattered | MEDIUM | Define per-domain state patterns |
| Component composition | ✅ Planned | LOW | Plan accounts for decomposition |
| Database naming | ⚠️ Inconsistent | LOW | Standardize prefix (_paper_trading vs _strategy) |
| Type safety | ⚠️ Loose | MEDIUM | Use discriminated unions for operators |

---

## 12. SUMMARY OF FINDINGS

### Critical Issues (Must Fix Before Implementation)

1. **Condition Evaluator Location** — Decide Python vs TypeScript (impacts backtest + paper trading architecture)
2. **Concurrent Strategy Execution** — Add distributed lock to prevent race conditions
3. **Indicator Library** — Define shared interface or API for indicator calculation
4. **Type Safety** — Use discriminated unions for operator-specific condition types

### High-Priority Issues (Fix in Phase 1)

5. **Validation Logic** — Extract to shared service, not duplicated in UI
6. **Position State Enum** — Expand from `open`/`closed` to include pending and close reasons
7. **Error Tracking** — Add dedicated error table for visibility in dashboard
8. **Slippage Model** — Make realistic (volume/volatility-dependent, not fixed 2%)

### Medium-Priority Issues (Address in Phase 1-2)

9. **State Management** — Use form library or state machine for complex condition builder
10. **Component Decomposition** — Create atomic components (ConditionForm, ConditionTree, etc.)
11. **Naming Consistency** — Standardize table prefixes (all _paper_trading or all _strategy)
12. **Code Duplication** — Implement position closing logic once, reuse everywhere

### Low-Priority Issues (Nice-to-Have)

13. **Circuit Breaker** — Add rule-based strategy halting (v2 feature)
14. **Strategy Versioning** — Allow users to snapshot strategy versions (v2 feature)
15. **Parameter Sensitivity** — Analyze impact of indicator parameter changes (v2 feature)
16. **Dashboard MVP** — Start minimal (positions + trades), add metrics/comparison in v2

---

## 13. RECOMMENDATIONS FOR IMPLEMENTATION

### Immediate Actions (Before Phase 1 Kickoff)

1. **Create ADR (Architecture Decision Record):**
   - Decision: Where does condition evaluator live? (TypeScript / Python)
   - Rationale: Single source of truth, testability, performance
   - Consequences: Backtest may need to call Edge Function for evaluation

2. **Define Shared Abstractions:**
   - `ConditionEvaluator` interface (signature, inputs, outputs)
   - `IndicatorCalculator` interface (signature, parameters)
   - `PositionClosingService` (rules for SL/TP/signal)

3. **Expand Database Schema:**
   - Add position state enum (pending_entry, open, pending_exit, closed_*)
   - Add execution error table
   - Rename tables with consistent prefixes

4. **Type Safety Improvements:**
   - Replace `operator: string` with discriminated union
   - Replace `indicator: string` with strongly-typed enum
   - Add validation schema (Zod / Yup)

### Phase 1 Focus (Weeks 1-2)

- **Condition Builder UI** (Hybrid forms + visual tree)
  - Use atomic components (ConditionForm, ConditionTree, ConditionNode)
  - Integrate with form library for state management
  - Add real-time validation

- **Shared Condition Validator Service**
  - Validate tree structure (no orphaned nodes, circular refs, max depth)
  - Enforce operator-field consistency
  - Reuse in UI, Edge Functions, and Python jobs

### Phase 2 Focus (Weeks 2-4)

- **Condition Evaluator** (TypeScript, shared by backtest + paper trading)
  - Recursive tree evaluation with AND/OR operators
  - Support all operator types (comparison, cross, range, touches)
  - 100% unit test coverage

- **Paper Trading Executor**
  - Use distributed lock for concurrency safety
  - Atomic transactions for position creation + logging
  - Error tracking in dedicated DB table

### Phase 3 Focus (Weeks 1-3, Parallel)

- **Indicator Menu**
  - Organize 30-40 indicators into 5 categories
  - Add metadata (default parameters, bullish/bearish signals)
  - Integrate with condition builder

### Phase 4 Focus (Weeks 3-4)

- **Multi-Condition Logic & Validation**
  - Tree evaluation is already covered in Phase 2
  - Focus on UI validation badges and error messages
  - Test integration: backtest + paper trading use same evaluator

---

## 14. RISK ASSESSMENT

### High-Risk Items

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Condition evaluator out of sync (backtest vs paper) | HIGH | CRITICAL | Implement once, reuse everywhere |
| Race conditions on concurrent strategy execution | MEDIUM | HIGH | Add distributed locking |
| Indicator calculation variance | MEDIUM | HIGH | Shared interface, dedicated tests |
| Position state corruption (partial writes) | LOW | HIGH | Atomic DB transactions |

### Medium-Risk Items

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Component complexity (condition builder) | MEDIUM | MEDIUM | Use form library, decompose early |
| Slippage model unrealistic | MEDIUM | MEDIUM | Volume/volatility-dependent calculation |
| Error handling silent degradation | MEDIUM | MEDIUM | Add error tracking table, dashboard alerts |

---

## 15. SUCCESS CRITERIA

**The plan is **execution-ready** when:**

1. ✅ Condition evaluator implementation location decided (Python / TypeScript)
2. ✅ Shared abstractions documented (Condition, Evaluator, Indicator interfaces)
3. ✅ Database schema updated with position state enum + error table
4. ✅ Type safety improvements applied (discriminated unions, enums)
5. ✅ Concurrency story clarified (distributed locking strategy)
6. ✅ Error handling pattern documented
7. ✅ Code duplication risks mitigated (shared services identified)
8. ✅ Component decomposition plan created (atomic component list)

---

## 16. FILES REFERENCED

**Plan document:**
- `/Users/ericpeterson/SwiftBolt_ML/docs/plans/2026-02-25-feat-strategy-platform-visual-builder-plan.md`

**Existing codebase patterns:**
- `/Users/ericpeterson/SwiftBolt_ML/frontend/src/components/StrategyUI.tsx` (current strategy builder)
- `/Users/ericpeterson/SwiftBolt_ML/supabase/functions/backtest-strategy/index.ts` (backtest executor)
- `/Users/ericpeterson/SwiftBolt_ML/supabase/functions/_shared/services/alert-evaluator.ts` (evaluation pattern reference)
- `/Users/ericpeterson/SwiftBolt_ML/ml/src/evaluation/walk_forward_cv.py` (backtest validation logic)

**Configuration & documentation:**
- `/Users/ericpeterson/SwiftBolt_ML/CLAUDE.md` (project instructions)

---

## Conclusion

The strategy platform plan demonstrates **strong architectural vision** but requires **refinement in 5 key areas:**

1. **Unify condition evaluation** (single source of truth for backtest + paper trading)
2. **Clarify concurrency model** (distributed locking for race condition safety)
3. **Define shared abstractions** (condition validator, evaluator, indicator calculator)
4. **Strengthen type safety** (discriminated unions for operators)
5. **Expand error handling** (dedicated error tracking, dashboard visibility)

**Estimated effort to address:**
- Critical issues: 2-3 days (architecture decisions + ADRs)
- High-priority issues: 3-5 days (schema updates, shared services)
- Implementation risk: **REDUCED from HIGH → MEDIUM** after addressing these items

**Overall recommendation:** Proceed with Phase 1-2 implementation after addressing critical and high-priority issues. Issues #13-16 can be deferred to Phase 2 (v2) without blocking MVP.

---

**Report prepared:** 2026-02-25
**Reviewer:** Pattern Recognition Specialist
**Status:** Ready for development team review
