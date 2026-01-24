"""
Forecast Weights - Calibrated weights for 3-layer forecast synthesis.

This module defines the weight configuration for combining:
- Layer 1: SuperTrend AI (momentum + trend)
- Layer 2: S/R Indicators (Pivot, Polynomial, Logistic)
- Layer 3: Ensemble ML (RF + GB consensus)
"""

import json
import os
from dataclasses import dataclass, field
from typing import Dict

from src.features.sr_correlation_analyzer import SRCorrelationAnalyzer


@dataclass
class ForecastWeights:
    """Calibrated weights for 3-layer forecast synthesis."""

    # Layer 1: SuperTrend weights
    supertrend_weights: Dict[str, float] = field(
        default_factory=lambda: {
            "trend_direction": 0.35,  # Trend bias importance
            "signal_strength": 0.25,  # Weight for strength score (0-10)
            "atr_volatility": 0.15,  # Volatility context
            "performance_index": 0.25,  # Historical quality (0-1)
        }
    )

    # Layer 2: S/R Indicator weights
    sr_weights: Dict[str, float] = field(
        default_factory=lambda: {
            "anchor_zones": 0.25,  # High-volume anchor zones
            "pivot_levels": 0.20,  # Multi-timeframe structure
            "polynomial": 0.20,  # Trend direction of S/R
            "moving_averages": 0.15,  # MA intersections
            "fibonacci": 0.10,  # Retracement levels
            "logistic": 0.10,  # ML probability
        }
    )

    # Layer 3: Ensemble ML weights
    ensemble_weights: Dict[str, float] = field(
        default_factory=lambda: {
            "base_confidence": 0.60,  # Raw ensemble probability
            "agreement_bonus": 0.40,  # RF/GB agreement + trend alignment
        }
    )

    # Final synthesis layer weights
    layer_weights: Dict[str, float] = field(
        default_factory=lambda: {
            "supertrend_component": 0.35,  # How much trend drives forecast
            "sr_component": 0.35,  # How much structure constrains
            "ensemble_component": 0.30,  # How much ML consensus influences
        }
    )

    # Confidence boost conditions
    confidence_boosts: Dict[str, float] = field(
        default_factory=lambda: {
            "all_layers_agree": 0.20,  # All 3 layers bullish/bearish
            "strong_agreement": 0.10,  # 2/3 layers agree
            "high_ensemble_conf": 0.15,  # Ensemble > 0.70
            "alignment_multiframe": 0.15,  # 1W: 3+ timeframes agree
            "strong_trend": 0.10,  # Signal strength >= 7/10
            "expanding_sr": 0.08,  # Polynomial diverging = room to move
        }
    )

    # Confidence penalty conditions
    confidence_penalties: Dict[str, float] = field(
        default_factory=lambda: {
            "weak_trend_strength": -0.15,  # Signal strength < 3/10
            "weak_ensemble_conf": -0.15,  # Ensemble < 0.55
            "conflicting_signals": -0.20,  # SuperTrend vs ML disagreement
            "strong_resistance": -0.10,  # High logistic resistance prob (>0.80)
            "strong_support": -0.10,  # High logistic support prob (bearish)
            "converging_sr": -0.05,  # Squeeze = limited move potential
        }
    )

    # Target calculation weights
    target_weights: Dict[str, float] = field(
        default_factory=lambda: {
            "supertrend_move": 0.40,  # ATR × strength based target
            "polynomial_forecast": 0.35,  # Polynomial extrapolation
            "sr_constraint": 0.25,  # Structure limit
        }
    )

    # Band calculation parameters
    band_params: Dict[str, float] = field(
        default_factory=lambda: {
            "sr_weight": 0.70,  # S/R level importance in bands
            "atr_weight": 0.30,  # ATR-based band component
            "volatility_expansion": 0.10,  # Band widening in high vol
            "min_band_pct": 0.5,  # Minimum band width (%)
            "max_band_pct": 5.0,  # Maximum band width (%)
        }
    )

    def validate(self) -> bool:
        """Ensure all weight groups sum to 1.0 (or close)."""
        groups = [
            ("supertrend_weights", self.supertrend_weights),
            ("sr_weights", self.sr_weights),
            ("ensemble_weights", self.ensemble_weights),
            ("layer_weights", self.layer_weights),
            ("target_weights", self.target_weights),
        ]

        for name, weights in groups:
            total = sum(weights.values())
            if abs(total - 1.0) > 0.01:
                print(f"[ForecastWeights] Warning: {name} sums to {total:.2f}, not 1.0")
                return False

        return True

    def adjust_for_symbol(self, symbol: str) -> "ForecastWeights":
        """
        Adjust weights based on symbol characteristics.
        Can be extended to load symbol-specific optimizations.
        """
        # High volatility symbols (e.g., meme stocks, small caps)
        high_vol_symbols = ["GME", "AMC", "BBBY", "TSLA"]

        # Low volatility symbols (e.g., utilities, bonds)
        low_vol_symbols = ["XLU", "TLT", "BND"]

        if symbol.upper() in high_vol_symbols:
            # Increase ATR weight for volatile symbols
            adjusted = ForecastWeights()
            adjusted.band_params["volatility_expansion"] = 0.20
            adjusted.target_weights["supertrend_move"] = 0.45
            adjusted.target_weights["polynomial_forecast"] = 0.30
            adjusted.target_weights["sr_constraint"] = 0.25
            return adjusted

        elif symbol.upper() in low_vol_symbols:
            # Decrease ATR weight for stable symbols
            adjusted = ForecastWeights()
            adjusted.band_params["volatility_expansion"] = 0.05
            adjusted.target_weights["supertrend_move"] = 0.35
            adjusted.target_weights["polynomial_forecast"] = 0.35
            adjusted.target_weights["sr_constraint"] = 0.30
            return adjusted

        return self

    def adjust_sr_weights_for_correlation(
        self,
        pivot_levels,
        polynomial_levels,
        logistic_levels,
    ) -> dict:
        """Adjust S/R weights based on indicator redundancy."""
        analyzer = SRCorrelationAnalyzer()
        result = analyzer.analyze(pivot_levels, polynomial_levels, logistic_levels)
        self.sr_weights = {
            "pivot_levels": result["adjusted_weights"]["pivot"],
            "polynomial": result["adjusted_weights"]["polynomial"],
            "logistic": result["adjusted_weights"]["logistic"],
        }
        return result

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "supertrend_weights": self.supertrend_weights,
            "sr_weights": self.sr_weights,
            "ensemble_weights": self.ensemble_weights,
            "layer_weights": self.layer_weights,
            "confidence_boosts": self.confidence_boosts,
            "confidence_penalties": self.confidence_penalties,
            "target_weights": self.target_weights,
            "band_params": self.band_params,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ForecastWeights":
        """Create from dictionary."""
        weights = cls()
        if "supertrend_weights" in data:
            weights.supertrend_weights.update(data["supertrend_weights"])
        if "sr_weights" in data:
            weights.sr_weights.update(data["sr_weights"])
        if "ensemble_weights" in data:
            weights.ensemble_weights.update(data["ensemble_weights"])
        if "layer_weights" in data:
            weights.layer_weights.update(data["layer_weights"])
        if "confidence_boosts" in data:
            weights.confidence_boosts.update(data["confidence_boosts"])
        if "confidence_penalties" in data:
            weights.confidence_penalties.update(data["confidence_penalties"])
        if "target_weights" in data:
            weights.target_weights.update(data["target_weights"])
        if "band_params" in data:
            weights.band_params.update(data["band_params"])
        return weights

    def save(self, filepath: str) -> None:
        """Save weights to JSON file."""
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        print(f"[ForecastWeights] Saved to {filepath}")

    @classmethod
    def load(cls, filepath: str) -> "ForecastWeights":
        """Load weights from JSON file."""
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                data = json.load(f)
            return cls.from_dict(data)
        else:
            print(f"[ForecastWeights] File not found: {filepath}, using defaults")
            return cls()


