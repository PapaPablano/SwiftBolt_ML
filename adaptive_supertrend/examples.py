"""
AdaptiveSuperTrend Usage Examples
Complete working examples for SwiftBolt_ML integration

Author: SwiftBolt_ML
Date: January 2026
"""

import os
import sys
import logging
import numpy as np
import pandas as pd
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from adaptive_supertrend import (
    AdaptiveSuperTrend,
    SuperTrendConfig,
    SuperTrendSignal,
    PerformanceMetrics
)
from supabase_integration import SupabaseAdaptiveSuperTrendSync
from swiftbolt_integration import (
    MultiTimeframeAnalyzer,
    PortfolioAdapter,
    MLFeatureExtractor,
    DataProvider
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# EXAMPLE 1: Basic AdaptiveSuperTrend with Synthetic Data
# ============================================================================

def example_1_basic_supertrend():
    """
    Most basic example: optimize factor and generate signal
    """
    print("\n" + "="*80)
    print("EXAMPLE 1: Basic AdaptiveSuperTrend")
    print("="*80)
    
    # Generate synthetic price data (trending market)
    np.random.seed(42)
    n_bars = 1000
    trend = np.sin(np.linspace(0, 4*np.pi, n_bars))
    noise = np.random.randn(n_bars) * 0.3
    close = 100 + np.cumsum(trend + noise)
    
    # High/low with some variation
    high = close + np.abs(np.random.randn(n_bars) * 0.8)
    low = close - np.abs(np.random.randn(n_bars) * 0.8)
    
    # Configure
    config = SuperTrendConfig(
        atr_period=10,
        metric_objective='sharpe',
        factor_step=0.5
    )
    
    # Initialize
    ast = AdaptiveSuperTrend(config=config)
    
    # Get optimal factor
    factor, metrics = ast.optimizer.get_optimal_factor_for_period(high, low, close)
    
    print(f"\n🎯 Optimal Factor: {factor:.2f}")
    print(f"\n📊 Performance Metrics:")
    print(f"  Sharpe Ratio:   {metrics.sharpe_ratio:>7.2f}")
    print(f"  Sortino Ratio:  {metrics.sortino_ratio:>7.2f}")
    print(f"  Calmar Ratio:   {metrics.calmar_ratio:>7.2f}")
    print(f"  Max Drawdown:   {metrics.max_drawdown:>7.1%}")
    print(f"  Win Rate:       {metrics.win_rate:>7.1%}")
    print(f"  Profit Factor:  {metrics.profit_factor:>7.2f}")
    print(f"  Num Trades:     {metrics.num_trades:>7.0f}")
    
    # Generate signal
    signal = ast.generate_signal(
        symbol='AAPL',
        timeframe='1h',
        high=high,
        low=low,
        close=close,
        factor=factor,
        metrics=metrics
    )
    
    print(f"\n📜 Signal:")
    print(f"  Trend:            {'🔼 Bullish' if signal.trend == 1 else '🔽 Bearish'}")
    print(f"  Price:            ${close[-1]:.2f}")
    print(f"  SuperTrend:       ${signal.supertrend_value:.2f}")
    print(f"  Distance:         {signal.distance_pct*100:.2f}%")
    print(f"  Signal Strength:  {signal.signal_strength:.1f}/10")
    print(f"  Confidence:       {signal.confidence:.1%}")
    print(f"  Trend Duration:   {signal.trend_duration} bars")


# ============================================================================
# EXAMPLE 2: Walk-Forward Optimization
# ============================================================================

def example_2_walk_forward_optimization():
    """
    Demonstrate walk-forward optimization showing factor evolution
    """
    print("\n" + "="*80)
    print("EXAMPLE 2: Walk-Forward Optimization")
    print("="*80)
    
    # Generate synthetic data
    np.random.seed(42)
    n_bars = 1500  # Enough for multiple walk-forward windows
    close = 100 + np.cumsum(np.random.randn(n_bars) * 0.5)
    high = close + np.abs(np.random.randn(n_bars) * 0.8)
    low = close - np.abs(np.random.randn(n_bars) * 0.8)
    
    # Configure
    config = SuperTrendConfig(
        atr_period=10,
        metric_objective='sharpe',
        test_period=252,
        train_period=504
    )
    
    # Initialize optimizer
    ast = AdaptiveSuperTrend(config=config)
    
    # Run walk-forward optimization
    print("\n🔄 Running walk-forward optimization...")
    timestamps, optimal_factors, history = ast.optimizer.optimize_factor_rolling(
        high, low, close
    )
    
    print(f"\n✅ Completed {len(timestamps)} optimization windows")
    
    # Show results
    print(f"\n📊 Factor Evolution:")
    print(f"{'':<12} {'Factor':>8} {'Sharpe':>8} {'Sortino':>8} {'Calmar':>8}")
    print("-" * 50)
    
    for i, ts in enumerate(timestamps[:5]):  # Show first 5
        # Get best factor for this period
        factor = optimal_factors[i]
        
        # Find this factor's metrics in history
        idx = next((j for j, (t, f) in enumerate(zip(history['timestamp'], history['factor']))
                   if t == ts and f == factor), None)
        
        if idx is not None:
            print(f"Window {i+1:<5} {factor:>8.2f} {history['sharpe'][idx]:>8.2f} "
                  f"{history['sortino'][idx]:>8.2f} {history['calmar'][idx]:>8.2f}")
    
    # Statistics
    print(f"\n📊 Factor Statistics:")
    print(f"  Mean Factor:    {np.mean(optimal_factors):.2f}")
    print(f"  Std Dev:        {np.std(optimal_factors):.2f}")
    print(f"  Min Factor:     {np.min(optimal_factors):.2f}")
    print(f"  Max Factor:     {np.max(optimal_factors):.2f}")
    print(f"  Range:          {np.max(optimal_factors) - np.min(optimal_factors):.2f}")


# ============================================================================
# EXAMPLE 3: Mock Supabase Integration
# ============================================================================

async def example_3_supabase_integration():
    """
    Demonstrate Supabase caching and signal storage
    (Uses mock Supabase client for demo)
    """
    print("\n" + "="*80)
    print("EXAMPLE 3: Supabase Integration (Mock)")
    print("="*80)
    
    # Check if Supabase credentials are available
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    
    if not supabase_url or not supabase_key:
        print("\n⚠️  Supabase credentials not configured")
        print("   Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables")
        print("   Showing mock example...\n")
        return
    
    try:
        sync = SupabaseAdaptiveSuperTrendSync(
            supabase_url=supabase_url,
            supabase_key=supabase_key
        )
        
        # Generate data
        np.random.seed(42)
        close = 100 + np.cumsum(np.random.randn(1000) * 0.5)
        high = close + np.abs(np.random.randn(1000) * 0.8)
        low = close - np.abs(np.random.randn(1000) * 0.8)
        
        # Process symbol
        print("\n🏙️  Processing AAPL 1h...")
        signal = await sync.process_symbol(
            symbol='AAPL',
            timeframe='1h',
            high=high.tolist(),
            low=low.tolist(),
            close=close.tolist(),
            store_signal=True
        )
        
        if signal:
            print(f"\n✅ Signal generated and stored")
            print(f"  Trend:    {'🔼 Bullish' if signal.trend == 1 else '🔽 Bearish'}")
            print(f"  Factor:   {signal.factor:.2f}")
            print(f"  Strength: {signal.signal_strength:.1f}/10")
            
            # Get cached factor
            print("\n📁 Retrieving from cache...")
            cached = await sync.cache.get_cached_factor('AAPL', '1h')
            if cached:
                print(f"\n✅ Cache hit!")
                print(f"  Cached Factor: {cached['optimal_factor']:.2f}")
                print(f"  Sharpe:        {cached['sharpe_ratio']:.2f}")
        
    except Exception as e:
        logger.error(f"Supabase integration error: {e}")
        print(f"\n❌ Error: {e}")


# ============================================================================
# EXAMPLE 4: Multi-Timeframe Analysis (Mock Data)
# ============================================================================

def example_4_multi_timeframe():
    """
    Analyze signals across multiple timeframes with consensus
    """
    print("\n" + "="*80)
    print("EXAMPLE 4: Multi-Timeframe Analysis")
    print("="*80)
    
    # Generate signals for different timeframes
    config = SuperTrendConfig(metric_objective='sharpe')
    ast = AdaptiveSuperTrend(config=config)
    
    signals = {}
    timeframes = ['15m', '1h', '4h']
    
    for timeframe in timeframes:
        # Generate synthetic data
        np.random.seed(hash(timeframe) % 2**32)
        close = 100 + np.cumsum(np.random.randn(500) * 0.5)
        high = close + np.abs(np.random.randn(500) * 0.8)
        low = close - np.abs(np.random.randn(500) * 0.8)
        
        # Get optimal factor
        factor, metrics = ast.optimizer.get_optimal_factor_for_period(high, low, close)
        
        # Generate signal
        signal = ast.generate_signal(
            symbol='AAPL',
            timeframe=timeframe,
            high=high,
            low=low,
            close=close,
            factor=factor,
            metrics=metrics
        )
        
        signals[timeframe] = signal
        
        print(f"\n{timeframe:>5}  Trend:{'🔼' if signal.trend == 1 else '🔽'} "
              f"  Strength:{signal.signal_strength:>5.1f}/10  "
              f"Factor:{factor:>4.1f}  Confidence:{signal.confidence:>5.1%}")
    
    # Get consensus
    analyzer = MultiTimeframeAnalyzer.__new__(MultiTimeframeAnalyzer)
    analyzer.mta = MultiTimeframeAnalyzer.__new__(MultiTimeframeAnalyzer)
    analyzer.mta.get_consensus_signal = lambda x: {
        'consensus': 'STRONG_BUY' if all(s.trend == 1 for s in x.values()) else 'NEUTRAL',
        'bullish_score': np.mean([s.signal_strength / 10 * s.trend for s in x.values()]),
        'confidence': len([s for s in x.values() if s.trend == 1]) / len(x),
        'recommendation': 'BUY with high confidence' if all(s.trend == 1 for s in x.values()) else 'HOLD'
    }
    
    # Simplified consensus
    trends = [s.trend for s in signals.values()]
    strengths = [s.signal_strength for s in signals.values()]
    
    consensus = 'STRONG_BUY' if all(t == 1 for t in trends) else \
                'STRONG_SELL' if all(t == 0 for t in trends) else 'NEUTRAL'
    
    avg_strength = np.mean(strengths)
    agreement = max(trends.count(1), trends.count(0)) / len(trends)
    
    print(f"\n{'-'*50}")
    print(f"\n🎯 CONSENSUS ANALYSIS:")
    print(f"  Consensus:      {consensus}")
    print(f"  Avg Strength:   {avg_strength:.1f}/10")
    print(f"  Agreement:      {agreement:.1%}")
    print(f"  Recommendation: {'BUY with high confidence' if agreement > 0.8 else 'Mixed signals'}")


# ============================================================================
# EXAMPLE 5: ML Feature Extraction
# ============================================================================

def example_5_ml_features():
    """
    Extract features for ML models
    """
    print("\n" + "="*80)
    print("EXAMPLE 5: ML Feature Extraction")
    print("="*80)
    
    # Generate mock signals
    config = SuperTrendConfig()
    ast = AdaptiveSuperTrend(config=config)
    
    signals = {}
    for timeframe in ['15m', '1h', '4h']:
        np.random.seed(hash(timeframe) % 2**32)
        close = 100 + np.cumsum(np.random.randn(500) * 0.5)
        high = close + np.abs(np.random.randn(500) * 0.8)
        low = close - np.abs(np.random.randn(500) * 0.8)
        
        factor, metrics = ast.optimizer.get_optimal_factor_for_period(high, low, close)
        signal = ast.generate_signal(
            symbol='AAPL',
            timeframe=timeframe,
            high=high,
            low=low,
            close=close,
            factor=factor,
            metrics=metrics
        )
        signals[timeframe] = signal
    
    # Calculate consensus
    trends = [s.trend for s in signals.values()]
    strengths = [s.signal_strength for s in signals.values()]
    consensus = {
        'bullish_score': np.mean([s.signal_strength / 10 * (s.trend or -1) for s in signals.values()]),
        'confidence': max(trends.count(1), trends.count(0)) / len(trends)
    }
    
    # Extract features
    features = MLFeatureExtractor.extract_features(signals, consensus)
    
    print(f"\n💺 Extracted {len(features)} Features for ML Models:")
    print(f"\n{'Feature Name':<40} {'Value':>10}")
    print("-" * 52)
    
    for feature_name, value in sorted(features.items()):
        if isinstance(value, float):
            print(f"{feature_name:<40} {value:>10.4f}")
        else:
            print(f"{feature_name:<40} {str(value):>10}")
    
    # Show how to use with ML
    print(f"\n🧰 ML Model Integration Example:")
    print(f"""    
    import xgboost as xgb
    
    # Combine with other indicators
    X = pd.concat([
        pd.DataFrame([features]),  # AdaptiveSuperTrend features
        other_indicators_df
    ], axis=1)
    
    # Train model
    model = xgb.XGBClassifier()
    model.fit(X, y_train)
    
    # Feature importance
    importance = model.get_booster().get_score()
    ast_importance = sum(v for k, v in importance.items() if 'ast_' in k)
    print(f"AdaptiveSuperTrend importance: {{ast_importance / sum(importance.values()):.1%}}")
    """)


# ============================================================================
# EXAMPLE 6: Comparison with Fixed Factor
# ============================================================================

def example_6_comparison():
    """
    Compare adaptive factor selection vs fixed factor
    """
    print("\n" + "="*80)
    print("EXAMPLE 6: Adaptive vs Fixed Factor Comparison")
    print("="*80)
    
    # Generate synthetic data
    np.random.seed(42)
    close = 100 + np.cumsum(np.random.randn(1000) * 0.5)
    high = close + np.abs(np.random.randn(1000) * 0.8)
    low = close - np.abs(np.random.randn(1000) * 0.8)
    
    config = SuperTrendConfig(metric_objective='sharpe')
    ast = AdaptiveSuperTrend(config=config)
    
    # Test fixed factors
    fixed_factors = [1.0, 2.0, 3.0, 4.0, 5.0]
    
    print(f"\n📊 Performance Comparison:")
    print(f"\n{'Factor':<10} {'Sharpe':>10} {'Sortino':>10} {'Calmar':>10} {'Win Rate':>10}")
    print("-" * 52)
    
    best_factor = None
    best_sharpe = -np.inf
    
    for factor in fixed_factors:
        metrics = ast.optimizer.evaluate_factor(high, low, close, factor)
        
        print(f"{factor:<10.1f} {metrics.sharpe_ratio:>10.2f} {metrics.sortino_ratio:>10.2f} "
              f"{metrics.calmar_ratio:>10.2f} {metrics.win_rate:>10.1%}")
        
        if metrics.sharpe_ratio > best_sharpe:
            best_sharpe = metrics.sharpe_ratio
            best_factor = factor
    
    # Get adaptive factor
    adaptive_factor, adaptive_metrics = ast.optimizer.get_optimal_factor_for_period(
        high, low, close
    )
    
    print(f"\n{'Adaptive*':<10} {adaptive_metrics.sharpe_ratio:>10.2f} "
          f"{adaptive_metrics.sortino_ratio:>10.2f} {adaptive_metrics.calmar_ratio:>10.2f} "
          f"{adaptive_metrics.win_rate:>10.1%}")
    
    # Improvement
    fixed_metrics = ast.optimizer.evaluate_factor(high, low, close, best_factor)
    improvement = (adaptive_metrics.sharpe_ratio - fixed_metrics.sharpe_ratio) / fixed_metrics.sharpe_ratio
    
    print(f"\n🌟 Adaptive Factor Selection Benefits:")
    print(f"  Best Fixed Factor:    {best_factor:.1f} (Sharpe: {best_sharpe:.2f})")
    print(f"  Adaptive Factor:      {adaptive_factor:.1f} (Sharpe: {adaptive_metrics.sharpe_ratio:.2f})")
    print(f"  Improvement:          {improvement:+.1%}")
    print(f"  Better Win Rate:      {adaptive_metrics.win_rate - fixed_metrics.win_rate:+.1%}")
    print(f"  Lower Max DD:         {adaptive_metrics.max_drawdown - fixed_metrics.max_drawdown:+.1%}")


# ============================================================================
# MAIN
# ============================================================================

async def main():
    """
    Run all examples
    """
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║  AdaptiveSuperTrend - SwiftBolt_ML Examples                     ║
    ║  Complete working examples for all features                    ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    
    examples = [
        ("1", "Basic SuperTrend", example_1_basic_supertrend),
        ("2", "Walk-Forward Optimization", example_2_walk_forward_optimization),
        ("3", "Supabase Integration", example_3_supabase_integration),
        ("4", "Multi-Timeframe Analysis", example_4_multi_timeframe),
        ("5", "ML Feature Extraction", example_5_ml_features),
        ("6", "Adaptive vs Fixed Factor", example_6_comparison),
    ]
    
    # Run sync examples
    for num, name, func in examples:
        if asyncio.iscoroutinefunction(func):
            await func()
        else:
            func()
    
    print("\n" + "="*80)
    print("🌟 All examples completed!")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
