# Addendum: Options Trading System Analysis
**Date**: January 22, 2026  
**Added After**: Comprehensive System Audit  
**Trigger**: New Options Trading Strategies skill added

---

## Executive Summary

After reviewing the **Options Trading Strategies skill**, I've identified **critical gaps** in the options trading system that weren't fully covered in the original audit. The skill reveals industry best practices that should be implemented.

### New Critical Findings

🔴 **Critical Gaps Identified:**
1. **No Black-Scholes Pricing Model** - Core options pricing missing
2. **No Backtesting Infrastructure** - Can't validate strategy performance
3. **No Payoff Visualization** - Missing critical analysis tools
4. **Limited Risk Management** - Greeks monitoring not automated
5. **No Volatility Analysis** - IV rank/percentile calculations missing

---

## Detailed Analysis

### 1. 🔴 Critical: Missing Black-Scholes Pricing Model

**Finding**: The system calculates Greeks (delta, gamma, theta, vega) but doesn't appear to have Black-Scholes pricing implementation.

**From Options Skill**:
```python
# Expected implementation
def black_scholes_call(S, K, T, r, sigma):
    """Calculate call option price using Black-Scholes."""
    d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
    d2 = d1 - sigma*np.sqrt(T)
    
    call_price = S * norm.cdf(d1) - K * np.exp(-r*T) * norm.cdf(d2)
    return call_price

def calculate_greeks(S, K, T, r, sigma):
    """Calculate all Greeks analytically."""
    d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
    d2 = d1 - sigma*np.sqrt(T)
    
    delta = norm.cdf(d1)
    gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
    theta = (-S * norm.pdf(d1) * sigma / (2*np.sqrt(T)) 
             - r * K * np.exp(-r*T) * norm.cdf(d2))
    vega = S * norm.pdf(d1) * np.sqrt(T)
    
    return delta, gamma, theta, vega
```

**Current System**: 
- Uses Greeks from API data (`options_snapshots.delta`, `.gamma`, etc.)
- No independent pricing validation
- Can't calculate theoretical prices for backtesting

**Risk**: 
- Dependent on external data quality
- Can't validate if options are mispriced
- Can't backtest with historical data (no theoretical prices)

**Recommendation**: Add Options Pricing Module