def get_default_weights() -> ForecastWeights:
    """Get default calibrated weights."""
    return ForecastWeights()


def optimize_weights(
    historical_forecasts: list, current_weights: ForecastWeights
) -> ForecastWeights:
    """
    Optimize weights based on historical forecast performance.

    Args:
        historical_forecasts: List of forecast dicts with outcomes
        current_weights: Current weight configuration

    Returns:
        Optimized ForecastWeights
    """
    if len(historical_forecasts) < 10:
        print("[optimize_weights] Not enough data for optimization, using current weights")
        return current_weights

    # Calculate accuracy per layer contribution
    supertrend_correct = 0
    ensemble_correct = 0
    sr_contained = 0
    total = len(historical_forecasts)

    for forecast in historical_forecasts:
        actual_direction = (
            "BULLISH"
            if forecast.get("actual_close", 0) > forecast.get("actual_open", 0)
            else "BEARISH"
        )

        # SuperTrend accuracy
        if forecast.get("supertrend_bias") == actual_direction:
            supertrend_correct += 1

        # Ensemble accuracy
        if forecast.get("ensemble_direction") == actual_direction:
            ensemble_correct += 1

        # S/R containment
        actual_high = forecast.get("actual_high", 0)
        actual_low = forecast.get("actual_low", 0)
        upper = forecast.get("upper_band", float("inf"))
        lower = forecast.get("lower_band", 0)

        if actual_high <= upper and actual_low >= lower:
            sr_contained += 1

    # Calculate accuracies
    st_acc = supertrend_correct / total if total > 0 else 0.5
    ens_acc = ensemble_correct / total if total > 0 else 0.5
    sr_acc = sr_contained / total if total > 0 else 0.5

    # Adjust layer weights inversely to weak performers
    # (diversify by boosting underperformers slightly)

    new_weights = ForecastWeights()

    # Rebalance layer weights
    new_weights.layer_weights["supertrend_component"] = min(
        0.45, max(0.25, 0.35 + (0.5 - st_acc) * 0.2)
    )
    new_weights.layer_weights["ensemble_component"] = min(
        0.40, max(0.20, 0.30 + (0.5 - ens_acc) * 0.2)
    )
    new_weights.layer_weights["sr_component"] = (
        1.0
        - new_weights.layer_weights["supertrend_component"]
        - new_weights.layer_weights["ensemble_component"]
    )

    # Adjust band params based on containment
    if sr_acc < 0.75:
        # Widen bands
        new_weights.band_params["sr_weight"] = 0.65
        new_weights.band_params["atr_weight"] = 0.35
        new_weights.band_params["volatility_expansion"] = 0.15
    elif sr_acc > 0.90:
        # Can tighten bands
        new_weights.band_params["sr_weight"] = 0.75
        new_weights.band_params["atr_weight"] = 0.25
        new_weights.band_params["volatility_expansion"] = 0.08

    print(
        f"[optimize_weights] ST acc: {st_acc:.1%}, Ens acc: {ens_acc:.1%}, S/R contain: {sr_acc:.1%}"
    )
    print(f"[optimize_weights] New layer weights: {new_weights.layer_weights}")

    return new_weights
