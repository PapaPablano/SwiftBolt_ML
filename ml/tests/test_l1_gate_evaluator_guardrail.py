"""
Guardrail: L1 gate evaluator must never write to Supabase.

File: ml/tests/test_l1_gate_evaluator_guardrail.py

The evaluator is a pure evaluation harness; it must not insert, update, or upsert
any data. This test verifies that by patching db write methods and asserting
they are never called during compute_loss_series.

Patch targets (src.data.supabase_db.db instance):
- insert_intraday_forecast
- save_indicator_snapshot

The evaluator does not import db; these patches catch writes from any transitive
dependency in the evaluation call chain.
"""

import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch


@pytest.fixture
def synthetic_m15_df():
    """Minimal 15m OHLC data for evaluator (enough for 1 origin)."""
    n = 150  # train_bars=120 + test room; 1 origin with max_origins=1
    np.random.seed(42)
    close = 100 + np.cumsum(np.random.randn(n) * 0.2)
    high = close + np.abs(np.random.randn(n) * 0.1)
    low = close - np.abs(np.random.randn(n) * 0.1)
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    return pd.DataFrame(
        {
            "ts": pd.date_range("2025-01-01 09:30", periods=n, freq="15min"),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": np.random.randint(1000, 10000, n),
        }
    )


def test_l1_gate_evaluator_never_writes_to_supabase(synthetic_m15_df):
    """
    Compute loss series must not trigger any Supabase insert/update/upsert.

    Patches db write methods to raise if called; evaluator must never touch them.
    """
    from src.data.supabase_db import db

    def fail_on_write(*args, **kwargs):
        raise AssertionError(
            "L1 gate evaluator must not write to Supabase; "
            "evaluation harness must be read-only"
        )

    with patch.object(db, "insert_intraday_forecast", side_effect=fail_on_write), \
         patch.object(db, "save_indicator_snapshot", side_effect=fail_on_write):
        from src.evaluation.l1_gate_evaluator import L1GateEvaluator

        evaluator = L1GateEvaluator(
            train_bars=120,
            test_bars=20,
            step_bars=20,
            max_origins_per_symbol=1,  # 1 origin for fast guardrail check
        )
        # Run evaluation; may produce 0 rows if data insufficient
        evaluator.compute_loss_series("TEST", synthetic_m15_df)


def test_l1_gate_index_alignment(synthetic_m15_df):
    """
    Guardrail: origin_ts must equal timestamp at t; actual_4 must come from t+LOOKAHEAD_BARS.

    Prevents off-by-one bugs from reindexing that could look like "performance."
    """
    from src.data.supabase_db import db
    from src.evaluation.l1_gate_evaluator import L1GateEvaluator, LOOKAHEAD_BARS

    def noop(*args, **kwargs):
        pass

    with patch.object(db, "insert_intraday_forecast", side_effect=noop), \
         patch.object(db, "save_indicator_snapshot", side_effect=noop):
        evaluator = L1GateEvaluator(
            train_bars=120,
            test_bars=20,
            step_bars=20,
            max_origins_per_symbol=5,
        )
        loss_df = evaluator.compute_loss_series("TEST", synthetic_m15_df)

    if len(loss_df) == 0:
        pytest.skip("Insufficient data for index alignment test")

    df = synthetic_m15_df.sort_values("ts").reset_index(drop=True)
    for _, row in loss_df.iterrows():
        # Find origin index t from origin_ts
        ts = pd.Timestamp(row["origin_ts"])
        mask = (df["ts"] == ts) | (df["ts"].astype(str).str[:19] == str(ts)[:19])
        matches = df[mask]
        assert len(matches) >= 1, f"origin_ts {row['origin_ts']} not found in df"
        t = int(matches.index[0])
        idx_actual = t + LOOKAHEAD_BARS
        assert idx_actual < len(df), "actual_4 index out of bounds"
        expected_actual = float(df["close"].iloc[idx_actual])
        assert abs(row["actual_4"] - expected_actual) < 1e-6, (
            f"actual_4 must come from t+LOOKAHEAD_BARS: got {row['actual_4']} "
            f"expected {expected_actual}"
        )


def test_run_dm_test_insufficient_sample_size():
    """
    Power check: run_dm_test fails fast when n_origins < 100.
    """
    from src.evaluation.l1_gate_evaluator import L1GateEvaluator

    evaluator = L1GateEvaluator()
    # Create loss_df with < 100 rows
    n = 50
    loss_df = pd.DataFrame(
        {
            "symbol": ["TEST"] * n,
            "origin_ts": pd.date_range("2025-01-01", periods=n, freq="15min"),
            "actual_4": 100.0 + np.random.randn(n) * 0.5,
            "pred_4": 100.0 + np.random.randn(n) * 0.5,
            "base_4": 100.0,
            "d": np.random.randn(n) * 0.1,
        }
    )
    result = evaluator.run_dm_test(loss_df)
    assert "Insufficient sample size" in result.interpretation
    assert not result.is_significant
    assert np.isnan(result.p_value)


def test_run_dm_test_sufficient_sample_size():
    """When n_origins >= 100, DM test runs normally."""
    from src.evaluation.l1_gate_evaluator import L1GateEvaluator

    evaluator = L1GateEvaluator()
    n = 150
    np.random.seed(42)
    loss_df = pd.DataFrame(
        {
            "symbol": ["TEST"] * n,
            "origin_ts": pd.date_range("2025-01-01", periods=n, freq="15min"),
            "actual_4": 100.0 + np.random.randn(n) * 0.5,
            "pred_4": 100.0 + np.random.randn(n) * 0.5,
            "base_4": 100.0,
            "d": np.random.randn(n) * 0.1,
        }
    )
    result = evaluator.run_dm_test(loss_df)
    assert "Insufficient sample size" not in result.interpretation
    assert not np.isnan(result.p_value)