```python
# ml/src/models/options_pricing.py
"""Black-Scholes options pricing and Greeks calculation."""

import numpy as np
from scipy.stats import norm
from dataclasses import dataclass
from typing import Optional

@dataclass
class OptionsPricing:
    """Black-Scholes pricing results."""
    theoretical_price: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    implied_vol: Optional[float] = None

class BlackScholesModel:
    """Black-Scholes options pricing model."""
    
    def __init__(self, risk_free_rate: float = 0.05):
        self.risk_free_rate = risk_free_rate
    
    def price_call(self, S: float, K: float, T: float, sigma: float) -> float:
        """Calculate European call option price."""
        if T <= 0:
            return max(S - K, 0)
        
        d1 = (np.log(S/K) + (self.risk_free_rate + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
        d2 = d1 - sigma*np.sqrt(T)
        
        call_price = S * norm.cdf(d1) - K * np.exp(-self.risk_free_rate*T) * norm.cdf(d2)
        return call_price
    
    def price_put(self, S: float, K: float, T: float, sigma: float) -> float:
        """Calculate European put option price."""
        if T <= 0:
            return max(K - S, 0)
        
        d1 = (np.log(S/K) + (self.risk_free_rate + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
        d2 = d1 - sigma*np.sqrt(T)
        
        put_price = K * np.exp(-self.risk_free_rate*T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        return put_price
    
    def calculate_greeks(
        self, 
        S: float, 
        K: float, 
        T: float, 
        sigma: float, 
        option_type: str = 'call'
    ) -> OptionsPricing:
        """Calculate option price and all Greeks."""
        if T <= 0:
            # At expiration
            if option_type == 'call':
                price = max(S - K, 0)
                delta = 1.0 if S > K else 0.0
            else:
                price = max(K - S, 0)
                delta = -1.0 if S < K else 0.0
            
            return OptionsPricing(
                theoretical_price=price,
                delta=delta,
                gamma=0.0,
                theta=0.0,
                vega=0.0,
                rho=0.0
            )
        
        # Calculate d1, d2
        d1 = (np.log(S/K) + (self.risk_free_rate + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
        d2 = d1 - sigma*np.sqrt(T)
        
        # Price
        if option_type == 'call':
            price = self.price_call(S, K, T, sigma)
            delta = norm.cdf(d1)
        else:
            price = self.price_put(S, K, T, sigma)
            delta = -norm.cdf(-d1)
        
        # Greeks (same for calls and puts)
        gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
        vega = S * norm.pdf(d1) * np.sqrt(T) / 100  # Per 1% change in vol
        
        if option_type == 'call':
            theta = ((-S * norm.pdf(d1) * sigma / (2*np.sqrt(T)) 
                     - self.risk_free_rate * K * np.exp(-self.risk_free_rate*T) * norm.cdf(d2)) 
                     / 365)  # Per day
            rho = K * T * np.exp(-self.risk_free_rate*T) * norm.cdf(d2) / 100
        else:
            theta = ((-S * norm.pdf(d1) * sigma / (2*np.sqrt(T)) 
                     + self.risk_free_rate * K * np.exp(-self.risk_free_rate*T) * norm.cdf(-d2)) 
                     / 365)
            rho = -K * T * np.exp(-self.risk_free_rate*T) * norm.cdf(-d2) / 100
        
        return OptionsPricing(
            theoretical_price=price,
            delta=delta,
            gamma=gamma,
            theta=theta,
            vega=vega,
            rho=rho
        )
    
    def calculate_implied_volatility(
        self, 
        market_price: float, 
        S: float, 
        K: float, 
        T: float, 
        option_type: str = 'call',
        initial_guess: float = 0.3
    ) -> float:
        """Calculate implied volatility using Newton-Raphson."""
        if T <= 0:
            return 0.0
        
        sigma = initial_guess
        max_iterations = 100
        tolerance = 1e-6
        
        for _ in range(max_iterations):
            # Calculate price and vega
            if option_type == 'call':
                price = self.price_call(S, K, T, sigma)
            else:
                price = self.price_put(S, K, T, sigma)
            
            diff = market_price - price
            
            if abs(diff) < tolerance:
                return sigma
            
            # Vega
            d1 = (np.log(S/K) + (self.risk_free_rate + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
            vega = S * norm.pdf(d1) * np.sqrt(T)
            
            if vega < 1e-10:
                break
            
            # Newton-Raphson update
            sigma += diff / vega
            
            # Bound sigma
            sigma = max(0.01, min(sigma, 5.0))
        
        return sigma
```

**Usage in Ranking System**:
```python
# Validate API Greeks against Black-Scholes
bs_model = BlackScholesModel()

for _, row in options_df.iterrows():
    theoretical = bs_model.calculate_greeks(
        S=underlying_price,
        K=row['strike'],
        T=row['days_to_expiry'] / 365,
        sigma=row['implied_volatility'],
        option_type='call' if row['side'] == 'call' else 'put'
    )
    
    # Compare API Greeks vs theoretical
    delta_diff = abs(row['delta'] - theoretical.delta)
    if delta_diff > 0.05:  # 5% tolerance
        logger.warning(f"Large delta discrepancy: API={row['delta']}, BS={theoretical.delta}")
```

**Priority**: 🔴 **HIGH** (Core functionality for options system)  
**Effort**: 8-12 hours  
**Impact**: Enables theoretical pricing, backtesting, and data validation

---

### 2. 🔴 Critical: No Options Backtesting Infrastructure

**Finding**: The options ranking system exists, but there's no way to validate its historical performance.

**From Options Skill**:
```python
class StrategyBacktester:
    """Backtest options strategies on historical data."""
    
    def run_backtest(self, strategy, start_date, end_date):
        # Fetch historical option chains
        # Simulate entries based on strategy rules
        # Track P/L, Greeks, adjustments
        # Calculate performance metrics
        pass
```

