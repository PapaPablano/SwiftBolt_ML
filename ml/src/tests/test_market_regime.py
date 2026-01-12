import pandas as pd
import pytest

from src.features.market_regime import MarketRegimeDetector, add_market_regime_features


def test_market_regime_graceful_with_constant_prices(monkeypatch):
    data = {
        "close": [100.0] * 60,
    }
    df = pd.DataFrame(data)
    n_states = MarketRegimeDetector().n_states

    # Force HMM fit failure to exercise fallback path
    def _raise_fit(*args, **kwargs):
        raise ValueError("boom")

    monkeypatch.setattr("src.features.market_regime.GaussianHMM.fit", _raise_fit)

    result = add_market_regime_features(df)

    assert len(result) == len(df)
    assert "hmm_regime" in result.columns
    prob_cols = [c for c in result.columns if c.startswith("hmm_regime_prob_")]
    # Defaults to 3 states
    assert len(prob_cols) == 3
    assert (result["hmm_regime"] == 0).all()
    expected_prob = 1 / n_states
    expected_probs = [expected_prob] * len(df)
    for col in prob_cols:
        assert result[col].to_numpy() == pytest.approx(expected_probs)
