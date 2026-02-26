# SwiftBolt ML - Strategy Platform Research Summary

**Date**: 2026-02-25
**Research Focus**: Strategy System Implementation, Backtesting Framework, UI Components, and Chart Integration

---

## Executive Summary

SwiftBolt ML has a **multi-layered strategy platform** with:
- **Database-driven strategy storage** (Supabase Postgres)
- **REST/Edge Function API** for CRUD and backtesting
- **Walk-forward validation framework** (prevents lookahead bias)
- **Job-queue backtesting system** with async result delivery
- **Rich charting integration** (TradingView Lightweight Charts)
- **Multi-platform UIs** (React + TypeScript, SwiftUI)

The system supports both **preset strategies** (hardcoded: SuperTrend AI, SMA Crossover, Buy & Hold) and **user-defined builder strategies** (custom conditions/indicators).

---

## 1. Strategy System Implementation

### 1.1 Database Schema

**Core Tables** (Location: `/Users/ericpeterson/SwiftBolt_ML/supabase/migrations/20260221100000_strategy_builder_v2.sql`)

```
strategy_user_strategies
├── id (UUID, PK)
├── user_id (UUID, FK to auth.users, nullable for demo)
├── name (TEXT)
├── description (TEXT, optional)
├── config (JSONB)  ← All strategy parameters stored as JSON
├── is_active (BOOLEAN)
├── created_at (TIMESTAMPTZ)
└── updated_at (TIMESTAMPTZ)

strategy_backtest_jobs
├── id (UUID, PK)
├── user_id (UUID, FK nullable)
├── strategy_id (UUID)
├── symbol (TEXT, default 'AAPL')
├── start_date (DATE)
├── end_date (DATE)
├── parameters (JSONB)
├── status (TEXT)  ← pending|running|completed|failed|cancelled
├── error_message (TEXT)
├── result_id (UUID, FK to strategy_backtest_results)
├── started_at (TIMESTAMPTZ)
├── completed_at (TIMESTAMPTZ)
└── created_at (TIMESTAMPTZ)

strategy_backtest_results
├── id (UUID, PK)
├── job_id (UUID, FK nullable)
├── metrics (JSONB)  ← {totalReturn, sharpeRatio, maxDrawdown, winRate, ...}
├── trades (JSONB)  ← [{entryTime, exitTime, entryPrice, exitPrice, pnl, ...}]
├── equity_curve (JSONB)  ← [{time, value}, ...]
└── created_at (TIMESTAMPTZ)
```

**RLS Policies** (Location: `/Users/ericpeterson/SwiftBolt_ML/supabase/migrations/20260222100000_strategy_rls_anon_insert.sql`):
- Users see only their own strategies (`user_id = auth.uid()`)
- Anon users can create demo strategies (`user_id IS NULL`)
- Cascade delete on backtest jobs when strategy deleted

**Index Strategy**:
- Primary index: `idx_backtest_jobs_user_status` on `(user_id, status, created_at DESC)` for polling job queues

### 1.2 Strategy Definition Format

**config JSONB schema** stored in `strategy_user_strategies.config`:

```typescript
interface StrategyConfig {
  entryConditions: Condition[];
  exitConditions: Condition[];
  positionSizing: PositionSizing;
  riskManagement: RiskManagement;
}

interface Condition {
  type: ConditionType;  // 'rsi', 'macd', 'sma', 'bb', etc.
  operator: Operator;  // '>', '<', '>=', '<=', '==', 'cross_up', 'cross_down'
  value: number;  // threshold
  params?: Record<string, number>;  // indicator-specific params (period, multiplier, etc.)
}

interface PositionSizing {
  type: 'fixed' | 'percent_of_equity' | 'kelly';
  value: number;
}

interface RiskManagement {
  stopLoss: { type: 'percent' | 'fixed'; value: number };
  takeProfit: { type: 'percent' | 'fixed'; value: number };
}
```

