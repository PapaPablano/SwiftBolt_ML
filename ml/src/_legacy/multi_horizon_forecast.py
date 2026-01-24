"""Multi-Horizon forecasting utilities for SwiftBolt ML."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.forecast_synthesizer import ForecastResult


@dataclass
class MultiHorizonForecast:
    """Multi-horizon forecast bundle for a specific timeframe."""

    timeframe: str
    symbol: str
    base_horizon: str  # Primary horizon (e.g., "4h" for M15)
    extended_horizons: List[str]  # Additional horizons
    forecasts: Dict[str, ForecastResult]  # horizon -> ForecastResult
    consensus_weights: Dict[str, float]  # horizon -> weight in consensus
    handoff_confidence: Dict[
        str, float
    ]  # horizon -> confidence in next timeframe

    # Metadata
    generated_at: Optional[str] = None
    current_price: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary for database storage."""
        return {
            "timeframe": self.timeframe,
            "symbol": self.symbol,
            "base_horizon": self.base_horizon,
            "extended_horizons": self.extended_horizons,
            "forecasts": {
                horizon: result.to_dict()
                for horizon, result in self.forecasts.items()
            },
            "consensus_weights": self.consensus_weights,
            "handoff_confidence": self.handoff_confidence,
            "generated_at": self.generated_at,
            "current_price": self.current_price,
            "metadata": self.metadata,
        }

    def get_primary_forecast(self) -> Optional[ForecastResult]:
        """Get the primary (base horizon) forecast."""
        return self.forecasts.get(self.base_horizon)

    def get_extended_forecast(self, horizon: str) -> Optional[ForecastResult]:
        """Get a specific extended horizon forecast."""
        return self.forecasts.get(horizon)


@dataclass
class CascadingConsensus:
    """
    Consensus forecast built from overlapping horizons across timeframes.

    Uses confidence weighting to combine predictions from multiple timeframes
    for the same time horizon (e.g., H4 30d + D1 30d).
    """

    horizon: str
    direction: str  # "BULLISH", "BEARISH", "NEUTRAL"
    confidence: float
    target: float
    upper_band: float
    lower_band: float

    # Contributing forecasts
    contributing_timeframes: List[str] = field(default_factory=list)
    timeframe_weights: Dict[str, float] = field(default_factory=dict)

    # Consensus metrics
    agreement_score: float = 0.0  # 0-1, how much timeframes agree
    handoff_quality: float = 0.0  # 0-1, quality of timeframe transitions

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "horizon": self.horizon,
            "direction": self.direction,
            "confidence": self.confidence,
            "target": self.target,
            "upper_band": self.upper_band,
            "lower_band": self.lower_band,
            "contributing_timeframes": self.contributing_timeframes,
            "timeframe_weights": self.timeframe_weights,
            "agreement_score": self.agreement_score,
            "handoff_quality": self.handoff_quality,
        }


def calculate_handoff_confidence(
    current_forecast: ForecastResult,
    next_timeframe_forecast: Optional[ForecastResult],
    horizon_days: float,
) -> float:
    """
    Calculate confidence in handing off to the next timeframe.

    High handoff confidence when:
    - Forecasts agree on direction
    - Confidence levels are similar
    - Targets are aligned

    Args:
        current_forecast: Forecast from current timeframe
        next_timeframe_forecast: Forecast from next timeframe (if available)
        horizon_days: Number of days in the forecast horizon

    Returns:
        Handoff confidence score (0-1)
    """
    if next_timeframe_forecast is None:
        # No next timeframe data, use current forecast confidence
        return current_forecast.confidence

    # Start with average of both confidences
    base_confidence = (
        current_forecast.confidence + next_timeframe_forecast.confidence
    ) / 2

    # Boost if directions agree
    direction_bonus = 0.0
    if current_forecast.direction == next_timeframe_forecast.direction:
        direction_bonus = 0.15
    elif (
        current_forecast.direction == "NEUTRAL"
        or next_timeframe_forecast.direction == "NEUTRAL"
    ):
        direction_bonus = 0.05

    # Boost if targets are aligned (within 10%)
    target_alignment = 0.0
    if current_forecast.target > 0 and next_timeframe_forecast.target > 0:
        target_diff_pct = (
            abs(current_forecast.target - next_timeframe_forecast.target)
            / current_forecast.target
        )

        if target_diff_pct < 0.05:  # Within 5%
            target_alignment = 0.10
        elif target_diff_pct < 0.10:  # Within 10%
            target_alignment = 0.05

    # Penalty if confidence levels diverge significantly
    confidence_penalty = 0.0
    confidence_diff = abs(
        current_forecast.confidence - next_timeframe_forecast.confidence
    )
    if confidence_diff > 0.30:
        confidence_penalty = -0.10
    elif confidence_diff > 0.20:
        confidence_penalty = -0.05

    handoff = (
        base_confidence
        + direction_bonus
        + target_alignment
        + confidence_penalty
    )
    return max(0.0, min(1.0, handoff))


