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
from .stock_sentiment import (
    daily_sentiment_series,
    get_finviz_news,
    get_historical_sentiment_series,
    get_sentiment_for_ticker,
    get_sentiment_items_for_api,
    hourly_sentiment_series,
    parse_news,
    plot_daily_sentiment,
    plot_hourly_sentiment,
    score_news,
    validate_sentiment_variance,
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
from .temporal_indicators import (
    SIMPLIFIED_FEATURES,
    create_lag_features,
    compute_simplified_features,
    prepare_training_data_temporal,
    TemporalFeatureEngineer,
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
    # Stock sentiment (FinViz + VADER)
    "daily_sentiment_series",
    "get_finviz_news",
    "get_historical_sentiment_series",
    "get_sentiment_for_ticker",
    "get_sentiment_items_for_api",
    "hourly_sentiment_series",
    "parse_news",
    "plot_daily_sentiment",
    "plot_hourly_sentiment",
    "score_news",
    "validate_sentiment_variance",
    # Temporal / simplified features
    "SIMPLIFIED_FEATURES",
    "create_lag_features",
    "compute_simplified_features",
    "prepare_training_data_temporal",
    "TemporalFeatureEngineer",
]
