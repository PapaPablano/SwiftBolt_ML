# flake8: noqa
"""
Helper utilities to convert S/R detector output into ML-ready features.

The goal is to compress rich indicator output (pivot levels, polynomial
regression, logistic regression probabilities) into a compact numeric vector
for the baseline and ensemble forecasters.
"""

from __future__ import annotations

from typing import Any, Dict

import numpy as np


def _safe_float(value: Any, default: float = np.nan) -> float:
    """Convert value to float if possible."""
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _avg_prob(levels: list[dict[str, Any]]) -> float:
    """Average probability from logistic levels."""
    if not levels:
        return 0.0
    probs = [_safe_float(level.get("probability"), np.nan) for level in levels]
    probs = [p for p in probs if not np.isnan(p)]
    if not probs:
        return 0.0
    return float(np.mean(probs))


def _max_prob(levels: list[dict[str, Any]]) -> float:
    """Max probability from logistic levels."""
    if not levels:
        return 0.0
    probs = [_safe_float(level.get("probability"), np.nan) for level in levels]
    probs = [p for p in probs if not np.isnan(p)]
    if not probs:
        return 0.0
    return float(np.max(probs))


def _level_density(levels: list[float], current_price: float, pct_window: float) -> int:
    """Count number of levels within +/- pct_window of current price."""
    if not current_price or not levels:
        return 0
    window = current_price * pct_window / 100
    return sum(1 for level in levels if level is not None and abs(level - current_price) <= window)


def build_sr_feature_map(sr_levels: Dict[str, Any]) -> Dict[str, float]:
    """
    Build a dictionary of engineered S/R features from detector output.

    Args:
        sr_levels: Output from SupportResistanceDetector.find_all_levels()

    Returns:
        Dict of feature_name -> value (floats or NaN)
    """
    features: Dict[str, float] = {}

    if not sr_levels:
        return features

    current_price = _safe_float(sr_levels.get("current_price"), np.nan)
    nearest_support = _safe_float(sr_levels.get("nearest_support"))
    nearest_resistance = _safe_float(sr_levels.get("nearest_resistance"))

    features["sr_nearest_support"] = nearest_support
    features["sr_nearest_resistance"] = nearest_resistance
    features["sr_support_distance_pct"] = _safe_float(sr_levels.get("support_distance_pct"))
    features["sr_resistance_distance_pct"] = _safe_float(sr_levels.get("resistance_distance_pct"))

    indicators = sr_levels.get("indicators", {})
    poly = indicators.get("polynomial", {})
    logistic = indicators.get("logistic", {})

    # Polynomial trend features
    features["sr_poly_support"] = _safe_float(poly.get("current_support"))
    features["sr_poly_resistance"] = _safe_float(poly.get("current_resistance"))
    features["sr_poly_support_slope"] = _safe_float(poly.get("support_slope"))
    features["sr_poly_resistance_slope"] = _safe_float(poly.get("resistance_slope"))
    features["sr_poly_is_diverging"] = float(bool(poly.get("is_diverging", False)))
    features["sr_poly_is_converging"] = float(bool(poly.get("is_converging", False)))

    # Logistic probability features
    support_levels = logistic.get("support_levels", [])
    resistance_levels = logistic.get("resistance_levels", [])
    features["sr_support_prob_avg"] = _avg_prob(support_levels)
    features["sr_support_prob_max"] = _max_prob(support_levels)
    features["sr_resistance_prob_avg"] = _avg_prob(resistance_levels)
    features["sr_resistance_prob_max"] = _max_prob(resistance_levels)
    features["sr_logistic_support_count"] = float(len(support_levels))
    features["sr_logistic_resistance_count"] = float(len(resistance_levels))

    # Pivot-level density signals
    supports = sr_levels.get("all_supports", [])
    resistances = sr_levels.get("all_resistances", [])
    features["sr_density_2pct"] = float(
        _level_density(supports + resistances, current_price, pct_window=2.0)
    )
    features["sr_density_5pct"] = float(
        _level_density(supports + resistances, current_price, pct_window=5.0)
    )

    # Signal counts
    signals = sr_levels.get("signals", []) or []
    features["sr_signal_count"] = float(len(signals))
    bullish_signals = sum(1 for sig in signals if "bull" in str(sig).lower())
    bearish_signals = sum(1 for sig in signals if "bear" in str(sig).lower())
    features["sr_signal_bullish"] = float(bullish_signals)
    features["sr_signal_bearish"] = float(bearish_signals)

    return features


def apply_sr_feature_columns(df, sr_levels: Dict[str, Any]):
    """
    Append S/R feature columns to the provided DataFrame (in-place).

    Args:
        df: pandas DataFrame returned from add_technical_features
        sr_levels: Support/Resistance detector output
    """
    feature_map = build_sr_feature_map(sr_levels)
    if not feature_map:
        return df

    for col, value in feature_map.items():
        df[col] = value
    return df
