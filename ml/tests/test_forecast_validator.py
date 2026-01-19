"""Tests for forecast validator and audit trail diff logging."""

import sys
import types

from src.forecast_validator import (
    ForecastOutcome,
    ForecastValidator,
    evaluate_single_forecast,
    summarize_forecast_accuracy,
)
if "imblearn" not in sys.modules:
    imblearn_module = types.ModuleType("imblearn")
    over_sampling_module = types.ModuleType("imblearn.over_sampling")
    setattr(over_sampling_module, "SMOTE", object)
    sys.modules["imblearn"] = imblearn_module
    sys.modules["imblearn.over_sampling"] = over_sampling_module

settings_stub = types.SimpleNamespace(
    log_level="INFO",
    supabase_url="http://localhost",
    supabase_key="test-key",
    supabase_service_role_key="test-key",
    enable_intraday_calibration=False,
    intraday_calibration_min_samples=50,
    min_bars_for_training=100,
    min_bars_for_high_confidence=504,
    forecast_horizons=["1D"],
    symbols_to_process=[],
)
sys.modules["config.settings"] = types.SimpleNamespace(settings=settings_stub)

from src import forecast_job  # noqa: E402


def test_forecast_validator_generate_report():
    validator = ForecastValidator()
    report = validator.generate_report(
        [
            {
                "symbol": "AAPL",
                "forecast_date": "2024-01-01",
                "forecast_direction": "BULLISH",
                "forecast_confidence": 0.65,
                "forecast_target": 100.0,
                "upper_band": 102.0,
                "lower_band": 98.0,
                "actual_open": 99.0,
                "actual_close": 101.0,
                "actual_high": 101.5,
                "actual_low": 98.5,
            }
        ]
    )

    assert report.summary["total_forecasts"] == 1
    assert report.directional_accuracy.total_forecasts == 1


def test_audit_trail_diff_logging(monkeypatch):
    calls = []

    def fake_insert_forecast_change(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(
        forecast_job.db,
        "insert_forecast_change",
        fake_insert_forecast_change,
    )

    existing_forecast = {
        "overall_label": "bullish",
        "confidence": 0.6,
        "synthesis_data": {
            "target": 150.0,
            "upper_band": 152.0,
            "lower_band": 148.0,
            "layers_agreeing": 2,
        },
    }
    new_forecast = {
        "label": "bearish",
        "confidence": 0.7,
        "synthesis": {
            "target": 149.0,
            "upper_band": 151.0,
            "lower_band": 147.0,
            "layers_agreeing": 3,
        },
    }

    forecast_job._record_forecast_audit_changes(
        forecast_id="test-forecast",
        existing_forecast=existing_forecast,
        forecast=new_forecast,
    )

    fields = {call["field_name"] for call in calls}
    assert "overall_label" in fields
    assert "confidence" in fields
    assert "synthesis.target" in fields
    assert "synthesis.upper_band" in fields
    assert "synthesis.lower_band" in fields
    assert "synthesis.layers_agreeing" in fields


def test_evaluate_single_forecast_outcomes():
    full_hit = evaluate_single_forecast(
        forecast_low=95.0,
        forecast_mid=100.0,
        forecast_high=105.0,
        horizon_days=1,
        actual_close=100.5,
        prior_close=99.0,
    )
    assert full_hit.outcome == ForecastOutcome.FULL_HIT
    assert full_hit.direction_correct is True
    assert full_hit.within_tolerance is True

    directional_hit = evaluate_single_forecast(
        forecast_low=95.0,
        forecast_mid=100.0,
        forecast_high=105.0,
        horizon_days=1,
        actual_close=101.5,
        prior_close=99.0,
    )
    assert directional_hit.outcome == ForecastOutcome.DIRECTIONAL_HIT
    assert directional_hit.direction_correct is True

    directional_only = evaluate_single_forecast(
        forecast_low=95.0,
        forecast_mid=100.0,
        forecast_high=105.0,
        horizon_days=1,
        actual_close=106.0,
        prior_close=99.0,
    )
    assert directional_only.outcome == ForecastOutcome.DIRECTIONAL_ONLY
    assert directional_only.within_2x_tolerance is False

    miss = evaluate_single_forecast(
        forecast_low=95.0,
        forecast_mid=100.0,
        forecast_high=105.0,
        horizon_days=1,
        actual_close=96.0,
        prior_close=99.0,
    )
    assert miss.outcome == ForecastOutcome.MISS
    assert miss.direction_correct is False


def test_summarize_forecast_accuracy():
    evaluations = [
        evaluate_single_forecast(95, 100, 105, 1, 100, 99),
        evaluate_single_forecast(95, 100, 105, 1, 101.5, 99),
        evaluate_single_forecast(95, 100, 105, 1, 96, 99),
    ]
    summary = summarize_forecast_accuracy(evaluations)

    assert summary.total_forecasts == 3
    assert summary.outcome_counts[ForecastOutcome.FULL_HIT.value] == 1
    assert summary.outcome_counts[ForecastOutcome.DIRECTIONAL_HIT.value] == 1
    assert summary.outcome_counts[ForecastOutcome.MISS.value] == 1
    assert summary.directional_accuracy > 0


def test_should_run_forecast_bypasses_cache_on_event_refresh(monkeypatch):
    monkeypatch.setattr(forecast_job, "_should_skip_forecast", lambda *_: True)
    assert (
        forecast_job._should_run_forecast(
            "symbol-id",
            ["1D"],
            {"reason": "event"},
        )
        is True
    )

    assert (
        forecast_job._should_run_forecast(
            "symbol-id",
            ["1D"],
            None,
        )
        is False
    )