**Current System**: 
- Has `ranking_evaluations` table (forward-looking validation)
- No historical backtesting capability
- Can't validate strategy parameters before deployment

**Recommendation**: Add Backtesting Module

```python
# ml/src/backtesting/options_backtester.py
"""Options strategy backtesting framework."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict
import pandas as pd
import numpy as np

@dataclass
class BacktestTrade:
    """Single backtest trade record."""
    entry_date: datetime
    exit_date: datetime
    symbol: str
    strategy_type: str
    legs: List[Dict]  # Each leg: strike, side, contracts, entry_price, exit_price
    entry_cost: float
    exit_value: float
    pnl: float
    pnl_pct: float
    hold_days: int
    max_loss: float
    max_gain: float
    underlying_entry: float
    underlying_exit: float
    exit_reason: str  # 'profit_target', 'stop_loss', 'expiration', 'signal_flip'

@dataclass
class BacktestResults:
    """Backtest performance metrics."""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    total_pnl: float
    max_drawdown: float
    sharpe_ratio: float
    profit_factor: float
    trades: List[BacktestTrade]
    equity_curve: pd.DataFrame

class OptionsStrategyBacktester:
    """Backtest multi-leg options strategies."""
    
    def __init__(self, db, initial_capital: float = 100000):
        self.db = db
        self.initial_capital = initial_capital
        self.trades: List[BacktestTrade] = []
    
    def run_backtest(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        strategy_params: Dict,
        ranking_threshold: float = 0.65,
    ) -> BacktestResults:
        """
        Run backtest for options ranking strategy.
        
        Args:
            symbols: List of underlying symbols to trade
            start_date: Backtest start date
            end_date: Backtest end date
            strategy_params: Strategy configuration
            ranking_threshold: Minimum ML score to enter trade
        
        Returns:
            BacktestResults with performance metrics
        """
        current_date = start_date
        capital = self.initial_capital
        equity_curve = []
        
        logger.info(f"Starting backtest: {start_date} to {end_date}")
        
        while current_date <= end_date:
            # Get options data for this date
            options_data = self._fetch_historical_options(symbols, current_date)
            
            if options_data.empty:
                current_date += timedelta(days=1)
                continue
            
            # Run ranking system on historical data
            from src.models.options_momentum_ranker import OptionsMomentumRanker
            ranker = OptionsMomentumRanker()
            
            for symbol in symbols:
                symbol_options = options_data[options_data['underlying'] == symbol]
                if symbol_options.empty:
                    continue
                
                # Get underlying price
                underlying_price = symbol_options['underlying_price'].iloc[0]
                
                # Rank options
                ranked = ranker.rank_options(
                    symbol_options,
                    underlying_price=underlying_price,
                    ranking_date=current_date
                )
                
                # Find trade opportunities
                top_options = ranked[ranked['composite_rank'] >= ranking_threshold].head(3)
                
                for _, option in top_options.iterrows():
                    # Simulate trade entry
                    trade = self._enter_trade(
                        option,
                        current_date,
                        capital,
                        strategy_params
                    )
                    
                    if trade:
                        self.trades.append(trade)
            
            # Check open positions for exits
            self._check_exit_conditions(current_date)
            
            # Update equity curve
            current_value = capital + sum(t.pnl for t in self.trades if t.exit_date is not None)
            equity_curve.append({
                'date': current_date,
                'equity': current_value
            })
            
            current_date += timedelta(days=1)
        
        # Calculate performance metrics
        results = self._calculate_metrics(equity_curve)
        
        logger.info(f"Backtest complete: {results.total_trades} trades, "
                   f"{results.win_rate:.1%} win rate, "
                   f"${results.total_pnl:,.2f} total P/L")
        
        return results
    
    def _fetch_historical_options(
        self,
        symbols: List[str],
        date: datetime
    ) -> pd.DataFrame:
        """Fetch historical options data from database."""
        # Query options_price_history table
        query = """
        SELECT 
            oh.underlying_symbol,
            oh.strike,
            oh.expiry,
            oh.side,
            oh.bid,
            oh.ask,
            oh.last,
            oh.volume,
            oh.open_interest,
            oh.implied_vol,
            oh.delta,
            oh.gamma,
            oh.theta,
            oh.vega,
            s.close as underlying_price
        FROM options_price_history oh
        JOIN symbols sym ON sym.ticker = oh.underlying_symbol
        JOIN ohlc_bars_v2 s ON s.symbol_id = sym.id 
            AND s.timeframe = 'd1' 
            AND DATE(s.ts) = DATE(%s)
        WHERE oh.recorded_at::date = %s
          AND oh.underlying_symbol = ANY(%s)
        """
        
        df = pd.read_sql(query, self.db.engine, params=(date, date, symbols))
        return df
    
    def _calculate_metrics(self, equity_curve: List[Dict]) -> BacktestResults:
        """Calculate backtest performance metrics."""
        winning = [t for t in self.trades if t.pnl > 0]
        losing = [t for t in self.trades if t.pnl < 0]
        
        # Basic metrics
        total_trades = len(self.trades)
        winning_trades = len(winning)
        losing_trades = len(losing)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        avg_win = np.mean([t.pnl for t in winning]) if winning else 0
        avg_loss = np.mean([t.pnl for t in losing]) if losing else 0
        total_pnl = sum(t.pnl for t in self.trades)
        
        # Risk metrics
        equity_df = pd.DataFrame(equity_curve)
        returns = equity_df['equity'].pct_change().dropna()
        
        sharpe_ratio = (
            returns.mean() / returns.std() * np.sqrt(252) 
            if len(returns) > 1 and returns.std() > 0 
            else 0
        )
        
        # Maximum drawdown
        cummax = equity_df['equity'].cummax()
        drawdown = (equity_df['equity'] - cummax) / cummax
        max_drawdown = drawdown.min()
        
        # Profit factor
        gross_profit = sum(t.pnl for t in winning)
        gross_loss = abs(sum(t.pnl for t in losing))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        return BacktestResults(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            total_pnl=total_pnl,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            profit_factor=profit_factor,
            trades=self.trades,
            equity_curve=equity_df
        )

# Usage
backtester = OptionsStrategyBacktester(db)

results = backtester.run_backtest(
    symbols=['SPY', 'AAPL', 'NVDA'],
    start_date=datetime(2023, 1, 1),
    end_date=datetime(2024, 12, 31),
    strategy_params={
        'max_dte': 45,
        'min_delta': 0.40,
        'max_delta': 0.70,
        'min_volume': 100,
        'max_position_size': 5  # contracts
    },
    ranking_threshold=0.65
)

print(f"Win Rate: {results.win_rate:.1%}")
print(f"Sharpe Ratio: {results.sharpe_ratio:.2f}")
print(f"Max Drawdown: {results.max_drawdown:.1%}")
```

