# Strategy System Technical Guide

**Reference Document:** Code paths and integration points for the SwiftBolt ML strategy system

---

## 1. DATABASE SCHEMA & STORAGE

### Location: `/Users/ericpeterson/SwiftBolt_ML/supabase/migrations/`

#### Key Migration Files

**`20260221100000_strategy_builder_v2.sql`**
- Main strategy tables: `strategy_user_strategies`, `strategy_backtest_jobs`, `strategy_backtest_results`
- RLS policies for multi-tenant isolation
- Job queue function: `claim_pending_backtest_job()`

**`20260221110000_fix_strategy_fk.sql`** & **`20260221120000_fix_backtest_fk.sql`**
- Foreign key fixes between jobs and results

**`20260222100000_strategy_rls_anon_insert.sql`** & **`20260222150000_allow_anon_strategies.sql`**
- Allow anonymous users to create strategies (demo mode)

### Table Schemas

```sql
-- Strategy definitions
CREATE TABLE strategy_user_strategies (
  id UUID PRIMARY KEY,
  user_id UUID,           -- RLS: auth.uid()
  name TEXT NOT NULL,
  description TEXT,
  config JSONB,           -- {entry_conditions: [...], exit_conditions: [...], filters: [...], parameters: {...}}
  is_active BOOLEAN,
  created_at, updated_at TIMESTAMPTZ
);

-- Backtest jobs queue
CREATE TABLE strategy_backtest_jobs (
  id UUID PRIMARY KEY,
  user_id UUID,
  strategy_id UUID,
  symbol TEXT,
  start_date, end_date DATE,
  parameters JSONB,
  status TEXT CHECK (...IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
  error_message TEXT,
  result_id UUID,
  started_at, completed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ
);

-- Backtest results storage
CREATE TABLE strategy_backtest_results (
  id UUID PRIMARY KEY,
  job_id UUID,
  metrics JSONB,      -- {sharpe_ratio, total_return, win_rate, max_drawdown, ...}
  trades JSONB,       -- [{entry_date, exit_date, pnl, return, ...}, ...]
  equity_curve JSONB, -- [{time, value}, ...]
  created_at TIMESTAMPTZ
);
```

---

## 2. BACKEND API (Supabase Edge Functions)

### Location: `/Users/ericpeterson/SwiftBolt_ML/backend/supabase/functions/strategies/`

**File:** `/strategies/index.ts`

#### Endpoints

| Method | Path | Handler | Purpose |
|--------|------|---------|---------|
| GET | `/strategies` | `handleGet()` | List all user strategies |
| GET | `/strategies?id=xxx` | `handleGet(id)` | Get single strategy |
| POST | `/strategies` | `handleCreate()` | Create new strategy |
| POST | `/strategies?action=duplicate` | `handleDuplicate()` | Clone existing strategy |
| PUT | `/strategies?id=xxx` | `handleUpdate()` | Update strategy config |
| DELETE | `/strategies?id=xxx` | `handleDelete()` | Delete strategy |

#### Request/Response Examples

**POST /strategies (Create)**
```json
{
  "name": "SuperTrend Strategy",
  "description": "Trend-following with SuperTrend indicator",
  "config": {
    "entry_conditions": [
      {
        "type": "indicator",
        "name": "supertrend",
        "operator": "crosses_above",
        "params": {"length": 10, "multiplier": 3.0}
      }
    ],
    "exit_conditions": [
      {
        "type": "stop_loss",
        "value": -0.02
      }
    ],
    "filters": [
      {
        "type": "regime",
        "name": "trending"
      }
    ],
    "parameters": {
      "length": 10,
      "multiplier": 3.0
    }
  },
  "is_active": true
}
```

**Response (201 Created)**
```json
{
  "strategy": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": "auth-user-id",
    "name": "SuperTrend Strategy",
    "description": "...",
    "config": {...},
    "is_active": true,
    "created_at": "2026-02-25T...",
    "updated_at": "2026-02-25T..."
  }
}
```