**Supported Condition Types** (from `/Users/ericpeterson/SwiftBolt_ML/frontend/src/components/StrategyBacktestPanel.tsx`):
```
rsi, macd, macd_signal, macd_hist, stochastic, kdj_k, kdj_d, kdj_j, mfi, williams_r, cci,
returns_1d, returns_5d, returns_20d, sma, ema, sma_cross, ema_cross, adx, plus_di, minus_di,
price_above_sma, price_above_ema, price_vs_sma20, price_vs_sma50, bb, bb_upper, bb_lower, atr,
volatility_20d, supertrend_factor, supertrend_trend, supertrend_signal, close, high, low, open,
volume, volume_ratio, obv, price_breakout, volume_spike, ml_signal
```

### 1.3 REST API Endpoints

**Strategy Management** (Location: `/Users/ericpeterson/SwiftBolt_ML/supabase/functions/strategy/index.ts`):
```
GET  /strategy
     - Returns all strategies for authenticated user
     - Response: { strategies: Strategy[], count: number }

POST /strategy
     - Create new strategy
     - Body: { name, description, parameters, type }
     - Response: { strategy: Strategy }

PUT  /strategy
     - Update existing strategy
     - Body: { id, name, description, parameters, type }

DELETE /strategy/:id
     - Delete strategy by ID
```

**Backtesting** (Location: `/Users/ericpeterson/SwiftBolt_ML/supabase/functions/strategy-backtest/index.ts`):
```
POST /strategy-backtest
     Queue a new backtest job
     Body: {
       strategy_id: string (UUID),
       symbol: string,
       start_date: string (YYYY-MM-DD),
       end_date: string (YYYY-MM-DD),
       parameters?: object
     }
     Response: {
       id: string (job_id),
       status: 'pending' | 'running' | 'completed' | 'failed'
     }

GET  /strategy-backtest?id=<job_id>
     Get job status and results
     Response: {
       id: string,
       status: string,
       result: {
         totalReturn: number,
         sharpeRatio: number,
         maxDrawdown: number,
         trades: Trade[],
         equity_curve: Point[]
       }
     }

GET  /strategy-backtest?status=pending
     List jobs for current user filtered by status
```

**Helper Function**:
```sql
claim_pending_backtest_job()
  -- Called by background worker
  -- Returns UUID of next pending job
  -- Sets status='running', started_at=NOW()
  -- Uses SKIP LOCKED for concurrency
```

### 1.4 Preset vs. Builder Strategies

**Preset Strategies** (hardcoded):
1. `supertrend_ai` - Trend-following with SuperTrend indicator
2. `sma_crossover` - SMA 20/50 crossing strategy
3. `buy_and_hold` - Simple buy-and-hold baseline

- Implementation: Called via FastAPI from backtest worker
- Location: `/Users/ericpeterson/SwiftBolt_ML/supabase/functions/strategy-backtest-worker/index.ts` (lines 60-76)
- They bypass the builder config and use hardcoded logic

**Builder Strategies** (user-defined):
- Stored in `strategy_user_strategies.config`
- Evaluated locally in TypeScript backtest worker (no FastAPI call)
- Conditions checked on each bar
- Entry/exit logic based on condition combinations

---

## 2. Backtesting & Evaluation Framework

### 2.1 Walk-Forward Validation (Time-Series Safe)

**Critical Design**: Walk-forward CV prevents **lookahead bias** that standard K-fold creates.

Location: `/Users/ericpeterson/SwiftBolt_ML/ml/src/evaluation/walk_forward_cv.py`

```python
class WalkForwardCV:
    """
    Train set grows; test set slides forward (no shuffling).

    Example with 5 splits, test_size=28 days, gap=0:
      Split 1: Train [0:504]  → Test [504:532]
      Split 2: Train [0:532]  → Test [532:560]
      Split 3: Train [0:560]  → Test [560:588]
      ...
    """

    def split(self, X: pd.DataFrame) -> List[Tuple[np.ndarray, np.ndarray]]:
        # Returns (train_indices, test_indices) tuples in temporal order
```