**Priority**: 🔴 **HIGH**  
**Effort**: 16-24 hours  
**Impact**: Validates strategy before deployment, optimizes parameters

---

### 3. 🟡 High: Missing Payoff Visualization Tools

**Finding**: No tools to visualize strategy payoffs (critical for options analysis).

**From Options Skill**:
```python
def plot_straddle_payoff(strike, call_premium, put_premium):
    """Visualize long straddle P/L at expiration."""
    prices = np.linspace(strike * 0.7, strike * 1.3, 100)
    payoffs = []
    
    for price in prices:
        call_payoff = max(price - strike, 0) - call_premium
        put_payoff = max(strike - price, 0) - put_premium
        total = call_payoff + put_payoff
        payoffs.append(total)
    
    plt.plot(prices, payoffs)
    plt.axhline(y=0, color='r', linestyle='--')
    plt.show()
```

**Recommendation**: Add to dashboard or ML pipeline

```python
# ml/src/visualization/options_payoff.py
"""Options strategy payoff visualization."""

import matplotlib.pyplot as plt
import numpy as np
from typing import List, Dict

class PayoffDiagram:
    """Generate payoff diagrams for options strategies."""
    
    @staticmethod
    def plot_multi_leg_strategy(
        strategy: Dict,
        underlying_price: float,
        price_range_pct: float = 0.3
    ):
        """
        Plot payoff diagram for multi-leg strategy.
        
        Args:
            strategy: Dict with 'legs' list, each leg has strike, side, position, premium
            underlying_price: Current underlying price
            price_range_pct: Price range to plot (30% = +/- 30%)
        """
        # Generate price range
        min_price = underlying_price * (1 - price_range_pct)
        max_price = underlying_price * (1 + price_range_pct)
        prices = np.linspace(min_price, max_price, 200)
        
        # Calculate payoff at each price
        payoffs = []
        for price in prices:
            total_payoff = 0
            for leg in strategy['legs']:
                leg_payoff = PayoffDiagram._calculate_leg_payoff(
                    price,
                    leg['strike'],
                    leg['side'],
                    leg['position'],  # 'long' or 'short'
                    leg['premium']
                )
                total_payoff += leg_payoff
            payoffs.append(total_payoff)
        
        # Plot
        fig, ax = plt.subplots(figsize=(12, 8))
        ax.plot(prices, payoffs, linewidth=2, label='Total P/L')
        ax.axhline(y=0, color='black', linestyle='--', alpha=0.5)
        ax.axvline(x=underlying_price, color='blue', linestyle='--', 
                  alpha=0.5, label=f'Current Price: ${underlying_price:.2f}')
        
        # Mark breakeven points
        breakevens = PayoffDiagram._find_breakevens(prices, payoffs)
        for be in breakevens:
            ax.axvline(x=be, color='green', linestyle=':', alpha=0.7)
            ax.text(be, max(payoffs)*0.9, f'BE: ${be:.2f}', 
                   rotation=90, va='bottom')
        
        # Mark max profit/loss
        max_profit = max(payoffs)
        max_loss = min(payoffs)
        ax.axhline(y=max_profit, color='green', linestyle=':', alpha=0.5, 
                  label=f'Max Profit: ${max_profit:.2f}')
        if max_loss < 0:
            ax.axhline(y=max_loss, color='red', linestyle=':', alpha=0.5, 
                      label=f'Max Loss: ${abs(max_loss):.2f}')
        
        ax.set_xlabel('Underlying Price at Expiration', fontsize=12)
        ax.set_ylabel('Profit/Loss ($)', fontsize=12)
        ax.set_title(f"{strategy['name']} - Payoff Diagram", fontsize=14, fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        return fig
    
    @staticmethod
    def _calculate_leg_payoff(price, strike, side, position, premium):
        """Calculate single leg payoff at expiration."""
        if side == 'call':
            intrinsic = max(price - strike, 0)
        else:  # put
            intrinsic = max(strike - price, 0)
        
        if position == 'long':
            return (intrinsic - premium) * 100  # Per contract
        else:  # short
            return (premium - intrinsic) * 100
    
    @staticmethod
    def _find_breakevens(prices, payoffs):
        """Find breakeven points where payoff crosses zero."""
        breakevens = []
        for i in range(len(payoffs) - 1):
            if (payoffs[i] < 0 and payoffs[i+1] >= 0) or \
               (payoffs[i] >= 0 and payoffs[i+1] < 0):
                # Linear interpolation for exact breakeven
                be = prices[i] + (prices[i+1] - prices[i]) * \
                     (-payoffs[i] / (payoffs[i+1] - payoffs[i]))
                breakevens.append(be)
        return breakevens
```