#### Authentication

- Uses JWT Bearer token from `Authorization` header
- Extracts `user_id` from JWT payload: `token.split('.')[1]` → `JSON.parse(atob(...))` → `payload.sub`
- Demo mode: defaults to `"00000000-0000-0000-0000-000000000001"` if no auth

---

## 3. FRONTEND COMPONENTS (React)

### Location: `/Users/ericpeterson/SwiftBolt_ML/frontend/src/components/`

#### StrategyUI.tsx
**File:** `/frontend/src/components/StrategyUI.tsx`

**Main Features:**
- Strategy list sidebar (left)
- Strategy editor (center) with parameter form
- Indicator selector with enable/disable
- Signal filter dropdown (Buy/Sell/Both)
- Active/Inactive toggle
- New strategy creation form
- Backtest trigger button

**Data Structure:**
```typescript
interface Strategy {
  id: string;
  name: string;
  description: string;
  parameters: StrategyParameter[];    // {name, type, value, description}
  indicators: StrategyIndicator[];    // {name, description, enabled}
  signalFilter: 'buy' | 'sell' | 'both';
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}
```

**Mock Data Included:**
1. SuperTrend Strategy (trend-following)
   - Parameters: length (10), multiplier (3.0)
   - Indicators: SuperTrend (enabled), RSI (enabled), MACD (disabled)

2. RSI Oversold Strategy (mean-reversion)
   - Parameters: rsiLength (14), overboughtLevel (70), oversoldLevel (30)
   - Indicators: RSI (enabled), BBands (enabled)

**Key Functions:**
- `handleCreateStrategy()` - Add new strategy to list
- `handleUpdateStrategy()` - Save parameter/indicator changes
- `handleBacktest()` - Call backtest API (currently mocked)

#### StrategyBacktestPanel.tsx
**File:** `/frontend/src/components/StrategyBacktestPanel.tsx`

**Purpose:** Execute backtest and display results

**Size:** 70+ KB (partially implemented, comprehensive)

**Expected Features:**
- Date range selector (start/end date inputs)
- Backtest execution button
- Results display:
  - Equity curve chart
  - Trade list (entry/exit, P&L)
  - Metrics: Sharpe, Sortino, max drawdown, win rate
  - Real-time progress updates (placeholder)

#### Supporting Components

**IndicatorPanel.tsx**
- Toggle/configure individual indicators
- Used by StrategyUI for indicator selection

**TradingViewChart.tsx**
- Display chart with indicator overlays
- Lightweight Charts library integration
- Real-time data updates

**ChartWithIndicators.tsx**
- Composite component combining chart + indicators

---

## 4. PYTHON BACKTESTING FRAMEWORK

### Location: `/Users/ericpeterson/SwiftBolt_ML/ml/src/backtesting/`, `/ml/src/testing/`

#### Walk-Forward Tester
**File:** `/ml/src/backtesting/walk_forward_tester.py`

**Purpose:** Time-series backtesting with zero lookahead bias

**Key Classes:**

```python
@dataclass
class BacktestMetrics:
    # Classification metrics
    accuracy: float
    precision: float
    recall: float
    f1_score: float

    # Financial metrics
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float

    # Trade metrics
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_win_size: float
    avg_loss_size: float

    # Metadata
    start_date: datetime
    end_date: datetime
    test_periods: int
    test_periods_list: Optional[List[Dict[str, str]]]

class WalkForwardBacktester:
    HORIZON_WINDOWS = {
        "1D": {"train": 126, "test": 10, "step": 2},
        "1W": {"train": 252, "test": 25, "step": 5},
        "1M": {"train": 504, "test": 60, "step": 20},
        # ...
    }

    def backtest(df, forecaster, horizons) -> BacktestMetrics
    def _get_horizon_days(horizon: str) -> int
    def _return_to_label(ret: float) -> str  # 'bullish', 'neutral', 'bearish'
    def _compute_metrics(...) -> BacktestMetrics
```

