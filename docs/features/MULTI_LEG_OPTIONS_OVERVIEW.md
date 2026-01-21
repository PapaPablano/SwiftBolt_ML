# Multi-Leg Options Strategy Support

## Overview

Multi-leg options strategies combine multiple option contracts (calls, puts, or both) to create sophisticated positions with defined risk/reward profiles. This document outlines the data architecture, strategy classification system, and integration approach for supporting multi-leg strategies in SwiftBolt ML.

## Supported Strategy Types

### Simple Spreads

| Strategy | Legs | Max Loss | Max Profit | Breakeven | Best For |
|----------|------|----------|-----------|-----------|----------|
| **Bull Call Spread** | 2 (Buy Call, Sell Call) | Premium Paid | Width - Premium | Long Strike + Premium | Bullish, limited capital |
| **Bear Call Spread** | 2 (Sell Call, Buy Call) | Width - Premium | Premium Collected | Short Strike - Premium | Bearish, premium collection |
| **Bull Put Spread** | 2 (Sell Put, Buy Put) | Width - Premium | Premium Collected | Short Strike - Premium | Bullish, premium collection |
| **Bear Put Spread** | 2 (Buy Put, Sell Put) | Premium Paid | Width - Premium | Long Strike + Premium | Bearish, defined risk |

### Straddles & Strangles

| Strategy | Legs | Max Loss | Max Profit | Breakeven | Best For |
|----------|------|----------|-----------|-----------|----------|
| **Long Straddle** | 2 (Buy Call, Buy Put) | Premium Paid | Unlimited | Strike ± Premium | High volatility, direction neutral |
| **Short Straddle** | 2 (Sell Call, Sell Put) | Unlimited | Premium Collected | Strike ± Premium | Low volatility, income |
| **Long Strangle** | 2 (Buy OTM Call, Buy OTM Put) | Premium Paid | Unlimited | Strikes ± Premium | High volatility, cheap |
| **Short Strangle** | 2 (Sell OTM Call, Sell OTM Put) | Unlimited | Premium Collected | Strikes ± Premium | Low volatility, income |

### Complex Multi-Leg Strategies

| Strategy | Legs | Structure | Use Case |
|----------|------|-----------|----------|
| **Iron Condor** | 4 | Bull Put + Bear Call | Income neutral, wide range |
| **Iron Butterfly** | 4 | Buy OTM, Sell ATM, Buy OTM | Income tight range |
| **Call Ratio Backspread** | 3+ | Sell ATM, Buy OTM | Bullish, unlimited upside |
| **Put Ratio Backspread** | 3+ | Sell ATM, Buy OTM | Bearish, unlimited downside |
| **Calendar Spread** | 2 | Same strike, different expiry | Theta decay play |
| **Diagonal Spread** | 2 | Different strike + expiry | Directional + income |
| **Butterfly Spread** | 3 | Buy ATM, Sell x2 middle, Buy ATM | Limited risk/reward |

## Data Model - Multi-Leg Positions

### Core Tables

#### `options_strategies` (Registry)
```sql
CREATE TABLE options_strategies (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES auth.users ON DELETE CASCADE,
  name TEXT NOT NULL,                    -- "Bull Call Spread - AAPL"
  strategy_type VARCHAR(50) NOT NULL,    -- "bull_call_spread", "iron_condor", etc.
  underlying_symbol_id UUID REFERENCES symbols(id),
  underlying_ticker TEXT,
  
  -- Strategy metadata
  created_at TIMESTAMPTZ DEFAULT NOW(),
  closed_at TIMESTAMPTZ,
  status VARCHAR(20) DEFAULT 'open',     -- "open", "closed", "expired"
  
  -- Net cost / credit structure
  total_debit NUMERIC,                   -- Cost to open (sum of all buys)
  total_credit NUMERIC,                  -- Income on open (sum of all sells)
  net_premium NUMERIC,                   -- Net debit or credit
  
  -- Risk profile
  max_risk NUMERIC,                      -- Maximum possible loss
  max_reward NUMERIC,                    -- Maximum possible profit
  breakeven_points NUMERIC[],            -- [breakeven1, breakeven2, ...]
  
  -- Forecast coupling
  ml_alignment_score NUMERIC,            -- How well does strategy align with forecast?
  ml_forecast_id UUID REFERENCES ml_forecasts(id),
  
  tags JSONB,                            -- {"sentiment": "bullish", "timeframe": "1w"}
  notes TEXT,
  
  UNIQUE(user_id, name, created_at)
);

CREATE INDEX ix_options_strategies_user_status ON options_strategies(user_id, status);
CREATE INDEX ix_options_strategies_symbol ON options_strategies(underlying_symbol_id);
```

