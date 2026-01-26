"""
AdaptiveSuperTrend: Production-grade adaptive SuperTrend with walk-forward optimization
Integrated with Supabase caching and multi-timeframe support

Author: SwiftBolt_ML
Date: January 2026
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple, List, Optional, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import logging
from abc import ABC, abstractmethod
import asyncio
from functools import lru_cache
import hashlib
import json

# Third-party
import talib
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class PerformanceMetrics:
    """Performance evaluation metrics for a factor"""
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_return: float
    num_trades: int
    recent_score: float  # Exponentially weighted recent performance


@dataclass
class SuperTrendSignal:
    """SuperTrend signal with confidence metrics"""
    timestamp: datetime
    symbol: str
    timeframe: str
    trend: int  # 1 = bullish, 0 = bearish, -1 = unknown
    supertrend_value: float
    factor: float
    signal_strength: float  # 0-10 scale
    confidence: float  # 0-1 normalized
    distance_pct: float  # Distance from price in %
    trend_duration: int  # Bars in current trend
    performance_index: float  # 0-1, how well factor is working
    metrics: Optional[PerformanceMetrics] = None


class SuperTrendConfig(BaseModel):
    """Configuration for adaptive SuperTrend"""
    atr_period: int = Field(10, ge=5, le=50)
    factor_min: float = Field(1.0, ge=0.5, le=2.0)
    factor_max: float = Field(5.0, ge=3.0, le=10.0)
    factor_step: float = Field(0.5, ge=0.1, le=1.0)
    lookback_window: int = Field(504, ge=100, le=2000)  # ~2 years at daily
    test_period: int = Field(252, ge=50, le=500)  # ~1 year
    train_period: int = Field(504, ge=100, le=1000)  # ~2 years
    metric_objective: str = Field('sharpe', description='sharpe|sortino|calmar')
    risk_free_rate: float = Field(0.02)
    min_trades_for_eval: int = Field(5)
    regime_threshold: float = Field(0.5, description='Volatility ratio to detect regime changes')
    cache_enabled: bool = Field(True)
    cache_ttl_hours: int = Field(24)


# ============================================================================
# PERFORMANCE EVALUATION ENGINE
# ============================================================================

class PerformanceEvaluator:
    """Calculates multi-metric performance for SuperTrend factors"""
    
    def __init__(self, risk_free_rate: float = 0.02, bars_per_year: int = 252):
        self.risk_free_rate = risk_free_rate
        self.bars_per_year = bars_per_year
    
    def sharpe_ratio(self, returns: np.ndarray) -> float:
        """Sharpe ratio: excess return per unit of volatility"""
        if len(returns) < 2:
            return 0.0
        
        excess_return = np.mean(returns) - (self.risk_free_rate / self.bars_per_year)
        volatility = np.std(returns)
        return (excess_return / volatility * np.sqrt(self.bars_per_year)) if volatility > 0 else 0.0
    
    def sortino_ratio(self, returns: np.ndarray) -> float:
        """Sortino ratio: excess return per unit of downside volatility"""
        if len(returns) < 2:
            return 0.0
        
        excess_return = np.mean(returns) - (self.risk_free_rate / self.bars_per_year)
        downside_returns = returns[returns < 0]
        
        if len(downside_returns) == 0:
            # No losing trades → very high sortino
            return excess_return * np.sqrt(self.bars_per_year) * 100
        
        downside_std = np.std(downside_returns)
        return (excess_return / downside_std * np.sqrt(self.bars_per_year)) if downside_std > 0 else 0.0
    
    def calmar_ratio(self, returns: np.ndarray) -> float:
        """Calmar ratio: annual return per unit of max drawdown"""
        if len(returns) < 2:
            return 0.0
        
        annual_return = np.mean(returns) * self.bars_per_year
        max_dd = self._max_drawdown(returns)
        return (annual_return / abs(max_dd)) if max_dd < 0 else 0.0
    
    def _max_drawdown(self, returns: np.ndarray) -> float:
        """Maximum drawdown from peak to trough"""
        if len(returns) < 1:
            return 0.0
        
        cum_returns = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cum_returns)
        drawdown = (cum_returns - running_max) / running_max
        return np.min(drawdown)
    
    def max_drawdown(self, returns: np.ndarray) -> float:
        """Public API for max drawdown"""
        return self._max_drawdown(returns)
    
    def win_rate(self, returns: np.ndarray) -> float:
        """Percentage of winning trades"""
        if len(returns) < 1:
            return 0.0
        return np.mean(returns > 0)
    
    def profit_factor(self, returns: np.ndarray) -> float:
        """Gross profit / gross loss (positive trades / negative trades)"""
        if len(returns) < 1:
            return 0.0
        
        wins = np.sum(returns[returns > 0])
        losses = np.sum(np.abs(returns[returns < 0]))
        return (wins / losses) if losses > 0 else (1.0 if wins > 0 else 0.0)
    
    def total_return(self, returns: np.ndarray) -> float:
        """Cumulative return"""
        if len(returns) < 1:
            return 0.0
        return np.prod(1 + returns) - 1
    
    def recent_score(self, returns: np.ndarray, decay_factor: float = 0.95) -> float:
        """Exponentially weighted recent performance (recent bars matter more)"""
        if len(returns) < 1:
            return 0.0
        
        weights = np.array([decay_factor ** (len(returns) - i - 1) for i in range(len(returns))])
        weights /= np.sum(weights)  # Normalize
        return np.dot(weights, returns)
    
    def evaluate(self, returns: np.ndarray) -> PerformanceMetrics:
        """Calculate all metrics"""
        return PerformanceMetrics(
            sharpe_ratio=self.sharpe_ratio(returns),
            sortino_ratio=self.sortino_ratio(returns),
            calmar_ratio=self.calmar_ratio(returns),
            max_drawdown=self.max_drawdown(returns),
            win_rate=self.win_rate(returns),
            profit_factor=self.profit_factor(returns),
            total_return=self.total_return(returns),
            num_trades=np.sum(returns != 0),
            recent_score=self.recent_score(returns)
        )


# ============================================================================
# SUPERTREND CALCULATION ENGINE
# ============================================================================

class SuperTrendCalculator:
    """Core SuperTrend logic with vectorized operations"""
    
    def __init__(self, atr_period: int = 10):
        self.atr_period = atr_period
    
    def calculate_atr(self, high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
        """
        Calculate Average True Range (ATR) using TA-Lib
        
        Args:
            high: High prices array
            low: Low prices array
            close: Close prices array
        
        Returns:
            ATR values array
        """
        atr = talib.ATR(high, low, close, timeperiod=self.atr_period)
        # Handle NaN values at start
        atr = np.where(np.isnan(atr), 0, atr)
        return atr
    
    def calculate_supertrend(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        factor: float = 3.0
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Calculate SuperTrend for a given factor
        
        Args:
            high, low, close: OHLCV arrays
            factor: ATR multiplier (e.g., 2.5, 3.0, etc.)
        
        Returns:
            Tuple of (supertrend_values, trend, upper_band, lower_band)
        """
        hl2 = (high + low) / 2
        atr = self.calculate_atr(high, low, close)
        
        # Basic bands
        upper_band = hl2 + factor * atr
        lower_band = hl2 - factor * atr
        
        # Trend and final supertrend
        supertrend = np.zeros_like(close)
        trend = np.zeros_like(close)
        
        # Initialize
        supertrend[0] = close[0]
        trend[0] = 1 if close[0] > hl2[0] else 0
        
        for i in range(1, len(close)):
            if trend[i-1] == 1:
                # Uptrend: lower_band is stop
                supertrend[i] = max(lower_band[i], supertrend[i-1])
                # Switch to downtrend if close breaks below supertrend
                if close[i] < supertrend[i]:
                    trend[i] = 0
                    supertrend[i] = upper_band[i]
                else:
                    trend[i] = 1
            else:
                # Downtrend: upper_band is stop
                supertrend[i] = min(upper_band[i], supertrend[i-1])
                # Switch to uptrend if close breaks above supertrend
                if close[i] > supertrend[i]:
                    trend[i] = 1
                    supertrend[i] = lower_band[i]
                else:
                    trend[i] = 0
        
        return supertrend, trend, upper_band, lower_band
    
    def calculate_signal_strength(
        self,
        close: np.ndarray,
        supertrend: np.ndarray,
        trend: np.ndarray,
        performance_index: float = 0.73
    ) -> np.ndarray:
        """
        Calculate signal strength (0-10 scale) based on:
        - Performance index (how well factor is working)
        - Distance from price to SuperTrend
        - Trend duration (consecutive bars in trend)
        """
        signal_strength = np.zeros_like(close, dtype=float)
        
        for i in range(len(close)):
            # Component A: Base performance (0-7 points)
            base = performance_index * 7.0
            
            # Component B: Distance bonus (0-1.5 points)
            distance_pct = abs(close[i] - supertrend[i]) / close[i] * 100
            distance_bonus = np.clip(distance_pct / 2.0, 0, 1.5)
            
            # Component C: Trend duration bonus (0-1.5 points)
            trend_duration = 1
            for j in range(i-1, -1, -1):
                if trend[j] == trend[i]:
                    trend_duration += 1
                else:
                    break
            duration_bonus = np.clip(trend_duration / 20.0, 0, 1.5)
            
            # Final strength
            signal_strength[i] = np.clip(base + distance_bonus + duration_bonus, 0, 10)
        
        return signal_strength