**Usage:**
```python
from ml.src.backtesting.walk_forward_tester import WalkForwardBacktester

tester = WalkForwardBacktester(horizon="1D")
metrics = tester.backtest(df, forecaster_class, horizons=["1D"])

print(f"Accuracy: {metrics.accuracy:.2%}")
print(f"Sharpe: {metrics.sharpe_ratio:.2f}")
print(f"Max Drawdown: {metrics.max_drawdown:.2%}")
```

#### Backtest Framework (Production Grade)
**File:** `/ml/src/testing/backtest_framework.py`

**Features:**
- Transaction cost modeling (commission + slippage)
- Position sizing rules (max % per position)
- Realistic execution simulation
- Trade logging with P&L
- Walk-forward optimization

**Classes:**

```python
@dataclass
class BacktestConfig:
    initial_capital: float = 100_000.0
    commission_rate: float = 0.001       # 0.1%
    slippage_bps: float = 5.0            # 5 basis points
    max_position_pct: float = 0.10       # 10%
    risk_free_rate: float = 0.05
    trading_days_per_year: int = 252

@dataclass
class BacktestResult:
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int
    equity_curve: pd.Series
    trades: pd.DataFrame
    daily_returns: pd.Series

    def summary() -> str  # Formatted output

class BacktestFramework:
    def __init__(config: Optional[BacktestConfig] = None)
    def run_backtest(data, signal_generator, start_date, end_date) -> BacktestResult
    def walk_forward_backtest(data, model_trainer, n_splits, train_pct) -> List[BacktestResult]
    def aggregate_walk_forward_results(results) -> dict
    def _simulate_trading(data, signals) -> Tuple[pd.Series, pd.DataFrame]
    def _calculate_metrics(...) -> BacktestResult
```

**Usage:**
```python
from ml.src.testing.backtest_framework import BacktestFramework, BacktestConfig

config = BacktestConfig(
    initial_capital=10000,
    commission_rate=0.001,
    slippage_bps=5,
    max_position_pct=0.10
)
framework = BacktestFramework(config)

# Simple backtest
result = framework.run_backtest(df, signal_generator)
print(result.summary())

# Walk-forward
results = framework.walk_forward_backtest(df, model_trainer, n_splits=5)
agg = framework.aggregate_walk_forward_results(results)
print(f"Mean Sharpe: {agg['sharpe_mean']:.2f}")
```

#### Backtest Engine (Options Specialized)
**File:** `/ml/src/backtesting/backtest_engine.py`

**Purpose:** Options-specific backtesting with Black-Scholes integration

**Key Features:**
- Options contract pricing
- Greeks calculation
- Position tracking by contract
- Realistic commission ($0.65/contract default)

---

## 5. TECHNICAL INDICATORS

### TradingView-Validated Indicators
**File:** `/ml/src/features/technical_indicators_tradingview.py`

```python
class TradingViewIndicators:
    @staticmethod
    def calculate_atr_wilder(df, period=14) -> pd.Series
    @staticmethod
    def calculate_supertrend(df, period=7, multiplier=2.0) -> pd.DataFrame
    @staticmethod
    def calculate_kdj(df, n=9, m1=5, m2=5) -> pd.DataFrame
    @staticmethod
    def calculate_adx(df, period=14) -> pd.DataFrame
    @staticmethod
    def add_all_tradingview_indicators(df) -> pd.DataFrame

def validate_against_tradingview(df, tv_df, symbol) -> dict
```

**Output Columns Added to DataFrame:**
```
supertrend, supertrend_direction, supertrend_signal
kdj_k, kdj_d, kdj_j, kdj_j_divergence
adx, plus_di, minus_di, adx_normalized
atr_14, atr_normalized
```

### Adaptive SuperTrend
**File:** `/ml/src/strategies/supertrend_ai.py`