**Priority**: 🟡 **MEDIUM**  
**Effort**: 6-8 hours  
**Impact**: Better strategy analysis and risk visualization

---

### 4. 🟡 High: Volatility Analysis Missing

**Finding**: The system uses implied volatility but doesn't calculate IV rank/percentile or historical volatility.

**From Options Skill**:
```python
# Calculate historical volatility (20-day/30-day)
# Analyze IV percentile/rank
# Identify IV expansion/compression
# Calculate expected move = Stock Price × IV × √(DTE/365)
```

**Recommendation**: Add Volatility Analysis Module

```python
# ml/src/features/volatility_analysis.py
"""Volatility analysis for options trading."""

import pandas as pd
import numpy as np

class VolatilityAnalyzer:
    """Analyze historical and implied volatility."""
    
    @staticmethod
    def calculate_historical_volatility(
        prices: pd.Series,
        window: int = 20
    ) -> float:
        """Calculate annualized historical volatility."""
        returns = np.log(prices / prices.shift(1)).dropna()
        return returns.std() * np.sqrt(252)
    
    @staticmethod
    def calculate_iv_rank(
        current_iv: float,
        iv_history: pd.Series,
        lookback_days: int = 252
    ) -> float:
        """
        Calculate IV rank (percentile of current IV in historical range).
        
        IV Rank = (Current IV - Min IV) / (Max IV - Min IV) × 100
        
        Returns: 0-100 (0 = lowest IV in period, 100 = highest)
        """
        recent_iv = iv_history.tail(lookback_days)
        min_iv = recent_iv.min()
        max_iv = recent_iv.max()
        
        if max_iv == min_iv:
            return 50.0
        
        iv_rank = (current_iv - min_iv) / (max_iv - min_iv) * 100
        return iv_rank
    
    @staticmethod
    def calculate_iv_percentile(
        current_iv: float,
        iv_history: pd.Series,
        lookback_days: int = 252
    ) -> float:
        """
        Calculate IV percentile (what % of days had lower IV).
        
        Returns: 0-100 (e.g., 80 = current IV higher than 80% of days)
        """
        recent_iv = iv_history.tail(lookback_days)
        percentile = (recent_iv < current_iv).sum() / len(recent_iv) * 100
        return percentile
    
    @staticmethod
    def calculate_expected_move(
        stock_price: float,
        implied_vol: float,
        days_to_expiration: int
    ) -> Dict[str, float]:
        """
        Calculate expected move based on implied volatility.
        
        Formula: Expected Move = Stock Price × IV × √(DTE/365)
        
        Returns: Dict with expected_move, upper_range, lower_range
        """
        time_factor = np.sqrt(days_to_expiration / 365)
        expected_move = stock_price * implied_vol * time_factor
        
        return {
            'expected_move': expected_move,
            'expected_move_pct': (expected_move / stock_price) * 100,
            'upper_range': stock_price + expected_move,
            'lower_range': stock_price - expected_move,
            'upper_2sd': stock_price + (2 * expected_move),
            'lower_2sd': stock_price - (2 * expected_move)
        }
    
    @staticmethod
    def identify_vol_regime(
        current_iv: float,
        iv_rank: float,
        iv_percentile: float
    ) -> str:
        """
        Classify volatility regime.
        
        Returns: 'low', 'normal', 'elevated', 'high'
        """
        if iv_percentile < 25:
            return 'low'
        elif iv_percentile < 50:
            return 'normal'
        elif iv_percentile < 75:
            return 'elevated'
        else:
            return 'high'
```