**Validation Metrics** (Directional Accuracy):
```python
def directional_accuracy(y_true, y_pred) -> float:
    """
    More important than MSE for trading strategies.
    Measures if model correctly predicts UP vs DOWN.
    """
    direction_true = np.diff(y_true) > 0
    direction_pred = np.diff(y_pred) > 0
    return np.mean(direction_true == direction_pred)
```

### 2.2 ML Pipeline Evaluation Jobs

**Daily Evaluation** (Location: `/Users/ericpeterson/SwiftBolt_ML/ml/src/evaluation_job_daily.py`):
```python
class DailyForecastEvaluator:
    BULLISH_THRESHOLD = 0.02  # +2%
    BEARISH_THRESHOLD = -0.02  # -2%

    def classify_return(self, return_pct: float) -> str:
        """Classify actual return into trend label."""
        if return_pct > BULLISH_THRESHOLD:
            return "bullish"
        elif return_pct < BEARISH_THRESHOLD:
            return "bearish"
        else:
            return "neutral"
```

Evaluates **1D, 5D, 10D, 20D** horizons by:
1. Calling `get_pending_evaluations(horizon)` RPC
2. De-duplicating overlapping forecasts (same symbol/date)
3. Computing actual returns vs forecast direction
4. Writing to `forecast_evaluations` table

### 2.3 Backtest Execution Flow

**Architecture** (Location: `/Users/ericpeterson/SwiftBolt_ML/supabase/functions/strategy-backtest-worker/index.ts`):

```
┌─────────────────────────────────────────────┐
│  User queues backtest (POST /strategy-backtest)
│  → Creates row in strategy_backtest_jobs
└──────────────────┬──────────────────────────┘
                   ↓
         ┌─────────────────────┐
         │  Background Worker  │
         │  Polls for pending  │
         └────────┬────────────┘
                  ↓
    ┌─────────────────────────────┐
    │ claim_pending_backtest_job() │
    │ Sets status='running'        │
    └─────────────┬───────────────┘
                  ↓
        ┌──────────────────────┐
        │  Fetch market data   │
        │  (YFinance)          │
        └─────────┬────────────┘
                  ↓
    ┌──────────────────────────────┐
    │ Choose route:                │
    │ 1. Preset? → Call FastAPI    │
    │ 2. Builder? → Local backtest │
    └────────────┬─────────────────┘
                 ↓
      ┌──────────────────────┐
      │ Simulate trades:     │
      │ • Entry conditions   │
      │ • Exit conditions    │
      │ • Position sizing    │
      │ • Risk mgmt (SL/TP)  │
      └────────┬─────────────┘
               ↓
    ┌──────────────────────────────┐
    │ Calculate metrics:           │
    │ • Total return, Sharpe ratio │
    │ • Max drawdown, Win rate     │
    │ • Equity curve               │
    └────────┬─────────────────────┘
             ↓
    ┌──────────────────────────────┐
    │ Insert strategy_backtest_results
    │ Update job status='completed'
    └──────────────────────────────┘
```

**Market Data Fetch** (YFinance):
```typescript
const bars = await yfinance.getHistoricalBars({
  symbol: "AAPL",
  timeframe: "d1",  // or m15, h1, h4, w1
  startDate: "2023-01-01",
  endDate: "2024-01-01"
});
// Returns: { dates, opens, highs, lows, closes, volumes }
```

### 2.4 Metrics Calculation

**Results stored in `strategy_backtest_results.metrics` (JSONB)**:
```json
{
  "totalTrades": 45,
  "winningTrades": 28,
  "losingTrades": 17,
  "totalProfit": 15432.50,
  "totalReturn": 1.5432,  // 154.32%
  "maxDrawdown": 0.1205,  // -12.05%
  "sharpeRatio": 1.85,
  "performanceMetrics": {
    "winRate": 0.6222,  // 62.22%
    "avgProfit": 550.86,
    "avgWin": 731.42,
    "avgLoss": 412.53,
    "profitFactor": 1.77
  }
}
```

