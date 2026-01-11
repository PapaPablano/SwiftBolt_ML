"""
Multi-Timeframe Pivot Levels Detector.

Port of PivotLevelsIndicator.swift - BigBeluga-style multi-timeframe pivot levels
with ATR-based status coloring.

Detects pivot highs and lows across 4 timeframes (5, 25, 50, 100 bars) and
calculates status based on price position relative to ATR threshold.

Usage:
    from src.features.pivot_levels_detector import PivotLevelsDetector

    detector = PivotLevelsDetector()
    result = detector.calculate(df)

    # Access levels
    print(result["nearest_support"])
    print(result["nearest_resistance"])
    print(result["pivot_levels"])  # All multi-timeframe levels
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class PivotType(Enum):
    """Type of pivot point."""

    HIGH = "high"
    LOW = "low"


class PivotStatus(Enum):
    """Status of pivot level relative to current price.

    Matches Swift PivotStatus enum:
    - support: Price above level + ATR threshold (green)
    - resistance: Price below level - ATR threshold (orange)
    - active: Price within ATR threshold (blue)
    - inactive: Not calculated (gray)
    """

    SUPPORT = "support"
    RESISTANCE = "resistance"
    ACTIVE = "active"
    INACTIVE = "inactive"


@dataclass
class DetectedPivot:
    """A detected pivot point."""

    index: int
    price: float
    timestamp: Optional[pd.Timestamp] = None
    type: PivotType = PivotType.HIGH


@dataclass
class PivotLevel:
    """A pivot level for a specific period."""

    period: int
    level_high: float = 0.0
    level_low: float = 0.0
    start_index_high: int = 0
    start_index_low: int = 0
    high_status: PivotStatus = PivotStatus.INACTIVE
    low_status: PivotStatus = PivotStatus.INACTIVE

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "period": self.period,
            "level_high": self.level_high,
            "level_low": self.level_low,
            "start_index_high": self.start_index_high,
            "start_index_low": self.start_index_low,
            "high_status": self.high_status.value,
            "low_status": self.low_status.value,
        }


class PivotDetector:
    """
    Detects pivot highs and lows in price data.

    Matches PineScript ta.pivothigh() and ta.pivotlow() behavior.
    """

    @staticmethod
    def detect_pivots(
        bars: pd.DataFrame,
        period: int,
    ) -> Tuple[List[DetectedPivot], List[DetectedPivot]]:
        """
        Detect all pivot points for a specific period.

        Args:
            bars: DataFrame with 'high', 'low', and optionally 'ts' columns
            period: Number of bars on each side to confirm pivot

        Returns:
            Tuple of (pivot_highs, pivot_lows)
        """
        pivot_highs: List[DetectedPivot] = []
        pivot_lows: List[DetectedPivot] = []

        highs = bars["high"].values
        lows = bars["low"].values
        n = len(bars)

        if n <= period * 2:
            return ([], [])

        # Get timestamps if available
        has_ts = "ts" in bars.columns

        # Iterate through bars where we have enough lookback AND lookforward
        for i in range(period, n - period):
            bar_high = highs[i]
            bar_low = lows[i]

            # Check pivot high: current high must be >= all surrounding highs
            is_high = True
            for j in range(i - period, i):
                if highs[j] > bar_high:
                    is_high = False
                    break
            if is_high:
                for j in range(i + 1, i + period + 1):
                    if highs[j] > bar_high:
                        is_high = False
                        break

            if is_high:
                ts = bars["ts"].iloc[i] if has_ts else None
                pivot_highs.append(
                    DetectedPivot(
                        index=i,
                        price=float(bar_high),
                        timestamp=ts,
                        type=PivotType.HIGH,
                    )
                )

            # Check pivot low: current low must be <= all surrounding lows
            is_low = True
            for j in range(i - period, i):
                if lows[j] < bar_low:
                    is_low = False
                    break
            if is_low:
                for j in range(i + 1, i + period + 1):
                    if lows[j] < bar_low:
                        is_low = False
                        break

            if is_low:
                ts = bars["ts"].iloc[i] if has_ts else None
                pivot_lows.append(
                    DetectedPivot(
                        index=i,
                        price=float(bar_low),
                        timestamp=ts,
                        type=PivotType.LOW,
                    )
                )

        return (pivot_highs, pivot_lows)

    @staticmethod
    def get_most_recent_pivots(
        bars: pd.DataFrame,
        period: int,
    ) -> Dict[str, Any]:
        """
        Get the most recent pivot high and low for a period.

        Equivalent to PineScript's ta.valuewhen(not na(ph), high[len], 0)

        Args:
            bars: DataFrame with 'high', 'low' columns
            period: Number of bars on each side to confirm pivot

        Returns:
            Dict with high, high_index, low, low_index
        """
        highs, lows = PivotDetector.detect_pivots(bars, period)

        recent_high = highs[-1] if highs else None
        recent_low = lows[-1] if lows else None

        return {
            "high": recent_high.price if recent_high else None,
            "high_index": recent_high.index if recent_high else None,
            "low": recent_low.price if recent_low else None,
            "low_index": recent_low.index if recent_low else None,
        }


@dataclass
class PivotLevelsSettings:
    """Settings for PivotLevelsDetector."""

    # Multi-timeframe periods
    period1_enabled: bool = True
    period1_length: int = 5  # Micro structure

    period2_enabled: bool = True
    period2_length: int = 25  # Short-term

    period3_enabled: bool = True
    period3_length: int = 50  # Medium-term

    period4_enabled: bool = True
    period4_length: int = 100  # Long-term macro

    # ATR-based color sensitivity
    # PineScript: atr = ta.atr(200) * 1.5
    atr_period: int = 200
    atr_multiplier: float = 1.5


class PivotLevelsDetector:
    """
    BigBeluga-style multi-timeframe pivot levels detector.

    Matches the TradingView "Pivot Levels [BigBeluga]" indicator.
    Detects pivots across 4 timeframes (5, 25, 50, 100 bars) and calculates
    status based on price position relative to ATR threshold.
    """

    def __init__(self, settings: Optional[PivotLevelsSettings] = None):
        """
        Initialize the detector.

        Args:
            settings: Configuration settings (uses defaults if not provided)
        """
        self.settings = settings or PivotLevelsSettings()
        self._current_atr: float = 0.0
        self._pivot_levels: List[PivotLevel] = []

    @property
    def enabled_periods(self) -> List[int]:
        """Get list of enabled period lengths."""
        periods = []
        if self.settings.period1_enabled:
            periods.append(self.settings.period1_length)
        if self.settings.period2_enabled:
            periods.append(self.settings.period2_length)
        if self.settings.period3_enabled:
            periods.append(self.settings.period3_length)
        if self.settings.period4_enabled:
            periods.append(self.settings.period4_length)
        return periods

    def calculate(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate pivot levels for given OHLC data.

        Args:
            df: DataFrame with 'high', 'low', 'close' columns

        Returns:
            Dict with:
            - pivot_levels: List of PivotLevel dicts for each period
            - nearest_support: Nearest support level
            - nearest_resistance: Nearest resistance level
            - support_distance_pct: Distance to support as percentage
            - resistance_distance_pct: Distance to resistance as percentage
            - atr_threshold: Current ATR * multiplier
        """
        if df.empty:
            return self._empty_result()

        # Calculate ATR threshold
        self._calculate_atr_threshold(df)

        # Detect pivots for each enabled period
        self._detect_all_pivots(df)

        # Update colors based on current price vs pivot levels
        self._update_pivot_statuses(df)

        # Calculate nearest support and resistance
        current_price = df["close"].iloc[-1]
        nearest_support, support_dist = self._find_nearest_support(current_price)
        nearest_resistance, resistance_dist = self._find_nearest_resistance(current_price)

        # Log results
        logger.info(
            f"PivotLevels: {len(self._pivot_levels)} periods calculated, "
            f"ATR threshold={self._current_atr:.4f}, "
            f"support={nearest_support}, resistance={nearest_resistance}"
        )

        return {
            "pivot_levels": [pl.to_dict() for pl in self._pivot_levels],
            "nearest_support": nearest_support,
            "nearest_resistance": nearest_resistance,
            "support_distance_pct": support_dist,
            "resistance_distance_pct": resistance_dist,
            "atr_threshold": self._current_atr,
            "current_price": float(current_price),
        }

    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result structure."""
        return {
            "pivot_levels": [],
            "nearest_support": None,
            "nearest_resistance": None,
            "support_distance_pct": None,
            "resistance_distance_pct": None,
            "atr_threshold": 0.0,
            "current_price": None,
        }

    def _calculate_atr_threshold(self, df: pd.DataFrame) -> None:
        """
        Calculate ATR threshold = ATR(200) * 1.5

        PineScript: atr = ta.atr(200) * 1.5
        """
        atr_period = self.settings.atr_period

        if len(df) <= atr_period:
            self._current_atr = 0.0
            return

        # Calculate true range for each bar
        highs = df["high"].values
        lows = df["low"].values
        closes = df["close"].values

        true_ranges = np.zeros(len(df))
        true_ranges[0] = highs[0] - lows[0]

        for i in range(1, len(df)):
            prev_close = closes[i - 1]
            tr = max(highs[i] - lows[i], abs(highs[i] - prev_close), abs(lows[i] - prev_close))
            true_ranges[i] = tr

        # Calculate ATR using Wilder's smoothing (EMA)
        atr = np.mean(true_ranges[:atr_period])

        for i in range(atr_period, len(df)):
            atr = (atr * (atr_period - 1) + true_ranges[i]) / atr_period

        # Apply multiplier
        self._current_atr = atr * self.settings.atr_multiplier

    def _detect_all_pivots(self, df: pd.DataFrame) -> None:
        """Detect pivots for all enabled periods."""
        self._pivot_levels = []

        for period in self.enabled_periods:
            pivot_data = PivotDetector.get_most_recent_pivots(df, period)

            # Need at least one pivot (high or low)
            if pivot_data["high"] is None and pivot_data["low"] is None:
                continue

            level = PivotLevel(
                period=period,
                level_high=pivot_data["high"] or 0.0,
                level_low=pivot_data["low"] or 0.0,
                start_index_high=pivot_data["high_index"] or len(df) - 1,
                start_index_low=pivot_data["low_index"] or len(df) - 1,
                high_status=PivotStatus.INACTIVE,
                low_status=PivotStatus.INACTIVE,
            )
            self._pivot_levels.append(level)

    def _update_pivot_statuses(self, df: pd.DataFrame) -> None:
        """
        Update pivot statuses based on current price position.

        PineScript:
          color1 = low > H+atr ? colorSup : high < H-atr ? colorRes : colorActive
          color2 = low > L+atr ? colorSup : high < L-atr ? colorRes : colorActive
        """
        if df.empty:
            return

        last_bar = df.iloc[-1]
        last_low = last_bar["low"]
        last_high = last_bar["high"]

        for i, level in enumerate(self._pivot_levels):
            # HIGH pivot color logic
            if level.level_high > 0:
                if last_low > level.level_high + self._current_atr:
                    level.high_status = PivotStatus.SUPPORT
                elif last_high < level.level_high - self._current_atr:
                    level.high_status = PivotStatus.RESISTANCE
                else:
                    level.high_status = PivotStatus.ACTIVE

            # LOW pivot color logic
            if level.level_low > 0:
                if last_low > level.level_low + self._current_atr:
                    level.low_status = PivotStatus.SUPPORT
                elif last_high < level.level_low - self._current_atr:
                    level.low_status = PivotStatus.RESISTANCE
                else:
                    level.low_status = PivotStatus.ACTIVE

            self._pivot_levels[i] = level

    def _find_nearest_support(
        self, current_price: float
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Find nearest support level below current price.

        Returns:
            Tuple of (support_price, distance_pct)
        """
        supports = []

        for level in self._pivot_levels:
            # Low pivots that are below current price are support
            if level.level_low > 0 and level.level_low < current_price:
                supports.append(level.level_low)
            # High pivots in support status (price above them)
            if level.level_high > 0 and level.level_high < current_price:
                supports.append(level.level_high)

        if not supports:
            return (None, None)

        # Get nearest (highest) support
        nearest = max(supports)
        distance_pct = (current_price - nearest) / current_price * 100

        return (nearest, round(distance_pct, 2))

    def _find_nearest_resistance(
        self, current_price: float
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Find nearest resistance level above current price.

        Returns:
            Tuple of (resistance_price, distance_pct)
        """
        resistances = []

        for level in self._pivot_levels:
            # High pivots that are above current price are resistance
            if level.level_high > 0 and level.level_high > current_price:
                resistances.append(level.level_high)
            # Low pivots in resistance status (price below them)
            if level.level_low > 0 and level.level_low > current_price:
                resistances.append(level.level_low)

        if not resistances:
            return (None, None)

        # Get nearest (lowest) resistance
        nearest = min(resistances)
        distance_pct = (nearest - current_price) / current_price * 100

        return (nearest, round(distance_pct, 2))

    def add_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add pivot level features to DataFrame for ML.

        Adds columns:
        - pivot_nearest_support: Nearest support level
        - pivot_nearest_resistance: Nearest resistance level
        - pivot_support_distance_pct: Distance to support
        - pivot_resistance_distance_pct: Distance to resistance
        - pivot_sr_ratio: Ratio of distances

        Args:
            df: DataFrame with OHLC data

        Returns:
            DataFrame with pivot features added
        """
        df = df.copy()

        result = self.calculate(df)

        df["pivot_nearest_support"] = result["nearest_support"]
        df["pivot_nearest_resistance"] = result["nearest_resistance"]
        df["pivot_support_distance_pct"] = result["support_distance_pct"]
        df["pivot_resistance_distance_pct"] = result["resistance_distance_pct"]

        # S/R ratio (>1 means closer to support)
        if result["support_distance_pct"] and result["resistance_distance_pct"]:
            if result["support_distance_pct"] > 0:
                df["pivot_sr_ratio"] = (
                    result["resistance_distance_pct"] / result["support_distance_pct"]
                )
            else:
                df["pivot_sr_ratio"] = np.nan
        else:
            df["pivot_sr_ratio"] = np.nan

        return df


def add_pivot_level_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convenience function to add pivot level features to a DataFrame.

    Args:
        df: DataFrame with OHLC data

    Returns:
        DataFrame with pivot features added
    """
    detector = PivotLevelsDetector()
    return detector.add_features(df)