def calculate_consensus_weights(
    forecasts: Dict[str, ForecastResult],
    base_horizon: str,
) -> Dict[str, float]:
    """
    Calculate consensus weights for each horizon forecast.

    Base horizon gets highest weight, extended horizons weighted by confidence.

    Args:
        forecasts: Dictionary of horizon -> ForecastResult
        base_horizon: Primary horizon identifier

    Returns:
        Dictionary of horizon -> weight (sums to 1.0)
    """
    if not forecasts:
        return {}

    weights = {}

    # Base horizon gets 50% weight
    if base_horizon in forecasts:
        weights[base_horizon] = 0.50

    # Extended horizons split remaining 50% by confidence
    extended = {h: f for h, f in forecasts.items() if h != base_horizon}
    if extended:
        total_confidence = sum(f.confidence for f in extended.values())

        if total_confidence > 0:
            remaining_weight = 0.50 if base_horizon in forecasts else 1.0
            for horizon, forecast in extended.items():
                weights[horizon] = (
                    forecast.confidence / total_confidence
                ) * remaining_weight

    # Normalize to ensure sum = 1.0
    total_weight = sum(weights.values())
    if total_weight > 0:
        weights = {h: w / total_weight for h, w in weights.items()}

    return weights


def build_cascading_consensus(
    all_forecasts: Dict[str, MultiHorizonForecast],
    target_horizon: str,
) -> Optional[CascadingConsensus]:
    """
    Build consensus forecast for a specific horizon across timeframes.

    Combines overlapping forecasts (e.g., H4 30d + D1 30d) using
    confidence weighting so shorter horizons influence near-term targets.

    Args:
        all_forecasts: Dictionary of timeframe -> MultiHorizonForecast
        target_horizon: Horizon to build consensus for (e.g., "30d")

    Returns:
        CascadingConsensus or None if no forecasts available
    """
    # Collect all forecasts for this horizon
    horizon_forecasts = {}
    for timeframe, mh_forecast in all_forecasts.items():
        if target_horizon in mh_forecast.forecasts:
            horizon_forecasts[timeframe] = mh_forecast.forecasts[
                target_horizon
            ]

    if not horizon_forecasts:
        return None

    # Calculate effective weights via timeframe weight, confidence, and handoff
    effective_weights = {}
    total_weight = 0.0

    for timeframe, forecast in horizon_forecasts.items():
        mh_forecast = all_forecasts[timeframe]

        # Shorter timeframes get more weight for near-term horizons
        timeframe_weight = _get_timeframe_weight(timeframe, target_horizon)

        # Get handoff confidence
        handoff = mh_forecast.handoff_confidence.get(target_horizon, 1.0)

        # Combine weights
        weight = timeframe_weight * forecast.confidence * handoff
        effective_weights[timeframe] = weight
        total_weight += weight

    # Normalize weights
    if total_weight > 0:
        effective_weights = {
            tf: w / total_weight for tf, w in effective_weights.items()
        }

    # Calculate weighted consensus across directions
    bullish_weight = 0.0
    bearish_weight = 0.0
    neutral_weight = 0.0

    weighted_target = 0.0
    weighted_upper = 0.0
    weighted_lower = 0.0
    weighted_confidence = 0.0

    for timeframe, forecast in horizon_forecasts.items():
        weight = effective_weights[timeframe]

        # Direction weights
        if forecast.direction == "BULLISH":
            bullish_weight += weight
        elif forecast.direction == "BEARISH":
            bearish_weight += weight
        else:
            neutral_weight += weight

        # Weighted averages
        weighted_target += forecast.target * weight
        weighted_upper += forecast.upper_band * weight
        weighted_lower += forecast.lower_band * weight
        weighted_confidence += forecast.confidence * weight

    # Determine consensus direction (require 20% threshold)
    if (
        bullish_weight > bearish_weight * 1.2
        and bullish_weight > neutral_weight
    ):
        direction = "BULLISH"
        agreement_score = bullish_weight
    elif (
        bearish_weight > bullish_weight * 1.2
        and bearish_weight > neutral_weight
    ):
        direction = "BEARISH"
        agreement_score = bearish_weight
    else:
        direction = "NEUTRAL"
        agreement_score = neutral_weight

    # Calculate handoff quality (average of all handoff confidences)
    handoff_scores = [
        all_forecasts[tf].handoff_confidence.get(target_horizon, 0.5)
        for tf in horizon_forecasts.keys()
    ]
    handoff_quality = (
        sum(handoff_scores) / len(handoff_scores) if handoff_scores else 0.5
    )

    return CascadingConsensus(
        horizon=target_horizon,
        direction=direction,
        confidence=round(weighted_confidence, 2),
        target=round(weighted_target, 2),
        upper_band=round(weighted_upper, 2),
        lower_band=round(weighted_lower, 2),
        contributing_timeframes=list(horizon_forecasts.keys()),
        timeframe_weights=effective_weights,
        agreement_score=round(agreement_score, 2),
        handoff_quality=round(handoff_quality, 2),
    )


