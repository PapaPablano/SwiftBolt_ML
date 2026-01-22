"""Volatility Analysis for Options Trading.

Provides tools for analyzing historical and implied volatility, including:
- Historical volatility calculation
- IV rank and percentile
- Expected move calculation
- Volatility regime classification

Usage:
    from src.features.volatility_analysis import VolatilityAnalyzer
    
    analyzer = VolatilityAnalyzer()
    
    # Historical volatility
    hv = analyzer.calculate_historical_volatility(prices, window=20)
    
    # IV metrics
    iv_rank = analyzer.calculate_iv_rank(current_iv=0.30, iv_history=iv_series)
    iv_percentile = analyzer.calculate_iv_percentile(0.30, iv_series)
    
    # Expected move
    move = analyzer.calculate_expected_move(
        stock_price=100,
        implied_vol=0.25,
        days_to_expiration=30
    )
    
    # Volatility regime
    regime = analyzer.identify_vol_regime(iv_rank=75, iv_percentile=80)

References:
    - Sinclair, E. (2013). "Volatility Trading" (2nd ed.)
    - Natenberg, S. (2015). "Option Volatility and Pricing" (2nd ed.)
"""

import logging
from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class VolatilityMetrics:
    """Comprehensive volatility metrics for an underlying.
    
    Attributes:
        current_iv: Current implied volatility
        historical_vol_20d: 20-day historical volatility
        historical_vol_30d: 30-day historical volatility
        iv_rank: IV rank (0-100, position in 52-week range)
        iv_percentile: IV percentile (0-100, % of days with lower IV)
        iv_high_52w: Highest IV in past 52 weeks
        iv_low_52w: Lowest IV in past 52 weeks
        iv_median_52w: Median IV in past 52 weeks
        expected_move_1sd: Expected 1-SD move (dollars)
        expected_move_pct: Expected 1-SD move (percentage)
        vol_regime: Volatility regime classification
    """
    current_iv: float
    historical_vol_20d: float
    historical_vol_30d: float
    iv_rank: float
    iv_percentile: float
    iv_high_52w: float
    iv_low_52w: float
    iv_median_52w: float
    expected_move_1sd: float
    expected_move_pct: float
    vol_regime: str
    
    def __str__(self) -> str:
        """Human-readable representation."""
        return (
            f"VolatilityMetrics(\n"
            f"  Current IV: {self.current_iv:.2%}\n"
            f"  HV 20-day: {self.historical_vol_20d:.2%}\n"
            f"  HV 30-day: {self.historical_vol_30d:.2%}\n"
            f"  IV Rank: {self.iv_rank:.1f}\n"
            f"  IV Percentile: {self.iv_percentile:.1f}\n"
            f"  52W IV Range: {self.iv_low_52w:.2%} - {self.iv_high_52w:.2%}\n"
            f"  Expected Move: ${self.expected_move_1sd:.2f} ({self.expected_move_pct:.1%})\n"
            f"  Regime: {self.vol_regime}\n"
            f")"
        )