**Integration with Ranking System**:
```python
# Add to options_momentum_ranker.py
vol_analyzer = VolatilityAnalyzer()

# Calculate for each underlying
iv_rank = vol_analyzer.calculate_iv_rank(
    current_iv=option['implied_volatility'],
    iv_history=historical_iv_series
)

# Adjust scoring based on IV regime
if vol_analyzer.identify_vol_regime(current_iv, iv_rank, iv_percentile) == 'high':
    # Favor premium selling strategies
    premium_selling_multiplier = 1.2
else:
    # Favor premium buying strategies
    premium_buying_multiplier = 1.2
```

**Priority**: 🟡 **MEDIUM**  
**Effort**: 4-6 hours  
**Impact**: Better strategy selection based on volatility regime

---

## Updated Priority Recommendations

### Revised Phase 1 (Weeks 1-2) - NOW INCLUDES OPTIONS

**Original Priority 1 (from audit):**
1. Fix CORS security (2-3 hrs)
2. Implement CI/CD testing (8-12 hrs)
3. Fix N+1 query (2-3 hrs)

**ADDED - Options Critical Items:**
4. **Implement Black-Scholes Pricing** (8-12 hrs) 🔴 **NEW**
5. **Add Volatility Analysis** (4-6 hrs) 🟡 **NEW**