#### `options_legs` (Individual Contracts)
```sql
CREATE TABLE options_legs (
  id UUID PRIMARY KEY,
  strategy_id UUID REFERENCES options_strategies(id) ON DELETE CASCADE,
  
  -- Leg position
  leg_number INT NOT NULL,               -- 1, 2, 3, 4 (order in strategy)
  position_type VARCHAR(10) NOT NULL,    -- "long" or "short"
  option_type VARCHAR(4) NOT NULL,       -- "call" or "put"
  
  -- Strike and expiration
  strike NUMERIC NOT NULL,
  expiry DATE NOT NULL,
  dte INT,                               -- Days to expiration at entry
  
  -- Entry details
  entry_price NUMERIC NOT NULL,          -- Premium paid/received per contract
  contracts INT NOT NULL DEFAULT 1,      -- Number of contracts
  total_cost NUMERIC,                    -- entry_price * contracts * 100
  entry_timestamp TIMESTAMPTZ,
  
  -- Current state
  current_price NUMERIC,
  current_value NUMERIC,                 -- current_price * contracts * 100
  pl_amount NUMERIC,                     -- current_value - total_cost
  pl_percent NUMERIC,                    -- (current_value - total_cost) / ABS(total_cost) * 100
  
  -- Exit (if leg closed early)
  exit_price NUMERIC,
  exit_timestamp TIMESTAMPTZ,
  exit_pl NUMERIC,
  
  -- Greeks (snapshot at entry, updated periodically)
  entry_delta NUMERIC,
  entry_gamma NUMERIC,
  entry_theta NUMERIC,
  entry_vega NUMERIC,
  
  current_delta NUMERIC,
  current_gamma NUMERIC,
  current_theta NUMERIC,
  current_vega NUMERIC,
  
  -- Risk flags
  is_assigned BOOLEAN DEFAULT FALSE,
  assignment_timestamp TIMESTAMPTZ,
  
  notes TEXT,
  UNIQUE(strategy_id, leg_number)
);

CREATE INDEX ix_options_legs_strategy ON options_legs(strategy_id);
```

#### `options_leg_entries` (Average Cost Tracking)
```sql
CREATE TABLE options_leg_entries (
  id UUID PRIMARY KEY,
  leg_id UUID REFERENCES options_legs(id) ON DELETE CASCADE,
  
  entry_price NUMERIC NOT NULL,
  contracts INT NOT NULL,
  entry_timestamp TIMESTAMPTZ DEFAULT NOW(),
  
  notes TEXT,
  
  CONSTRAINT positive_contracts CHECK (contracts > 0)
);

CREATE INDEX ix_options_leg_entries_leg ON options_leg_entries(leg_id);
```

#### `options_multi_leg_alerts` (Strategy-Level Alerts)
```sql
CREATE TABLE options_multi_leg_alerts (
  id UUID PRIMARY KEY,
  strategy_id UUID REFERENCES options_strategies(id) ON DELETE CASCADE,
  
  alert_type VARCHAR(50) NOT NULL,   -- "leg_expires_soon", "strike_breached", 
                                       -- "forecast_flip", "assignment_risk", 
                                       -- "profit_target_hit", "stop_loss_hit"
  
  severity VARCHAR(20) NOT NULL,     -- "info", "warning", "critical"
  reason TEXT,
  details JSONB,
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  resolved_at TIMESTAMPTZ,
  
  action_required BOOLEAN DEFAULT TRUE
);

CREATE INDEX ix_multi_leg_alerts_strategy ON options_multi_leg_alerts(strategy_id);
```