```python
class SuperTrendAI:
    def __init__(
        self,
        df: pd.DataFrame,
        atr_length=10,
        min_mult=1.0,
        max_mult=5.0,
        step=0.5,
        perf_alpha=10,
        from_cluster='Best'
    )

    def calculate() -> Tuple[pd.DataFrame, Dict[str, Any]]
    def predict(new_df, target_factor) -> pd.DataFrame

    def calculate_atr() -> pd.Series
    def calculate_supertrend(atr, factor) -> Tuple[pd.Series, pd.Series]
    def calculate_performance(supertrend, trend) -> float
    def run_kmeans_clustering(performances, factors) -> Tuple[float, Dict]
    def calculate_signal_confidence(perf_idx) -> pd.Series
    def extract_signal_metadata(perf_idx, risk_reward_ratio=2.0) -> List[Dict]
    def get_current_state() -> Dict[str, Any]
```

**Output Info Dict:**
```json
{
  "target_factor": 2.5,
  "cluster_mapping": {"0": "Worst", "1": "Average", "2": "Best"},
  "performance_index": 0.75,
  "signal_strength": 7,  // 0-10 score
  "factors_tested": [1.0, 1.5, 2.0, ...],
  "performances": [0.12, 0.45, 0.78, ...],
  "signals": [
    {
      "date": "2026-02-25T...",
      "type": "BUY",
      "price": 150.25,
      "confidence": 8,
      "stop_level": 148.50,
      "target_price": 154.00,
      "atr_at_signal": 1.75,
      "risk_amount": 1.75,
      "reward_amount": 3.50
    }
  ],
  "current_trend": "BULLISH",
  "current_stop_level": 149.50,
  "trend_duration_bars": 42
}
```

### Support/Resistance
**File:** `/ml/src/features/support_resistance_detector.py`

- Detects pivot levels
- Calculates support/resistance probability
- Polynomial/logistic SR indicators

**File:** `/ml/src/features/sr_probability.py`, `/sr_feature_builder.py`

---

## 6. API ROUTERS

### Backtest Router
**File:** `/ml/api/routers/backtest.py`

```python
@router.post("/backtest-strategy")
async def run_backtest_endpoint(request: BacktestRequest) -> BacktestResponse

@router.get("/strategy-backtest-results")
async def get_strategy_backtest_results(job_id: str) -> StrategyBacktestResultsResponse
```

**Request Model:**
```python
class BacktestRequest(BaseModel):
    symbol: str
    strategy: str           # 'supertrend_ai', 'sma_crossover', 'buy_and_hold'
    startDate: str         # YYYY-MM-DD
    endDate: str
    timeframe: Optional[str]  # 'd1', '1h', '15m' etc.
    initialCapital: Optional[float]  # default 10000
    params: Optional[Dict[str, Any]]  # strategy-specific
```

**Response Model:**
```python
class BacktestResponse(BaseModel):
    totalTrades: int
    winningTrades: int
    losingTrades: int
    totalProfit: float
    totalReturn: float
    maxDrawdown: float
    sharpeRatio: float
    performanceMetrics: Dict[str, float]
    trades: List[Dict]
    equityCurve: List[Dict]
```

---

## 7. INTEGRATION POINTS

### Where Indicators Feed Into System

1. **Feature Pipeline** → ML Models
   - Indicators computed in `ml/src/features/`
   - Fed to ensemble forecaster
   - Used in daily/intraday forecast jobs

2. **Chart Endpoint** → Frontend
   - `/chart` Edge Function computes indicators
   - Returns: OHLCV + indicators + forecasts + validation metrics
   - Consumed by React/SwiftUI clients

3. **Strategy Builder** → Backtest
   - User selects indicators as entry/exit conditions
   - Backtest engine evaluates conditions against historical data
   - Results stored in `strategy_backtest_results`

4. **Real-Time Updates** → WebSocket (Future)
   - Live indicator values pushed to clients
   - Placeholder in codebase: `/hooks/useWebSocket.ts`

---

## 8. CONFIGURATION & ENVIRONMENT

### Feature Flags
**File:** `/ml/config/settings.py` (pydantic-settings singleton)