def _get_timeframe_weight(timeframe: str, target_horizon: str) -> float:
    """
    Get weight for a timeframe based on target horizon.

    Shorter timeframes get more weight for near-term horizons,
    longer timeframes get more weight for far-term horizons.
    """
    # Parse horizon days
    horizon_days = _parse_horizon_days(target_horizon)

    # Timeframe priorities (shorter = higher priority for near-term)
    timeframe_order = {"m15": 0, "h1": 1, "h4": 2, "d1": 3, "w1": 4}
    tf_priority = timeframe_order.get(timeframe, 2)

    # Weight based on horizon length
    if horizon_days < 1:  # Intraday
        weights = [1.0, 0.8, 0.5, 0.3, 0.1]
    elif horizon_days <= 7:  # Week or less
        weights = [0.8, 1.0, 0.8, 0.5, 0.3]
    elif horizon_days <= 30:  # Month
        weights = [0.3, 0.5, 1.0, 0.9, 0.5]
    elif horizon_days <= 90:  # Quarter
        weights = [0.1, 0.3, 0.8, 1.0, 0.8]
    else:  # Long-term
        weights = [0.05, 0.1, 0.5, 0.8, 1.0]

    return weights[tf_priority]


def _parse_horizon_days(horizon: str) -> float:
    """Parse horizon string to days (e.g., '4h' -> 0.167, '30d' -> 30)."""
    horizon = horizon.lower().strip()

    if horizon.endswith("h"):
        hours = float(horizon[:-1])
        return hours / 24.0
    elif horizon.endswith("d"):
        return float(horizon[:-1])
    elif horizon.endswith("w"):
        weeks = float(horizon[:-1])
        return weeks * 7.0
    elif horizon.endswith("m"):
        months = float(horizon[:-1])
        return months * 30.0
    elif horizon.endswith("y"):
        years = float(horizon[:-1])
        return years * 365.0

    # Default: assume days
    try:
        return float(horizon)
    except ValueError:
        return 1.0
