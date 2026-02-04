import sys
from pathlib import Path
from typing import Dict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ML_ROOT = PROJECT_ROOT / "ml"
if str(ML_ROOT) not in sys.path:
    sys.path.insert(0, str(ML_ROOT))

import numpy as np
import pandas as pd
import pytest

from src.features.lookahead_checks import LookaheadViolation, run_synthetic_feature_guard
from src.features.temporal_indicators import compute_simplified_features
from src.forecast_synthesizer import ForecastSynthesizer
from src.models.baseline_forecaster import BaselineForecaster


def _build_monotonic_frame(rows: int = 400) -> pd.DataFrame:
    rows = max(rows, 60)
    base = np.arange(rows, dtype=float)
    dates = pd.date_range("2020-01-01", periods=rows, freq="B")
    return pd.DataFrame(
        {
            "ts": dates,
            "open": 100 + base * 0.25,
            "high": 100.5 + base * 0.25,
            "low": 99.5 + base * 0.25,
            "close": 100 + base * 0.25,
            "volume": 1_000_000 + base * 50,
        }
    )


def _minimal_supertrend() -> Dict:
    return {
        "current_trend": "NEUTRAL",
        "signal_strength": 5,
        "performance_index": 0.5,
        "atr": 2.0,
    }


def _minimal_sr_response() -> Dict:
    return {
        "levels": [],
        "support": {"nearest": 98.0, "distance_pct": 0.02},
        "resistance": {"nearest": 102.0, "distance_pct": 0.02},
    }


def _minimal_ml_result() -> Dict:
    return {
        "target": 101.0,
        "confidence": 0.55,
        "label": "bullish",
        "n_models": 3,
    }


def test_synthetic_feature_guard_detects_future_mutations():
    """
    Ensure helper raises if future-row tampering affects historical features.
    """
    run_synthetic_feature_guard()


@pytest.mark.parametrize("horizon", [1, 5, 10, 20])
def test_training_data_excludes_future_rows(horizon: int):
    df = _build_monotonic_frame(rows=420)
    df = compute_simplified_features(df)
    forecaster = BaselineForecaster()

    X, y = forecaster.prepare_training_data(df, horizon_days=horizon)
    assert not X.empty, "Expected at least one training sample"
    assert len(X) == len(y)

    feature_ts = pd.to_datetime(X["ts"])
    df_ts = pd.to_datetime(df["ts"])
    # Latest feature timestamp must trail the original dataframe by >= horizon bars.
    assert feature_ts.max() <= df_ts.iloc[-(horizon + 1)]


def test_forecast_synthesizer_rejects_t_columns(monkeypatch):
    monkeypatch.setenv("STRICT_LOOKAHEAD_CHECK", "1")
    synth = ForecastSynthesizer()

    df = pd.DataFrame(
        {
            "close[t]": [100.0, 101.0],
            "atr": [2.0, 2.1],
            "high": [101.0, 102.0],
            "low": [99.0, 100.0],
        }
    )

    with pytest.raises(LookaheadViolation):
        synth.generate_1d_forecast(
            current_price=101.0,
            df=df,
            supertrend_info=_minimal_supertrend(),
            sr_response=_minimal_sr_response(),
            ensemble_result=_minimal_ml_result(),
            symbol="TEST",
        )