**New Week 1-2 Total**: 24-36 hours

---

### Revised Phase 2 (Weeks 3-4) - OPTIONS BACKTESTING

**Original Priority 2:**
1. W&B integration (10-16 hrs)
2. Structured logging (6-8 hrs)
3. Add SQL indexes (2-4 hrs)

**ADDED - Options Testing:**
4. **Options Backtesting Framework** (16-24 hrs) 🔴 **NEW**
5. **Payoff Visualization Tools** (6-8 hrs) 🟡 **NEW**

**New Week 3-4 Total**: 40-60 hours

---

## Options-Specific Metrics to Track

### Current State (Estimated)
- **Black-Scholes Pricing**: ❌ Not implemented
- **Backtesting**: ❌ None (forward-looking validation only)
- **Payoff Visualization**: ❌ None
- **Volatility Analysis**: 🟡 Basic (uses API IV only)
- **Greeks Validation**: 🟡 Trusts API data (no validation)
- **Risk Controls**: 🟡 Database-level only (no runtime checks)

### Target State
- **Black-Scholes Pricing**: ✅ Implemented with full Greeks
- **Backtesting**: ✅ 2+ years historical validation
- **Payoff Visualization**: ✅ All strategy types covered
- **Volatility Analysis**: ✅ IV rank, percentile, expected move
- **Greeks Validation**: ✅ Compare API vs theoretical (alert on >5% diff)
- **Risk Controls**: ✅ Automated Greeks monitoring and alerts

---

## Conclusion

The **Options Trading Strategies skill** revealed critical gaps in the options system:

1. **🔴 Missing Core Pricing Model** - Black-Scholes implementation needed
2. **🔴 No Backtesting** - Can't validate strategy performance
3. **🟡 Limited Volatility Analysis** - Need IV rank/percentile
4. **🟡 No Visualization** - Payoff diagrams missing
5. **🟡 No Greeks Validation** - Trusting API data without verification

**Impact on Timeline**:
- Phase 1: +12-18 hours (Black-Scholes + vol analysis)
- Phase 2: +22-32 hours (Backtesting + visualization)
- **Total Added**: 34-50 hours

**Revised Total Implementation**: 144-214 hours (vs original 110-164 hours)

**ROI Remains High**: Options strategies are high-value, these additions will significantly improve reliability and performance.

---

**Recommendation**: Prioritize Black-Scholes pricing and backtesting infrastructure before deploying any options strategies to production. The current system ranks options well but lacks validation and theoretical pricing needed for institutional-grade trading.

---

## Integration with W&B (from ML Audit)

**Additional Opportunity**: Track backtesting results in W&B

```python
# Track options backtests in W&B
import wandb

run = wandb.init(project="swiftbolt-options", job_type="backtest")

# Log backtest parameters
wandb.config.update({
    "symbols": symbols,
    "ranking_threshold": 0.65,
    "start_date": start_date,
    "end_date": end_date
})

# Log results
wandb.log({
    "win_rate": results.win_rate,
    "sharpe_ratio": results.sharpe_ratio,
    "max_drawdown": results.max_drawdown,
    "total_pnl": results.total_pnl,
    "total_trades": results.total_trades
})

# Log equity curve
wandb.log({"equity_curve": wandb.plot.line_series(
    xs=results.equity_curve['date'],
    ys=[results.equity_curve['equity']],
    keys=["Equity"],
    title="Options Strategy Equity Curve"
)})
```

This allows comparing different ranking thresholds, timeframes, and strategy parameters systematically.
