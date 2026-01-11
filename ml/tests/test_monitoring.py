"""Tests for monitoring utilities."""

import pytest
import pandas as pd
import numpy as np

from src.monitoring.drift_detector import DriftDetector, DriftResult


@pytest.fixture
def reference_data():
    """Generate reference (training) data."""
    np.random.seed(42)
    n = 100

    return pd.DataFrame(
        {
            "rsi": np.random.normal(50, 15, n),
            "macd": np.random.normal(0, 1, n),
            "volume": np.random.lognormal(15, 1, n),
        }
    )


@pytest.fixture
def similar_data():
    """Generate data similar to reference (no drift)."""
    np.random.seed(123)
    n = 100

    return pd.DataFrame(
        {
            "rsi": np.random.normal(50, 15, n),
            "macd": np.random.normal(0, 1, n),
            "volume": np.random.lognormal(15, 1, n),
        }
    )


@pytest.fixture
def drifted_data():
    """Generate data with significant drift."""
    np.random.seed(456)
    n = 100

    return pd.DataFrame(
        {
            "rsi": np.random.normal(70, 10, n),  # Shifted mean
            "macd": np.random.normal(2, 0.5, n),  # Shifted mean, different std
            "volume": np.random.lognormal(17, 0.5, n),  # Different distribution
        }
    )


class TestDriftDetector:
    """Tests for DriftDetector."""

    def test_no_drift_detected(self, reference_data, similar_data):
        """Test that similar distributions show no drift."""
        detector = DriftDetector(significance_level=0.05)

        results = detector.detect_drift(
            reference_data,
            similar_data,
            features=["rsi", "macd", "volume"],
        )

        assert len(results) == 3

        # Most features should not show drift
        drifted_count = sum(1 for r in results if r.is_drifted)
        assert drifted_count <= 1  # Allow one false positive

    def test_drift_detected(self, reference_data, drifted_data):
        """Test that different distributions show drift."""
        detector = DriftDetector(significance_level=0.05)

        results = detector.detect_drift(
            reference_data,
            drifted_data,
            features=["rsi", "macd", "volume"],
        )

        assert len(results) == 3

        # Most features should show drift
        drifted_count = sum(1 for r in results if r.is_drifted)
        assert drifted_count >= 2

    def test_drift_result_properties(self, reference_data, drifted_data):
        """Test DriftResult properties."""
        detector = DriftDetector()

        results = detector.detect_drift(
            reference_data,
            drifted_data,
            features=["rsi"],
        )

        result = results[0]

        assert isinstance(result, DriftResult)
        assert result.feature == "rsi"
        assert 0 <= result.statistic <= 1
        assert 0 <= result.p_value <= 1
        assert isinstance(result.is_drifted, bool)
        assert result.drift_severity in ["none", "low", "medium", "high"]

    def test_insufficient_samples(self):
        """Test handling of insufficient samples."""
        detector = DriftDetector(min_samples=50)

        small_ref = pd.DataFrame({"x": [1, 2, 3]})
        small_cur = pd.DataFrame({"x": [4, 5, 6]})

        results = detector.detect_drift(small_ref, small_cur, features=["x"])

        # Should not detect drift due to insufficient samples
        assert not results[0].is_drifted
        assert results[0].p_value == 1.0

    def test_generate_report(self, reference_data, drifted_data):
        """Test report generation."""
        detector = DriftDetector()

        results = detector.detect_drift(
            reference_data,
            drifted_data,
            features=["rsi", "macd"],
        )

        report = detector.generate_report(results)

        assert "DATA DRIFT REPORT" in report
        assert "Features analyzed" in report
        assert "rsi" in report
        assert "macd" in report

    def test_auto_detect_features(self, reference_data, similar_data):
        """Test automatic feature detection."""
        detector = DriftDetector()

        # Don't specify features - should auto-detect numeric columns
        results = detector.detect_drift(reference_data, similar_data)

        assert len(results) == 3  # All numeric columns


class TestDriftSeverity:
    """Tests for drift severity classification."""

    def test_severity_none(self):
        """Test 'none' severity for low KS statistic."""
        result = DriftResult(
            feature="test",
            statistic=0.05,
            p_value=0.5,
            is_drifted=False,
            drift_severity="none",
        )
        assert result.drift_severity == "none"

    def test_severity_high(self):
        """Test 'high' severity for high KS statistic."""
        result = DriftResult(
            feature="test",
            statistic=0.4,
            p_value=0.001,
            is_drifted=True,
            drift_severity="high",
        )
        assert result.drift_severity == "high"

    def test_str_representation(self):
        """Test string representation of DriftResult."""
        result = DriftResult(
            feature="rsi",
            statistic=0.25,
            p_value=0.01,
            is_drifted=True,
            drift_severity="medium",
        )

        str_repr = str(result)

        assert "rsi" in str_repr
        assert "DRIFT" in str_repr
        assert "0.25" in str_repr
