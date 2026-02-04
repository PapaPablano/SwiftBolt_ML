"""
Temporal-aware feature engineering to prevent lookahead bias.
Computes features bar-by-bar ensuring no forward-looking information.
"""

import logging
from typing import Tuple

import numpy as np
import pandas as pd

from src.features.technical_indicators_corrected import TechnicalIndicatorsCorrect

logger = logging.getLogger(__name__)

# Simplified feature set (31 features) based on empirical importance analysis.
# Includes sentiment features (validated; pipeline fixed).
SIMPLIFIED_FEATURES = [
    # Price & Volume
    "close",
    "volume",
    "volume_ratio",
    # MACD Family
    "macd",
    "macd_hist",
    "macd_signal",
    # Oscillators
    "rsi_14",
    # Bollinger Bands
    "bb_lower",
    "bb_upper",
    "bb_width_pct",
    # Trend Strength
    "adx",
    "supertrend_trend",
    "roc_5d",
    "roc_20d",
    # Volatility
    "atr_14",
    "vix_proxy_atr",
    # Custom Lag Features
    "supertrend_trend_lag1",
    "supertrend_trend_lag7",
    "supertrend_trend_lag14",
    "supertrend_trend_lag30",
    "kdj_divergence_lag1",
    "kdj_divergence_lag7",
    "kdj_divergence_lag14",
    "kdj_divergence_lag30",
    "macd_hist_lag1",
    "macd_hist_lag7",
    "macd_hist_lag14",
    "macd_hist_lag30",
    # KDJ
    "kdj_divergence",
    # Moving Averages
    "sma_50",
    "sma_200",
    # Sentiment (validated; FinViz pipeline fixed)
    "sentiment_score",
    "sentiment_score_lag1",
    "sentiment_score_lag7",
    # Regime (market context; add via add_all_regime_features before compute_simplified_features)
    "spy_above_200ma",
    "spy_trend_strength",
    "spy_trend_regime",
    "vix",
    "vix_regime",
    "vix_percentile",
    "vix_change_5d",
    "correlation_to_spy_30d",
    "correlation_regime",
    "beta_to_spy",
    "sector_relative_strength",
    "sector_outperforming",
    # Stock-specific volatility (no external data; replaces VIX for single-stock prediction)
    "historical_volatility_20d",
    "historical_volatility_60d",
    "atr_normalized",
    "bb_width",
    "volatility_regime",
    "volatility_percentile",
    "volatility_change",
    # Simple regime (stock-only; add via add_all_simple_regime_features before compute_simplified_features)
    "distance_from_200ma",
    "trend_regime",
    "trend_strength",
    "adx_14",
    "momentum_regime",
]

VOLATILITY_FEATURES = [
    "historical_volatility_20d",
    "historical_volatility_60d",
    "atr_normalized",
    "bb_width",
    "volatility_regime",
    "volatility_percentile",
    "volatility_change",
]


def create_lag_features(
    df: pd.DataFrame,
    lags: tuple[int, ...] = (1, 7, 14, 30),
) -> pd.DataFrame:
    """
    Add lagged columns for supertrend_trend, kdj_divergence, macd_hist,
    and sentiment_score (lag1 and lag7 only).
    """
    df = df.copy()
    # Source column for KDJ lags: output names are always kdj_divergence_lag*
    kdj_src = "kdj_divergence" if "kdj_divergence" in df.columns else "kdj_j_divergence"
    lag_specs: list[tuple[str, str]] = [
        ("supertrend_trend", "supertrend_trend"),
        (kdj_src, "kdj_divergence"),
        ("macd_hist", "macd_hist"),
    ]
    for src_col, out_prefix in lag_specs:
        if src_col not in df.columns:
            continue
        for k in lags:
            df[f"{out_prefix}_lag{k}"] = df[src_col].shift(k)
    # Sentiment: lag1 and lag7 only (previous day and previous week)
    if "sentiment_score" in df.columns:
        for k in (1, 7):
            df[f"sentiment_score_lag{k}"] = df["sentiment_score"].shift(k)
    return df


