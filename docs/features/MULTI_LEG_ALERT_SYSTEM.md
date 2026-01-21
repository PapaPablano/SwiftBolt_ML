# Multi-Leg Options Alert System

## Overview

This document describes the real-time alert and monitoring system for multi-leg option strategies. The system evaluates open strategies against market conditions, forecasts, and user-defined thresholds to surface actionable alerts.

## Alert Types

### Market-Based Alerts

#### 1. Expiration Soon
**Type:** `expiration_soon`  
**Severity:** warning (info if 10+ days)  
**Trigger:** Any leg with DTE <= 3

**Evaluation:**
```python
def check_expiration_soon(leg: OptionsLeg) -> Optional[Alert]:
    dte = leg.current_dte
    if dte <= 3:
        return Alert(
            alert_type="expiration_soon",
            severity="warning" if dte <= 3 else "info",
            title=f"Leg {leg.leg_number} expires in {dte} day(s)",
            reason=f"Contract expires on {leg.expiry.strftime('%b %d')}",
            details={
                "leg_number": leg.leg_number,
                "option_type": leg.option_type,
                "strike": float(leg.strike),
                "expiry": leg.expiry.isoformat(),
                "dte": dte
            },
            suggested_action="Close leg or roll to next expiration"
        )
```

#### 2. Strike Breached
**Type:** `strike_breached`  
**Severity:** critical  
**Trigger:** Underlying price crosses or approaches significant strikes

**Evaluation:**
```python
def check_strike_breached(strategy: MultiLegStrategy, underlying_price: Decimal) -> List[Alert]:
    alerts = []
    
    for leg in strategy.legs:
        if leg.is_closed:
            continue
        
        # Check if current price crossed strike
        itm_threshold = leg.strike * Decimal('0.99')  # 1% away
        
        if leg.position_type == "short":
            # Short leg: breached if underlying moved TOWARD strike
            if leg.option_type == "call" and underlying_price >= itm_threshold:
                alerts.append(Alert(
                    alert_type="strike_breached",
                    severity="critical",
                    title=f"Short {leg.option_type.upper()} strike ${leg.strike} breached",
                    reason=f"Underlying ${underlying_price} is within 1% of strike",
                    details={
                        "leg_number": leg.leg_number,
                        "strike": float(leg.strike),
                        "underlying_price": float(underlying_price),
                        "distance_to_strike": float(underlying_price - leg.strike),
                        "is_itm": underlying_price > leg.strike
                    },
                    suggested_action="Monitor for assignment or close position"
                ))
    
    return alerts
```

#### 3. Assignment Risk
**Type:** `assignment_risk`  
**Severity:** critical  
**Trigger:** Short leg is deep ITM with low extrinsic value

**Evaluation:**
```python
def check_assignment_risk(leg: OptionsLeg, current_price: Decimal, 
                         current_iv: Decimal) -> Optional[Alert]:
    if leg.position_type != "short" or leg.option_type != "call":
        return None
    
    # Assignment likely if:
    # 1. Deep ITM (>2 strikes)
    # 2. Days to expiry < 3
    # 3. Extrinsic value < 0.1 * strike width
    
    is_deep_itm = current_price > leg.strike + 2.0
    days_to_expiry = leg.current_dte
    
    if is_deep_itm and days_to_expiry <= 3:
        return Alert(
            alert_type="assignment_risk",
            severity="critical",
            title=f"Assignment risk: ${leg.strike} short call",
            reason=f"Contract is deep ITM ({current_price:.2f} vs ${leg.strike}) with {days_to_expiry} DTE",
            details={
                "leg_number": leg.leg_number,
                "strike": float(leg.strike),
                "current_price": float(current_price),
                "is_deep_itm": is_deep_itm,
                "dte": days_to_expiry
            },
            suggested_action="Close position immediately or prepare for assignment"
        )
```