```python
USE_UNIFIED_FORECAST = True
USE_SEPARATE_EVALUATIONS = True
STRICT_LOOKAHEAD_CHECK = 0|1  # Enable synthetic lookahead guards
ENABLE_ADAPTIVE_SUPERTREND = True
```

### Lookahead Bias Guards
**File:** `/ml/src/features/lookahead_checks.py`

- Validates feature engineering doesn't peek into future
- Run with `STRICT_LOOKAHEAD_CHECK=1` for safety checks
- Critical for walk-forward validation integrity

---

## 9. EXECUTION FLOW (End-to-End)

### User Creates Strategy & Runs Backtest

```
1. React Frontend (StrategyUI.tsx)
   └─ User fills strategy form
   └─ Sends POST /strategies → Edge Function

2. Supabase Edge Function (/strategies)
   └─ Validates config
   └─ Inserts into strategy_user_strategies
   └─ Returns strategy ID

3. User selects strategy + date range in StrategyBacktestPanel.tsx
   └─ Sends POST /backtest-strategy

4. Backend Router (/ml/api/routers/backtest.py)
   └─ Calls run_backtest() from ml/scripts/run_backtest.py

5. Python Backtest Engine
   └─ Fetches OHLCV data
   └─ Initializes WalkForwardBacktester
   └─ Iterates windows: train/test split
   └─ For each window:
      └─ Computes indicators (TradingView implementations)
      └─ Evaluates strategy conditions
      └─ Generates signals
      └─ Runs financial simulation
      └─ Calculates metrics
   └─ Aggregates results

6. Results Stored
   └─ Inserts into strategy_backtest_results (metrics, trades, equity_curve)
   └─ Updates strategy_backtest_jobs (status='completed')

7. Frontend Displays Results
   └─ Fetches from GET /strategy-backtest-results
   └─ Renders charts (equity curve, drawdown)
   └─ Displays table (trades with entry/exit)
   └─ Shows metrics (Sharpe, win rate, etc.)
```

---

## 10. CURRENT LIMITATIONS & GAPS

### Not Implemented

- **Real-time Signal Generation** - Only in backtest context
- **Live Order Execution** - No Alpaca order placement
- **Paper Trading** - No simulated real-time execution
- **Risk Management Enforcement** - Rules exist in framework, not enforced
- **Multi-strategy Portfolio** - Single strategy at a time
- **Strategy Performance Tracking** - No live P&L vs. backtest comparison
- **Condition Builder UI** - Strategies created via form, not visual builder
- **Alert System** - No email/SMS when conditions met

### Partially Implemented

- **Indicator Configuration** - Basic form, no advanced constraints
- **Strategy Templates** - Mock data only, no library
- **Backtest Queueing** - Schema exists, not actively used
- **Options Strategies** - Advanced models exist, not integrated into UI

---

## 11. CODE QUALITY & TESTING

### Test Locations
- `/ml/tests/` - unit & integration tests
- Backtesting validation against TradingView exports
- Walk-forward test periods tracked with actual date ranges

### Validation Examples
**TradingView Indicator Validation**
```python
# File: technical_indicators_tradingview.py
results = validate_against_tradingview(our_df, tv_export_df, 'AAPL')
# Returns: {
#   "supertrend_error": 13.5,  # Excellent match
#   "kdj_k_error": 0.08,       # Near-perfect
#   "adx_error": 5.69          # Good match
# }
```

---

## Summary Checklist

- [x] **Indicators:** TradingView-validated SuperTrend, KDJ, ADX + adaptive variants
- [x] **Strategy Definition:** Database schema, REST API, React UI
- [x] **Backtesting:** Walk-forward framework, transaction costs, metrics
- [x] **Data Flow:** Alpaca → Postgres → Forecasts → Charts
- [ ] **Live Trading:** Not implemented
- [ ] **Paper Trading:** Not implemented
- [ ] **Real-time Signals:** Not implemented (backtest only)
- [ ] **Condition Builder UI:** Visual drag-drop not yet built