#### `options_strategy_templates` (Pre-built Configs)
```sql
CREATE TABLE options_strategy_templates (
  id UUID PRIMARY KEY,
  name VARCHAR(100) NOT NULL UNIQUE,  -- "Bull Call 1:1", "Iron Condor ATM"
  strategy_type VARCHAR(50) NOT NULL,
  
  leg_config JSONB NOT NULL,          -- Predefined leg setup:
                                       -- [{
                                       --   "leg": 1,
                                       --   "type": "long",
                                       --   "option_type": "call",
                                       --   "strike_offset": -5,  -- relative to spot
                                       --   "dte": 30
                                       -- }, ...]
  
  description TEXT,
  
  -- Expected outcome ranges
  typical_max_risk NUMERIC,
  typical_max_reward NUMERIC,
  
  created_by UUID REFERENCES auth.users(id),
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

## Strategy Classification System

### Leg Roles

Each leg in a multi-leg strategy has semantic meaning:

```typescript
enum LegRole {
  // Spreads
  PRIMARY_LEG = "primary_leg",        // Main directional bet (e.g., long call)
  HEDGE_LEG = "hedge_leg",            // Risk reduction (e.g., short call above)
  
  // Straddles / Strangles
  UPSIDE_LEG = "upside_leg",          // Long call or short put
  DOWNSIDE_LEG = "downside_leg",      // Long put or short call
  
  // Multi-leg
  INCOME_LEG = "income_leg",          // Short legs collecting premium
  PROTECTION_LEG = "protection_leg",  // Long legs limiting loss
  SPECULATION_LEG = "speculation_leg" // Unlimited upside/downside
}
```

### Payoff Diagram Zones

Multi-leg strategies create **three zones**:

1. **Profit Zone** — Where underlying price yields net profit
2. **Loss Zone** — Where underlying price yields net loss
3. **Breakeven Points** — Exact underlying prices where P&L = 0

Example: Bull Call Spread (Buy $100C, Sell $105C at $1 net debit)
- Profit Zone: $101 – $105 (profit = (underlying - $100) - $1 credit if ITM legs)
- Loss Zone: < $99 or > $105
- Breakevens: $101 and $105

## Real-Time P&L Calculation

### Single Leg P&L
```
P&L = (Current Price - Entry Price) × 100 × Contracts × ± Position Type
      where ± = +1 for long, -1 for short
```

### Multi-Leg Strategy P&L
```
Strategy P&L = Σ(Leg P&L for all legs)

Example (Bull Call Spread):
  - Long $100 Call @ $3 = -$300 (debit)
  - Short $105 Call @ $1 = +$100 (credit)
  - Net Entry Cost = -$200
  
  If underlying = $102.50:
  - Long $100 Call now @ $2.75 = -$275
  - Short $105 Call now @ $0.25 = +$25
  - Current Value = -$250
  - P&L = -$250 - (-$200) = -$50 (loss of $50)
```

## Integration Points

### 1. ML Forecast Coupling

Multi-leg strategies can be **aligned with ML forecasts**:

```sql
-- Add to options_strategies
- forecast_horizon VARCHAR(10),      -- "1D", "1W", etc.
- forecast_alignment TEXT,           -- "bullish", "bearish", "neutral"
- confidence_threshold NUMERIC,      -- Min confidence to flag misalignment
```

**Alert Logic:**
- If strategy is bullish (bull call spread) but forecast flips bearish → `forecast_flip` alert
- If confidence drops below user threshold → `confidence_weakened` alert

### 2. Options Ranker Integration

Legs are auto-populated from **options ranker** suggestions:

1. User selects 2+ strikes from ranker result
2. SwiftUI workflow: "Create Spread" → selects strategy type → validates strikes
3. Legs inherit: current price, IV, delta, gamma, theta from ranker data
4. Strategy stored; alerts initialized

### 3. Watchlist Monitoring

Multi-leg strategies surface in **watchlist** with:

- Strategy name and type badge
- Net P&L and % return
- Days to expiration (minimum across all legs)
- Next alert (e.g., "Assignment risk in 3 days")
- ML alignment indicator (green/yellow/red)

### 4. Scheduled Jobs

#### `evaluate_multi_leg_strategies` (Every 15 min)
```python
for each open strategy:
  1. Fetch current option prices from options_ranker / cache
  2. Compute legs P&L, updated greeks
  3. Check alert triggers:
     - Days to expiration < 3 days
     - Strike breached (underlying crossed boundary)
     - Assignment risk (ITM short leg)
     - Forecast misalignment
     - Profit target or stop loss hit
  4. Write alerts to options_multi_leg_alerts
  5. Update strategy P&L and status