def add_volatility_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add stock-specific volatility indicators (no external data).

    Replaces VIX for single-stock prediction. Requires 'close' (and optionally
    'high', 'low' for ATR/BB from TechnicalIndicatorsCorrect; atr_normalized
    and bb_width are added by add_all_technical_features_correct).
    """
    df = df.copy()
    returns = df["close"].pct_change(fill_method=None)
    # Annualized historical volatility (decimal, e.g. 0.20 = 20%)
    df["historical_volatility_20d"] = returns.rolling(20).std() * np.sqrt(252)
    df["historical_volatility_60d"] = returns.rolling(60).std() * np.sqrt(252)
    # atr_normalized and bb_width come from TechnicalIndicatorsCorrect; ensure if missing
    if "atr_normalized" not in df.columns and "atr_14" in df.columns:
        df["atr_normalized"] = df["atr_14"] / df["close"]
    if "bb_width" not in df.columns and "bb_upper" in df.columns and "bb_middle" in df.columns and "bb_lower" in df.columns:
        df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_middle"].replace(0, np.nan)
    hv = df["historical_volatility_20d"]
    # Volatility regime: 0=low (<20%), 1=medium (20–40%), 2=high (>40%)
    df["volatility_regime"] = np.select(
        [hv < 0.20, hv < 0.40], [0, 1], default=2
    )
    # Percentile of current vol vs last 252 days (0–100)
    def _pct(w) -> float:
        s = pd.Series(w).dropna()
        if len(s) < 2:
            return np.nan
        return float(s.rank(pct=True).iloc[-1]) * 100

    df["volatility_percentile"] = hv.rolling(252, min_periods=60).apply(_pct, raw=False)
    df["volatility_change"] = hv.pct_change(5)

    # Market stress: VIX proxy from ATR (no external VIX needed)
    # Scale ATR/close to VIX-like level: ~15–40 in normal/crisis
    if "atr_14" in df.columns:
        atr_pct = (df["atr_14"] / df["close"].replace(0, np.nan)) * 100
        df["vix_proxy_atr"] = atr_pct * np.sqrt(252)  # annualized, VIX-ish scale
    else:
        tr = np.maximum(
            df["high"] - df["low"],
            np.maximum(
                (df["high"] - df["close"].shift(1)).abs(),
                (df["low"] - df["close"].shift(1)).abs(),
            ),
        )
        atr = tr.rolling(14).mean()
        df["vix_proxy_atr"] = (atr / df["close"].replace(0, np.nan) * 100 * np.sqrt(252))

    # Rate-of-change (trend strength complement to ADX)
    df["roc_5d"] = df["close"].pct_change(5)
    df["roc_20d"] = df["close"].pct_change(20)

    return df


def compute_simplified_features(
    df: pd.DataFrame,
    sentiment_series: pd.Series | None = None,
    add_volatility: bool = True,
) -> pd.DataFrame:
    """
    Compute the simplified feature set: base indicators + lags + sentiment + volatility.

    Uses TechnicalIndicatorsCorrect for base indicators, then add_lag_features,
    optional add_volatility_features, then merge optional sentiment. Requires OHLCV columns.
    """
    df = df.copy()
    df = TechnicalIndicatorsCorrect.add_all_technical_features_correct(df)
    df["kdj_divergence"] = df["kdj_j_divergence"]
    # Add sentiment before lags so sentiment_score_lag1/lag7 can be created
    if sentiment_series is not None:
        if "ts" in df.columns:
            date_index = pd.to_datetime(df["ts"], utc=False).dt.tz_localize(None).dt.normalize()
        else:
            date_index = df.index
        sentiment_aligned = sentiment_series.reindex(date_index).fillna(0.0)
        df["sentiment_score"] = sentiment_aligned.values
    else:
        df["sentiment_score"] = 0.0
    df = create_lag_features(df)
    if add_volatility:
        df = add_volatility_features(df)
    # Simple regime columns (defaults so SIMPLIFIED_FEATURES selection never misses)
    from src.features.regime_features_simple import add_simple_regime_defaults
    df = add_simple_regime_defaults(df)
    # Old regime columns (SPY/VIX) with defaults so SIMPLIFIED_FEATURES selection never misses
    from src.features.regime_features import add_regime_defaults
    df = add_regime_defaults(df)
    return df


class TemporalFeatureEngineer:
    """Compute features bar-by-bar with no lookahead bias."""

    @staticmethod
    def compute_sma(close_prices: np.ndarray, window: int, idx: int) -> float:
        """Compute SMA up to index idx (no lookahead)."""
        if idx < window - 1:
            return np.nan
        return float(np.mean(close_prices[idx - window + 1 : idx + 1]))

    @staticmethod
    def compute_ema(close_prices: np.ndarray, window: int, idx: int) -> float:
        """Compute EMA up to index idx (no lookahead)."""
        if idx < window - 1:
            return np.nan

        prices = close_prices[idx - window + 1 : idx + 1]
        ema = prices[0]
        multiplier = 2 / (window + 1)

        for price in prices[1:]:
            ema = price * multiplier + ema * (1 - multiplier)

        return float(ema)

    @staticmethod
    def compute_rsi(close_prices: np.ndarray, window: int, idx: int) -> float:
        """RSI with no lookahead."""
        if idx < window:
            return np.nan

        changes = np.diff(close_prices[idx - window : idx + 1])
        gains = np.sum(np.maximum(changes, 0))
        losses = np.sum(np.maximum(-changes, 0))

        if losses == 0:
            return 100.0 if gains > 0 else 0.0

        rs = gains / losses
        rsi = 100 - (100 / (1 + rs))
        return float(rsi)

    @staticmethod
    def compute_macd(
        close_prices: np.ndarray,
        idx: int,
    ) -> Tuple[float, float]:
        """MACD with no lookahead."""
        if idx < 26:
            return np.nan, np.nan

        prices = close_prices[: idx + 1]

        ema12 = prices[idx - 12 + 1 : idx + 1].mean()
        for i in range(idx - 11, idx + 1):
            ema12 = prices[i] * (2 / 13) + ema12 * (11 / 13)

        ema26 = prices[idx - 26 + 1 : idx + 1].mean()
        for i in range(idx - 25, idx + 1):
            ema26 = prices[i] * (2 / 27) + ema26 * (25 / 27)

        macd = ema12 - ema26
        return float(macd), float(ema26)

    @staticmethod
    def compute_supertrend_features(
        df: pd.DataFrame,
        idx: int,
        atr_length: int = 10,
        multiplier: float = 2.0,
    ) -> dict:
        """
        Compute SuperTrend features up to idx (no lookahead).

        Uses precomputed SuperTrend AI columns if present in df; otherwise
        falls back to a basic SuperTrend calculation using only history.
        """
        min_required = max(atr_length, 2)
        if idx < min_required:
            return {
                "supertrend_value": np.nan,
                "supertrend_trend": np.nan,
                "supertrend_factor": np.nan,
                "supertrend_performance_index": np.nan,
                "supertrend_signal_strength": np.nan,
                "signal_confidence": np.nan,
                "supertrend_confidence_norm": np.nan,
                "supertrend_distance_norm": np.nan,
                "perf_ama": np.nan,
            }

        # Prefer precomputed AI features if available in df
        if "supertrend_value" in df.columns and "supertrend_trend" in df.columns:
            row = df.iloc[idx]
            value = float(row.get("supertrend_value", np.nan))
            trend = float(row.get("supertrend_trend", np.nan))
            factor = float(row.get("supertrend_factor", multiplier))
            perf_idx = float(row.get("supertrend_performance_index", 0.5))
            strength = float(row.get("supertrend_signal_strength", 5))
            confidence = float(row.get("signal_confidence", 5))
            conf_norm = float(row.get("supertrend_confidence_norm", confidence / 10.0))
            dist_norm = float(row.get("supertrend_distance_norm", np.nan))
            perf_ama = float(row.get("perf_ama", value))

            if pd.isna(dist_norm):
                close_val = float(row.get("close", np.nan))
                if close_val and close_val == close_val:
                    dist_norm = float(abs(close_val - value) / close_val)

            return {
                "supertrend_value": value,
                "supertrend_trend": trend,
                "supertrend_factor": factor,
                "supertrend_performance_index": perf_idx,
                "supertrend_signal_strength": strength,
                "signal_confidence": confidence,
                "supertrend_confidence_norm": conf_norm,
                "supertrend_distance_norm": dist_norm,
                "perf_ama": perf_ama,
            }

        # Fallback: compute a basic SuperTrend using only historical data
        high = df["high"].values[: idx + 1]
        low = df["low"].values[: idx + 1]
        close = df["close"].values[: idx + 1]

        start = max(1, idx - atr_length + 1)
        high_window = high[start : idx + 1]
        low_window = low[start : idx + 1]
        close_window = close[start : idx + 1]

        if start > 0:
            prev_close = np.concatenate([close[start - 1 : start], close_window[:-1]])
        else:
            prev_close = np.concatenate([close_window[:1], close_window[:-1]])

        tr = np.maximum(
            high_window - low_window,
            np.maximum(
                np.abs(high_window - prev_close),
                np.abs(low_window - prev_close),
            ),
        )
        atr = float(np.mean(tr)) if len(tr) else np.nan

        hl2 = (high[-1] + low[-1]) / 2.0
        basic_upper = hl2 + (multiplier * atr)
        basic_lower = hl2 - (multiplier * atr)

        close_last = close[-1]
        supertrend_value = basic_lower if close_last > basic_upper else basic_upper
        supertrend_trend = 1 if close_last > supertrend_value else 0
        distance_norm = float(abs(close_last - supertrend_value) / close_last) if close_last else np.nan

        return {
            "supertrend_value": float(supertrend_value),
            "supertrend_trend": float(supertrend_trend),
            "supertrend_factor": float(multiplier),
            "supertrend_performance_index": 0.5,
            "supertrend_signal_strength": 5.0,
            "signal_confidence": 5.0,
            "supertrend_confidence_norm": 0.5,
            "supertrend_distance_norm": distance_norm,
            "perf_ama": float(supertrend_value),
        }

    @staticmethod
    def add_features_to_point(
        df: pd.DataFrame,
        idx: int,
        lookback: int = 50,
    ) -> dict:
        """
        Add features for point at idx using only data up to idx.

        If df already contains all SIMPLIFIED_FEATURES (e.g. from compute_simplified_features),
        returns only those columns plus ts. Otherwise computes bar-by-bar (legacy).
        """
        _ = lookback  # reserved for future use
        point = df.iloc[idx]
        ts_col = point.get("ts") if "ts" in point else point.get("date")

        # Use precomputed simplified features when present (no lookahead: row at idx only)
        if all(c in df.columns for c in SIMPLIFIED_FEATURES):
            features = {c: point[c] for c in SIMPLIFIED_FEATURES}
            features["ts"] = ts_col
            return features

        # Legacy bar-by-bar computation
        close_prices = df["close"].values[: idx + 1]
        high_prices = df["high"].values[: idx + 1]
        low_prices = df["low"].values[: idx + 1]
        _ = (high_prices, low_prices)
        volume_data = df["volume"].values[: idx + 1]
        _ = volume_data

        sma_20 = TemporalFeatureEngineer.compute_sma(close_prices, 20, idx)

        features = {
            "ts": ts_col,
            "close": point["close"],
            "volume": point["volume"],
            "high": point["high"],
            "low": point["low"],
            "sma_5": TemporalFeatureEngineer.compute_sma(close_prices, 5, idx),
            "sma_20": sma_20,
            "sma_50": TemporalFeatureEngineer.compute_sma(close_prices, 50, idx),
            "ema_12": TemporalFeatureEngineer.compute_ema(close_prices, 12, idx),
            "ema_26": TemporalFeatureEngineer.compute_ema(close_prices, 26, idx),
            "rsi_14": TemporalFeatureEngineer.compute_rsi(close_prices, 14, idx),
            "price_vs_sma20": (
                (point["close"] - sma_20) / point["close"] if point["close"] > 0 else 0
            ),
        }

        supertrend_features = TemporalFeatureEngineer.compute_supertrend_features(df, idx)
        features.update(supertrend_features)

        return features


def prepare_training_data_temporal(
    df: pd.DataFrame,
    horizon_days: int = 1,
    use_simplified_features: bool = True,
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Prepare training data with NO lookahead bias.

    If use_simplified_features is True (default), runs compute_simplified_features
    first and uses start_idx=200 (sma_200 + lags). Otherwise uses legacy bar-by-bar
    and start_idx=50.
    """
    if use_simplified_features and not all(c in df.columns for c in SIMPLIFIED_FEATURES):
        df = compute_simplified_features(df)

    engineer = TemporalFeatureEngineer()
    X_list: list[dict] = []
    y_list: list[str] = []

    horizon_days_int = max(1, int(np.ceil(horizon_days)))
    forward_returns = (
        df["close"].pct_change(periods=horizon_days_int).shift(-horizon_days_int).copy()
    )
    if horizon_days_int > 0:
        forward_returns.iloc[-horizon_days_int:] = np.nan

    # Simplified pipeline requires 200+ bars (sma_200 and lags)
    start_idx = 200 if all(c in df.columns for c in SIMPLIFIED_FEATURES) else 50

    for idx in range(start_idx, len(df) - horizon_days_int):
        features = engineer.add_features_to_point(df, idx, lookback=50)
        actual_return = forward_returns.iloc[idx]

        if pd.notna(actual_return):
            X_list.append(features)
            label = (
                "bullish"
                if actual_return > 0.02
                else "bearish" if actual_return < -0.02 else "neutral"
            )
            y_list.append(label)

    logger.info("Prepared %s temporal samples (no lookahead)", len(X_list))

    return pd.DataFrame(X_list), pd.Series(y_list)