class VolatilityAnalyzer:
    """Analyze historical and implied volatility for options trading.
    
    Provides various volatility metrics used in options strategy selection
    and risk management.
    """
    
    @staticmethod
    def calculate_historical_volatility(
        prices: pd.Series,
        window: int = 20,
        annualization_factor: int = 252
    ) -> float:
        """Calculate annualized historical volatility.
        
        Uses log returns to compute volatility:
        σ = std(ln(P_t / P_(t-1))) × √annualization_factor
        
        Args:
            prices: Price series (typically close prices)
            window: Lookback window in days
            annualization_factor: Trading days per year (default: 252)
        
        Returns:
            Annualized historical volatility (e.g., 0.25 for 25%)
        """
        if len(prices) < window:
            logger.warning(f"Insufficient data: {len(prices)} < {window}, using all available")
            window = len(prices)
        
        # Calculate log returns
        log_returns = np.log(prices / prices.shift(1)).dropna()
        
        if len(log_returns) < 2:
            logger.warning("Insufficient returns data for volatility calculation")
            return 0.0
        
        # Use most recent window
        recent_returns = log_returns.tail(window)
        
        # Annualized volatility
        volatility = recent_returns.std() * np.sqrt(annualization_factor)
        
        return float(volatility)
    
    @staticmethod
    def calculate_iv_rank(
        current_iv: float,
        iv_history: pd.Series,
        lookback_days: int = 252
    ) -> float:
        """Calculate IV rank (position in range).
        
        IV Rank = (Current IV - Min IV) / (Max IV - Min IV) × 100
        
        Measures where current IV sits in its historical range.
        - 0 = lowest IV in period
        - 50 = midpoint
        - 100 = highest IV in period
        
        Args:
            current_iv: Current implied volatility
            iv_history: Historical IV series
            lookback_days: Days to look back (default: 252 = 1 year)
        
        Returns:
            IV rank (0-100)
        """
        if iv_history.empty:
            logger.warning("No IV history provided, returning 50 (neutral)")
            return 50.0
        
        # Use most recent period
        recent_iv = iv_history.tail(lookback_days)
        
        if len(recent_iv) < 2:
            logger.warning("Insufficient IV history, returning 50 (neutral)")
            return 50.0
        
        min_iv = recent_iv.min()
        max_iv = recent_iv.max()
        
        # Avoid division by zero
        if max_iv == min_iv:
            return 50.0
        
        # Calculate rank
        iv_rank = (current_iv - min_iv) / (max_iv - min_iv) * 100
        
        # Bound to [0, 100]
        iv_rank = np.clip(iv_rank, 0, 100)
        
        return float(iv_rank)
    
    @staticmethod
    def calculate_iv_percentile(
        current_iv: float,
        iv_history: pd.Series,
        lookback_days: int = 252
    ) -> float:
        """Calculate IV percentile (% of days with lower IV).
        
        IV Percentile = (# days with IV < current) / total days × 100
        
        Measures what percentage of historical days had lower IV.
        - 0 = current IV is lowest ever
        - 50 = current IV is at median
        - 100 = current IV is highest ever
        
        More robust than IV rank as it's less sensitive to outliers.
        
        Args:
            current_iv: Current implied volatility
            iv_history: Historical IV series
            lookback_days: Days to look back (default: 252 = 1 year)
        
        Returns:
            IV percentile (0-100)
        """
        if iv_history.empty:
            logger.warning("No IV history provided, returning 50 (neutral)")
            return 50.0
        
        # Use most recent period
        recent_iv = iv_history.tail(lookback_days)
        
        if len(recent_iv) < 2:
            logger.warning("Insufficient IV history, returning 50 (neutral)")
            return 50.0
        
        # Count days with lower IV
        days_lower = (recent_iv < current_iv).sum()
        total_days = len(recent_iv)
        
        # Calculate percentile
        percentile = (days_lower / total_days) * 100
        
        return float(percentile)
    
    @staticmethod
    def calculate_expected_move(
        stock_price: float,
        implied_vol: float,
        days_to_expiration: int
    ) -> Dict[str, float]:
        """Calculate expected move based on implied volatility.
        
        Formula: Expected Move = Stock Price × IV × √(DTE/365)
        
        This represents the 1-standard deviation expected move by expiration,
        assuming normal distribution (68.2% probability).
        
        Args:
            stock_price: Current stock price
            implied_vol: Implied volatility (annualized)
            days_to_expiration: Days until option expiration
        
        Returns:
            Dictionary with expected move metrics:
            - expected_move: Dollar amount (1-SD)
            - expected_move_pct: Percentage move
            - upper_range: Upper bound (price + move)
            - lower_range: Lower bound (price - move)
            - upper_2sd: Upper 2-SD bound (~95% confidence)
            - lower_2sd: Lower 2-SD bound (~95% confidence)
        """
        if days_to_expiration <= 0:
            return {
                'expected_move': 0.0,
                'expected_move_pct': 0.0,
                'upper_range': stock_price,
                'lower_range': stock_price,
                'upper_2sd': stock_price,
                'lower_2sd': stock_price,
            }
        
        # Time factor
        time_factor = np.sqrt(days_to_expiration / 365)
        
        # Expected 1-SD move
        expected_move = stock_price * implied_vol * time_factor
        expected_move_pct = (expected_move / stock_price) * 100
        
        # Calculate ranges
        upper_1sd = stock_price + expected_move
        lower_1sd = stock_price - expected_move
        upper_2sd = stock_price + (2 * expected_move)
        lower_2sd = stock_price - (2 * expected_move)
        
        return {
            'expected_move': float(expected_move),
            'expected_move_pct': float(expected_move_pct),
            'upper_range': float(upper_1sd),
            'lower_range': float(lower_1sd),
            'upper_2sd': float(upper_2sd),
            'lower_2sd': float(lower_2sd),
        }
    
    @staticmethod
    def identify_vol_regime(
        current_iv: Optional[float] = None,
        iv_rank: Optional[float] = None,
        iv_percentile: Optional[float] = None
    ) -> str:
        """Classify volatility regime based on IV metrics.
        
        Uses IV rank/percentile to classify market regime:
        - 'extremely_low': IV < 10th percentile (sell vol strategies unfavorable)
        - 'low': IV 10-25th percentile (neutral to slight premium selling)
        - 'normal': IV 25-50th percentile (balanced strategies)
        - 'elevated': IV 50-75th percentile (favor premium selling)
        - 'high': IV 75-90th percentile (strong premium selling)
        - 'extremely_high': IV > 90th percentile (max premium selling, risk of spike)
        
        Args:
            current_iv: Current implied volatility (optional, for context)
            iv_rank: IV rank (0-100)
            iv_percentile: IV percentile (0-100)
        
        Returns:
            Volatility regime classification
        """
        # Prefer percentile over rank (more robust)
        metric = iv_percentile if iv_percentile is not None else iv_rank
        
        if metric is None:
            logger.warning("No IV metrics provided, returning 'unknown'")
            return 'unknown'
        
        # Classify regime
        if metric < 10:
            return 'extremely_low'
        elif metric < 25:
            return 'low'
        elif metric < 50:
            return 'normal'
        elif metric < 75:
            return 'elevated'
        elif metric < 90:
            return 'high'
        else:
            return 'extremely_high'
    
    @staticmethod
    def get_strategy_recommendations(vol_regime: str) -> Dict[str, str]:
        """Get options strategy recommendations based on volatility regime.
        
        Args:
            vol_regime: Volatility regime classification
        
        Returns:
            Dictionary with strategy recommendations:
            - preferred: Best strategies for this regime
            - avoid: Strategies to avoid
            - reasoning: Why these strategies work
        """
        recommendations = {
            'extremely_low': {
                'preferred': 'Long options (straddles, strangles, calendars)',
                'avoid': 'Short premium strategies (iron condors, butterflies)',
                'reasoning': 'IV likely to increase; buy volatility when cheap'
            },
            'low': {
                'preferred': 'Long options, debit spreads, calendars',
                'avoid': 'Naked short options',
                'reasoning': 'IV below average; favor buying strategies'
            },
            'normal': {
                'preferred': 'Balanced strategies (iron condors, butterflies, spreads)',
                'avoid': 'None (balanced environment)',
                'reasoning': 'IV at average levels; all strategies viable'
            },
            'elevated': {
                'preferred': 'Credit spreads, iron condors, covered calls',
                'avoid': 'Long straddles/strangles',
                'reasoning': 'IV above average; favor selling strategies'
            },
            'high': {
                'preferred': 'Short premium (iron condors, credit spreads)',
                'avoid': 'Long volatility plays',
                'reasoning': 'IV expensive; strong premium selling opportunity'
            },
            'extremely_high': {
                'preferred': 'Short premium with caution, iron condors with wide wings',
                'avoid': 'Undefined risk short volatility',
                'reasoning': 'IV very high but risk of further spike; use defined risk'
            },
            'unknown': {
                'preferred': 'Neutral strategies (butterflies, iron condors)',
                'avoid': 'Directional bets',
                'reasoning': 'Insufficient data; use balanced approach'
            }
        }
        
        return recommendations.get(vol_regime, recommendations['unknown'])
    
    def analyze_comprehensive(
        self,
        current_iv: float,
        prices: pd.Series,
        iv_history: pd.Series,
        stock_price: float,
        days_to_expiration: int = 30,
        lookback_days: int = 252
    ) -> VolatilityMetrics:
        """Perform comprehensive volatility analysis.
        
        Combines all volatility metrics into a single analysis.
        
        Args:
            current_iv: Current implied volatility
            prices: Price history for HV calculation
            iv_history: Historical IV series
            stock_price: Current stock price
            days_to_expiration: Days to option expiration
            lookback_days: Historical lookback period
        
        Returns:
            VolatilityMetrics object with all metrics
        """
        # Historical volatility
        hv_20d = self.calculate_historical_volatility(prices, window=20)
        hv_30d = self.calculate_historical_volatility(prices, window=30)
        
        # IV metrics
        iv_rank = self.calculate_iv_rank(current_iv, iv_history, lookback_days)
        iv_percentile = self.calculate_iv_percentile(current_iv, iv_history, lookback_days)
        
        # IV statistics
        recent_iv = iv_history.tail(lookback_days)
        iv_high_52w = float(recent_iv.max()) if not recent_iv.empty else current_iv
        iv_low_52w = float(recent_iv.min()) if not recent_iv.empty else current_iv
        iv_median_52w = float(recent_iv.median()) if not recent_iv.empty else current_iv
        
        # Expected move
        move = self.calculate_expected_move(stock_price, current_iv, days_to_expiration)
        
        # Volatility regime
        vol_regime = self.identify_vol_regime(current_iv, iv_rank, iv_percentile)
        
        return VolatilityMetrics(
            current_iv=current_iv,
            historical_vol_20d=hv_20d,
            historical_vol_30d=hv_30d,
            iv_rank=iv_rank,
            iv_percentile=iv_percentile,
            iv_high_52w=iv_high_52w,
            iv_low_52w=iv_low_52w,
            iv_median_52w=iv_median_52w,
            expected_move_1sd=move['expected_move'],
            expected_move_pct=move['expected_move_pct'],
            vol_regime=vol_regime
        )


