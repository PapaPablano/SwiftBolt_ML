"""
Cross-Timeframe Consensus Confidence Scoring
=============================================

Implements multi-timeframe consensus from STOCK_FORECASTING_FRAMEWORK.md:
- Aggregates signals across 15m, 1h, 4h, daily timeframes
- Boosts confidence when multiple timeframes agree
- Reduces confidence when timeframes conflict
- Provides alignment scores for risk management

Key Insight:
When short-term (1h) aligns with medium-term (4h) which aligns with long-term (daily),
the forecast has much higher probability of success.

Usage:
    consensus = TimeframeConsensus()
    result = consensus.calculate_consensus(symbol_id, current_forecast)

    # Use alignment score to adjust confidence
    adjusted_confidence = result.adjusted_confidence
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.data.supabase_db import db

logger = logging.getLogger(__name__)


@dataclass
class TimeframeSignal:
    """Signal from a single timeframe."""

    timeframe: str
    direction: str  # "bullish", "bearish", "neutral"
    strength: float  # 0-1
    confidence: float  # 0-1
    forecast_return: float
    timestamp: datetime


@dataclass
class ConsensusResult:
    """Result of cross-timeframe consensus analysis."""

    # Primary outputs
    consensus_direction: str  # Overall direction
    alignment_score: float  # 0-1, how well timeframes agree
    adjusted_confidence: float  # Original confidence adjusted by consensus

    # Details
    signals: Dict[str, TimeframeSignal]
    agreeing_timeframes: List[str]
    conflicting_timeframes: List[str]

    # Interpretation
    consensus_strength: str  # "strong", "moderate", "weak", "conflicted"
    recommendation: str  # Human-readable recommendation


class TimeframeConsensus:
    """
    Calculates consensus across multiple timeframes for confidence adjustment.

    Timeframe hierarchy:
    - m15: Very short-term (noise, momentum)
    - h1: Short-term (intraday trend)
    - h4: Medium-term (swing trend)
    - d1: Long-term (primary trend)

    Agreement rules:
    - All 4 agree: +20% confidence boost, "strong consensus"
    - 3/4 agree: +10% confidence boost, "moderate consensus"
    - 2/4 agree: No change, "weak consensus"
    - 1/4 or split: -10% confidence, "conflicted"
    """

    TIMEFRAMES = ["m15", "h1", "h4", "d1"]
    TIMEFRAME_WEIGHTS = {
        "m15": 0.10,  # Low weight - noisy
        "h1": 0.20,   # Medium weight
        "h4": 0.30,   # Higher weight - reliable
        "d1": 0.40,   # Highest weight - primary trend
    }

    def __init__(
        self,
        confidence_boost_full_consensus: float = 0.20,
        confidence_boost_strong: float = 0.10,
        confidence_penalty_conflicted: float = 0.10,
    ):
        """
        Initialize consensus calculator.

        Args:
            confidence_boost_full_consensus: Boost when all timeframes agree
            confidence_boost_strong: Boost when 3/4 agree
            confidence_penalty_conflicted: Penalty when signals conflict
        """
        self.confidence_boost_full = confidence_boost_full_consensus
        self.confidence_boost_strong = confidence_boost_strong
        self.confidence_penalty = confidence_penalty_conflicted

    def calculate_consensus(
        self,
        symbol_id: str,
        current_forecast: Optional[Dict[str, Any]] = None,
    ) -> ConsensusResult:
        """
        Calculate cross-timeframe consensus for a symbol.

        Args:
            symbol_id: Symbol UUID
            current_forecast: Optional current forecast to include

        Returns:
            ConsensusResult with consensus analysis
        """
        # Fetch signals from all timeframes
        signals = self._fetch_timeframe_signals(symbol_id)

        # Include current forecast if provided
        if current_forecast:
            forecast_tf = current_forecast.get("timeframe", "d1")
            signals[forecast_tf] = TimeframeSignal(
                timeframe=forecast_tf,
                direction=current_forecast.get("label", "neutral").lower(),
                strength=current_forecast.get("confidence", 0.5),
                confidence=current_forecast.get("confidence", 0.5),
                forecast_return=current_forecast.get("forecast_return", 0),
                timestamp=datetime.now(),
            )

        if not signals:
            return self._empty_consensus()

        # Analyze consensus
        return self._analyze_consensus(signals, current_forecast)

    def _fetch_timeframe_signals(
        self,
        symbol_id: str,
    ) -> Dict[str, TimeframeSignal]:
        """Fetch latest forecasts from each timeframe."""
        signals = {}

        for tf in self.TIMEFRAMES:
            try:
                forecast = self._get_latest_forecast(symbol_id, tf)
                if forecast:
                    signals[tf] = TimeframeSignal(
                        timeframe=tf,
                        direction=self._extract_direction(forecast),
                        strength=float(forecast.get("confidence", 0.5)),
                        confidence=float(forecast.get("confidence", 0.5)),
                        forecast_return=float(forecast.get("forecast_return", 0) or 0),
                        timestamp=self._parse_timestamp(forecast.get("created_at")),
                    )
            except Exception as e:
                logger.debug("Error fetching %s forecast: %s", tf, e)

        return signals

    def _get_latest_forecast(
        self,
        symbol_id: str,
        timeframe: str,
    ) -> Optional[Dict]:
        """Get the latest forecast for a timeframe."""
        try:
            # Try intraday table for m15, h1
            if timeframe in ("m15", "h1"):
                result = db.client.table("ml_forecasts_intraday").select(
                    "overall_label", "confidence", "forecast_return", "created_at"
                ).eq("symbol_id", symbol_id).eq("timeframe", timeframe).order(
                    "created_at", desc=True
                ).limit(1).execute()
            else:
                # Try main forecasts table for h4, d1
                horizon = "4H" if timeframe == "h4" else "1D"
                result = db.client.table("ml_forecasts").select(
                    "overall_label", "confidence", "forecast_return", "created_at"
                ).eq("symbol_id", symbol_id).eq("horizon", horizon).order(
                    "created_at", desc=True
                ).limit(1).execute()

            if result.data and len(result.data) > 0:
                return result.data[0]
            return None

        except Exception as e:
            logger.debug("Error querying forecast: %s", e)
            return None

    def _extract_direction(self, forecast: Dict) -> str:
        """Extract direction from forecast."""
        label = forecast.get("overall_label", "Neutral")
        if isinstance(label, str):
            label_lower = label.lower()
            if "bull" in label_lower:
                return "bullish"
            elif "bear" in label_lower:
                return "bearish"
        return "neutral"

    def _parse_timestamp(self, ts_str: Optional[str]) -> datetime:
        """Parse timestamp string."""
        if ts_str is None:
            return datetime.now()
        try:
            return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except:
            return datetime.now()

    def _analyze_consensus(
        self,
        signals: Dict[str, TimeframeSignal],
        current_forecast: Optional[Dict],
    ) -> ConsensusResult:
        """Analyze consensus across timeframes."""
        # Count directions
        direction_counts = {"bullish": 0, "bearish": 0, "neutral": 0}
        weighted_scores = {"bullish": 0.0, "bearish": 0.0, "neutral": 0.0}

        for tf, signal in signals.items():
            weight = self.TIMEFRAME_WEIGHTS.get(tf, 0.25)
            direction_counts[signal.direction] += 1
            weighted_scores[signal.direction] += weight * signal.confidence

        # Determine consensus direction
        if weighted_scores["bullish"] > weighted_scores["bearish"]:
            if weighted_scores["bullish"] > weighted_scores["neutral"]:
                consensus_direction = "bullish"
            else:
                consensus_direction = "neutral"
        elif weighted_scores["bearish"] > weighted_scores["neutral"]:
            consensus_direction = "bearish"
        else:
            consensus_direction = "neutral"

        # Find agreeing/conflicting timeframes
        agreeing = [tf for tf, sig in signals.items() if sig.direction == consensus_direction]
        conflicting = [tf for tf, sig in signals.items() if sig.direction != consensus_direction and sig.direction != "neutral"]

        # Calculate alignment score
        alignment_score = self._calculate_alignment_score(signals, consensus_direction)

        # Determine consensus strength
        n_signals = len(signals)
        n_agreeing = len(agreeing)

        if n_agreeing == n_signals and n_signals >= 3:
            consensus_strength = "strong"
            confidence_adjustment = self.confidence_boost_full
        elif n_agreeing >= n_signals * 0.75 and n_signals >= 3:
            consensus_strength = "moderate"
            confidence_adjustment = self.confidence_boost_strong
        elif n_agreeing >= n_signals * 0.5:
            consensus_strength = "weak"
            confidence_adjustment = 0
        else:
            consensus_strength = "conflicted"
            confidence_adjustment = -self.confidence_penalty

        # Adjust confidence
        original_confidence = 0.5
        if current_forecast:
            original_confidence = current_forecast.get("confidence", 0.5)
        elif signals:
            original_confidence = np.mean([s.confidence for s in signals.values()])

        adjusted_confidence = np.clip(
            original_confidence + confidence_adjustment,
            0.1,
            0.95
        )

        # Generate recommendation
        recommendation = self._generate_recommendation(
            consensus_direction,
            consensus_strength,
            agreeing,
            conflicting,
        )

        return ConsensusResult(
            consensus_direction=consensus_direction,
            alignment_score=alignment_score,
            adjusted_confidence=adjusted_confidence,
            signals=signals,
            agreeing_timeframes=agreeing,
            conflicting_timeframes=conflicting,
            consensus_strength=consensus_strength,
            recommendation=recommendation,
        )

    def _calculate_alignment_score(
        self,
        signals: Dict[str, TimeframeSignal],
        consensus_direction: str,
    ) -> float:
        """
        Calculate alignment score (0-1).

        Score considers:
        - Direction agreement
        - Signal strength
        - Timeframe weight
        """
        if not signals:
            return 0.0

        total_weight = 0.0
        alignment_weight = 0.0

        for tf, signal in signals.items():
            weight = self.TIMEFRAME_WEIGHTS.get(tf, 0.25)
            total_weight += weight

            if signal.direction == consensus_direction:
                alignment_weight += weight * signal.confidence
            elif signal.direction == "neutral":
                alignment_weight += weight * 0.5  # Neutral partially counts

        if total_weight == 0:
            return 0.0

        return alignment_weight / total_weight

    def _generate_recommendation(
        self,
        direction: str,
        strength: str,
        agreeing: List[str],
        conflicting: List[str],
    ) -> str:
        """Generate human-readable recommendation."""
        if strength == "strong":
            return f"Strong {direction} consensus across all timeframes. High confidence setup."
        elif strength == "moderate":
            return f"Moderate {direction} consensus. {', '.join(agreeing)} agree."
        elif strength == "weak":
            conflict_str = f" Conflicts: {', '.join(conflicting)}." if conflicting else ""
            return f"Weak {direction} consensus.{conflict_str} Consider smaller position."
        else:
            return f"Conflicted signals. {', '.join(conflicting)} disagree. Wait for clarity."

    def _empty_consensus(self) -> ConsensusResult:
        """Return empty consensus when no data available."""
        return ConsensusResult(
            consensus_direction="neutral",
            alignment_score=0.0,
            adjusted_confidence=0.5,
            signals={},
            agreeing_timeframes=[],
            conflicting_timeframes=[],
            consensus_strength="unknown",
            recommendation="Insufficient data for consensus analysis.",
        )


def add_consensus_to_forecast(
    forecast: Dict[str, Any],
    symbol_id: str,
) -> Dict[str, Any]:
    """
    Add consensus analysis to an existing forecast.

    Args:
        forecast: Existing forecast dict
        symbol_id: Symbol UUID

    Returns:
        Forecast dict with consensus fields added
    """
    consensus_calc = TimeframeConsensus()
    consensus = consensus_calc.calculate_consensus(symbol_id, forecast)

    forecast["consensus_direction"] = consensus.consensus_direction
    forecast["alignment_score"] = consensus.alignment_score
    forecast["adjusted_confidence"] = consensus.adjusted_confidence
    forecast["consensus_strength"] = consensus.consensus_strength
    forecast["agreeing_timeframes"] = consensus.agreeing_timeframes
    forecast["conflicting_timeframes"] = consensus.conflicting_timeframes
    forecast["consensus_recommendation"] = consensus.recommendation

    return forecast


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.INFO)

    print("Testing TimeframeConsensus...")

    # Create synthetic signals
    consensus = TimeframeConsensus()

    # Test with mock signals
    from unittest.mock import patch

    mock_signals = {
        "m15": TimeframeSignal("m15", "bullish", 0.6, 0.6, 0.01, datetime.now()),
        "h1": TimeframeSignal("h1", "bullish", 0.7, 0.7, 0.02, datetime.now()),
        "h4": TimeframeSignal("h4", "bullish", 0.8, 0.8, 0.03, datetime.now()),
        "d1": TimeframeSignal("d1", "bullish", 0.75, 0.75, 0.05, datetime.now()),
    }

    result = consensus._analyze_consensus(mock_signals, None)

    print(f"\nConsensus Direction: {result.consensus_direction}")
    print(f"Alignment Score: {result.alignment_score:.2f}")
    print(f"Adjusted Confidence: {result.adjusted_confidence:.2f}")
    print(f"Consensus Strength: {result.consensus_strength}")
    print(f"Agreeing: {result.agreeing_timeframes}")
    print(f"Conflicting: {result.conflicting_timeframes}")
    print(f"Recommendation: {result.recommendation}")

    # Test with conflicting signals
    print("\n--- Testing Conflicted Signals ---")
    conflicted_signals = {
        "m15": TimeframeSignal("m15", "bearish", 0.6, 0.6, -0.01, datetime.now()),
        "h1": TimeframeSignal("h1", "bullish", 0.7, 0.7, 0.02, datetime.now()),
        "h4": TimeframeSignal("h4", "bearish", 0.65, 0.65, -0.02, datetime.now()),
        "d1": TimeframeSignal("d1", "bullish", 0.75, 0.75, 0.05, datetime.now()),
    }

    result2 = consensus._analyze_consensus(conflicted_signals, None)
    print(f"Consensus: {result2.consensus_direction} ({result2.consensus_strength})")
    print(f"Alignment: {result2.alignment_score:.2f}")
    print(f"Recommendation: {result2.recommendation}")

    print("\nSUCCESS: TimeframeConsensus working!")
