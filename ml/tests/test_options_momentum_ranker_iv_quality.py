"""Tests for IV curve quality handling in OptionsMomentumRanker."""

import pandas as pd

from src.models.options_momentum_ranker import (
    IVStatistics,
    OptionsMomentumRanker,
)


def _sample_options_chain() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "contract_symbol": ["C1", "C2", "C3"],
            "strike": [100.0, 105.0, 110.0],
            "expiration": ["2024-03-15", "2024-03-15", "2024-03-15"],
            "side": ["call", "call", "call"],
            "bid": [1.0, 1.2, 1.4],
            "ask": [1.1, 1.3, 1.6],
            "mark": [1.05, 1.25, 1.5],
            "last_price": [1.05, 1.25, 1.5],
            "volume": [100, 120, 140],
            "openInterest": [500, 600, 700],
            "impliedVolatility": [0.20, 0.35, 0.55],
            "delta": [0.55, 0.50, 0.45],
            "gamma": [0.02, 0.02, 0.02],
            "theta": [-0.01, -0.01, -0.01],
            "vega": [0.10, 0.10, 0.10],
            "rho": [0.01, 0.01, 0.01],
        }
    )


def test_iv_curve_quality_flags_applied():
    iv_stats = IVStatistics(
        iv_high=0.60,
        iv_low=0.15,
        iv_median=0.30,
        iv_current=0.35,
        days_of_data=252,
    )
    ranker = OptionsMomentumRanker()
    df = _sample_options_chain()

    ranked = ranker.rank_options(df, iv_stats=iv_stats)

    assert "iv_curve_ok" in ranked.columns
    assert "iv_data_quality_score" in ranked.columns
    assert ranked["iv_curve_ok"].dtype == bool
    assert (ranked["iv_data_quality_score"] <= 1.0).all()


def test_iv_curve_penalty_reduces_value_score():
    iv_stats = IVStatistics(
        iv_high=0.60,
        iv_low=0.15,
        iv_median=0.30,
        iv_current=0.35,
        days_of_data=252,
    )
    ranker = OptionsMomentumRanker()
    df = _sample_options_chain()

    ranked = ranker.rank_options(df, iv_stats=iv_stats)

    assert (ranked["iv_curve_ok"] == False).any()  # noqa: E712
    assert (ranked["value_score"] < 100).any()