if __name__ == "__main__":
    # Example usage and self-test
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 70)
    print("Volatility Analyzer - Self Test")
    print("=" * 70)
    
    analyzer = VolatilityAnalyzer()
    
    # Generate sample data
    np.random.seed(42)
    dates = pd.date_range('2023-01-01', '2024-01-01', freq='D')
    prices = pd.Series(100 * np.exp(np.cumsum(np.random.randn(len(dates)) * 0.01)), index=dates)
    iv_series = pd.Series(0.20 + 0.10 * np.random.randn(len(dates)).cumsum() * 0.01, index=dates)
    iv_series = iv_series.clip(0.10, 0.60)  # Realistic IV range
    
    current_iv = 0.30
    stock_price = float(prices.iloc[-1])
    
    # Test 1: Historical Volatility
    print("\n📊 Test 1: Historical Volatility")
    hv_20 = analyzer.calculate_historical_volatility(prices, window=20)
    hv_30 = analyzer.calculate_historical_volatility(prices, window=30)
    print(f"20-day HV: {hv_20:.2%}")
    print(f"30-day HV: {hv_30:.2%}")
    
    # Test 2: IV Rank & Percentile
    print("\n📊 Test 2: IV Rank & Percentile")
    iv_rank = analyzer.calculate_iv_rank(current_iv, iv_series)
    iv_percentile = analyzer.calculate_iv_percentile(current_iv, iv_series)
    print(f"Current IV: {current_iv:.2%}")
    print(f"IV Rank: {iv_rank:.1f}")
    print(f"IV Percentile: {iv_percentile:.1f}")
    
    # Test 3: Expected Move
    print("\n📊 Test 3: Expected Move")
    move = analyzer.calculate_expected_move(stock_price, current_iv, days_to_expiration=30)
    print(f"Stock Price: ${stock_price:.2f}")
    print(f"Expected 1-SD Move: ${move['expected_move']:.2f} ({move['expected_move_pct']:.1%})")
    print(f"Expected Range: ${move['lower_range']:.2f} - ${move['upper_range']:.2f}")
    
    # Test 4: Volatility Regime
    print("\n📊 Test 4: Volatility Regime")
    regime = analyzer.identify_vol_regime(current_iv, iv_rank, iv_percentile)
    print(f"Volatility Regime: {regime}")
    
    recommendations = analyzer.get_strategy_recommendations(regime)
    print(f"\nStrategy Recommendations:")
    print(f"  Preferred: {recommendations['preferred']}")
    print(f"  Avoid: {recommendations['avoid']}")
    print(f"  Reasoning: {recommendations['reasoning']}")
    
    # Test 5: Comprehensive Analysis
    print("\n📊 Test 5: Comprehensive Analysis")
    metrics = analyzer.analyze_comprehensive(
        current_iv=current_iv,
        prices=prices,
        iv_history=iv_series,
        stock_price=stock_price,
        days_to_expiration=30
    )
    print(metrics)
    
    print("\n" + "=" * 70)
    print("✅ All tests passed!")
    print("=" * 70)
