"""
Store unified predictions to Supabase.

Integrates the UnifiedValidator with the database layer to persist
validated predictions with drift analysis and reconciliation metadata.
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

from validation.unified_framework import (
    UnifiedValidator,
    ValidationScores,
    UnifiedPrediction,
)

logger = logging.getLogger(__name__)


class UnifiedPredictionStore:
    """
    Store and retrieve unified predictions from the database.

    Uses the ml_forecasts table with extended metadata in the points field.
    """

    def __init__(self, validator: Optional[UnifiedValidator] = None):
        """
        Initialize the prediction store.

        Args:
            validator: Optional UnifiedValidator instance (creates default if None)
        """
        self.validator = validator or UnifiedValidator()
        # Lazy import to avoid database connection at module load time
        from data.db import get_db
        self.db = get_db()

    def store_prediction(
        self,
        symbol: str,
        direction: str,
        backtesting_score: float,
        walkforward_score: float,
        live_score: float,
        multi_tf_scores: Optional[Dict[str, float]] = None,
        forecast_points: Optional[List[Dict]] = None,
    ) -> UnifiedPrediction:
        """
        Validate and store a unified prediction.

        Args:
            symbol: Trading symbol (e.g., "AAPL")
            direction: Prediction direction (BULLISH, BEARISH, NEUTRAL)
            backtesting_score: Historical accuracy (0-1)
            walkforward_score: Recent quarterly accuracy (0-1)
            live_score: Current prediction accuracy (0-1)
            multi_tf_scores: Optional timeframe scores
            forecast_points: Optional list of price forecast points

        Returns:
            UnifiedPrediction with reconciled confidence
        """
        # Create validation scores
        scores = ValidationScores(
            backtesting_score=backtesting_score,
            walkforward_score=walkforward_score,
            live_score=live_score,
            multi_tf_scores=multi_tf_scores or {},
        )

        # Validate and reconcile
        prediction = self.validator.validate(symbol, direction, scores)

        # Get symbol_id
        try:
            symbol_id = self.db.get_symbol_id(symbol)
        except ValueError:
            logger.error(f"Symbol {symbol} not found in database")
            raise

        # Prepare forecast points with unified metadata
        points_with_metadata = self._prepare_points(prediction, forecast_points)

        # Map direction to label
        label_map = {
            "BULLISH": "bullish",
            "BEARISH": "bearish",
            "NEUTRAL": "neutral",
        }
        overall_label = label_map.get(direction.upper(), "neutral")

        # Store to database
        self.db.upsert_forecast(
            symbol_id=symbol_id,
            horizon="unified",  # Special horizon for unified predictions
            overall_label=overall_label,
            confidence=prediction.unified_confidence,
            points=points_with_metadata,
        )

        logger.info(
            f"Stored unified prediction for {symbol}: "
            f"{direction} {prediction.unified_confidence:.1%} "
            f"(drift={prediction.drift_detected})"
        )

        return prediction

    def _prepare_points(
        self,
        prediction: UnifiedPrediction,
        forecast_points: Optional[List[Dict]] = None,
    ) -> List[Dict]:
        """
        Prepare forecast points with unified validation metadata.

        Embeds the validation results into the points array for storage.
        """
        # Start with any provided forecast points
        points = forecast_points or []

        # Add unified validation metadata as a special point
        metadata_point = {
            "type": "unified_validation",
            "ts": prediction.timestamp.isoformat(),
            "validation": {
                "unified_confidence": round(prediction.unified_confidence, 4),
                "component_scores": {
                    "backtesting": round(prediction.backtesting_score, 4),
                    "walkforward": round(prediction.walkforward_score, 4),
                    "live": round(prediction.live_score, 4),
                },
                "drift": {
                    "detected": prediction.drift_detected,
                    "magnitude": round(prediction.drift_magnitude, 4),
                    "severity": prediction.drift_severity,
                    "explanation": prediction.drift_explanation,
                },
                "multi_tf": {
                    "conflict": prediction.timeframe_conflict,
                    "consensus": prediction.consensus_direction,
                    "explanation": prediction.conflict_explanation,
                    "scores": prediction.multi_tf_consensus,
                },
                "adjustments": prediction.adjustments,
                "recommendation": prediction.recommendation,
                "retraining": {
                    "trigger": prediction.retraining_trigger,
                    "reason": prediction.retraining_reason,
                },
            },
        }

        points.append(metadata_point)
        return points

    def store_batch(
        self,
        predictions: List[Dict],
    ) -> List[UnifiedPrediction]:
        """
        Store multiple predictions in batch.

        Args:
            predictions: List of dicts with keys:
                - symbol: str
                - direction: str
                - backtesting_score: float
                - walkforward_score: float
                - live_score: float
                - multi_tf_scores: Optional[Dict[str, float]]

        Returns:
            List of UnifiedPrediction results
        """
        results = []

        for pred in predictions:
            try:
                result = self.store_prediction(
                    symbol=pred["symbol"],
                    direction=pred["direction"],
                    backtesting_score=pred["backtesting_score"],
                    walkforward_score=pred["walkforward_score"],
                    live_score=pred["live_score"],
                    multi_tf_scores=pred.get("multi_tf_scores"),
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to store prediction for {pred.get('symbol')}: {e}")

        logger.info(f"Stored {len(results)}/{len(predictions)} unified predictions")
        return results

    def get_latest_prediction(self, symbol: str) -> Optional[Dict]:
        """
        Retrieve the latest unified prediction for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Dict with prediction data or None if not found
        """
        try:
            symbol_id = self.db.get_symbol_id(symbol)
        except ValueError:
            return None

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT overall_label, confidence, points, run_at
                    FROM ml_forecasts
                    WHERE symbol_id = %s AND horizon = 'unified'
                    ORDER BY run_at DESC
                    LIMIT 1
                    """,
                    (symbol_id,),
                )
                row = cur.fetchone()

                if not row:
                    return None

                # Parse points to extract validation metadata
                points = row[2] if isinstance(row[2], list) else json.loads(row[2])
                validation_point = next(
                    (p for p in points if p.get("type") == "unified_validation"),
                    None,
                )

                return {
                    "symbol": symbol,
                    "direction": row[0].upper(),
                    "unified_confidence": row[1],
                    "run_at": row[3],
                    "validation": (
                        validation_point.get("validation") if validation_point else None
                    ),
                }

    def get_drift_alerts(self, min_severity: str = "moderate") -> List[Dict]:
        """
        Get all symbols with drift alerts at or above minimum severity.

        Args:
            min_severity: Minimum severity level (minor, moderate, severe, critical)

        Returns:
            List of symbols with drift alerts
        """
        severity_order = ["none", "minor", "moderate", "severe", "critical"]
        min_idx = severity_order.index(min_severity)

        alerts = []

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT s.ticker, f.confidence, f.points, f.run_at
                    FROM ml_forecasts f
                    JOIN symbols s ON f.symbol_id = s.id
                    WHERE f.horizon = 'unified'
                    ORDER BY f.run_at DESC
                    """
                )
                rows = cur.fetchall()

                seen_symbols = set()
                for row in rows:
                    symbol = row[0]
                    if symbol in seen_symbols:
                        continue
                    seen_symbols.add(symbol)

                    points = row[2] if isinstance(row[2], list) else json.loads(row[2])
                    validation_point = next(
                        (p for p in points if p.get("type") == "unified_validation"),
                        None,
                    )

                    if validation_point:
                        drift = validation_point.get("validation", {}).get("drift", {})
                        severity = drift.get("severity", "none")

                        if severity_order.index(severity) >= min_idx:
                            alerts.append({
                                "symbol": symbol,
                                "confidence": row[1],
                                "drift_severity": severity,
                                "drift_magnitude": drift.get("magnitude", 0),
                                "explanation": drift.get("explanation", ""),
                                "run_at": row[3],
                            })

        return alerts


def store_unified_prediction(
    symbol: str,
    direction: str,
    backtesting_score: float,
    walkforward_score: float,
    live_score: float,
    multi_tf_scores: Optional[Dict[str, float]] = None,
) -> UnifiedPrediction:
    """
    Convenience function to store a single unified prediction.

    Args:
        symbol: Trading symbol
        direction: Prediction direction
        backtesting_score: Historical accuracy
        walkforward_score: Recent quarterly accuracy
        live_score: Current prediction accuracy
        multi_tf_scores: Optional timeframe scores

    Returns:
        UnifiedPrediction with reconciled confidence
    """
    store = UnifiedPredictionStore()
    return store.store_prediction(
        symbol=symbol,
        direction=direction,
        backtesting_score=backtesting_score,
        walkforward_score=walkforward_score,
        live_score=live_score,
        multi_tf_scores=multi_tf_scores,
    )


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)

    store = UnifiedPredictionStore()

    # Store a prediction (requires database connection)
    try:
        result = store.store_prediction(
            symbol="AAPL",
            direction="BULLISH",
            backtesting_score=0.988,
            walkforward_score=0.78,
            live_score=0.40,
            multi_tf_scores={
                "M15": -0.48,
                "H1": -0.40,
                "D1": 0.60,
                "W1": 0.70,
            },
        )
        print(f"Stored prediction: {result.unified_confidence:.1%}")
    except Exception as e:
        print(f"Could not store prediction (DB may not be connected): {e}")
