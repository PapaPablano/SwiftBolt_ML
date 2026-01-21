# Multi-Leg Options P&L Calculator

## Overview

This document defines the calculation engine for multi-leg strategy pricing, Greeks aggregation, and real-time P&L tracking. All calculations use the Black-Scholes model for theoretical pricing and Greeks.

## Core Concepts

### P&L Components

For a multi-leg strategy at any point in time:

```
Total Strategy P&L = Σ(Individual Leg P&L)

Where for each leg:
Individual Leg P&L = (Current Value - Entry Cost) × ±1
                    (±1: +1 for long legs, -1 for short legs)

Current Value = Current Price × 100 × Number of Contracts
Entry Cost = Entry Price × 100 × Number of Contracts
```

### Greeks Aggregation

Portfolio Greeks are the sum of individual leg Greeks:

```
Portfolio Delta = Σ(Leg Delta) × Position Multiplier
Portfolio Gamma = Σ(Leg Gamma) × Position Multiplier
Portfolio Theta = Σ(Leg Theta) × Position Multiplier
Portfolio Vega = Σ(Leg Vega) × Position Multiplier
Portfolio Rho = Σ(Leg Rho) × Position Multiplier

Position Multiplier = +1 for long, -1 for short
```

## P&L Calculation Engine

### Python Implementation