#### 4. Volatility Events
**Type:** `volatility_spike` | `vega_squeeze`  
**Severity:** warning | info  
**Trigger:** IV change > 1 std dev from historical average

**Evaluation:**
```python
def check_volatility_events(strategy: MultiLegStrategy, 
                           current_iv: Decimal,
                           historical_iv_mean: Decimal,
                           historical_iv_std: Decimal) -> List[Alert]:
    alerts = []
    
    iv_zscore = abs((current_iv - historical_iv_mean) / (historical_iv_std or Decimal('0.01')))
    
    if iv_zscore > Decimal('2.0'):  # > 2 std devs
        # Determine if short or long vega
        short_vega = sum(leg.current_vega or 0 for leg in strategy.legs 
                        if leg.position_type == "short" and not leg.is_closed)
        
        alert_type = "volatility_spike" if iv_zscore > 2 else "vega_squeeze"
        severity = "warning" if short_vega else "info"
        
        alerts.append(Alert(
            alert_type=alert_type,
            severity=severity,
            title=f"Implied volatility spike ({iv_zscore:.1f} std dev)",
            reason=f"IV is {current_iv:.1%}, historical mean {historical_iv_mean:.1%}",
            details={
                "current_iv": float(current_iv),
                "historical_mean": float(historical_iv_mean),
                "zscore": float(iv_zscore),
                "short_vega_exposure": float(short_vega) if short_vega else 0
            },
            suggested_action="Short vega strategies may profit; monitor for exit" if short_vega 
                          else "Review vega exposure; consider hedging"
        ))
    
    return alerts
```

### Forecast-Based Alerts

#### 5. Forecast Flip
**Type:** `forecast_flip`  
**Severity:** critical  
**Trigger:** Strategy thesis contradicts ML forecast direction

**Evaluation:**
```python
def check_forecast_flip(strategy: MultiLegStrategy, 
                       forecast: MLForecast) -> Optional[Alert]:
    if not strategy.forecast_id or not strategy.forecast_alignment:
        return None
    
    strategy_thesis = strategy.forecast_alignment  # bullish, neutral, bearish
    forecast_label = forecast.overall_label       # bullish, neutral, bearish
    
    # Misalignment examples:
    # - Bull call spread but forecast turns bearish
    # - Short straddle (neutral) but forecast is bullish
    
    are_aligned = (
        (strategy_thesis == "bullish" and forecast_label in ["bullish", "neutral"]) or
        (strategy_thesis == "bearish" and forecast_label in ["bearish", "neutral"]) or
        (strategy_thesis == "neutral" and forecast_label == "neutral")
    )
    
    if not are_aligned and forecast.confidence > Decimal('0.7'):
        return Alert(
            alert_type="forecast_flip",
            severity="critical",
            title=f"Forecast misalignment: {strategy_thesis} strategy vs {forecast_label} forecast",
            reason=f"Strategy was opened assuming {strategy_thesis} outlook, "
                   f"but forecast shows {forecast_label} with {forecast.confidence:.0%} confidence",
            details={
                "strategy_thesis": strategy_thesis,
                "forecast_label": forecast_label,
                "forecast_confidence": float(forecast.confidence),
                "forecast_horizon": forecast.horizon
            },
            suggested_action="Review thesis or close position if conviction is lost"
        )
```

#### 6. Target Price Breached
**Type:** `profit_target_hit` | `stop_loss_hit`  
**Severity:** warning  
**Trigger:** Strategy reaches profit target or stop loss threshold

