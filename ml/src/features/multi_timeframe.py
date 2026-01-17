"""
Multi-Timeframe Feature Engineering for ML Models.

This module provides functionality to compute technical indicators across
multiple timeframes and align them for use in attention-based models.

Supported timeframes (matching ChartViewModel.availableTimeframes):
- m15: 15-minute bars
- h1: 1-hour bars
- d1: Daily bars
- w1: Weekly bars
"""

import logging
from typing import Callable, Dict, List, Optional

import pandas as pd

from .technical_indicators import add_all_technical_features

logger = logging.getLogger(__name__)


# Default timeframes aligned with Swift app ChartViewModel (and ML stack requirement)
DEFAULT_TIMEFRAMES = ["m15", "h1", "h4", "d1", "w1"]

# Columns to exclude from feature suffixing (raw OHLCV data)
OHLCV_COLUMNS = {"ts", "open", "high", "low", "close", "volume"}


class MultiTimeframeFeatures:
    """
    Compute indicators across multiple timeframes for attention-based models.

    This class handles:
    1. Computing technical indicators for each timeframe
    2. Aligning features to a common index (typically daily)
    3. Computing cross-timeframe alignment scores
    4. Preparing multi-timeframe feature matrices for ML models
    """

    def __init__(
        self,
        timeframes: Optional[List[str]] = None,
        indicators_func: Optional[Callable[[pd.DataFrame], pd.DataFrame]] = None,
    ):
        """
        Initialize MultiTimeframeFeatures.

        Args:
            timeframes: List of timeframes to process (default: m15, h1, d1, w1)
            indicators_func: Function to compute indicators on a DataFrame.
                           Default: add_all_technical_features
        """
        self.timeframes = timeframes or DEFAULT_TIMEFRAMES
        self.indicators_func = indicators_func or add_all_technical_features

        logger.info(f"MultiTimeframeFeatures initialized with timeframes: {self.timeframes}")

    def compute_single_timeframe(self, df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        """
        Compute indicators for a single timeframe.

        Args:
            df: DataFrame with OHLCV data for the timeframe
            timeframe: Timeframe identifier (e.g., 'd1', 'h1')

        Returns:
            DataFrame with indicator columns suffixed by timeframe
        """
        if df.empty:
            logger.warning(f"Empty DataFrame for timeframe {timeframe}")
            return pd.DataFrame()

        # Compute indicators
        df_with_indicators = self.indicators_func(df.copy())

        # Rename indicator columns with timeframe suffix
        rename_map = {}
        for col in df_with_indicators.columns:
            if col not in OHLCV_COLUMNS:
                rename_map[col] = f"{col}_{timeframe}"

        df_renamed = df_with_indicators.rename(columns=rename_map)

        logger.debug(f"Computed {len(rename_map)} indicators for {timeframe}")

        return df_renamed

    def compute_all_timeframes(
        self,
        data_dict: Dict[str, pd.DataFrame],
        align_to: str = "d1",
    ) -> pd.DataFrame:
        """
        Compute indicators for all timeframes and align to common index.

        Args:
            data_dict: Dictionary mapping timeframe to OHLCV DataFrame
                      e.g., {'m15': df_15m, 'h1': df_1h, 'd1': df_1d, 'w1': df_1w}
            align_to: Timeframe to use as the base index (default: 'd1')

        Returns:
            DataFrame with columns like 'rsi_14_m15', 'rsi_14_h1', 'rsi_14_d1', etc.
            aligned to the base timeframe's index
        """
        if not data_dict:
            logger.error("Empty data_dict provided")
            return pd.DataFrame()

        if align_to not in data_dict:
            logger.warning(
                f"Align-to timeframe '{align_to}' not in data_dict, using first available"
            )
            align_to = list(data_dict.keys())[0]

        # Process each timeframe
        processed_dfs = {}
        for tf in self.timeframes:
            if tf not in data_dict:
                logger.warning(f"Timeframe {tf} not in data_dict, skipping")
                continue

            df = data_dict[tf]
            if df.empty:
                logger.warning(f"Empty DataFrame for {tf}, skipping")
                continue

            processed_dfs[tf] = self.compute_single_timeframe(df, tf)

        if not processed_dfs:
            logger.error("No timeframes processed successfully")
            return pd.DataFrame()

        # Get base DataFrame for alignment
        base_df = processed_dfs[align_to].copy()

        # Ensure ts column is datetime
        if "ts" in base_df.columns:
            base_df["ts"] = pd.to_datetime(base_df["ts"])
            base_df = base_df.set_index("ts")

        # Merge other timeframes using forward-fill alignment
        for tf, df in processed_dfs.items():
            if tf == align_to:
                continue

            # Prepare for merge
            if "ts" in df.columns:
                df["ts"] = pd.to_datetime(df["ts"])
                df = df.set_index("ts")

            # Select only indicator columns (those with timeframe suffix)
            indicator_cols = [col for col in df.columns if col.endswith(f"_{tf}")]

            if not indicator_cols:
                continue

            # Resample to base timeframe using forward-fill
            df_aligned = self._align_to_base(df[indicator_cols], base_df.index, tf, align_to)

            # Merge with base
            base_df = base_df.join(df_aligned, how="left")

        # Reset index
        base_df = base_df.reset_index()

        logger.info(
            f"Computed multi-timeframe features: {len(base_df)} rows, "
            f"{len(base_df.columns)} columns"
        )

        return base_df

    def _align_to_base(
        self,
        df: pd.DataFrame,
        base_index: pd.DatetimeIndex,
        source_tf: str,
        target_tf: str,
    ) -> pd.DataFrame:
        """
        Align a higher/lower frequency DataFrame to the base index.

        For higher frequency data (e.g., m15 -> d1): use last value of each day
        For lower frequency data (e.g., w1 -> d1): forward-fill

        Args:
            df: DataFrame with DatetimeIndex
            base_index: Target DatetimeIndex to align to
            source_tf: Source timeframe
            target_tf: Target timeframe

        Returns:
            Aligned DataFrame
        """
        # Determine if source is higher or lower frequency
        tf_order = {"m15": 0, "h1": 1, "h4": 2, "d1": 3, "w1": 4}

        source_order = tf_order.get(source_tf, 3)
        target_order = tf_order.get(target_tf, 3)

        if source_order < target_order:
            # Higher frequency -> lower frequency: resample with last value
            # e.g., m15 -> d1: take last 15-min bar of each day
            if target_tf == "d1":
                df_resampled = df.resample("D").last()
            elif target_tf == "w1":
                df_resampled = df.resample("W").last()
            else:
                df_resampled = df.resample("D").last()
        else:
            # Lower frequency -> higher frequency: forward-fill
            df_resampled = df.reindex(base_index, method="ffill")
            return df_resampled

        # Align to base index
        df_aligned = df_resampled.reindex(base_index, method="ffill")

        return df_aligned

    def compute_alignment_score(self, features_df: pd.DataFrame) -> pd.Series:
        """
        Compute cross-timeframe trend alignment score.

        Higher score = more timeframes agree on direction.
        Score of 1.0 = all timeframes bullish
        Score of 0.0 = all timeframes bearish
        Score of 0.5 = mixed signals

        Args:
            features_df: DataFrame with multi-timeframe features

        Returns:
            Series with alignment scores (0-1)
        """
        # Look for trend-related columns across timeframes
        trend_indicators = []

        for tf in self.timeframes:
            # RSI-based trend (>50 = bullish)
            rsi_col = f"rsi_14_{tf}"
            if rsi_col in features_df.columns:
                trend_indicators.append((features_df[rsi_col] > 50).astype(float))

            # MACD-based trend (>0 = bullish)
            macd_col = f"macd_{tf}"
            if macd_col in features_df.columns:
                trend_indicators.append((features_df[macd_col] > 0).astype(float))

            # Price vs SMA20 (>0 = bullish)
            sma_col = f"price_vs_sma20_{tf}"
            if sma_col in features_df.columns:
                trend_indicators.append((features_df[sma_col] > 0).astype(float))

            # ADX direction (+DI > -DI = bullish)
            plus_di_col = f"plus_di_{tf}"
            minus_di_col = f"minus_di_{tf}"
            if plus_di_col in features_df.columns and minus_di_col in features_df.columns:
                trend_indicators.append(
                    (features_df[plus_di_col] > features_df[minus_di_col]).astype(float)
                )

        if not trend_indicators:
            logger.warning("No trend indicators found for alignment score")
            return pd.Series(0.5, index=features_df.index)

        # Average all trend signals
        alignment = pd.concat(trend_indicators, axis=1).mean(axis=1)

        logger.debug(f"Computed alignment score: mean={alignment.mean():.3f}")

        return alignment

    def compute_trend_strength(self, features_df: pd.DataFrame) -> pd.Series:
        """
        Compute overall trend strength across timeframes.

        Uses ADX values from each timeframe to determine trend strength.

        Args:
            features_df: DataFrame with multi-timeframe features

        Returns:
            Series with trend strength scores (0-100)
        """
        adx_cols = [f"adx_{tf}" for tf in self.timeframes if f"adx_{tf}" in features_df.columns]

        if not adx_cols:
            logger.warning("No ADX columns found for trend strength")
            return pd.Series(25.0, index=features_df.index)  # Default to weak trend

        # Average ADX across timeframes
        strength = features_df[adx_cols].mean(axis=1)

        logger.debug(f"Computed trend strength: mean={strength.mean():.1f}")

        return strength

    def aggregate_signals(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """
        Aggregate signals across all timeframes into a consensus signal.

        This is the key method for multi-timeframe signal fusion. It combines
        trend indicators from all timeframes and produces:
        - signal: 'buy', 'sell', or 'neutral'
        - confidence: 0.0 to 1.0 (how many TFs agree)
        - bullish_count: number of bullish timeframes
        - bearish_count: number of bearish timeframes
        - dominant_tf: which timeframe has strongest signal

        Args:
            features_df: DataFrame with multi-timeframe features

        Returns:
            DataFrame with aggregated signal columns
        """
        result = pd.DataFrame(index=features_df.index)

        # Collect signals from each timeframe
        tf_signals = {}
        tf_strengths = {}

        for tf in self.timeframes:
            # Build composite signal for this timeframe
            signals = []
            weights = []

            # RSI signal (weight: 1.0)
            rsi_col = f"rsi_14_{tf}"
            if rsi_col in features_df.columns:
                rsi = features_df[rsi_col]
                rsi_signal = pd.Series(0.0, index=features_df.index)
                rsi_signal[rsi > 60] = 1.0  # Bullish
                rsi_signal[rsi < 40] = -1.0  # Bearish
                rsi_signal[(rsi >= 40) & (rsi <= 60)] = 0.0  # Neutral
                signals.append(rsi_signal)
                weights.append(1.0)

            # MACD signal (weight: 1.5)
            macd_col = f"macd_{tf}"
            macd_signal_col = f"macd_signal_{tf}"
            if macd_col in features_df.columns:
                macd = features_df[macd_col]
                macd_sig = features_df.get(macd_signal_col, pd.Series(0, index=features_df.index))
                macd_signal = pd.Series(0.0, index=features_df.index)
                macd_signal[(macd > 0) & (macd > macd_sig)] = 1.0  # Bullish
                macd_signal[(macd < 0) & (macd < macd_sig)] = -1.0  # Bearish
                signals.append(macd_signal)
                weights.append(1.5)

            # Price vs SMA signal (weight: 1.0)
            sma_col = f"price_vs_sma20_{tf}"
            if sma_col in features_df.columns:
                sma_diff = features_df[sma_col]
                sma_signal = pd.Series(0.0, index=features_df.index)
                sma_signal[sma_diff > 0.02] = 1.0  # >2% above SMA = bullish
                sma_signal[sma_diff < -0.02] = -1.0  # >2% below SMA = bearish
                signals.append(sma_signal)
                weights.append(1.0)

            # ADX direction signal (weight: 1.5 if ADX > 25, else 0.5)
            plus_di_col = f"plus_di_{tf}"
            minus_di_col = f"minus_di_{tf}"
            adx_col = f"adx_{tf}"
            if plus_di_col in features_df.columns and minus_di_col in features_df.columns:
                plus_di = features_df[plus_di_col]
                minus_di = features_df[minus_di_col]
                adx = features_df.get(adx_col, pd.Series(25, index=features_df.index))

                di_signal = pd.Series(0.0, index=features_df.index)
                di_signal[plus_di > minus_di] = 1.0
                di_signal[plus_di < minus_di] = -1.0
                signals.append(di_signal)

                # Weight based on ADX strength
                adx_weight = pd.Series(0.5, index=features_df.index)
                adx_weight[adx > 25] = 1.5
                weights.append(adx_weight.mean())  # Use mean for simplicity

            # Compute weighted average signal for this timeframe
            if signals:
                weighted_signals = [s * w for s, w in zip(signals, weights)]
                total_weight = sum(weights)
                tf_signal = sum(weighted_signals) / total_weight
                tf_signals[tf] = tf_signal

                # Strength is absolute value of signal
                tf_strengths[tf] = tf_signal.abs()

        if not tf_signals:
            logger.warning("No signals computed from any timeframe")
            result["signal"] = "neutral"
            result["confidence"] = 0.0
            result["bullish_count"] = 0
            result["bearish_count"] = 0
            result["dominant_tf"] = None
            return result

        # Aggregate across timeframes
        all_signals = pd.DataFrame(tf_signals)
        all_strengths = pd.DataFrame(tf_strengths)

        # Count bullish/bearish timeframes
        result["bullish_count"] = (all_signals > 0.2).sum(axis=1)
        result["bearish_count"] = (all_signals < -0.2).sum(axis=1)

        # Average signal across timeframes
        avg_signal = all_signals.mean(axis=1)

        # Determine consensus signal
        result["signal"] = "neutral"
        result.loc[avg_signal > 0.3, "signal"] = "buy"
        result.loc[avg_signal < -0.3, "signal"] = "sell"

        # Confidence = agreement level (0-1)
        # High confidence when most TFs agree
        total_tfs = len(tf_signals)
        agreement = result[["bullish_count", "bearish_count"]].max(axis=1) / total_tfs
        result["confidence"] = agreement.clip(0, 1)

        # Dominant timeframe (strongest signal)
        result["dominant_tf"] = all_strengths.idxmax(axis=1)

        # Raw signal value for further processing
        result["signal_value"] = avg_signal

        logger.info(
            f"Aggregated signals: "
            f"buy={len(result[result['signal'] == 'buy'])}, "
            f"sell={len(result[result['signal'] == 'sell'])}, "
            f"neutral={len(result[result['signal'] == 'neutral'])}"
        )

        return result

    def compute_volatility_regime(self, features_df: pd.DataFrame) -> pd.Series:
        """
        Determine volatility regime across timeframes.

        Returns:
            Series with regime labels: 'low', 'normal', 'high'
        """
        vol_cols = [
            f"volatility_20d_{tf}"
            for tf in self.timeframes
            if f"volatility_20d_{tf}" in features_df.columns
        ]

        if not vol_cols:
            logger.warning("No volatility columns found")
            return pd.Series("normal", index=features_df.index)

        # Average volatility
        avg_vol = features_df[vol_cols].mean(axis=1)

        # Determine regime based on percentiles
        low_threshold = avg_vol.quantile(0.25)
        high_threshold = avg_vol.quantile(0.75)

        regime = pd.Series("normal", index=features_df.index)
        regime[avg_vol <= low_threshold] = "low"
        regime[avg_vol >= high_threshold] = "high"

        return regime

    def get_feature_columns(self, features_df: pd.DataFrame) -> List[str]:
        """
        Get list of feature columns (excluding metadata columns).

        Args:
            features_df: DataFrame with multi-timeframe features

        Returns:
            List of feature column names
        """
        exclude_cols = {"ts", "open", "high", "low", "close", "volume"}

        # Also exclude raw OHLCV columns with timeframe suffix
        for tf in self.timeframes:
            exclude_cols.update(
                {f"open_{tf}", f"high_{tf}", f"low_{tf}", f"close_{tf}", f"volume_{tf}"}
            )

        return [col for col in features_df.columns if col not in exclude_cols]

    def prepare_for_ml(
        self,
        features_df: pd.DataFrame,
        dropna: bool = True,
    ) -> pd.DataFrame:
        """
        Prepare multi-timeframe features for ML training.

        Args:
            features_df: DataFrame with multi-timeframe features
            dropna: Whether to drop rows with NaN values

        Returns:
            Clean DataFrame ready for ML training
        """
        feature_cols = self.get_feature_columns(features_df)

        # Keep ts and close for reference, plus all features
        keep_cols = ["ts", "close"] + [col for col in feature_cols if col in features_df.columns]

        result = features_df[keep_cols].copy()

        if dropna:
            original_len = len(result)
            result = result.dropna()
            dropped = original_len - len(result)
            if dropped > 0:
                logger.info(f"Dropped {dropped} rows with NaN values")

        logger.info(
            f"Prepared {len(result)} samples with {len(feature_cols)} features "
            f"across {len(self.timeframes)} timeframes"
        )

        return result


def fetch_multi_timeframe_data(
    symbol: str,
    timeframes: Optional[List[str]] = None,
    limit: Optional[int] = None,
) -> Dict[str, pd.DataFrame]:
    """
    Fetch OHLC data for multiple timeframes from the database.

    Args:
        symbol: Stock ticker symbol
        timeframes: List of timeframes to fetch (default: m15, h1, d1, w1)
        limit: Maximum bars per timeframe

    Returns:
        Dictionary mapping timeframe to DataFrame
    """
    from ..data.supabase_db import db

    timeframes = timeframes or DEFAULT_TIMEFRAMES
    data_dict = {}

    for tf in timeframes:
        try:
            df = db.fetch_ohlc_bars(symbol, timeframe=tf, limit=limit)
            if not df.empty:
                data_dict[tf] = df
                logger.info(f"Fetched {len(df)} bars for {symbol} ({tf})")
            else:
                logger.warning(f"No data for {symbol} ({tf})")
        except Exception as e:
            logger.error(f"Error fetching {symbol} ({tf}): {e}")

    return data_dict


def compute_multi_timeframe_features_for_symbol(
    symbol: str,
    timeframes: Optional[List[str]] = None,
    align_to: str = "d1",
    limit: Optional[int] = None,
) -> pd.DataFrame:
    """
    Convenience function to compute multi-timeframe features for a symbol.

    Args:
        symbol: Stock ticker symbol
        timeframes: List of timeframes (default: m15, h1, d1, w1)
        align_to: Base timeframe for alignment
        limit: Maximum bars per timeframe

    Returns:
        DataFrame with multi-timeframe features
    """
    # Fetch data
    data_dict = fetch_multi_timeframe_data(symbol, timeframes, limit)

    if not data_dict:
        logger.error(f"No data available for {symbol}")
        return pd.DataFrame()

    # Compute features
    mtf = MultiTimeframeFeatures(timeframes=timeframes)
    features_df = mtf.compute_all_timeframes(data_dict, align_to=align_to)

    # Add alignment and strength scores
    if not features_df.empty:
        features_df["tf_alignment"] = mtf.compute_alignment_score(features_df)
        features_df["tf_trend_strength"] = mtf.compute_trend_strength(features_df)
        features_df["tf_volatility_regime"] = mtf.compute_volatility_regime(features_df)

    return features_df
