"""
AdaptiveSuperTrend: Production-Grade Adaptive SuperTrend Indicator for SwiftBolt_ML

A sophisticated walk-forward optimization system that automatically selects optimal
SuperTrend ATR multipliers (1.0-5.0) based on historical performance, with Supabase
caching, multi-timeframe analysis, and ML feature extraction.

Features:
  - Walk-forward optimization with multiple performance metrics (Sharpe, Sortino, Calmar)
  - Supabase caching for factor storage and signal persistence
  - Multi-timeframe analysis (15m, 1h, 4h) with consensus weighting
  - ML-ready feature extraction for XGBoost/Random Forest models
  - Portfolio-level analysis with parallel processing
  - Real-time signal generation with confidence metrics

Usage:
    from adaptive_supertrend import AdaptiveSuperTrend, SuperTrendConfig
    
    config = SuperTrendConfig(metric_objective='sharpe')
    ast = AdaptiveSuperTrend(config=config)
    
    signal = await ast.generate_signal_with_optimization(
        symbol='AAPL',
        timeframe='1h',
        high=high_array,
        low=low_array,
        close=close_array
    )

Documentation: See README.md
Examples: See examples.py

Author: SwiftBolt_ML Team
Date: January 2026
"""

from .adaptive_supertrend import (
    AdaptiveSuperTrend,
    AdaptiveSuperTrendOptimizer,
    SuperTrendCalculator,
    PerformanceEvaluator,
    SuperTrendConfig,
    SuperTrendSignal,
    PerformanceMetrics,
    BatchOptimizer
)

from .supabase_integration import (
    SupabaseAdaptiveSuperTrendSync,
    SupabaseFactorCache,
    SupabaseSignalStorage
)

from .swiftbolt_integration import (
    MultiTimeframeAnalyzer,
    PortfolioAdapter,
    MLFeatureExtractor,
    DataProvider,
    AlpacaDataProvider,
    TimeframeConfig
)

__version__ = "1.0.0"
__author__ = "SwiftBolt_ML Team"
__license__ = "Proprietary"

__all__ = [
    # Core classes
    "AdaptiveSuperTrend",
    "AdaptiveSuperTrendOptimizer",
    "SuperTrendCalculator",
    "PerformanceEvaluator",
    "BatchOptimizer",
    
    # Configuration & Data Models
    "SuperTrendConfig",
    "SuperTrendSignal",
    "PerformanceMetrics",
    
    # Supabase Integration
    "SupabaseAdaptiveSuperTrendSync",
    "SupabaseFactorCache",
    "SupabaseSignalStorage",
    
    # SwiftBolt Integration
    "MultiTimeframeAnalyzer",
    "PortfolioAdapter",
    "MLFeatureExtractor",
    "DataProvider",
    "AlpacaDataProvider",
    "TimeframeConfig",
]

print(f"""
🎯 AdaptiveSuperTrend v{__version__} loaded
   Walk-forward optimization engine for SuperTrend
   Integrated with Supabase & ML pipeline
""")
