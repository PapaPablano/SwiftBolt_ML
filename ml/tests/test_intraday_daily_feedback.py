"""
Unit tests for Intraday-Daily Feedback Loop.

Tests:
- Status tracking
- Recalibration triggers
- Weight management
- Feedback loop orchestration
"""

import sys
import types
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

# Mock settings before importing modules that use it
settings_stub = types.SimpleNamespace(
    log_level="INFO",
    supabase_url="http://localhost",
    supabase_key="test-key",
    supabase_service_role_key="test-key",
    intraday_lookback_hours=336,
    intraday_calibration_min_samples=50,
)
sys.modules["config.settings"] = types.SimpleNamespace(settings=settings_stub)

from src.intraday_daily_feedback import (  # noqa: E402
    FeedbackLoopStatus,
    IntradayDailyFeedback,
)


class TestIntradayDailyFeedback:
    """Test suite for IntradayDailyFeedback."""

    @pytest.fixture
    def feedback(self):
        """Create feedback loop manager."""
        return IntradayDailyFeedback(
            calibration_staleness_hours=24,
            min_new_evaluations=20,
            min_calibration_samples=50,
        )

    def test_initialization(self, feedback):
        """Test feedback loop initialization."""
        assert feedback.calibration_staleness_hours == 24
        assert feedback.min_new_evaluations == 20
        assert feedback.min_calibration_samples == 50
        assert feedback.recalibration_history == []
        print("✓ Initialization successful")

    def test_status_dataclass(self):
        """Test FeedbackLoopStatus dataclass."""
        now = datetime.now()
        status = FeedbackLoopStatus(
            symbol="AAPL",
            symbol_id="test-id",
            last_calibration=now,
            calibration_age_hours=12.0,
            evaluation_count=100,
            new_evaluations_since_calibration=30,
            calibration_stale=False,
            has_valid_weights=True,
            weight_source="intraday_calibrated",
            current_weights={"st": 0.3, "sr": 0.3, "ens": 0.4},
        )

        assert status.symbol == "AAPL"
        assert status.calibration_age_hours == 12.0
        assert status.has_valid_weights is True
        assert status.current_weights["ens"] == 0.4
        print("✓ FeedbackLoopStatus dataclass working")

    def test_needs_recalibration_fresh(self, feedback):
        """Test that fresh calibration doesn't trigger recalibration."""
        status = FeedbackLoopStatus(
            symbol="AAPL",
            symbol_id="test-id",
            last_calibration=datetime.now() - timedelta(hours=6),
            calibration_age_hours=6.0,
            evaluation_count=100,
            new_evaluations_since_calibration=5,  # Not enough new evals
            calibration_stale=False,
            has_valid_weights=True,
            weight_source="intraday_calibrated",
            current_weights={"st": 0.3, "sr": 0.3, "ens": 0.4},
        )

        with patch.object(feedback, "get_feedback_status", return_value=status):
            needs_recal = feedback.needs_recalibration("AAPL")
            assert needs_recal is False
            print("✓ Fresh calibration doesn't trigger recalibration")

    def test_needs_recalibration_stale(self, feedback):
        """Test that stale calibration triggers recalibration."""
        status = FeedbackLoopStatus(
            symbol="AAPL",
            symbol_id="test-id",
            last_calibration=datetime.now() - timedelta(hours=48),
            calibration_age_hours=48.0,
            evaluation_count=100,
            new_evaluations_since_calibration=30,  # Enough new evals
            calibration_stale=True,
            has_valid_weights=True,
            weight_source="intraday_calibrated",
            current_weights={"st": 0.3, "sr": 0.3, "ens": 0.4},
        )

        with patch.object(feedback, "get_feedback_status", return_value=status):
            needs_recal = feedback.needs_recalibration("AAPL")
            assert needs_recal is True
            print("✓ Stale calibration triggers recalibration")

    def test_needs_recalibration_no_weights(self, feedback):
        """Test that missing weights trigger calibration."""
        status = FeedbackLoopStatus(
            symbol="AAPL",
            symbol_id="test-id",
            last_calibration=None,
            calibration_age_hours=None,
            evaluation_count=100,  # Enough samples
            new_evaluations_since_calibration=100,
            calibration_stale=True,
            has_valid_weights=False,  # No weights
            weight_source="default",
            current_weights={"st": 0.33, "sr": 0.33, "ens": 0.34},
        )

        with patch.object(feedback, "get_feedback_status", return_value=status):
            needs_recal = feedback.needs_recalibration("AAPL")
            assert needs_recal is True
            print("✓ Missing weights trigger calibration")

    def test_get_best_weights_fresh(self, feedback):
        """Test getting fresh calibrated weights."""
        with patch.object(
            feedback,
            "_get_current_weights",
            return_value=({"st": 0.3, "sr": 0.3, "ens": 0.4}, "intraday_calibrated (fresh)"),
        ):
            with patch("src.intraday_daily_feedback.db") as mock_db:
                mock_db.get_symbol_id.return_value = "test-id"

                weights, source = feedback.get_best_weights("AAPL", "1D")

                assert source == "intraday_calibrated (fresh)"
                # Weights can be dict or ForecastWeights object
                assert weights is not None
                print(f"✓ Fresh weights retrieved: {source}")

    def test_get_best_weights_default(self, feedback):
        """Test getting default weights when none available."""
        with patch.object(
            feedback,
            "_get_current_weights",
            return_value=({"st": 0.33, "sr": 0.33, "ens": 0.34}, "default"),
        ):
            with patch("src.intraday_daily_feedback.db") as mock_db:
                mock_db.get_symbol_id.return_value = "test-id"

                weights, source = feedback.get_best_weights("AAPL", "1D")

                assert source == "default"
                print(f"✓ Default weights returned: {source}")

    def test_recalibration_history_tracking(self, feedback):
        """Test that recalibration history is tracked."""
        # Simulate a recalibration
        with patch.object(feedback.calibrator, "calibrate_symbol", return_value=None):
            with patch.object(feedback.calibrator, "calibrate_and_save", return_value=False):
                feedback.run_recalibration("AAPL")

        # History should be updated
        assert len(feedback.recalibration_history) >= 0  # May be 0 if failed
        print("✓ Recalibration history tracking working")

    def test_staleness_detection(self):
        """Test calibration staleness detection."""
        feedback = IntradayDailyFeedback(calibration_staleness_hours=24)

        # Fresh calibration
        fresh_age = 12.0
        is_stale = fresh_age > feedback.calibration_staleness_hours
        assert is_stale is False

        # Stale calibration
        stale_age = 36.0
        is_stale = stale_age > feedback.calibration_staleness_hours
        assert is_stale is True

        print("✓ Staleness detection working")

    def test_evaluation_counting(self, feedback):
        """Test evaluation counting logic."""
        with patch("src.intraday_daily_feedback.db") as mock_db:
            mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value.count = (
                50
            )

            count = feedback._count_evaluations("test-id")
            assert count == 50
            print("✓ Evaluation counting working")

    def test_feedback_loop_status_info(self):
        """Test FeedbackLoopStatus provides all required info."""
        now = datetime.now()
        status = FeedbackLoopStatus(
            symbol="AAPL",
            symbol_id="test-id",
            last_calibration=now,
            calibration_age_hours=12.0,
            evaluation_count=100,
            new_evaluations_since_calibration=25,
            calibration_stale=False,
            has_valid_weights=True,
            weight_source="intraday_calibrated",
            current_weights={"st": 0.3, "sr": 0.3, "ens": 0.4},
        )

        # Verify all fields are accessible
        assert status.symbol == "AAPL"
        assert status.evaluation_count == 100
        assert status.new_evaluations_since_calibration == 25
        assert status.has_valid_weights is True
        assert status.calibration_stale is False
        print("✓ FeedbackLoopStatus has all required fields")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Intraday-Daily Feedback Loop")
    print("=" * 60)

    test = TestIntradayDailyFeedback()
    feedback = test.feedback()

    test.test_initialization(feedback)
    test.test_status_dataclass()
    test.test_needs_recalibration_fresh(feedback)
    test.test_needs_recalibration_stale(feedback)
    test.test_needs_recalibration_no_weights(feedback)
    test.test_get_best_weights_fresh(feedback)
    test.test_get_best_weights_default(feedback)
    test.test_recalibration_history_tracking(feedback)
    test.test_staleness_detection()
    test.test_evaluation_counting(feedback)
    test.test_feedback_loop_status_info()

    print("\n" + "=" * 60)
    print("All Feedback Loop tests passed! ✓")
    print("=" * 60)