**Evaluation:**
```python
def check_pl_targets(strategy: MultiLegStrategy,
                    user_profit_target_pct: Decimal = Decimal('0.5'),
                    user_stop_loss_pct: Decimal = Decimal('-0.5')) -> List[Alert]:
    alerts = []
    
    # Check profit target
    if strategy.total_pl_pct >= user_profit_target_pct:
        alerts.append(Alert(
            alert_type="profit_target_hit",
            severity="warning",
            title=f"Profit target reached: {strategy.total_pl_pct:.1%}",
            reason=f"Position has gained {strategy.total_pl_pct:.1%} (target {user_profit_target_pct:.1%})",
            details={
                "total_pl": float(strategy.total_pl),
                "total_pl_pct": float(strategy.total_pl_pct),
                "target_pct": float(user_profit_target_pct)
            },
            suggested_action="Consider taking profits or scaling out"
        ))
    
    # Check stop loss
    if strategy.total_pl_pct <= user_stop_loss_pct:
        alerts.append(Alert(
            alert_type="stop_loss_hit",
            severity="critical",
            title=f"Stop loss triggered: {strategy.total_pl_pct:.1%}",
            reason=f"Position has lost {abs(strategy.total_pl_pct):.1%} (stop {user_stop_loss_pct:.1%})",
            details={
                "total_pl": float(strategy.total_pl),
                "total_pl_pct": float(strategy.total_pl_pct),
                "stop_loss_pct": float(user_stop_loss_pct)
            },
            suggested_action="Close position per stop loss rule"
        ))
    
    return alerts
```

### Greeks-Based Alerts

#### 7. Theta Decay Benefit
**Type:** `theta_decay_benefit`  
**Severity:** info  
**Trigger:** Short positions accumulating theta > $50/day (configurable)

**Evaluation:**
```python
def check_theta_benefit(strategy: MultiLegStrategy,
                       min_daily_theta: Decimal = Decimal('50')) -> Optional[Alert]:
    # Short positions benefit from theta decay
    daily_theta = strategy.combined_theta or Decimal('0')
    
    if daily_theta >= min_daily_theta:  # Positive theta for short positions
        return Alert(
            alert_type="theta_decay_benefit",
            severity="info",
            title=f"Strong theta decay benefit: ${daily_theta:.2f}/day",
            reason=f"Short premium strategy collecting ~${daily_theta:.2f} per day from time decay",
            details={
                "daily_theta": float(daily_theta),
                "total_theta": float(strategy.combined_theta or 0),
                "min_dte": strategy.min_dte
            },
            suggested_action="Monitor strategy; let theta work in your favor"
        )
```

#### 8. Gamma Risk
**Type:** `gamma_risk`  
**Severity:** warning  
**Trigger:** High gamma exposure with large daily moves

**Evaluation:**
```python
def check_gamma_risk(strategy: MultiLegStrategy,
                    underlying_daily_move: Decimal) -> Optional[Alert]:
    # Gamma = delta change per 1% underlying move
    gamma_impact = (strategy.combined_gamma or Decimal('0')) * underlying_daily_move
    
    if abs(gamma_impact) > Decimal('0.15'):  # Delta could swing 15%
        return Alert(
            alert_type="gamma_risk",
            severity="warning",
            title=f"High gamma risk: delta could swing {gamma_impact:.0%}",
            reason=f"Underlying moved {underlying_daily_move:.2%}, gamma exposure suggests delta change",
            details={
                "gamma": float(strategy.combined_gamma or 0),
                "underlying_move": float(underlying_daily_move),
                "delta_impact": float(gamma_impact)
            },
            suggested_action="Monitor delta closely; rehedge if needed"
        )
```

## Scheduled Evaluation Job

### `evaluate_multi_leg_strategies` (Every 15 minutes)