```

#### `rebalance_multi_leg_suggestions` (Daily at market open)
```python
for each open strategy:
  1. Check if any leg has close expiration (< 7 days)
  2. Suggest roll or close action
  3. If forecast available:
     - Compare strategy thesis to forecast direction
     - Flag if misaligned
```

## User Workflows

### Create a Multi-Leg Strategy

```
User: Click "New Strategy"
  ↓
System: Show strategy type selector
  (Bull Call Spread, Iron Condor, etc.)
  ↓
User: Select "Bull Call Spread"
  ↓
System: Show template with "Buy Call" and "Sell Call" slots
  ↓
User: Input underlying (AAPL)
  ↓
System: Show current options chain, highlighted suggested strikes
  (e.g., ATM -5 for long call, ATM for short call)
  ↓
User: Click leg 1 strike (or use template)
  ↓
System: Update P&L diagram and Greeks summary
  ↓
User: Click leg 2 strike
  ↓
System: Finalize max risk, max reward, breakevens
  ↓
User: Confirm entry price/contracts → SAVE
  ↓
System: Create strategy record, initialize alerts, show on watchlist
```

### Manage Open Strategy

```
User: Click strategy in watchlist
  ↓
System: Show strategy detail page:
  - Payoff diagram (real-time)
  - Current P&L per leg + total
  - Greeks summary (combined delta, theta, vega)
  - Alerts (assignment risk, expiration, forecast misalignment)
  ↓
User: Click "Close Leg" or "Roll Leg"
  ↓
System: Show current prices, suggest exits
  ↓
User: Confirm → record exit, update strategy status
```

## Security & RLS

All tables use **Row Level Security (RLS)** to ensure users see only their own strategies:

```sql
ALTER TABLE options_strategies ENABLE ROW LEVEL SECURITY;

CREATE POLICY options_strategies_user_own ON options_strategies
  FOR ALL
  USING (auth.uid() = user_id);

-- Similar for options_legs, options_multi_leg_alerts, options_leg_entries
```

## Performance Considerations

### Indexes for Key Queries

```sql
-- Fast strategy lookup by user and status
CREATE INDEX ix_options_strategies_user_status 
  ON options_strategies(user_id, status);

-- Fast underlying symbol queries
CREATE INDEX ix_options_strategies_symbol 
  ON options_strategies(underlying_symbol_id);

-- Fast alert evaluation
CREATE INDEX ix_options_multi_leg_alerts_strategy 
  ON options_multi_leg_alerts(strategy_id, created_at DESC);

-- Fast leg P&L updates
CREATE INDEX ix_options_legs_strategy 
  ON options_legs(strategy_id);
```

### Query Optimization

- **Batch fetch legs:** Query all legs for a strategy once; avoid N+1
- **Cache current prices:** Use `options_ranker` table; don't re-query raw options API
- **Lazy-load alerts:** Load only active alerts on strategy detail, resolved alerts on demand

## Next Steps

1. **Schema Migration** — Create tables in Supabase
2. **Backend Evaluator** — Implement alert logic in Python job
3. **SwiftUI Wiring** — Add multi-leg form, strategy detail, alerts
4. **Testing** — Unit tests for P&L, Greeks, alert triggers
5. **Documentation** — Strategy guides for users (bull spreads, iron condors, etc.)

---

## References

- [Options Chain Implementation](../OPTIONS_CHAIN_IMPLEMENTATION.md)
- [Options Ranker Setup](../OPTIONS_RANKER_SETUP.md)
- [Options Watchlist Plan](../../options_watchlist.md)
- [Master Blueprint - Options Ranker](../master_blueprint.md#42-options-ranker)