```python
# backend/services/pl_calculator.py

from decimal import Decimal
from datetime import datetime, date
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import math
from scipy.stats import norm

@dataclass
class PLSnapshot:
    """Current P&L state of a strategy."""
    underlying_price: Decimal
    timestamp: datetime
    
    # Totals
    total_entry_cost: Decimal        # Total debit (negative) or credit (positive)
    total_current_value: Decimal     # Sum of all leg current values
    total_unrealized_pl: Decimal     # Total P&L
    total_unrealized_pl_pct: Decimal  # P&L as % of entry cost
    
    # Per-leg breakdown
    leg_snapshots: List['LegPLSnapshot']
    
    # Greeks
    delta: Decimal
    gamma: Decimal
    theta: Decimal
    vega: Decimal
    rho: Decimal

@dataclass
class LegPLSnapshot:
    """P&L snapshot for single leg."""
    leg_id: str
    leg_number: int
    
    # Prices
    entry_price: Decimal
    current_price: Decimal
    
    # Costs
    entry_cost: Decimal              # entry_price * contracts * 100
    current_value: Decimal           # current_price * contracts * 100
    
    # P&L
    unrealized_pl: Decimal           # current_value - entry_cost (unsigned)
    unrealized_pl_signed: Decimal    # P&L with position sign applied
    unrealized_pl_pct: Decimal       # P&L %
    
    # Greeks
    delta: Decimal
    gamma: Decimal
    theta: Decimal
    vega: Decimal
    rho: Decimal
    
    # Flags
    is_itm: bool
    is_deep_itm: bool
    is_breaching_strike: bool


class MultiLegPLCalculator:
    """Calculate P&L and Greeks for multi-leg strategies."""
    
    # Risk-free rate (updated daily)
    RISK_FREE_RATE = Decimal('0.045')
    
    def __init__(self, strategy: dict, current_option_ dict):
        """
        Args:
            strategy: Strategy record with legs
            current_option_ {leg_id: {price, iv, bid, ask, delta, ...}}
        """
        self.strategy = strategy
        self.current_option_data = current_option_data
    
    def calculate_strategy_pl(self, underlying_price: Decimal) -> PLSnapshot:
        """
        Calculate total P&L and Greeks for strategy.
        
        Args:
            underlying_price: Current underlying price
        
        Returns:
            PLSnapshot with all P&L and Greeks info
        """
        timestamp = datetime.utcnow()
        leg_snapshots = []
        
        total_entry_cost = Decimal('0')
        total_current_value = Decimal('0')
        total_delta = Decimal('0')
        total_gamma = Decimal('0')
        total_theta = Decimal('0')
        total_vega = Decimal('0')
        total_rho = Decimal('0')
        
        for leg in self.strategy['legs']:
            if leg['is_closed']:
                continue
            
            leg_snapshot = self.calculate_leg_pl(
                leg=leg,
                underlying_price=underlying_price,
                current_data=self.current_option_data.get(leg['id'], {})
            )
            
            leg_snapshots.append(leg_snapshot)
            
            # Sum costs and values
            total_entry_cost += leg_snapshot.entry_cost
            total_current_value += leg_snapshot.current_value
            
            # Sum Greeks (with position sign)
            position_sign = Decimal('1') if leg['position_type'] == 'long' else Decimal('-1')
            total_delta += leg_snapshot.delta * position_sign
            total_gamma += leg_snapshot.gamma * position_sign
            total_theta += leg_snapshot.theta * position_sign
            total_vega += leg_snapshot.vega * position_sign
            total_rho += leg_snapshot.rho * position_sign
        
        # Calculate net P&L
        total_unrealized_pl = total_current_value - total_entry_cost
        total_unrealized_pl_pct = (
            total_unrealized_pl / abs(total_entry_cost)
            if total_entry_cost != 0 else Decimal('0')
        )
        
        return PLSnapshot(
            underlying_price=underlying_price,
            timestamp=timestamp,
            total_entry_cost=total_entry_cost,
            total_current_value=total_current_value,
            total_unrealized_pl=total_unrealized_pl,
            total_unrealized_pl_pct=total_unrealized_pl_pct,
            leg_snapshots=leg_snapshots,
            delta=total_delta,
            gamma=total_gamma,
            theta=total_theta,
            vega=total_vega,
            rho=total_rho
        )
    
    def calculate_leg_pl(self, leg: dict, underlying_price: Decimal,
                        current_ dict) -> LegPLSnapshot:
        """
        Calculate P&L and Greeks for single leg.
        
        Args:
            leg: Leg record
            underlying_price: Current underlying price
            current_ {price, iv, delta, gamma, theta, vega, rho, bid, ask}
        
        Returns:
            LegPLSnapshot
        """
        contracts = Decimal(leg['contracts'])
        entry_price = Decimal(str(leg['entry_price']))
        current_price = Decimal(str(current_data.get('price', 0)))
        
        # Calculate costs
        entry_cost = entry_price * contracts * Decimal('100')
        current_value = current_price * contracts * Decimal('100')
        
        # Calculate P&L (unsigned first)
        unrealized_pl = current_value - entry_cost
        unrealized_pl_pct = (
            unrealized_pl / abs(entry_cost) if entry_cost != 0 else Decimal('0')
        )
        
        # Apply position sign to get signed P&L
        position_sign = Decimal('1') if leg['position_type'] == 'long' else Decimal('-1')
        unrealized_pl_signed = unrealized_pl * position_sign
        
        # Get Greeks (already per 1 share, multiply by 100 for 1 contract)
        delta = Decimal(str(current_data.get('delta', 0))) * Decimal('100') * contracts
        gamma = Decimal(str(current_data.get('gamma', 0))) * Decimal('100') * contracts
        theta = Decimal(str(current_data.get('theta', 0))) * Decimal('100') * contracts
        vega = Decimal(str(current_data.get('vega', 0))) * Decimal('100') * contracts
        rho = Decimal(str(current_data.get('rho', 0))) * Decimal('100') * contracts
        
        # Determine ITM status
        strike = Decimal(str(leg['strike']))
        is_itm = (
            (leg['option_type'] == 'call' and underlying_price > strike) or
            (leg['option_type'] == 'put' and underlying_price < strike)
        )
        
        is_deep_itm = (
            (leg['option_type'] == 'call' and underlying_price > strike + Decimal('2')) or
            (leg['option_type'] == 'put' and underlying_price < strike - Decimal('2'))
        )
        
        # Breaching = within 0.5% of strike
        breach_threshold = abs(strike) * Decimal('0.005')
        is_breaching_strike = abs(underlying_price - strike) <= breach_threshold
        
        return LegPLSnapshot(
            leg_id=leg['id'],
            leg_number=leg['leg_number'],
            entry_price=entry_price,
            current_price=current_price,
            entry_cost=entry_cost,
            current_value=current_value,
            unrealized_pl=unrealized_pl,
            unrealized_pl_signed=unrealized_pl_signed,
            unrealized_pl_pct=unrealized_pl_pct,
            delta=delta,
            gamma=gamma,
            theta=theta,
            vega=vega,
            rho=rho,
            is_itm=is_itm,
            is_deep_itm=is_deep_itm,
            is_breaching_strike=is_breaching_strike
        )
    
    def calculate_max_risk_reward(self) -> Tuple[Decimal, Decimal, List[Decimal]]:
        """
        Calculate max risk, max reward, and breakeven points for strategy.
        
        This uses the strategy type to determine the payoff structure.
        
        Returns:
            (max_risk, max_reward, [breakeven_prices])
        """
        strategy_type = self.strategy['strategy_type']
        
        # Get sorted strikes
        strikes = sorted([
            Decimal(str(leg['strike'])) for leg in self.strategy['legs']
        ])
        
        # Calculate based on strategy type
        if strategy_type == 'bull_call_spread':
            return self._calc_bull_call_spread()
        elif strategy_type == 'bear_call_spread':
            return self._calc_bear_call_spread()
        elif strategy_type == 'bull_put_spread':
            return self._calc_bull_put_spread()
        elif strategy_type == 'bear_put_spread':
            return self._calc_bear_put_spread()
        elif strategy_type == 'long_straddle':
            return self._calc_long_straddle()
        elif strategy_type == 'short_straddle':
            return self._calc_short_straddle()
        elif strategy_type == 'iron_condor':
            return self._calc_iron_condor()
        else:
            return Decimal('0'), Decimal('0'), []
    
    def _calc_bull_call_spread(self) -> Tuple[Decimal, Decimal, List[Decimal]]:
        """
        Bull Call Spread = Long Call at K1 + Short Call at K2 (K2 > K1)
        
        Max Loss = Net Debit = K1_premium - K2_premium
        Max Gain = Width - Net Debit = (K2 - K1) - (K1_premium - K2_premium)
        Breakeven = K1 + Net Debit
        """
        long_leg = next(l for l in self.strategy['legs'] if l['position_type'] == 'long')
        short_leg = next(l for l in self.strategy['legs'] if l['position_type'] == 'short')
        
        k1 = Decimal(str(long_leg['strike']))
        k2 = Decimal(str(short_leg['strike']))
        p1 = Decimal(str(long_leg['entry_price']))
        p2 = Decimal(str(short_leg['entry_price']))
        
        net_debit = (p1 - p2) * Decimal('100')
        width = (k2 - k1) * Decimal('100')
        
        max_loss = net_debit
        max_reward = width - net_debit
        breakeven = k1 + (net_debit / Decimal('100'))
        
        return max_loss, max_reward, [breakeven]
    
    def _calc_bear_call_spread(self) -> Tuple[Decimal, Decimal, List[Decimal]]:
        """
        Bear Call Spread = Short Call at K1 + Long Call at K2 (K2 > K1)
        
        Max Profit = Net Credit = K1_premium - K2_premium
        Max Loss = Width - Net Credit = (K2 - K1) - (K1_premium - K2_premium)
        Breakeven = K1 + Net Credit
        """
        short_leg = next(l for l in self.strategy['legs'] if l['position_type'] == 'short')
        long_leg = next(l for l in self.strategy['legs'] if l['position_type'] == 'long')
        
        k1 = Decimal(str(short_leg['strike']))
        k2 = Decimal(str(long_leg['strike']))
        p1 = Decimal(str(short_leg['entry_price']))
        p2 = Decimal(str(long_leg['entry_price']))
        
        net_credit = (p1 - p2) * Decimal('100')
        width = (k2 - k1) * Decimal('100')
        
        max_reward = net_credit
        max_loss = width - net_credit
        breakeven = k1 + (net_credit / Decimal('100'))
        
        return max_loss, max_reward, [breakeven]
    
    def _calc_bull_put_spread(self) -> Tuple[Decimal, Decimal, List[Decimal]]:
        """
        Bull Put Spread = Short Put at K2 + Long Put at K1 (K1 < K2)
        
        Max Profit = Net Credit
        Max Loss = Width - Net Credit
        Breakeven = K2 - Net Credit
        """
        short_leg = next(l for l in self.strategy['legs'] if l['position_type'] == 'short')
        long_leg = next(l for l in self.strategy['legs'] if l['position_type'] == 'long')
        
        k2 = Decimal(str(short_leg['strike']))  # Higher strike
        k1 = Decimal(str(long_leg['strike']))   # Lower strike
        p2 = Decimal(str(short_leg['entry_price']))
        p1 = Decimal(str(long_leg['entry_price']))
        
        net_credit = (p2 - p1) * Decimal('100')
        width = (k2 - k1) * Decimal('100')
        
        max_reward = net_credit
        max_loss = width - net_credit
        breakeven = k2 - (net_credit / Decimal('100'))
        
        return max_loss, max_reward, [breakeven]
    
    def _calc_bear_put_spread(self) -> Tuple[Decimal, Decimal, List[Decimal]]:
        """
        Bear Put Spread = Long Put at K1 + Short Put at K2 (K2 > K1)
        
        Max Loss = Net Debit
        Max Profit = Width - Net Debit
        Breakeven = K2 - Width + Net Debit
        """
        long_leg = next(l for l in self.strategy['legs'] if l['position_type'] == 'long')
        short_leg = next(l for l in self.strategy['legs'] if l['position_type'] == 'short')
        
        k1 = Decimal(str(long_leg['strike']))
        k2 = Decimal(str(short_leg['strike']))
        p1 = Decimal(str(long_leg['entry_price']))
        p2 = Decimal(str(short_leg['entry_price']))
        
        net_debit = (p1 - p2) * Decimal('100')
        width = (k2 - k1) * Decimal('100')
        
        max_loss = net_debit
        max_reward = width - net_debit
        breakeven = k2 - (width - net_debit) / Decimal('100')
        
        return max_loss, max_reward, [breakeven]
    
    def _calc_long_straddle(self) -> Tuple[Decimal, Decimal, List[Decimal]]:
        """
        Long Straddle = Long Call + Long Put (same strike K)
        
        Max Loss = Total Premium Paid
        Max Gain = Unlimited
        Breakevens = K + Premium, K - Premium
        """
        strike = Decimal(str(self.strategy['legs'][0]['strike']))
        total_premium = sum(
            Decimal(str(l['entry_price'])) for l in self.strategy['legs']
        ) * Decimal('100')
        
        max_loss = total_premium
        max_reward = Decimal('999999999')  # Unlimited upside
        be_up = strike + (total_premium / Decimal('100'))
        be_down = strike - (total_premium / Decimal('100'))
        
        return max_loss, max_reward, [be_down, be_up]
    
    def _calc_short_straddle(self) -> Tuple[Decimal, Decimal, List[Decimal]]:
        """
        Short Straddle = Short Call + Short Put (same strike K)
        
        Max Gain = Total Premium Collected
        Max Loss = Unlimited
        Breakevens = K + Premium, K - Premium
        """
        strike = Decimal(str(self.strategy['legs'][0]['strike']))
        total_premium = sum(
            Decimal(str(l['entry_price'])) for l in self.strategy['legs']
        ) * Decimal('100')
        
        max_reward = total_premium
        max_loss = Decimal('999999999')  # Unlimited downside
        be_up = strike + (total_premium / Decimal('100'))
        be_down = strike - (total_premium / Decimal('100'))
        
        return max_loss, max_reward, [be_down, be_up]
    
    def _calc_iron_condor(self) -> Tuple[Decimal, Decimal, List[Decimal]]:
        """
        Iron Condor = Bull Call Spread + Bull Put Spread
        
        Max Profit = Net Credit
        Max Loss = Width of one spread - Net Credit
        Breakevens = Short strikes ± Net Credit
        """
        # Get all strikes (should be 4)
        strikes = sorted([Decimal(str(l['strike'])) for l in self.strategy['legs']])
        
        # Calculate total credit
        total_credit = sum(
            Decimal(str(l['entry_price'])) if l['position_type'] == 'short' else 0
            for l in self.strategy['legs']
        ) - sum(
            Decimal(str(l['entry_price'])) if l['position_type'] == 'long' else 0
            for l in self.strategy['legs']
        )
        total_credit *= Decimal('100')
        
        # Spread width (typically same for both spreads)
        spread_width = (strikes[1] - strikes[0]) * Decimal('100')
        
        max_reward = total_credit
        max_loss = spread_width - total_credit
        
        # Breakevens at short strikes
        short_call_strike = strikes[2]  # Or strikes[3]
        short_put_strike = strikes[1]   # Or strikes[0]
        
        be_up = short_call_strike + (total_credit / Decimal('100'))
        be_down = short_put_strike - (total_credit / Decimal('100'))
        
        return max_loss, max_reward, [be_down, be_up]


# Greek calculation helpers (using Black-Scholes)

def calculate_black_scholes_option(
    spot: Decimal,
    strike: Decimal,
    time_to_expiry: Decimal,  # in years
    volatility: Decimal,
    risk_free_rate: Decimal,
    option_type: str,  # 'call' or 'put'
    dividend_yield: Decimal = Decimal('0')
) -> Dict[str, Decimal]:
    """
    Calculate option price and Greeks using Black-Scholes.
    
    Returns dict with: price, delta, gamma, theta, vega, rho
    """
    # Convert to float for scipy
    S = float(spot)
    K = float(strike)
    T = float(time_to_expiry)
    sigma = float(volatility)
    r = float(risk_free_rate)
    q = float(dividend_yield)
    
    if T <= 0:
        # Option at/near expiration
        intrinsic = max(S - K, 0) if option_type == 'call' else max(K - S, 0)
        return {
            'price': Decimal(str(intrinsic)),
            'delta': Decimal('1') if option_type == 'call' and S > K else Decimal('0'),
            'gamma': Decimal('0'),
            'theta': Decimal('0'),
            'vega': Decimal('0'),
            'rho': Decimal('0')
        }
    
    # Black-Scholes formula
    d1 = (math.log(S / K) + (r - q + sigma**2 / 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    
    Nd1 = norm.cdf(d1)
    Nd2 = norm.cdf(d2)
    nd1 = norm.pdf(d1)  # Standard normal PDF
    
    if option_type == 'call':
        price = S * math.exp(-q * T) * Nd1 - K * math.exp(-r * T) * Nd2
        delta = math.exp(-q * T) * Nd1
    else:  # put
        price = K * math.exp(-r * T) * norm.cdf(-d2) - S * math.exp(-q * T) * norm.cdf(-d1)
        delta = math.exp(-q * T) * (Nd1 - 1)
    
    gamma = math.exp(-q * T) * nd1 / (S * sigma * math.sqrt(T))
    
    if option_type == 'call':
        theta = (-S * math.exp(-q * T) * nd1 * sigma / (2 * math.sqrt(T)) -
                r * K * math.exp(-r * T) * Nd2 +
                q * S * math.exp(-q * T) * Nd1) / 365
    else:
        theta = (-S * math.exp(-q * T) * nd1 * sigma / (2 * math.sqrt(T)) +
                r * K * math.exp(-r * T) * norm.cdf(-d2) -
                q * S * math.exp(-q * T) * norm.cdf(-d1)) / 365
    
    vega = S * math.exp(-q * T) * nd1 * math.sqrt(T) / 100  # Per 1% IV change
    
    if option_type == 'call':
        rho = K * T * math.exp(-r * T) * Nd2 / 100
    else:
        rho = -K * T * math.exp(-r * T) * norm.cdf(-d2) / 100
    
    return {
        'price': Decimal(str(price)),
        'delta': Decimal(str(delta)),
        'gamma': Decimal(str(gamma)),
        'theta': Decimal(str(theta)),
        'vega': Decimal(str(vega)),
        'rho': Decimal(str(rho))
    }
```