```python
# backend/jobs/evaluate_multi_leg_strategies.py

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List

from supabase import create_client
from services.strategy_evaluator import StrategyEvaluator
from services.options_ranker import OptionsRankerService
from services.ml_forecast import MLForecastService

async def evaluate_all_strategies():
    """Main job: evaluate all open strategies and generate alerts."""
    print(f"[{datetime.now()}] Starting multi-leg strategy evaluation...")
    
    # 1. Fetch all open strategies
    strategies = await fetch_open_strategies()
    print(f"Evaluating {len(strategies)} open strategies")
    
    for strategy in strategies:
        try:
            await evaluate_single_strategy(strategy)
        except Exception as e:
            print(f"Error evaluating strategy {strategy['id']}: {str(e)}")
            # Log error but continue with other strategies
    
    print(f"[{datetime.now()}] Evaluation complete")

async def evaluate_single_strategy(strategy: dict):
    """Evaluate one strategy and create alerts."""
    
    strategy_id = strategy['id']
    user_id = strategy['user_id']
    
    # 1. Fetch current option prices from ranker
    legs_with_prices = await fetch_current_leg_prices(strategy)
    
    # 2. Fetch forecast if attached
    forecast = None
    if strategy['forecast_id']:
        forecast = await fetch_forecast(strategy['forecast_id'])
    
    # 3. Calculate current P&L and Greeks
    evaluator = StrategyEvaluator(strategy, legs_with_prices)
    pl_summary = evaluator.calculate_pl_summary()
    greeks_summary = evaluator.calculate_greeks_summary()
    
    # 4. Check all alert triggers
    alerts = []
    
    # Market-based
    alerts.extend(await check_expiration_alerts(strategy['legs']))
    alerts.extend(await check_strike_breach_alerts(strategy, pl_summary['underlying_price']))
    alerts.extend(await check_assignment_risk_alerts(strategy))
    
    # Forecast-based
    if forecast:
        alerts.extend(await check_forecast_alerts(strategy, forecast))
        alerts.extend(await check_pl_targets(strategy, forecast))
    
    # Greeks-based
    alerts.extend(await check_greeks_alerts(strategy, greeks_summary))
    
    # 5. Write new alerts (skip if already exists)
    for alert in alerts:
        await write_alert_if_new(strategy_id, alert)
    
    # 6. Update strategy P&L and Greeks
    await update_strategy_state(strategy_id, pl_summary, greeks_summary)
    
    # 7. Record daily metric snapshot
    await record_strategy_metric(strategy_id, pl_summary)
    
    return alerts

async def fetch_current_leg_prices(strategy: dict) -> List[dict]:
    """Get current option prices from options_ranker table."""
    # Query options_ranker for most recent prices of strategy legs
    pass

async def check_expiration_alerts(legs: List[dict]) -> List[dict]:
    """Check all legs for expiration alerts."""
    alerts = []
    for leg in legs:
        if not leg['is_closed']:
            alert = check_expiration_soon(leg)
            if alert:
                alerts.append(alert)
    return alerts

async def write_alert_if_new(strategy_id: str, alert: dict):
    """Write alert only if similar alert doesn't already exist."""
    # Check for similar unresolved alert
    existing = await query_existing_alert(
        strategy_id=strategy_id,
        alert_type=alert['alert_type'],
        resolved_at=None  # Only unresolved
    )
    
    if not existing:
        await insert_alert(strategy_id, alert)
```

## Alert Configuration

Users can configure alert thresholds:

```sql
CREATE TABLE user_alert_preferences (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  
  -- Expiration
  enable_expiration_alerts BOOLEAN DEFAULT TRUE,
  expiration_alert_dte INT DEFAULT 3,         -- Alert when DTE <= this
  
  -- Strike breach
  enable_strike_alerts BOOLEAN DEFAULT TRUE,
  strike_breach_threshold NUMERIC DEFAULT 0.01,  -- 1% away from strike
  
  -- Assignment
  enable_assignment_alerts BOOLEAN DEFAULT TRUE,
  
  -- P&L targets
  enable_profit_target_alerts BOOLEAN DEFAULT TRUE,
  profit_target_pct NUMERIC DEFAULT 0.50,    -- 50%
  
  enable_stop_loss_alerts BOOLEAN DEFAULT TRUE,
  stop_loss_pct NUMERIC DEFAULT -0.30,       -- -30%
  
  -- Forecast
  enable_forecast_alerts BOOLEAN DEFAULT TRUE,
  min_forecast_confidence NUMERIC DEFAULT 0.70,  -- 70%
  
  -- Greeks
  enable_theta_alerts BOOLEAN DEFAULT TRUE,
  min_daily_theta NUMERIC DEFAULT 50,        -- $50/day
  
  enable_gamma_alerts BOOLEAN DEFAULT TRUE,
  gamma_alert_threshold NUMERIC DEFAULT 0.15,  -- 15% delta swing
  
  -- Frequency (to avoid alert spam)
  max_alerts_per_hour INT DEFAULT 10,
  alert_batch_window_minutes INT DEFAULT 15,  -- Batch alerts
  
  UNIQUE(user_id)
);
```

