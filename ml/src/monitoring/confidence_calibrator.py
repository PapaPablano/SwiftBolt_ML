"""Confidence calibration for forecast validation.

Validates and adjusts confidence scores based on historical accuracy.
If predicted confidence is 80% but actual accuracy is 60%, the calibrator
will apply an adjustment factor of 0.75 to future predictions.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class CalibrationResult:
    """Calibration analysis result for a confidence bucket."""

    bucket: str  # e.g., "70-80%"
    predicted_confidence: float  # Average confidence in bucket
    actual_accuracy: float  # Actual hit rate
    n_samples: int
    is_calibrated: bool  # Within 10% of predicted
    adjustment_factor: float  # Multiply confidence by this


class ConfidenceCalibrator:
    """
    Validates and adjusts confidence scores based on historical accuracy.

    Usage:
        calibrator = ConfidenceCalibrator()
        calibrator.fit(historical_forecasts)
        adjusted_confidence = calibrator.calibrate(raw_confidence)
    """

    BUCKETS = [
        (0.4, 0.5),
        (0.5, 0.6),
        (0.6, 0.7),
        (0.7, 0.8),
        (0.8, 0.9),
        (0.9, 1.0),
    ]

    def __init__(self) -> None:
        self.calibration_map: Dict[Tuple[float, float], float] = {}
        self.is_fitted = False

    def fit(
        self,
        forecasts: pd.DataFrame,
        min_samples_per_bucket: int = 30,
    ) -> List[CalibrationResult]:
        """
        Fit calibration model on historical forecasts.

        Args:
            forecasts: DataFrame with 'confidence', 'predicted_label', 'actual_label'
            min_samples_per_bucket: Minimum samples to compute adjustment

        Returns:
            List of CalibrationResult for each bucket
        """
        results = []

        for low, high in self.BUCKETS:
            bucket_mask = (forecasts["confidence"] >= low) & (
                forecasts["confidence"] < high
            )
            bucket_data = forecasts[bucket_mask]

            if len(bucket_data) < min_samples_per_bucket:
                # Not enough data, use 1.0 (no adjustment)
                self.calibration_map[(low, high)] = 1.0
                logger.debug(
                    f"Bucket {int(low*100)}-{int(high*100)}%: insufficient samples "
                    f"({len(bucket_data)} < {min_samples_per_bucket}), using 1.0"
                )
                continue

            # Calculate actual accuracy
            correct = (
                bucket_data["predicted_label"] == bucket_data["actual_label"]
            ).sum()
            actual_accuracy = correct / len(bucket_data)
            predicted_confidence = bucket_data["confidence"].mean()

            # Calculate adjustment factor
            # If predicted 75% but actual 60%, factor = 60/75 = 0.8
            if predicted_confidence > 0:
                adjustment = actual_accuracy / predicted_confidence
            else:
                adjustment = 1.0
            adjustment = np.clip(adjustment, 0.5, 1.5)  # Limit extreme adjustments

            self.calibration_map[(low, high)] = adjustment

            results.append(
                CalibrationResult(
                    bucket=f"{int(low*100)}-{int(high*100)}%",
                    predicted_confidence=predicted_confidence,
                    actual_accuracy=actual_accuracy,
                    n_samples=len(bucket_data),
                    is_calibrated=abs(actual_accuracy - predicted_confidence) < 0.10,
                    adjustment_factor=adjustment,
                )
            )

            logger.info(
                f"Bucket {int(low*100)}-{int(high*100)}%: "
                f"predicted={predicted_confidence:.2%}, actual={actual_accuracy:.2%}, "
                f"adjustment={adjustment:.2f}, n={len(bucket_data)}"
            )

        self.is_fitted = True
        return results

    def calibrate(self, confidence: float) -> float:
        """
        Apply calibration adjustment to raw confidence.

        Args:
            confidence: Raw confidence score (0-1)

        Returns:
            Calibrated confidence score
        """
        if not self.is_fitted:
            return confidence

        for (low, high), adjustment in self.calibration_map.items():
            if low <= confidence < high:
                calibrated = np.clip(confidence * adjustment, 0.40, 0.95)
                return float(calibrated)

        return confidence

    def calibrate_batch(self, confidences: pd.Series) -> pd.Series:
        """
        Apply calibration to a batch of confidence scores.

        Args:
            confidences: Series of raw confidence scores

        Returns:
            Series of calibrated confidence scores
        """
        return confidences.apply(self.calibrate)

    def get_calibration_report(self) -> str:
        """Generate human-readable calibration report."""
        if not self.is_fitted:
            return "Calibrator not fitted. Call fit() with historical data."

        lines = ["Confidence Calibration Report", "=" * 40]
        for (low, high), adjustment in self.calibration_map.items():
            status = "OK" if 0.9 <= adjustment <= 1.1 else "ADJUST"
            lines.append(f"{int(low*100)}-{int(high*100)}%: x{adjustment:.2f} [{status}]")

        return "\n".join(lines)

    def get_calibration_stats(self) -> Dict:
        """Get calibration statistics as a dictionary."""
        if not self.is_fitted:
            return {"is_fitted": False}

        stats = {
            "is_fitted": True,
            "buckets": {},
        }

        for (low, high), adjustment in self.calibration_map.items():
            bucket_name = f"{int(low*100)}-{int(high*100)}%"
            stats["buckets"][bucket_name] = {
                "adjustment_factor": adjustment,
                "needs_adjustment": not (0.9 <= adjustment <= 1.1),
            }

        return stats