**Trades tracked** in `strategy_backtest_results.trades`:
```json
[
  {
    "entryTime": "2023-01-15T09:30:00Z",
    "exitTime": "2023-01-20T14:00:00Z",
    "entryPrice": 150.25,
    "exitPrice": 155.80,
    "quantity": 100,
    "pnl": 555.00,
    "pnlPercent": 0.0369,  // 3.69%
    "isWin": true
  },
  ...
]
```

---

## 3. Paper Trading Support (Limited)

**Current Status**: No explicit paper trading infrastructure exists.

**Alternative**: Backtesting results serve as performance estimates.

**Gaps**:
- ❌ No live position tracking table
- ❌ No real-time P&L updates
- ❌ No order management (pending, filled, cancelled)
- ❌ No slippage/commission modeling

**Could be added** with new tables:
```sql
paper_trading_positions
├── id (UUID)
├── strategy_id (UUID)
├── symbol (TEXT)
├── side (BUY|SELL)
├── quantity (numeric)
├── entry_price (numeric)
├── entry_time (TIMESTAMPTZ)
├── current_price (numeric)
├── current_pnl (numeric)
├── status (OPEN|CLOSED)
└── closed_at (TIMESTAMPTZ, nullable)
```

---

## 4. UI Components

### 4.1 React/TypeScript Frontend

**Strategy Builder Panel** (Location: `/Users/ericpeterson/SwiftBolt_ML/frontend/src/components/StrategyUI.tsx`):
```typescript
interface Strategy {
  id: string;
  name: string;
  description: string;
  parameters: StrategyParameter[];
  indicators: StrategyIndicator[];
  signalFilter: 'buy' | 'sell' | 'both';
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

// Component features:
// - Create/update/delete strategies
// - Select indicators (with toggles)
// - Configure parameters (number, string, boolean)
// - Queue backtests
// - Display mock results
```

**Backtest Panel** (Location: `/Users/ericpeterson/SwiftBolt_ML/frontend/src/components/StrategyBacktestPanel.tsx`):
```typescript
export interface StrategyConfig {
  entryConditions: EntryExitCondition[];
  exitConditions: EntryExitCondition[];
  positionSizing: PositionSizing;
  riskManagement: RiskManagement;
}

// Features:
// - Date range selector (presets: 1M, 3M, 1Y, etc.)
// - Symbol selector (AAPL, NVDA, CRWD, etc.)
// - Parameter tuning
// - Timeframe selection (d1, h1, m15, etc.)
// - Initial capital input
// - Results display: return, sharpe, max DD, win rate
// - Equity curve visualization
// - Trade list with entry/exit details
```

**Indicator Panel** (Location: `/Users/ericpeterson/SwiftBolt_ML/frontend/src/components/IndicatorPanel.tsx`):
- Lets user select which indicators to compute
- Configurable periods (RSI length, SMA period, etc.)
- Toggle visibility on chart

### 4.2 SwiftUI macOS Client

**Backtesting ViewModel** (Location: `/Users/ericpeterson/SwiftBolt_ML/client-macos/SwiftBoltML/ViewModels/BacktestingViewModel.swift`):
```swift
@MainActor
final class BacktestingViewModel: ObservableObject {
    @Published var backtestResult: BacktestResponse?
    @Published var isLoading = false
    @Published var error: String?
    @Published var jobId: String?
    @Published var jobStatus: BacktestJobStatus

    // Polling for async results
    let pollIntervalSeconds: UInt64 = 2
    let maxPolls = 300  // ~10 minutes timeout

    func runBacktest(symbol: String, timeframe: String = "d1") async {
        // 1. Queue job via APIClient.queueBacktestJob()
        // 2. Receive jobId
        // 3. Poll strategy-backtest?id=jobId every 2 sec
        // 4. When status='completed', display results
    }
}
```

