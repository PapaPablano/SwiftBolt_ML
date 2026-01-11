"""Feature engineering modules for SwiftBolt ML."""

from .multi_timeframe import (
    DEFAULT_TIMEFRAMES,
    MultiTimeframeFeatures,
    compute_multi_timeframe_features_for_symbol,
    fetch_multi_timeframe_data,
)
from .sr_correlation_analyzer import (
    SRCorrelationAnalyzer,
    analyze_sr_redundancy,
)
from .technical_indicators import (
    add_all_technical_features,
    add_technical_features,
    calculate_adx,
    calculate_atr,
    calculate_kdj,
    calculate_keltner_channel,
    calculate_mfi,
    calculate_obv,
    calculate_rsi,
    calculate_stochastic,
    calculate_vroc,
    prepare_features_for_ml,
)

__all__ = [
    # Technical indicators
    "add_all_technical_features",
    "add_technical_features",
    "calculate_adx",
    "calculate_atr",
    "calculate_kdj",
    "calculate_keltner_channel",
    "calculate_mfi",
    "calculate_obv",
    "calculate_rsi",
    "calculate_stochastic",
    "calculate_vroc",
    "prepare_features_for_ml",
    # Multi-timeframe
    "DEFAULT_TIMEFRAMES",
    "MultiTimeframeFeatures",
    "compute_multi_timeframe_features_for_symbol",
    "fetch_multi_timeframe_data",
    # S/R Correlation
    "SRCorrelationAnalyzer",
    "analyze_sr_redundancy",
]