## Swift Implementation

```swift
// client-macos/SwiftBoltML/Services/MultiLegPLService.swift

import Foundation

class MultiLegPLService {
    
    /// Calculate P&L snapshot for strategy
    static func calculateStrategyPL(
        strategy: MultiLegStrategy,
        underlyingPrice: Decimal,
        optionPrices: [UUID: OptionPriceData]
    ) -> StrategyPLSnapshot {
        
        var legSnapshots: [LegPLSnapshot] = []
        var totalEntryDollars = Decimal('0')
        var totalCurrentValue = Decimal('0')
        var totalDelta = Decimal('0')
        var totalTheta = Decimal('0')
        
        for leg in strategy.legs where !leg.isClosed {
            let currentData = optionPrices[leg.id]
            let legSnapshot = calculateLegPL(
                leg: leg,
                underlyingPrice: underlyingPrice,
                currentPrice: currentData?.price ?? leg.currentPrice ?? 0,
                delta: currentData?.delta ?? leg.currentDelta ?? 0,
                theta: currentData?.theta ?? leg.currentTheta ?? 0
            )
            
            legSnapshots.append(legSnapshot)
            
            totalEntryDollars += legSnapshot.entryCost
            totalCurrentValue += legSnapshot.currentValue
            
            // Apply position sign
            let positionMultiplier: Decimal = leg.positionType == .long ? 1 : -1
            totalDelta += (legSnapshot.delta ?? 0) * positionMultiplier
            totalTheta += (legSnapshot.theta ?? 0) * positionMultiplier
        }
        
        let totalPL = totalCurrentValue - totalEntryDollars
        let totalPLPct = totalEntryDollars != 0 
            ? (totalPL / abs(totalEntryDollars)) * 100 
            : 0
        
        return StrategyPLSnapshot(
            underlyingPrice: underlyingPrice,
            totalEntryDollars: totalEntryDollars,
            totalCurrentValue: totalCurrentValue,
            totalPL: totalPL,
            totalPLPct: totalPLPct,
            legSnapshots: legSnapshots,
            delta: totalDelta,
            theta: totalTheta
        )
    }
    
    static func calculateLegPL(
        leg: OptionsLeg,
        underlyingPrice: Decimal,
        currentPrice: Decimal,
        delta: Decimal?,
        theta: Decimal?
    ) -> LegPLSnapshot {
        
        let contracts = Decimal(leg.contracts)
        let entryCost = leg.entryPrice * contracts * 100
        let currentValue = currentPrice * contracts * 100
        
        let unrealizedPL = currentValue - entryCost
        let unrealizedPLPct = entryCost != 0 ? unrealizedPL / abs(entryCost) else 0
        
        let isITM = (
            (leg.optionType == .call && underlyingPrice > leg.strike) ||
            (leg.optionType == .put && underlyingPrice < leg.strike)
        )
        
        return LegPLSnapshot(
            legNumber: leg.legNumber,
            entryPrice: leg.entryPrice,
            currentPrice: currentPrice,
            entryCost: entryCost,
            currentValue: currentValue,
            unrealizedPL: unrealizedPL,
            unrealizedPLPct: unrealizedPLPct,
            delta: delta,
            theta: theta,
            isITM: isITM
        )
    }
}

struct StrategyPLSnapshot {
    let underlyingPrice: Decimal
    let totalEntryDollars: Decimal
    let totalCurrentValue: Decimal
    let totalPL: Decimal
    let totalPLPct: Decimal
    let legSnapshots: [LegPLSnapshot]
    let delta: Decimal
    let theta: Decimal
}

struct LegPLSnapshot {
    let legNumber: Int
    let entryPrice: Decimal
    let currentPrice: Decimal
    let entryCost: Decimal
    let currentValue: Decimal
    let unrealizedPL: Decimal
    let unrealizedPLPct: Decimal
    let delta: Decimal?
    let theta: Decimal?
    let isITM: Bool
}
```

## Real-Time Updates

P&L is updated whenever:

1. **New option price received** → Update via WebSocket from `options_ranker`
2. **Daily metrics recorded** → Snapshot stored to database
3. **Strategy viewed** → Recalculate from latest ranker data

## Performance Optimization

- **Lazy calculation**: Only calculate Greeks when requested (not every update)
- **Cache current prices**: Use `options_ranker` table, updated every 15 min
- **Batch calculations**: Process all strategies in one job, not individually

## Next Steps

1. Implement P&L calculator in backend
2. Create edge functions for on-demand P&L calculation
3. Wire Swift service to strategy detail views
4. Add P&L chart visualization
5. Test with real market data

---

## References

- [Multi-Leg Options Overview](./MULTI_LEG_OPTIONS_OVERVIEW.md)
- [Multi-Leg Data Model](./MULTI_LEG_DATA_MODEL.md)
- [Alert System](./MULTI_LEG_ALERT_SYSTEM.md)