**Strategy Models** (Location: `/Users/ericpeterson/SwiftBolt_ML/client-macos/SwiftBoltML/Models/TSStrategy.swift`):
```swift
struct TSStrategyModel: Codable, Identifiable {
    let id: String
    let name: String
    let description: String?
    var enabled: Bool
    let createdAt: Date
    var updatedAt: Date
    let conditions: [TSCondition]
    let actions: [TSAction]
}

struct TSCondition: Codable, Identifiable {
    let id: String
    let indicatorId: String  // 'rsi', 'macd', 'sma', etc.
    let threshold: Double
    let conditionOperator: TSOperator  // '>', '<', 'cross_up', etc.
    let logicalOperator: TSLogicalOperator  // 'and', 'or'
}
```

---

## 5. Chart Integration

### 5.1 TradingView Lightweight Charts

**Main Chart Component** (Location: `/Users/ericpeterson/SwiftBolt_ML/frontend/src/components/TradingViewChart.tsx`):

```typescript
export const TradingViewChart: React.FC<TradingViewChartProps> = ({
  symbol,
  horizon,
  daysBack = 7,
  srData = null,  // Support/Resistance levels
  strategySignals = [],  // Buy/sell signals
  indicators = [],  // RSI, MACD, BB, etc.
  trades = [],  // Historical trades
  backtestTrades = null,  // Backtest entry/exit markers
  thresholds = [],  // Threshold lines (e.g., overbought/oversold)
}) => {
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const forecastSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const confidenceBandRef = useRef<ISeriesApi<'Area'> | null>(null);

  // Series management:
  // 1. Candlestick: OHLC bars
  // 2. Line: Forecast target
  // 3. Area: Confidence bands (upper/lower)
  // 4. Line: Indicators (RSI, MACD lines, etc.)
  // 5. Markers: Entry/exit signals + backtest trades
};
```

**Data Flow**:
```
1. Load bars from /chart endpoint
   GET /chart?symbol=AAPL&timeframe=d1&start=2025-01-01&end=2025-12-31
   Response: { bars: ChartBar[], forecasts: ForecastData[], optionsRanks: OptionsRank[] }

2. Create candlestick series from bars
   bars.forEach(bar => candleSeries.update({
     time: toChartTime(bar.ts),
     open: bar.open,
     high: bar.high,
     low: bar.low,
     close: bar.close
   }))

3. Overlay forecasts (line series)
   forecast.points.forEach(point => forecastSeries.update({
     time: toChartTime(point.ts),
     value: point.value
   }))

4. Confidence bands (area series)
   area = chart.addAreaSeries({
     topColor: 'rgba(76, 175, 80, 0.2)',
     bottomColor: 'rgba(76, 175, 80, 0)'
   })
   forecast.points.forEach(point => area.update({
     time: toChartTime(point.ts),
     value: point.value
   }))

5. Markers for backtest trades
   backtestTrades.forEach(trade => candleSeries.setMarkers([
     {
       time: toChartTime(trade.entryTime),
       position: 'belowBar',
       color: '#2196F3',
       shape: 'arrowUp',
       text: `Entry: $${trade.entryPrice.toFixed(2)}`
     },
     {
       time: toChartTime(trade.exitTime),
       position: 'aboveBar',
       color: trade.isWin ? '#4CAF50' : '#F44336',
       shape: 'arrowDown',
       text: `Exit: $${trade.exitPrice.toFixed(2)} (${trade.pnlPercent.toFixed(1)}%)`
     }
   ])
```