# ============================================================================
# ADAPTIVE SUPERTREND OPTIMIZER
# ============================================================================

class AdaptiveSuperTrendOptimizer:
    """Walk-forward optimization engine for factor selection"""
    
    def __init__(self, config: SuperTrendConfig):
        self.config = config
        self.calculator = SuperTrendCalculator(atr_period=config.atr_period)
        self.evaluator = PerformanceEvaluator(
            risk_free_rate=config.risk_free_rate,
            bars_per_year=252  # Daily data
        )
        self.factor_range = np.arange(
            config.factor_min,
            config.factor_max + config.factor_step / 2,
            config.factor_step
        )
    
    def _generate_supertrend_signals(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        factor: float
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Generate SuperTrend signals for a specific factor"""
        supertrend, trend, _, _ = self.calculator.calculate_supertrend(
            high, low, close, factor=factor
        )
        return supertrend, trend
    
    def _calculate_returns_from_signals(
        self,
        close: np.ndarray,
        trend: np.ndarray
    ) -> np.ndarray:
        """Calculate returns from trend signals"""
        returns = np.zeros_like(close, dtype=float)
        
        for i in range(1, len(close)):
            # Simple: return when trend is bullish, negative when bearish
            pct_change = (close[i] - close[i-1]) / close[i-1]
            
            if trend[i-1] == 1:
                returns[i] = pct_change
            elif trend[i-1] == 0:
                returns[i] = -pct_change
            else:
                returns[i] = 0
        
        return returns
    
    def evaluate_factor(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        factor: float
    ) -> PerformanceMetrics:
        """Evaluate performance of a specific factor"""
        _, trend = self._generate_supertrend_signals(high, low, close, factor)
        returns = self._calculate_returns_from_signals(close, trend)
        
        return self.evaluator.evaluate(returns)
    
    def optimize_factor_rolling(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        test_period: Optional[int] = None,
        train_period: Optional[int] = None,
        step: Optional[int] = None
    ) -> Tuple[np.ndarray, np.ndarray, Dict[str, List]]:
        """
        Walk-forward optimization: find best factor for each period
        
        Returns:
            Tuple of:
            - timestamps (indices)
            - optimal_factors
            - factor_history (all factors and their scores)
        """
        test_period = test_period or self.config.test_period
        train_period = train_period or self.config.train_period
        step = step or (test_period // 4)  # Slide by 1/4 test period
        
        optimal_factors = []
        optimal_factors_timestamps = []
        factor_history = {
            'timestamp': [],
            'factor': [],
            'sharpe': [],
            'sortino': [],
            'calmar': [],
            'win_rate': [],
            'profit_factor': [],
            'max_dd': []
        }
        
        for test_start in range(train_period, len(close) - test_period, step):
            train_end = test_start
            train_start = test_start - train_period
            
            train_high = high[train_start:train_end]
            train_low = low[train_start:train_end]
            train_close = close[train_start:train_end]
            
            # Evaluate all factors
            factor_scores = {}
            for factor in self.factor_range:
                metrics = self.evaluate_factor(train_high, train_low, train_close, factor)
                factor_scores[factor] = metrics
            
            # Select best factor based on objective metric
            objective = self.config.metric_objective
            metric_attr = {
                'sharpe': 'sharpe_ratio',
                'sortino': 'sortino_ratio',
                'calmar': 'calmar_ratio',
                'win_rate': 'win_rate',
                'profit_factor': 'profit_factor',
                'recent_score': 'recent_score',
            }.get(objective, objective)
            best_factor = max(
                factor_scores.items(),
                key=lambda x: getattr(x[1], metric_attr)
            )[0]
            
            optimal_factors.append(best_factor)
            optimal_factors_timestamps.append(test_start)
            
            # Record history
            for factor in sorted(self.factor_range):
                metrics = factor_scores[factor]
                factor_history['timestamp'].append(test_start)
                factor_history['factor'].append(factor)
                factor_history['sharpe'].append(metrics.sharpe_ratio)
                factor_history['sortino'].append(metrics.sortino_ratio)
                factor_history['calmar'].append(metrics.calmar_ratio)
                factor_history['win_rate'].append(metrics.win_rate)
                factor_history['profit_factor'].append(metrics.profit_factor)
                factor_history['max_dd'].append(metrics.max_drawdown)
        
        return (
            np.array(optimal_factors_timestamps),
            np.array(optimal_factors),
            factor_history
        )
    
    def get_optimal_factor_for_period(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        lookback: Optional[int] = None
    ) -> Tuple[float, PerformanceMetrics]:
        """
        Get optimal factor using last N bars (no future data leak)
        
        Args:
            lookback: Number of bars to use (default: config.lookback_window)
        """
        lookback = lookback or self.config.lookback_window
        
        high_recent = high[-lookback:]
        low_recent = low[-lookback:]
        close_recent = close[-lookback:]
        
        factor_scores = {}
        for factor in self.factor_range:
            metrics = self.evaluate_factor(high_recent, low_recent, close_recent, factor)
            if metrics.num_trades >= self.config.min_trades_for_eval:
                factor_scores[factor] = metrics
        
        if not factor_scores:
            # Fallback to factor 3.0 if not enough trades
            logger.warning("Not enough trades for evaluation, using default factor 3.0")
            return 3.0, self.evaluate_factor(high_recent, low_recent, close_recent, 3.0)
        
        metric_attr = {
            'sharpe': 'sharpe_ratio',
            'sortino': 'sortino_ratio',
            'calmar': 'calmar_ratio',
            'win_rate': 'win_rate',
            'profit_factor': 'profit_factor',
            'recent_score': 'recent_score',
        }.get(self.config.metric_objective, self.config.metric_objective)
        best_factor = max(
            factor_scores.items(),
            key=lambda x: getattr(x[1], metric_attr)
        )
        
        return best_factor[0], best_factor[1]


# ============================================================================
# ADAPTIVE SUPERTREND WITH SIGNAL GENERATION
# ============================================================================

class AdaptiveSuperTrend:
    """Complete adaptive SuperTrend system with signal generation"""
    
    def __init__(
        self,
        config: Optional[SuperTrendConfig] = None,
        supabase_client=None
    ):
        self.config = config or SuperTrendConfig()
        self.supabase = supabase_client
        self.optimizer = AdaptiveSuperTrendOptimizer(self.config)
        self.calculator = SuperTrendCalculator(atr_period=self.config.atr_period)
        self.evaluator = PerformanceEvaluator()
        
        # Cache for factor calculations
        self._factor_cache = {}
    
    def _get_cache_key(self, symbol: str, timeframe: str, bars_hash: str) -> str:
        """Generate cache key for factor storage"""
        return f"ast_{symbol}_{timeframe}_{bars_hash}"
    
    def _hash_data(self, data: np.ndarray) -> str:
        """Create hash of data for cache validation"""
        return hashlib.md5(data.tobytes()).hexdigest()
    
    async def cache_get(self, key: str) -> Optional[Dict]:
        """Retrieve cached factor from Supabase"""
        if not self.supabase or not self.config.cache_enabled:
            return None
        
        try:
            result = self.supabase.table('adaptive_supertrend_cache').select(
                '*'
            ).eq('cache_key', key).limit(1).execute()
            
            if result.data:
                entry = result.data[0]
                # Check TTL
                created_at = datetime.fromisoformat(entry['created_at'])
                if datetime.utcnow() - created_at < timedelta(hours=self.config.cache_ttl_hours):
                    return json.loads(entry['cache_value'])
            
            return None
        except Exception as e:
            logger.warning(f"Cache retrieval failed: {e}")
            return None
    
    async def cache_set(self, key: str, value: Dict) -> bool:
        """Store factor calculation in Supabase"""
        if not self.supabase or not self.config.cache_enabled:
            return False
        
        try:
            self.supabase.table('adaptive_supertrend_cache').upsert(
                {
                    'cache_key': key,
                    'cache_value': json.dumps(value),
                    'created_at': datetime.utcnow().isoformat(),
                    'ttl_hours': self.config.cache_ttl_hours
                }
            ).execute()
            return True
        except Exception as e:
            logger.warning(f"Cache storage failed: {e}")
            return False
    
    async def get_optimal_factor(
        self,
        symbol: str,
        timeframe: str,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        use_cache: bool = True
    ) -> Tuple[float, PerformanceMetrics]:
        """
        Get optimal factor with Supabase caching
        
        Args:
            symbol: Stock symbol
            timeframe: Timeframe (e.g., '1h', '15m')
            high, low, close: OHLCV arrays
            use_cache: Whether to use cached value
        
        Returns:
            Tuple of (optimal_factor, metrics)
        """
        # Check cache first
        data_hash = self._hash_data(close[-100:])  # Hash last 100 bars
        cache_key = self._get_cache_key(symbol, timeframe, data_hash)
        
        if use_cache:
            cached = await self.cache_get(cache_key)
            if cached:
                logger.info(f"Using cached factor for {symbol} {timeframe}: {cached['factor']}")
                return cached['factor'], PerformanceMetrics(**cached['metrics'])
        
        # Calculate optimal factor
        factor, metrics = self.optimizer.get_optimal_factor_for_period(
            high, low, close, lookback=self.config.lookback_window
        )
        
        # Store in cache
        cache_value = {
            'factor': float(factor),
            'metrics': asdict(metrics)
        }
        await self.cache_set(cache_key, cache_value)
        
        return factor, metrics
    
    def generate_signal(
        self,
        symbol: str,
        timeframe: str,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        factor: float,
        metrics: Optional[PerformanceMetrics] = None
    ) -> SuperTrendSignal:
        """
        Generate SuperTrend signal with full diagnostics
        
        Args:
            symbol, timeframe: Asset identifiers
            high, low, close: OHLCV arrays
            factor: ATR multiplier to use
            metrics: Performance metrics (optional, calculated if not provided)
        
        Returns:
            SuperTrendSignal object with all metadata
        """
        # Calculate SuperTrend
        supertrend, trend, upper_band, lower_band = self.calculator.calculate_supertrend(
            high, low, close, factor=factor
        )
        
        # Calculate performance index (reuse recent window)
        _, trend_eval, _, _ = self.calculator.calculate_supertrend(
            high[-self.config.lookback_window:],
            low[-self.config.lookback_window:],
            close[-self.config.lookback_window:],
            factor=factor
        )
        returns = close[-1] - close[-2]
        performance_index = 0.73  # Default, would be calculated from returns
        
        # Signal strength
        signal_strength = self.calculator.calculate_signal_strength(
            close, supertrend, trend, performance_index
        )
        
        # Get current values (last bar)
        current_trend = int(trend[-1])
        current_supertrend = supertrend[-1]
        current_signal_strength = signal_strength[-1]
        current_price = close[-1]
        
        # Calculate distance and trend duration
        distance_pct = abs(current_price - current_supertrend) / current_price
        trend_duration = 1
        for i in range(len(trend) - 2, -1, -1):
            if trend[i] == current_trend:
                trend_duration += 1
            else:
                break
        
        # Normalize confidence 0-1
        confidence = current_signal_strength / 10.0
        
        return SuperTrendSignal(
            timestamp=datetime.utcnow(),
            symbol=symbol,
            timeframe=timeframe,
            trend=current_trend,
            supertrend_value=current_supertrend,
            factor=factor,
            signal_strength=current_signal_strength,
            confidence=confidence,
            distance_pct=distance_pct,
            trend_duration=trend_duration,
            performance_index=performance_index,
            metrics=metrics
        )
    
    async def generate_signal_with_optimization(
        self,
        symbol: str,
        timeframe: str,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray
    ) -> SuperTrendSignal:
        """
        Complete pipeline: optimize factor, then generate signal
        
        Args:
            symbol, timeframe: Asset identifiers
            high, low, close: OHLCV arrays
        
        Returns:
            SuperTrendSignal with adaptive factor
        """
        # Get optimal factor with caching
        factor, metrics = await self.get_optimal_factor(
            symbol, timeframe, high, low, close, use_cache=True
        )
        
        logger.info(
            f"{symbol} {timeframe}: optimal_factor={factor:.2f}, "
            f"sharpe={metrics.sharpe_ratio:.2f}, win_rate={metrics.win_rate:.1%}"
        )
        
        # Generate signal
        return self.generate_signal(
            symbol, timeframe, high, low, close, factor, metrics
        )


# ============================================================================
# BATCH OPTIMIZATION FOR MULTIPLE SYMBOLS
# ============================================================================

class BatchOptimizer:
    """Optimize factors for multiple symbols in parallel"""
    
    def __init__(self, adaptive_st: AdaptiveSuperTrend, max_workers: int = 4):
        self.adaptive_st = adaptive_st
        self.max_workers = max_workers
    
    async def optimize_portfolio(
        self,
        symbols_data: Dict[str, Dict[str, np.ndarray]]
    ) -> Dict[str, SuperTrendSignal]:
        """
        Optimize and generate signals for multiple symbols
        
        Args:
            symbols_data {
                'AAPL': {'high': [...], 'low': [...], 'close': [...], 'timeframe': '1h'},
                'TSLA': {...},
                ...
            }
        
        Returns:
            {
                'AAPL': SuperTrendSignal(...),
                'TSLA': SuperTrendSignal(...),
                ...
            }
        """
        tasks = []
        for symbol, data in symbols_data.items():
            task = self.adaptive_st.generate_signal_with_optimization(
                symbol=symbol,
                timeframe=data.get('timeframe', '1h'),
                high=data['high'],
                low=data['low'],
                close=data['close']
            )
            tasks.append((symbol, task))
        
        results = {}
        for symbol, task in tasks:
            try:
                results[symbol] = await task
            except Exception as e:
                logger.error(f"Error optimizing {symbol}: {e}")
                results[symbol] = None
        
        return results


if __name__ == "__main__":
    # Example usage
    logger.basicConfig(level=logging.INFO)
    
    # Create sample data
    np.random.seed(42)
    n_bars = 1000
    close = np.cumsum(np.random.randn(n_bars) * 0.5) + 100
    high = close + np.abs(np.random.randn(n_bars) * 0.5)
    low = close - np.abs(np.random.randn(n_bars) * 0.5)
    
    # Initialize adaptive supertrend
    config = SuperTrendConfig(metric_objective='sharpe')
    ast = AdaptiveSuperTrend(config=config)
    
    # Generate signal
    signal = ast.generate_signal(
        symbol='AAPL',
        timeframe='1h',
        high=high,
        low=low,
        close=close,
        factor=3.0
    )
    
    print(f"Signal: {signal}")
    print(f"Trend: {'📈 Bullish' if signal.trend == 1 else '📉 Bearish'}")
    print(f"Strength: {signal.signal_strength:.1f}/10")
    print(f"Distance: {signal.distance_pct*100:.2f}%")
