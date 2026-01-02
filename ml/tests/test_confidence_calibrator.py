"""Unit tests for ConfidenceCalibrator."""

import numpy as np
import pandas as pd
import pytest

from src.monitoring.confidence_calibrator import CalibrationResult, ConfidenceCalibrator


class TestConfidenceCalibrator:
    """Test suite for ConfidenceCalibrator."""

    def test_init(self):
        """Test calibrator initialization."""
        calibrator = ConfidenceCalibrator()
        assert not calibrator.is_fitted
        assert len(calibrator.calibration_map) == 0

    def test_fit_with_sufficient_samples(self):
        """Test fitting with enough samples per bucket."""
        np.random.seed(42)
        n_samples = 300

        # Create forecasts with known miscalibration
        confidences = np.random.uniform(0.5, 0.9, n_samples)
        predicted_labels = np.random.choice(["bullish", "neutral", "bearish"], n_samples)

        # 70% accuracy (lower than confidence suggests)
        actual_labels = []
        for i in range(n_samples):
            if np.random.random() < 0.7:
                actual_labels.append(predicted_labels[i])
            else:
                other = [l for l in ["bullish", "neutral", "bearish"] if l != predicted_labels[i]]
                actual_labels.append(np.random.choice(other))

        forecasts = pd.DataFrame({
            "confidence": confidences,
            "predicted_label": predicted_labels,
            "actual_label": actual_labels,
        })

        calibrator = ConfidenceCalibrator()
        results = calibrator.fit(forecasts, min_samples_per_bucket=20)

        assert calibrator.is_fitted
        assert len(results) > 0
        assert len(calibrator.calibration_map) > 0

    def test_fit_with_insufficient_samples(self):
        """Test fitting with too few samples uses default adjustment."""
        forecasts = pd.DataFrame({
            "confidence": [0.75, 0.76],
            "predicted_label": ["bullish", "bearish"],
            "actual_label": ["bullish", "bullish"],
        })

        calibrator = ConfidenceCalibrator()
        calibrator.fit(forecasts, min_samples_per_bucket=30)

        # Should still be fitted but with default adjustments
        assert calibrator.is_fitted
        # All buckets should have 1.0 adjustment due to insufficient data
        for adjustment in calibrator.calibration_map.values():
            assert adjustment == 1.0

    def test_calibrate_before_fit(self):
        """Test that calibrating before fit returns original value."""
        calibrator = ConfidenceCalibrator()
        original = 0.75
        calibrated = calibrator.calibrate(original)
        assert calibrated == original

    def test_calibrate_after_fit(self):
        """Test calibration adjusts confidence."""
        np.random.seed(42)
        n_samples = 200

        # Create systematically overconfident predictions
        confidences = np.random.uniform(0.7, 0.85, n_samples)
        predicted_labels = np.random.choice(["bullish", "bearish"], n_samples)

        # Only 50% accuracy despite 75%+ confidence
        actual_labels = []
        for i in range(n_samples):
            if np.random.random() < 0.5:
                actual_labels.append(predicted_labels[i])
            else:
                actual_labels.append("bearish" if predicted_labels[i] == "bullish" else "bullish")

        forecasts = pd.DataFrame({
            "confidence": confidences,
            "predicted_label": predicted_labels,
            "actual_label": actual_labels,
        })

        calibrator = ConfidenceCalibrator()
        calibrator.fit(forecasts, min_samples_per_bucket=10)

        # High confidence should be adjusted down
        original = 0.80
        calibrated = calibrator.calibrate(original)

        # Should be lower than original due to overconfidence
        assert calibrated < original

    def test_calibrate_respects_bounds(self):
        """Test calibration stays within 0.40-0.95 bounds."""
        calibrator = ConfidenceCalibrator()

        # Mock extreme adjustments
        calibrator.calibration_map = {
            (0.4, 0.5): 0.1,  # Would push below minimum
            (0.9, 1.0): 2.0,  # Would push above maximum
        }
        calibrator.is_fitted = True

        # Very low adjustment shouldn't go below 0.40
        low_calibrated = calibrator.calibrate(0.45)
        assert low_calibrated >= 0.40

        # High adjustment shouldn't go above 0.95
        high_calibrated = calibrator.calibrate(0.95)
        assert high_calibrated <= 0.95

    def test_calibrate_batch(self):
        """Test batch calibration on Series."""
        calibrator = ConfidenceCalibrator()
        calibrator.calibration_map = {(0.7, 0.8): 0.9}
        calibrator.is_fitted = True

        confidences = pd.Series([0.75, 0.76, 0.50])
        calibrated = calibrator.calibrate_batch(confidences)

        assert len(calibrated) == 3
        # 0.75 and 0.76 should be adjusted
        assert calibrated.iloc[0] < 0.75
        assert calibrated.iloc[1] < 0.76
        # 0.50 is not in mapped bucket, should stay same
        assert calibrated.iloc[2] == 0.50

    def test_get_calibration_report_before_fit(self):
        """Test report before fitting."""
        calibrator = ConfidenceCalibrator()
        report = calibrator.get_calibration_report()
        assert "not fitted" in report.lower()

    def test_get_calibration_report_after_fit(self):
        """Test report after fitting."""
        calibrator = ConfidenceCalibrator()
        calibrator.calibration_map = {
            (0.5, 0.6): 1.0,
            (0.7, 0.8): 0.85,
        }
        calibrator.is_fitted = True

        report = calibrator.get_calibration_report()

        assert "Calibration Report" in report
        assert "50-60%" in report
        assert "70-80%" in report
        assert "ADJUST" in report  # 0.85 is outside OK range

    def test_get_calibration_stats(self):
        """Test stats dictionary output."""
        calibrator = ConfidenceCalibrator()

        # Before fit
        stats = calibrator.get_calibration_stats()
        assert stats["is_fitted"] is False

        # After fit
        calibrator.calibration_map = {(0.6, 0.7): 1.05}
        calibrator.is_fitted = True

        stats = calibrator.get_calibration_stats()
        assert stats["is_fitted"] is True
        assert "60-70%" in stats["buckets"]
        assert stats["buckets"]["60-70%"]["needs_adjustment"] is False  # 1.05 is OK

    def test_calibration_result_dataclass(self):
        """Test CalibrationResult dataclass."""
        result = CalibrationResult(
            bucket="70-80%",
            predicted_confidence=0.75,
            actual_accuracy=0.60,
            n_samples=100,
            is_calibrated=False,
            adjustment_factor=0.80,
        )

        assert result.bucket == "70-80%"
        assert result.predicted_confidence == 0.75
        assert result.actual_accuracy == 0.60
        assert result.n_samples == 100
        assert result.is_calibrated is False
        assert result.adjustment_factor == 0.80