**Supported Overlays** (from TypeScript interfaces):
- Candlestick price chart
- Forecast target line
- Confidence bands (area)
- Support/Resistance lines (polynomial curves)
- Moving averages (SMA, EMA)
- Momentum indicators (RSI, MACD, Stochastic)
- Volume bars
- Bollinger Bands
- Strategy entry/exit markers
- Backtest trade markers with P&L labels

### 5.2 Chart Data Endpoint

**Location**: `/Users/ericpeterson/SwiftBolt_ML/supabase/functions/chart/index.ts`

```typescript
GET /chart?symbol=AAPL&timeframe=d1&start=2025-01-01&end=2025-12-31

Response: {
  bars: ChartBar[],
  forecasts: ForecastData[],
  optionsRanks: OptionsRank[],
  latestPrice: number,
  lastBarTs: string,
  dataStatus: string,  // 'fresh' | 'stale' | 'gap'
  isMarketOpen: boolean,
  latestForecastRunAt: string,
  pendingSplitsWarning: boolean
}

interface ChartBar {
  ts: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  provider: string;  // 'alpaca', 'yfinance', 'polygon'
  dataStatus: string;  // 'verified', 'estimated', 'gap'
}

interface ForecastPoint {
  ts: string;
  value: number;
  lower: number;
  upper: number;
}

interface ForecastData {
  label: string;  // e.g., '1D', '5D', '20D'
  confidence: number;  // 0.0-1.0
  horizon: string;
  runAt: string;
  points: ForecastPoint[];
}
```

### 5.3 Intraday Chart Time Handling

**Challenge**: Mixed intraday (timestamps) + daily (dates) on same chart.

**Solution** (from `/Users/ericpeterson/SwiftBolt_ML/frontend/src/components/StrategyBacktestPanel.tsx`):
```typescript
function toChartTime(raw: string | number): string | number {
  if (typeof raw === 'number') return raw;  // Unix timestamp
  const s = String(raw ?? '').trim();
  if (!s) return '';

  // Has time component? → Unix timestamp (seconds)
  const hasTime = /^\d{4}-\d{2}-\d{2}[T\s]\d/.test(s);
  if (hasTime) return Math.floor(new Date(s).getTime() / 1000);

  // Date only? → Business day string (avoids duplicate timestamps)
  const day = s.match(/^(\d{4}-\d{2}-\d{2})/)?.[1];
  return day ?? s;  // e.g., '2025-01-15'
}
```

**Why**: Lightweight Charts can't render two bars at same `time`. Using business day strings for daily prevents collisions.

---

## 6. Condition/Rule Engine

### 6.1 Condition Evaluation Logic

**Builder Strategy Evaluation** (in backtest worker):
```typescript
function normalizeConfig(raw: StrategyConfig): {
  entry_conditions: Condition[];
  exit_conditions: Condition[];
} {
  // Converts frontend camelCase format to snake_case backend format
  const mapOne = (c: FrontendCondition): Condition => ({
    type: "indicator",
    name: c.type,  // 'rsi', 'macd', etc.
    operator: c.operator === ">" ? "above"
             : c.operator === "<" ? "below"
             : c.operator === "==" ? "equals"
             : "above",
    value: c.value ?? 0
  });
  return {
    entry_conditions: (raw.entryConditions ?? []).map(mapOne),
    exit_conditions: (raw.exitConditions ?? []).map(mapOne),
  };
}
```

**Bar-by-Bar Evaluation** (backtest loop):
```
FOR each bar IN historical_data:
  1. Compute all indicators (RSI, MACD, SMA, etc.) for this bar
  2. Evaluate entry_conditions:
     - For each condition: check if indicator[condition.name] [condition.operator] condition.value
     - If ALL entry conditions met AND position==FLAT → ENTER
  3. Evaluate exit_conditions:
     - For each condition: check exit logic
     - If ANY exit condition met AND position==LONG → EXIT
  4. Apply risk mgmt: Check stop_loss and take_profit
  5. Record trade if exit triggered
```

### 6.2 Supported Operators

