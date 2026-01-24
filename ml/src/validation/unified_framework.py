"""
Unified Validation Framework

Reconciles three validation metrics into a single confidence score:
1. Backtesting score (40% weight) - historical accuracy over 3 months
2. Walk-forward score (35% weight) - recent quarterly rolling accuracy
3. Live score (25% weight) - current prediction accuracy (last 30 predictions)

Outputs unified confidence with drift detection and multi-TF reconciliation.

Example:
    ```python
    from ml.src.validation import UnifiedValidator, ValidationScores

    validator = UnifiedValidator()

    scores = ValidationScores(
        backtesting_score=0.988,
        walkforward_score=0.78,
        live_score=0.40,
        multi_tf_scores={
            'M15': -0.48,
            'H1': -0.40,
            'D1': 0.60,
            'W1': 0.70
        }
    )

    result = validator.validate('AAPL', 'BULLISH', scores)
    print(f"Unified Confidence: {result.unified_confidence:.1%}")
    print(f"Drift Detected: {result.drift_detected}")
    ```
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Literal, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ValidationScores:
    """Component scores for validation from different sources."""

    backtesting_score: float  # 3-month historical accuracy (0-1)
    walkforward_score: float  # Recent quarterly accuracy (0-1)
    live_score: float  # Last 30 predictions accuracy (0-1)
    multi_tf_scores: Dict[str, float] = field(default_factory=dict)  # M15, H1, H4, D1, W1
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class UnifiedPrediction:
    """Output of unified validator with reconciled confidence."""

    symbol: str
    direction: str  # BULLISH, BEARISH, NEUTRAL
    unified_confidence: float  # 0-1, final reconciled score

    # Component breakdown
    backtesting_score: float
    walkforward_score: float
    live_score: float
    multi_tf_consensus: Dict[str, float]

    # Drift analysis
    drift_detected: bool
    drift_magnitude: float  # 0-1
    drift_severity: Literal["none", "minor", "moderate", "severe", "critical"]
    drift_explanation: str

    # Multi-timeframe reconciliation
    timeframe_conflict: bool
    conflict_explanation: str
    consensus_direction: str
    hierarchy_weights: Dict[str, float]

    # Recommendations
    recommendation: str
    retraining_trigger: bool
    retraining_reason: str
    next_retraining_date: Optional[datetime]

    # Adjustments applied
    adjustments: List[str]

    timestamp: datetime

    def to_dict(self) -> Dict:
        """Convert to dictionary for storage/serialization."""
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "unified_confidence": round(self.unified_confidence, 4),
            "backtesting_score": round(self.backtesting_score, 4),
            "walkforward_score": round(self.walkforward_score, 4),
            "live_score": round(self.live_score, 4),
            "drift_detected": self.drift_detected,
            "drift_magnitude": round(self.drift_magnitude, 4),
            "drift_severity": self.drift_severity,
            "drift_explanation": self.drift_explanation,
            "timeframe_conflict": self.timeframe_conflict,
            "consensus_direction": self.consensus_direction,
            "recommendation": self.recommendation,
            "retraining_trigger": self.retraining_trigger,
            "retraining_reason": self.retraining_reason,
            "adjustments": self.adjustments,
            "timestamp": self.timestamp.isoformat(),
        }

    def get_status_emoji(self) -> str:
        """Get status indicator for dashboard display."""
        if self.unified_confidence >= 0.75:
            return "🟢"  # High confidence
        elif self.unified_confidence >= 0.60:
            return "🟡"  # Moderate confidence
        elif self.unified_confidence >= 0.40:
            return "🟠"  # Low confidence
        else:
            return "🔴"  # Very low confidence


class UnifiedValidator:
    """
    Main validation reconciliation engine.

    Combines backtesting, walk-forward, and live validation scores
    with configurable weights and drift detection thresholds.
    """

    # Default weights (configurable)
    BACKTEST_WEIGHT = 0.40  # Historical accuracy weight
    WALKFORWARD_WEIGHT = 0.35  # Quarterly rolling weight
    LIVE_WEIGHT = 0.25  # Real-time accuracy weight

    # Drift thresholds
    DRIFT_MINOR_THRESHOLD = 0.15  # 15% divergence
    DRIFT_MODERATE_THRESHOLD = 0.25  # 25% divergence = flag as drift
    DRIFT_SEVERE_THRESHOLD = 0.50  # 50% = auto-investigate
    DRIFT_CRITICAL_THRESHOLD = 0.75  # 75% = consider retraining

    # Multi-timeframe hierarchy (longer = more weight in consensus)
    TF_HIERARCHY = {
        "W1": 0.35,  # Weekly: 35%
        "D1": 0.30,  # Daily: 30%
        "H4": 0.20,  # 4-hour: 20%
        "H1": 0.10,  # Hourly: 10%
        "M15": 0.05,  # 15-min: 5%
    }

    # Direction threshold for multi-TF scores
    BULLISH_THRESHOLD = 0.30
    BEARISH_THRESHOLD = -0.30

    def __init__(
        self,
        backtest_weight: float = 0.40,
        walkforward_weight: float = 0.35,
        live_weight: float = 0.25,
        last_retraining_date: Optional[datetime] = None,
    ):
        """
        Initialize validator with configurable weights.

        Args:
            backtest_weight: Weight for backtesting score (default 0.40)
            walkforward_weight: Weight for walk-forward score (default 0.35)
            live_weight: Weight for live score (default 0.25)
            last_retraining_date: Date of last model retraining
        """
        # Normalize weights to sum to 1.0
        total = backtest_weight + walkforward_weight + live_weight
        self.BACKTEST_WEIGHT = backtest_weight / total
        self.WALKFORWARD_WEIGHT = walkforward_weight / total
        self.LIVE_WEIGHT = live_weight / total

        self.last_retraining_date = last_retraining_date or (
            datetime.now() - timedelta(days=30)
        )

    def validate(
        self,
        symbol: str,
        direction: str,
        scores: ValidationScores,
    ) -> UnifiedPrediction:
        """
        Main validation method - reconciles all scores into unified prediction.

        Args:
            symbol: Trading symbol (AAPL, etc.)
            direction: BULLISH, BEARISH, or NEUTRAL
            scores: ValidationScores with component accuracies

        Returns:
            UnifiedPrediction with reconciled confidence and metadata
        """
        adjustments = []

        # Step 1: Calculate base unified confidence
        unified_conf = self._calculate_unified_confidence(scores)

        # Step 2: Detect drift
        drift_detected, drift_mag, drift_severity, drift_explain = self._detect_drift(
            scores
        )

        # Step 3: Reconcile multi-timeframe
        tf_conflict, conflict_explain, consensus_dir, weights = (
            self._reconcile_timeframes(scores.multi_tf_scores)
        )

        # Step 4: Apply adjustments
        adjusted_conf, new_adjustments = self._apply_adjustments(
            unified_conf,
            drift_detected,
            drift_mag,
            tf_conflict,
            consensus_dir,
            direction,
        )
        adjustments.extend(new_adjustments)

        # Step 5: Generate recommendation
        recommendation = self._generate_recommendation(adjusted_conf, adjustments)

        # Step 6: Check retraining trigger
        retrain_trigger, retrain_reason, next_retrain_date = (
            self._check_retraining_trigger(drift_mag, adjusted_conf)
        )

        return UnifiedPrediction(
            symbol=symbol,
            direction=direction,
            unified_confidence=adjusted_conf,
            backtesting_score=scores.backtesting_score,
            walkforward_score=scores.walkforward_score,
            live_score=scores.live_score,
            multi_tf_consensus=scores.multi_tf_scores,
            drift_detected=drift_detected,
            drift_magnitude=drift_mag,
            drift_severity=drift_severity,
            drift_explanation=drift_explain,
            timeframe_conflict=tf_conflict,
            conflict_explanation=conflict_explain,
            consensus_direction=consensus_dir,
            hierarchy_weights=weights,
            recommendation=recommendation,
            retraining_trigger=retrain_trigger,
            retraining_reason=retrain_reason,
            next_retraining_date=next_retrain_date,
            adjustments=adjustments,
            timestamp=scores.timestamp or datetime.now(),
        )

    def _calculate_unified_confidence(self, scores: ValidationScores) -> float:
        """
        Weighted average of three validation scores.

        Formula:
            unified = weight_bt * backtesting + weight_wf * walkforward + weight_live * live
        """
        unified = (
            self.BACKTEST_WEIGHT * scores.backtesting_score
            + self.WALKFORWARD_WEIGHT * scores.walkforward_score
            + self.LIVE_WEIGHT * scores.live_score
        )
        return min(1.0, max(0.0, unified))

    def _detect_drift(
        self, scores: ValidationScores
    ) -> Tuple[bool, float, str, str]:
        """
        Detect model drift by comparing live vs backtesting performance.

        Drift magnitude = |backtesting - live| / backtesting

        Returns:
            (drift_detected, drift_magnitude, severity, explanation)
        """
        if scores.backtesting_score == 0:
            return False, 0.0, "none", "No historical data for comparison"

        # Calculate drift magnitude
        drift_mag = abs(scores.backtesting_score - scores.live_score) / scores.backtesting_score

        # Determine severity and if drift is detected
        if drift_mag < self.DRIFT_MINOR_THRESHOLD:
            severity = "none"
            explanation = "Model stable, no significant drift detected"
            drift_detected = False
        elif drift_mag < self.DRIFT_MODERATE_THRESHOLD:
            severity = "minor"
            explanation = "Minor drift detected, continue monitoring"
            drift_detected = False
        elif drift_mag < self.DRIFT_SEVERE_THRESHOLD:
            severity = "moderate"
            explanation = f"Moderate drift ({drift_mag:.0%}), investigate cause"
            drift_detected = True
        elif drift_mag < self.DRIFT_CRITICAL_THRESHOLD:
            severity = "severe"
            explanation = f"Severe drift ({drift_mag:.0%}), model degraded significantly"
            drift_detected = True
        else:
            severity = "critical"
            explanation = f"Critical drift ({drift_mag:.0%}), immediate retraining recommended"
            drift_detected = True

        return drift_detected, drift_mag, severity, explanation

    def _reconcile_timeframes(
        self,
        multi_tf_scores: Dict[str, float],
    ) -> Tuple[bool, str, str, Dict[str, float]]:
        """
        Reconcile conflicting multi-timeframe predictions.

        Uses weighted voting based on timeframe hierarchy.

        Returns:
            (conflict_detected, explanation, consensus_direction, weights_used)
        """
        if not multi_tf_scores:
            return False, "No multi-TF data available", "UNKNOWN", {}

        # Normalize scores to directions
        predictions = {}
        for tf, score in multi_tf_scores.items():
            if score > self.BULLISH_THRESHOLD:
                predictions[tf] = "BULLISH"
            elif score < self.BEARISH_THRESHOLD:
                predictions[tf] = "BEARISH"
            else:
                predictions[tf] = "NEUTRAL"

        # Calculate weighted votes
        bullish_weight = sum(
            self.TF_HIERARCHY.get(tf, 0.05)
            for tf, pred in predictions.items()
            if pred == "BULLISH"
        )
        bearish_weight = sum(
            self.TF_HIERARCHY.get(tf, 0.05)
            for tf, pred in predictions.items()
            if pred == "BEARISH"
        )
        neutral_weight = sum(
            self.TF_HIERARCHY.get(tf, 0.05)
            for tf, pred in predictions.items()
            if pred == "NEUTRAL"
        )

        total_weight = bullish_weight + bearish_weight + neutral_weight

        if total_weight == 0:
            return False, "No valid predictions", "NEUTRAL", self.TF_HIERARCHY

        # Determine consensus
        if bullish_weight == bearish_weight:
            conflict_detected = True
            explanation = "Equal bullish/bearish weight - high uncertainty"
            consensus_dir = "NEUTRAL"
        elif abs(bullish_weight - bearish_weight) / total_weight < 0.15:
            # Close call (within 15% of each other)
            conflict_detected = True
            explanation = f"Weak consensus ({abs(bullish_weight - bearish_weight) / total_weight:.0%} margin)"
            consensus_dir = "BULLISH" if bullish_weight > bearish_weight else "BEARISH"
        else:
            conflict_detected = False
            explanation = "Strong consensus across timeframes"
            consensus_dir = "BULLISH" if bullish_weight > bearish_weight else "BEARISH"

        # Add detail about which timeframes agree/disagree
        bullish_tfs = [tf for tf, pred in predictions.items() if pred == "BULLISH"]
        bearish_tfs = [tf for tf, pred in predictions.items() if pred == "BEARISH"]

        if conflict_detected and bullish_tfs and bearish_tfs:
            explanation += f" (Bullish: {', '.join(bullish_tfs)}; Bearish: {', '.join(bearish_tfs)})"

        return conflict_detected, explanation, consensus_dir, self.TF_HIERARCHY

    def _apply_adjustments(
        self,
        base_confidence: float,
        drift_detected: bool,
        drift_mag: float,
        tf_conflict: bool,
        consensus_dir: str,
        prediction_dir: str,
    ) -> Tuple[float, List[str]]:
        """
        Apply confidence adjustments based on drift and conflict status.

        Returns:
            (adjusted_confidence, list_of_adjustments_applied)
        """
        adjusted = base_confidence
        adjustments = []

        # Drift penalty (scale with magnitude)
        if drift_detected:
            drift_penalty = min(0.30, drift_mag * 0.4)  # Max 30% penalty
            adjusted *= 1 - drift_penalty
            adjustments.append(f"Drift penalty: -{drift_penalty * 100:.1f}%")

        # Multi-TF conflict penalty
        if tf_conflict:
            adjusted *= 0.85  # 15% penalty for conflict
            adjustments.append("Multi-TF conflict: -15%")

        # Consensus alignment bonus
        if consensus_dir == prediction_dir and not tf_conflict:
            adjusted *= 1.08  # 8% bonus
            adjustments.append("Consensus alignment: +8%")

        # Clamp to valid range
        adjusted = min(1.0, max(0.0, adjusted))

        return adjusted, adjustments

    def _generate_recommendation(
        self,
        confidence: float,
        adjustments: List[str],
    ) -> str:
        """Generate actionable recommendation based on confidence level."""
        if confidence >= 0.75:
            base = "High confidence - strong signal"
        elif confidence >= 0.60:
            base = "Moderate confidence - trade with normal risk"
        elif confidence >= 0.45:
            base = "Low confidence - consider reduced position size"
        elif confidence >= 0.30:
            base = "Very low confidence - use tight stops or skip"
        else:
            base = "Insufficient confidence - avoid trading"

        return base

    def _check_retraining_trigger(
        self,
        drift_mag: float,
        confidence: float,
    ) -> Tuple[bool, str, Optional[datetime]]:
        """
        Determine if model should be retrained.

        Triggers:
        1. Critical drift (>75%)
        2. Severe drift persisting (>50% for extended period)
        3. Regular schedule (30 days)
        """
        days_since_retrain = (datetime.now() - self.last_retraining_date).days

        # Trigger 1: Critical drift
        if drift_mag > self.DRIFT_CRITICAL_THRESHOLD:
            return (
                True,
                f"Critical drift detected ({drift_mag:.0%})",
                datetime.now() + timedelta(hours=2),
            )

        # Trigger 2: Severe drift for extended period
        if drift_mag > self.DRIFT_SEVERE_THRESHOLD and days_since_retrain > 7:
            return (
                True,
                f"Persistent severe drift ({drift_mag:.0%}) for 7+ days",
                datetime.now() + timedelta(hours=6),
            )

        # Trigger 3: Regular retraining schedule (30 days)
        if days_since_retrain > 30:
            return (
                True,
                "Scheduled retraining (30-day cycle)",
                datetime.now() + timedelta(hours=12),
            )

        # No trigger
        next_scheduled = self.last_retraining_date + timedelta(days=30)
        return False, "Model within acceptable drift range", next_scheduled


def validate_prediction(
    symbol: str,
    direction: str,
    backtesting_score: float,
    walkforward_score: float,
    live_score: float,
    multi_tf_scores: Optional[Dict[str, float]] = None,
) -> UnifiedPrediction:
    """
    Convenience function to validate a single prediction.

    Args:
        symbol: Trading symbol
        direction: BULLISH, BEARISH, or NEUTRAL
        backtesting_score: Historical accuracy (0-1)
        walkforward_score: Recent quarterly accuracy (0-1)
        live_score: Current prediction accuracy (0-1)
        multi_tf_scores: Optional dict of timeframe scores

    Returns:
        UnifiedPrediction with reconciled confidence
    """
    validator = UnifiedValidator()
    scores = ValidationScores(
        backtesting_score=backtesting_score,
        walkforward_score=walkforward_score,
        live_score=live_score,
        multi_tf_scores=multi_tf_scores or {},
    )
    return validator.validate(symbol, direction, scores)


if __name__ == "__main__":
    # Example usage demonstrating the dashboard scenario from audit
    validator = UnifiedValidator()

    # Simulate the conflicting signals from the audit:
    # - Backtesting: 98.8%
    # - Walk-forward: 78%
    # - Live: 40%
    # - Multi-TF: M15 -48%, H1 -40%, D1 +60%, W1 +70%
    scores = ValidationScores(
        backtesting_score=0.988,
        walkforward_score=0.78,
        live_score=0.40,
        multi_tf_scores={
            "M15": -0.48,
            "H1": -0.40,
            "H4": -0.35,
            "D1": 0.60,
            "W1": 0.70,
        },
    )

    result = validator.validate("AAPL", "BULLISH", scores)

    print(f"\n{'=' * 60}")
    print(f"UNIFIED PREDICTION FOR {result.symbol}")
    print(f"{'=' * 60}")
    print(f"\nDirection: {result.direction}")
    print(f"Unified Confidence: {result.unified_confidence:.1%} {result.get_status_emoji()}")
    print(f"\nComponent Scores:")
    print(f"  Backtesting:  {result.backtesting_score:.1%}")
    print(f"  Walk-forward: {result.walkforward_score:.1%}")
    print(f"  Live:         {result.live_score:.1%}")
    print(f"\nDrift Analysis:")
    print(f"  Detected:   {result.drift_detected}")
    print(f"  Magnitude:  {result.drift_magnitude:.1%}")
    print(f"  Severity:   {result.drift_severity}")
    print(f"  Explanation: {result.drift_explanation}")
    print(f"\nMulti-Timeframe Reconciliation:")
    print(f"  Conflict:   {result.timeframe_conflict}")
    print(f"  Consensus:  {result.consensus_direction}")
    print(f"  Explanation: {result.conflict_explanation}")
    print(f"\nAdjustments Applied:")
    for adj in result.adjustments:
        print(f"  - {adj}")
    print(f"\nRecommendation: {result.recommendation}")
    print(f"\nRetraining:")
    print(f"  Trigger:  {result.retraining_trigger}")
    print(f"  Reason:   {result.retraining_reason}")
    if result.next_retraining_date:
        print(f"  Next:     {result.next_retraining_date.strftime('%Y-%m-%d %H:%M')}")
    print(f"\n{'=' * 60}")