## Alert Display in UI

### SwiftUI Alert Panel

```swift
// client-macos/SwiftBoltML/Views/MultiLegAlertView.swift

import SwiftUI

struct MultiLegAlertPanel: View {
    @ObservedObject var viewModel: StrategyDetailViewModel
    @State private var selectedAlert: MultiLegAlert?
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Alerts")
                    .font(.headline)
                Spacer()
                Text("\(viewModel.activeAlerts.count)")
                    .font(.caption)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Color.red.opacity(0.2))
                    .cornerRadius(4)
            }
            
            if viewModel.activeAlerts.isEmpty {
                Text("No active alerts")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .padding(.vertical, 8)
            } else {
                ScrollView {
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(viewModel.activeAlerts) { alert in
                            AlertRow(alert: alert)
                                .onTapGesture {
                                    selectedAlert = alert
                                }
                        }
                    }
                }
            }
        }
        .sheet(item: $selectedAlert) { alert in
            AlertDetailSheet(alert: alert, viewModel: viewModel)
        }
    }
}

struct AlertRow: View {
    let alert: MultiLegAlert
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Image(systemName: severityIcon)
                    .foregroundColor(severityColor)
                
                Text(alert.title)
                    .font(.subheadline)
                    .fontWeight(.semibold)
                
                Spacer()
                
                Text(alert.createdAt, style: .time)
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
            
            if let reason = alert.reason {
                Text(reason)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .lineLimit(2)
            }
            
            if let action = alert.suggestedAction {
                Text(action)
                    .font(.caption)
                    .foregroundColor(.blue)
                    .lineLimit(1)
            }
        }
        .padding(8)
        .background(Color(.controlBackgroundColor))
        .cornerRadius(6)
    }
    
    private var severityIcon: String {
        switch alert.severity {
        case "critical": return "exclamationmark.circle.fill"
        case "warning": return "exclamationmark.triangle.fill"
        default: return "info.circle.fill"
        }
    }
    
    private var severityColor: Color {
        switch alert.severity {
        case "critical": return .red
        case "warning": return .orange
        default: return .blue
        }
    }
}
```

## Performance Optimization

### Query Optimization

```sql
-- Fast alert retrieval
CREATE INDEX ix_alerts_user_unresolved 
  ON options_multi_leg_alerts(strategy_id, action_required, created_at DESC);

-- Fast strategy evaluation
CREATE INDEX ix_strategies_evaluation 
  ON options_strategies(status, user_id, min_dte);
```

### Caching Strategy

- Cache option prices from `options_ranker` table (updated every 15 min)
- Cache forecast data (re-fetch only if forecast_id changed)
- Use Redis for fast alert dedup (check if similar alert exists in last hour)

## Next Steps

1. Implement alert evaluator functions in Python
2. Deploy scheduled job to Supabase Functions
3. Wire alert panel into SwiftUI strategy detail view
4. Add alert preference settings to user profile
5. Test with sample strategies and market conditions

---

## References

- [Multi-Leg Options Overview](./MULTI_LEG_OPTIONS_OVERVIEW.md)
- [Multi-Leg Data Model](./MULTI_LEG_DATA_MODEL.md)
- [P&L Calculator](./MULTI_LEG_PL_CALCULATOR.md)