```typescript
type Operator = '>' | '<' | '>=' | '<=' | '==' | 'cross_up' | 'cross_down';

// Examples:
// rsi > 70  → RSI above 70 (overbought)
// macd_signal cross_up macd  → MACD crosses above signal line
// bb_upper > close  → Price below upper band
// sma_20 cross_down close  → 20-SMA crosses below price (bearish)
```

**Cross Detection**:
```python
# Implemented in indicator calculation
def detect_cross(series1: np.ndarray, series2: np.ndarray) -> np.ndarray:
    """
    Returns array of True where series1 crosses above/below series2.
    Requires 2+ bars to detect.
    """
    cross_up = (series1[:-1] <= series2[:-1]) & (series1[1:] > series2[1:])
    cross_down = (series1[:-1] >= series2[:-1]) & (series1[1:] < series2[1:])
    return cross_up | cross_down
```

---

## 7. Key Files & Architecture Map

### Database & Migrations
- **Core strategy tables**: `/Users/ericpeterson/SwiftBolt_ML/supabase/migrations/20260221100000_strategy_builder_v2.sql`
- **RLS policies (anon support)**: `/Users/ericpeterson/SwiftBolt_ML/supabase/migrations/20260222100000_strategy_rls_anon_insert.sql`
- **FK constraints**: `/Users/ericpeterson/SwiftBolt_ML/supabase/migrations/20260221120000_fix_backtest_fk.sql`

### Backend APIs
- **Strategy CRUD**: `/Users/ericpeterson/SwiftBolt_ML/supabase/functions/strategy/index.ts`
- **Backtest queuing**: `/Users/ericpeterson/SwiftBolt_ML/supabase/functions/strategy-backtest/index.ts`
- **Backtest worker** (async): `/Users/ericpeterson/SwiftBolt_ML/supabase/functions/strategy-backtest-worker/index.ts`
- **Chart data**: `/Users/ericpeterson/SwiftBolt_ML/supabase/functions/chart/index.ts`

### ML Evaluation
- **Walk-forward CV**: `/Users/ericpeterson/SwiftBolt_ML/ml/src/evaluation/walk_forward_cv.py`
- **Daily evaluation job**: `/Users/ericpeterson/SwiftBolt_ML/ml/src/evaluation_job_daily.py`
- **Intraday evaluation job**: `/Users/ericpeterson/SwiftBolt_ML/ml/src/evaluation_job_intraday.py`

### React Frontend
- **Strategy UI**: `/Users/ericpeterson/SwiftBolt_ML/frontend/src/components/StrategyUI.tsx`
- **Backtest panel**: `/Users/ericpeterson/SwiftBolt_ML/frontend/src/components/StrategyBacktestPanel.tsx`
- **TradingView chart**: `/Users/ericpeterson/SwiftBolt_ML/frontend/src/components/TradingViewChart.tsx`
- **Indicator panel**: `/Users/ericpeterson/SwiftBolt_ML/frontend/src/components/IndicatorPanel.tsx`
- **Utility types**: `/Users/ericpeterson/SwiftBolt_ML/frontend/src/components/StrategyBacktestPanel.tsx` (lines 99-150)

### SwiftUI macOS Client
- **Backtesting ViewModel**: `/Users/ericpeterson/SwiftBolt_ML/client-macos/SwiftBoltML/ViewModels/BacktestingViewModel.swift`
- **Strategy models**: `/Users/ericpeterson/SwiftBolt_ML/client-macos/SwiftBoltML/Models/TSStrategy.swift`
- **GA strategy models**: `/Users/ericpeterson/SwiftBolt_ML/client-macos/SwiftBoltML/Models/GAStrategyModels.swift`

---

## 8. Implementation Gaps & Future Work

### Gaps (Missing Features)
1. **Paper Trading**: No live position tracking / P&L updates
2. **Real-time Signals**: Backtest results only; no live trade alerts
3. **Parameter Optimization**: No genetic algorithm or Bayesian tuning UI
4. **Multi-leg Strategies**: Only single entry/exit supported
5. **Commission/Slippage**: Backtest assumes zero friction
6. **Portfolio Backtesting**: Only single symbol per job
7. **Sentiment Integration**: Disabled due to zero-variance issue
8. **Risk Metrics**: No Calmar ratio, Sortino ratio options

### Recommended Enhancements
1. **Position Tracking Table**: Track live trades for paper trading
2. **Real-time Condition Checker**: Evaluate conditions on live bars
3. **Parameter Grid Search UI**: Let users specify ranges for optimization
4. **Multi-leg Template Library**: Pre-built spreads (iron condor, calendar spread, etc.)
5. **Walk-forward Results Display**: Show fold-by-fold performance in UI
6. **Strategy Comparison**: Side-by-side backtest metrics for A/B testing
7. **Backtested Forecast Blending**: Weight strategies by historical accuracy
8. **Webhooks for Alerts**: Notify when entry conditions met

---

## 9. Code Conventions & Patterns

### Python (ML Pipeline)
- **Type hints** on all function signatures
- **pydantic-settings** for config (`ml/config/settings.py`)
- **Walk-forward validation** only (no random splits)
- **Lookahead checks** via `STRICT_LOOKAHEAD_CHECK` env flag

### TypeScript/Deno (Edge Functions)
- Each function in own `supabase/functions/<name>/index.ts`
- Shared utilities in `supabase/functions/_shared/`
- Cache-first reads (return cached, refresh if stale)
- RLS policies enforce data isolation

### React/TypeScript
- Controlled components with `useState`
- Async backtest polling with intervals
- Deduplication logic for time-series data
- Intraday-aware time formatting (Unix vs. business day string)

### Swift (macOS)
- `@MainActor` for UI updates
- `async/await` for network calls
- Combine `@Published` for reactive updates
- Polling with max timeout (300 polls × 2 sec = 10 min)

---

## 10. Testing & Validation

### Test Coverage
- **ML**: Unit tests in `ml/tests/` (run with `pytest ml/tests/ -m "not integration" -v`)
- **Edge Functions**: Deno linting with `deno lint supabase/functions/`
- **Walk-forward validation**: Verified no data leakage in `ml/src/evaluation/walk_forward_cv.py`

### Known Test Commands
```bash
# ML tests
pytest ml/tests/ -v
pytest ml/tests/path/to/test_file.py::TestClass::test_method -v

# Edge Functions
deno lint supabase/functions/
deno fmt --check supabase/functions/

# Frontend build
cd frontend && npm run build
```

---

## Summary Table

| Component | Location | Type | Status | Notes |
|-----------|----------|------|--------|-------|
| **Strategy Storage** | Supabase Postgres | JSONB | ✅ | `strategy_user_strategies.config` |
| **Backtest Jobs** | Supabase Postgres | Job Queue | ✅ | `strategy_backtest_jobs` + worker |
| **Walk-Forward CV** | Python ML | Validation | ✅ | No lookahead bias |
| **Preset Strategies** | FastAPI | Backend | ✅ | SuperTrend AI, SMA Crossover, Buy&Hold |
| **Builder Strategies** | TypeScript Worker | Local | ✅ | Custom conditions evaluated in TS |
| **Chart Integration** | TradingView | Frontend | ✅ | Lightweight Charts library |
| **Strategy Indicators** | TypeScript/Python | Computation | ✅ | 30+ indicator types supported |
| **Paper Trading** | — | — | ❌ | No live position tracking |
| **Multi-leg Strategies** | — | — | ❌ | Single entry/exit only |
| **Parameter Optimization** | — | — | ❌ | No GA/Bayesian tuning UI |
| **Real-time Alerts** | — | — | ❌ | Backtest results only |

---

**Research Complete**
Ready for strategy platform planning and implementation sprints.
